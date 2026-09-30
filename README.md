# Fraud Rule Engine with Review Console

A plugin-based fraud rule engine with a React reviewer console, PostgreSQL
persistence, and AWS SNS high-risk alerts emulated locally via LocalStack.
No real AWS account or paid services required: `docker compose up --build`.

```
payment event -> FastAPI backend -> rule engine -+-> PostgreSQL (transactions + fraud_flags)
                                                 +-> SNS fraud-alerts (LocalStack) on HIGH risk
reviewer -> React console -> flags -> REVIEWED / CONFIRMED_FRAUD / CLEARED
```

Demo risk policy (illustrative, not banking standards): velocity +30, unusual
amount +30, impossible travel +40. Levels: 0-29 LOW, 30-59 MEDIUM, 60+ HIGH.

## Architecture

```
React console (:5173) --REST--> FastAPI backend (:8000, main.py)
api/ (thin HTTP) -> services/fraud_service.py -> fraud_engine/ (pure)
FraudEngine runs velocity, amount, location rules independently,
aggregates scores via RiskPolicy, persists to PostgreSQL :5432,
publishes HIGH alerts to LocalStack SNS :4566. seed.py demos all cases.
```

Backend layering: `api/` -> `services/fraud_service.py` (orchestration) ->
`fraud_engine/` (no DB, no AWS) + `services/notification_service.py`.
Rules take immutable `TransactionData` + `EvaluationContext` (history).

## Stack

React 18 + Vite 5 (plain CSS) | Python 3.11, FastAPI, Pydantic v2,
SQLAlchemy 2 | PostgreSQL 15 (Numeric money, JSONB payloads) |
LocalStack 3 + boto3 SNS | Docker Compose | pytest + vitest.

## Directory structure

```
docker-compose.yml  .env.example  README.md
localstack/init/01-create-sns-topic.sh
backend/main.py  requirements.txt  Dockerfile  seed.py  app/
  config.py  dependencies.py  api/ (transactions, reviews, stats, health)
  fraud_engine/ (base, engine, risk, registry, geo)  rules/ (velocity, amount, location)
  models/ (transaction, fraud_flag, status)  schemas/  services/  database/  tests/ (9 modules)
frontend/Dockerfile  vite.config.js  src/ (App, api, utils, components/Dashboard, FlagTable, FlagDetail)
```
## Fraud rules

All rules implement `FraudRule.evaluate(transaction, context)` returning
`RuleResult(rule, triggered, reason, score, details)`, registered with
`@register_rule` and auto-discovered. Engine never imports concrete rules.

1. `transaction_velocity`: count of account txns in `[now-W, now]` (DB history
   + new row); fires when count > N. Env: `VELOCITY_MAX_TRANSACTIONS=5`,
   `VELOCITY_WINDOW_MINUTES=10`, score `VELOCITY_SCORE=30`.
2. `unusual_amount` (simplified demo): fires when `amount > mean(last<=50, min 3) x M`.
   Env: `AMOUNT_MULTIPLIER=10`, score `AMOUNT_SCORE=30`.
3. `impossible_location`: Haversine distance vs previous txn with coords;
   `speed = dist/dt`; fires when `speed > V` and `dist > 1km`.
   Env: `MAX_TRAVEL_SPEED_KMH=1000`, score `LOCATION_SCORE=40`.

Skips (not errors) on no history / missing coords; zero dt = infinite speed.
A broken plugin is caught and recorded, never breaks evaluation.

## Risk scoring

Engine sums triggered scores; `RiskPolicy`: >=60 HIGH, >=30 MEDIUM else LOW.
Every txn persists triggered_rules, per-rule rule_details, risk_score,
risk_level, reasons. Scores computed server-side only.

## API (docs at http://localhost:8000/docs, JSON, no stack traces)

- POST /api/transactions (201: {transaction, evaluation, fraud_flag})
- GET /api/transactions?account_id=&limit=&offset= ; GET /api/transactions/{id}
- GET /api/fraud-flags?status=&risk_level=&account_id=&limit=&offset= (embeds transaction)
- GET /api/fraud-flags/{id} (flag + transaction + 10-row history + policy + allowed transitions)
- PATCH /api/fraud-flags/{id}/review {"status": REVIEWED|CONFIRMED_FRAUD|..., "reviewer": "name"}
- PATCH /api/fraud-flags/{id}/clear {"reviewer": "name"} (shortcut to CLEARED)
- GET /api/stats/summary (dashboard counters) ; GET /api/stats/engine (plugins + policy)
- GET /health {status, database, notifications, rules} ; GET / (info + rule names)

Transitions: PENDING_REVIEW->{REVIEWED,CLEARED,CONFIRMED_FRAUD};
REVIEWED->{CLEARED,CONFIRMED_FRAUD,PENDING_REVIEW}; terminal states reopen via
PENDING_REVIEW only. Illegal -> 409, bad status -> 422, missing -> 404.
## Database schema

