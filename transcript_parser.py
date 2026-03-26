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


def split_foods(query: str) -> list[str]:
    normalized = str(query or "")
    normalized = re.sub(r"\bwith\b", " and ", normalized)
    normalized = normalized.replace("&", " and ")

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

    match = re.match(r"^(\d+(?:\.\d+)?)\s+(.*)$", phrase)
    if match:
        quantity = float(match.group(1))
        food_name = match.group(2).strip()
        return quantity, food_name

    return 1.0, phrase


def parse_text_transcript(raw_input: str) -> list[dict[str, Any]]:
    cleaned = clean_transcript_input(raw_input)
    numerized = convert_number_words(cleaned)
    phrases = split_foods(numerized)

    parsed: list[dict[str, Any]] = []
    for phrase in phrases:
        quantity, food_name = parse_food_quantity(phrase)
        if not food_name:
            continue
        parsed.append(
            {
                "quantity": quantity,
                "food_name": food_name,
                "lookup_query": normalize_for_matching(food_name),
            }
        )

    return parsed
