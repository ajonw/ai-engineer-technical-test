"""Grounded database 'AI tools' for the three assessment example questions.
"""
from __future__ import annotations

import re
import os
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from .db import connection


def current_day() -> date:
    try:
        return datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE', 'Asia/Jakarta'))).date()
    except KeyError:
        return datetime.now(ZoneInfo('UTC')).date()


def date_range(question: str, today: date | None = None) -> tuple[date, date, str]:
    from dateutil import parser
    today = today or current_day()
    text = question.lower()
    if 'yesterday' in text or 'kemarin' in text:
        value = today - timedelta(days=1)
        return value, value, ''
    if re.search(r'last\s+7\s+days?|past\s+7\s+days?|7\s+hari\s+terakhir', text):
        return today - timedelta(days=6), today, ''
    if 'today' in text or 'hari ini' in text:
        return today, today, ''
    match = re.search(r'\b(\d{1,2}\s+[a-zA-Z]+(?:\s+\d{4})?|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})\b', question, re.I)
    if match:
        raw = match.group(1)
        try:
            parsed = parser.parse(raw, dayfirst=not raw.startswith('20'), default=datetime(today.year, 1, 1))
            value = parsed.date()
            assumed = '' if re.search(r'\b\d{4}\b', raw) else f' (assuming year {today.year})'
            return value, value, assumed
        except (ValueError, OverflowError):
            pass
    raise ValueError('Please specify a time range: yesterday, today, last 7 days, or a date such as 20 June 2026.')


def classify(question: str) -> str:
    q = question.lower()
    if any(term in q for term in ('how much', 'total', 'expenses', 'spend', 'spent', 'pengeluaran', 'berapa')):
        return 'expenses'
    if any(term in q for term in ('where', 'which restaurant', 'where did', 'dimana', 'di mana')):
        return 'where'
    if any(term in q for term in ('what food', 'what did', 'what items', 'bought', 'buy', 'makanan apa', 'apa yang')):
        return 'items'
    raise ValueError('Supported questions: food bought, food expenses, or where a food item was purchased.')


def _item_term(q: str) -> str:
    """Extract item after 'buy X from' or 'bought X' for location queries."""
    match = re.search(r'\b(?:buy|bought|purchase|purchased)\s+(.+?)\s+(?:from|in|during|over|within|on)\b', q, re.I)
    if match:
        return match.group(1).strip(' ?!')
    match = re.search(r'\b(?:where .*? buy|where .*? bought)\s+([\w\s-]+)', q, re.I)
    if match:
        return re.sub(r'\b(last|past|yesterday|today)\b.*', '', match.group(1), flags=re.I).strip(' ?!')
    raise ValueError('Ask where you bought a specific item, e.g. "Where did I buy hamburger from last 7 days?"')


def execute_tool(intent: str, start: date, end: date, item: str | None = None, note: str = '') -> dict:
    """Fixed set of read-only SQL tools; neither callers nor LLMs supply SQL."""
    if intent not in {'expenses', 'items', 'where'}:
        raise ValueError('Unsupported tool')
    beginning, ending = start.isoformat(), end.isoformat()
    with connection() as conn:
        if intent == 'expenses':
            rows = conn.execute('''
                SELECT currency, COUNT(*) AS receipts,
                    SUM(COALESCE(total, (SELECT SUM(total_price) FROM receipt_items WHERE receipt_id=receipts.id))) AS amount
                FROM receipts WHERE purchased_at BETWEEN ? AND ? GROUP BY currency
            ''', (beginning, ending)).fetchall()
            if not rows:
                answer = 'No dated receipts were found in this period; this does not prove that no purchases occurred.'
            else:
                detail = ', '.join(f'{row["currency"]} {row["amount"]:,.2f} across {row["receipts"]} receipt(s)'
                                   if row['amount'] is not None else f'{row["receipts"]} {row["currency"]} receipts without parsed totals'
                                   for row in rows)
                answer = 'Recorded food receipt totals: ' + detail + '. Shipping, taxes, and other fees may be included.'
        elif intent == 'items':
            rows = conn.execute('''
                SELECT r.merchant, i.name, i.quantity
                FROM receipts r JOIN receipt_items i ON i.receipt_id=r.id
                WHERE r.purchased_at BETWEEN ? AND ? ORDER BY r.purchased_at, i.id
            ''', (beginning, ending)).fetchall()
            if not rows:
                answer = 'No parsed food items found for this period. OCR extraction or receipt dates may be incomplete.'
            else:
                answer = 'Items in your stored receipts: ' + '; '.join(
                    f'{row["quantity"]:g} × {row["name"]} ({row["merchant"]})' for row in rows[:25])
                if len(rows) > 25:
                    answer += f'; and {len(rows)-25} more.'
        else:
            term = item or ""
            if not term:
                raise ValueError("A product name is required for a location query.")
            search_terms = ['hamburger', 'burger'] if term.lower() in ('hamburger', 'burger') else [term.lower()]
            rows = conn.execute('''
                SELECT DISTINCT r.merchant, r.purchased_at, i.name
                FROM receipts r JOIN receipt_items i ON i.receipt_id=r.id
                WHERE r.purchased_at BETWEEN ? AND ?
            ''', (beginning, ending)).fetchall()
            matches = [row for row in rows if any(t in row['name'].lower() for t in search_terms)]
            if not matches:
                answer = f'No matching receipt item for "{term}" was found in this period.'
            else:
                answer = f'Purchases matching "{term}": ' + '; '.join(
                    f'{row["name"]} at {row["merchant"]} on {row["purchased_at"]}' for row in matches[:25])
                if len(matches) > 25:
                    answer += f'; and {len(matches)-25} more.'
    return {'tool': intent, 'date_start': beginning, 'date_end': ending,
            'answer': answer + note, 'note': 'Only saved OCR-extracted receipts with recognized purchase dates are considered.'}



def answer_question(question: str, today: date | None = None) -> dict:
    intent = classify(question)
    start, end, note = date_range(question, today)
    item = _item_term(question) if intent == 'where' else None
    return execute_tool(intent, start, end, item=item, note=note)
