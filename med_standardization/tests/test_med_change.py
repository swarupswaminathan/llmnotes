'''
Pytest test file for medication change standardization script.
To run these tests, execute the following command from the root of the repository:
python -m pytest tests/test_med_change.py
'''


import pytest
import logging
import json

from src.change_med_standardization import standardize_medication_change_list


# --------------------------------------------------
# Logging setup
# --------------------------------------------------

logger = logging.getLogger("med_change_standardizer_tests")
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler (persistent log)
file_handler = logging.FileHandler("test_med_change_standardizer.log")
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
    logger.info(f"OUTPUT: {result['standardized_medication_change_list']}")
    logger.debug("FULL RESULT:")
    logger.debug(json.dumps(result, indent=2))



# --------------------------------------------------
# Parametrized tests
# --------------------------------------------------


@pytest.mark.parametrize(
    "med_list, med_type, expected",
    [
        # S1 Typo and duplication correction
        (
            "Start brimonodine BID BID",
            "OD",
            "Start brimonidine BID",
        ),

        # S2 Remove extra verbiage
        (
            "Start brimonidine BID (well-tolerated)",
            "OD",
            "Start brimonidine BID",
        ),
        (
            "Start Lumigan QHS for IOP control",
            "OD",
            "Start bimatoprost QHS",
        ),
        (
            "Stop timolol due to bradycardia",
            "OD",
            "Stop timolol",
        ),

        # S3 Unknown laterality placeholdrs
        (
            "Start brimonidine BID (laterality unknown)",
            "OD",
            "Start brimonidine BID (laterality unknown)",
        ),

        # S4 Brand -> generic, sorting by change phrase priority: Start, Stop, Increase, Decrease
        (
            "Stop Alphagan, Start Cosopt TID",
            "OS",
            "Start dorzolamide/timolol TID, Stop brimonidine",
        ),

        # remove "increase to" phrasing
        (
            "Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily",
            "OD",
            "Start bimatoprost QHS, Stop brimonidine, Increase dorzolamide/timolol TID",
        ),

        # S5 Extended release
        (
            "Start metipranolol XR",
            "OD",
            "Start metipranolol XE",
        ),
        (
            "Increase timolol XE BID",
            "OD",
            "Increase timolol XE BID",
        ),

        # S6 Combination drug generic odering
        (
            "Start Cosopt BID, Stop Combigan",
            "OD",
            "Start dorzolamide/timolol BID, Stop brimonidine/timolol",
        ),
        (
            "Start timolol/dorzolamide BID",
            "OD",
            "Start dorzolamide/timolol BID",
        ),

        # S7 remove artificial tears 
        (
            "Start Refresh QID",
            "OD",
            "None",
        ),
        (
            "Stop Refresh QID, Increase timolol BID",
            "OD",
            "Increase timolol BID",
        ),

        # S8 PF suffix
        (
            "Start PF timolol BID",
            "OD",
            "Start timolol PF BID",
        ),
        (
            "Increase timolol PF BID",
            "OD",
            "Increase timolol PF BID",
        ),

        # PF retained for combo drops after generic conversion
        (
            "Start Cosopt PF 2x daily",
            "OD",
            "Start dorzolamide/timolol PF BID",
        ),

        # S9 autologous serum tears standardization + laterality unknown retained
        (
            "Start AST QID (laterality unknown)",
            "OS",
            "Start autologous serum tears QID (laterality unknown)",
        ),
        (
            "Start autologous serum eye drops QID",
            "OS",
            "Start autologous serum tears QID",
        ),
        (
            "Start serum tears BID",
            "OD",
            "Start autologous serum tears BID",
        ),

        # S10 prednisolone and atropine percentage removal
        (
            "Start prednisolone 0.12% QID",
            "OD",
            "Start prednisolone QID",
        ),
        (
            "Start Pred Forte 1% 4x daily",
            "OD",
            "Start prednisolone QID",
        ),
        (
            "Start atropine 1% BID",
            "OS",
            "Start atropine BID",
        ),
        (
            "Increase pilocarpine 1% QID",
            "OD",
            "Increase pilocarpine 1% QID",
        ),

        # S11 Frequency standarization
        (
            "Start brimonidine 2x daily, Start timolol daily, Start latanoprost nightly, Start prednisolone 4x daily x14 days",
            "OD",
            "Start brimonidine BID, Start latanoprost QHS, Start prednisolone QID x14 days, Start timolol daily",
        ),

        # S12 prostaglandin daily -> QHS
        (
            "Start travoprost once daily",
            "OD",
            "Start travoprost QHS",
        ),

        # S13 none handling
        ("None", "OD", "None"),
        ("no medication changes", "OS", "None"),
        ("n/a", "oral", "None"),        

        # Stop entries should not keep frequency
        (
            "Stop timolol BID",
            "OD",
            "Stop timolol",
        ),
        (
            "Stop Diamox 500mg daily",
            "oral",
            "Stop acetazolamide 500mg",
        ),

        # Split same action across two topical meds
        (
            "Start Xalatan and Alphagan TID",
            "OD",
            "Start brimonidine TID, Start latanoprost TID",
        ),

        # Split same action across two oral meds
        (
            "Start Diamox 250 BID and Neptazane 50 BID",
            "oral",
            "Start acetazolamide 250mg BID, Start methazolamide 50mg BID",
        ),

        # "or" truncation rule
        (
            "Start Xalatan or Lumigan",
            "OD",
            "Start latanoprost",
        ),

        # Oral typo correction + mg insertion + frequency standardization
        (
            "Increase Diamx 250 three times a day",
            "oral",
            "Increase acetazolamide 250mg TID",
        ),

        # Oral extra verbiage removal
        (
            "Start Diamox 250mg BID with food",
            "oral",
            "Start acetazolamide 250mg BID",
        ),

        # Unknown dose retained
        (
            "Start methazolamide (unknown dose) BID",
            "oral",
            "Start methazolamide BID",
        ),

        # Unknown frequency retained
        (
            "Start acetazolamide 250mg (unknown frequency)",
            "oral",
            "Start acetazolamide 250mg",
        ),

        # Unknown dose + unknown frequency retained
        (
            "Start methazolamide (unknown dose) (unknown frequency)",
            "oral",
            "Start methazolamide",
        ),

        # Change phrase ordering + alphabetical ordering within same change phrase
        (
            "Decrease Trusopt BID, Decrease brimonidine BID, Start timolol daily",
            "OD",
            "Start timolol daily, Decrease brimonidine BID, Decrease dorzolamide BID",
        ),

        # Duplicate rendered items are deduped in final output
        (
            "Start timolol BID, Start timolol BID",
            "OS",
            "Start timolol BID",
        ),

        # Switch phrasing handling
        (
            "Switch timolol BID to Cosopt BID",
            "OD",
            "Start dorzolamide/timolol BID, Stop timolol",
        ),
    ],
)
def test_standardized_change_output(med_list, med_type, expected):
    result = standardize_medication_change_list(med_list, med_type)

    log_result(med_list, med_type, result)

    assert result["standardized_medication_change_list"] == expected

