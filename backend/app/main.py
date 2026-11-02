import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .db import Base, SessionLocal, engine
from .routers import alerts, ask, assessments, auth, company, dashboard, filings, library, regulations, reminders, reports, risk
from .routers import settings as settings_router

log = logging.getLogger("reglens")
settings = get_settings()


def _ensure_columns(connection, table: str, columns: dict[str, str]) -> None:
    existing = {c["name"] for c in inspect(connection).get_columns(table)}
    for name, ddl in columns.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    # Add fields introduced after the first release to existing installations.
    with engine.begin() as connection:
        _ensure_columns(connection, "risks", {"ignored": "BOOLEAN NOT NULL DEFAULT FALSE"})
        _ensure_columns(connection, "findings", {"ai_evaluated": "BOOLEAN NOT NULL DEFAULT FALSE", "ai_confidence": "FLOAT",
                                                 "ai_summary": "TEXT", "ai_findings": "JSON"})
        _ensure_columns(connection, "assessments", {"compliance_score_reason": "TEXT", "meta": "JSON"})
        if engine.dialect.name == "postgresql":
            score_type = str(next((c["type"] for c in inspect(connection).get_columns("assessments")
                                   if c["name"] == "compliance_score"), "")).upper()
            if "INT" in score_type:
                connection.execute(text("ALTER TABLE assessments ALTER COLUMN compliance_score TYPE FLOAT USING compliance_score::FLOAT"))
    with SessionLocal() as db:
        # Keep existing installs aligned with the reserved administrator account.
        from .models import Assessment, User
        from sqlalchemy import update
        from sqlalchemy.orm import selectinload
        db.execute(update(User).where(User.email == "zairahussain27@gmail.com").values(role="admin"))
        db.execute(update(User).where(User.email != "zairahussain27@gmail.com").values(role="user"))
        from .services import scoring
        # One-time backfill: re-derive scores for assessments created before score metadata existed.
        for assessment in db.scalars(select(Assessment).options(selectinload(Assessment.findings))
                                     .where(Assessment.meta.is_(None))).all():
            summary = scoring.compliance_summary(assessment.findings)
            assessment.compliance_score, assessment.compliance_score_reason = summary["score"], summary["reason"]
            assessment.meta = {"coverage": summary["coverage"], "confidence": summary["confidence"], "basis": summary["basis"],
                               "assessed": summary["assessed"], "total": summary["total"], "waiting": summary["waiting"]}
        db.commit()
    yield


app = FastAPI(title="RegLens AI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok"}


for module in (auth, dashboard, ask, regulations, library, reports, alerts, company, risk, reminders, filings,
               settings_router, assessments):
    api.include_router(module.router)
app.include_router(api)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    parts = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
        msg = str(e["msg"]).removeprefix("Value error, ")
        parts.append(f"{field}: {msg}" if field else msg)
    return JSONResponse({"detail": "; ".join(parts) or "Invalid request"}, status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_handler(_: Request, exc: IntegrityError):
    log.warning("Integrity error: %s", exc)
    return JSONResponse({"detail": "That conflicts with existing data"}, status_code=409)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


# Serve the built frontend from the same origin in production (no CORS / proxy needed).
dist = settings.frontend_dist
assets_dir = dist / "assets"
if dist.is_dir() and assets_dir.is_dir() and (dist / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")