# Vocalorie: System Design & Architecture Specification

## 1. High-Level Architecture
Vocalorie is a voice-first dietary tracking application. The system leverages an LLM to parse natural language voice inputs into structured queries, resolving them against a tiered database architecture to log nutritional metrics.

* **Frontend:** HTML/JS with Jinja2 Templating.
* **Backend:** Python / FastAPI.
* **Database:** Supabase (PostgreSQL).
* **AI/NLP Parsing:** Groq API (Llama 3).
* **External Nutrition API:** USDA FoodData Central.
* **Hosting:** AWS (EC2 or Elastic Beanstalk for the backend app).

---

## 2. Frontend Page Specifications

### Page 1: Logging & Food Creation (`/log`)
The core interaction loop for the user. Explicitly avoids auto-logging to build trust and allow for frictionless corrections.

* **Voice Interface:** Uses the Web Speech API to capture speech, transcribe it, and send the text to the backend.
* **The Staging Card (Receipt):** Instead of auto-logging, the UI renders the single best guess returned by the Food Resolver as a staging card (e.g., "1 Bowl - Bojangles Mac n Cheese (450 kcal)").
* **The Commit Action:** A primary "[Log Meal]" button that, when tapped, commits the staged items to the user's daily journal.
* **The Override (Personal DB):** An "[Edit]" or "[Change]" button next to the staged item. Tapping this exposes a manual entry form prepopulated with the parsed food name. The user inputs their custom macros (e.g., for a homemade version) and hits "[Save & Update]". This silently commits the new version to their `personal_foods` database tier and updates the Staging Card for final logging.

### Page 2: Food Journal (`/journal`)
The historical tracking and aggregation dashboard.

* **Date Selection:** Defaults to `TODAY`. Users can select past dates to view history.
* **Daily Log List:** Displays all items from the `daily_logs` table for the selected date and `user_id`.
* **Aggregation Metrics:** Calculates the `SUM()` of Calories, Protein, Carbs, and Fat for the day, and compares the total consumed calories against the user's `daily_calorie_goal`.

### Page 3: Profile Editing (`/profile`)
Standard account management.

* **Editable Fields:** `display_name`, `daily_calorie_goal` (essential for the Journal's math), and password reset.

### Page 4: Authentication (`/login`, `/register`)
Standard identity management.

* **Forms:** Standard email/password inputs.
* **Integration:** Posts to backend routes that interface with Supabase Auth to establish the user session.

---

## 3. The Data Parsing & Logging Flow

When a user speaks into the Logging Page, the backend executes the following pipeline:

**A. NLP Entity Extraction (Groq LLM)**
The raw transcript is parsed into a strict JSON array capturing `item`, `quantity`, `unit`, `descriptors`, `brand`, and a `fallback_search_query`.

```python
system_prompt = """
You are a strict dietary data extraction API. 
Your only job is to analyze the user's transcript and extract the food items they ate.
You must output a valid JSON array of objects. Do not output any conversational text, markdown, or explanations. 

For each distinct food item mentioned, extract the following fields:
- "quantity": The numeric amount (convert words like "two" to 2, "half" to 0.5. Default to 1 if unspecified).
- "unit": The measurement unit (e.g., "cup", "bowl", "slice", "glass", "grams", "whole"). 
- "food_name": The core base ingredient (e.g., "milk", "egg", "rice", "chicken").
- "descriptors": An array of adjectives modifying the food (e.g., ["scrambled"], ["grilled"], ["whole"], ["2%"]).
- "brand": The brand name if explicitly mentioned, otherwise null.
- "fallback_search_query": A clean, concatenated string of the brand, descriptors, and food_name for database searching.

Example Input: "For breakfast I had a massive bowl of oatmeal with a handful of blueberries and two slices of Dave's Killer Bread."
Example Output:
[
  {
    "quantity": 1,
    "unit": "bowl",
    "food_name": "oatmeal",
    "descriptors": ["massive"],
    "brand": null,
    "fallback_search_query": "massive oatmeal"
  },
  {
    "quantity": 1,
    "unit": "handful",
    "food_name": "blueberries",
    "descriptors": [],
    "brand": null,
    "fallback_search_query": "blueberries"
  },
  {
    "quantity": 2,
    "unit": "slice",
    "food_name": "bread",
    "descriptors": [],
    "brand": "Dave's Killer Bread",
    "fallback_search_query": "Dave's Killer Bread bread"
  }
]

Process the following transcript:
"""
```

**B. The Food Resolver Cascade**
For *each* item in the extracted list, the backend checks:
1. **Personal DB:** Matches `user_id` + `item` + `descriptors`.
2. **Crowdsourced DB:** Matches global community entries.
3. **USDA API (Smart Fetch):** If no DB match, queries USDA. Uses `brand` to filter for Branded data, or `descriptors` to find the exact Foundation match. Caches the result in the Crowdsourced DB for future use.

**C. Stage, Then Commit**
The backend returns the resolved JSON array to the frontend. The frontend holds this data in the "Staging Card". Once the user manually verifies the data and clicks "[Log Meal]", the frontend sends a final POST request to the backend, which writes the aggregated items into the `daily_logs` table with the `user_id` and `logged_at` timestamp.

---

## 4. Database Schema (Supabase)

The PostgreSQL database consists of four interconnected tables:

1. **`users`**: `id` (UUID), `email`, `display_name`, `daily_calorie_goal`.
2. **`personal_foods`**: `id`, `user_id` (FK to users), `food_name`, `calories`, macros. *(Overrides for specific users).*
3. **`global_foods`**: `id`, `food_name`, `calories`, macros, `source` (USDA vs Crowdsourced). *(The communal cache).*
4. **`daily_logs`**: `id`, `user_id` (FK), `food_name`, `calories`, macros, `logged_at` (Timestamp). *(The Journal).*

---

## 5. AWS Hosting Strategy (MVP)

To ensure the Web Speech API functions properly on the frontend, the site **must** be served over HTTPS. 
* **Compute:** The Python FastAPI app will run on a single AWS EC2 instance (or Elastic Beanstalk for easier environment variable management).
* **Routing/Security:** AWS Route 53 for domain DNS, pointing to an Application Load Balancer (ALB) configured with an AWS Certificate Manager (ACM) SSL certificate to provide HTTPS.