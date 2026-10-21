"""Best-effort OCR parsing; production needs manual review for amounts and dates."""
from __future__ import annotations

import io
import re
from datetime import date

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError

SKIP = re.compile(r'\b(total|subtotal|sub total|tax|vat|service|delivery|shipping|discount|change|cash|balance|payment|paid|grand total|qty|quantity)\b', re.I)
AMOUNT = re.compile(r'(?:Rp\.?\s*|IDR\s*|USD\s*|\$\s*)?(-?\d[\d.,]*)(?:\s*(?:IDR|USD))?$', re.I)
DATE_PATTERNS = (
    re.compile(r'\b(20\d{2}-\d{1,2}-\d{1,2})\b'),
    re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b'),
    re.compile(r'\b(\d{1,2}\s+[A-Za-z]+\s+20\d{2})\b', re.I),
    re.compile(r'\b([A-Za-z]+\s+\d{1,2},?\s+20\d{2})\b', re.I),
)


def money_number(raw: str, currency: str = 'IDR') -> float:
    """Approximate locale-aware amount parser for common IDR/USD receipts."""
    value = re.sub(r'[^\d.,-]', '', raw)
    if not value or value == '-':
        raise ValueError('Missing amount')
    if ',' in value and '.' in value:
        value = value.replace('.', '').replace(',', '.') if value.rfind(',') > value.rfind('.') else value.replace(',', '')
    elif ',' in value:
        pieces = value.split(',')
        value = value.replace(',', '') if currency == 'IDR' or len(pieces[-1]) == 3 else value.replace(',', '.')
    elif '.' in value:
        pieces = value.split('.')
        value = value.replace('.', '') if currency == 'IDR' and len(pieces[-1]) == 3 else value
    return float(value)


def extract_text(data: bytes, filename: str) -> str:
    if filename.lower().endswith('.pdf'):
        try:
            import fitz
            pdf = fitz.open(stream=data, filetype='pdf')
            if len(pdf) > 10:
                raise ValueError('PDF must contain at most 10 pages')
            parts = []
            for page in pdf:
                text = page.get_text('text')
                if not text.strip():
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    text = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes('png'))))
                parts.append(text)
            return '\n'.join(parts)
        except ImportError as exc:
            raise ValueError('PDF support requires PyMuPDF') from exc
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 30_000_000:
            raise ValueError('Image resolution too large')
        image = ImageOps.exif_transpose(image).convert('RGB')
        return pytesseract.image_to_string(image, config='--psm 6')
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Invalid image') from exc


def parse_date(text: str) -> str | None:
    from dateutil import parser
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                parsed = parser.parse(match.group(1), dayfirst=not match.group(1).startswith('20'))
                return parsed.date().isoformat()
            except (ValueError, OverflowError):
                continue
    return None


def parse_receipt(text: str) -> dict:
    """Heuristic extraction; edits/corrections should be enabled in production."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    currency = 'USD' if re.search(r'\bUSD\b|\$', text, re.I) else 'IDR'
    purchased_at = parse_date(text)
    merchant = next((line for line in lines[:5]
                     if not SKIP.search(line)
                     and not any(pattern.search(line) for pattern in DATE_PATTERNS)),
                    'Unknown merchant')
    merchant = merchant[:120]
    total = None
    items = []
    for line in lines:
        if any(pattern.fullmatch(line) for pattern in DATE_PATTERNS):
            continue
        m = AMOUNT.search(line)
        if not m:
            continue
        prefix = line[:m.start()].strip(' :.-\t')
        if not prefix:
            continue
        try:
            value = money_number(m.group(0), currency)
        except ValueError:
            continue
        if re.search(r'\b(grand\s+total|total\s+due|total\s+payment|total)\b', prefix, re.I) and not re.search(r'subtotal|sub total', prefix, re.I):
            total = value
            continue
        if SKIP.search(prefix) or re.search(r'\b(date|time|invoice|phone|tel|receipt|order|no\.)\b', prefix, re.I):
            continue
        quantity = 1.0
        quantity_match = re.match(r'^(\d+(?:\.\d+)?)\s*[xX]\s+(.+)$', prefix)
        if quantity_match:
            quantity, prefix = float(quantity_match.group(1)), quantity_match.group(2)
        if not any(c.isalpha() for c in prefix):
            continue
        items.append({'name': prefix[:200], 'quantity': quantity, 'total_price': value})
    if total is None and items:
        total = round(sum(x['total_price'] for x in items), 2)
    return {
        'merchant': merchant, 'purchased_at': purchased_at,
        'total': total, 'currency': currency, 'items': items,
        'warnings': [msg for cond, msg in (
            (purchased_at is None, 'Purchase date not detected; date questions will exclude this receipt.'),
            (not items, 'No line items detected; improve OCR or parsing.'),
            (total is None, 'No total amount detected.'),
        ) if cond],
    }
