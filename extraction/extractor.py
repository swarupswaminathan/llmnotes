"""
Single unified extractor driven entirely by cvar.

Lifted from notebook Cell 24; filtered to the four staged meds cvars.
"""

from __future__ import annotations

import json
import re
from typing import Any

# -- DataFrame ground-truth columns (four cvars only) -------------------------
CONFIG_TO_COLUMN: dict[str, list[str] | str] = {
    "oral_meds_staged": "Oral Meds",
    "oral_meds_change_staged": "Change in Oral Meds",
    "top_meds_change_staged": ["Change in Topical Treatment OD", "Change in Topical Treatment OS"],
    "top_meds_staged": ["Topical Meds OD", "Topical Meds OS"],
}

CVAR_OUTPUT_KEYS: dict[str, list[str]] = {
    "top_meds_change_staged": ["OD", "OS"],
    "top_meds_staged": ["OD", "OS"],
    "oral_meds_staged": ["Oral"],
    "oral_meds_change_staged": ["Oral"],
}

# No normalization maps needed for the four staged meds cvars.
NORMALIZATION_MAPS: dict[str, dict[str, str]] = {}


def is_bilateral(cvar: str) -> bool:
    """Return True if cvar is a bilateral (OD/OS) task."""
    return isinstance(CONFIG_TO_COLUMN.get(cvar), list)


def target_columns_for(cvar: str) -> list[str]:
    """Return DataFrame column(s) as a list for uniform iteration."""
    cols = CONFIG_TO_COLUMN.get(cvar, cvar)
    return cols if isinstance(cols, list) else [cols]


def output_keys_for(cvar: str) -> list[str]:
    """Return JSON keys the model produces for cvar."""
    return CVAR_OUTPUT_KEYS.get(cvar, [cvar])


def _failed_response(keys: list[str]) -> dict[str, str]:
    return {k: "None (failed)" for k in keys}


def _try_parse_json(text: str) -> tuple[dict, bool]:
    try:
        return json.loads(text), True
    except (json.JSONDecodeError, TypeError):
        return {}, False


def _extract_fields(text: str) -> dict[str, str]:
    return dict(re.findall(r'"(\w+)":\s*"([^"]*)"', text))


def _log_extraction_failure(text: str) -> None:
    print("No JSON content found in the response.")
    print(text)


def extract_json_content(text: str, cvar: str) -> tuple[dict, bool]:
    """Extract and parse JSON from a model response string.

    Strategy:
        1. Direct JSON parse
        2. Last {...} block
        3. Field-level regex if any expected key present
        4. Failed sentinel
    """
    keys = output_keys_for(cvar)
    failed = _failed_response(keys)

    if not text or not isinstance(text, str):
        return failed.copy(), False

    parsed, ok = _try_parse_json(text.strip())
    if ok:
        return parsed, True

    blocks = re.findall(r"\{.*?\}", text, re.DOTALL)
    if blocks:
        parsed, ok = _try_parse_json(blocks[-1])
        if ok:
            return parsed, True

    fields = _extract_fields(text)
    if any(fields.get(k) for k in keys):
        for k in keys:
            fields.setdefault(k, "None (failed)")
        return fields, True

    _log_extraction_failure(text)
    return failed.copy(), False


def normalize_value(value: Any, cvar: str | None = None) -> Any:
    """Normalise a label value using the map for cvar (no-op for staged meds)."""
    return NORMALIZATION_MAPS.get(cvar or "", {}).get(str(value).lower(), value)


def join_fields(*values: str | None) -> str | None:
    """Join non-empty string fields with a space, or return None if all empty."""
    return " ".join(v for v in values if v) or None
