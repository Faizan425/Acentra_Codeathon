"""End-to-end integration test of the whole fraud pipeline.

Flow: create a suspicious transaction -> rules execute -> fraud flag persisted ->
HIGH risk detected -> SNS notification generated -> transaction visible in the
reviewer console -> reviewer can act on it.
"""

from __future__ import annotations

from datetime import timedelta

from app.dependencies import get_fraud_engine, get_notification_service

from tests.conftest import SpyNotifier, utcnow

CHENNAI = (13.0827, 80.2707)
LONDON = (51.5074, -0.1278)


def _payload(account_id, amount, minutes_ago, lat, lon, location):
    return {
        "account_id": account_id,
        "amount": amount,
        "timestamp": (utcnow() - timedelta(minutes=minutes_ago)).isoformat(),
        "latitude": lat,
        "longitude": lon,
        "location": location,
    }


def _seed_baseline(client, account_id="ACC-E2E"):
    """Routine Chennai spending so the amount rule has a baseline."""
    for days in (7, 6, 5, 4):
        response = client.post(
            "/api/transactions",
            json=_payload(account_id, 500.0, days * 1440, *CHENNAI, "Chennai, IN"),
        )
        assert response.status_code == 201
    for minutes in (5, 4, 3, 2, 1):
        response = client.post(
            "/api/transactions",
            json=_payload(account_id, 500.0, minutes, *CHENNAI, "Chennai, IN"),
        )
        assert response.status_code == 201


def test_full_fraud_pipeline_from_http_request_to_reviewer_console(client):
    from main import app

    spy = SpyNotifier()
    app.dependency_overrides[get_notification_service] = lambda: spy

    _seed_baseline(client)

    # 1. the suspicious transaction arrives
    response = client.post(
        "/api/transactions",
        json=_payload("ACC-E2E", 80_000.0, 0, *LONDON, "London, UK"),
    )
    assert response.status_code == 201
    created = response.json()
    transaction_id = created["transaction"]["id"]

    # 2. every rule executed and reported its verdict
    assert {entry["rule"] for entry in created["evaluation"]["rule_details"]} == {
        "transaction_velocity",
        "unusual_amount",
        "impossible_location",
    }

    # 3. all three rules fired and the scores were aggregated
    assert set(created["evaluation"]["triggered_rules"]) == {
        "transaction_velocity",
        "unusual_amount",
        "impossible_location",
    }
    assert created["evaluation"]["risk_score"] == 100
    assert created["evaluation"]["risk_level"] == "HIGH"

    # 4. the fraud flag was persisted with its explanations
    flag = created["fraud_flag"]
    assert flag["status"] == "PENDING_REVIEW"
    assert flag["risk_score"] == 100
    assert len(flag["reasons"]) == 3
    assert any("Implied travel speed" in reason for reason in flag["reasons"])

    # 5. a HIGH risk transaction triggered exactly one SNS notification
    assert len(spy.calls) == 1
    assert spy.calls[0]["transaction"].id == transaction_id
    assert spy.calls[0]["flag"].risk_level == "HIGH"
    assert flag["alert_published"] is True

    # 6. the transaction is visible in the reviewer console
    listing = client.get("/api/fraud-flags").json()
    assert listing["total"] == 1
    listed = listing["items"][0]
    assert listed["id"] == flag["id"]
    assert listed["transaction_id"] == transaction_id

    detail = client.get(f"/api/fraud-flags/{flag['id']}").json()
    assert detail["transaction"]["account_id"] == "ACC-E2E"
    assert detail["transaction"]["amount"] == 80_000.0
    assert detail["history"]  # historical context for the reviewer

    summary = client.get("/api/stats/summary").json()
    assert summary["total_transactions"] == 10
    assert summary["flagged_transactions"] == 1
    assert summary["high_risk_transactions"] == 1
    assert summary["pending_reviews"] == 1

    # 7. the reviewer marks it reviewed, then clears it
    reviewed = client.patch(
        f"/api/fraud-flags/{flag['id']}/review",
        json={"status": "REVIEWED", "reviewer": "alice"},
    )
    assert reviewed.status_code == 200

    cleared = client.patch(f"/api/fraud-flags/{flag['id']}/clear", json={"reviewer": "alice"})
    assert cleared.status_code == 200
    assert cleared.json()["flag"]["status"] == "CLEARED"

    summary_after = client.get("/api/stats/summary").json()
    assert summary_after["pending_reviews"] == 0
    assert summary_after["cleared_transactions"] == 1


def test_new_rule_plugin_is_picked_up_by_the_api_without_engine_changes(client):
    """Proves the plugin architecture end to end (the request path uses it)."""
    from main import app

    from app.fraud_engine.base import FraudRule, RuleResult
    from app.fraud_engine.engine import FraudEngine
    from app.fraud_engine.rules.amount_rule import UnusualAmountRule

    class LargeSinglePaymentRule(FraudRule):
        """Demo plugin: flags any single payment of 1000 or more."""

        name = "large_single_payment"

        def evaluate(self, transaction, context):
            if transaction.amount >= 1000:
                return RuleResult.hit(
                    self.name,
                    "Single payment of 1000 or more",
                    45,
                    {"amount": transaction.amount},
                )
            return RuleResult.clear(self.name, "Amount below the plugin threshold")

    app.dependency_overrides[get_fraud_engine] = lambda: FraudEngine(
        [LargeSinglePaymentRule(), UnusualAmountRule()]
    )

    response = client.post(
        "/api/transactions",
        json=_payload("ACC-PLUGIN", 5000.0, 0, *CHENNAI, "Chennai, IN"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["evaluation"]["triggered_rules"] == ["large_single_payment"]
    assert body["evaluation"]["risk_score"] == 45
    assert body["evaluation"]["risk_level"] == "MEDIUM"

    # The REST surface did not change at all to support the new rule.
    engine_info = client.get("/api/stats/engine").json()
    assert {rule["name"] for rule in engine_info["rules"]} == {
        "large_single_payment",
        "unusual_amount",
    }


def test_transactions_survive_engine_failures(client):
    """A crash inside one plugin must not lose the transaction."""
    from main import app

    from app.fraud_engine.base import FraudRule
    from app.fraud_engine.engine import FraudEngine

    class ExplodingRule(FraudRule):
        name = "exploding_rule"

        def evaluate(self, transaction, context):
            raise RuntimeError("unexpected plugin failure")

    app.dependency_overrides[get_fraud_engine] = lambda: FraudEngine([ExplodingRule()])

    response = client.post(
        "/api/transactions",
        json=_payload("ACC-BOOM", 100.0, 0, *CHENNAI, "Chennai, IN"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction"]["id"] > 0
    assert body["evaluation"]["risk_score"] == 0
    assert body["fraud_flag"] is None
    assert client.get("/api/transactions").json()["total"] == 1
