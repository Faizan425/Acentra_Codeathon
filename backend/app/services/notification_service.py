"""AWS SNS notification service backed by LocalStack.

The endpoint (``AWS_ENDPOINT_URL``) is fully configurable, so the exact same
code works against LocalStack locally and could talk to real AWS by changing an
environment variable - nothing is hardcoded.

Design rules:
* publishing must **never** raise into the request path,
* a failed notification must not damage the persisted fraud record,
* the outcome is recorded on the fraud flag (``alert_published``/``alert_error``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class NotificationResult:
    """Outcome of a notification attempt."""

    def __init__(
        self, published: bool, message_id: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        self.published = published
        self.message_id = message_id
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<NotificationResult published={self.published} error={self.error}>"


class FraudNotificationService:
    """Publishes high risk fraud alerts to an SNS topic."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._topic_arn: Optional[str] = self.settings.sns_topic_arn or None

    # ------------------------------------------------------------------ client
    def _client(self):
        return boto3.client(
            "sns",
            endpoint_url=self.settings.aws_endpoint_url or None,
            region_name=self.settings.aws_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            config=BotoConfig(
                connect_timeout=self.settings.aws_connect_timeout,
                read_timeout=self.settings.aws_read_timeout,
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.settings.notifications_enabled)

    # ------------------------------------------------------------------- topic
    def ensure_topic(self) -> Optional[str]:
        """Return the topic ARN, creating the topic if it does not exist yet."""
        if not self.enabled:
            return None
        if self._topic_arn:
            return self._topic_arn

        try:
            client = self._client()
            response = client.create_topic(Name=self.settings.sns_topic_name)
            self._topic_arn = response.get("TopicArn")
            logger.info("SNS topic ready: %s", self._topic_arn)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("Could not create/verify SNS topic: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unexpected error while creating SNS topic: %s", exc)
            return None
        return self._topic_arn

    # ----------------------------------------------------------------- payload
    @staticmethod
    def build_message(transaction: Any, flag: Any) -> Dict[str, Any]:
        """Build the alert payload published to SNS."""
        transaction_dict = (
            transaction.to_dict() if hasattr(transaction, "to_dict") else dict(transaction)
        )
        return {
            "event": "fraud.high_risk_transaction",
            "alert_type": "HIGH_RISK_TRANSACTION",
            "transaction_id": transaction_dict.get("id"),
            "account_id": transaction_dict.get("account_id"),
            "amount": transaction_dict.get("amount"),
            "risk_score": flag.risk_score,
            "risk_level": flag.risk_level,
            "triggered_rules": list(flag.triggered_rules or []),
            "reasons": list(flag.reasons or []),
            "status": flag.status,
            "transaction_timestamp": transaction_dict.get("timestamp"),
            "location": transaction_dict.get("location"),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    # ----------------------------------------------------------------- publish
    def publish_fraud_alert(self, transaction: Any, flag: Any) -> NotificationResult:
        """Publish a high-risk alert. Never raises."""
        if not self.enabled:
            return NotificationResult(False, error="notifications disabled")

        topic_arn = self.ensure_topic()
        if not topic_arn:
            return NotificationResult(
                False, error="SNS topic unavailable (is LocalStack running?)"
            )

        message = self.build_message(transaction, flag)
        try:
            client = self._client()
            response = client.publish(
                TopicArn=topic_arn,
                Subject=(
                    "HIGH RISK fraud alert - transaction "
                    f"{message.get('transaction_id')}"
                ),
                Message=json.dumps(message, indent=2, default=str),
                MessageAttributes={
                    "risk_level": {
                        "DataType": "String",
                        "StringValue": str(flag.risk_level or "UNKNOWN"),
                    },
                    "account_id": {
                        "DataType": "String",
                        "StringValue": str(message.get("account_id") or "unknown"),
                    },
                },
            )
            message_id = response.get("MessageId")
            logger.info(
                "Published HIGH risk SNS alert for transaction %s (MessageId=%s)",
                message.get("transaction_id"),
                message_id,
            )
            return NotificationResult(True, message_id=message_id)
        except (BotoCoreError, ClientError) as exc:
            logger.error("SNS publish failed: %s", exc)
            return NotificationResult(False, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected SNS publish error: %s", exc)
            return NotificationResult(False, error=str(exc))

    # ------------------------------------------------------------------ health
    def health(self) -> Tuple[bool, str]:
        """Best-effort connectivity probe used by the health endpoint."""
        if not self.enabled:
            return True, "disabled"
        try:
            self._client().list_topics()
            return True, "ok"
        except Exception as exc:
            return False, f"unavailable: {exc.__class__.__name__}"

            return None
        return self._topic_arn