@pytest.mark.parametrize(
    "med_list, expected",
    [
        ("Add timolol BID", "Start timolol BID"),
        ("Begin timolol BID", "Start timolol BID"),
        ("Discontinue timolol", "Stop timolol"),
        ("DC timolol", "Stop timolol"),
        ("Reduce timolol to daily", "Decrease timolol daily"),
        ("Lower timolol BID", "Decrease timolol BID"),
    ],
)
def test_change_phrase_synonyms(med_list, expected):
    result = standardize_medication_change_list(med_list, "OD")
    assert result["standardized_medication_change_list"] == expected

@pytest.mark.parametrize(
    "med_list, med_type",
    [
        ("Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily", "OD"),
        ("Start AST QID (laterality unknown), Increase timolol BID", "OS"),
        ("Start Diamox 250 BID and Neptazane 50 BID", "oral"),
    ],
)
def test_returns_expected_top_level_keys(med_list, med_type):
    result = standardize_medication_change_list(med_list, med_type)

    log_result(med_list, med_type, result)

    assert "input_type" in result
    assert "raw_input" in result
    assert "standardized_medication_change_list" in result
    assert "parsed_items" in result
    assert "manual_review_required" in result


@pytest.mark.parametrize(
    "med_list, med_type, expected_manual_review",
    [
        ("Start Lumigan nightly", "OD", False),
        ("Stop Diamox 500mg daily", "oral", False),
    ],
)
def test_manual_review_flag_clean_cases(med_list, med_type, expected_manual_review):
    result = standardize_medication_change_list(med_list, med_type)

    log_result(med_list, med_type, result)

    assert result["manual_review_required"] is expected_manual_review


def test_period_delimiter_between_change_clauses():
    result = standardize_medication_change_list(
        "Increase Azopt to TID. Start Alphagan P BID",
        "OD",
    )
    assert result["standardized_medication_change_list"] == (
        "Start brimonidine BID, Increase brinzolamide TID"
    )

def test_period_delimiter_does_not_break_percentage():
    result = standardize_medication_change_list(
        "Start prednisolone 0.5% QID. Stop timolol",
        "OD",
    )
    assert result["standardized_medication_change_list"] == (
        "Start prednisolone QID, Stop timolol"
    )

def test_parsed_items_count_after_split():
    result = standardize_medication_change_list("Start Xalatan and Alphagan TID", "OD")

    log_result("Start Xalatan and Alphagan TID", "OD", result)

    assert len(result["parsed_items"]) == 2


def test_invalid_medication_type_raises_value_error():
    with pytest.raises(ValueError, match="med_list_type must be one of"):
        standardize_medication_change_list("Start timolol BID", "OU")