from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException
from supabase_client import supabase


def add_to_journal(user_id: str, items: list[dict], logged_at: datetime = None):
    """
    Takes a list of resolved food items and writes them to daily_logs.
    Called after the user confirms their meal.
    """
    if not items:
        raise HTTPException(status_code=400, detail="No items provided")

    logged_at = logged_at or datetime.now(timezone.utc)

    rows = []
    for item in items:
        rows.append({
            "user_id": user_id,
            "food_name": item["name"],
            "calories": item["calories"],
            "protein": item["protein"],
            "carbs": item["carbs"],
            "fat": item["fat"],
            "logged_at": logged_at.isoformat(),
        })

    try:
        supabase.table("daily_logs").insert(rows).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save to journal: {exc}")

    return {
        "status": "success",
        "inserted": len(rows),
        "logged_at": logged_at.isoformat(),
    }


def get_journal(user_id: str, journal_date: date = None):
    """
    Fetches all food entries for a given day and computes daily macro totals.
    """
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch journal: {exc}")

    logs = response.data or []

    # Compute daily totals
    totals = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }

    for entry in logs:
        totals["calories"] += float(entry.get("calories") or 0)
        totals["protein"] += float(entry.get("protein") or 0)
        totals["carbs"] += float(entry.get("carbs") or 0)
        totals["fat"] += float(entry.get("fat") or 0)

    # Get user's calorie goal
    calorie_goal = None

    try:
        result = (
            supabase.table("users")
            .select("daily_calorie_goal")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if result.data:
            calorie_goal = result.data[0].get("daily_calorie_goal")
    except Exception:
        calorie_goal = None

    # Calculate remaining calories
    remaining_calories = None
    if calorie_goal is not None:
        remaining_calories = float(calorie_goal) - totals["calories"]

    return {
        "status": "success",
        "date": day.isoformat(),
        "entries": logs,
        "totals": totals,
        "calorie_goal": calorie_goal,
        "remaining_calories": remaining_calories,
    }
  
