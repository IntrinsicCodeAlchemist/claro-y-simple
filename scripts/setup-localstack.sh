#!/usr/bin/env bash
# =============================================================================
# setup-localstack.sh
# Bootstrap LocalStack with all AWS resources needed for local development
# of the Claro y Simple backend modules.
#
# Run once after starting the LocalStack container, before integration tests.
#
# Usage:
#   ./scripts/setup-localstack.sh
#   ./scripts/setup-localstack.sh --env-file backend/ingestion/.env
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

LOCALSTACK_ENDPOINT="http://localhost:4566"
HEALTH_URL="${LOCALSTACK_ENDPOINT}/_localstack/health"

# Resource names — override via .env or environment variables
S3_BUCKET_NAME="${S3_BUCKET_NAME:-claro-y-simple-contracts}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Table names are fixed by the interface contracts (interface-contracts.md)
TABLE_EXTRACTIONS="ContractExtractions"
TABLE_ANALYSES="ContractAnalyses"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Shorthand for aws cli pointing to LocalStack
aws_local() {
  aws --endpoint-url="${LOCALSTACK_ENDPOINT}" --region="${AWS_DEFAULT_REGION}" "$@"
}

# ---------------------------------------------------------------------------
# Parse arguments and load .env
# ---------------------------------------------------------------------------

ENV_FILE=""
if [[ "${1:-}" == "--env-file" && -n "${2:-}" ]]; then
  ENV_FILE="$2"
elif [[ -f "backend/ingestion/.env" ]]; then
  ENV_FILE="backend/ingestion/.env"
fi

if [[ -n "$ENV_FILE" ]]; then
  if [[ -f "$ENV_FILE" ]]; then
    log_info "Loading configuration from $ENV_FILE"
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" | grep -v '^#')
    set +o allexport
    # Re-apply after sourcing .env (env vars may have been overridden)
    S3_BUCKET_NAME="${S3_BUCKET_NAME:-claro-y-simple-contracts}"
    AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
  else
    log_warn "Env file '$ENV_FILE' not found — using defaults"
  fi
fi

# ---------------------------------------------------------------------------
# Step 1: Health check — verify LocalStack is running
# ---------------------------------------------------------------------------

log_info "Checking LocalStack health at ${HEALTH_URL} ..."

if ! curl --silent --fail --max-time 5 "${HEALTH_URL}" > /dev/null 2>&1; then
  log_error "LocalStack is not running or not reachable at ${LOCALSTACK_ENDPOINT}"
  log_error ""
  log_error "Start LocalStack with one of:"
  log_error "  docker run --rm -d -p 4566:4566 -p 4510-4559:4510-4559 localstack/localstack"
  log_error "  docker-compose up -d localstack"
  log_error ""
  log_error "Then wait a few seconds and re-run this script."
  exit 1
fi

# Verify that S3 and DynamoDB services are available
HEALTH_JSON=$(curl --silent --max-time 5 "${HEALTH_URL}")

for SERVICE in s3 dynamodb; do
  STATUS=$(python -c "
import sys, json
data = json.loads('${HEALTH_JSON//\'/\\\'}')
services = data.get('services', {})
print(services.get('${SERVICE}', 'unavailable'))
" 2>/dev/null || echo "unavailable")

  if [[ "$STATUS" != "running" && "$STATUS" != "available" ]]; then
    log_error "LocalStack service '${SERVICE}' is not ready (status: ${STATUS})"
    log_error "Wait a few seconds for LocalStack to finish initializing and try again."
    exit 1
  fi
done

log_info "LocalStack is healthy. S3 and DynamoDB are ready."
echo ""

# ---------------------------------------------------------------------------
# Tracking results for the summary
# ---------------------------------------------------------------------------

CREATED=()
EXISTED=()

# ---------------------------------------------------------------------------
# Step 2: S3 bucket + lifecycle policy
# ---------------------------------------------------------------------------

log_info "--- S3 bucket: ${S3_BUCKET_NAME} ---"

if aws_local s3api head-bucket --bucket "${S3_BUCKET_NAME}" > /dev/null 2>&1; then
  log_warn "Bucket '${S3_BUCKET_NAME}' already exists — skipping creation"
  EXISTED+=("S3 bucket: ${S3_BUCKET_NAME}")
else
  # us-east-1 does not accept a LocationConstraint; all other regions require it
  if [[ "${AWS_DEFAULT_REGION}" == "us-east-1" ]]; then
    aws_local s3api create-bucket \
      --bucket "${S3_BUCKET_NAME}" \
      > /dev/null
  else
    aws_local s3api create-bucket \
      --bucket "${S3_BUCKET_NAME}" \
      --create-bucket-configuration "LocationConstraint=${AWS_DEFAULT_REGION}" \
      > /dev/null
  fi
  log_info "Created S3 bucket: ${S3_BUCKET_NAME}"
  CREATED+=("S3 bucket: ${S3_BUCKET_NAME}")
fi

# Lifecycle policy: expire objects under contracts/ prefix after 24 hours.
# put-bucket-lifecycle-configuration is idempotent — overwrites existing rules.
log_info "Applying lifecycle policy: contracts/ prefix expires after 1 day ..."
aws_local s3api put-bucket-lifecycle-configuration \
  --bucket "${S3_BUCKET_NAME}" \
  --lifecycle-configuration '{
    "Rules": [
      {
        "ID": "expire-contracts-24h",
        "Status": "Enabled",
        "Filter": { "Prefix": "contracts/" },
        "Expiration": { "Days": 1 }
      }
    ]
  }' > /dev/null

