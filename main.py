from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import json
import re

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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

# ------------------ FOOD PARSER PROMPT ------------------

FOOD_PARSER_PROMPT = """
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

# ------------------ ROUTES ------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("front_end.html", {"request": request})

# TEXT INPUT ROUTE
@app.get("/foods/search", response_class=HTMLResponse)
async def usda_api(request: Request, query: str):
    query = clean_voice_input(query)
    foods = await extract_foods_with_ai(query)
    return await process_foods(request, foods)

# VOICE INPUT ROUTE
@app.post("/voice")
async def voice_input(request: Request, file: UploadFile = File(...)):
    transcript = await transcribe_audio(file)
    if not transcript:
        return {"error": "Transcription failed"}
    cleaned_query = normalize_transcript(transcript)
    cleaned_query = clean_voice_input(cleaned_query)
    foods = await extract_foods_with_ai(cleaned_query)
    return await process_foods(request, foods, transcript=transcript)

# ------------------ CLEAN INPUT ------------------

def clean_voice_input(query: str):
    query = query.lower()
    fillers = ["i ate", "i had", "i just ate", "for breakfast", "for lunch", "for dinner"]
    for f in fillers:
        query = query.replace(f, "")
    return query.strip()

def normalize_transcript(text: str):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

# ------------------ WHISPER ------------------

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

def safe_groq_call(user_prompt: str, system_prompt: str = "Return ONLY valid JSON."):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Groq error:", e)
        return None

# ------------------ JSON ------------------

def extract_json(text):
    try:
        return json.loads(text)
    except Exception as e:
        print("JSON parse error:", e)
        return None

# ------------------ VALIDATE ------------------

def validate_foods(data):
    VALID_STOPWORDS = {"and", "of", "a", "the"}
    clean = []
    for item in data:
        food = item.get("food", "").strip()
        if not food or food in VALID_STOPWORDS:
            continue
        try:
            quantity = float(item.get("quantity", 1))
        except:
            quantity = 1
        clean.append({"food": food, "quantity": quantity})
    return clean

# ------------------ DECOMPOSE ------------------

def decompose_dish_to_ingredients(dish_name: str):
    try:
        text = safe_groq_call(dish_name, "Return a JSON array of core ingredients only.")
        data = extract_json(text)
        if isinstance(data, list):
            return data
    except Exception as e:
        print("Decomposition error:", e)
    return [dish_name]

# ------------------ PORTION ------------------

def estimate_portion(food_text: str):
    try:
        text = safe_groq_call(food_text, """
Return ONLY JSON: {"quantity": number}

Rules:
- one=1, two=2, three=3
- a/an=1
- bowl=2, plate=2
- slice=1, cup=1, glass=1

Examples:
"one bowl pasta" → 2
"two bowls pasta" → 4

If unclear → 1
""")
        data = extract_json(text)
        return float(data.get("quantity", 1))
    except Exception as e:
        print("Portion error:", e)
        return 1

# ------------------ AI EXTRACTION ------------------

async def extract_foods_with_ai(query: str):
    # Ask Groq AI to parse the foods using our strict prompt
    text = safe_groq_call(query, FOOD_PARSER_PROMPT)

    if text:
        data = extract_json(text)

        if data:
            # AI returned a list → treat as separate foods
            if isinstance(data, list):
                validated = validate_foods(data)
                portion = estimate_portion(query)
                for item in validated:
                    item["quantity"] *= portion
                return validated

            # AI returned a single dish → do NOT decompose, treat as 1 item
            elif isinstance(data, dict) and "dish" in data:
                portion = estimate_portion(query)
                return [{"food": data["dish"], "quantity": portion}]

    # Fallback → treat input as a single food
    return [{"food": query, "quantity": 1}]

# ------------------ PORTION ------------------

def estimate_portion(food_text: str):
    """
    Estimates quantity based on text like:
    - "one bowl pasta" → 1
    - "two bowls pasta" → 2
    - "half cup rice" → 0.5
    - "1.5 slices bread" → 1.5
    Defaults to 1 if unclear.
    """
    try:
        text = safe_groq_call(food_text, """
Return ONLY JSON: {"quantity": number}

Rules:
1. NUMBER WORDS
- one → 1, two → 2, three → 3, four → 4, five → 5
- a/an → 1
- half → 0.5, quarter → 0.25
- If a decimal is written (e.g., 1.5) → use it directly

2. UNITS
- bowl, plate, cup, glass, slice → do NOT multiply; unit only helps clarify
- Ignore words like 'serving', 'piece', 'portion' unless numeric

3. DEFAULT
- If no number found → 1
- Fractions or mixed numbers should be handled correctly

EXAMPLES:
- "one bowl pasta" → 1
- "two bowls pasta" → 2
- "half cup rice" → 0.5
- "1.5 slices bread" → 1.5
- "a plate of chicken" → 1

Return JSON only, nothing else.
""")
        data = extract_json(text)
        return float(data.get("quantity", 1))
    except Exception as e:
        print("Portion error:", e)
        return 1

# ------------------ USDA ------------------
async def fetch_usda(food_name: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={"api_key": USDA_API_KEY},
            json={"query": food_name}
        )

        if response.status_code != 200:
            return None

        foods = response.json().get("foods", [])
        if not foods:
            return None

        selected = foods[0]

        # Define all macros we want
        lookup = {
            "Energy": "calories",
            "Protein": "protein_g",
            "Carbohydrate, by difference": "carbs_g",
            "Total lipid (fat)": "fat_g",
            "Sugars, total including NLEA": "sugar_g",
            "Fiber, total dietary": "fiber_g",
            "Vitamin D (D2 + D3), International Units": "vitamin_d_mcg"
        }

        # Initialize with "Not Available"
        nutrition = {v: "Not Available" for v in lookup.values()}

        for n in selected.get("foodNutrients", []):
            if n.get("nutrientName") in lookup:
                nutrition[lookup[n["nutrientName"]]] = n.get("value", "Not Available")

        return nutrition

# ------------------ PROCESS ------------------

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
        nutrition = await fetch_usda(food["food"]) or {k: "Not Available" for k in totals}

        # Multiply numeric values by quantity
        for k in nutrition:
            if isinstance(nutrition[k], (int, float)):
                nutrition[k] *= food["quantity"]
            else:
                nutrition[k] = "Not Available"

        result = {"food": f"{food['quantity']} x {food['food']}", **nutrition}
        results.append(result)

        # Add to totals if numeric
        for key in totals:
            if isinstance(nutrition[key], (int, float)):
                totals[key] += nutrition[key]

    # Convert totals for missing values
    for key in totals:
        if totals[key] == 0:
            totals[key] = "Not Available"

    return templates.TemplateResponse(
        "front_end.html",
        {"request": request, "results": results, "totals": totals, "transcript": transcript}
    )