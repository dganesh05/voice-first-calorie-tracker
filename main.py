# hNxr2ADEnipXcoYNXcK5VWfxI4KPVfZWbefUct3q - key
# https://bnydqorligelcednwxgl.supabase.co - project url
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJueWRxb3JsaWdlbGNlZG53eGdsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTYwMjgzMCwiZXhwIjoyMDg3MTc4ODMwfQ.UmHUoldhlebYBhqZihXteIQnliXSr06fR7E_Xj9f1wI - SupaBase service role

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import httpx
import os

from supabase_client import supabase

app = FastAPI()
load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
SupaBase_Service_Role = os.getenv("SupaBase_Service_Role")

if not USDA_API_KEY:
    raise RuntimeError("USDA_API_KEY environment variable not set")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("front_end.html", {"request": request})

@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str):

    params = {"api_key": USDA_API_KEY}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params=params,
            json={
                "query": query,
                "dataType": ["Foundation", "Branded Foods", "SR Legacy", "Survey (FNDDS)"]
            }
        )

    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="USDA API error")

    foods = response.json().get("foods", [])

    if not foods:
        raise HTTPException(status_code=404, detail="Food not found")

    query_lower = query.lower()
    query_words = query_lower.split()

    filtered_foods = [
        food for food in foods
        if query_lower in food.get("description", "").lower()
    ]

    if not filtered_foods:
        def score_food(food):
            description = food.get("description", "").lower()
            return sum(word in description for word in query_words)

        foods = sorted(foods, key=score_food, reverse=True)
    else:
        foods = filtered_foods

    priority_order = ["Foundation", "SR Legacy", "Survey (FNDDS)"]
    selected_food = None

    for priority in priority_order:
        for food in foods:
            if food["dataType"] == priority:
                selected_food = food
                break
        if selected_food:
            break

    if not selected_food:
        selected_food = foods[0]

    nutrient_lookup = {
        "Energy": "calories",
        "Protein": "protein_g",
        "Carbohydrate, by difference": "carbs_g",
        "Total lipid (fat)": "fat_g",
        "Total Sugars": "sugar_g",
        "Fiber, total dietary": "fiber_g",
        "Vitamin D (D2 + D3)": "vitamin_d_mcg"
    }

    nutrition_data = {v: None for v in nutrient_lookup.values()}

    for nutrient in selected_food["foodNutrients"]:
        name = nutrient["nutrientName"]
        if name in nutrient_lookup:
            nutrition_data[nutrient_lookup[name]] = nutrient["value"]

    result = {
        "food": selected_food["description"],
        **nutrition_data
    }

    supabase.table("food_searches").insert({
        "food_name": result["food"],
        "calories": result["calories"],
        "protein": result["protein_g"],
        "carbs": result["carbs_g"],
        "fat": result["fat_g"]
    }).execute()

    return templates.TemplateResponse(
        "front_end.html",
        {
            "request": request,
            "result": result
        }
    )