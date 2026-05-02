"""
Pytest test file with logging for medication standardization script.
To run these tests, execute the following command from the root of the repository:
python -m pytest tests/test_med_current.py
"""

from unittest import result

import pytest
import logging
import json

from src.current_med_standardization import standardize_medication_list


# --------------------------------------------------
# Logging setup
# --------------------------------------------------

logger = logging.getLogger("med_standardizer_tests")
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler (persistent log)
file_handler = logging.FileHandler("test_med_standardizer.log")
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


def log_result(med_list, med_type, result):
    logger.info("--------------------------------------------------")
    logger.info(f"INPUT: {med_list} | TYPE: {med_type}")
    logger.info(f"OUTPUT: {result['standardized_medication_list']}")
    logger.debug("FULL RESULT:")
    logger.debug(json.dumps(result, indent=2))


# --------------------------------------------------
# Parametrized tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "med_list, med_list_type, expected",
    [
        (
            "Lumigan QHS, Cosopt PF 2x daily, Alphagan 3x daily",
            "OD",
            "bimatoprost QHS, brimonidine TID, dorzolamide/timolol PF BID",
        ),
        (
            "Xalatan daily",
            "OS",
            "latanoprost QHS",
        ),
        (
            "prednisolone 1% QID, lanatoprost once daily (well-tolerated)",
            "OS",
            "latanoprost QHS, prednisolone QID",
        ),
        (
            "AST QID (laterality unknown), timolol BID",
            "OD",
            "autologous serum tears QID (laterality unknown), timolol BID",
        ),
        (
            "travoprost once daily, dorzolamide BID",
            "OS",
            "dorzolamide BID, travoprost QHS",
        ),
        (
            "brimonidine BID BID (well-tolerated per patient), timolol 0.5% 0.5% BID",
            "OD",
            "brimonidine BID, timolol 0.5% BID",
        ),
        (
            "Systane BID, Refresh QID",
            "OS",
            "None",
        ),
        (
            "brimonidine BID, Refresh QID",
            "OS",
            "brimonidine BID",
        ),
        (
            "None",
            "OD",
            "None",
        ),
        (
            "Unspecified",
            "OS",
            "Unspecified",
        ),
        (
            "Diamox 250mg mg BID PO",
            "oral",
            "acetazolamide 250mg BID",
        ),
        (
            "methazolamide 50 three times a day",
            "oral",
            "methazolamide 50mg TID",
        ),
        (
            "acetazolamide 250mg BID with food",
            "oral",
            "acetazolamide 250mg BID",
        ),
        (
            "Neptazane 50mg BID, Diamox 500mg daily",
            "oral",
            "acetazolamide 500mg daily, methazolamide 50mg BID",
        ),
        (
            "acetazolamide BID (unknown dose) 2x daily",
            "oral",
            "acetazolamide BID",
        ),
        (
            "methazolamide (unknown dose) (unknown frequency)",
            "oral",
            "methazolamide",
        ),
        (
            "None",
            "oral",
            "None",
        ),
        (
            "Unspecified",
            "oral",
            "Unspecified",
        ),
    ],
)
def test_standardized_output(med_list, med_list_type, expected):
    result = standardize_medication_list(med_list, med_list_type)

    log_result(med_list, med_list_type, result)

    assert result["standardized_medication_list"] == expected

@pytest.mark.parametrize(
    "med_list, expected",
    [
        ("timolol/dorzolamide BID", "dorzolamide/timolol BID"),
        ("dorzolamide-timolol BID", "dorzolamide/timolol BID"),
        ("brinzolamide/brimonidine TID", "brimonidine/brinzolamide TID"),
        ("netarsudil/latanoprost QHS", "latanoprost/netarsudil QHS"),
        ("Combigan BID", "brimonidine/timolol BID"),
        ("Cosopt PF BID", "dorzolamide/timolol PF BID"),
    ],
)
def test_combination_drop_generic_ordering(med_list, expected):
    result = standardize_medication_list(med_list, "OD")

    log_result(med_list, "OD", result)

    assert result["standardized_medication_list"] == expected

# --------------------------------------------------
# Edge cases
# --------------------------------------------------

def test_manual_review_flag_for_unmapped_or_ambiguous():
    med_list = "zzzzdrug BID"
    result = standardize_medication_list(med_list, "oral")

    log_result(med_list, "oral", result)

    assert result["manual_review_required"] is True
    assert any(
        item["confidence_flag"] in {"ambiguous", "unmapped"}
        for item in result["parsed_items"]
    )


def test_eye_type_sets_laterality_from_input():
    result = standardize_medication_list("Lumigan QHS", "OD")

    log_result("Lumigan QHS", "OD", result)

    assert result["parsed_items"][0]["laterality"] == "OD"


def test_oral_type_sets_laterality_not_applicable():
    result = standardize_medication_list("Diamox BID", "oral")

    log_result("Diamox BID", "oral", result)

    assert result["parsed_items"][0]["laterality"] == "not_applicable"


def test_pf_suffix_position():
    result = standardize_medication_list("PF timolol BID", "OD")

    log_result("PF timolol BID", "OD", result)

    assert result["standardized_medication_list"] == "timolol PF BID"


def test_prednisolone_percentage_removed():
    result = standardize_medication_list("prednisolone 1% QID", "OS")

    log_result("prednisolone 1% QID", "OS", result)

    assert result["standardized_medication_list"] == "prednisolone QID"


def test_non_prednisolone_percentage_retained():
    result = standardize_medication_list("pilocarpine 1% QID", "OD")

    log_result("pilocarpine 1% QID", "OD", result)

    assert result["standardized_medication_list"] == "pilocarpine 1% QID"

def test_nonessential_word_removed_current():
    result = standardize_medication_list("generic Cosopt BID", "OD")
    assert result["standardized_medication_list"] == "dorzolamide/timolol BID"

def test_duration_for_phrase_current():
    result = standardize_medication_list(
        "brimonidine/timolol (Combigan) BID for 2 weeks",
        "OD",
    )
    assert result["standardized_medication_list"] == "brimonidine/timolol BID x2 weeks"


def test_invalid_type_raises():
    with pytest.raises(ValueError):
        standardize_medication_list("Lumigan QHS", "OU")