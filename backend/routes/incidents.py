from __future__ import annotations

import json
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models import audit_runs, diagnoses as diagnoses_crud
from models import events as events_crud
from models import incidents as incidents_crud

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1)
    event_ids: list[str] = Field(min_length=1)
    priority: int = Field(default=3, ge=1, le=5)


class IncidentCreateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    incident_id: str


@router.post("", response_model=IncidentCreateResponse)
def create_incident(body: IncidentCreate) -> IncidentCreateResponse:
    t0 = time.perf_counter()
    inp = body.model_dump()
    try:
        uuids: list[uuid.UUID] = []
        for raw in body.event_ids:
            try:
                uuids.append(uuid.UUID(str(raw)))
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"invalid event_id: {raw}") from e
        unique = list(dict.fromkeys(uuids))
        found = events_crud.count_events_by_ids(unique)
        if found != len(unique):
            raise HTTPException(status_code=404, detail="one or more event_ids not found")

        try:
            iid = incidents_crud.insert_incident_with_events(
                title=body.title.strip(),
                event_ids=unique,
                priority=body.priority,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        out = {"status": "ok", "incident_id": str(iid)}
        audit_runs.insert_audit_run(
            action="POST /incidents",
            input_data=inp,
            output_data=out,
            status="ok",
            error=None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return IncidentCreateResponse(incident_id=str(iid))
    except HTTPException as e:
        audit_runs.insert_audit_run(
            action="POST /incidents",
            input_data=inp,
            output_data=None,
            status="error",
            error=str(e.detail),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        raise


@router.get("")
def list_incidents() -> list[dict]:
    return incidents_crud.list_incidents_recent(limit=20)


@router.get("/{incident_id}")
def get_incident(incident_id: str) -> dict:
    try:
        uid = uuid.UUID(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="invalid incident_id") from e
    row = incidents_crud.get_incident(uid)
    if not row:
        raise HTTPException(status_code=404, detail="incident not found")
    eids = incidents_crud.list_event_ids_for_incident(uid)
    evs = events_crud.get_events_by_ids(eids)
    return {**row, "events": evs}


@router.get("/{incident_id}/diagnosis/latest")
def latest_diagnosis(incident_id: str) -> dict:
    try:
        uid = uuid.UUID(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="invalid incident_id") from e
    d = diagnoses_crud.get_latest_for_incident(uid)
    if not d:
        raise HTTPException(status_code=404, detail="no diagnosis for incident")
    raw = d.get("diagnosis_json") or ""
    try:
        d["diagnosis_parsed"] = json.loads(raw)
    except json.JSONDecodeError:
        d["diagnosis_parsed"] = None
    return d
