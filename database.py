# database.py
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "leads.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            username TEXT,
            text TEXT,
            published_on TEXT,
            reply_count INTEGER,
            processed_by_ai INTEGER DEFAULT 0,
            is_lead INTEGER DEFAULT 0,
            ai_comment TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_post(post: Dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO posts 
        (url, username, text, published_on, reply_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        post['url'], post['username'], post['text'],
        post['published_on'], post['reply_count'],
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

def get_unprocessed_posts(limit: int = 20) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM posts WHERE processed_by_ai = 0 LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_post_ai_status(post_id: int, is_lead: int, ai_comment: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE posts
        SET processed_by_ai = 1, is_lead = ?, ai_comment = ?
        WHERE id = ?
    ''', (is_lead, ai_comment, post_id))
    conn.commit()
    conn.close()

def get_leads(limit: int = 50) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM posts WHERE is_lead = 1 ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]