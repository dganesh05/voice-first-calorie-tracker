import os
import json
import re
import string
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from supabase_client import supabase

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"), override=True)


USDA_API_KEY = os.getenv("USDA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
_USDA_KEY_DISABLED_REASON: str | None = None


def _planner_model_candidates() -> list[str]:
    """Return ordered Groq planner model candidates.

    Can be overridden with GROQ_PLANNER_MODELS="model-a,model-b".
    """
    raw = str(os.getenv("GROQ_PLANNER_MODELS") or "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models

    return [
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
    ]


def _log_resolution_step(message: str, **details: Any) -> None:
    if details:
        print(f"[food_resolver] {message} | {details}")
        return
    print(f"[food_resolver] {message}")


def _has_usable_usda_key() -> bool:
    key = str(USDA_API_KEY or "").strip()
    if not key:
        return False
    placeholders = {
        "your-usda-api-key",
        "your_usda_api_key",
        "replace-me",
        "changeme",
    }
    return key.lower() not in placeholders


def _to_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_query(food_item: str) -> str:
    return str(food_item or "").strip().lower()


def _canonicalize_text(value: str) -> str:
    text = str(value or "").lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text_list(value: Any) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _canonicalize_text(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _collect_lookup_terms(food_item: str) -> list[str]:
    canonical = _canonicalize_text(food_item)
    terms = [term for term in canonical.split() if term]
    if canonical and canonical not in terms:
        terms.insert(0, canonical)
    return terms[:4]


def _merge_lookup_terms(*queries: str | None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for query in queries:
        for term in _collect_lookup_terms(str(query or "")):
            if term in seen:
                continue
            seen.add(term)
            merged.append(term)
    return merged[:8]


def _normalize_food_record(record: dict, fallback_name: str) -> dict:
    """Return a consistent macro schema regardless of data source."""
    category = record.get("food_category") or record.get("category")
    protein = _to_number(record.get("protein", record.get("protein_g", 0)))
    carbs = _to_number(record.get("carbs", record.get("carbs_g", 0)))
    fat = _to_number(record.get("fat", record.get("fat_g", 0)))
    calories = _to_number(record.get("calories", 0))
    category_text = str(category or "").strip().lower()
    is_branded = category_text == "branded"
    if calories <= 0 and (protein > 0 or carbs > 0 or fat > 0) and not is_branded:
        calories = _infer_calories_from_macros(protein, carbs, fat)
    return {
        "food_name": record.get("food_name") or fallback_name,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "source": record.get("source") or "internal",
        "category": category or "unknown",
    }


def _extract_nutrient_value(food: dict, preferred_names: list[str]) -> float:
    nutrients = food.get("foodNutrients", [])
    for nutrient in nutrients:
        nutrient_name = str(nutrient.get("nutrientName", "")).strip().lower()
        if nutrient_name in preferred_names:
            return _to_number(nutrient.get("value"))
    return 0.0


def _looks_branded(food_item: str) -> bool:
    text = _normalize_query(food_item)
    branded_signals = [
        "brand",
        "bar",
        "protein powder",
        "chips",
        "cookie",
        "cereal",
        "soda",
        "yogurt",
        "starbucks",
        "mcdonald",
        "taco bell",
        "chipotle",
        "subway",
        "kellogg",
        "oreo",
        "chobani",
    ]
    return any(signal in text for signal in branded_signals)


def _looks_mixed_dish(food_item: str) -> bool:
    text = _normalize_query(food_item)
    mixed_dish_signals = [
        "burrito",
        "lasagna",
        "sandwich",
        "salad",
        "soup",
        "pizza",
        "pasta",
        "stew",
        "curry",
        "taco",
        "bowl",
        "casserole",
    ]
    return any(signal in text for signal in mixed_dish_signals)


def _local_resolution_hints(
    food_item: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
) -> dict[str, Any]:
    text = _canonicalize_text(food_item)
    hints: dict[str, Any] = {}

    spelling_corrections = {
        "omlette": "omelet",
        "omelette": "omelet",
    }
    if text in spelling_corrections:
        hints["corrected_food_name"] = spelling_corrections[text]

    if "toast" in text:
        hints.setdefault("corrected_food_name", "toast")
        hints["source_items"] = ["bread"]
        hints["compound_foods"] = ["toast", "bread"]
        if "avocado" in text:
            hints["compound_foods"] = ["toast", "avocado", "bread"]

    if "maggi" in text and not brand:
        hints["brand"] = "Maggi"

    if not hints:
        return {}

    return {
        "corrected_food_name": hints.get("corrected_food_name", ""),
        "compound_foods": _normalize_text_list(hints.get("compound_foods")),
        "source_items": _normalize_text_list(hints.get("source_items")),
        "brand": _first_nonempty(hints.get("brand")),
        "notes": "",
    }


def _has_usable_groq_key() -> bool:
    key = str(GROQ_API_KEY or "").strip()
    if not key:
        return False
    placeholders = {
        "your-groq-api-key",
        "your_groq_api_key",
        "replace-me",
        "changeme",
    }
    return key.lower() not in placeholders


def _descriptor_score(description: str, descriptors: list[str] | None) -> int:
    if not descriptors:
        return 0
    haystack = str(description or "").lower()
    return sum(1 for d in descriptors if str(d).lower() in haystack)


_DERIVATIVE_QUALIFIERS = {
    "oil",
    "butter",
    "sauce",
    "dressing",
    "spread",
    "dip",
    "powder",
    "extract",
    "concentrate",
    "seasoning",
    "flavor",
    "juice",
    "drink",
    "beverage",
}


def _intent_tokens(
    food_item: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
) -> set[str]:
    text_parts = [food_item, fallback_search_query, brand, " ".join(descriptors or [])]
    tokens: set[str] = set()
    for part in text_parts:
        canonical = _canonicalize_text(part or "")
        if not canonical:
            continue
        tokens.update([token for token in canonical.split() if token])
    return tokens


def _qualifier_mismatch_penalty(candidate_text: str, intent: set[str]) -> int:
    if not candidate_text:
        return 0
    candidate_tokens = set(_canonicalize_text(candidate_text).split())
    mismatches = [q for q in _DERIVATIVE_QUALIFIERS if q in candidate_tokens and q not in intent]
    if not mismatches:
        return 0

    penalty = len(mismatches) * 12

    # Short, ambiguous intents (e.g., single brand tokens) are especially prone
    # to derivative false positives like seasoning/oil/sauce cache rows.
    if len(intent) <= 3:
        penalty += 4

    return penalty


def _infer_calories_from_macros(protein: float, carbs: float, fat: float) -> float:
    """Estimate calories when USDA energy is missing but macros are present."""
    estimated = (protein * 4.0) + (carbs * 4.0) + (fat * 9.0)
    if estimated <= 0:
        return 0.0
    return round(estimated, 2)


def _candidate_score(food_item: str, candidate: dict, descriptors: list[str] | None) -> int:
    description = str(candidate.get("description") or "")
    query_tokens = set(_canonicalize_text(food_item).split())
    description_tokens = set(_canonicalize_text(description).split())

    score = _descriptor_score(description, descriptors)
    score += len(query_tokens & description_tokens) * 2

    if "toast" in query_tokens:
        if "toast" in description_tokens or "bread" in description_tokens:
            score += 4
        if "oil" in description_tokens and "toast" not in description_tokens and "bread" not in description_tokens:
            score -= 4

    if "omelet" in query_tokens or "omelette" in query_tokens:
        if "omelet" in description_tokens or "omelette" in description_tokens or "egg" in description_tokens:
            score += 4

    return score


def _candidate_score_with_intent(
    food_item: str,
    candidate: dict,
    descriptors: list[str] | None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
) -> int:
    base_score = _candidate_score(food_item, candidate, descriptors)
    intent = _intent_tokens(
        food_item,
        descriptors=descriptors,
        brand=brand,
        fallback_search_query=fallback_search_query,
    )
    description = str(candidate.get("description") or "")
    penalty = _qualifier_mismatch_penalty(description, intent)
    return base_score - penalty


def _pick_usda_food(
    food_item: str,
    candidates: list[dict],
    brand: str | None = None,
    descriptors: list[str] | None = None,
    fallback_search_query: str | None = None,
) -> dict | None:
    if not candidates:
        return None

    if brand or _looks_branded(food_item):
        brand_text = str(brand or "").strip().lower()
        branded_candidates = [f for f in candidates if f.get("dataType") == "Branded"]
        if brand_text:
            exact_brand = next(
                (
                    f
                    for f in branded_candidates
                    if brand_text in str(f.get("brandOwner") or "").lower()
                    or brand_text in str(f.get("brandName") or "").lower()
                    or brand_text in str(f.get("description") or "").lower()
                ),
                None,
            )
            if exact_brand:
                return exact_brand
        if branded_candidates:
            best = max(
                branded_candidates,
                key=lambda f: _candidate_score_with_intent(
                    food_item,
                    f,
                    descriptors,
                    brand=brand,
                    fallback_search_query=fallback_search_query,
                ),
            )
            if _candidate_score_with_intent(
                food_item,
                best,
                descriptors,
                brand=brand,
                fallback_search_query=fallback_search_query,
            ) <= 0:
                return None
            return best

    if _looks_mixed_dish(food_item):
        survey = next((f for f in candidates if f.get("dataType") == "Survey (FNDDS)"), None)
        if survey:
            return survey

    foundation = next(
        (
            f
            for f in candidates
            if f.get("dataType") in {"Foundation", "SR Legacy"}
        ),
        None,
    )
    if foundation:
        scored_foundations = [f for f in candidates if f.get("dataType") in {"Foundation", "SR Legacy"}]
        best = max(
            scored_foundations,
            key=lambda f: _candidate_score_with_intent(
                food_item,
                f,
                descriptors,
                brand=brand,
                fallback_search_query=fallback_search_query,
            ),
        )
        if _candidate_score_with_intent(
            food_item,
            best,
            descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        ) <= 0:
            return None
        return best

    best = max(
        candidates,
        key=lambda f: _candidate_score_with_intent(
            food_item,
            f,
            descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        ),
    )
    if _candidate_score_with_intent(
        food_item,
        best,
        descriptors,
        brand=brand,
        fallback_search_query=fallback_search_query,
    ) <= 0:
        return None
    return best


async def _infer_resolution_hints(
    food_item: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
) -> dict[str, Any]:
    if not _has_usable_groq_key():
        return {}

    prompt = """
You are a food lookup planner. Given a user food token, infer only search-helpful hints.

Return valid JSON with these optional fields:
- corrected_food_name: the most likely spelling-corrected or normalized food name, if the token resembles a misspelling
- compound_foods: array of component foods if the item is a compound dish
- source_items: array of source ingredient names if the item is a transformed food or should be searched via source items
- brand: brand name if the token looks branded, otherwise null
- notes: short string only if useful

Rules:
- Be conservative.
- If the token already looks like a valid food, keep corrected_food_name the same or omit it.
- Use brand-aware reasoning for items like Maggi, Sara Lee Bread, Kellogg's, etc.
- For items like avocado toast, return compound_foods like ["avocado", "bread"] and source_items like ["bread"].
- For transformed foods like toast, return source_items like ["bread"] even if corrected_food_name is unchanged.
- Use the whole transcript and fallback query to infer the most likely form of the food.
- Example: if the intent is just "maggi" or "1 bowl maggi", prefer noodles/meal products over seasoning unless the transcript explicitly says seasoning, sauce, bouillon, or spice mix.
- Example: if the intent says "cooked with avocado oil", a derivative oil match is appropriate; if it says "avocado toast", keep avocado as the fruit/ingredient and do not shift to oil.
- Example: if a compound dish has a base item like bread or toast, preserve that base separately in source_items rather than folding it into the main ingredient.
""".strip()

    user_payload = {
        "food_item": food_item,
        "descriptors": descriptors or [],
        "brand": brand,
        "fallback_search_query": fallback_search_query,
    }

    models = _planner_model_candidates()
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        content = ""
        for model in models:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps(user_payload)},
                    ],
                    "temperature": 0.0,
                },
            )

            if response.status_code < 400:
                content = response.json()["choices"][0]["message"]["content"]
                break

            # Keep full body detail so planner failures are diagnosable in logs.
            detail = (response.text or response.reason_phrase or "unknown error").strip()
            errors.append(f"model={model} status={response.status_code} detail={detail}")

        if not content:
            raise RuntimeError("Groq planner failed: " + " | ".join(errors))

    text = (content or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}

    return {
        "corrected_food_name": _first_nonempty(parsed.get("corrected_food_name"), parsed.get("food_name")),
        "compound_foods": _normalize_text_list(parsed.get("compound_foods")),
        "source_items": _normalize_text_list(parsed.get("source_items")),
        "brand": _first_nonempty(parsed.get("brand")),
        "notes": _first_nonempty(parsed.get("notes")),
    }


