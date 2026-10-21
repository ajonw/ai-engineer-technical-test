"""Optional local LLM tool selector using Ollama's structured JSON output.
"""
from __future__ import annotations

import json
import os
from typing import Literal
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from pydantic import BaseModel, Field

from .qa import date_range, execute_tool


class ToolSelection(BaseModel):
    intent: Literal['items', 'expenses', 'where']
    item: str | None = Field(default=None, max_length=120)


def select_tool(question: str) -> ToolSelection:
    url = os.getenv('OLLAMA_URL', '').rstrip('/')
    if not url:
        raise ConnectionError('OLLAMA_URL is not configured; use /ask for deterministic questions.')
    system = ("Classify the user's food receipt question. Choose exactly one intent: "
              "'items' to list foods bought, 'expenses' to total costs, or 'where' "
              "to find merchants for a named food. For 'where' provide only the product "
              "name in 'item'. Return JSON matching the schema; do not generate SQL, "
              "dates, answers, or extra fields. If ambiguous, choose 'items'.")
    payload = {
        'model': os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct'),
        'stream': False,
        'format': ToolSelection.model_json_schema(),
        'options': {'temperature': 0},
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': question}],
    }
    request = Request(url + '/api/chat', data=json.dumps(payload).encode('utf-8'),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=50) as response:
        content = json.load(response)['message']['content']
    return ToolSelection.model_validate_json(content)


def answer_with_local_llm(question: str) -> dict:
    # Validate date using user input, not a model-generated value.
    start, end, note = date_range(question)
    selection = select_tool(question)
    if selection.intent == 'where' and not (selection.item or '').strip():
        raise ValueError('Model did not provide a product for the merchant-search tool.')
    result = execute_tool(selection.intent, start, end, item=selection.item, note=note)
    result['agent'] = 'Ollama selected a validated SQL tool; the database generated the facts.'
    return result
