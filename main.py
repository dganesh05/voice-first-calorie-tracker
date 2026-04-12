from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import json
import re
import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tavily import TavilyClient
from openai import OpenAI
from supabase_client import supabase_admin

app = FastAPI()
logger = logging.getLogger("vocalorie.api")
logging.basicConfig(level=logging.INFO)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

MAX_QUERY_LENGTH = 200
MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
}

RATE_LIMIT_BUCKETS = defaultdict(list)
RATE_LIMIT_LOCK = Lock()


def validate_environment() -> None:
    required = [
        "USDA_API_KEY",
        "GROQ_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url.startswith("https://"):
        raise RuntimeError("SUPABASE_URL must start with https://")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"

    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"

    return response

# ------------------ API KEYS ------------------

validate_environment()

USDA_API_KEY = os.getenv("USDA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ------------------ CLIENTS ------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

stt_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

tavily = TavilyClient(api_key=TAVILY_API_KEY)
templates = Jinja2Templates(directory="templates")


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    daily_calorie_goal: int | None = Field(default=None, ge=100, le=10000)
    protein_goal_g: int | None = Field(default=None, ge=0, le=1000)
    carb_goal_g: int | None = Field(default=None, ge=0, le=2000)
    fat_goal_g: int | None = Field(default=None, ge=0, le=1000)

    model_config = {"extra": "forbid"}


class JournalEntryCreateRequest(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(default=1, gt=0, le=100)
    calories: float | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)
    carbs_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=1000)

    model_config = {"extra": "forbid"}


class JournalEntryUpdateRequest(BaseModel):
    food_name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: float | None = Field(default=None, gt=0, le=100)
    calories: float | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)
    carbs_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=1000)

    model_config = {"extra": "forbid"}


class PersonalFoodCreateRequest(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    calories: float = Field(default=0, ge=0, le=5000)
    protein: float = Field(default=0, ge=0, le=1000)
    carbs: float = Field(default=0, ge=0, le=1000)
    fat: float = Field(default=0, ge=0, le=1000)

    model_config = {"extra": "forbid"}


def get_admin_supabase_or_503():
    if not supabase_admin:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database admin client is not configured.",
        )

    return supabase_admin


def _is_missing_table_error(exc: Exception) -> bool:
    lower_message = str(exc).lower()
    return (
        "pgrst205" in lower_message
        or "could not find the table" in lower_message
        or ("relation" in lower_message and "does not exist" in lower_message)
    )


def _translate_supabase_error(exc: Exception) -> HTTPException:
    message = str(exc)
    lower_message = message.lower()

    if "relation" in lower_message and "does not exist" in lower_message:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database schema is not initialized. Apply supabase/migrations/20260411_initial_security_schema.sql.",
        )

    if "invalid api key" in lower_message or "apikey" in lower_message:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase admin key is invalid for backend persistence. Set SUPABASE_SERVICE_ROLE_KEY to the real service role key.",
        )

    if "permission denied" in lower_message or "row-level security" in lower_message:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database denied access. Verify RLS policies and ensure backend uses the correct service role key.",
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Supabase persistence error: {message}",
    )


def apply_rate_limit(identifier: str, route_key: str, limit: int, window_seconds: int):
    now = time.time()
    bucket_key = f"{route_key}:{identifier}"

    with RATE_LIMIT_LOCK:
        timestamps = RATE_LIMIT_BUCKETS[bucket_key]
        RATE_LIMIT_BUCKETS[bucket_key] = [
            ts for ts in timestamps if now - ts < window_seconds
        ]
        timestamps = RATE_LIMIT_BUCKETS[bucket_key]

        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

        timestamps.append(now)


def validate_query(query: str) -> str:
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query is required.",
        )

    cleaned = query.strip()
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Query too long. Max {MAX_QUERY_LENGTH} characters.",
        )

    return cleaned


