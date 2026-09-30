"""FastAPI application entry point for the Fraud Rule Engine."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health as health_api
from app.api import reviews, stats, transactions
from app.config import get_settings
from app.database.session import init_db

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database schema and the LocalStack SNS topic on startup."""
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - depends on live infra
        logger.error("Database initialisation failed: %s", exc)

    # Best effort: make sure the SNS topic exists. A failure here is not fatal.
    try:
        from app.dependencies import get_notification_service

        service = get_notification_service()
        if service.enabled:
            arn = service.ensure_topic()
            logger.info("SNS notifications enabled, topic ARN: %s", arn or "unavailable")
    except Exception as exc:  # pragma: no cover - depends on live infra
        logger.warning("Could not prepare the SNS topic: %s", exc)

    yield


app = FastAPI(
    title="Fraud Rule Engine",
    description=(
        "A flexible, plugin based rule engine that scores transactions for fraud, "
        "persists the verdicts in PostgreSQL and publishes HIGH risk alerts to "
        "AWS SNS emulated by LocalStack."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Wildcard origins cannot be combined with credentials per the CORS spec.
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_api.router)
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(reviews.router, prefix="/api/fraud-flags", tags=["fraud-flags"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak stack traces to the caller - log them server side instead."""
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": "Fraud Rule Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "rules": [rule.describe() for rule in _get_engine().rules],
    }


def _get_engine():
    from app.dependencies import get_fraud_engine

    return get_fraud_engine()
