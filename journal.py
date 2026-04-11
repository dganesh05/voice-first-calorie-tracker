from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
from fastapi import HTTPException
from supabase_client import supabase


# -----------------------------
#  ADD TO JOURNAL
# -----------------------------
def add_to_journal(user_id: str, items: list[dict], logged_at: datetime = None):
    """
    Takes a list of resolved food items and writes them to daily_logs.
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


# -----------------------------
#  GET SINGLE DAY JOURNAL
# -----------------------------
def get_journal(user_id: str, journal_date: date = None):
    """
    Fetch all entries for a given day + totals + calorie goal
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
            .order("logged_at", desc=True)  
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch journal: {exc}")

    logs = response.data or []

    # Totals
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

    # Get calorie goal
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


# -----------------------------
#  GROUPED SUMMARY (DATE RANGE)
# -----------------------------
def get_journal_summary(
    user_id: str,
    start_date: date,
    end_date: date,
):
    """
    Returns grouped logs by date with totals.
    Sorted by date DESC.
    """

    start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)

    try:
        response = (
            supabase.table("daily_logs")
            .select("food_name, calories, protein, carbs, fat, logged_at")
            .eq("user_id", user_id)
            .gte("logged_at", start_dt.isoformat())
            .lte("logged_at", end_dt.isoformat())
            .order("logged_at", desc=True)  
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch summary: {exc}")

    logs = response.data or []

    #  Group by day
    grouped = defaultdict(lambda: {
        "entries": [],
        "totals": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
    })

    for entry in logs:
        try:
            log_dt = datetime.fromisoformat(entry["logged_at"])
        except Exception:
            continue

        day_key = log_dt.date().isoformat()

        grouped[day_key]["entries"].append(entry)

        grouped[day_key]["totals"]["calories"] += float(entry.get("calories") or 0)
        grouped[day_key]["totals"]["protein"] += float(entry.get("protein") or 0)
        grouped[day_key]["totals"]["carbs"] += float(entry.get("carbs") or 0)
        grouped[day_key]["totals"]["fat"] += float(entry.get("fat") or 0)

    #  Sort days DESC
    sorted_days = sorted(grouped.keys(), reverse=True)

    result = []
    for day in sorted_days:
        result.append({
            "date": day,
            "entries": grouped[day]["entries"],
            "totals": grouped[day]["totals"],
        })

    return {
        "status": "success",
        "days": result
    }


# -----------------------------
#  CHART DATA (FRONTEND READY)
# -----------------------------
def get_chart_data(
    user_id: str,
    start_date: date,
    end_date: date,
):
    """
    Returns flat chart-friendly data
    """

    summary = get_journal_summary(user_id, start_date, end_date)

    chart_data = []

    for day in summary["days"]:
        chart_data.append({
            "date": day["date"],
            "calories": day["totals"]["calories"],
            "protein": day["totals"]["protein"],
            "carbs": day["totals"]["carbs"],
            "fat": day["totals"]["fat"],
        })

    # chronological order for charts
    chart_data.reverse()

    return {
        "status": "success",
        "chart_data": chart_data
    }
