"""Transaction API tests (creation, validation, listing, persistence)."""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import utcnow


def _payload(account_id="ACC-API", amount=250.0, minutes_ago=0, **extra):
    payload = {
        "account_id": account_id,
        "amount": amount,
        "timestamp": (utcnow() - timedelta(minutes=minutes_ago)).isoformat(),
    }
    payload.update(extra)
    return payload


def test_health_endpoint_reports_services(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "up"
    assert set(body["rules"]) >= {
        "transaction_velocity",
        "unusual_amount",
        "impossible_location",
    }


def test_root_endpoint_lists_the_engine_rules(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Fraud Rule Engine"


def test_create_transaction_is_persisted(client):
    response = client.post(
        "/api/transactions",
        json=_payload(amount=100.0, latitude=13.0827, longitude=80.2707, location="Chennai, IN"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction"]["id"] > 0
    assert body["transaction"]["account_id"] == "ACC-API"
    assert body["transaction"]["amount"] == 100.0
    assert body["evaluation"]["risk_score"] == 0
    assert body["evaluation"]["risk_level"] == "LOW"
    assert body["fraud_flag"] is None

    listing = client.get("/api/transactions").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == body["transaction"]["id"]


def test_client_supplied_risk_fields_are_rejected(client):
    """Risk is always computed on the backend, never accepted from the client."""
    response = client.post(
        "/api/transactions", json={**_payload(), "risk_score": 999, "risk_level": "LOW"}
    )

    assert response.status_code == 422


def test_invalid_amount_is_rejected(client):
    response = client.post("/api/transactions", json=_payload(amount=-10))

    assert response.status_code == 422


def test_missing_account_id_is_rejected(client):
    response = client.post("/api/transactions", json={"amount": 100})

    assert response.status_code == 422


def test_out_of_range_coordinates_are_rejected(client):
    response = client.post(
        "/api/transactions", json=_payload(latitude=123.0, longitude=80.0)
    )
    assert response.status_code == 422


def test_half_supplied_coordinates_are_rejected(client):
    response = client.post("/api/transactions", json=_payload(latitude=13.08))

    assert response.status_code == 422
    assert "together" in response.text


def test_invalid_timestamp_is_rejected(client):
    response = client.post(
        "/api/transactions", json={**_payload(), "timestamp": "not-a-timestamp"}
    )

    assert response.status_code == 422


def test_timestamp_defaults_to_now(client):
    response = client.post("/api/transactions", json={"account_id": "ACC-NOW", "amount": 10})

    assert response.status_code == 201
    assert response.json()["transaction"]["timestamp"] is not None


def test_transaction_persists_its_coordinates(client):
    response = client.post(
        "/api/transactions",
        json=_payload(latitude=51.5074, longitude=-0.1278, location="London, UK"),
    )

    body = response.json()["transaction"]
    assert body["latitude"] == 51.5074
    assert body["longitude"] == -0.1278
    assert body["location"] == "London, UK"


def test_get_transaction_404_for_unknown_id(client):
    response = client.get("/api/transactions/999999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_transactions_filters_by_account(client):
    client.post("/api/transactions", json=_payload(account_id="ACC-A"))
    client.post("/api/transactions", json=_payload(account_id="ACC-B"))

    listing = client.get("/api/transactions", params={"account_id": "ACC-A"}).json()

    assert listing["total"] == 1
    assert listing["items"][0]["account_id"] == "ACC-A"


def test_list_transactions_supports_pagination(client):
    for index in range(5):
        client.post("/api/transactions", json=_payload(minutes_ago=index))

    listing = client.get("/api/transactions", params={"limit": 2, "offset": 0}).json()

    assert listing["total"] == 5
    assert len(listing["items"]) == 2
    assert listing["limit"] == 2


def test_only_suspicious_transactions_are_flagged(client):
    normal = client.post("/api/transactions", json=_payload(account_id="ACC-NORMAL"))
    assert normal.json()["fraud_flag"] is None

    # 6 transactions in a few minutes from the same account trips the velocity rule.
    for index in range(6):
        response = client.post(
            "/api/transactions",
            json=_payload(account_id="ACC-FAST", minutes_ago=6 - index, amount=100.0),
        )

    body = response.json()
    assert body["fraud_flag"] is not None
    assert "transaction_velocity" in body["fraud_flag"]["triggered_rules"]
    assert body["evaluation"]["risk_score"] >= 30