async def _lookup_with_candidates(
    food_item: str,
    user_id: str,
    candidates: list[str],
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
    prefer_usda_first: bool = False,
    strict_query_match: bool = False,
):
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = _normalize_query(candidate)
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)

        personal_match = _lookup_personal_food(
            normalized_candidate,
            user_id,
            descriptors=descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        )
        if personal_match:
            return _normalize_food_record(personal_match, normalized_candidate)

        if prefer_usda_first:
            usda_data = await fetch_from_usda(
                normalized_candidate,
                search_query=normalized_candidate,
                brand=brand,
                descriptors=descriptors,
            )
            if usda_data:
                cache_record = {
                    "food_name": usda_data.get("food_name", normalized_candidate),
                    "calories": usda_data.get("calories", 0),
                    "protein": usda_data.get("protein", 0),
                    "carbs": usda_data.get("carbs", 0),
                    "fat": usda_data.get("fat", 0),
                    "source": "USDA",
                    "food_category": usda_data.get("food_category") or usda_data.get("category"),
                }
                try:
                    supabase.table("global_foods").insert(cache_record).execute()
                    _log_resolution_step(
                        "USDA cache insert completed",
                        table="global_foods",
                        food_name=cache_record.get("food_name"),
                    )
                except Exception:
                    _log_resolution_step(
                        "USDA cache insert skipped",
                        table="global_foods",
                        reason="write failure or missing table",
                    )
                return _normalize_food_record(usda_data, normalized_candidate)

        cache_match = _lookup_global_food(
            normalized_candidate,
            descriptors=descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        )
        if cache_match:
            normalized_cache = _normalize_food_record(cache_match, normalized_candidate)
            if strict_query_match:
                normalized_name = _canonicalize_text(normalized_cache.get("food_name") or "")
                if normalized_name != _canonicalize_text(normalized_candidate):
                    continue
            return normalized_cache

        usda_search_query = normalized_candidate if prefer_usda_first else fallback_search_query
        usda_data = await fetch_from_usda(
            normalized_candidate,
            search_query=usda_search_query,
            brand=brand,
            descriptors=descriptors,
        )
        if usda_data:
            cache_record = {
                "food_name": usda_data.get("food_name", normalized_candidate),
                "calories": usda_data.get("calories", 0),
                "protein": usda_data.get("protein", 0),
                "carbs": usda_data.get("carbs", 0),
                "fat": usda_data.get("fat", 0),
                "source": "USDA",
                "food_category": usda_data.get("food_category") or usda_data.get("category"),
            }
            try:
                supabase.table("global_foods").insert(cache_record).execute()
                _log_resolution_step(
                    "USDA cache insert completed",
                    table="global_foods",
                    food_name=cache_record.get("food_name"),
                )
            except Exception:
                _log_resolution_step(
                    "USDA cache insert skipped",
                    table="global_foods",
                    reason="write failure or missing table",
                )
            return _normalize_food_record(usda_data, normalized_candidate)

    return None


