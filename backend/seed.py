"""Demo data seeder.

Creates transactions that deterministically demonstrate every rule:

=====================  ===========================================  ==========
Account                Scenario                                     Expected
=====================  ===========================================  ==========
ACC-NORMAL             One ordinary payment in Chennai               no flag
ACC-VELOCITY           6 payments in 5 minutes                       MEDIUM (30)
ACC-AMOUNT             45,000 against a ~500 baseline                MEDIUM (30)
ACC-LOCATION           Chennai -> London five minutes later          MEDIUM (40)
ACC-MULTI              Burst + huge amount + impossible travel        HIGH (100) + SNS
=====================  ===========================================  ==========

Usage (from the repository root, with the stack running):

    docker compose exec backend python seed.py
    # or, against a locally running API:
    python backend/seed.py --api-url http://localhost:8000

Add ``--reset`` to wipe existing rows first for a clean demo.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

CHENNAI = {"latitude": 13.0827, "longitude": 80.2707, "location": "Chennai, IN"}
BENGALURU = {"latitude": 12.9716, "longitude": 77.5946, "location": "Bengaluru, IN"}
LONDON = {"latitude": 51.5074, "longitude": -0.1278, "location": "London, UK"}


def _iso(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


class SeedClient:
    def __init__(self, api_url: str, verbose: bool = True) -> None:
        self.api_url = api_url.rstrip("/")
        self.verbose = verbose
        self.created: List[Dict[str, Any]] = []

    def create(
        self,
        account_id: str,
        amount: float,
        minutes_ago: float,
        place: Dict[str, Any],
        label: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "account_id": account_id,
            "amount": amount,
            "timestamp": _iso(minutes_ago),
            **place,
        }
        response = requests.post(f"{self.api_url}/api/transactions", json=payload, timeout=15)
        if response.status_code != 201:
            raise SystemExit(
                f"Failed to create transaction for {account_id}: "
                f"{response.status_code} {response.text}"
            )
        body = response.json()
        if self.verbose:
            flag = body.get("fraud_flag")
            verdict = (
                f"FLAGGED {flag['risk_level']} score={flag['risk_score']} "
                f"rules={','.join(flag['triggered_rules'])}"
                if flag
                else "clean"
            )
            print(
                f"  {account_id:<14} {amount:>12,.2f}  {place['location']:<14} -> {verdict}"
                + (f"   [{label}]" if label else "")
            )
        self.created.append(body)
        return body

    def reset(self) -> None:
        """Delete every row directly through the ORM (no API round-trip)."""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.database.session import SessionLocal
        from app.models.fraud_flag import FraudFlag
        from app.models.transaction import Transaction

        session = SessionLocal()
        try:
            deleted_flags = session.query(FraudFlag).delete()
            deleted_tx = session.query(Transaction).delete()
            session.commit()
            print(f"Reset database: removed {deleted_tx} transactions and {deleted_flags} flags")
        finally:
            session.close()


# --------------------------------------------------------------------- scenarios
def seed_scenario_1_normal(client: SeedClient) -> None:
    """One ordinary payment: no rule should fire."""
    print("\n[1] Normal transaction (expected: no flag)")
    client.create("ACC-NORMAL", 250.0, 30, CHENNAI, "single small payment")


def seed_scenario_2_velocity(client: SeedClient) -> None:
    """6 transactions inside 5 minutes -> limit is 5 per 10 minutes."""
    print("\n[2] Transaction velocity (expected: transaction_velocity, +30 = MEDIUM)")
    for index in range(6):
        client.create("ACC-VELOCITY", 120.0, 6 - index, CHENNAI, f"burst #{index + 1}")


def seed_scenario_3_amount(client: SeedClient) -> None:
    """Baseline of ~500, then a 45,000 payment -> 90x the average (limit 10x)."""
    print("\n[3] Unusual amount (expected: unusual_amount, +30 = MEDIUM)")
    for index, days in enumerate((40, 30, 20, 10), start=1):
        client.create("ACC-AMOUNT", 500.0, days * 1440, CHENNAI, f"baseline #{index}")
    client.create("ACC-AMOUNT", 45_000.0, 1, CHENNAI, "huge payment")


def seed_scenario_4_location(client: SeedClient) -> None:
    """Chennai -> London in five minutes -> ~98,000 km/h."""
    print("\n[4] Impossible location (expected: impossible_location, +40 = MEDIUM)")
    client.create("ACC-LOCATION", 2_000.0, 5, CHENNAI, "payment in Chennai")
    client.create("ACC-LOCATION", 2_500.0, 0, LONDON, "payment in London 5 min later")


def seed_scenario_5_multiple(client: SeedClient) -> None:
    """Baseline + burst + huge amount + teleport -> HIGH risk and an SNS alert."""
    print("\n[5] Multiple rules at once (expected: HIGH 100 + SNS alert)")
    for index, days in enumerate((45, 35, 25, 15), start=1):
        client.create("ACC-MULTI", 500.0, days * 1440, CHENNAI, f"baseline #{index}")
    for minutes in (5, 4, 3, 2, 1):
        client.create("ACC-MULTI", 500.0, minutes, CHENNAI, "burst")
    client.create("ACC-MULTI", 80_000.0, 0, LONDON, "BIG payment from London")


def seed_scenario_6_normal_travel(client: SeedClient) -> None:
    """Realistic travel should not trigger the impossible-travel rule."""
    print("\n[6] Realistic travel (expected: no flag)")
    client.create("ACC-TRAVEL", 800.0, 8 * 60, CHENNAI, "morning payment")
    client.create("ACC-TRAVEL", 900.0, 60, BENGALURU, "later payment 290 km away")


def run_all(client: SeedClient) -> None:
    seed_scenario_1_normal(client)
    seed_scenario_2_velocity(client)
    seed_scenario_3_amount(client)
    seed_scenario_4_location(client)
    seed_scenario_5_multiple(client)
    seed_scenario_6_normal_travel(client)


def print_summary(client: SeedClient) -> None:
    summary = requests.get(f"{client.api_url}/api/stats/summary", timeout=15).json()
    print("\n" + "=" * 78)
    print("SEED SUMMARY")
    print("=" * 78)
    print(f"  transactions created in this run : {len(client.created)}")
    print(f"  total transactions in database   : {summary['total_transactions']}")
    print(f"  flagged transactions             : {summary['flagged_transactions']}")
    print(f"  HIGH risk                        : {summary['high_risk_transactions']}")
    print(f"  MEDIUM risk                      : {summary['medium_risk_transactions']}")
    print(f"  pending reviews                  : {summary['pending_reviews']}")

    flags = requests.get(f"{client.api_url}/api/fraud-flags", timeout=15).json()["items"]
    if flags:
        print("\n  Flagged transactions:")
        print(f"  {'ID':>4}  {'ACCOUNT':<14} {'AMOUNT':>12}  {'LEVEL':<7} {'SCORE':>5}  RULES")
        for flag in flags:
            tx = flag["transaction"]
            print(
                f"  {flag['id']:>4}  {tx['account_id']:<14} {tx['amount']:>12,.2f}  "
                f"{flag['risk_level']:<7} {flag['risk_score']:>5}  "
                f"{', '.join(flag['triggered_rules'])}"
            )
    print("=" * 78)
    print("Open the reviewer console at http://localhost:5173")


# -------------------------------------------------------------------------- main
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the fraud engine demo data")
    parser.add_argument(
        "--api-url",
        default=os.getenv("API_URL", "http://localhost:8000"),
        help="Base URL of the fraud engine API",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing transactions and fraud flags first",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print the summary")
    args = parser.parse_args(argv)

    client = SeedClient(args.api_url, verbose=not args.quiet)

    try:
        health = requests.get(f"{client.api_url}/health", timeout=10)
        health.raise_for_status()
    except Exception as exc:
        print(f"API is not reachable at {client.api_url}: {exc}")
        print("Start the stack with: docker compose up --build")
        return 1

    print(f"Fraud Rule Engine demo seeder -> {client.api_url}")
    print(f"Rule plugins: {', '.join(health.json().get('rules', []))}")

    if args.reset:
        client.reset()

    run_all(client)
    print_summary(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
