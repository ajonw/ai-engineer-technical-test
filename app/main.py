"""FastAPI receipt dashboard"""
from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .db import connection, init_db, save_receipt
from .qa import answer_question
from .receipt import extract_text, parse_receipt
from .vector import index_receipt, search_receipts
from .agent import answer_with_local_llm

MAX_BYTES = 8 * 1024 * 1024
ALLOWED_SUFFIX = {'.png', '.jpg', '.jpeg', '.webp', '.pdf'}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title='Receipt Knowledge Agent', version='1.0', lifespan=lifespan)


class AskBody(BaseModel):
    question: str = Field(min_length=4, max_length=500)


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=200)


@app.get('/', response_class=HTMLResponse)
def homepage():
    return HTMLResponse('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Receipt Knowledge Agent</title>
<style>body{font-family:system-ui,Arial,sans-serif;background:#f4f7fb;color:#19253a;max-width:850px;margin:2rem auto;padding:0 1rem}h1{font-size:2rem}
section{background:white;border:1px solid #dde4ee;border-radius:12px;padding:1.3rem;margin:1.2rem 0;box-shadow:0 1px 4px #0001}
input,button{font:inherit;padding:.7rem;border:1px solid #b9c6d9;border-radius:7px}input[type=text]{width:min(95%,650px);margin-bottom:.6rem}button{background:#1557a5;color:white;cursor:pointer;border:0}button:hover{background:#0d407c}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eff4fa;padding:1rem;border-radius:7px;font-size:.9rem}p{line-height:1.5;color:#43516b}</style></head><body>
<h1>Receipt Knowledge Agent</h1><p>Upload a food receipt image or PDF, review extracted fields, and query your own receipt database. OCR fields can be inaccurate; verify amounts.</p>
<section><h2>1. Upload receipt</h2><form id="upload"><input type="file" name="file" accept=".png,.jpg,.jpeg,.webp,.pdf" required> <button>Read receipt</button></form><pre id="uploadResult">Waiting for upload...</pre></section>
<section><h2>2. Ask about purchases</h2><p>Examples: "What food did I buy yesterday?", "Give me total expenses for food on 20 June 2026", "Where did I buy hamburger from last 7 days?"</p>
<form id="ask"><input name="question" type="text" required placeholder="What food did I buy yesterday?"> <button>Ask (SQL tools)</button> <button type="button" onclick="askLLM()">Ask via Ollama</button></form><pre id="answer">Answers appear here.</pre></section>
<section><h2>3. Search vector database</h2><p>Demonstration uses hashed-word vectors with manual cosine re-ranking; not a semantic embedding model.</p>
<form id="search"><input name="query" type="text" required placeholder="burger coffee"> <button>Search</button></form><pre id="searchResult">Search results appear here.</pre></section>
<section><h2>Stored receipts</h2><button onclick="loadReceipts()">Refresh list</button><pre id="receipts">Click refresh.</pre></section>
<script>
function show(id,data){document.getElementById(id).textContent=typeof data==='string'?data:JSON.stringify(data,null,2)}
async function submit(url,body,isForm,id){show(id,'Processing...');try{const r=await fetch(url,{method:'POST',headers:isForm?{}:{'Content-Type':'application/json'},body:isForm?body:JSON.stringify(body)});const x=await r.json();show(id,x);if(r.ok&&id==='uploadResult')loadReceipts();}catch(e){show(id,String(e))}}
document.getElementById('upload').onsubmit=e=>{e.preventDefault();submit('/receipts/upload',new FormData(e.target),true,'uploadResult')};
document.getElementById('ask').onsubmit=e=>{e.preventDefault();submit('/ask',{question:e.target.elements.namedItem('question').value},false,'answer')};
document.getElementById('search').onsubmit=e=>{e.preventDefault();submit('/semantic-search',{query:e.target.elements.namedItem('query').value},false,'searchResult')};
function askLLM(){submit('/ask/agent',{question:document.querySelector('#ask input').value},false,'answer')}
async function loadReceipts(){try{const r=await fetch('/receipts');show('receipts',await r.json())}catch(e){show('receipts',String(e))}}
</script></body></html>''')


@app.post('/receipts/upload')
async def upload_receipt(file: UploadFile = File(...)):
    filename = Path(file.filename or '').name
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(400, 'Upload a PNG, JPG, WEBP, or PDF file')
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Maximum file size is 8 MiB')
    if not data:
        raise HTTPException(400, 'Empty file')
    try:
        text = extract_text(data, filename)
        if not text.strip():
            raise ValueError('No text detected in receipt. Try a clearer scan or photo.')
        parsed = parse_receipt(text)
        digest = hashlib.sha256(data).hexdigest()
        receipt_id, created = save_receipt(parsed, text, filename, digest)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Retry indexing on duplicate uploads in case the earlier Qdrant write failed.
    indexing = 'indexed'
    try:
        index_receipt(receipt_id, text, parsed['merchant'])
    except Exception as exc:
        indexing = f'not indexed (Qdrant unavailable: {type(exc).__name__})'
    return {'receipt_id': receipt_id, 'created': created, 'parsed': parsed,
            'ocr_text': text[:2000], 'vector_index_status': indexing}


@app.get('/receipts')
def list_receipts():
    with connection() as conn:
        rows = conn.execute('''SELECT id, merchant, purchased_at, total, currency, original_filename
                               FROM receipts ORDER BY id DESC LIMIT 100''').fetchall()
        return [dict(row) for row in rows]


@app.post('/ask')
def ask(payload: AskBody):
    try:
        return answer_question(payload.question)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/ask/agent')
def ask_agent(payload: AskBody):
    try:
        return answer_with_local_llm(payload.question)
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise HTTPException(503, f'Local Ollama service unavailable: {type(exc).__name__}') from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/semantic-search')
def semantic_search(payload: SearchBody):
    try:
        return {'results': search_receipts(payload.query)}
    except Exception as exc:
        raise HTTPException(503, f'Qdrant unavailable: {type(exc).__name__}') from exc


@app.get('/health')
def health():
    return {'status': 'ok'}