async def fetch_from_usda(
    food_item: str,
    search_query: str | None = None,
    brand: str | None = None,
    descriptors: list[str] | None = None,
):
    global _USDA_KEY_DISABLED_REASON

    if _USDA_KEY_DISABLED_REASON:
        _log_resolution_step("USDA lookup skipped", reason=_USDA_KEY_DISABLED_REASON)
        return None

    if not _has_usable_usda_key():
        _log_resolution_step("USDA lookup skipped", reason="missing or placeholder USDA_API_KEY")
        return None

    query_text = str(search_query or food_item or "").strip() or food_item
    _log_resolution_step(
        "USDA lookup started",
        food_item=food_item,
        query=query_text,
        brand=brand,
        descriptors=descriptors or [],
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={"api_key": USDA_API_KEY},
            json={
                "query": query_text,
                "pageSize": 10,
                "dataType": [
                    "Foundation",
                    "SR Legacy",
                    "Branded",
                    "Survey (FNDDS)",
                ],
            },
        )

        if response.status_code != 200:
            response_text = (response.text or "").strip()
            parsed_error = ""
            try:
                error_payload = response.json()
                parsed_error = str(
                    error_payload.get("error", {}).get("code")
                    or error_payload.get("error", {}).get("message")
                    or ""
                ).strip()
            except Exception:
                parsed_error = ""

            error_blob = f"{response_text} {parsed_error}".lower()
            if response.status_code in {401, 403} and "api_key_invalid" in error_blob:
                _USDA_KEY_DISABLED_REASON = "USDA_API_KEY rejected by USDA (API_KEY_INVALID)"

            _log_resolution_step(
                "USDA lookup failed",
                status_code=response.status_code,
                response_text=response_text[:300],
                reason=_USDA_KEY_DISABLED_REASON or "USDA request rejected",
            )
            return None

        foods = response.json().get("foods") or []
        food = _pick_usda_food(
            food_item,
            foods,
            brand=brand,
            descriptors=descriptors,
            fallback_search_query=search_query,
        )
        if not food:
            _log_resolution_step("USDA lookup skipped", reason="no suitable USDA candidate selected")
            return None

        category = food.get("dataType") or food.get("foodCategory") or "USDA"
        _log_resolution_step(
            "USDA lookup matched",
            food_name=food.get("description") or food_item,
            category=category,
        )

        protein = _extract_nutrient_value(food, ["protein"])
        carbs = _extract_nutrient_value(food, ["carbohydrate, by difference"])
        fat = _extract_nutrient_value(food, ["total lipid (fat)"])
        calories = _extract_nutrient_value(food, ["energy"])
        is_branded = str(category).strip().lower() == "branded"
        if calories <= 0 and (protein > 0 or carbs > 0 or fat > 0) and not is_branded:
            calories = _infer_calories_from_macros(protein, carbs, fat)

        return {
            "food_name": food.get("description") or food_item,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "source": "USDA",
            "category": category,
            "food_category": category,
        }


