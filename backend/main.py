from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.database import close_pool, init_schema
from models import audit_runs as audit_crud
from routes.admin import router as admin_router
from routes.ai import router as ai_router
from routes.events import router as events_router
from routes.incidents import router as incidents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield
    close_pool()


app = FastAPI(title="AI Editor Ops API", lifespan=lifespan)

app.include_router(events_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    t0 = getattr(request.state, "audit_start", None)
    duration_ms = int((time.perf_counter() - t0) * 1000) if t0 is not None else None
    try:
        audit_crud.insert_audit_run(
            action=f"{request.method} {request.url.path}",
            input_data={"errors": exc.errors(), "body": getattr(exc, "body", None)},
            output_data=None,
            status="error",
            error="validation",
            duration_ms=duration_ms,
        )
    except Exception:
        pass
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.middleware("http")
async def mark_audit_timer(request: Request, call_next):
    request.state.audit_start = time.perf_counter()
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
