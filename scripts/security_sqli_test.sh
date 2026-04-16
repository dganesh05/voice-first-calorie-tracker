#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ACCESS_TOKEN="${ACCESS_TOKEN:-}"
SUPABASE_URL="${SUPABASE_URL:-${NEXT_PUBLIC_SUPABASE_URL:-}}"
SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "python or python3 is required for JSON parsing in this script."
    exit 1
  fi
fi

if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "ACCESS_TOKEN is required for SQL injection tests."
  exit 1
fi

pass() {
  echo "[PASS] $1"
}

fail() {
  echo "[FAIL] $1"
  exit 1
}

status_and_body() {
  local output_file="$1"
  shift
  curl -s -o "$output_file" -w '%{http_code}' "$@"
}

parse_json_field() {
  local body_file="$1"
  local field="$2"
  BODY_FILE="$body_file" FIELD="$field" "$PYTHON_BIN" - <<'PY'
import json, os
with open(os.environ["BODY_FILE"], "r", encoding="utf-8") as f:
    body = json.load(f)
value = body.get(os.environ["FIELD"], "") if isinstance(body, dict) else ""
print(value if value is not None else "")
PY
}

ensure_user_row() {
  if [[ -z "$SUPABASE_URL" || -z "$SUPABASE_ANON_KEY" ]]; then
    fail "SUPABASE_URL and SUPABASE_ANON_KEY (or NEXT_PUBLIC variants) are required to seed users row"
  fi

  local me_body
  me_body=$(mktemp)
  local me_status
  me_status=$(status_and_body "$me_body" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${API_BASE_URL}/api/me")

  if [[ "$me_status" != "200" ]]; then
    cat "$me_body"
    rm -f "$me_body"
    fail "Could not resolve authenticated user via /api/me (status=${me_status})"
  fi

  local user_id
  local user_email
  user_id=$(parse_json_field "$me_body" "id")
  user_email=$(parse_json_field "$me_body" "email")
  rm -f "$me_body"

  if [[ -z "$user_id" ]]; then
    fail "Could not parse user id from /api/me"
  fi

  local upsert_body
  upsert_body=$(mktemp)
  local upsert_status
  upsert_status=$(status_and_body "$upsert_body" \
    -X POST "${SUPABASE_URL}/rest/v1/users?on_conflict=id" \
    -H "apikey: ${SUPABASE_ANON_KEY}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -H "Prefer: resolution=merge-duplicates,return=representation" \
    -d "[{\"id\":\"${user_id}\",\"email\":\"${user_email}\",\"display_name\":\"SQLi Test User\"}]")

  if [[ "$upsert_status" != "200" && "$upsert_status" != "201" ]]; then
    cat "$upsert_body"
    rm -f "$upsert_body"
    fail "Could not seed users row required by daily_logs FK (status=${upsert_status})"
  fi

  rm -f "$upsert_body"
  pass "User row prerequisite is satisfied"
}

entry_exists() {
  local body_file="$1"
  local entry_id="$2"
  BODY_FILE="$body_file" ENTRY_ID="$entry_id" "$PYTHON_BIN" - <<'PY'
import json, os
with open(os.environ["BODY_FILE"], "r", encoding="utf-8") as f:
    body = json.load(f)
entries = body.get("entries", []) if isinstance(body, dict) else []
entry_id = os.environ["ENTRY_ID"]
print("yes" if any(str(item.get("id")) == entry_id for item in entries if isinstance(item, dict)) else "no")
PY
}

echo "Running SQL injection abuse tests against ${API_BASE_URL}"

ensure_user_row

CREATE_BODY=$(mktemp)
CREATE_STATUS=$(status_and_body "$CREATE_BODY" \
  -X POST "${API_BASE_URL}/api/journal/entries" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"food_name":"'"'"' OR 1=1 --","quantity":1,"calories":123,"protein_g":10,"carbs_g":11,"fat_g":12}')

if [[ "$CREATE_STATUS" != "200" ]]; then
  cat "$CREATE_BODY"
  rm -f "$CREATE_BODY"
  fail "Create journal entry with SQLi payload should succeed as literal text (status=${CREATE_STATUS})"
fi

ENTRY_ID=$(parse_json_field "$CREATE_BODY" "id")
CREATED_FOOD_NAME=$(parse_json_field "$CREATE_BODY" "food_name")
rm -f "$CREATE_BODY"

if [[ -z "$ENTRY_ID" ]]; then
  fail "Could not parse created journal entry id"
fi

if [[ "$CREATED_FOOD_NAME" != "' OR 1=1 --" ]]; then
  fail "SQLi payload was unexpectedly transformed during create"
fi
pass "Create endpoint treats SQLi payload as plain data"

LIST_BODY=$(mktemp)
LIST_STATUS=$(status_and_body "$LIST_BODY" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${API_BASE_URL}/api/journal/entries?limit=200")

if [[ "$LIST_STATUS" != "200" ]]; then
  cat "$LIST_BODY"
  rm -f "$LIST_BODY"
  fail "Listing entries failed unexpectedly (status=${LIST_STATUS})"
fi

EXISTS_RESULT=$(entry_exists "$LIST_BODY" "$ENTRY_ID")
rm -f "$LIST_BODY"
[[ "$EXISTS_RESULT" == "yes" ]] || fail "Created entry not found after SQLi payload insert"
pass "List endpoint remains stable after SQLi payload insert"

UPDATE_BODY=$(mktemp)
UPDATE_STATUS=$(status_and_body "$UPDATE_BODY" \
  -X PUT "${API_BASE_URL}/api/journal/entries/${ENTRY_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"food_name":"\"; DROP TABLE daily_logs; --"}')

if [[ "$UPDATE_STATUS" != "200" ]]; then
  cat "$UPDATE_BODY"
  rm -f "$UPDATE_BODY"
  fail "Update with SQLi payload should not break query handling (status=${UPDATE_STATUS})"
fi

UPDATED_FOOD_NAME=$(parse_json_field "$UPDATE_BODY" "food_name")
rm -f "$UPDATE_BODY"

if [[ "$UPDATED_FOOD_NAME" != '"; DROP TABLE daily_logs; --' ]]; then
  fail "Updated payload not persisted as literal text"
fi
pass "Update endpoint treats SQLi payload as plain data"

BAD_ID_BODY=$(mktemp)
BAD_ID_STATUS=$(status_and_body "$BAD_ID_BODY" \
  -X DELETE "${API_BASE_URL}/api/journal/entries/%27%20OR%201%3D1%20--" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

if [[ "$BAD_ID_STATUS" != "404" && "$BAD_ID_STATUS" != "422" ]]; then
  cat "$BAD_ID_BODY"
  rm -f "$BAD_ID_BODY"
  fail "Injected path id should not match unintended rows (expected 404 or 422, got ${BAD_ID_STATUS})"
fi
rm -f "$BAD_ID_BODY"
pass "Injected path id cannot trigger broad delete"

POST_BAD_ID_LIST_BODY=$(mktemp)
POST_BAD_ID_LIST_STATUS=$(status_and_body "$POST_BAD_ID_LIST_BODY" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${API_BASE_URL}/api/journal/entries?limit=200")

if [[ "$POST_BAD_ID_LIST_STATUS" != "200" ]]; then
  cat "$POST_BAD_ID_LIST_BODY"
  rm -f "$POST_BAD_ID_LIST_BODY"
  fail "List after bad-id delete probe failed (status=${POST_BAD_ID_LIST_STATUS})"
fi

EXISTS_AFTER_BAD_ID=$(entry_exists "$POST_BAD_ID_LIST_BODY" "$ENTRY_ID")
rm -f "$POST_BAD_ID_LIST_BODY"
[[ "$EXISTS_AFTER_BAD_ID" == "yes" ]] || fail "Entry disappeared after bad-id SQLi delete probe"
pass "No unintended deletion after injected path id"

DELETE_BODY=$(mktemp)
DELETE_STATUS=$(status_and_body "$DELETE_BODY" \
  -X DELETE "${API_BASE_URL}/api/journal/entries/${ENTRY_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

if [[ "$DELETE_STATUS" != "200" ]]; then
  cat "$DELETE_BODY"
  rm -f "$DELETE_BODY"
  fail "Cleanup delete failed (status=${DELETE_STATUS})"
fi

DELETED_VALUE=$(parse_json_field "$DELETE_BODY" "deleted")
rm -f "$DELETE_BODY"
[[ "$DELETED_VALUE" == "True" || "$DELETED_VALUE" == "true" ]] || fail "Cleanup delete did not report deleted=true"
pass "Cleanup succeeded"

echo "SQL injection abuse tests completed successfully."