def _rank_candidate(record: dict, descriptors: list[str] | None, brand: str | None) -> int:
    score = 0
    searchable = " ".join(
        [
            str(record.get("food_name") or ""),
            str(record.get("brand") or ""),
            str(record.get("descriptors") or ""),
        ]
    ).lower()
    if brand and str(brand).lower() in searchable:
        score += 3
    for descriptor in descriptors or []:
        if str(descriptor).lower() in searchable:
            score += 1
    return score


def _match_score(food_item: str, record: dict) -> int:
    query = _canonicalize_text(food_item)
    candidate = _canonicalize_text(record.get("food_name") or "")
    if not query or not candidate:
        return 0
    if query == candidate:
        return 12
    if query in candidate:
        return 8

    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    if not query_tokens or not candidate_tokens:
        return 0
    overlap = len(query_tokens & candidate_tokens)
    return overlap


def _pick_best_cache_candidate(
    food_item: str,
    candidates: list[dict],
    descriptors: list[str] | None,
    brand: str | None,
    fallback_search_query: str | None,
    strict_query_match: bool = False,
) -> dict | None:
    """Pick the most relevant cached candidate, or None if all are weak matches.

    This prevents broad fallback queries (e.g. from compound foods) from selecting
    unrelated rows just because they appeared first in fuzzy search results.
    """
    if not candidates:
        return None

    intent = _intent_tokens(
        food_item,
        descriptors=descriptors,
        brand=brand,
        fallback_search_query=fallback_search_query,
    )
    query = _canonicalize_text(food_item)
    query_tokens = set(query.split())
    scored = []
    for rec in candidates:
        name = str(rec.get("food_name") or "")
        candidate_text = _canonicalize_text(name)
        candidate_tokens = set(candidate_text.split())
        base = _match_score(food_item, rec) + _rank_candidate(rec, descriptors, brand)
        base -= _qualifier_mismatch_penalty(name, intent)

        if strict_query_match:
            if query and candidate_text != query and not candidate_text.startswith(f"{query} "):
                base -= 8
            if len(query_tokens) <= 2 and len(candidate_tokens) > len(query_tokens) + 2:
                base -= 4

        scored.append((base, rec))
    best_score, best_record = max(scored, key=lambda item: item[0])

    # Require a meaningful match before accepting cache hits.
    if best_score <= 0:
        return None
    return best_record


