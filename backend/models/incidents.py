"""
Инциденты и связь с событиями.

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5)
);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents(priority ASC);

CREATE TABLE IF NOT EXISTS incident_events (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY (incident_id, event_id),
    CONSTRAINT uq_incident_events_event_id UNIQUE (event_id)
);
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from core.database import connection

INCIDENTS_DDL = """
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5)
);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents(priority ASC);
"""

INCIDENT_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS incident_events (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY (incident_id, event_id),
    CONSTRAINT uq_incident_events_event_id UNIQUE (event_id)
);
"""


def ensure_incident_events_event_unique(cur) -> None:
    """Одно событие не может входить в несколько инцидентов (миграция старых БД)."""
    cur.execute("DROP INDEX IF EXISTS idx_incident_events_event")
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'incident_events'
              AND c.contype = 'u'
              AND pg_get_constraintdef(c.oid) LIKE '%(event_id)%'
        )
        """
    )
    row = cur.fetchone()
    if row and row[0]:
        return
    cur.execute(
        """
        ALTER TABLE incident_events
        ADD CONSTRAINT uq_incident_events_event_id UNIQUE (event_id)
        """
    )


def _normalize_diagnosis_confidence(raw: Any) -> str | None:
    """Нормализует значение confidence из JSON/SQL к high|medium|low."""
    if raw is None:
        return None
    if isinstance(raw, str):
        c = raw.strip().lower()
        if c in ("high", "medium", "low"):
            return c
    return None


def _confidence_from_diagnosis_json(raw: str) -> str | None:
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        c = obj.get("confidence")
        return _normalize_diagnosis_confidence(c)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


def insert_incident_with_events(
    *,
    title: str,
    event_ids: list[uuid.UUID],
    priority: int = 3,
) -> uuid.UUID:
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incidents (title, priority)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (title, priority),
                )
                incident_id = cur.fetchone()[0]
                for eid in event_ids:
                    try:
                        cur.execute(
                            """
                            INSERT INTO incident_events (incident_id, event_id)
                            VALUES (%s, %s)
                            """,
                            (incident_id, eid),
                        )
                    except pg_errors.UniqueViolation:
                        raise ValueError(
                            "одно или несколько событий уже привязаны к другому инциденту"
                        ) from None
    return incident_id


def list_incidents_recent(*, limit: int = 20) -> list[dict[str, Any]]:
    """Сортировка: приоритет (1→5), затем диагностика — low, medium, high, без статуса; далее дата создания."""
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT i.id, i.created_at, i.title, i.priority,
                       d.diagnosis_json, d.needs_review, d.confidence_raw
                FROM incidents i
                LEFT JOIN LATERAL (
                    SELECT diagnosis_json, needs_review,
                           (diagnosis_json::jsonb->>'confidence') AS confidence_raw
                    FROM diagnoses
                    WHERE diagnoses.incident_id = i.id
                    ORDER BY diagnoses.created_at DESC
                    LIMIT 1
                ) d ON TRUE
                ORDER BY i.priority ASC,
                    CASE COALESCE(lower(trim(both from COALESCE(d.confidence_raw, ''))), '')
                        WHEN 'low' THEN 0
                        WHEN 'medium' THEN 1
                        WHEN 'high' THEN 2
                        ELSE 3
                    END ASC,
                    i.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ca = d["created_at"]
        i_id = str(d["id"])
        diag_raw = d.get("diagnosis_json")
        if diag_raw is None:
            conf: str | None = None
            review: bool | None = None
        else:
            raw_s = diag_raw if isinstance(diag_raw, str) else str(diag_raw or "")
            conf = _normalize_diagnosis_confidence(
                d.get("confidence_raw")
            ) or _confidence_from_diagnosis_json(raw_s)
            nr = d.get("needs_review")
            review = bool(nr)
        out.append(
            {
                "incident_id": i_id,
                "id": i_id,
                "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
                "title": d["title"],
                "priority": d["priority"],
                "diagnosis_confidence": conf,
                "diagnosis_needs_review": review,
            }
        )
    return out


def list_incidents_admin(
    *,
    date_from: date | datetime | None = None,
    date_to_inclusive: date | datetime | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if date_from is not None:
        clauses.append("created_at >= %s")
        params.append(date_from)
    if date_to_inclusive is not None:
        clauses.append("created_at <= %s")
        params.append(date_to_inclusive)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, created_at, title, priority
        FROM incidents
        {where}
        ORDER BY priority ASC, created_at DESC
    """
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ca = d["created_at"]
        out.append(
            {
                "incident_id": str(d["id"]),
                "id": str(d["id"]),
                "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
                "title": d["title"],
                "priority": d["priority"],
            }
        )
    return out


def get_incident(incident_id: uuid.UUID) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, title, priority
                FROM incidents WHERE id = %s
                """,
                (incident_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    ca = d["created_at"]
    return {
        "incident_id": str(d["id"]),
        "id": str(d["id"]),
        "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
        "title": d["title"],
        "priority": d["priority"],
    }


def list_event_ids_for_incident(incident_id: uuid.UUID) -> list[uuid.UUID]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id FROM incident_events
                WHERE incident_id = %s
                """,
                (incident_id,),
            )
            return [r[0] for r in cur.fetchall()]
