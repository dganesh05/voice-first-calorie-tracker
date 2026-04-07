import os
import re
import string
from typing import Any

import httpx
from dotenv import load_dotenv

from supabase_client import supabase

load_dotenv(override=True)


USDA_API_KEY = os.getenv("USDA_API_KEY")


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
    return {
        "food_name": record.get("food_name") or fallback_name,
        "calories": _to_number(record.get("calories", 0)),
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


def _descriptor_score(description: str, descriptors: list[str] | None) -> int:
    if not descriptors:
        return 0
    haystack = str(description or "").lower()
    return sum(1 for d in descriptors if str(d).lower() in haystack)


def _pick_usda_food(
    food_item: str,
    candidates: list[dict],
    brand: str | None = None,
    descriptors: list[str] | None = None,
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
            return max(
                branded_candidates,
                key=lambda f: _descriptor_score(f.get("description"), descriptors),
            )

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
        return foundation
    return max(candidates, key=lambda f: _descriptor_score(f.get("description"), descriptors))


async def fetch_from_usda(
    food_item: str,
    search_query: str | None = None,
    brand: str | None = None,
    descriptors: list[str] | None = None,
):
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
            _log_resolution_step(
                "USDA lookup failed",
                status_code=response.status_code,
                response_text=(response.text or "").strip()[:300],
            )
            return None

        foods = response.json().get("foods") or []
        food = _pick_usda_food(food_item, foods, brand=brand, descriptors=descriptors)
        if not food:
            _log_resolution_step("USDA lookup skipped", reason="no suitable USDA candidate selected")
            return None

        category = food.get("dataType") or food.get("foodCategory") or "USDA"
        _log_resolution_step(
            "USDA lookup matched",
            food_name=food.get("description") or food_item,
            category=category,
        )

        return {
            "food_name": food.get("description") or food_item,
            "calories": _extract_nutrient_value(food, ["energy"]),
            "protein": _extract_nutrient_value(food, ["protein"]),
            "carbs": _extract_nutrient_value(food, ["carbohydrate, by difference"]),
            "fat": _extract_nutrient_value(food, ["total lipid (fat)"]),
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

        if not candidates:
            return None
        return max(
            candidates,
            key=lambda rec: _match_score(food_item, rec) + _rank_candidate(rec, descriptors, brand),
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

        if not candidates:
            return None
        return max(
            candidates,
            key=lambda rec: _match_score(food_item, rec) + _rank_candidate(rec, descriptors, brand),
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

    # 1. Check Personal DB First
    _log_resolution_step("Tier 1 lookup started", tier="personal_foods")
    personal_match = _lookup_personal_food(
        normalized_food_item,
        user_id,
        descriptors=descriptors,
        brand=brand,
        fallback_search_query=fallback_search_query,
    )
    if personal_match:
        _log_resolution_step(
            "Tier 1 lookup matched",
            tier="personal_foods",
            food_name=personal_match.get("food_name") or normalized_food_item,
        )
        _log_resolution_step("Tier 2 lookup skipped", tier="global_foods", reason="personal match found")
        _log_resolution_step("Tier 3 lookup skipped", tier="USDA", reason="personal match found")
        return _normalize_food_record(personal_match, normalized_food_item)

    _log_resolution_step("Tier 1 lookup missed", tier="personal_foods")

    # 2. Check shared global cache
    _log_resolution_step("Tier 2 lookup started", tier="global_foods")
    cache_match = _lookup_global_food(
        normalized_food_item,
        descriptors=descriptors,
        brand=brand,
        fallback_search_query=fallback_search_query,
    )
    if cache_match:
        _log_resolution_step(
            "Tier 2 lookup matched",
            tier="global_foods",
            food_name=cache_match.get("food_name") or normalized_food_item,
        )
        _log_resolution_step("Tier 3 lookup skipped", tier="USDA", reason="global cache match found")
        return _normalize_food_record(cache_match, normalized_food_item)

    _log_resolution_step("Tier 2 lookup missed", tier="global_foods")

    # 3. Fallback to USDA API
    _log_resolution_step("Tier 3 lookup started", tier="USDA")
    usda_data = await fetch_from_usda(
        normalized_food_item,
        search_query=fallback_search_query,
        brand=brand,
        descriptors=descriptors,
    )

    if usda_data:
        # Save it to the cache so we never hit USDA for this exact item again.
        cache_record = {
            "food_name": usda_data.get("food_name", normalized_food_item),
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
            # Cache writes should never fail the user-facing lookup.
            _log_resolution_step(
                "USDA cache insert skipped",
                table="global_foods",
                reason="write failure or missing table",
            )
            pass
        return _normalize_food_record(usda_data, normalized_food_item)

    _log_resolution_step("Tier 3 lookup missed", tier="USDA")
    return None  # Food not found anywhere