def _lookup_personal_food(
    food_item: str,
    user_id: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
):
    normalized = _normalize_query(food_item)
    terms = _merge_lookup_terms(food_item, fallback_search_query)
    try:
        candidates: list[dict] = []
        seen_ids: set[str] = set()

        exact_response = (
            supabase.table("personal_foods")
            .select("*")
            .eq("user_id", user_id)
            .ilike("food_name", normalized)
            .limit(5)
            .execute()
        )
        for row in exact_response.data or []:
            row_id = str(row.get("id") or "")
            if row_id and row_id in seen_ids:
                continue
            if row_id:
                seen_ids.add(row_id)
            candidates.append(row)

        for term in terms:
            fuzzy_response = (
                supabase.table("personal_foods")
                .select("*")
                .eq("user_id", user_id)
                .ilike("food_name", f"%{term}%")
                .limit(10)
                .execute()
            )
            for row in fuzzy_response.data or []:
                row_id = str(row.get("id") or "")
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                candidates.append(row)

        return _pick_best_cache_candidate(
            food_item,
            candidates,
            descriptors,
            brand,
            fallback_search_query,
        )
    except Exception:
        # Treat connectivity and setup issues (missing table, auth, etc.) as cache miss.
        return None


def _lookup_global_food(
    food_item: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
):
    normalized = _normalize_query(food_item)
    terms = _merge_lookup_terms(food_item, fallback_search_query)
    try:
        candidates: list[dict] = []
        seen_ids: set[str] = set()

        exact_response = (
            supabase.table("global_foods")
            .select("*")
            .ilike("food_name", normalized)
            .limit(5)
            .execute()
        )
        for row in exact_response.data or []:
            row_id = str(row.get("id") or "")
            if row_id and row_id in seen_ids:
                continue
            if row_id:
                seen_ids.add(row_id)
            candidates.append(row)

        for term in terms:
            fuzzy_response = (
                supabase.table("global_foods")
                .select("*")
                .ilike("food_name", f"%{term}%")
                .limit(10)
                .execute()
            )
            for row in fuzzy_response.data or []:
                row_id = str(row.get("id") or "")
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                candidates.append(row)

        return _pick_best_cache_candidate(
            food_item,
            candidates,
            descriptors,
            brand,
            fallback_search_query,
        )
    except Exception:
        # Treat connectivity and setup issues (missing table, auth, etc.) as cache miss.
        return None


