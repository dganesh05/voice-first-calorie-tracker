from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import json
import re

from fastapi import FastAPI, Request, UploadFile, File
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

stt_client = OpenAI(
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

def normalize_transcript(text: str):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

# ------------------ WHISPER STT ------------------

async def transcribe_audio(file):
    try:
        audio_bytes = await file.read()
        response = stt_client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3-turbo"
        )
        return response.text
    except Exception as e:
        print("Whisper error:", e)
        return None

# ------------------ SAFE GROQ CALL ------------------

def safe_groq_call(prompt: str):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
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
        return json.loads(text)
    except Exception as e:
        print("JSON parse error:", e)
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

# ------------------ DISH DECOMPOSITION ------------------

def decompose_dish_to_ingredients(dish_name: str):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """<Your full strict food parser system prompt here>"""
                },
                {"role": "user", "content": dish_name}
            ],
            temperature=0
        )
        text = response.choices[0].message.content
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception as e:
        print("Decomposition error:", e)
    return [dish_name]

# ------------------ PORTION ESTIMATION ------------------

def estimate_portion(food_text: str):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are an EXTREMELY STRICT, HIGH-PRECISION food parser.

Your job is to convert natural language food descriptions into structured JSON with near-perfect consistency.

You MUST return ONLY valid JSON. No explanations. No extra text.

-----------------------------------
OUTPUT FORMATS (ONLY TWO ALLOWED)
-----------------------------------

1. MULTIPLE SEPARATE FOODS:
[
  {"food": "egg", "quantity": 2},
  {"food": "milk", "quantity": 1, "unit": "cup"}
]

2. SINGLE COMPOSED DISH:
{
  "dish": "chicken alfredo pasta with mushrooms and onions"
}

-----------------------------------
CORE PRINCIPLE (VERY IMPORTANT)
-----------------------------------

WHEN IN DOUBT → RETURN A SINGLE DISH.

It is ALWAYS better to group foods into ONE dish unless there is STRONG, EXPLICIT evidence they are separate.

-----------------------------------
AGGRESSIVE DECISION LOGIC
-----------------------------------

A. SINGLE DISH (DEFAULT BEHAVIOR)

Return ONE "dish" object if the input describes a meal, plate, or foods likely eaten together.

This includes:

- "X with Y" → ALWAYS SINGLE DISH
- "X and Y" → ASSUME SINGLE DISH unless clearly separate
- Combo meals, plates, bowls, or typical pairings
- Foods served together (main + sides)

-----------------------------------

B. MULTIPLE FOODS (ONLY WITH STRONG EVIDENCE)

Return a LIST ONLY if there is CLEAR separation in time, intent, or phrasing.

STRONG separation signals:

- Time separation:
  "later", "after", "then", "for dessert"
- Explicit separation:
  "separately", "on its own", "by itself"
- Different actions:
  "ate X and drank Y later"

-----------------------------------
CRITICAL EDGE CASE RULES
-----------------------------------

1. "AND" RULE
- Default: SAME DISH
- Only split if strong separation signals exist

2. BREAKFAST / COMBO PLATES
- Multiple foods listed together → SINGLE DISH

3. DRINKS
- Included in dish if part of meal
- Separate ONLY if clearly consumed independently

4. "WITH" RULE
- ALWAYS SINGLE DISH

5. "ON THE SIDE"
- STILL SINGLE DISH unless explicitly consumed separately

-----------------------------------
PARSING RULES
-----------------------------------

1. QUANTITIES
- Convert number words to integers
- "a/an" → 1
- Only apply to separate food items
- NEVER assign quantity to "dish"

2. UNITS
- Extract only if explicitly stated
- Keep lowercase and singular
- Do NOT guess

3. FOOD NORMALIZATION
- Simplify names:
  "scrambled eggs" → "egg"
  "a glass of milk" → "milk"

4. DISH PRESERVATION
- Preserve full description
- Do NOT split ingredients

