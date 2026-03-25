# Food Resolver Architecture & Flow

The Food Resolver is the core backend engine of Vocalorie. Its primary responsibility is to take unstructured, natural language input and reliably convert it into structured nutritional data to be displayed on the frontend. 

**The Food Resolver is agnostic to the input method.** It does not care if the input string came from a hardcoded testing script or a frontend Web Speech API transcription. As long as it receives a text string, the cascade will execute.



## The 5-Phase Resolution Pipeline

Every string passed to the `/foods/process` endpoint goes through the following synchronous flow.

### Phase 1: Input Standardization (The LLM Parser)
Human speech uses non-standard measurements (e.g., "a handful," "a massive bowl"). Relational databases and the USDA API cannot parse this effectively.

* **Action:** The raw transcript is sent to the Groq API (Llama 3) with a strict system prompt.
* **Output:** Groq returns a strict JSON array of standardized entities and quantities.
* **Example:** * *Input:* "uh yeah I ate like two scrambled eggs and some Dave's Killer Bread toast"
  * *Output:* `[{"item": "scrambled egg", "qty": 2}, {"item": "Dave's Killer Bread toast", "qty": 1}]`

### Phase 2: Tier 1 - The Personal Database
The system loops through each standardized item. The first check is always the user's personal database.

* **Action:** Supabase queries the `personal_foods` table matching the specific `user_id` and `food_name`.
* **Why:** Allows users to have custom recipes or overwrite global calorie counts for their specific portion sizes.
* **Result:** If a match is found, the data is returned, multiplied by the `qty`, and the loop moves to the next food item. If no match is found, it falls through to Phase 3.

### Phase 3: Tier 2 - The Crowdsourced / Global Cache
If the user hasn't logged this specific food, the system checks our internal global cache.

* **Action:** Supabase queries the `crowdsourced_foods` table.
* **Why:** Hitting external APIs is slow. This table acts as a cache for every food item any user has ever successfully resolved, saving us from redundant network requests.
* **Result:** If a match is found, the data is returned. If no match is found, the system falls through to Phase 4.

### Phase 4: Tier 3 - The USDA API ("Smart" Fetch & Filter)
This is the final resort. If the food does not exist in our internal databases, we fetch it from the USDA FoodData Central API. Because the USDA database is massive, we must query and filter across three distinct data types to ensure accurate results.

* **Action:** The system makes an HTTP POST request to the USDA API, requesting the top 10 results across these specific `dataTypes`:
  1. **Foundation / SR Legacy ("Normal"):** Single-ingredient, generic foods (e.g., raw apple, chicken breast).
  2. **Branded:** Store-bought items with barcodes (e.g., Oreo, Chobani).
  3. **Survey - FNDDS ("Exotic" / Mixed):** Complex restaurant meals or prepared dishes (e.g., Taco Bell Burrito, Lasagna).
* **The Filtering Logic:** The backend script evaluates the USDA's top 10 returned items based on the original parsed string:
  * If the string implies a brand name, it selects the first `Branded` result.
  * If the string implies a complex/mixed dish, it selects the first `Survey (FNDDS)` result.
  * For all other generic queries, it defaults to the first `Foundation` or `SR Legacy` result.
* **The Cache Save:** Before returning this data to the loop, the system **inserts this new record into the `crowdsourced_foods` table**, appending its USDA `food_category`. 
* **Why:** The next time any user asks for this food item, it will be caught in Phase 3.

### Phase 5: Aggregation and Response
Once every item in the Phase 1 JSON array has cascaded through the database tiers, the backend aggregates the data.

* **Action:** The script calculates the running totals for calories and macros for the entire meal.
* **Output:** A single JSON payload is sent back to the frontend containing the line-item breakdown and the meal totals.

```json
{
  "status": "success",
  "results": [
    {"name": "scrambled egg", "calories": 180, "protein": 12, "source": "USDA", "category": "Foundation"},
    {"name": "Dave's Killer Bread toast", "calories": 110, "protein": 5, "source": "USDA", "category": "Branded"}
  ],
  "totals": {
    "calories": 290,
    "protein": 17
  }
}