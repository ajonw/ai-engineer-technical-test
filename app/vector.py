"""Qdrant over plain HTTP; cosine similarity implemented with standard Python.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

DIM = 128
COLLECTION = 'receipts'


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError('Vector dimensions must match')
    if not a:
        raise ValueError('Vectors must not be empty')
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def text_vector(text: str, dimension: int = DIM) -> list[float]:
    """Signed feature hashing into a fixed-dimensional vector, no ML library."""
    vector = [0.0] * dimension
    for word in re.findall(r'\w+', text.lower(), flags=re.UNICODE):
        digest = hashlib.blake2b(word.encode('utf-8'), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], 'little') % dimension
        sign = 1 if digest[4] & 1 else -1
        vector[bucket] += sign
    return vector


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    base = os.getenv('QDRANT_URL', 'http://localhost:6333').rstrip('/')
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if os.getenv('QDRANT_API_KEY'):
        headers['api-key'] = os.environ['QDRANT_API_KEY']
    request = Request(base + path, data=data, headers=headers, method=method)
    with urlopen(request, timeout=3) as result:
        return json.load(result)


def ensure_collection() -> None:
    try:
        _request('GET', f'/collections/{COLLECTION}')
    except HTTPError as exc:
        if exc.code != 404:
            raise
        _request('PUT', f'/collections/{COLLECTION}', {
            'vectors': {'size': DIM, 'distance': 'Cosine'},
        })


def index_receipt(receipt_id: int, searchable_text: str, merchant: str) -> None:
    ensure_collection()
    _request('PUT', f'/collections/{COLLECTION}/points?wait=true', {
        'points': [{
            'id': receipt_id,
            'vector': text_vector(searchable_text),
            'payload': {'receipt_id': receipt_id, 'merchant': merchant},
        }],
    })


def search_receipts(query: str, limit: int = 5) -> list[dict]:
    """Get candidates from Qdrant, then manually re-score via cosine."""
    ensure_collection()
    query_vector = text_vector(query)
    data = _request('POST', f'/collections/{COLLECTION}/points/query', {
        'query': query_vector, 'limit': min(max(1, limit * 3), 100),
        'with_vector': True, 'with_payload': True,
    })
    output = []
    for point in data.get('result', {}).get('points', []):
        vector = point.get('vector')
        if not isinstance(vector, list):
            continue
        output.append({
            'receipt_id': point['id'],
            'merchant': point.get('payload', {}).get('merchant'),
            'manual_cosine': round(cosine_similarity(query_vector, vector), 5),
        })
    return sorted(output, key=lambda p: p['manual_cosine'], reverse=True)[:limit]
