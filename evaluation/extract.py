"""Pull drug names, frequencies, and change phrases from med cells or JSON.

Prefers structured JSON (``parsed_items``) when available; falls back to
``standardize_medication_list`` on the raw text cell. Oral paths omit doses.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from standardization.src.current_med_standardization import (
    standardize_medication_list,
)


def extract_drug_names_only(cell_value: Any, eye: str) -> list[str]:
    """Extract sorted unique drug names from a free-text medication cell."""
    if isinstance(cell_value, list):
        items = [
            str(i)
            for i in cell_value
            if str(i).strip().lower() not in ["no", "none", "nan", ""]
        ]
        if not items:
            return ["no"]
        cell_value = ", ".join(items)

    try:
        if pd.isna(cell_value):
            return ["no"]
    except (ValueError, TypeError):
        pass

    if str(cell_value).strip().lower() in ["", "no", "none", "nan"]:
        return ["no"]

    result = standardize_medication_list(str(cell_value), eye)

    if result["standardized_medication_list"] in {"Unspecified", "unspecified"}:
        return ["unspecified"]

    drug_names: list[str] = []
    seen: set[str] = set()
    for item in result["parsed_items"]:
        drug = item.get("drug_name")
        if drug and drug not in {None, "None"}:
            drug_lower = drug.lower().strip()
            if drug_lower == "unspecified":
                drug_names.append("unspecified")
            elif drug_lower not in seen:
                drug_names.append(drug_lower)
            seen.add(drug_lower)

    return sorted(drug_names) if drug_names else ["no"]


def extract_from_json_topical(
    json_val: Any, change: bool = False
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Parse topical med JSON into (drugs, frequencies, change_phrases).

    Returns ``(None, None, None)`` on parse failure so the caller can fall back.
    """
    if pd.isna(json_val) or str(json_val).strip().lower() in ["", "none", "nan"]:
        return ["no"], ["no"], ["no"]

    try:
        items = json.loads(json_val) if isinstance(json_val, str) else json_val
        if not isinstance(items, list) or len(items) == 0:
            return ["no"], ["no"], ["no"]

        drug_names: list[str] = []
        frequencies: list[str] = []
        terms: list[str] = []
        seen: set[str] = set()

        for item in items:
            drug = item.get("drug_name")
            freq = item.get("frequency")
            term = item.get("change_phrase") if change else None

            if drug and str(drug).lower() not in {"none", "nan", "unspecified"}:
                drug_lower = drug.lower().strip()
                if drug_lower not in seen:
                    drug_names.append(drug_lower)
                    frequencies.append(
                        freq.lower().strip() if freq else "unspecified"
                    )
                    terms.append(term.lower().strip() if term else "unspecified")
                seen.add(drug_lower)

        return (
            sorted(drug_names) if drug_names else ["no"],
            frequencies if frequencies else ["no"],
            terms if terms else ["no"],
        )

    except (json.JSONDecodeError, AttributeError, TypeError):
        return None, None, None


def extract_from_json_oral(
    json_val: Any, change: bool = False
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Parse oral med JSON into (drugs, frequencies, change_terms); doses omitted."""
    if pd.isna(json_val) or str(json_val).strip().lower() in ["", "none", "nan"]:
        return ["no"], ["no"], ["no"]

    try:
        items = json.loads(json_val) if isinstance(json_val, str) else json_val
        if not isinstance(items, list) or len(items) == 0:
            return ["no"], ["no"], ["no"]

        drug_names: list[str] = []
        frequencies: list[str] = []
        terms: list[str] = []
        seen: set[str] = set()

        for item in items:
            drug = item.get("drug_name")
            freq = item.get("frequency")
            term = item.get("change_phrase") if change else None

            if drug and str(drug).lower() not in {"none", "nan", "unspecified"}:
                drug_lower = drug.lower().strip()
                if drug_lower not in seen:
                    drug_names.append(drug_lower)
                    frequencies.append(
                        freq.lower().strip() if freq else "unspecified"
                    )
                    terms.append(term.lower().strip() if term else "unspecified")
                seen.add(drug_lower)

        return (
            sorted(drug_names) if drug_names else ["no"],
            frequencies if frequencies else ["no"],
            terms if terms else ["no"],
        )

    except (json.JSONDecodeError, AttributeError, TypeError):
        return None, None, None


def get_drugs_freqs_terms_topical(
    json_val: Any, raw_val: Any, eye: str, change: bool = False
) -> tuple[Any, Any, Any]:
    """Prefer topical JSON; fall back to standardizing the raw text cell."""
    drug_names, frequencies, terms = extract_from_json_topical(
        json_val, change=change
    )
    if drug_names is None:
        drug_names = extract_drug_names_only(raw_val, eye)
        frequencies = terms = None
    return drug_names, frequencies, terms


def get_drugs_freqs_terms_oral(
    json_val: Any, raw_val: Any, eye: str = "oral", change: bool = False
) -> tuple[Any, Any, Any]:
    """Prefer oral JSON; fall back with ``eye='oral'`` (no doses)."""
    drug_names, frequencies, terms = extract_from_json_oral(
        json_val, change=change
    )
    if drug_names is None:
        drug_names = extract_drug_names_only(raw_val, eye)
        frequencies = terms = None
    return drug_names, frequencies, terms
