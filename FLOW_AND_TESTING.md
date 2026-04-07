# Voice-First Calorie Tracker Final: Flow, Decisions, and Testing

## Goal
This project combines both implementations with a strict boundary:
- AI is used for transcript parsing.
- Food resolution remains deterministic and cache-first.

## Input Flow
1. User enters transcript by:
- Typing into the transcript box, or
- Recording with browser speech recognition (Start/Stop Recording).

2. Frontend sends transcript to:
- `POST /foods/process`
- Payload: `{ "raw_transcript": "..." }`

3. Backend parse stage:
- First attempt: AI parser (`llm_parser.parse_raw_transcript`).
- If AI fails or returns malformed payload: deterministic fallback parser (`transcript_parser.parse_text_transcript`).

4. Backend resolve stage (for each parsed item):
- Tier 1: `personal_foods` by `user_id`
- Tier 2: `global_foods`
- Tier 3: USDA lookup + cache insert into `global_foods`

5. Backend response:
- Returns staged items, resolved items, totals, unresolved items.
- No journal write at resolve time.

6. Commit stage:
- User chooses log actions.
- `POST /foods/confirm` writes selected items to `daily_logs`.

## Parsing Choices Made
1. Canonical parser output schema:
- `quantity`
- `unit`
- `food_name`
- `descriptors`
- `brand`
- `fallback_search_query`

2. AI output normalization rules:
- Accept list payloads.
- Accept single object payloads.
- If object contains `dish`, normalize to one item using `food_name = dish`.

3. Deterministic fallback behavior:
- If AI parse is unavailable or invalid, fallback parser produces equivalent item shape.
- Resolver always receives structured items.

## Resolver Choices Made
1. Resolver is not responsible for transcript understanding.
2. Resolver ranking uses text overlap plus brand/descriptor relevance.
3. USDA heuristic remains a tie-break/fallback behavior, not primary intelligence.
4. Successful USDA results are cached to reduce repeat external calls.

## Key Files
- `main.py`: pipeline orchestration and API routes
- `llm_parser.py`: AI parsing and top-level payload normalization
- `transcript_parser.py`: deterministic parser fallback
- `food_resolver.py`: deterministic 3-tier food resolution
- `templates/front_end.html`: combined text + voice input staging UI
- `.env`: blank config file for local environment setup

## Testing Steps
## A. Environment and startup
1. Fill `.env` with required keys:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY` (recommended)
- `GROQ_API_KEY`
- `USDA_API_KEY`

2. Install dependencies:
- `pip install -r requirements.txt`

3. Run app:
- `uvicorn main:app --reload`

4. Voice recording prerequisites:
- Use a Chromium browser (Chrome/Edge) for best Web Speech API support.
- Open the app on `localhost` (or HTTPS origin).
- Allow microphone permission when prompted.
- Firefox uses audio capture plus server transcription because Web Speech API is not available there.

## B. Functional tests
1. Text parse and resolve:
- Input: `I just ate two eggs and one toast`
- Expected: multiple staged items with quantity handling.

2. Voice capture:
- Click Start Recording, speak meal, click Stop Recording.
- Expected: transcript textarea auto-populates.
- If blocked: check browser site settings and ensure microphone access is allowed.
- Firefox should show an audio-recording status and then populate the transcript after transcription completes.

3. AI dish object normalization:
- Input likely to be returned as dish form by model.
- Expected: backend still produces one structured item, not an error.

4. AI failure fallback:
- Temporarily unset `GROQ_API_KEY`.
- Input: `I had oatmeal and blueberries`
- Expected: deterministic parser fallback still returns staged items.

5. Unresolved item:
- Input: non-food phrase.
- Expected: unresolved staging card with create-manual path.

6. Personal override precedence:
- Create a personal food via UI.
- Re-run same input.
- Expected: personal tier chosen over global/USDA.

7. Commit integrity:
- Resolve multiple items and log only one.
- Expected: only selected item inserted to `daily_logs`.

## C. Data correctness checks
1. Verify no writes to `daily_logs` during `/foods/process`.
2. Verify writes occur only via `/foods/confirm`.
3. Verify USDA hits are inserted into `global_foods` cache.

## D. Regression checks
1. Auth pages still gate protected routes.
2. Journal endpoint still returns daily totals and delta.
3. Manual food creation still supports personal/global destinations.

## Acceptance Criteria
- Voice and text inputs both supported.
- AI parsing is primary transcript interpreter.
- Resolver remains deterministic and cache-first.
- Explicit confirm step controls journal writes.
- Fallback parsing keeps the app usable when AI parsing fails.
