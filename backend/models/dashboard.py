"""
Сводная статистика по событиям и инцидентам для дашборда.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from core.database import connection
from models.events import event_row_to_api
from models.incidents import _confidence_from_diagnosis_json, _normalize_diagnosis_confidence


def dashboard_snapshot() -> dict[str, Any]:
    """Счётчики событий/привязок, распределение инцидентов по приоритету, полный список инцидентов с событиями."""
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT COUNT(*)::bigint AS n FROM events")
            total_events = int(cur.fetchone()["n"])

            cur.execute("SELECT COUNT(DISTINCT event_id)::bigint AS n FROM incident_events")
            linked_events = int(cur.fetchone()["n"])

            cur.execute("SELECT COUNT(*)::bigint AS n FROM incidents")
            total_incidents = int(cur.fetchone()["n"])

            cur.execute(
                """
                SELECT COALESCE(i.priority::text, '?') AS k, COUNT(*)::bigint AS n
                FROM incidents i
                GROUP BY i.priority
                ORDER BY i.priority ASC
                """
            )
            by_pri: dict[str, int] = {}
            for row in cur.fetchall():
                by_pri[str(row["k"])] = int(row["n"])

            cur.execute(
                """
                SELECT
                    i.id AS incident_id,
                    i.created_at,
                    i.title,
                    i.priority,
                    d.diagnosis_json,
                    d.needs_review,
                    d.confidence_raw,
                    e.id AS event_id,
                    e.created_at AS event_created_at,
                    e.service AS event_service,
                    e.level AS event_level,
                    e.message AS event_message,
                    e.ts AS event_ts
                FROM incidents i
                LEFT JOIN LATERAL (
                    SELECT diagnosis_json, needs_review,
                           (diagnosis_json::jsonb->>'confidence') AS confidence_raw
                    FROM diagnoses
                    WHERE diagnoses.incident_id = i.id
                    ORDER BY diagnoses.created_at DESC
                    LIMIT 1
                ) d ON TRUE
                LEFT JOIN incident_events ie ON ie.incident_id = i.id
                LEFT JOIN events e ON e.id = ie.event_id
                ORDER BY
                    i.priority ASC,
                    i.created_at DESC,
                    e.created_at DESC NULLS LAST
                """
            )
            raw_rows = cur.fetchall()

    unlinked = max(0, total_events - linked_events)

    incidents_out: list[dict[str, Any]] = []
    current_key: uuid.UUID | None = None
    bucket: dict[str, Any] | None = None

    for r in raw_rows:
        row = dict(r)
        iid = row["incident_id"]
        if iid != current_key:
            if bucket is not None:
                incidents_out.append(bucket)
            current_key = iid
            ca = row["created_at"]
            diag_raw = row.get("diagnosis_json")
            if diag_raw is None:
                conf: str | None = None
                review: bool | None = None
            else:
                raw_s = diag_raw if isinstance(diag_raw, str) else str(diag_raw or "")
                conf = _normalize_diagnosis_confidence(row.get("confidence_raw")) or _confidence_from_diagnosis_json(
                    raw_s
                )
                review = bool(row.get("needs_review"))
            bucket = {
                "incident_id": str(iid),
                "id": str(iid),
                "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
                "title": row["title"],
                "priority": row["priority"],
                "diagnosis_confidence": conf,
                "diagnosis_needs_review": review,
                "events": [],
            }
        if row.get("event_id") is not None:
            assert bucket is not None
            ts = row.get("event_ts")
            cae = row.get("event_created_at")
            ev = event_row_to_api(
                {
                    "id": row["event_id"],
                    "created_at": cae,
                    "service": row["event_service"],
                    "level": row["event_level"],
                    "message": row["event_message"],
                    "ts": ts,
                }
            )
            bucket["events"].append(ev)
    if bucket is not None:
        incidents_out.append(bucket)

    return {
        "events": {
            "total": total_events,
            "linked_to_incident": linked_events,
            "unlinked": unlinked,
        },
        "incidents": {
            "total": total_incidents,
            "by_priority": {
                str(n): int(by_pri.get(str(n), 0)) for n in range(1, 6)
            },
            "blocking": by_pri.get("1", 0),
            "critical": by_pri.get("2", 0),
            "urgent": by_pri.get("3", 0),
            "medium": by_pri.get("4", 0),
            "low": by_pri.get("5", 0),
        },
        "incident_rows": incidents_out,
    }