transactions(id, account_id, amount NUMERIC(14,2), timestamp TIMESTAMPTZ,
latitude/longitude DOUBLE, location VARCHAR(128), created_at), indexed on
(account_id, timestamp). fraud_flags(id, transaction_id UNIQUE FK CASCADE,
risk_score INT, risk_level VARCHAR, triggered_rules/reasons/rule_details JSONB,
status default PENDING_REVIEW, reviewed_at/by, alert_published BOOL,
alert_error TEXT, created_at). One-to-one Transaction<->FraudFlag.

## LocalStack (no AWS account needed)

localstack:3.8 (SNS+SQS) on :4566; init hook
`localstack/init/01-create-sns-topic.sh` creates topic `fraud-alerts`,
queue `fraud-alerts-queue` (env `SQS_QUEUE_NAME`), and the SNS->SQS
subscription with RawMessageDelivery, so every HIGH alert payload is
readable. Backend startup also ensures the topic via idempotent
create_topic. All env-configurable: AWS_ENDPOINT_URL, SNS_TOPIC_NAME,
SQS_QUEUE_NAME, NOTIFICATIONS_ENABLED, dummy test/test creds. HIGH
verdict publishes {transaction_id, account_id, amount, risk_score,
risk_level, triggered_rules, reasons, timestamp} with short timeouts;
never raises; outcome stored as alert_published/alert_error. View
payloads (queue URL from `awslocal sqs list-queues`):

```bash
docker exec fraud-localstack awslocal sns list-topics
docker exec fraud-localstack awslocal sqs list-queues
docker exec fraud-localstack awslocal sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:000000000000:fraud-alerts
docker exec fraud-localstack awslocal sqs receive-message \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/fraud-alerts-queue \
  --max-number-of-messages 10
# or from the host (needs AWS CLI + AWS_ENDPOINT_URL=http://localhost:4566):
aws --endpoint-url=http://localhost:4566 sns list-topics
```

## Docker

postgres (healthy-gated) + localstack + backend (:8000, waits for postgres) +
frontend (:5173, VITE_API_URL for browser->backend). Tunables in .env.example.

## How to run (step by step)

### Prerequisites

- Git, Docker Desktop (with Docker Compose v2), 8 GB RAM free.
- Ports free: 5432 (postgres), 4566 (localstack), 8000 (backend), 5173 (frontend).
- No AWS account needed. No real credentials needed.

Check:

```bash
docker --version
docker compose version
git --version
```

If Docker Desktop is stopped, start it first. On Windows confirm
`docker info` works before continuing.

### Step 1 - Get the code

```bash
git clone <your-fork-url> acentra-fraud-engine
cd acentra-fraud-engine
```

You should see `docker-compose.yml`, `backend/`, `frontend/`,
`localstack/`, `.env.example`, `README.md`.

### Step 2 - Configure environment (optional but recommended)

```bash
cp .env.example .env
```

Defaults already work for demo. This repo ships a `.env` that remaps
host ports because `ecommerce-db` already owns 5432 on this machine:
`POSTGRES_PORT=5433`, `BACKEND_PORT=8000`, `FRONTEND_PORT=5174`
(container-internal ports are unchanged). **Important:** shell env vars
override `.env` in Compose — if you previously ran the SQLite fallback
(`$env:DATABASE_URL`, `$env:NOTIFICATIONS_ENABLED='false'`), clear them
first or the container inherits `NOTIFICATIONS_ENABLED=false` and SNS
stays disabled:

```powershell
$env:DATABASE_URL=$null; $env:NOTIFICATIONS_ENABLED=$null
docker compose down
docker compose up --build -d
```

Frontend URL is therefore http://localhost:5174 (not 5173) on this
machine. `VITE_API_URL=http://localhost:8000` (browser -> backend).

### Step 3 - Start all four services

```bash
docker compose up --build
```

What happens: postgres starts first (health-gated), localstack boots
and runs `localstack/init/01-create-sns-topic.sh` to create the
`fraud-alerts` SNS topic, backend builds, waits for healthy postgres,
creates tables via `init_db()` and ensures the SNS topic via boto3
`create_topic` (idempotent), frontend serves the Vite dev server.

