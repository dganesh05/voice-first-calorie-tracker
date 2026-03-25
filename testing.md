# VoCalorie Testing Guide

This document is the living test runbook for the project.

- Use this file to validate current behavior.
- Append new sections for future features as they are implemented.
- Keep steps reproducible so anyone can run them end-to-end.

## 1. Scope

Current implementation coverage:

- Supabase schema and indexes
- FastAPI startup and health checks
- Authentication endpoints
- Food processing pipeline (LLM parse + resolver)
- Manual fallback save flow
- Journal commit and daily aggregation
- Profile read/update

Not fully covered yet:

- Dedicated multi-page frontend flows for login/register/profile/journal/log
- Full voice UI and correction UX automation
- Password reset UI/API flow
- Full unit/integration test suite

## 2. Prerequisites

Required environment variables in .env:

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- GROQ_API_KEY
- USDA_API_KEY (optional for now)

Behavior note:

- If USDA_API_KEY is missing, resolver skips USDA fallback and only uses personal/global DB data.

## 3. Database Setup (Supabase)

Run these scripts in Supabase SQL Editor in this exact order:

1. supabase/00_extensions.sql
2. supabase/01_core_tables.sql
3. supabase/02_indexes_and_triggers.sql
4. supabase/03_optional_rls_policies.sql (optional)

Verification SQL:

select to_regclass('public.users');
select to_regclass('public.personal_foods');
select to_regclass('public.global_foods');
select to_regclass('public.daily_logs');
select to_regclass('public.food_searches');

## 4. Start Backend

From project root:

source .venv/bin/activate
uvicorn main:app --reload

App URLs:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/log

## 4.1 Automated Smoke Test Script

Script path:

- scripts/smoke_test.sh

Make executable once:

chmod +x scripts/smoke_test.sh

Run with defaults:

./scripts/smoke_test.sh

Run with custom values:

BASE_URL="http://127.0.0.1:8000" \
TEST_EMAIL="your_test_email@example.com" \
TEST_PASSWORD="StrongPass123!" \
TODAY="$(date +%F)" \
./scripts/smoke_test.sh

Exit behavior:

- exit code 0: all checks passed
- exit code 1: one or more checks failed

## 5. API Test Runbook (Current)

Use a second terminal while backend runs.

### 5.1 Health Check

curl -s http://127.0.0.1:8000/health/supabase

Expected:

- ok true when Supabase is reachable
- usda_configured true only if USDA key is set and not placeholder

### 5.2 Register

curl -s -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"you@example.com",
    "password":"StrongPass123!",
    "display_name":"Divya",
    "daily_calorie_goal":1900
  }'

Expected:

- status success
- user_id present
- access_token may be present depending on auth confirmation settings

### 5.3 Login

curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email":"you@example.com",
    "password":"StrongPass123!"
  }'

Expected:

- status success
- user_id present
- access_token present

Store token:

TOKEN="paste_access_token_here"

### 5.4 Process Food Transcript (Protected)

curl -s -X POST http://127.0.0.1:8000/foods/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_transcript":"I had two eggs and a glass of whole milk"
  }'

Expected:

- status success
- results array with resolved foods
- totals object
- unresolved_items array (possibly empty)

### 5.5 Confirm Meal Commit to Daily Logs (Protected)

curl -s -X POST http://127.0.0.1:8000/foods/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items":[
      {"name":"egg","calories":140,"protein":12,"carbs":1,"fat":10},
      {"name":"whole milk","calories":150,"protein":8,"carbs":12,"fat":8}
    ]
  }'

Expected:

- status success
- inserted count greater than 0

### 5.6 Manual Fallback Save (Protected)

Save to personal_foods:

curl -s -X POST http://127.0.0.1:8000/foods/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "food_name":"my custom smoothie",
    "calories":320,
    "protein":25,
    "carbs":30,
    "fat":12,
    "destination":"personal"
  }'

Save to global_foods:

curl -s -X POST http://127.0.0.1:8000/foods/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "food_name":"community granola bowl",
    "calories":410,
    "protein":14,
    "carbs":56,
    "fat":16,
    "destination":"global"
  }'

Expected:

- status success
- table is personal_foods or global_foods

### 5.7 Journal Query + Aggregation (Protected)

curl -s "http://127.0.0.1:8000/journal?journal_date=2026-03-25" \
  -H "Authorization: Bearer $TOKEN"

Expected:

- status success
- logs array for the selected date
- totals object with calories/protein/carbs/fat
- daily_calorie_goal from users table
- calorie_delta value

### 5.8 Profile Read/Update (Protected)

Read:

curl -s http://127.0.0.1:8000/profile \
  -H "Authorization: Bearer $TOKEN"

Update:

curl -s -X PUT http://127.0.0.1:8000/profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name":"Divya G",
    "daily_calorie_goal":2050
  }'

Expected:

- read returns current profile
- update returns status success
- follow-up read reflects changes

## 6. Negative Tests (Must Pass)

Missing token:

curl -s -X POST http://127.0.0.1:8000/foods/process \
  -H "Content-Type: application/json" \
  -d '{"raw_transcript":"1 apple"}'

Expected: HTTP 401

Empty confirm payload:

curl -s -X POST http://127.0.0.1:8000/foods/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items":[]}'

Expected: HTTP 400

## 7. DB Verification Queries (Optional but Useful)

Run in Supabase SQL editor after tests:

select id, email, display_name, daily_calorie_goal, created_at
from public.users
order by created_at desc
limit 5;

select id, user_id, food_name, calories, protein, carbs, fat, logged_at
from public.daily_logs
order by logged_at desc
limit 20;

select id, food_name, calories, protein, carbs, fat, source, created_at
from public.personal_foods
order by created_at desc
limit 20;

select id, food_name, calories, protein, carbs, fat, source, created_at
from public.global_foods
order by created_at desc
limit 20;

## 8. Troubleshooting

- Register works but login fails:
  - Check Supabase auth provider settings and email confirmation requirements.
- 401 on protected endpoints:
  - Verify token is from login response and sent as Bearer token.
- Process endpoint returns empty results:
  - Check GROQ_API_KEY and prompt output; also verify existing foods in personal/global tables.
- USDA lookups never happen:
  - This is expected if USDA_API_KEY is missing or placeholder.
- Health says setup incomplete:
  - Ensure food_searches table exists by running supabase/01_core_tables.sql.

## 9. How To Extend This File For Future Implementations

For every new feature, add a section using this format:

### Feature: <name>

- Implementation files:
  - <path1>
  - <path2>
- Preconditions:
  - <required env vars, seed data, auth state>
- Happy path tests:
  1. <step>
  2. <step>
- Error path tests:
  1. <step>
  2. <step>
- Expected outputs:
  - <status codes>
  - <key response fields>
- Regression checks:
  - <existing endpoints that must still pass>

Keep older sections; only append and update when behavior intentionally changes.
