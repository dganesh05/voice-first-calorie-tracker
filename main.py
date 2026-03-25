from dotenv import load_dotenv
load_dotenv(override=True)

import os
import re
import string
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from pydantic import BaseModel

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates

from supabase_client import supabase
from food_resolver import resolve_food_item
from llm_parser import parse_raw_transcript

app = FastAPI()

templates = Jinja2Templates(directory="templates")
security = HTTPBearer(auto_error=False)


def _has_usable_usda_key() -> bool:
    key = str(os.getenv("USDA_API_KEY") or "").strip()
    if not key:
        return False
    placeholders = {
        "your-usda-api-key",
        "your_usda_api_key",
        "replace-me",
        "changeme",
    }
    return key.lower() not in placeholders


class FoodProcessRequest(BaseModel):
    raw_transcript: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    daily_calorie_goal: float = 2000


class LoginRequest(BaseModel):
    email: str
    password: str


class FoodConfirmItem(BaseModel):
    name: str
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0


class FoodConfirmRequest(BaseModel):
    items: list[FoodConfirmItem]
    logged_at: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    daily_calorie_goal: float | None = None


class ManualFoodEntryRequest(BaseModel):
    food_name: str
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    destination: Literal["personal", "global"]


def _user_id_from_auth_response(response_obj) -> str | None:
    user = getattr(response_obj, "user", None)
    if user is None and isinstance(response_obj, dict):
        user = response_obj.get("user")
    if user is None:
        return None
    if isinstance(user, dict):
        return str(user.get("id") or "").strip() or None
    return str(getattr(user, "id", "") or "").strip() or None


def _session_token_from_auth_response(response_obj) -> str | None:
    session = getattr(response_obj, "session", None)
    if session is None and isinstance(response_obj, dict):
        session = response_obj.get("session")
    if session is None:
        return None
    if isinstance(session, dict):
        return str(session.get("access_token") or "").strip() or None
    return str(getattr(session, "access_token", "") or "").strip() or None


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        auth_response = supabase.auth.get_user(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    user_id = _user_id_from_auth_response(auth_response)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to resolve user from token",
        )
    return user_id


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "front_end.html")


@app.get("/log", response_class=HTMLResponse)
async def log_page(request: Request):
    return templates.TemplateResponse(request, "front_end.html")


@app.post("/register")
async def register(payload: RegisterRequest):
    try:
        auth_response = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Register failed: {exc}") from exc

    user_id = _user_id_from_auth_response(auth_response)
    if not user_id:
        raise HTTPException(status_code=400, detail="Supabase did not return a user id")

    # Keep profile metadata in app-level users table for journal math.
    try:
        supabase.table("users").upsert(
            {
                "id": user_id,
                "email": payload.email,
                "display_name": payload.display_name,
                "daily_calorie_goal": payload.daily_calorie_goal,
            }
        ).execute()
    except Exception:
        # Auth account can exist even if profile row write fails.
        pass

    return {
        "status": "success",
        "user_id": user_id,
        "access_token": _session_token_from_auth_response(auth_response),
    }