async def resolve_food_item(
    food_item: str,
    user_id: str,
    descriptors: list[str] | None = None,
    brand: str | None = None,
    fallback_search_query: str | None = None,
):
    normalized_food_item = _normalize_query(food_item)
    if not normalized_food_item:
        _log_resolution_step("Resolution skipped", reason="empty food item")
        return None

    _log_resolution_step(
        "Resolution started",
        food_item=normalized_food_item,
        user_id=user_id,
        descriptors=descriptors or [],
        brand=brand,
        fallback_search_query=fallback_search_query,
    )

    resolution_hints: dict[str, Any] = {}
    if _has_usable_groq_key():
        try:
            resolution_hints = await _infer_resolution_hints(
                normalized_food_item,
                descriptors=descriptors,
                brand=brand,
                fallback_search_query=fallback_search_query,
            )
        except Exception as exc:
            _log_resolution_step("Resolution hints skipped", reason="planner failed", error=str(exc))

    if not resolution_hints:
        resolution_hints = _local_resolution_hints(
            normalized_food_item,
            descriptors=descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
        )

    corrected_food_name = _normalize_query(resolution_hints.get("corrected_food_name") or "")
    is_spelling_correction = bool(corrected_food_name and corrected_food_name != normalized_food_item)
    hint_brand = _first_nonempty(resolution_hints.get("brand"), brand) or None
    compound_foods = _normalize_text_list(resolution_hints.get("compound_foods"))
    source_items = _normalize_text_list(resolution_hints.get("source_items"))

    lookup_sequence: list[tuple[str, list[str]]] = [
        ("exact", [normalized_food_item]),
    ]
    if corrected_food_name and corrected_food_name != normalized_food_item:
        lookup_sequence.append(("corrected", [corrected_food_name]))
    if compound_foods:
        lookup_sequence.append(("compound", compound_foods))
    if source_items:
        lookup_sequence.append(("source", source_items))

    if hint_brand and not brand:
        brand = hint_brand

    for stage_name, stage_candidates in lookup_sequence:
        _log_resolution_step("Lookup interval started", stage=stage_name, candidates=stage_candidates)
        staged_match = await _lookup_with_candidates(
            normalized_food_item,
            user_id,
            stage_candidates,
            descriptors=descriptors,
            brand=brand,
            fallback_search_query=fallback_search_query,
            prefer_usda_first=(stage_name == "corrected" and is_spelling_correction),
            strict_query_match=(stage_name == "corrected" and is_spelling_correction),
        )
        if staged_match:
            _log_resolution_step(
                "Lookup interval matched",
                stage=stage_name,
                food_name=staged_match.get("food_name") or normalized_food_item,
            )
            return staged_match

    _log_resolution_step("Lookup intervals exhausted", food_item=normalized_food_item)
    return None  # Food not found anywhere
