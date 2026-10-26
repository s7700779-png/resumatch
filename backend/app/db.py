import json, sqlite3, uuid
from datetime import datetime, timezone
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, department TEXT, description TEXT NOT NULL,
  required_skills TEXT DEFAULT '[]', preferred_skills TEXT DEFAULT '[]',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS batches(
  id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), created_at TEXT, skip_duplicates INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS candidates(
  id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL REFERENCES jobs(id), filename TEXT, stored_name TEXT, ext TEXT, size INTEGER,
  file_hash TEXT, status TEXT DEFAULT 'pending', error TEXT, retryable INTEGER DEFAULT 0,
  duplicate_of TEXT, created_at TEXT, analyzed_at TEXT,
  name TEXT, score REAL, text TEXT, result TEXT);
CREATE INDEX IF NOT EXISTS ix_c_batch ON candidates(batch_id);
CREATE INDEX IF NOT EXISTS ix_c_job ON candidates(job_id);
CREATE TABLE IF NOT EXISTS reports(
  id TEXT PRIMARY KEY, kind TEXT, ref_id TEXT, title TEXT, filename TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid():
    return uuid.uuid4().hex[:12]


def conn():
    c = sqlite3.connect(config.DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def q(sql, args=(), one=False):
    c = conn()
    try:
        rows = c.execute(sql, args).fetchall()
    finally:
        c.close()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    c = conn()
    try:
        with c:
            cur = c.execute(sql, args)
        return cur.rowcount
    finally:
        c.close()


def get_settings():
    s = dict(config.DEFAULT_SETTINGS)
    for r in q("SELECT key,value FROM settings"):
        if r["key"] in s:
            s[r["key"]] = int(r["value"])
    return s


def save_settings(values):
    for k, v in values.items():
        run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(int(v))))


def job_out(r):
    if not r:
        return None
    r = dict(r)
    r["required_skills"] = json.loads(r.get("required_skills") or "[]")
    r["preferred_skills"] = json.loads(r.get("preferred_skills") or "[]")
    return r