@app.post("/login")
async def login(payload: LoginRequest):
    try:
        auth_response = supabase.auth.sign_in_with_password(
            {
                "email": payload.email,
                "password": payload.password,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Login failed: {exc}") from exc

    user_id = _user_id_from_auth_response(auth_response)
    token = _session_token_from_auth_response(auth_response)
    if not user_id or not token:
        raise HTTPException(status_code=401, detail="Login did not return a valid session")

    return {
        "status": "success",
        "user_id": user_id,
        "access_token": token,
    }


@app.get("/health/supabase")
async def health_supabase():
    configured_url = str(os.getenv("SUPABASE_URL") or "").strip()
    try:
        response = supabase.table("food_searches").select("*").limit(1).execute()
        return {
            "ok": True,
            "message": "Supabase reachable.",
            "supabase_url": configured_url,
            "sample_rows": len(response.data or []),
            "usda_configured": _has_usable_usda_key(),
        }
    except Exception as exc:
        error_text = str(exc)
        # Supabase reachable, but expected table is not created yet.
        if "PGRST205" in error_text or "schema cache" in error_text:
            return {
                "ok": True,
                "message": "Supabase reachable, but table setup is incomplete.",
                "setup_needed": "Create table public.food_searches",
                "error": error_text,
                "supabase_url": configured_url,
                "usda_configured": _has_usable_usda_key(),
            }

        return {
            "ok": False,
            "message": "Supabase not reachable or request failed.",
            "error": error_text,
            "supabase_url": configured_url,
            "usda_configured": _has_usable_usda_key(),
        }


def convert_number_words(query: str):

    number_map = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10"
    }

    words = query.split()

    converted = [number_map.get(w, w) for w in words]

    return " ".join(converted)


def clean_voice_input(query: str):

    fillers = [
        "i ate",
        "i had",
        "i just ate",
        "for breakfast",
        "for lunch",
        "for dinner"
    ]

    query = query.lower()

    for f in fillers:
        query = query.replace(f, "")

    query = query.translate(str.maketrans('', '', string.punctuation))

    return query.strip()


# Improved splitting logic
def split_foods(query: str):

    # normalize separators
    query = query.replace(" with ", " and ")
    query = query.replace("&", " and ")
    query = query.replace(",", " and ")

    foods = [f.strip() for f in query.split(" and ")]

    # remove articles like "a banana"
    cleaned = []
    for food in foods:
        words = food.split()
        if words and words[0] in ["a", "an", "the"]:
            food = " ".join(words[1:])
        cleaned.append(food)

    return cleaned


def parse_food_quantity(food_phrase: str):

    match = re.match(r"(\d+)\s+(.*)", food_phrase)

    if match:
        quantity = int(match.group(1))
        food_name = match.group(2)
    else:
        quantity = 1
        food_name = food_phrase

    return quantity, food_name


@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str, user_id: str = "anonymous"):

    query = clean_voice_input(query)
    query = convert_number_words(query)

    foods_to_search = split_foods(query)

    results = []

    totals = {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
        "sugar_g": 0,
        "fiber_g": 0,
        "vitamin_d_mcg": 0
    }

    for food_phrase in foods_to_search:
        quantity, food_query = parse_food_quantity(food_phrase)
        resolved_food = await resolve_food_item(food_query, user_id)

        if not resolved_food:
            continue

        food_name = resolved_food.get("food_name") or resolved_food.get("description") or food_query

        calories = resolved_food.get("calories", 0) or 0
        protein = resolved_food.get("protein_g", resolved_food.get("protein", 0)) or 0
        carbs = resolved_food.get("carbs_g", resolved_food.get("carbs", 0)) or 0
        fat = resolved_food.get("fat_g", resolved_food.get("fat", 0)) or 0
        sugar = resolved_food.get("sugar_g", 0) or 0
        fiber = resolved_food.get("fiber_g", 0) or 0
        vitamin_d = resolved_food.get("vitamin_d_mcg", 0) or 0

        result = {
            "food": f"{quantity} x {food_name}",
            "calories": calories * quantity,
            "protein_g": protein * quantity,
            "carbs_g": carbs * quantity,
            "fat_g": fat * quantity,
            "sugar_g": sugar * quantity,
            "fiber_g": fiber * quantity,
            "vitamin_d_mcg": vitamin_d * quantity,
        }

        results.append(result)

        totals["calories"] += result["calories"]
        totals["protein_g"] += result["protein_g"]
        totals["carbs_g"] += result["carbs_g"]
        totals["fat_g"] += result["fat_g"]
        totals["sugar_g"] += result["sugar_g"]
        totals["fiber_g"] += result["fiber_g"]
        totals["vitamin_d_mcg"] += result["vitamin_d_mcg"]

        try:
            supabase.table("food_searches").insert({
                "food_name": result["food"],
                "calories": result["calories"],
                "protein": result["protein_g"],
                "carbs": result["carbs_g"],
                "fat": result["fat_g"]
            }).execute()
        except Exception as e:
            print("Supabase insert failed:", e)

    return templates.TemplateResponse(
        request,
        "front_end.html",
        {
            "results": results,
            "totals": totals
        }
    )


async def _process_food_pipeline(raw_transcript: str, user_id: str):
    # 1. Standardize free-form transcript into strict JSON array.
    parsed_items = await parse_raw_transcript(raw_transcript)

    results = []
    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    unresolved_items = []

    # 2. Resolve each item via the 3-tier cascade.
    for item in parsed_items:
        food_item = str(item.get("food_name", item.get("item", ""))).strip()
        if not food_item:
            continue

        descriptors = item.get("descriptors") or []
        brand = item.get("brand")
        fallback_search_query = item.get("fallback_search_query")

        food_data = await resolve_food_item(
            food_item,
            user_id,
            descriptors=descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        )

        if not food_data:
            unresolved_items.append(item)
            continue

        raw_qty = item.get("quantity", item.get("qty", 1))
        try:
            qty = float(raw_qty)
        except (TypeError, ValueError):
            qty = 1.0

        calories = (food_data.get("calories") or 0) * qty
        protein = (food_data.get("protein", food_data.get("protein_g", 0)) or 0) * qty
        carbs = (food_data.get("carbs", food_data.get("carbs_g", 0)) or 0) * qty
        fat = (food_data.get("fat", food_data.get("fat_g", 0)) or 0) * qty

        results.append({
            "name": food_data.get("food_name", food_item).strip(),
            "quantity": qty,
            "unit": item.get("unit", "serving"),
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "source": food_data.get("source", "internal"),
            "category": food_data.get("category", "unknown"),
        })

        totals["calories"] += calories
        totals["protein"] += protein
        totals["carbs"] += carbs
        totals["fat"] += fat

    return {
        "status": "success",
        "results": results,
        "totals": totals,
        "unresolved_items": unresolved_items,
    }


