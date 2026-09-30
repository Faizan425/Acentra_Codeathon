"""Central application configuration.

Every setting is read from an environment variable and falls back to a safe
local-development default, so the project runs out of the box with Docker
Compose. The AWS values are the well known *dummy* credentials that LocalStack
accepts - no real AWS account or real credentials are ever required.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Runtime configuration for the fraud rule engine."""

    def __init__(self) -> None:
        # ---------------------------------------------------------------- infra
        self.database_url = _env_str(
            "DATABASE_URL",
            "postgresql+psycopg2://fraud_user:fraud_pass123@localhost:5432/fraud_db",
        )
        # The backend retries the initial schema creation while Postgres boots.
        self.db_init_retries = _env_int("DB_INIT_RETRIES", 15)
        self.db_init_retry_delay = _env_float("DB_INIT_RETRY_DELAY", 2.0)

        # ------------------------------------------------------ LocalStack / AWS
        self.aws_endpoint_url = _env_str(
            "AWS_ENDPOINT_URL", _env_str("LOCALSTACK_ENDPOINT", "http://localhost:4566")
        )
        self.aws_region = _env_str("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_access_key_id = _env_str("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = _env_str("AWS_SECRET_ACCESS_KEY", "test")
        self.sns_topic_name = _env_str("SNS_TOPIC_NAME", "fraud-alerts")
        # Optional: when empty the ARN is resolved/created from the topic name.
        self.sns_topic_arn = _env_str("SNS_TOPIC_ARN", "")
        self.notifications_enabled = _env_bool("NOTIFICATIONS_ENABLED", True)
        self.aws_connect_timeout = _env_float("AWS_CONNECT_TIMEOUT", 2.0)
        self.aws_read_timeout = _env_float("AWS_READ_TIMEOUT", 4.0)

        # --------------------------------------------- fraud rule configuration
        # Rule 1 - transaction velocity
        self.velocity_max_transactions = _env_int("VELOCITY_MAX_TRANSACTIONS", 5)
        self.velocity_window_minutes = _env_int("VELOCITY_WINDOW_MINUTES", 10)
        self.velocity_score = _env_int("VELOCITY_SCORE", 30)

        # Rule 2 - unusual amount
        self.amount_multiplier = _env_float("AMOUNT_MULTIPLIER", 10.0)
        self.amount_min_history = _env_int("AMOUNT_MIN_HISTORY", 3)
        self.amount_history_limit = _env_int("AMOUNT_HISTORY_LIMIT", 50)
        self.amount_score = _env_int("AMOUNT_SCORE", 30)

        # Rule 3 - impossible travel
        self.max_travel_speed_kmh = _env_float("MAX_TRAVEL_SPEED_KMH", 1000.0)
        self.location_min_distance_km = _env_float("LOCATION_MIN_DISTANCE_KM", 1.0)
        self.location_score = _env_int("LOCATION_SCORE", 40)

        # ---------------------------------------------------- risk aggregation
        self.medium_risk_threshold = _env_int("MEDIUM_RISK_THRESHOLD", 30)
        self.high_risk_threshold = _env_int("HIGH_RISK_THRESHOLD", 60)

        # ---------------------------------------------------------------- HTTP
        self.cors_origins = _env_list("CORS_ORIGINS", ["*"])
        self.log_level = _env_str("LOG_LEVEL", "INFO").upper()
        self.debug = _env_bool("DEBUG", False)
        self.history_lookup_limit = _env_int("HISTORY_LOOKUP_LIMIT", 200)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