5. IGNORE FILLER TEXT
- Ignore phrases like:
  "I had", "for lunch", "today", etc.

-----------------------------------
FEW-SHOT EXAMPLES (CRITICAL)
-----------------------------------

Input: "2 eggs and 1 cup milk"
Output:
[
  {"food": "egg", "quantity": 2},
  {"food": "milk", "quantity": 1, "unit": "cup"}
]

---

Input: "chicken alfredo pasta with mushrooms and onions"
Output:
{
  "dish": "chicken alfredo pasta with mushrooms and onions"
}

---

Input: "pasta and salad"
Output:
{
  "dish": "pasta and salad"
}

---

Input: "eggs toast and bacon"
Output:
{
  "dish": "eggs toast and bacon"
}

---

Input: "burger and fries with a drink"
Output:
{
  "dish": "burger and fries with a drink"
}

---

Input: "I had pasta and later drank milk"
Output:
[
  {"food": "pasta", "quantity": 1},
  {"food": "milk", "quantity": 1}
]

---

Input: "coffee and a bagel"
Output:
{
  "dish": "coffee and bagel"
}

-----------------------------------
FINAL INSTRUCTION
-----------------------------------

Return ONLY valid JSON.
NO explanations.
NO extra text.
NO formatting errors.
"""
                },
                {"role": "user", "content": food_text}
            ],
            temperature=0
        )
        text = response.choices[0].message.content
        data = json.loads(text)
        if "quantity" in data:
            return float(data["quantity"])
    except Exception as e:
        print("Portion estimation error:", e)
    return 1

# ------------------ AI FOOD EXTRACTION ------------------

async def extract_foods_with_ai(query: str):
    prompt = f'Extract foods from: "{query}"'
    text = safe_groq_call(prompt)
    if text:
        data = extract_json(text)
        if data:
            # CASE 1: multiple foods
            if isinstance(data, list):
                validated = validate_foods(data)
                for item in validated:
                    item["quantity"] *= estimate_portion(item["food"])
                return validated
            # CASE 2: dish → decompose
            elif isinstance(data, dict) and "dish" in data:
                ingredients = decompose_dish_to_ingredients(data["dish"])
                portion = estimate_portion(data["dish"])
                return [
                    {"food": ingredient, "quantity": portion}
                    for ingredient in ingredients
                ]
    return [{"food": query, "quantity": 1}]

# ------------------ USDA FETCH ------------------

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

        nutrient_lookup = {
            "Energy": "calories",
            "Protein": "protein_g",
            "Carbohydrate, by difference": "carbs_g",
            "Total lipid (fat)": "fat_g",
            "Total Sugars including NLEA": "sugar_g",
            "Fiber, total dietary": "fiber_g",
            "Vitamin D (D2 + D3)": "vitamin_d_mcg",
        }

        nutrition_data = {v: 0 for v in nutrient_lookup.values()}

        for nutrient in selected_food.get("foodNutrients", []):
            name = nutrient.get("nutrientName")
            if name in nutrient_lookup:
                nutrition_data[nutrient_lookup[name]] = nutrient.get("value", 0)

        return nutrition_data

# ------------------ TEXT INPUT ------------------

@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str):
    query = clean_voice_input(query)
    foods = await extract_foods_with_ai(query)
    return await process_foods(request, foods)

# ------------------ VOICE INPUT ------------------

@app.post("/voice")
async def voice_input(request: Request, file: UploadFile = File(...)):
    transcript = await transcribe_audio(file)
    if not transcript:
        return {"error": "Transcription failed"}

    cleaned_query = normalize_transcript(transcript)
    cleaned_query = clean_voice_input(cleaned_query)
    foods = await extract_foods_with_ai(cleaned_query)
    return await process_foods(request, foods, transcript=transcript)

# ------------------ PROCESS FOODS ------------------

async def process_foods(request, foods, transcript=None):
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
            print(f"USDA failed for: {food['food']}")
            nutrition = {k: 0 for k in totals}

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
            "totals": totals,
            "transcript": transcript
        }
    )