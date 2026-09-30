"""Fraud flag / reviewer console API tests."""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import utcnow


def _payload(account_id, amount=100.0, minutes_ago=0, **extra):
    payload = {
        "account_id": account_id,
        "amount": amount,
        "timestamp": (utcnow() - timedelta(minutes=minutes_ago)).isoformat(),
    }
    payload.update(extra)
    return payload


def _create_flagged(client, account_id="ACC-FLAGGED"):
    """Create 6 quick transactions: the last one trips the velocity rule."""
    response = None
    for index in range(6):
        response = client.post(
            "/api/transactions",
            json=_payload(account_id, amount=100.0, minutes_ago=6 - index),
        )
        assert response.status_code == 201
    return response.json()


def test_no_flags_when_nothing_is_suspicious(client):
    client.post("/api/transactions", json=_payload("ACC-CLEAN"))

    listing = client.get("/api/fraud-flags").json()

    assert listing["total"] == 0
    assert listing["items"] == []


def test_flagged_transaction_appears_in_the_console_list(client):
    created = _create_flagged(client)

    listing = client.get("/api/fraud-flags").json()

    assert listing["total"] == 1
    flag = listing["items"][0]
    assert flag["id"] == created["fraud_flag"]["id"]
    assert flag["status"] == "PENDING_REVIEW"
    assert flag["risk_level"] in {"MEDIUM", "HIGH"}
    assert flag["transaction"]["account_id"] == "ACC-FLAGGED"


def test_flag_detail_explains_every_rule(client):
    created = _create_flagged(client)
    flag_id = created["fraud_flag"]["id"]

    detail = client.get(f"/api/fraud-flags/{flag_id}").json()

    assert detail["risk_score"] >= 30
    assert "transaction_velocity" in detail["triggered_rules"]
    # Every rule reports a reason, triggered or not, so the reviewer understands why.
    rules_seen = {entry["rule"] for entry in detail["rule_details"]}
    assert rules_seen == {"transaction_velocity", "unusual_amount", "impossible_location"}
    triggered = [e for e in detail["rule_details"] if e["triggered"]]
    assert all(entry["reason"] for entry in triggered)
    assert detail["allowed_transitions"] == ["CLEARED", "CONFIRMED_FRAUD", "REVIEWED"]
    assert detail["risk_policy"]["high_threshold"] == 60
    # Historical context for the reviewer.
    assert len(detail["history"]) >= 1


def test_flag_detail_404_for_unknown_id(client):
    response = client.get("/api/fraud-flags/424242")

    assert response.status_code == 404


def test_mark_reviewed_records_timestamp_and_reviewer(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]

    response = client.patch(
        f"/api/fraud-flags/{flag_id}/review", json={"status": "REVIEWED", "reviewer": "alice"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["previous_status"] == "PENDING_REVIEW"
    assert body["flag"]["status"] == "REVIEWED"
    assert body["flag"]["reviewed_by"] == "alice"
    assert body["flag"]["reviewed_at"] is not None


def test_clear_transaction(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]

    response = client.patch(f"/api/fraud-flags/{flag_id}/clear", json={"reviewer": "bob"})

    assert response.status_code == 200
    body = response.json()
    assert body["flag"]["status"] == "CLEARED"
    assert body["flag"]["reviewed_by"] == "bob"
    assert body["flag"]["reviewed_at"] is not None


def test_default_review_action_is_reviewed(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]

    response = client.patch(f"/api/fraud-flags/{flag_id}/review", json={})

    assert response.status_code == 200
    assert response.json()["flag"]["status"] == "REVIEWED"


def test_invalid_status_value_is_rejected(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]

    response = client.patch(f"/api/fraud-flags/{flag_id}/review", json={"status": "BANANA"})

    assert response.status_code == 422
    assert "not a valid review status" in response.json()["detail"]


def test_invalid_status_transition_is_rejected(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]
    client.patch(f"/api/fraud-flags/{flag_id}/clear", json={})

    # A cleared flag must be reopened before another decision is recorded.
    response = client.patch(f"/api/fraud-flags/{flag_id}/review", json={"status": "REVIEWED"})

    assert response.status_code == 409
    assert "Cannot move fraud flag" in response.json()["detail"]


def test_cleared_flag_can_be_reopened(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]
    client.patch(f"/api/fraud-flags/{flag_id}/clear", json={})

    response = client.patch(
        f"/api/fraud-flags/{flag_id}/review", json={"status": "PENDING_REVIEW"}
    )

    assert response.status_code == 200
    body = response.json()["flag"]
    assert body["status"] == "PENDING_REVIEW"
    assert body["reviewed_at"] is None


def test_confirm_fraud_status_is_supported(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]

    response = client.patch(
        f"/api/fraud-flags/{flag_id}/review", json={"status": "CONFIRMED_FRAUD"}
    )

    assert response.status_code == 200
    assert response.json()["flag"]["status"] == "CONFIRMED_FRAUD"


def test_flags_can_be_filtered_by_status_and_risk(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]
    client.patch(f"/api/fraud-flags/{flag_id}/clear", json={})

    assert client.get("/api/fraud-flags", params={"status": "CLEARED"}).json()["total"] == 1
    assert client.get("/api/fraud-flags", params={"status": "PENDING_REVIEW"}).json()["total"] == 0
    assert client.get("/api/fraud-flags", params={"min_score": 10_000}).json()["total"] == 0


def test_dashboard_summary_reflects_reviewer_actions(client):
    flag_id = _create_flagged(client)["fraud_flag"]["id"]
    client.post("/api/transactions", json=_payload("ACC-PLAIN"))
    client.patch(f"/api/fraud-flags/{flag_id}/clear", json={})

    summary = client.get("/api/stats/summary").json()

    assert summary["total_transactions"] == 7
    assert summary["flagged_transactions"] == 1
    assert summary["pending_reviews"] == 0
    assert summary["cleared_transactions"] == 1


def test_engine_info_endpoint_lists_rules(client):
    response = client.get("/api/stats/engine")

    assert response.status_code == 200
    body = response.json()
    names = {rule["name"] for rule in body["rules"]}
    assert names >= {"transaction_velocity", "unusual_amount", "impossible_location"}
    assert body["risk_policy"]["high_threshold"] == 60
