#!/bin/bash
# LocalStack "ready" hook - creates the SNS topic, an SQS queue, and the
# subscription between them so HIGH-risk alert payloads are visible via
# `awslocal sqs receive-message`. The backend also creates the topic on
# startup, so this is a belt-and-braces measure.
set -euo pipefail

TOPIC_NAME="${SNS_TOPIC_NAME:-fraud-alerts}"
QUEUE_NAME="${SQS_QUEUE_NAME:-fraud-alerts-queue}"

echo "[localstack-init] ensuring SNS topic '${TOPIC_NAME}' + SQS queue '${QUEUE_NAME}'"
TOPIC_ARN="$(awslocal sns create-topic --name "${TOPIC_NAME}" --query 'TopicArn' --output text)"
QUEUE_URL="$(awslocal sqs create-queue --queue-name "${QUEUE_NAME}" --query 'QueueUrl' --output text)"
QUEUE_ARN="$(awslocal sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
awslocal sns subscribe --topic-arn "${TOPIC_ARN}" --protocol sqs --notification-endpoint "${QUEUE_ARN}" --attributes RawMessageDelivery=true >/dev/null
awslocal sns list-topics
awslocal sqs list-queues
echo "[localstack-init] done: ${TOPIC_ARN} -> ${QUEUE_ARN}"
