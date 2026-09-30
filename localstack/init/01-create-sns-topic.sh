#!/bin/bash
# LocalStack "ready" hook - creates the SNS topic the backend publishes to.
# The backend also creates it on startup, so this is a belt-and-braces measure
# that makes the demo work even if the backend starts first.
set -euo pipefail

TOPIC_NAME="${SNS_TOPIC_NAME:-fraud-alerts}"

echo "[localstack-init] ensuring SNS topic '${TOPIC_NAME}'"
awslocal sns create-topic --name "${TOPIC_NAME}"
awslocal sns list-topics
echo "[localstack-init] done"
