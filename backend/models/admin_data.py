"""
Хранилище произвольных админ/клиентских пакетов (метрики, контекст с фронта).

CREATE TABLE IF NOT EXISTS admin_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL,
    source TEXT NOT NULL DEFAULT 'frontend'
);
CREATE INDEX IF NOT EXISTS idx_admin_data_created ON admin_data(created_at DESC);
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core.database import connection

ADMIN_DATA_DDL = """
CREATE TABLE IF NOT EXISTS admin_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL,
    source TEXT NOT NULL DEFAULT 'frontend'
);
CREATE INDEX IF NOT EXISTS idx_admin_data_created ON admin_data(created_at DESC);
"""


def insert_admin_payload(*, payload: dict[str, Any], source: str = "frontend") -> uuid.UUID:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_data (payload, source)
                VALUES (%s, %s)
                RETURNING id
                """,
                (Jsonb(payload), source),
            )
            rid = cur.fetchone()[0]
        conn.commit()
    return rid


def list_admin_payloads(*, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, payload, source
                FROM admin_data
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ca = d["created_at"]
        pl = d["payload"]
        if isinstance(pl, (bytes, memoryview)):
            import json

            pl = json.loads(bytes(pl))
        out.append(
            {
                "id": str(d["id"]),
                "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
                "payload": pl,
                "source": d["source"],
            }
        )
    return out
