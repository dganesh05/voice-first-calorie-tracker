import os
import json
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

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


def _build_fallback_query(brand: str | None, descriptors: list[str], food_name: str) -> str:
    parts = []
    if brand:
        parts.append(brand)
    parts.extend(descriptors)
    parts.append(food_name)
    return " ".join([p for p in parts if p]).strip()


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
- "fallback_search_query": concatenation of brand + descriptors + food_name

Rules:
- Return only JSON array.
- Ensure each object has all fields.
- Keep descriptors as an array (can be empty).
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

        if not isinstance(parsed, list):
            raise ValueError("Groq parser response was not a JSON array")

        normalized = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            food_name = str(entry.get("food_name") or entry.get("item") or "").strip()
            if not food_name:
                continue
            quantity = _parse_quantity(entry.get("quantity", entry.get("qty", 1)))
            unit = str(entry.get("unit") or "serving").strip()
            descriptors = _normalize_descriptors(entry.get("descriptors"))

            raw_brand = entry.get("brand")
            brand = str(raw_brand).strip() if raw_brand not in (None, "", "null") else None

            fallback_search_query = str(
                entry.get("fallback_search_query")
                or _build_fallback_query(brand, descriptors, food_name)
            ).strip()

            normalized.append(
                {
                    "quantity": quantity,
                    "unit": unit,
                    "food_name": food_name,
                    "descriptors": descriptors,
                    "brand": brand,
                    "fallback_search_query": fallback_search_query,
                }
            )

        return normalized