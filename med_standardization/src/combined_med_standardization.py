'''
Unified interface for standardizing both current medication lists and medication change lists.
Test run this script in med_standardization directory with: 
python -m src.combined_med_standardization
'''

from typing import Dict, Any

from .current_med_standardization import standardize_medication_list
from .change_med_standardization import standardize_medication_change_list


VALID_MED_TYPES = {"OD", "OS", "oral"}
VALID_LABEL_TYPES = {"current", "change"}


def normalize_medication_type(medication_type: str) -> str:
    """
    Normalize user-facing medication type input to the values expected by the
    underlying scripts.

    Accepted:
      - "OD"
      - "OS"
      - "oral"
    """
    if not isinstance(medication_type, str):
        raise TypeError("medication_type must be a string")

    med_type = medication_type.strip()

    if med_type.lower() == "oral":
        return "oral"
    if med_type in {"OD", "OS"}:
        return med_type

    raise ValueError('medication_type must be one of: "OD", "OS", or "oral"')


def normalize_label_type(label_type: str) -> str:
    """
    Normalize label type input.

    Accepted:
      - "current"
      - "change"
    """
    if not isinstance(label_type, str):
        raise TypeError("label_type must be a string")

    normalized = label_type.strip().lower()
    if normalized not in VALID_LABEL_TYPES:
        raise ValueError('label_type must be either "current" or "change"')

    return normalized


def standardize_medication_label(
    medication_string: str,
    medication_type: str,
    label_type: str,
) -> Dict[str, Any]:
    """
    Route to the correct standardization script based on label_type.

    Args:
        medication_string: Raw medication label text
        medication_type: "OD", "OS", or "oral"
        label_type: "current" or "change"

    Returns:
        The dict returned by the underlying standardization script, with
        an extra "label_type" field added.
    """
    if not isinstance(medication_string, str):
        raise TypeError("medication_string must be a string")

    normalized_med_type = normalize_medication_type(medication_type)
    normalized_label_type = normalize_label_type(label_type)

    if normalized_label_type == "current":
        result = standardize_medication_list(
            med_list=medication_string,
            med_list_type=normalized_med_type,
        )
    else:  # "change"
        result = standardize_medication_change_list(
            med_list=medication_string,
            med_list_type=normalized_med_type,
        )

    result["label_type"] = normalized_label_type
    return result


if __name__ == "__main__":
    examples = [
        {
            "medication_string": "Lumigan QHS, Cosopt PF 2x daily",
            "medication_type": "OD",
            "label_type": "current",
        },
        {
            "medication_string": "Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily",
            "medication_type": "OD",
            "label_type": "change",
        },
        {
            "medication_string": "Diamox BID, prednisone daily x7 days",
            "medication_type": "oral",
            "label_type": "current",
        },
        {
            "medication_string": "Start Diamox 250 BID and Neptazane 50 BID",
            "medication_type": "oral",
            "label_type": "change",
        },
    ]

    import json

    for example in examples:
        output = standardize_medication_label(**example)
        print(json.dumps(output, indent=2))
        print("-" * 80)