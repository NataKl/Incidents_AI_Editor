from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models import audit_runs, diagnoses as diagnoses_crud
from models import incidents as incidents_crud
from services.diagnosis import DiagnosisPayload, OpenAIDiagnosisFailed, run_diagnosis

router = APIRouter(prefix="/ai", tags=["ai"])


class DiagnoseRequest(BaseModel):
    title: str = Field(min_length=1)
    messages: list[str] = Field(min_length=1)
    incident_id: str | None = None


class DiagnoseResponse(BaseModel):
    root_cause_hypothesis: str
    confidence: Literal["high", "medium", "low"]
    next_steps: list[str]
    needs_review: bool


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(body: DiagnoseRequest) -> DiagnoseResponse:
    t0 = time.perf_counter()
    inp = body.model_dump()
    incident_uuid: uuid.UUID | None = None
    if body.incident_id:
        try:
            incident_uuid = uuid.UUID(body.incident_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail="invalid incident_id") from e
        if not incidents_crud.get_incident(incident_uuid):
            raise HTTPException(status_code=404, detail="incident not found")

    try:
        payload, diagnosis_stored_text, err = await run_diagnosis(body.title, body.messages)
        assert isinstance(payload, DiagnosisPayload)

        if incident_uuid:
            diagnoses_crud.insert_diagnosis(
                incident_id=incident_uuid,
                diagnosis_json=diagnosis_stored_text,
                needs_review=True if err == "INVALID_JSON" else payload.needs_review,
                error=err,
            )

        out = payload.model_dump()
        audit_runs.insert_audit_run(
            action="POST /ai/diagnose",
            input_data=inp,
            output_data=out,
            status="ok",
            error=err,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return DiagnoseResponse.model_validate(out)
    except OpenAIDiagnosisFailed as e:
        audit_runs.insert_audit_run(
            action="POST /ai/diagnose",
            input_data=inp,
            output_data=None,
            status="error",
            error=e.message,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        raise HTTPException(status_code=503, detail=e.message) from e
    except HTTPException:
        raise
    except Exception as e:
        audit_runs.insert_audit_run(
            action="POST /ai/diagnose",
            input_data=inp,
            output_data=None,
            status="error",
            error=str(e),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        raise
