from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from models import admin_data as admin_crud
from models import audit_runs as audit_crud
from models import dashboard as dashboard_crud
from models import incidents as incidents_crud

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def admin_dashboard_summary() -> dict:
    """Сводная статистика событий/инцидентов и полный список инцидентов с связанными событиями (для дашборда)."""
    return dashboard_crud.dashboard_snapshot()


class AdminIngestBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "frontend"


def _parse_start_inclusive(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            d = date.fromisoformat(s)
            return datetime.combine(d, datetime.min.time())
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"invalid date_from: {s}") from e


def _parse_end_inclusive(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            d = date.fromisoformat(s)
            return datetime.combine(d, datetime.max.time())
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"invalid date_to: {s}") from e


@router.get("/incidents")
def admin_incidents(
    date_from: str | None = Query(None, description="ISO date или datetime, начало периода (включительно)"),
    date_to: str | None = Query(None, description="ISO date или datetime, конец периода (включительно)"),
) -> list[dict]:
    start = _parse_start_inclusive(date_from)
    end = _parse_end_inclusive(date_to)
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="date_to must not be before date_from")
    return incidents_crud.list_incidents_admin(date_from=start, date_to_inclusive=end)


@router.get("/audit-runs")
def admin_audit_runs(limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return audit_crud.list_audit_runs(limit=limit)


@router.post("/ingest")
def admin_ingest(body: AdminIngestBody) -> dict[str, str]:
    t0 = time.perf_counter()
    rid = admin_crud.insert_admin_payload(payload=body.payload, source=body.source)
    audit_crud.insert_audit_run(
        action="POST /admin/ingest",
        input_data=body.model_dump(),
        output_data={"id": str(rid)},
        status="ok",
        error=None,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    return {"status": "ok", "id": str(rid)}
