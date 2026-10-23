"""SQLite helpers for CyberNews Tracker: schema, seed data and a per-request connection."""

import sqlite3
from pathlib import Path

from flask import g
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "data" / "cybernews.db"

CATEGORIES = ["Vulnerabilities", "Ransomware", "Data Breach", "Malware", "Phishing", "Research"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    summary    TEXT NOT NULL,
    content    TEXT NOT NULL,
    category   TEXT NOT NULL,
    source     TEXT NOT NULL,
    source_url TEXT,
    published  TEXT NOT NULL,
    featured   INTEGER NOT NULL DEFAULT 0,
    author_id  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS login_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    success    INTEGER NOT NULL,
    ip         TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookmarks (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, article_id)
);
"""

def get_db():
    """One connection per request, closed again by close_db()."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and seed the demo accounts on the very first start."""
    DB_PATH.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        # Demo accounts - only the hash is stored
        for username, password, role in (("alice", "alicepass", "user"), ("bob", "bobpass", "admin")):
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
    # Articles now come from the live news import - drop the old placeholder articles (they have no source link)
    db.execute("DELETE FROM articles WHERE source_url IS NULL AND source IN"
               " ('PatchNews', 'SecureWire', 'TechWatch', 'CyberDaily')")
    db.commit()
    db.close()
