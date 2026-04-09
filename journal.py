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
