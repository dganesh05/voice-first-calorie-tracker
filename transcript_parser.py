import re
import string
from typing import Any

NUMBER_WORD_MAP = {
    "zero": "0",
    "a": "1",
    "an": "1",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

FILLER_PHRASES = [
    "i ate",
    "i had",
    "i just ate",
    "for breakfast",
    "for lunch",
    "for dinner",
]

ARTICLES = {"a", "an", "the"}

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


def convert_number_words(text: str) -> str:
    words = str(text or "").split()
    converted = [NUMBER_WORD_MAP.get(word.lower(), word) for word in words]
    return " ".join(converted)


def clean_transcript_input(text: str) -> str:
    # Keep punctuation that may be meaningful in food names (e.g., 14", 2%).
    cleaned = str(text or "").lower()
    for phrase in FILLER_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_for_matching(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.translate(str.maketrans("", "", string.punctuation))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def sanitize_food_text(text: str) -> str:
    # Keep letters, numbers, spaces, percent, and apostrophes for USDA-friendly queries.
    value = str(text or "").lower()
    value = re.sub(r"[^a-z0-9%\s']+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_foods(query: str) -> list[str]:
    normalized = str(query or "")
    normalized = re.sub(r"\bwith\b", " and ", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[,;]", " and ", normalized)

    foods = [item.strip() for item in normalized.split(" and ") if item.strip()]

    cleaned: list[str] = []
    for food in foods:
        words = food.split()
        if words and words[0].lower() in ARTICLES:
            words = words[1:]
        cleaned_food = " ".join(words).strip()
        if cleaned_food:
            cleaned.append(cleaned_food)

    return cleaned


def parse_food_quantity(food_phrase: str) -> tuple[float, str]:
    phrase = str(food_phrase or "").strip()
    if not phrase:
        return 1.0, ""

    # Match explicit multiplier form first, e.g. "2x banana".
    times_match = re.match(r"^(\d+(?:\.\d+)?)\s*x\s+(.+)$", phrase)
    if times_match:
        quantity = float(times_match.group(1))
        food_name = times_match.group(2).strip()
        return quantity, food_name

    # Match standard quantity form, e.g. "2 eggs".
    # Requiring whitespace avoids misreading "2% yogurt" as quantity 2.
    qty_match = re.match(r"^(\d+(?:\.\d+)?)\s+(.+)$", phrase)
    if qty_match:
        quantity = float(qty_match.group(1))
        food_name = qty_match.group(2).strip()
        return quantity, food_name

    return 1.0, phrase


def split_unit_from_food(food_phrase: str) -> tuple[str, str]:
    phrase = sanitize_food_text(food_phrase)
    if not phrase:
        return "serving", ""

    # Example: "piece of toast" -> ("piece", "toast")
    of_match = re.match(r"^(\w+)\s+of\s+(.+)$", phrase)
    if of_match:
        unit = UNIT_ALIASES.get(of_match.group(1), "serving")
        food_name = of_match.group(2).strip()
        if food_name:
            return unit, food_name

    words = phrase.split()
    if words and words[0] in UNIT_ALIASES and len(words) > 1:
        return UNIT_ALIASES[words[0]], " ".join(words[1:]).strip()

    return "serving", phrase


def parse_text_transcript(raw_input: str) -> list[dict[str, Any]]:
    cleaned = clean_transcript_input(raw_input)
    numerized = convert_number_words(cleaned)
    phrases = split_foods(numerized)

    parsed: list[dict[str, Any]] = []
    for phrase in phrases:
        quantity, food_name = parse_food_quantity(phrase)
        unit, normalized_food_name = split_unit_from_food(food_name)
        if not normalized_food_name:
            continue
        parsed.append(
            {
                "quantity": quantity,
                "unit": unit,
                "food_name": normalized_food_name,
                "lookup_query": normalize_for_matching(normalized_food_name),
            }
        )

    return parsed
