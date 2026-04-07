#!/usr/bin/env python3
"""Parser normalization regression matrix.

Run from project root:
    python scripts/parser_matrix_test.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_parser import (
    _build_fallback_query,
    _normalize_food_name_and_unit,
    _sanitize_food_text,
    _split_compound_food,
)
from transcript_parser import parse_text_transcript


@dataclass(frozen=True)
class TranscriptCase:
    transcript: str
    expected: list[dict]


@dataclass(frozen=True)
class LlmNormalizationCase:
    food_name: str
    unit: str
    expected_food_name: str
    expected_unit: str


TRANSCRIPT_CASES: list[TranscriptCase] = [
    TranscriptCase(
        transcript="I had two eggs and a glass of whole milk",
        expected=[
            {"quantity": 2.0, "unit": "serving", "food_name": "eggs", "lookup_query": "eggs"},
            {
                "quantity": 1.0,
                "unit": "glass",
                "food_name": "whole milk",
                "lookup_query": "whole milk",
            },
        ],
    ),
    TranscriptCase(
        transcript="3 pieces of toast",
        expected=[
            {"quantity": 3.0, "unit": "piece", "food_name": "toast", "lookup_query": "toast"}
        ],
    ),
    TranscriptCase(
        transcript="1 slice of pizza",
        expected=[
            {"quantity": 1.0, "unit": "slice", "food_name": "pizza", "lookup_query": "pizza"}
        ],
    ),
    TranscriptCase(
        transcript="2x banana",
        expected=[
            {"quantity": 2.0, "unit": "serving", "food_name": "banana", "lookup_query": "banana"}
        ],
    ),
    TranscriptCase(
        transcript="I just ate one bowl of chicken noodle soup",
        expected=[
            {
                "quantity": 1.0,
                "unit": "bowl",
                "food_name": "chicken noodle soup",
                "lookup_query": "chicken noodle soup",
            }
        ],
    ),
    TranscriptCase(
        transcript="2% greek yogurt",
        expected=[
            {
                "quantity": 1.0,
                "unit": "serving",
                "food_name": "2% greek yogurt",
                "lookup_query": "2 greek yogurt",
            }
        ],
    ),
    TranscriptCase(
        transcript="Oreo, chips; and salsa",
        expected=[
            {"quantity": 1.0, "unit": "serving", "food_name": "oreo", "lookup_query": "oreo"},
            {"quantity": 1.0, "unit": "serving", "food_name": "chips", "lookup_query": "chips"},
            {"quantity": 1.0, "unit": "serving", "food_name": "salsa", "lookup_query": "salsa"},
        ],
    ),
    TranscriptCase(
        transcript="an apple and a banana",
        expected=[
            {"quantity": 1.0, "unit": "serving", "food_name": "apple", "lookup_query": "apple"},
            {"quantity": 1.0, "unit": "serving", "food_name": "banana", "lookup_query": "banana"},
        ],
    ),
    TranscriptCase(
        transcript="I had 4 oz chicken breast",
        expected=[
            {
                "quantity": 4.0,
                "unit": "oz",
                "food_name": "chicken breast",
                "lookup_query": "chicken breast",
            }
        ],
    ),
    TranscriptCase(
        transcript="2 glasses of orange juice",
        expected=[
            {
                "quantity": 2.0,
                "unit": "glass",
                "food_name": "orange juice",
                "lookup_query": "orange juice",
            }
        ],
    ),
]


LLM_CASES: list[LlmNormalizationCase] = [
    LlmNormalizationCase(
        food_name="piece of toast",
        unit="serving",
        expected_food_name="toast",
        expected_unit="piece",
    ),
    LlmNormalizationCase(
        food_name="slice pizza",
        unit="serving",
        expected_food_name="pizza",
        expected_unit="slice",
    ),
    LlmNormalizationCase(
        food_name="chobani greek yogurt!!!",
        unit="serving",
        expected_food_name="chobani greek yogurt",
        expected_unit="serving",
    ),
]


def _assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}\nExpected: {expected}\nActual:   {actual}")


def run_transcript_matrix() -> None:
    for index, case in enumerate(TRANSCRIPT_CASES, start=1):
        actual = parse_text_transcript(case.transcript)
        _assert_equal(
            actual,
            case.expected,
            f"[Transcript Case {index}] {case.transcript}",
        )


def run_llm_matrix() -> None:
    for index, case in enumerate(LLM_CASES, start=1):
        food_name, unit = _normalize_food_name_and_unit(case.food_name, case.unit)
        _assert_equal(
            (food_name, unit),
            (case.expected_food_name, case.expected_unit),
            f"[LLM Case {index}] normalize_food_name_and_unit",
        )

    fallback = _build_fallback_query(
        brand="Chobani",
        descriptors=["low-fat", "2%"],
        food_name="Greek Yogurt!!!",
    )
    _assert_equal(
        fallback,
        "chobani low fat 2% greek yogurt",
        "[LLM Case 4] fallback query punctuation cleanup",
    )

    cleaned = _sanitize_food_text("Taco-Bell® burrito!!!")
    _assert_equal(cleaned, "taco bell burrito", "[LLM Case 5] sanitize punctuation")

    toast_fallback = _build_fallback_query(
        brand=None,
        descriptors=[],
        food_name="toast",
    )
    _assert_equal(
        toast_fallback,
        "toast bread",
        "[LLM Case 6] source ingredient expansion for toast",
    )

    omelette_fallback = _build_fallback_query(
        brand=None,
        descriptors=["cheese"],
        food_name="omelette",
    )
    _assert_equal(
        omelette_fallback,
        "cheese omelette egg",
        "[LLM Case 7] source ingredient expansion for omelette",
    )

    alias_food_name, alias_unit = _normalize_food_name_and_unit("omlette", "serving")
    _assert_equal(
        (alias_food_name, alias_unit),
        ("omelette", "serving"),
        "[LLM Case 8] typo alias canonicalization omlette -> omelette",
    )

    split_foods = _split_compound_food("avocado toast")
    _assert_equal(
        split_foods,
        ["avocado", "toast"],
        "[LLM Case 9] compound split for avocado toast",
    )


def main() -> None:
    run_transcript_matrix()
    run_llm_matrix()
    total = len(TRANSCRIPT_CASES) + len(LLM_CASES) + 6
    print(f"PASS: parser matrix checks passed ({total} assertions)")


if __name__ == "__main__":
    main()
