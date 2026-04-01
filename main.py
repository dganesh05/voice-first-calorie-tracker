from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import json
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from supabase_client import supabase
from tavily import TavilyClient
from openai import OpenAI

app = FastAPI()

# ------------------ API KEYS ------------------

USDA_API_KEY = os.getenv("USDA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not USDA_API_KEY:
    raise RuntimeError("USDA_API_KEY not set")

# ------------------ CLIENTS ------------------

groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

tavily = TavilyClient(api_key=TAVILY_API_KEY)
templates = Jinja2Templates(directory="templates")

# ------------------ ROUTE ------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("front_end.html", {"request": request})


# ------------------ CLEAN INPUT ------------------

def clean_voice_input(query: str):
    query = query.lower()
    fillers = [
        "i ate", "i had", "i just ate",
        "for breakfast", "for lunch", "for dinner"
    ]
    for f in fillers:
        query = query.replace(f, "")
    return query.strip()


# ------------------ SAFE GROQ CALL ------------------

def safe_groq_call(prompt: str):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content":"""
You are a STRICT food parser.

Return ONLY valid JSON.

TWO possible formats:

1. If the input is a list of separate foods:
[
  {"food": "egg", "quantity": 2},
  {"food": "milk", "quantity": 1, "unit": "cup"}
]

2. If the input is a SINGLE COMPOSED DISH:
{
  "dish": "chicken alfredo pasta"
}

Rules:
- If foods are combined into one meal (e.g., "chicken alfredo pasta", "burger with fries"), treat as ONE dish
- If clearly separate items (e.g., "2 eggs and milk"), split them
- Convert words to numbers
- Return ONLY JSON
"""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Groq error:", e)
        return None


# ------------------ JSON EXTRACTION ------------------

def extract_json(text):
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print("JSON error:", e)
    return None


# ------------------ VALIDATE FOODS ------------------

def validate_foods(data):
    VALID_STOPWORDS = {"and", "of", "a", "the"}
    clean = []
    for item in data:
        food = item.get("food", "").strip()
        if not food or food in VALID_STOPWORDS:
            continue
        quantity = item.get("quantity", 1)
        try:
            quantity = float(quantity)
        except:
            quantity = 1
        clean.append({
            "food": food,
            "quantity": quantity
        })
    return clean


# ------------------ AI FOOD EXTRACTION ------------------

async def extract_foods_with_ai(query: str):
    prompt = f'Extract foods from: "{query}"'
    text = safe_groq_call(prompt)
    if text:
        data = extract_json(text)
        if data:
            return validate_foods(data)
    # HARD fallback (safe)
    return [{"food": query, "quantity": 1}]


# ------------------ SMART USDA FETCH ------------------

async def fetch_usda(food_name: str):
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={"api_key": USDA_API_KEY},
            json={"query": food_name}
        )

        if response.status_code != 200:
            return None

        foods = response.json().get("foods", [])
        if not foods:
            return None

        # Score foods to select the most realistic one
        def score_food(food):
            desc = food.get("description", "").lower()
            score = 0
            if "raw" in desc:
                score += 5
            if "large" in desc:
                score += 3
            bad_words = ["dried", "powder", "mix", "substitute", "liquid"]
            for word in bad_words:
                if word in desc:
                    score -= 10
            return score

        foods_sorted = sorted(foods, key=score_food, reverse=True)
        selected_food = foods_sorted[0]

        # Extract key nutrients
        nutrient_lookup = {
            "Energy": "calories",
            "Protein": "protein_g",
            "Carbohydrate, by difference": "carbs_g",
            "Total lipid (fat)": "fat_g",
            "Sugars, total including NLEA": "sugar_g",
            "Fiber, total dietary": "fiber_g",
            "Vitamin D (D2 + D3)": "vitamin_d_mcg",
        }
        nutrition_data = {v: 0 for v in nutrient_lookup.values()}

        for nutrient in selected_food.get("foodNutrients", []):
            name = nutrient.get("nutrientName")
            if name in nutrient_lookup:
                nutrition_data[nutrient_lookup[name]] = nutrient.get("value", 0)

        # ------------------ SERVING NORMALIZATION ------------------
        desc = selected_food.get("description", "").lower()
        if "egg" in food_name.lower():
            # USDA often returns per 100g; 1 egg ≈ 50g
            for k in nutrition_data:
                nutrition_data[k] *= 0.5
        elif "milk" in food_name.lower():
            # 1 cup ≈ 244g
            for k in nutrition_data:
                nutrition_data[k] *= 2.44

        return nutrition_data


# ------------------ MAIN ENDPOINT ------------------

@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str):
    query = clean_voice_input(query)
    foods = await extract_foods_with_ai(query)

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

    for food in foods:
        nutrition = await fetch_usda(food["food"])
        if not nutrition:
            nutrition = {
                "calories": 0,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0,
                "sugar_g": 0,
                "fiber_g": 0,
                "vitamin_d_mcg": 0
            }

        for k in nutrition:
            nutrition[k] *= food["quantity"]

        result = {
            "food": f"{food['quantity']} x {food['food']}",
            **nutrition
        }

        results.append(result)

        for key in totals:
            totals[key] += result.get(key, 0)

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