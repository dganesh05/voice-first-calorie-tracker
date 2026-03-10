from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import re
import string

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from supabase_client import supabase

app = FastAPI()

USDA_API_KEY = os.getenv("USDA_API_KEY")

if not USDA_API_KEY:
    raise RuntimeError("USDA_API_KEY environment variable not set")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("front_end.html", {"request": request})


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
async def usda_api(request: Request, query: str):

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

    async with httpx.AsyncClient() as http_client:

        for food_phrase in foods_to_search:

            quantity, food_query = parse_food_quantity(food_phrase)

            params = {"api_key": USDA_API_KEY}

            response = await http_client.post(
                "https://api.nal.usda.gov/fdc/v1/foods/search",
                params=params,
                json={
                    "query": food_query,
                    "dataType": [
                        "Foundation",
                        "Branded Foods",
                        "SR Legacy",
                        "Survey (FNDDS)"
                    ]
                }
            )

            if response.status_code != 200:
                continue

            foods = response.json().get("foods", [])

            if not foods:
                continue

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
                "food": f"{quantity} x {selected_food['description']}",
                "calories": (nutrition_data["calories"] or 0) * quantity,
                "protein_g": (nutrition_data["protein_g"] or 0) * quantity,
                "carbs_g": (nutrition_data["carbs_g"] or 0) * quantity,
                "fat_g": (nutrition_data["fat_g"] or 0) * quantity,
                "sugar_g": (nutrition_data["sugar_g"] or 0) * quantity,
                "fiber_g": (nutrition_data["fiber_g"] or 0) * quantity,
                "vitamin_d_mcg": (nutrition_data["vitamin_d_mcg"] or 0) * quantity
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
        "front_end.html",
        {
            "request": request,
            "results": results,
            "totals": totals
        }
    )