async def get_current_user(authorization: str = Header(default="")) -> dict:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_ANON_KEY,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session.",
            )

        data = response.json()
        user_id = data.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session payload.",
            )

        return data
    except HTTPException:
        raise
    except Exception:
        logger.warning("Auth verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

# ------------------ FOOD PARSER PROMPT ------------------

FOOD_PARSER_PROMPT = """
You are a HIGH-PRECISION food parser designed for nutrition tracking.

Your job is to convert natural language food descriptions into structured JSON.

You MUST return ONLY valid JSON.
NO explanations. NO extra text.

-----------------------------------
OUTPUT FORMATS (ONLY TWO ALLOWED)
-----------------------------------

1. MULTIPLE DISTINCT FOODS:
[
    {"food": "egg", "quantity": 2},
    {"food": "milk", "quantity": 1, "unit": "cup"},
    {"food": "maggi noodles", "quantity": 1, "brand": "Maggi", "intent": "branded_product"}
]

2. SINGLE DISH:
{
  "dish": "chicken alfredo pasta with mushrooms"
}

-----------------------------------
CORE PRINCIPLE
-----------------------------------

You must decide whether the input represents:

- ONE dish → return a single "dish"
- MULTIPLE foods → return a list

DO NOT default to a single dish blindly.
Use reasoning based on food structure.

-----------------------------------
MEAL vs DISH (CRITICAL)
-----------------------------------

A DISH = one prepared food item  
A MEAL = multiple distinct food items eaten together

You MUST return MULTIPLE foods when the input contains clearly separate items.

-----------------------------------
WHEN TO RETURN MULTIPLE FOODS
-----------------------------------

Return a LIST if ANY of the following are true:

1. DIFFERENT FOOD CATEGORIES:
   - Solid food + drink (e.g., pasta + coke)
   - Main + sandwich (e.g., pasta + grilled cheese)
   - Meal + beverage

2. MULTIPLE MAIN ITEMS:
   - pasta and sandwich
   - eggs and bacon and toast

3. ITEMS THAT COULD BE ORDERED SEPARATELY:
   - burger, fries, soda → separate

4. EXPLICIT QUANTITIES ON DIFFERENT ITEMS:
   - 2 eggs and 1 cup milk

5. TIME SEPARATION:
   - "later", "after", "then"

-----------------------------------
WHEN TO RETURN A SINGLE DISH
-----------------------------------

Return ONE "dish" ONLY if:

1. It is clearly ONE combined food:
   - "chicken alfredo pasta with mushrooms"
   - "burger with fries"
   - "salad with chicken"

2. "with" describes ingredients or sides that are part of the same plate

-----------------------------------
IMPORTANT DISTINCTION
-----------------------------------

"burger with fries" → SINGLE DISH  
"pasta with grilled cheese and coke" → MULTIPLE FOODS

Why?

- Fries are a typical side → same dish  
- Grilled cheese + coke → separate items

-----------------------------------
BRANDED / PACKAGED PRODUCT RULES
-----------------------------------

If the input names a brand or packaged product, preserve that intent.

Examples:
- "maggi" → branded_product
- "coke" → branded_product
- "oreo" → branded_product
- "lays" → branded_product
- "pepsi" → branded_product

Rules:
- Keep the exact brand/product wording in the food text whenever a packaged item is intended.
- If the item is clearly branded or packaged, you may add:
    - "brand": the brand name if it is obvious from the input
    - "intent": "branded_product"
- Treat short brand-like queries as packaged products by default.
- Prefer the packaged product users likely mean over generic ingredients, condiments, or loose pantry items.
- If the brand is mentioned with a specific product, keep both parts.
- Do not rewrite branded short-hands into generic ingredients unless the user clearly asks for the ingredient itself.

-----------------------------------
PARSING RULES
-----------------------------------

1. QUANTITIES
- Convert number words to numbers (one → 1, two → 2)
- "a/an" → 1
- Only apply quantities to individual foods
- NEVER assign quantity to "dish"

2. UNITS
- Include ONLY if explicitly stated
- Keep lowercase and singular (cup, slice, bowl)

3. FOOD NORMALIZATION
- Simplify:
  "scrambled eggs" → "egg"
  "a glass of milk" → "milk"

4. DISH PRESERVATION
- Keep full dish description intact
- Do NOT split ingredients inside a dish

5. BRAND PRESERVATION
- For short branded names and packaged products, preserve the product identity.
- Examples: "coke", "oreo", "lays", "maggi", "sprite", "nutella".
- Do not collapse these into a generic food unless the user clearly names the generic item.

6. IGNORE FILLER TEXT
Ignore:
"I had", "for lunch", "today", etc.

-----------------------------------
EDGE CASE RULES
-----------------------------------

1. "AND"
- Evaluate context carefully
- Do NOT assume single dish

2. DRINKS
- If paired with food → usually separate item
- Example: "pasta and coke" → split

3. "WITH"
- Sometimes same dish, sometimes not
- Decide based on food type:
   - ingredients → same dish
   - separate foods → split

-----------------------------------
FEW-SHOT EXAMPLES
-----------------------------------

Input: "2 eggs and 1 cup milk"
Output:
[
  {"food": "egg", "quantity": 2},
  {"food": "milk", "quantity": 1, "unit": "cup"}
]

---

Input: "chicken alfredo pasta with mushrooms"
Output:
{
  "dish": "chicken alfredo pasta with mushrooms"
}

---

Input: "burger with fries"
Output:
{
  "dish": "burger with fries"
}

---

Input: "pasta and salad"
Output:
[
  {"food": "pasta", "quantity": 1},
  {"food": "salad", "quantity": 1}
]

---

Input: "chicken alfredo pasta with grilled cheese and coke"
Output:
[
  {"food": "chicken alfredo pasta", "quantity": 1},
  {"food": "grilled cheese sandwich", "quantity": 1},
  {"food": "coke", "quantity": 1}
]

---

Input: "eggs toast and bacon"
Output:
[
  {"food": "egg", "quantity": 1},
  {"food": "toast", "quantity": 1},
  {"food": "bacon", "quantity": 1}
]

---

Input: "I had pasta and later drank milk"
Output:
[
  {"food": "pasta", "quantity": 1},
  {"food": "milk", "quantity": 1}
]

---

Input: "coke"
Output:
[
    {"food": "coke", "quantity": 1, "brand": "Coke", "intent": "branded_product"}
]

---

Input: "oreo"
Output:
[
    {"food": "oreo", "quantity": 1, "brand": "Oreo", "intent": "branded_product"}
]

---

Input: "lays chips"
Output:
[
    {"food": "lays chips", "quantity": 1, "brand": "Lays", "intent": "branded_product"}
]

-----------------------------------
FINAL INSTRUCTION
-----------------------------------

Return ONLY valid JSON.
NO explanations.
NO extra text.
"""

# ------------------ ROUTES ------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("front_end.html", {"request": request})

@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str):
    query = clean_voice_input(validate_query(query))
    foods = await extract_foods_with_ai(query)
    return await process_foods(request, foods)

