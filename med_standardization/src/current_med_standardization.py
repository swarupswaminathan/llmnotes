'''
Medication standardization script for current medication list processing.
Test run this script in med_standardization directory with: 
python -m src.current_med_standardization
'''

import json
from dataclasses import asdict
from typing import Dict, Any

from .parser import parse_medication_list, render_standardized_med
from .utils import sort_key


def standardize_medication_list(med_list: str, med_list_type: str) -> Dict[str, Any]:
    parsed = parse_medication_list(med_list, med_list_type)

    if len(parsed) == 1 and parsed[0].drug_name in {"None", "Unspecified"}:
        return {
            "input_type": med_list_type,
            "raw_input": med_list,
            "standardized_medication_list": parsed[0].drug_name,
            "parsed_items": [asdict(x) for x in parsed],
            "manual_review_required": False,
        }

    valid = [p for p in parsed if p.drug_name not in {None, "None", "Unspecified"}]
    valid = sorted(valid, key=sort_key)

    standardized_items = []
    seen = set()
    for item in valid:
        rendered = render_standardized_med(item)
        if rendered not in seen:
            standardized_items.append(rendered)
            seen.add(rendered)

    manual_review_required = any(
        p.confidence_flag in {"ambiguous", "unmapped"} for p in parsed
    )

    standardized_string = ", ".join(standardized_items) if standardized_items else "None"

    return {
        "input_type": med_list_type,
        "raw_input": med_list,
        "standardized_medication_list": standardized_string,
        "parsed_items": [asdict(x) for x in parsed],
        "manual_review_required": manual_review_required,
    }


# ============================================================
# Example usage
# ============================================================

if __name__ == "__main__":
    examples = [
        ("Lumigan QHS, Cosopt PF 2x daily, Alphagan 3x daily", "OD"),
        ("prednisolone 1% QID, lanatoprost once daily (well-tolerated)", "OS"),
        ("Diamox BID, prednisone daily x7 days, methazolamide 50 three times a day", "oral"),
        ("AST QID (laterality unknown), timolol BID", "OD"),
    ]

    for med_list, med_type in examples:
        result = standardize_medication_list(med_list, med_type)
        print(json.dumps(result, indent=2))
        print("-" * 80)