"""Parameterized SQLite access with receipt/item normalisation."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connection() -> sqlite3.Connection:
    filename = os.getenv('DATABASE_PATH', './data/receipts.sqlite3')
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(filename)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn


def init_db() -> None:
    with connection() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant TEXT NOT NULL,
                purchased_at TEXT,
                total REAL,
                currency TEXT NOT NULL DEFAULT 'IDR',
                ocr_text TEXT NOT NULL,
                original_filename TEXT,
                image_sha256 TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS receipt_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                total_price REAL
            );
            CREATE INDEX IF NOT EXISTS idx_receipt_date ON receipts(purchased_at);
            CREATE INDEX IF NOT EXISTS idx_items_receipt ON receipt_items(receipt_id);
        ''')


def save_receipt(parsed: dict, ocr_text: str, filename: str, digest: str) -> tuple[int, bool]:
    with connection() as conn:
        existing = conn.execute('SELECT id FROM receipts WHERE image_sha256=?', (digest,)).fetchone()
        if existing:
            return existing['id'], False
        cursor = conn.execute('''
            INSERT INTO receipts(merchant, purchased_at, total, currency, ocr_text, original_filename, image_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (parsed['merchant'], parsed['purchased_at'], parsed['total'],
              parsed['currency'], ocr_text, filename, digest))
        receipt_id = cursor.lastrowid
        for item in parsed['items']:
            conn.execute('INSERT INTO receipt_items(receipt_id, name, quantity, total_price) VALUES (?, ?, ?, ?)',
                         (receipt_id, item['name'], item['quantity'], item['total_price']))
        return receipt_id, True
