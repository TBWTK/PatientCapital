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
  --data '{"expected_version":null,"base_currency":"RUB","investment_horizon_years":5,"risk_level":"balanced","cash_buffer":"0.00","broker_name":"Docker Smoke Broker","fee_rate":"0.001","minimum_fee":"1.00"}' \
  | jq -e '.version == 1' >/dev/null

proposal="$(curl --fail --silent --show-error \
  --request POST \
  --header 'Content-Type: application/json' \
  --data '{"contribution":"8000.00"}' \
  --url "$api_base/v1/discovery/recommendations")"

printf '%s' "$proposal" \
  | jq -e '.mode == "automatic" and .horizon_years == 5 and .policy_version == "five-year-moex-v1" and (.candidates | length >= 1) and (.lines | length >= 1) and ((.spent | tonumber) <= 8000)' >/dev/null

asset_id="$(printf '%s' "$proposal" | jq -r '.candidates[0].asset_id')"

curl --fail --silent --show-error \
  --request POST "$api_base/v1/transactions" \
  --header 'Content-Type: application/json' \
  --data "{\"idempotency_key\":\"docker-smoke-confirmed-buy\",\"asset_id\":\"$asset_id\",\"side\":\"BUY\",\"quantity\":1,\"unit_price\":\"1.00\",\"fee\":\"0.00\",\"currency\":\"RUB\",\"occurred_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"note\":\"simulated separately confirmed smoke fact\"}" \
  | jq -e --arg asset_id "$asset_id" '.asset_id == $asset_id and .quantity == 1' >/dev/null

curl --fail --silent --show-error "$api_base/v1/portfolio" \
  | jq -e --arg asset_id "$asset_id" '(.assets | map(select(.asset_id == $asset_id and .quantity == 1)) | length == 1)' >/dev/null

echo "PASS: clean-volume Docker flow completed for $project_name"