Wait until you see `fraud-backend` responding. In a second terminal:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs fraud-backend --tail 20
docker logs fraud-localstack --tail 10
docker exec fraud-backend curl -s http://localhost:8000/health
```

Expected health JSON: `{"status": "healthy", "database": "up",
"notifications": "up", "notification_detail": "ok", "rules":
[...]}`. On this machine the init hook must use LF line endings —
CRLF breaks it with `No such file or directory:
'/etc/localstack/init/ready.d/01-create-sns-topic.sh'` (fixed; the
backend's own `create_topic` is the real safety net).

Open in browser:

- Reviewer console: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/health
- Engine info: http://localhost:8000/api/stats/engine

### Step 4 - Seed the demo data (required for hackathon demo)

```bash
docker compose exec backend python seed.py --reset
```

This creates six deterministic scenarios via `POST
/api/transactions`: ACC-NORMAL (clean), ACC-VELOCITY (6 in 6 min ->
velocity +30 MEDIUM), ACC-AMOUNT (4x500 baseline then 45000 -> amount
+30 MEDIUM), ACC-LOCATION (Chennai -> London in 5 min -> location +40
MEDIUM), ACC-MULTI (burst + huge amount + teleport -> 100 HIGH + SNS
alert), ACC-TRAVEL (Chennai -> Bengaluru over 8h -> clean). The seeder
prints every verdict plus a summary table. Refresh the console at
:5173 to see flags appear.

Alternative without docker exec (from repo root, stack must be up):

```bash
python backend/seed.py --api-url http://localhost:8000 --reset
```

### Step 5 - Walk the reviewer flow

1. Console dashboard (`/api/stats/summary`): totals, flagged, HIGH,
   pending, cleared.
2. Flag table (`GET /api/fraud-flags`): id, account, amount,
   timestamp, location, risk score/level, status, triggered rules.
3. Click HIGH ACC-MULTI row (`GET /api/fraud-flags/{id}`): full
   transaction, risk score/level, per-rule reasons + details
   (counts, average/ratio, distance/speed math), 10-row history,
   allowed transitions.
4. `PATCH /api/fraud-flags/{id}/review` with `{"status": "REVIEWED",
   "reviewer": "demo"}` then `PATCH
   /api/fraud-flags/{id}/clear` with `{"reviewer": "demo"}`. Illegal
   moves (e.g. CLEARED -> REVIEWED) return 409 with allowed list.

### Step 6 - Verify HIGH-risk SNS via LocalStack

```bash
docker compose logs backend | grep -i -E "sns|HIGH|alert"
```

List the emulated topic (needs AWS CLI or awslocal; dummy creds
`test`/`test` are fine):

```bash
aws --endpoint-url=http://localhost:4566 sns list-topics
```

The backend publishes `{transaction_id, account_id, amount,
risk_score, risk_level, triggered_rules, reasons, timestamp}` only on
HIGH. Outcome is stored on the flag (`alert_published`,
`alert_error`); a failed publish never rolls back the fraud record.

### Step 7 - Run tests

```bash
docker compose config                    # compose validation
cd backend && python -m pytest tests -q  # 81 backend tests (rules, engine, API, SNS, integration)
cd ../frontend && npm install && npm test && npm run build
```

Note: outside Docker use the project venv
(`.venv/Scripts/python.exe -m pytest backend/tests -q`) so `boto3`
resolves. Frontend vitest covers 8 util cases; `vite build` must
succeed.

### Step 8 - Stop / reset

```bash
docker compose down        # stop, keep postgres volume
docker compose down -v     # stop + wipe demo data (fresh next demo)
docker compose up --build  # start again
```

### Backend-only mode (no Docker, for quick API hacking)

```bash
cd backend
pip install -r requirements.txt
# Windows cmd:
set DATABASE_URL=sqlite:///./local_demo.sqlite3
# bash:
export DATABASE_URL=sqlite:///./local_demo.sqlite3
python -m uvicorn main:app --reload
# open http://localhost:8000/docs
```

Postgres is used in Docker; SQLite here is dev/test convenience
only. SNS calls fail gracefully (`alert_error` set) when LocalStack
is not running.
## Seed demo data (6 scenarios)

docker compose exec backend python seed.py --reset (or python backend/seed.py
--api-url http://localhost:8000 --reset). ACC-NORMAL clean; ACC-VELOCITY 6 in
6min -> velocity +30 MEDIUM; ACC-AMOUNT 4x500 then 45000 -> amount +30 MEDIUM;
ACC-LOCATION Chennai->London 5min -> location +40 MEDIUM; ACC-MULTI all three
-> 100 HIGH + SNS; ACC-TRAVEL Chennai->Bengaluru 8h realistic -> clean.

## Testing

cd backend && python -m pytest tests -q (~100 tests: rules below/at/above,
window expiry, per-account isolation, amount spike/history, Haversine ~8200km
Chennai-London, zero-dt, engine aggregation/levels/dynamic registration/fault
isolation, API CRUD + 409/422/404, SNS publish + failure safety, full
integration). cd frontend && npm install && npm test && npm run build.
docker compose config validates compose.

## Demo script (~3 min)

up --build, open :5173, seed --reset, click HIGH ACC-MULTI (3 rules + math +
history), Mark Reviewed then Clear a MEDIUM flag, show 409 guard in /docs,
grep backend logs for SNS publish, note NORMAL/TRAVEL stay clean.

## Design decisions

Boring on purpose (no K8s/auth/ML); engine purity (rules pure, DB/AWS in
services/); reliability ordering (history before insert, flag commit before
SNS, failure marks alert_error only); honest prototype docs; env knobs.

## Add a new rule (no engine changes)

Create backend/app/fraud_engine/rules/device_rule.py with @register_rule class
(FraudRule: name, description, from_settings, evaluate->RuleResult.hit/clear,
describe). Registry auto-discovers; restart backend; score flows into total;
listed at /api/stats/engine; console renders with zero frontend changes.
See README history / registry.py docstring for full example.

## Acceptance

Compose up all services; CRUD + persist; 3 rules independent; engine rule-free;
dynamic registration; scores/levels persisted; React flags + detail + review +
clear + 409 guard; HIGH->SNS via LocalStack, no AWS; seed covers all scenarios;
tests green; this README complete.
