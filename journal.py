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

  
