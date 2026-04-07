import os
import json
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


NUMBER_WORDS = {
    "zero": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "half": 0.5,
    "quarter": 0.25,
}

UNIT_ALIASES = {
    "piece": "piece",
    "pieces": "piece",
    "slice": "slice",
    "slices": "slice",
    "cup": "cup",
    "cups": "cup",
    "bowl": "bowl",
    "bowls": "bowl",
    "glass": "glass",
    "glasses": "glass",
    "serving": "serving",
    "servings": "serving",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "gram": "gram",
    "grams": "gram",
}


def _extract_json_payload(content: str):
    text = (content or "").strip()

    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

    return json.loads(text)


def _parse_quantity(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip().lower()
    if not raw:
        return 1.0
    if raw in NUMBER_WORDS:
        return float(NUMBER_WORDS[raw])
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0


def _normalize_descriptors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _sanitize_food_text(text: str) -> str:
    # Keep letters, numbers, spaces, percent, and apostrophes for cleaner queries.
    value = str(text or "").lower()
    value = re.sub(r"[^a-z0-9%\s']+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_food_name_and_unit(food_name: str, unit: str) -> tuple[str, str]:
    cleaned_food = _sanitize_food_text(food_name)
    normalized_unit = str(unit or "serving").strip().lower() or "serving"

    of_match = re.match(r"^(\w+)\s+of\s+(.+)$", cleaned_food)
    if of_match:
        parsed_unit = UNIT_ALIASES.get(of_match.group(1))
        parsed_food = of_match.group(2).strip()
        if parsed_unit and parsed_food:
            if normalized_unit in {"", "serving"}:
                normalized_unit = parsed_unit
            cleaned_food = parsed_food

    words = cleaned_food.split()
    if words and words[0] in UNIT_ALIASES and len(words) > 1:
        parsed_unit = UNIT_ALIASES[words[0]]
        parsed_food = " ".join(words[1:]).strip()
        if parsed_food:
            if normalized_unit in {"", "serving"}:
                normalized_unit = parsed_unit
            cleaned_food = parsed_food

    return cleaned_food, normalized_unit


def _normalize_text_list(value: Any) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _sanitize_food_text(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _build_fallback_query(
    brand: str | None,
    descriptors: list[str],
    food_name: str,
    source_items: list[str] | None = None,
    base_query: str | None = None,
) -> str:
    parts = []
    if base_query:
        parts.append(_sanitize_food_text(base_query))
    if brand:
        parts.append(_sanitize_food_text(brand))
    parts.extend([_sanitize_food_text(d) for d in descriptors])
    parts.append(_sanitize_food_text(food_name))
    parts.extend(_normalize_text_list(source_items))

    deduped_parts: list[str] = []
    seen_parts: set[str] = set()
    for part in parts:
        if not part or part in seen_parts:
            continue
        seen_parts.add(part)
        deduped_parts.append(part)
    return " ".join(deduped_parts).strip()


def _normalize_top_level_payload(parsed: Any) -> list[dict[str, Any]]:
    # Accept either a list of items or a single dish object and normalize to list.
    if isinstance(parsed, list):
        return [entry for entry in parsed if isinstance(entry, dict)]

    if isinstance(parsed, dict):
        dish_name = str(parsed.get("dish") or "").strip()
        if dish_name:
            return [
                {
                    "quantity": 1,
                    "unit": "serving",
                    "food_name": dish_name,
                    "descriptors": [],
                    "brand": None,
                    "split_foods": [dish_name],
                    "source_items": [],
                    "fallback_search_query": dish_name,
                }
            ]
        return [parsed]

    return []


async def parse_raw_transcript(transcript: str) -> list:
    """Sends raw voice text to Groq and returns a structured JSON array."""
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY in environment")

    system_prompt = """
You are a strict dietary data extraction API.
Your only job is to analyze the user's transcript and extract the food items they ate.
You must output a valid JSON array of objects. Do not output any conversational text, markdown, or explanations.

For each distinct food item mentioned, extract exactly these fields:
- "quantity": numeric amount (convert words like "two" -> 2, "half" -> 0.5, default 1)
- "unit": measurement unit when present (e.g., cup, bowl, slice, glass, grams); default "serving"
- "food_name": base food name
- "descriptors": array of modifiers/adjectives
- "brand": brand name if explicit, otherwise null
- "split_foods": array of resolvable foods for this item. For compound dishes, include each component food; for simple foods, include [food_name].
- "source_items": array of source ingredients/components that help search (can be empty)
- "fallback_search_query": concise search phrase using brand + descriptors + component/source context

Rules:
- Return only JSON array.
- Ensure each object has all fields.
- Keep descriptors as an array (can be empty).
- Use food-context reasoning (not fixed mappings) to infer split_foods and source_items.
- If the transcript implies transformed or composite foods, include likely component foods in split_foods/source_items.
""".strip()
    user_prompt = f"Process this transcript:\n\"{transcript}\""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama3-8b-8192", # Fast and free
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0
            }
        )

        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json_payload(content)
        entries = _normalize_top_level_payload(parsed)
        if not entries:
            raise ValueError("Groq parser response did not contain usable food entities")

        normalized = []
        for entry in entries:
            food_name = str(entry.get("food_name") or entry.get("item") or "").strip()
            if not food_name:
                continue
            quantity = _parse_quantity(entry.get("quantity", entry.get("qty", 1)))
            unit = str(entry.get("unit") or "serving").strip()
            descriptors = [_sanitize_food_text(d) for d in _normalize_descriptors(entry.get("descriptors"))]
            descriptors = [d for d in descriptors if d]

            food_name, unit = _normalize_food_name_and_unit(food_name, unit)
            if not food_name:
                continue

            raw_brand = entry.get("brand")
            brand = str(raw_brand).strip() if raw_brand not in (None, "", "null") else None
            brand = _sanitize_food_text(brand) if brand else None

            base_query = str(entry.get("fallback_search_query") or "").strip() or None
            source_items = _normalize_text_list(entry.get("source_items"))
            split_foods = _normalize_text_list(entry.get("split_foods"))
            if not split_foods:
                split_foods = [food_name]

            for split_food in split_foods:
                fallback_search_query = _build_fallback_query(
                    brand,
                    descriptors,
                    split_food,
                    source_items=source_items,
                    base_query=base_query,
                )

                normalized.append(
                    {
                        "quantity": quantity,
                        "unit": unit,
                        "food_name": split_food,
                        "descriptors": descriptors,
                        "brand": brand,
                        "source_items": source_items,
                        "fallback_search_query": fallback_search_query,
                    }
                )

        return normalized