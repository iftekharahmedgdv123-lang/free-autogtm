"""SQLite storage: leads, drafts, campaigns, suppression. No ORM, no deps."""
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    website TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    role TEXT DEFAULT '',
    email TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    followup1 TEXT DEFAULT '',
    followup2 TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS suppressed (
    email TEXT PRIMARY KEY,
    reason TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
"""

def connect(db_path="data.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

def _now():
    return int(time.time())

def is_suppressed(conn, email):
    if not email:
        return False
    row = conn.execute(
        "SELECT 1 FROM suppressed WHERE lower(email)=lower(?)", (email,)
    ).fetchone()
    return row is not None

def suppress(conn, email, reason="opt-out"):
    conn.execute(
        "INSERT OR IGNORE INTO suppressed(email, reason, created_at) VALUES (?,?,?)",
        (email.strip(), reason, _now()),
    )
    conn.commit()

def add_lead(conn, lead):
    """Insert a lead, de-duplicated by domain+company. Returns id or None."""
    domain = (lead.get("domain") or "").lower().strip()
    company = (lead.get("company") or "").strip()
    if not company:
        return None
    existing = conn.execute(
        "SELECT id FROM leads WHERE lower(company)=lower(?) OR (domain!='' AND lower(domain)=lower(?))",
        (company, domain),
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute(
        """INSERT INTO leads(company, website, domain, contact_name, role, email,
               source_url, notes, score, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            company,
            lead.get("website", ""),
            domain,
            lead.get("contact_name", ""),
            lead.get("role", ""),
            lead.get("email", ""),
            lead.get("source_url", ""),
            lead.get("notes", ""),
            int(lead.get("score", 0)),
            lead.get("status", "new"),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid

def list_leads(conn, status=None, limit=200):
    if status:
        rows = conn.execute(
            "SELECT * FROM leads WHERE status=? ORDER BY score DESC, id LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY score DESC, id LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def update_lead(conn, lead_id, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE leads SET {sets} WHERE id=?", (*fields.values(), lead_id))
    conn.commit()

def add_draft(conn, lead_id, subject, body, followup1, followup2):
    existing = conn.execute(
        "SELECT id FROM drafts WHERE lead_id=?", (lead_id,)
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute(
        """INSERT INTO drafts(lead_id, subject, body, followup1, followup2, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (lead_id, subject, body, followup1, followup2, "draft", _now()),
    )
    conn.commit()
    return cur.lastrowid

def list_drafts(conn, status=None, limit=200):
    if status:
        rows = conn.execute(
            """SELECT d.*, l.company, l.email, l.contact_name FROM drafts d
               JOIN leads l ON l.id=d.lead_id WHERE d.status=? ORDER BY d.id LIMIT ?""",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT d.*, l.company, l.email, l.contact_name FROM drafts d
               JOIN leads l ON l.id=d.lead_id ORDER BY d.id LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def set_draft_status(conn, draft_id, status):
    conn.execute("UPDATE drafts SET status=? WHERE id=?", (status, draft_id))
    conn.commit()

def delete_lead(conn, lead_id):
    conn.execute("DELETE FROM drafts WHERE lead_id=?", (lead_id,))
    conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn.commit()

def update_draft_fields(conn, draft_id, **fields):
    allowed = {"subject", "body", "followup1", "followup2", "status"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE drafts SET {sets} WHERE id=?", (*fields.values(), draft_id))
    conn.commit()

def list_suppressed(conn):
    rows = conn.execute("SELECT * FROM suppressed ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

def get_setting(conn, key, default=""):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()

def list_campaigns(conn):
    rows = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

def add_campaign(conn, name):
    cur = conn.execute(
        "INSERT INTO campaigns(name, created_at) VALUES (?,?)", (name, _now())
    )
    conn.commit()
    return cur.lastrowid

def stats(conn):
    def count(table, where=""):
        row = conn.execute(f"SELECT COUNT(*) c FROM {table} {where}").fetchone()
        return row["c"]
    return {
        "leads": count("leads"),
        "leads_with_email": count("leads", "WHERE email != ''"),
        "drafts": count("drafts"),
        "approved": count("drafts", "WHERE status='approved'"),
        "sent": count("drafts", "WHERE status='sent'"),
        "suppressed": count("suppressed"),
    }
