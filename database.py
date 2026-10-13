from __future__ import annotations
import os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("CRISIS_RESQ_DB", "data/crisis_resq.db"))

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS sos_alerts (
            message_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, victim_name TEXT NOT NULL,
            emergency_type TEXT NOT NULL, people_count INTEGER NOT NULL, battery INTEGER NOT NULL,
            latitude REAL, longitude REAL, location_text TEXT, message TEXT,
            priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Queued', relay_hops INTEGER NOT NULL DEFAULT 0
        )""")

def create_sos(**kwargs):
    row = {"message_id": "SOS-" + uuid.uuid4().hex[:10].upper(), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **kwargs, "status":"Queued", "relay_hops":0}
    cols = list(row.keys())
    with _connect() as conn:
        conn.execute(f"INSERT INTO sos_alerts ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", [row[c] for c in cols])
    return row

def list_sos(limit=100):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM sos_alerts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def update_status(message_id, status):
    with _connect() as conn:
        conn.execute("UPDATE sos_alerts SET status=? WHERE message_id=?", (status, message_id))

def get_stats():
    rows = list_sos(100000)
    return {"total":len(rows), "active":sum(r["status"] not in ("Resolved", "Delivered") for r in rows), "urgent":sum(r["priority"] in ("CRITICAL","HIGH") and r["status"] != "Resolved" for r in rows), "delivered":sum(r["status"] == "Delivered" for r in rows)}

def export_sos_csv():
    import csv, io
    rows = list_sos(100000)
    out = io.StringIO()
    if rows:
        writer = csv.DictWriter(out, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return out.getvalue()
