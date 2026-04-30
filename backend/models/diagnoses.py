"""
Результат диагностики инцидента.

CREATE TABLE IF NOT EXISTS diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    diagnosis_json TEXT NOT NULL,
    needs_review BOOLEAN NOT NULL,
    error TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_diagnoses_incident ON diagnoses(incident_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_created ON diagnoses(created_at DESC);
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from core.database import connection

DIAGNOSES_DDL = """
CREATE TABLE IF NOT EXISTS diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    diagnosis_json TEXT NOT NULL,
    needs_review BOOLEAN NOT NULL,
    error TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_diagnoses_incident ON diagnoses(incident_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_created ON diagnoses(created_at DESC);
"""


def insert_diagnosis(
    *,
    incident_id: uuid.UUID,
    diagnosis_json: str,
    needs_review: bool,
    error: str | None,
) -> uuid.UUID:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO diagnoses (incident_id, diagnosis_json, needs_review, error)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (incident_id, diagnosis_json, needs_review, error),
            )
            did = cur.fetchone()[0]
        conn.commit()
    return did


def get_latest_for_incident(incident_id: uuid.UUID) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, incident_id, diagnosis_json, needs_review, error
                FROM diagnoses
                WHERE incident_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (incident_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    ca = d["created_at"]
    return {
        "diagnosis_id": str(d["id"]),
        "created_at": ca.isoformat() if isinstance(ca, datetime) else ca,
        "incident_id": str(d["incident_id"]),
        "diagnosis_json": d["diagnosis_json"],
        "needs_review": d["needs_review"],
        "error": d["error"],
    }
