#!/bin/sh
set -eu

project_name="patientcapital-smoke-$$"
api_port="${PATIENTCAPITAL_SMOKE_API_PORT:-58000}"
web_port="${PATIENTCAPITAL_SMOKE_WEB_PORT:-53000}"
postgres_port="${PATIENTCAPITAL_SMOKE_POSTGRES_PORT:-55433}"
api_base="http://127.0.0.1:${api_port}"
web_base="http://127.0.0.1:${web_port}"

cleanup() {
  docker compose --project-name "$project_name" down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

export API_PORT="$api_port"
export WEB_PORT="$web_port"
export POSTGRES_PORT="$postgres_port"

docker compose --project-name "$project_name" up --build --wait

curl --fail --silent --show-error "$api_base/health/ready" \
  | jq -e '.status == "ready"' >/dev/null
curl --fail --silent --show-error "$web_base" \
  | grep -q 'PatientCapital'

curl --fail --silent --show-error \
  --request PUT "$api_base/v1/profile" \
  --header 'Content-Type: application/json' \
  --data '{"expected_version":null,"base_currency":"RUB","investment_horizon_years":15,"risk_level":"balanced","cash_buffer":"1000.00","broker_name":"Docker Smoke Broker","fee_rate":"0.001","minimum_fee":"1.00"}' \
  | jq -e '.version == 1' >/dev/null

for asset_id in AAA BBB; do
  curl --fail --silent --show-error \
    --request PUT "$api_base/v1/assets/$asset_id" \
    --header 'Content-Type: application/json' \
    --data "{\"expected_version\":null,\"name\":\"Asset $asset_id\",\"currency\":\"RUB\",\"lot_size\":1,\"target_weight\":\"0.5\",\"is_active\":true}" \
    | jq -e '.version == 1' >/dev/null

  curl --fail --silent --show-error \
    --request POST "$api_base/v1/assets/$asset_id/prices" \
    --header 'Content-Type: application/json' \
    --data "{\"price\":\"100.00\",\"currency\":\"RUB\",\"as_of\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"max_age_seconds\":86400,\"source\":\"docker-smoke\"}" \
    | jq -e --arg asset_id "$asset_id" '.asset_id == $asset_id' >/dev/null
done

curl --fail --silent --show-error \
  --request POST "$api_base/v1/recommendations" \
  --header 'Content-Type: application/json' \
  --data '{"contribution":"10000.00"}' \
  | jq -e '.reason == "ALLOCATED" and (.lines | length == 2) and .spent == "8908.90"' >/dev/null

curl --fail --silent --show-error \
  --request POST "$api_base/v1/transactions" \
  --header 'Content-Type: application/json' \
  --data "{\"idempotency_key\":\"docker-smoke-buy-aaa\",\"asset_id\":\"AAA\",\"side\":\"BUY\",\"quantity\":10,\"unit_price\":\"100.00\",\"fee\":\"1.00\",\"currency\":\"RUB\",\"occurred_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"note\":\"isolated clean-volume smoke\"}" \
  | jq -e '.asset_id == "AAA" and .quantity == 10' >/dev/null

curl --fail --silent --show-error "$api_base/v1/portfolio" \
  | jq -e '.total_market_value == "1000.00" and (.assets | map(select(.asset_id == "AAA" and .quantity == 10)) | length == 1)' >/dev/null

echo "PASS: clean-volume Docker flow completed for $project_name"
