#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TEST_EMAIL="${TEST_EMAIL:-smoke.$(date +%s)@example.com}"
TEST_PASSWORD="${TEST_PASSWORD:-StrongPass123!}"
TEST_DISPLAY_NAME="${TEST_DISPLAY_NAME:-Smoke User}"
TEST_DAILY_GOAL="${TEST_DAILY_GOAL:-1900}"
TODAY="${TODAY:-$(date +%F)}"

PASS_COUNT=0
FAIL_COUNT=0

log() {
  echo "[$(date +%H:%M:%S)] $*"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "  PASS: $*"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "  FAIL: $*"
}

json_field() {
  local payload="$1"
  local field="$2"

  if command -v jq >/dev/null 2>&1; then
    echo "$payload" | jq -r ".${field} // empty"
    return
  fi

  python3 - "$field" <<'PY'
import json
import sys

field = sys.argv[1]
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)

value = data
for part in field.split('.'):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if value is None:
    print("")
elif isinstance(value, (dict, list)):
    print(json.dumps(value))
else:
    print(str(value))
PY
}

request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local token="${4:-}"

  local headers=(-H "Content-Type: application/json")
  if [[ -n "$token" ]]; then
    headers+=(-H "Authorization: Bearer $token")
  fi

  local tmp_body
  tmp_body="$(mktemp)"

  local http_code
  if [[ -n "$data" ]]; then
    http_code="$(curl -sS -o "$tmp_body" -w '%{http_code}' -X "$method" "${BASE_URL}${path}" "${headers[@]}" -d "$data")"
  else
    http_code="$(curl -sS -o "$tmp_body" -w '%{http_code}' -X "$method" "${BASE_URL}${path}" "${headers[@]}")"
  fi

  local body
  body="$(cat "$tmp_body")"
  rm -f "$tmp_body"

  printf '%s\n%s' "$http_code" "$body"
}

run_check() {
  local name="$1"
  shift
  log "Running: ${name}"
  if "$@"; then
    pass "$name"
  else
    fail "$name"
  fi
}

check_health() {
  local result
  result="$(request GET /health/supabase)"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"ok":true'* || "$body" == *'"ok": true'* ]]
}

check_register_or_existing_user() {
  local payload
  payload="{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"display_name\":\"${TEST_DISPLAY_NAME}\",\"daily_calorie_goal\":${TEST_DAILY_GOAL}}"

  local result
  result="$(request POST /register "$payload")"
  local code
  code="$(echo "$result" | head -n1)"

  if [[ "$code" == "200" ]]; then
    return 0
  fi

  # If register fails because user exists or confirmation setting, we still proceed to login.
  [[ "$code" == "400" || "$code" == "422" ]]
}

check_login_and_store_token() {
  local payload
  payload="{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}"

  local result
  result="$(request POST /login "$payload")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1

  TOKEN="$(json_field "$body" access_token | tr -d '\n')"
  [[ -n "$TOKEN" ]]
}

check_protected_requires_token() {
  local payload
  payload='{"raw_transcript":"1 apple"}'

  local result
  result="$(request POST /foods/process "$payload")"
  local code
  code="$(echo "$result" | head -n1)"

  [[ "$code" == "401" ]]
}

check_process() {
  local payload
  payload='{"raw_transcript":"I had two eggs and one banana"}'

  local result
  result="$(request POST /foods/process "$payload" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"status":"success"'* || "$body" == *'"status": "success"'* ]] || return 1
  [[ "$body" == *'"totals"'* ]] || return 1
  [[ "$body" == *'"unresolved_items"'* ]]
}

check_confirm() {
  local payload
  payload='{"items":[{"name":"egg","calories":140,"protein":12,"carbs":1,"fat":10},{"name":"banana","calories":105,"protein":1.3,"carbs":27,"fat":0.3}]}'

  local result
  result="$(request POST /foods/confirm "$payload" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"inserted":'* ]]
}

check_manual_personal() {
  local payload
  payload='{"food_name":"smoke custom personal","calories":250,"protein":20,"carbs":22,"fat":9,"destination":"personal"}'

  local result
  result="$(request POST /foods/manual "$payload" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"table":"personal_foods"'* || "$body" == *'"table": "personal_foods"'* ]]
}

check_manual_global() {
  local payload
  payload='{"food_name":"smoke custom global","calories":300,"protein":10,"carbs":45,"fat":9,"destination":"global"}'

  local result
  result="$(request POST /foods/manual "$payload" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"table":"global_foods"'* || "$body" == *'"table": "global_foods"'* ]]
}

check_journal() {
  local result
  result="$(request GET "/journal?journal_date=${TODAY}" "" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"logs"'* ]] || return 1
  [[ "$body" == *'"totals"'* ]]
}

check_profile_get() {
  local result
  result="$(request GET /profile "" "$TOKEN")"
  local code body
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"

  [[ "$code" == "200" ]] || return 1
  [[ "$body" == *'"profile"'* ]]
}

check_profile_update() {
  local payload
  payload='{"display_name":"Smoke Updated","daily_calorie_goal":2050}'

  local result
  result="$(request PUT /profile "$payload" "$TOKEN")"
  local code
  code="$(echo "$result" | head -n1)"

  [[ "$code" == "200" ]]
}

main() {
  log "Starting VoCalorie smoke tests against ${BASE_URL}"
  log "Test email: ${TEST_EMAIL}"

  run_check "Health check" check_health
  run_check "Register (or already exists)" check_register_or_existing_user
  run_check "Login and capture token" check_login_and_store_token
  run_check "Protected endpoint requires token" check_protected_requires_token
  run_check "Food processing" check_process
  run_check "Confirm meal commit" check_confirm
  run_check "Manual save to personal" check_manual_personal
  run_check "Manual save to global" check_manual_global
  run_check "Journal query" check_journal
  run_check "Profile read" check_profile_get
  run_check "Profile update" check_profile_update

  echo
  echo "Smoke test summary: PASS=${PASS_COUNT} FAIL=${FAIL_COUNT}"

  if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
  fi
}

TOKEN=""
main