log_info "Lifecycle policy applied."
echo ""

# ---------------------------------------------------------------------------
# Step 3: DynamoDB — ContractExtractions (TTL: 24 hours)
# ---------------------------------------------------------------------------

log_info "--- DynamoDB table: ${TABLE_EXTRACTIONS} ---"

if aws_local dynamodb describe-table --table-name "${TABLE_EXTRACTIONS}" > /dev/null 2>&1; then
  log_warn "Table '${TABLE_EXTRACTIONS}' already exists — skipping creation"
  EXISTED+=("DynamoDB table: ${TABLE_EXTRACTIONS}")
else
  aws_local dynamodb create-table \
    --table-name "${TABLE_EXTRACTIONS}" \
    --attribute-definitions AttributeName=document_id,AttributeType=S \
    --key-schema AttributeName=document_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    > /dev/null

  log_info "Waiting for '${TABLE_EXTRACTIONS}' to become ACTIVE ..."
  aws_local dynamodb wait table-exists --table-name "${TABLE_EXTRACTIONS}"

  log_info "Created DynamoDB table: ${TABLE_EXTRACTIONS}"
  CREATED+=("DynamoDB table: ${TABLE_EXTRACTIONS}")
fi

# Enable TTL on the 'ttl' attribute (Unix timestamp, 24h expiry).
# update-time-to-live is idempotent; LocalStack may return an error if TTL
# is already enabled with the same config — suppress that with || true.
log_info "Enabling TTL on '${TABLE_EXTRACTIONS}' (attribute: ttl, 24h) ..."
aws_local dynamodb update-time-to-live \
  --table-name "${TABLE_EXTRACTIONS}" \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  > /dev/null 2>&1 || true
log_info "TTL configured."
echo ""

# ---------------------------------------------------------------------------
# Step 4: DynamoDB — ContractAnalyses (TTL: 7 days)
# ---------------------------------------------------------------------------

log_info "--- DynamoDB table: ${TABLE_ANALYSES} ---"

if aws_local dynamodb describe-table --table-name "${TABLE_ANALYSES}" > /dev/null 2>&1; then
  log_warn "Table '${TABLE_ANALYSES}' already exists — skipping creation"
  EXISTED+=("DynamoDB table: ${TABLE_ANALYSES}")
else
  aws_local dynamodb create-table \
    --table-name "${TABLE_ANALYSES}" \
    --attribute-definitions AttributeName=document_id,AttributeType=S \
    --key-schema AttributeName=document_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    > /dev/null

  log_info "Waiting for '${TABLE_ANALYSES}' to become ACTIVE ..."
  aws_local dynamodb wait table-exists --table-name "${TABLE_ANALYSES}"

  log_info "Created DynamoDB table: ${TABLE_ANALYSES}"
  CREATED+=("DynamoDB table: ${TABLE_ANALYSES}")
fi

log_info "Enabling TTL on '${TABLE_ANALYSES}' (attribute: ttl, 7 days) ..."
aws_local dynamodb update-time-to-live \
  --table-name "${TABLE_ANALYSES}" \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  > /dev/null 2>&1 || true
log_info "TTL configured."
echo ""

# ---------------------------------------------------------------------------
# Step 5: Summary
# ---------------------------------------------------------------------------

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LocalStack bootstrap complete${NC}"
echo -e "${GREEN}========================================${NC}"

if [[ ${#CREATED[@]} -gt 0 ]]; then
  echo -e "\n${GREEN}Created:${NC}"
  for item in "${CREATED[@]}"; do
    echo "  ✓ $item"
  done
fi

if [[ ${#EXISTED[@]} -gt 0 ]]; then
  echo -e "\n${YELLOW}Already existed (no changes):${NC}"
  for item in "${EXISTED[@]}"; do
    echo "  - $item"
  done
fi

echo -e "\n${GREEN}Verify with:${NC}"
echo ""
echo "  # S3 buckets:"
echo "  aws --endpoint-url=${LOCALSTACK_ENDPOINT} s3 ls"
echo ""
echo "  # S3 lifecycle policy:"
echo "  aws --endpoint-url=${LOCALSTACK_ENDPOINT} s3api get-bucket-lifecycle-configuration --bucket ${S3_BUCKET_NAME}"
echo ""
echo "  # DynamoDB tables:"
echo "  aws --endpoint-url=${LOCALSTACK_ENDPOINT} --region=${AWS_DEFAULT_REGION} dynamodb list-tables"
echo ""
echo "  # TTL on ContractExtractions:"
echo "  aws --endpoint-url=${LOCALSTACK_ENDPOINT} --region=${AWS_DEFAULT_REGION} dynamodb describe-time-to-live --table-name ${TABLE_EXTRACTIONS}"
echo ""
echo "  # TTL on ContractAnalyses:"
echo "  aws --endpoint-url=${LOCALSTACK_ENDPOINT} --region=${AWS_DEFAULT_REGION} dynamodb describe-time-to-live --table-name ${TABLE_ANALYSES}"
echo ""