@app.get("/foods/process")
async def process_voice_log_get(
    raw_transcript: str,
    user_id: str = Depends(get_current_user_id),
):
    return await _process_food_pipeline(raw_transcript=raw_transcript, user_id=user_id)


@app.post("/foods/process")
async def process_voice_log_post(
    payload: FoodProcessRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await _process_food_pipeline(
        raw_transcript=payload.raw_transcript,
        user_id=user_id,
    )


@app.post("/foods/confirm")
async def confirm_food_log(
    payload: FoodConfirmRequest,
    user_id: str = Depends(get_current_user_id),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items provided for journal commit")

    logged_at = payload.logged_at or datetime.now(timezone.utc)
    rows = []
    for item in payload.items:
        rows.append(
            {
                "user_id": user_id,
                "food_name": item.name,
                "calories": item.calories,
                "protein": item.protein,
                "carbs": item.carbs,
                "fat": item.fat,
                "logged_at": logged_at.isoformat(),
            }
        )

    try:
        supabase.table("daily_logs").insert(rows).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save daily log: {exc}") from exc

    return {
        "status": "success",
        "inserted": len(rows),
        "logged_at": logged_at.isoformat(),
    }


@app.post("/foods/manual")
async def add_manual_food(
    payload: ManualFoodEntryRequest,
    user_id: str = Depends(get_current_user_id),
):
    target_table = "personal_foods" if payload.destination == "personal" else "global_foods"
    row = {
        "food_name": payload.food_name,
        "calories": payload.calories,
        "protein": payload.protein,
        "carbs": payload.carbs,
        "fat": payload.fat,
        "source": "crowdsourced" if payload.destination == "global" else "manual",
    }
    if payload.destination == "personal":
        row["user_id"] = user_id

    try:
        supabase.table(target_table).insert(row).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save manual food: {exc}") from exc

    return {"status": "success", "table": target_table}


@app.get("/journal")
async def get_journal(
    journal_date: date | None = None,
    user_id: str = Depends(get_current_user_id),
):
    day = journal_date or date.today()
    start_dt = datetime.combine(day, time.min).replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    try:
        response = (
            supabase.table("daily_logs")
            .select("food_name, calories, protein, carbs, fat, logged_at")
            .eq("user_id", user_id)
            .gte("logged_at", start_dt.isoformat())
            .lt("logged_at", end_dt.isoformat())
            .order("logged_at")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch journal: {exc}") from exc

    logs = response.data or []
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    for row in logs:
        totals["calories"] += float(row.get("calories") or 0)
        totals["protein"] += float(row.get("protein") or 0)
        totals["carbs"] += float(row.get("carbs") or 0)
        totals["fat"] += float(row.get("fat") or 0)

    daily_calorie_goal = None
    try:
        user_response = (
            supabase.table("users")
            .select("daily_calorie_goal")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if user_response.data:
            daily_calorie_goal = user_response.data[0].get("daily_calorie_goal")
    except Exception:
        daily_calorie_goal = None

    calorie_delta = None
    if daily_calorie_goal is not None:
        calorie_delta = float(daily_calorie_goal) - totals["calories"]

    return {
        "status": "success",
        "date": day.isoformat(),
        "logs": logs,
        "totals": totals,
        "daily_calorie_goal": daily_calorie_goal,
        "calorie_delta": calorie_delta,
    }


@app.get("/profile")
async def get_profile(user_id: str = Depends(get_current_user_id)):
    try:
        response = (
            supabase.table("users")
            .select("id, email, display_name, daily_calorie_goal")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {exc}") from exc

    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "success", "profile": response.data[0]}


@app.put("/profile")
async def update_profile(
    payload: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    updates = {}
    if payload.display_name is not None:
        updates["display_name"] = payload.display_name
    if payload.daily_calorie_goal is not None:
        updates["daily_calorie_goal"] = payload.daily_calorie_goal

    if not updates:
        raise HTTPException(status_code=400, detail="No profile fields provided")

    try:
        response = (
            supabase.table("users")
            .update(updates)
            .eq("id", user_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {exc}") from exc

    return {"status": "success", "updated": response.data or []}