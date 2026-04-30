"""
События — «что произошло».

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    service TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error')),
    message TEXT NOT NULL,
    ts TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_events_service ON events(service);
CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC);
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from core.database import connection

EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    service TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error')),
    message TEXT NOT NULL,
    ts TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_events_service ON events(service);
CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC);
"""


def event_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    ts = row.get("ts")
    created = row.get("created_at")
    return {
        "event_id": str(row["id"]),
        "id": str(row["id"]),
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
        "ts": ts.isoformat() if isinstance(ts, datetime) else ts,
        "service": row["service"],
        "level": row["level"],
        "message": row["message"],
    }


def insert_event(
    *,
    service: str,
    level: str,
    message: str,
    ts: datetime | None,
) -> uuid.UUID:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (service, level, message, ts)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (service, level, message, ts),
            )
            row = cur.fetchone()
            eid = row[0]
        conn.commit()
    return eid


def list_events(
    *,
    service: str | None = None,
    level: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if service:
        # Совпадение без учёта регистра / краевых пробелов (выбор из списка и строка в БД могут различаться)
        clauses.append("LOWER(TRIM(service)) = LOWER(TRIM(%s))")
        params.append(service)
    if level:
        clauses.append("level = %s")
        params.append(level)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, created_at, service, level, message, ts
        FROM events
        {where}
        ORDER BY CASE level
                     WHEN 'error' THEN 1
                     WHEN 'warning' THEN 2
                     WHEN 'info' THEN 3
                     ELSE 4
                 END,
                 service ASC,
                 created_at DESC
        LIMIT %s
    """
    params.append(limit)
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [event_row_to_api(dict(r)) for r in rows]


def delete_event(*, event_id: uuid.UUID) -> bool:
    """Удалить событие. Связи incident_events удаляются по ON DELETE CASCADE."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = %s::uuid", (str(event_id),))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def get_events_by_ids(event_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    if not event_ids:
        return []
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, service, level, message, ts
                FROM events
                WHERE id = ANY(%s::uuid[])
                ORDER BY created_at DESC
                """,
                (event_ids,),
            )
            rows = cur.fetchall()
    return [event_row_to_api(dict(r)) for r in rows]


def count_events_by_ids(event_ids: list[uuid.UUID]) -> int:
    if not event_ids:
        return 0
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM events WHERE id = ANY(%s::uuid[])",
                (event_ids,),
            )
            return int(cur.fetchone()[0])
