"""Notification tests - SNS publishing, failure handling and HIGH-risk gating."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.dependencies import get_notification_service
from app.services.notification_service import FraudNotificationService

from tests.conftest import SpyNotifier, utcnow

TOPIC_ARN = "arn:aws:sns:us-east-1:000000000000:fraud-alerts"


class FakeSnsClient:
    """Minimal boto3 SNS test double."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.published = []
        self.topics_created = []

    def create_topic(self, Name):  # noqa: N803 - boto3 keyword style
        self.topics_created.append(Name)
        return {"TopicArn": TOPIC_ARN}

    def publish(self, **kwargs):
        if self.fail:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "LocalStack unavailable"}},
                "Publish",
            )
        self.published.append(kwargs)
        return {"MessageId": "11111111-2222-3333-4444-555555555555"}

    def list_topics(self):
        if self.fail:
            raise ClientError(
                {"Error": {"Code": "EndpointConnectionError", "Message": "no endpoint"}},
                "ListTopics",
            )
        return {"Topics": [{"TopicArn": TOPIC_ARN}]}


def _settings(**overrides):
    settings = Settings()
    settings.aws_endpoint_url = "http://localhost:4566"
    settings.sns_topic_arn = ""
    settings.notifications_enabled = True
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _service(monkeypatch, client):
    service = FraudNotificationService(_settings())
    monkeypatch.setattr(service, "_client", lambda: client)
    return service


def _fake_flag():
    return SimpleNamespace(
        risk_score=100,
        risk_level="HIGH",
        triggered_rules=["transaction_velocity", "unusual_amount", "impossible_location"],
        reasons=["6 transactions within 10 minutes", "Amount 80000.00 is 160x the average"],
        status="PENDING_REVIEW",
    )


def _fake_transaction():
    return SimpleNamespace(
        to_dict=lambda: {
            "id": 42,
            "account_id": "ACC-MULTI",
            "amount": 80000.0,
            "timestamp": utcnow().isoformat(),
            "location": "London, UK",
        }
    )


# ------------------------------------------------------------------ unit level
def test_topic_is_created_when_no_arn_is_configured(monkeypatch):
    fake = FakeSnsClient()
    service = _service(monkeypatch, fake)

    arn = service.ensure_topic()

    assert arn == TOPIC_ARN
    assert fake.topics_created == ["fraud-alerts"]


def test_publish_sends_the_expected_payload(monkeypatch):
    fake = FakeSnsClient()
    service = _service(monkeypatch, fake)

    outcome = service.publish_fraud_alert(_fake_transaction(), _fake_flag())

    assert outcome.published is True
    assert outcome.message_id == "11111111-2222-3333-4444-555555555555"
    assert len(fake.published) == 1

    call = fake.published[0]
    assert call["TopicArn"] == TOPIC_ARN
    payload = json.loads(call["Message"])
    assert payload["transaction_id"] == 42
    assert payload["account_id"] == "ACC-MULTI"
    assert payload["risk_score"] == 100
    assert payload["risk_level"] == "HIGH"
    assert payload["triggered_rules"] == [
        "transaction_velocity",
        "unusual_amount",
        "impossible_location",
    ]
    assert call["MessageAttributes"]["risk_level"]["StringValue"] == "HIGH"


def test_publish_failure_is_reported_not_raised(monkeypatch):
    fake = FakeSnsClient(fail=True)
    service = _service(monkeypatch, fake)

    outcome = service.publish_fraud_alert(_fake_transaction(), _fake_flag())

    assert outcome.published is False
    assert outcome.error


def test_notifications_can_be_disabled(monkeypatch):
    fake = FakeSnsClient()
    service = FraudNotificationService(_settings(notifications_enabled=False))
    monkeypatch.setattr(service, "_client", lambda: fake)

    outcome = service.publish_fraud_alert(_fake_transaction(), _fake_flag())

    assert outcome.published is False
    assert outcome.error == "notifications disabled"
    assert fake.published == []


def test_health_reports_unavailable_localstack(monkeypatch):
    service = _service(monkeypatch, FakeSnsClient(fail=True))

    ok, detail = service.health()

    assert ok is False
    assert "unavailable" in detail


# ------------------------------------------------------------- API integration
def _payload(account_id, amount, minutes_ago, latitude=None, longitude=None, location=None):
    payload = {
        "account_id": account_id,
        "amount": amount,
        "timestamp": (utcnow() - timedelta(minutes=minutes_ago)).isoformat(),
    }
    if latitude is not None:
        payload["latitude"] = latitude
        payload["longitude"] = longitude
        payload["location"] = location
    return payload


CHENNAI = (13.0827, 80.2707)
LONDON = (51.5074, -0.1278)


def _create_high_risk_scenario(client):
    """Baseline spending in Chennai, then a burst ending in a huge London payment."""
    for days in (7, 6, 5, 4):
        client.post(
            "/api/transactions",
            json=_payload("ACC-HIGH", 500.0, days * 1440, *CHENNAI, "Chennai, IN"),
        )
    for minutes in (5, 4, 3, 2, 1):
        client.post(
            "/api/transactions",
            json=_payload("ACC-HIGH", 500.0, minutes, *CHENNAI, "Chennai, IN"),
        )
    return client.post(
        "/api/transactions",
        json=_payload("ACC-HIGH", 80_000.0, 0, *LONDON, "London, UK"),
    )


def _with_spy(client, spy):
    from main import app

    app.dependency_overrides[get_notification_service] = lambda: spy
    return client


def test_high_risk_transaction_publishes_an_sns_alert(client, spy_notifier):
    _with_spy(client, spy_notifier)

    response = _create_high_risk_scenario(client)

    assert response.status_code == 201
    body = response.json()
    assert body["evaluation"]["risk_level"] == "HIGH"
    assert set(body["evaluation"]["triggered_rules"]) == {
        "transaction_velocity",
        "unusual_amount",
        "impossible_location",
    }
    assert len(spy_notifier.calls) == 1
    assert body["alert_published"] is True
    assert body["fraud_flag"]["alert_published"] is True


def test_medium_risk_transaction_does_not_notify(client, spy_notifier):
    _with_spy(client, spy_notifier)

    for index in range(6):
        response = client.post(
            "/api/transactions", json=_payload("ACC-MEDIUM", 100.0, 6 - index)
        )

    body = response.json()
    assert body["evaluation"]["risk_level"] == "MEDIUM"
    assert body["evaluation"]["triggered_rules"] == ["transaction_velocity"]
    assert spy_notifier.calls == []


def test_notification_failure_does_not_break_the_fraud_record(client):
    from main import app

    failing_spy = SpyNotifier(published=False, error="LocalStack is down")
    app.dependency_overrides[get_notification_service] = lambda: failing_spy

    response = _create_high_risk_scenario(client)

    assert response.status_code == 201
    body = response.json()
    # The transaction and the fraud flag are still persisted and usable.
    assert body["fraud_flag"]["alert_published"] is False
    assert body["fraud_flag"]["alert_error"] == "LocalStack is down"
    assert client.get("/api/fraud-flags").json()["total"] == 1


def test_notification_service_dependency_is_overridable(client, spy_notifier):
    """Guards the seam used by every notification test above."""
    from main import app

    assert get_notification_service() is not spy_notifier
    app.dependency_overrides[get_notification_service] = lambda: spy_notifier
    assert app.dependency_overrides[get_notification_service]() is spy_notifier
