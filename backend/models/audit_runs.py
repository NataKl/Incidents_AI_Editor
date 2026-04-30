"""
Журнал аудита операций сервиса.

CREATE TABLE IF NOT EXISTS audit_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    action TEXT NOT NULL,
    input JSONB,
    output JSONB,
    status TEXT NOT NULL,
    error TEXT,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_audit_runs_created ON audit_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_runs_action ON audit_runs(action);
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core.database import connection

AUDIT_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS audit_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    action TEXT NOT NULL,
    input JSONB,
    output JSONB,
    status TEXT NOT NULL,
    error TEXT,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_audit_runs_created ON audit_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_runs_action ON audit_runs(action);
"""


def insert_audit_run(
    *,
    action: str,
    input_data: Any | None,
    output_data: Any | None,
    status: str,
    error: str | None,
    duration_ms: int | None,
) -> uuid.UUID:
    def to_jsonb(val: Any | None) -> Jsonb | None:
        if val is None:
            return None
        if isinstance(val, Jsonb):
            return val
        return Jsonb(val)

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_runs (action, input, output, status, error, duration_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    action,
                    to_jsonb(input_data),
                    to_jsonb(output_data),
                    status,
                    error,
                    duration_ms,
                ),
            )
            aid = cur.fetchone()[0]
        conn.commit()
    return aid


def list_audit_runs(*, limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, action, input, output, status, error, duration_ms
                FROM audit_runs
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

        def jsonify(v: Any) -> Any:
            if v is None:
                return None
            if isinstance(v, (dict, list)):
                return v
            if isinstance(v, (bytes, memoryview)):
                return json.loads(bytes(v))
            return v

        out.append(
            {
                "id": str(d["id"]),
                "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
                "action": d["action"],
                "input": jsonify(d["input"]),
                "output": jsonify(d["output"]),
                "status": d["status"],
                "error": d["error"],
                "duration_ms": d["duration_ms"],
            }
        )
    return out
