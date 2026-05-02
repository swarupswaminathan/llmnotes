'''
Standardize free-text medication change lists into a consistent format.
Test run this script in med_standardization directory with: 
python -m src.change_med_standardization
'''

import json
from dataclasses import asdict
from typing import Dict, Any

from .parser import parse_medication_change_list, render_standardized_change
from .utils import sort_key_change


def standardize_medication_change_list(med_list: str, med_list_type: str) -> Dict[str, Any]:
    parsed = parse_medication_change_list(med_list, med_list_type)

    if len(parsed) == 1 and parsed[0].drug_name in {"None", "Unspecified"}:
        return {
            "input_type": med_list_type,
            "raw_input": med_list,
            "standardized_medication_change_list": parsed[0].drug_name,
            "parsed_items": [asdict(x) for x in parsed],
            "manual_review_required": False,
        }

    valid = [p for p in parsed if p.drug_name not in {None, "None", "Unspecified"}]
    valid = sorted(valid, key=sort_key_change)

    standardized_items = []
    seen = set()
    for item in valid:
        rendered = render_standardized_change(item)
        if rendered not in seen:
            standardized_items.append(rendered)
            seen.add(rendered)

    standardized_string = ", ".join(standardized_items) if standardized_items else "None"

    manual_review_required = any(
        p.confidence_flag in {"ambiguous", "unmapped"} for p in parsed
    )

    return {
        "input_type": med_list_type,
        "raw_input": med_list,
        "standardized_medication_change_list": standardized_string,
        "parsed_items": [asdict(x) for x in parsed],
        "manual_review_required": manual_review_required,
    }


# ============================================================
# Example usage
# ============================================================

if __name__ == "__main__":
    examples = [
        ("Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily", "OD"),
        ("Start AST QID (laterality unknown), Increase timolol BID", "OS"),
        ("Start Xalatan and Alphagan TID", "OD"),
        ("Start Rhopressa QHS", "OS"),

    ]

    for med_list, med_type in examples:
        result = standardize_medication_change_list(med_list, med_type)
        print(json.dumps(result, indent=2))
        print("-" * 80)