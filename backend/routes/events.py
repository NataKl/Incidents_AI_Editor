from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from models import audit_runs, events as events_crud

router = APIRouter(prefix="/events", tags=["events"])


class EventCreate(BaseModel):
    service: str = Field(min_length=1)
    level: Literal["info", "warning", "error"]
    message: str
    ts: str | None = None

    @field_validator("level", mode="before")
    @classmethod
    def level_normalize(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("message")
    @classmethod
    def message_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        return v.strip()


class EventCreateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    event_id: str


def _parse_ts(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    s = raw.strip()
    if s == "" or s.lower() in ("null", "none", "string"):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid ts format, use ISO-8601")


@router.post("", response_model=EventCreateResponse)
def create_event(body: EventCreate) -> EventCreateResponse:
    t0 = time.perf_counter()
    inp = body.model_dump()
    try:
        ts = _parse_ts(body.ts)
        eid = events_crud.insert_event(
            service=body.service.strip(),
            level=body.level,
            message=body.message,
            ts=ts,
        )
        out = {"status": "ok", "event_id": str(eid)}
        audit_runs.insert_audit_run(
            action="POST /events",
            input_data=inp,
            output_data=out,
            status="ok",
            error=None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return EventCreateResponse(event_id=str(eid))
    except HTTPException as e:
        audit_runs.insert_audit_run(
            action="POST /events",
            input_data=inp,
            output_data=None,
            status="error",
            error=str(e.detail),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        raise


@router.get("")
def list_events(
    service: Annotated[str | None, Query()] = None,
    level: Annotated[str | None, Query()] = None,
) -> list[dict]:
    svc: str | None = None
    if service is not None and service.strip() != "":
        svc = service.strip()
    lvl: Literal["info", "warning", "error"] | None = None
    if level is not None and level.strip() != "":
        low = level.strip().lower()
        if low not in ("info", "warning", "error"):
            raise HTTPException(
                status_code=422,
                detail="level must be one of: info, warning, error",
            )
        lvl = cast(Literal["info", "warning", "error"], low)
    return events_crud.list_events(service=svc, level=lvl)


class EventDeleteResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.delete("/{event_id}", response_model=EventDeleteResponse)
def delete_event(event_id: uuid.UUID) -> EventDeleteResponse:
    ok = events_crud.delete_event(event_id=event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="event not found")
    return EventDeleteResponse()
