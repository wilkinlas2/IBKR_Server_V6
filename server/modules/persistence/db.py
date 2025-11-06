from __future__ import annotations
import os, sqlite3, json, threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

_DB_DIR = Path(__file__).resolve().parents[3] / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "app.db"

_lock = threading.Lock()

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            # graphs
            cur.execute("""
            CREATE TABLE IF NOT EXISTS graphs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            # oca registry (legs apart)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS oca_registry (
                oca_group TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS oca_legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                oca_group TEXT NOT NULL,
                role TEXT NOT NULL,
                internal_id TEXT NOT NULL,
                ib_order_id INTEGER,
                status TEXT,
                UNIQUE(oca_group, role),
                FOREIGN KEY(oca_group) REFERENCES oca_registry(oca_group) ON DELETE CASCADE
            );
            """)
            conn.commit()
        finally:
            conn.close()

def save_graph(graph_id: str, name: str, description: str, json_payload: Dict[str, Any]) -> None:
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO graphs (id, name, description, json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description, json=excluded.json
            """, (graph_id, name, description, json.dumps(json_payload)))
            conn.commit()
        finally:
            conn.close()

def load_graph(graph_id: str) -> Dict[str, Any] | None:
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, json FROM graphs WHERE id=?", (graph_id,))
            row = cur.fetchone()
            if not row:
                return None
            payload = json.loads(row["json"])
            payload["id"] = row["id"]
            payload["name"] = row["name"]
            payload["description"] = row["description"]
            return payload
        finally:
            conn.close()

def load_all_graphs() -> List[Dict[str, Any]]:
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, json FROM graphs ORDER BY created_at ASC")
            rows = cur.fetchall()
            out = []
            for r in rows:
                p = json.loads(r["json"])
                p["id"] = r["id"]
                p["name"] = r["name"]
                p["description"] = r["description"]
                out.append(p)
            return out
        finally:
            conn.close()

# ---- OCA registry persistence ----

def oca_upsert(oca_group: str, symbol: str) -> None:
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO oca_registry (oca_group, symbol)
                VALUES (?, ?)
                ON CONFLICT(oca_group) DO UPDATE SET symbol=excluded.symbol
            """, (oca_group, symbol))
            conn.commit()
        finally:
            conn.close()

def oca_upsert_leg(oca_group: str, role: str, internal_id: str, ib_order_id: int | None, status: str | None) -> None:
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO oca_legs (oca_group, role, internal_id, ib_order_id, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(oca_group, role) DO UPDATE SET internal_id=excluded.internal_id, ib_order_id=excluded.ib_order_id, status=excluded.status
            """, (oca_group, role, internal_id, ib_order_id, status))
            conn.commit()
        finally:
            conn.close()

def oca_load_all() -> Dict[str, Dict[str, Any]]:
    """
    Return shape:
    {
      "OCA-...": {
         "symbol": "AAPL",
         "legs": [{"role":"parent","internal_id":"...","ib_order_id":123,"status":null}, ...]
      }
    }
    """
    init_db()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT oca_group, symbol FROM oca_registry")
            regs = {r["oca_group"]: {"symbol": r["symbol"], "legs": []} for r in cur.fetchall()}
            if not regs:
                return {}
            cur.execute("SELECT oca_group, role, internal_id, ib_order_id, status FROM oca_legs")
            for r in cur.fetchall():
                group = r["oca_group"]
                if group in regs:
                    regs[group]["legs"].append({
                        "role": r["role"],
                        "internal_id": r["internal_id"],
                        "ib_order_id": r["ib_order_id"],
                        "status": r["status"],
                    })
            return regs
        finally:
            conn.close()
