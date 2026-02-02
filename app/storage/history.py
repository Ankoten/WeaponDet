"""Хранение истории запросов (SQLite)."""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            filename TEXT,
            detections_count INTEGER DEFAULT 0,
            detections_json TEXT,
            processing_time_ms REAL,
            has_weapon INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def save_query(
    source: str,
    filename: str | None,
    detections: list[dict],
    processing_time_ms: float,
) -> str:
    init_db()
    qid = str(uuid.uuid4())
    detections_json = json.dumps(detections, ensure_ascii=False)
    has_weapon = 1 if detections else 0

    conn = _get_conn()
    conn.execute(
        """INSERT INTO query_history 
           (id, timestamp, source, filename, detections_count, detections_json, processing_time_ms, has_weapon)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (qid, datetime.utcnow().isoformat(), source, filename or "", len(detections), detections_json, processing_time_ms, has_weapon),
    )
    conn.commit()
    conn.close()
    return qid


def get_history(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, timestamp, source, filename, detections_count, 
                  detections_json, processing_time_ms, has_weapon
           FROM query_history ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "source": r["source"],
            "filename": r["filename"],
            "detections_count": r["detections_count"],
            "detections": json.loads(r["detections_json"] or "[]"),
            "processing_time_ms": r["processing_time_ms"],
            "has_weapon": bool(r["has_weapon"]),
        }
        for r in rows
    ]


def get_stats() -> dict[str, Any]:
    init_db()
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM query_history").fetchone()[0]
    with_weapon = conn.execute("SELECT COUNT(*) FROM query_history WHERE has_weapon = 1").fetchone()[0]
    by_source = dict(conn.execute("SELECT source, COUNT(*) FROM query_history GROUP BY source").fetchall())
    avg_time = conn.execute("SELECT AVG(processing_time_ms) FROM query_history").fetchone()[0] or 0
    conn.close()

    return {
        "total_queries": total,
        "queries_with_weapon": with_weapon,
        "by_source": by_source,
        "avg_processing_time_ms": round(avg_time, 2),
    }


def export_json(filepath: str | Path) -> Path:
    data = get_history(limit=10000)
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