@app.get("/api/foods/search")
async def usda_api_json(
    request: Request,
    query: str,
    user: dict = Depends(get_current_user),
):
    query = clean_voice_input(validate_query(query))
    apply_rate_limit(user["id"], "foods_search", limit=60, window_seconds=60)
    if request.client and request.client.host:
        apply_rate_limit(request.client.host, "foods_search_ip", limit=90, window_seconds=60)

    foods = await extract_foods_with_ai(query)
    results, totals = await compute_results_and_totals(foods, user_id=user["id"])
    return {
        "query": query,
        "results": results,
        "totals": totals,
    }


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "role": user.get("role"),
    }


@app.get("/api/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    try:
        response = (
            client.table("profiles")
            .select("user_id, full_name, daily_calorie_goal, protein_goal_g, carb_goal_g, fat_goal_g, updated_at")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []

        if rows:
            return rows[0]

        return {
            "user_id": user_id,
            "full_name": user.get("user_metadata", {}).get("full_name"),
            "daily_calorie_goal": 2300,
            "protein_goal_g": 180,
            "carb_goal_g": 220,
            "fat_goal_g": 70,
            "updated_at": None,
        }
    except Exception as exc:
        if _is_missing_table_error(exc):
            try:
                users_response = (
                    client.table("users")
                    .select("id, email, display_name, daily_calorie_goal, created_at, updated_at")
                    .eq("id", user_id)
                    .limit(1)
                    .execute()
                )
                users_rows = users_response.data or []
                if users_rows:
                    row = users_rows[0]
                    return {
                        "user_id": row.get("id"),
                        "full_name": row.get("display_name"),
                        "daily_calorie_goal": row.get("daily_calorie_goal") or 2300,
                        "protein_goal_g": 180,
                        "carb_goal_g": 220,
                        "fat_goal_g": 70,
                        "updated_at": row.get("updated_at"),
                    }

                return {
                    "user_id": user_id,
                    "full_name": user.get("user_metadata", {}).get("full_name"),
                    "daily_calorie_goal": 2300,
                    "protein_goal_g": 180,
                    "carb_goal_g": 220,
                    "fat_goal_g": 70,
                    "updated_at": None,
                }
            except Exception as users_exc:
                translated = _translate_supabase_error(users_exc)
                logger.exception("Failed to fetch profile from users fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to fetch profile")
        raise translated


@app.put("/api/profile")
async def update_profile(
    payload: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    profile_payload = {"user_id": user_id}
    updates = payload.model_dump(exclude_none=True)
    profile_payload.update(updates)

    try:
        response = (
            client.table("profiles")
            .upsert(profile_payload, on_conflict="user_id")
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else profile_payload
    except Exception as exc:
        if _is_missing_table_error(exc):
            users_payload = {"id": user_id}
            email = user.get("email")
            if email:
                users_payload["email"] = email

            if "full_name" in updates:
                users_payload["display_name"] = updates["full_name"]
            if "daily_calorie_goal" in updates:
                users_payload["daily_calorie_goal"] = updates["daily_calorie_goal"]

            try:
                users_response = (
                    client.table("users")
                    .upsert(users_payload, on_conflict="id")
                    .execute()
                )
                users_rows = users_response.data or []
                row = users_rows[0] if users_rows else users_payload
                return {
                    "user_id": row.get("id", user_id),
                    "full_name": row.get("display_name"),
                    "daily_calorie_goal": row.get("daily_calorie_goal") or 2300,
                    "protein_goal_g": 180,
                    "carb_goal_g": 220,
                    "fat_goal_g": 70,
                    "updated_at": row.get("updated_at"),
                }
            except Exception as users_exc:
                translated = _translate_supabase_error(users_exc)
                logger.exception("Failed to update profile in users fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to update profile")
        raise translated


@app.get("/api/journal/entries")
async def list_journal_entries(
    user: dict = Depends(get_current_user),
    limit: int = 50,
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]
    safe_limit = max(1, min(limit, 200))

    try:
        response = (
            client.table("journal_entries")
            .select("id, user_id, food_name, quantity, calories, protein_g, carbs_g, fat_g, logged_at, created_at")
            .eq("user_id", user_id)
            .order("logged_at", desc=True)
            .limit(safe_limit)
            .execute()
        )
        return {"entries": response.data or []}
    except Exception as exc:
        if _is_missing_table_error(exc):
            try:
                fallback_response = (
                    client.table("daily_logs")
                    .select("id, user_id, food_name, calories, protein, carbs, fat, logged_at, created_at")
                    .eq("user_id", user_id)
                    .order("logged_at", desc=True)
                    .limit(safe_limit)
                    .execute()
                )
                mapped_entries = []
                for row in fallback_response.data or []:
                    mapped_entries.append(
                        {
                            "id": row.get("id"),
                            "user_id": row.get("user_id"),
                            "food_name": row.get("food_name"),
                            "quantity": 1,
                            "calories": row.get("calories"),
                            "protein_g": row.get("protein"),
                            "carbs_g": row.get("carbs"),
                            "fat_g": row.get("fat"),
                            "logged_at": row.get("logged_at"),
                            "created_at": row.get("created_at"),
                        }
                    )
                return {"entries": mapped_entries}
            except Exception as fallback_exc:
                translated = _translate_supabase_error(fallback_exc)
                logger.exception("Failed to list journal entries from daily_logs fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to list journal entries")
        raise translated


@app.post("/api/journal/entries")
async def create_journal_entry(
    payload: JournalEntryCreateRequest,
    user: dict = Depends(get_current_user),
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    entry_payload = payload.model_dump()
    entry_payload["user_id"] = user_id

    try:
        response = client.table("journal_entries").insert(entry_payload).execute()
        rows = response.data or []
        return rows[0] if rows else entry_payload
    except Exception as exc:
        if _is_missing_table_error(exc):
            fallback_payload = {
                "user_id": user_id,
                "food_name": payload.food_name,
                "calories": payload.calories if payload.calories is not None else 0,
                "protein": payload.protein_g if payload.protein_g is not None else 0,
                "carbs": payload.carbs_g if payload.carbs_g is not None else 0,
                "fat": payload.fat_g if payload.fat_g is not None else 0,
            }

            try:
                fallback_response = client.table("daily_logs").insert(fallback_payload).execute()
                rows = fallback_response.data or []
                row = rows[0] if rows else fallback_payload
                return {
                    "id": row.get("id"),
                    "user_id": row.get("user_id", user_id),
                    "food_name": row.get("food_name", payload.food_name),
                    "quantity": payload.quantity,
                    "calories": row.get("calories"),
                    "protein_g": row.get("protein"),
                    "carbs_g": row.get("carbs"),
                    "fat_g": row.get("fat"),
                    "logged_at": row.get("logged_at"),
                    "created_at": row.get("created_at"),
                }
            except Exception as fallback_exc:
                translated = _translate_supabase_error(fallback_exc)
                logger.exception("Failed to create journal entry in daily_logs fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to create journal entry")
        raise translated


@app.post("/api/personal-foods")
async def create_personal_food(
    payload: PersonalFoodCreateRequest,
    user: dict = Depends(get_current_user),
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    personal_food_payload = {
        "user_id": user_id,
        "food_name": payload.food_name,
        "calories": payload.calories,
        "protein": payload.protein,
        "carbs": payload.carbs,
        "fat": payload.fat,
        "source": "manual",
    }

    try:
        response = client.table("personal_foods").insert(personal_food_payload).execute()
        rows = response.data or []
        return rows[0] if rows else personal_food_payload
    except Exception as exc:
        translated = _translate_supabase_error(exc)
        logger.exception("Failed to create personal food")
        raise translated


@app.put("/api/journal/entries/{entry_id}")
async def update_journal_entry(
    entry_id: str,
    payload: JournalEntryUpdateRequest,
    user: dict = Depends(get_current_user),
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field is required for update.",
        )

    try:
        response = (
            client.table("journal_entries")
            .update(updates)
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journal entry not found.",
            )
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_table_error(exc):
            fallback_updates = {}
            if "food_name" in updates:
                fallback_updates["food_name"] = updates["food_name"]
            if "calories" in updates:
                fallback_updates["calories"] = updates["calories"]
            if "protein_g" in updates:
                fallback_updates["protein"] = updates["protein_g"]
            if "carbs_g" in updates:
                fallback_updates["carbs"] = updates["carbs_g"]
            if "fat_g" in updates:
                fallback_updates["fat"] = updates["fat_g"]

            if not fallback_updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Only food name and macro updates are supported with daily_logs fallback schema.",
                )

            try:
                fallback_response = (
                    client.table("daily_logs")
                    .update(fallback_updates)
                    .eq("id", entry_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                rows = fallback_response.data or []
                if not rows:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Journal entry not found.",
                    )
                row = rows[0]
                return {
                    "id": row.get("id"),
                    "user_id": row.get("user_id", user_id),
                    "food_name": row.get("food_name"),
                    "quantity": 1,
                    "calories": row.get("calories"),
                    "protein_g": row.get("protein"),
                    "carbs_g": row.get("carbs"),
                    "fat_g": row.get("fat"),
                    "logged_at": row.get("logged_at"),
                    "created_at": row.get("created_at"),
                }
            except HTTPException:
                raise
            except Exception as fallback_exc:
                translated = _translate_supabase_error(fallback_exc)
                logger.exception("Failed to update journal entry in daily_logs fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to update journal entry")
        raise translated


@app.delete("/api/journal/entries/{entry_id}")
async def delete_journal_entry(
    entry_id: str,
    user: dict = Depends(get_current_user),
):
    client = get_admin_supabase_or_503()
    user_id = user["id"]

    try:
        response = (
            client.table("journal_entries")
            .delete()
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journal entry not found.",
            )
        return {"deleted": True, "id": entry_id}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_table_error(exc):
            try:
                fallback_response = (
                    client.table("daily_logs")
                    .delete()
                    .eq("id", entry_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                rows = fallback_response.data or []
                if not rows:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Journal entry not found.",
                    )
                return {"deleted": True, "id": entry_id}
            except HTTPException:
                raise
            except Exception as fallback_exc:
                translated = _translate_supabase_error(fallback_exc)
                logger.exception("Failed to delete journal entry in daily_logs fallback")
                raise translated

        translated = _translate_supabase_error(exc)
        logger.exception("Failed to delete journal entry")
        raise translated

@app.post("/voice")
async def voice_input(request: Request, file: UploadFile = File(...)):
    transcript = await transcribe_audio(file)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transcription failed.",
        )

    cleaned_query = clean_voice_input(normalize_transcript(transcript))
    foods = await extract_foods_with_ai(cleaned_query)

    return await process_foods(request, foods, transcript=transcript)

@app.post("/api/voice")
async def voice_input_json(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    apply_rate_limit(user["id"], "voice", limit=20, window_seconds=60)
    if request.client and request.client.host:
        apply_rate_limit(request.client.host, "voice_ip", limit=35, window_seconds=60)

    transcript = await transcribe_audio(file)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transcription failed.",
        )

    try:
        cleaned_query = clean_voice_input(normalize_transcript(transcript))
        foods = await extract_foods_with_ai(cleaned_query)
        results, totals = await compute_results_and_totals(foods, user_id=user["id"])
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voice processing pipeline failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Voice processing failed. Please try again.",
        )

    return {
        "transcript": transcript,
        "results": results,
        "totals": totals
    }

# ------------------ CLEAN INPUT ------------------

def clean_voice_input(query: str):
    query = query.lower()
    fillers = ["i ate", "i had", "i just ate", "for breakfast", "for lunch", "for dinner"]
    for f in fillers:
        query = query.replace(f, "")
    return query.strip()

def normalize_transcript(text: str):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()

# ------------------ WHISPER ------------------

async def transcribe_audio(file):
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio type.",
        )

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded file is empty.",
            )

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio file too large. Max {MAX_AUDIO_BYTES // (1024 * 1024)}MB.",
            )

        filename = file.filename or "audio.webm"
        content_type = file.content_type or "application/octet-stream"
        response = stt_client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3-turbo"
        )
        return response.text
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Whisper transcription failed: %s", type(e).__name__)
        return None

# ------------------ GROQ ------------------

def safe_groq_call(user_prompt: str, system_prompt: str):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("Groq call failed: %s", type(e).__name__)
        return None

# ------------------ JSON ------------------

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

# ------------------ VALIDATE ------------------

def validate_foods(data):
    clean = []
    for item in data:
        try:
            clean_item = {
                "food": item["food"],
                "quantity": float(item.get("quantity", 1)),
            }

            for optional_key in ("brand", "intent", "raw_food", "descriptor"):
                if optional_key in item and item[optional_key]:
                    clean_item[optional_key] = item[optional_key]

            clean.append(clean_item)
        except:
            continue
    return clean

# ------------------ PORTION ------------------

def estimate_portion(text: str):
    try:
        result = safe_groq_call(text, """
Return ONLY JSON: {"quantity": number} Rules: 1. NUMBER WORDS - one → 1, two → 2, three → 3, four → 4, five → 5 - a/an → 1 - half → 0.5, quarter → 0.25 - If a decimal is written (e.g., 1.5) → use it directly 2. UNITS - bowl, plate, cup, glass, slice → do NOT multiply; unit only helps clarify - Ignore words like 'serving', 'piece', 'portion' unless numeric 3. DEFAULT - If no number found → 1 - Fractions or mixed numbers should be handled correctly EXAMPLES: - "one bowl pasta" → 1 - "two bowls pasta" → 2 - "half cup rice" → 0.5 - "1.5 slices bread" → 1.5 - "a plate of chicken" → 1 Return JSON only, nothing else.
""")
        data = extract_json(result)
        return float(data.get("quantity", 1))
    except:
        return 1

# ------------------ AI EXTRACTION ------------------

async def extract_foods_with_ai(query: str):
    text = safe_groq_call(query, FOOD_PARSER_PROMPT)

    if text:
        data = extract_json(text)

        if isinstance(data, list):
            return validate_foods(data)

        elif isinstance(data, dict) and "dish" in data:
            return [{
                "food": data["dish"],
                "quantity": estimate_portion(query)
            }]

    return [{"food": query, "quantity": 1}]

# ------------------ USDA ------------------

async def fetch_usda(food_name: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={"api_key": USDA_API_KEY},
            json={"query": food_name, "pageSize": 10, "requireAllWords": False}
        )

        if response.status_code != 200:
            return None

        foods = response.json().get("foods", [])
        if not foods:
            return None

        selected = select_usda_candidate(food_name, foods)

        lookup = {
            "Energy": "calories",
            "Protein": "protein_g",
            "Carbohydrate, by difference": "carbs_g",
            "Total lipid (fat)": "fat_g",
            "Sugars, total including NLEA": "sugar_g",
            "Fiber, total dietary": "fiber_g",
            "Vitamin D (D2 + D3), International Units": "vitamin_d_mcg"
        }

        nutrition = {v: "Not Available" for v in lookup.values()}

        for n in selected.get("foodNutrients", []):
            if n.get("nutrientName") in lookup:
                nutrition[lookup[n["nutrientName"]]] = n.get("value", "Not Available")

        return nutrition


def normalize_food_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _personal_food_match_score(query: str, food_name: str) -> int:
    normalized_query = normalize_food_text(query)
    normalized_food_name = normalize_food_text(food_name)

    if not normalized_query or not normalized_food_name:
        return 0

    if normalized_query == normalized_food_name:
        return 1000

    query_boundary = f" {normalized_query} "
    food_boundary = f" {normalized_food_name} "

    if query_boundary.startswith(f" {normalized_food_name} "):
        return 900 + len(normalized_food_name)

    if food_boundary in query_boundary:
        return 800 + len(normalized_food_name)

    query_tokens = set(normalized_query.split())
    food_tokens = set(normalized_food_name.split())
    if food_tokens and food_tokens.issubset(query_tokens):
        return 700 + len(normalized_food_name)

    return 0


def _build_personal_food_nutrition(row: dict) -> dict:
    return {
        "calories": row.get("calories", 0) or 0,
        "protein_g": row.get("protein", 0) or 0,
        "carbs_g": row.get("carbs", 0) or 0,
        "fat_g": row.get("fat", 0) or 0,
        "sugar_g": 0,
        "fiber_g": 0,
        "vitamin_d_mcg": 0,
    }


async def fetch_personal_food(user_id: str, food_name: str) -> dict | None:
    client = get_admin_supabase_or_503()

    try:
        response = (
            client.table("personal_foods")
            .select("food_name, calories, protein, carbs, fat")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        translated = _translate_supabase_error(exc)
        logger.exception("Failed to search personal foods")
        raise translated

    best_match = None
    best_score = 0
    for row in response.data or []:
        score = _personal_food_match_score(food_name, row.get("food_name", ""))
        if score > best_score:
            best_score = score
            best_match = row

    if not best_match:
        return None

    return {
        "food": best_match.get("food_name", food_name),
        "nutrition": _build_personal_food_nutrition(best_match),
        "source": "personal",
    }


def candidate_text(candidate: dict) -> str:
    parts = [
        candidate.get("description"),
        candidate.get("brandOwner"),
        candidate.get("brandName"),
        candidate.get("ingredients"),
        candidate.get("foodCategory"),
        candidate.get("dataType"),
    ]
    return normalize_food_text(" ".join(str(part) for part in parts if part))


def count_numeric_nutrients(candidate: dict) -> int:
    count = 0
    for nutrient in candidate.get("foodNutrients", []):
        value = nutrient.get("value")
        if isinstance(value, (int, float)):
            count += 1
    return count


def is_brand_like_query(query: str) -> bool:
    normalized = normalize_food_text(query)
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return False

    brand_terms = {
        "maggi",
        "oreo",
        "coke",
        "pepsi",
        "lays",
        "kitkat",
        "kelloggs",
        "kellogg",
        "nestle",
        "nutella",
        "doritos",
        "pringles",
        "fanta",
        "sprite",
        "snickers",
        "twix",
        "maggi",
    }

    return len(tokens) <= 3 or any(token in brand_terms for token in tokens)


def score_usda_candidate(query: str, candidate: dict) -> float:
    normalized_query = normalize_food_text(query)
    query_tokens = [token for token in normalized_query.split() if token]
    candidate_tokens = set(candidate_text(candidate).split())
    candidate_description = normalize_food_text(candidate.get("description", ""))

    score = 0.0

    if normalized_query and normalized_query == candidate_description:
        score += 120

    if normalized_query and normalized_query in candidate_text(candidate):
        score += 70

    for token in query_tokens:
        if token in candidate_tokens:
            score += 12

    if candidate.get("dataType") == "Branded":
        score += 18

    if candidate.get("brandOwner"):
        brand_owner = normalize_food_text(str(candidate.get("brandOwner", "")))
        if any(token and token in brand_owner for token in query_tokens):
            score += 25

    if candidate.get("brandName"):
        brand_name = normalize_food_text(str(candidate.get("brandName", "")))
        if any(token and token in brand_name for token in query_tokens):
            score += 20

    if is_brand_like_query(query):
        if candidate.get("dataType") == "Branded":
            score += 12
        else:
            score -= 12

    score += min(count_numeric_nutrients(candidate), 10)

    generic_terms = {"seasoning", "sauce", "powder", "extract", "base"}
    if is_brand_like_query(query) and any(term in candidate_tokens for term in generic_terms):
        score -= 10

    return score


def select_usda_candidate(query: str, foods: list[dict]) -> dict:
    scored = sorted(
        ((score_usda_candidate(query, food), food) for food in foods),
        key=lambda item: item[0],
        reverse=True,
    )

    if not scored:
        return {}

    if len(scored) == 1:
        return scored[0][1]

    best_score, best_candidate = scored[0]
    second_score, _ = scored[1]

    if is_brand_like_query(query) and best_score - second_score <= 8:
        ai_choice = select_usda_candidate_with_ai(query, [candidate for _, candidate in scored[:5]])
        if ai_choice is not None and 0 <= ai_choice < min(len(scored), 5):
            return scored[ai_choice][1]

    return best_candidate


def select_usda_candidate_with_ai(query: str, foods: list[dict]) -> int | None:
    payload = []
    for index, food in enumerate(foods):
        payload.append({
            "index": index,
            "description": food.get("description"),
            "brandOwner": food.get("brandOwner"),
            "brandName": food.get("brandName"),
            "dataType": food.get("dataType"),
            "foodCategory": food.get("foodCategory"),
            "nutritionCount": count_numeric_nutrients(food),
        })

    prompt = (
        "Choose the single best USDA food candidate for the user's intended food. "
        "The input may be a brand-only or packaged-product query. Prefer the packaged product the user most likely means, "
        "not a loose ingredient, seasoning, condiment, or pantry base, unless the query clearly asks for that. "
        "Short-hand branded foods like coke, oreo, lays, maggi, pepsi, and similar packaged items should resolve to the branded product intent. "
        "Return only JSON in the form {\"selected_index\": number}.\n\n"
        f"User query: {query}\n"
        f"Candidates: {json.dumps(payload, ensure_ascii=False)}"
    )

    text = safe_groq_call(prompt, "You are a strict food resolver that returns only JSON.")
    data = extract_json(text) if text else None
    if isinstance(data, dict) and isinstance(data.get("selected_index"), int):
        return data["selected_index"]

    return None

# ------------------ PROCESS ------------------

async def process_foods_json(foods, user_id: str | None = None):
    results = []
    totals = {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0
    }

    for food in foods:
        search_query = food.get("food", "")
        brand = food.get("brand")
        if brand and brand.lower() not in normalize_food_text(search_query):
            search_query = f"{brand} {search_query}".strip()

        personal_food = None
        if user_id:
            personal_food = await fetch_personal_food(user_id, search_query)

        if personal_food:
            nutrition = personal_food["nutrition"]
            source = personal_food["source"]
            selected_food_name = personal_food["food"]
        else:
            nutrition = await fetch_usda(search_query) or {}
            source = "USDA"
            selected_food_name = food["food"]

        for k in totals:
            val = nutrition.get(k)
            if isinstance(val, (int, float)):
                totals[k] += val * food["quantity"]

        results.append({
            "food": selected_food_name,
            "quantity": food["quantity"],
            "nutrition": nutrition,
            "source": source,
        })

    return results, totals


async def compute_results_and_totals(foods, user_id: str | None = None):
    raw_results, totals = await process_foods_json(foods, user_id=user_id)
    normalized_results = []

    for item in raw_results:
        food_name = item.get("food", "Unknown food")
        quantity = float(item.get("quantity", 1) or 1)
        nutrition = item.get("nutrition", {}) or {}
        source = item.get("source", "USDA")

        label = f"{quantity:g} x {food_name}" if quantity != 1 else food_name

        normalized_results.append(
            {
                "food": label,
                "quantity": quantity,
                "source": source,
                "source_item": food_name,
                "calories": nutrition.get("calories", 0),
                "protein_g": nutrition.get("protein_g", 0),
                "carbs_g": nutrition.get("carbs_g", 0),
                "fat_g": nutrition.get("fat_g", 0),
                "sugar_g": nutrition.get("sugar_g", 0),
                "fiber_g": nutrition.get("fiber_g", 0),
                "vitamin_d_mcg": nutrition.get("vitamin_d_mcg", 0),
            }
        )

    return normalized_results, totals


async def process_foods(request: Request, foods, transcript: str | None = None):
    results, totals = await compute_results_and_totals(foods)
    payload = {
        "results": results,
        "totals": totals,
    }
    if transcript is not None:
        payload["transcript"] = transcript

    return payload