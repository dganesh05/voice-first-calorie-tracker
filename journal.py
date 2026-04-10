from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
from fastapi import HTTPException
from supabase_client import supabase


def add_to_journal(user_id: str, items: list[dict], logged_at: datetime = None):
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
            .order("logged_at", desc=True)  # CHANGED: descending order
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch journal: {exc}")

    logs = response.data or []

    # ADDED: group entries by date, newest date first
    grouped = defaultdict(list)
    for row in logs:
        row_date = row["logged_at"][:10]  # grab just YYYY-MM-DD
        grouped[row_date].append(row)

    grouped_by_date = [
        {"date": d, "entries": entries}
        for d, entries in sorted(grouped.items(), reverse=True)
    ]

    # Compute totals for the requested day
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for row in logs:
        totals["calories"] += float(row.get("calories") or 0)
        totals["protein"] += float(row.get("protein") or 0)
        totals["carbs"] += float(row.get("carbs") or 0)
        totals["fat"] += float(row.get("fat") or 0)

    # ADDED: fetch all logs for chart aggregation (last 30 days)
    chart_start = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        chart_response = (
            supabase.table("daily_logs")
            .select("calories, protein, carbs, fat, logged_at")
            .eq("user_id", user_id)
            .gte("logged_at", chart_start.isoformat())
            .order("logged_at", desc=True)
            .execute()
        )
    except Exception:
        chart_response = None

    # ADDED: aggregate chart data by day
    chart_data = defaultdict(lambda: {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0})
    for row in (chart_response.data or []):
        row_date = row["logged_at"][:10]
        chart_data[row_date]["calories"] += float(row.get("calories") or 0)
        chart_data[row_date]["protein"] += float(row.get("protein") or 0)
        chart_data[row_date]["carbs"] += float(row.get("carbs") or 0)
        chart_data[row_date]["fat"] += float(row.get("fat") or 0)

    # Sort chart data newest first
    chart_aggregation = [
        {"date": d, **vals}
        for d, vals in sorted(chart_data.items(), reverse=True)
    ]

    # Fetch calorie goal
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
        pass

    calorie_delta = None
    if daily_calorie_goal is not None:
        calorie_delta = float(daily_calorie_goal) - totals["calories"]

    return {
        "status": "success",
        "date": day.isoformat(),
        "logs": logs,
        "grouped_by_date": grouped_by_date,   # ADDED: grouped + sorted descending
        "totals": totals,
        "chart_aggregation": chart_aggregation, # ADDED: per-day totals for charts
        "daily_calorie_goal": daily_calorie_goal,
        "calorie_delta": calorie_delta,
    }
