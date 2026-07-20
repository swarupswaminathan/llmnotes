"""
Read an Excel sheet containing current and/or change medication labels,
standardize selected columns, and write results to a new Excel file.

Example:
python run.py \
    --input data.xlsx \
    --output data_standardized.xlsx \
    --current-od-col current_od \
    --current-os-col current_os \
    --current-oral-col current_oral \
    --change-od-col change_od \
    --change-os-col change_os \
    --change-oral-col change_oral

Example:
python run.py \
    --input train_data.xlsx \
    --output train_data_standardized.xlsx \
    --current-od-col "Topical Meds OD" \
    --current-os-col "Topical Meds OS" \
    --current-oral-col "Oral Meds" \
    --change-od-col "Change in Topical Treatment OD" \
    --change-os-col "Change in Topical Treatment OS" \
    --change-oral-col "Change in Oral Meds" 
    
Example:
python run.py \
    --input val_data.xlsx \
    --output val_data_standardized.xlsx \
    --current-od-col "Topical Meds OD" \
    --current-os-col "Topical Meds OS" \
    --current-oral-col "Oral Meds" \
    --change-od-col "Change in Topical Treatment OD" \
    --change-os-col "Change in Topical Treatment OS" \
    --change-oral-col "Change in Oral Meds" \
    --current-topical-col-json "GPT Topical Meds_gtms" "Claude Topical Meds_ctms" \
    --current-oral-col-json "GPT Oral Meds_goms" "Claude Oral Meds_coms" \
    --change-topical-col-json "GPT Topical Meds Change_gtmcs" "Claude Topical Meds Change_ctmcs" \
    --change-oral-col-json "GPT Oral Meds Change_gomcs" "Claude Oral Meds Change_comcs" 
   

python run.py \
    --input val_data_standardized_tmp.xlsx \
    --output val_data_standardized_v3.xlsx \
    --current-topical-col-json "Claude Topical Meds_ctms" \
    --current-oral-col-json "Claude Oral Meds_coms" \
    --change-topical-col-json "Claude Topical Meds Change_ctmcs" \
    --change-oral-col-json "Claude Oral Meds Change_comcs" 


python run.py \
    --input adjudicated_meds_last_final.xlsx \
    --output adjudicated_med_last_final_standardized.xlsx \
    --current-od-col "Topical Meds OD" \
    --current-os-col "Topical Meds OS" \
    --current-oral-col "Oral Meds" \
    --change-od-col "Change in Topical Treatment OD" \
    --change-os-col "Change in Topical Treatment OS" \
    --change-oral-col "Change in Oral Meds"

# Grading-results convenience mode (inference → evaluation bridge):
# Input:  .../grading_results_{cvar}.xlsx
# Output: .../grading_results_{acronym}_standardized.xlsx  (same directory)
# Column names match evaluation/column_map.py (AI_Diagnosis__standardized_*).
python run.py \
    --grading-results \
    --input results/oral_meds_staged/.../grading_results_oral_meds_staged.xlsx
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd

from src.combined_med_standardization import standardize_medication_label
from src.current_med_standardization import standardize_medication_list
from src.change_med_standardization import standardize_medication_change_list


# ---------------------------------------------------------------------------
# Grading-results mode — aligned with evaluation/column_map.py
# ---------------------------------------------------------------------------
# Output basename: grading_results_{acronym}_standardized.xlsx
# Standardized AI_Diagnosis columns use the same suffixes the evaluation
# FILE_COLUMN_MAP expects (…_output, …_failed_match, …_parsed_items).

@dataclass(frozen=True)
class GradingCvarSpec:
    cvar: str
    acronym: str
    json_kind: str  # "topical" | "oral"
    label_type: str  # "current" | "change"


# Keep in sync with evaluation.column_map.CVAR_TO_ACRONYM / TOPICAL/CHANGE sets.
GRADING_CVAR_SPECS: dict[str, GradingCvarSpec] = {
    "top_meds_staged": GradingCvarSpec(
        "top_meds_staged", "tms", "topical", "current"
    ),
    "top_meds_change_staged": GradingCvarSpec(
        "top_meds_change_staged", "tmcs", "topical", "change"
    ),
    "oral_meds_staged": GradingCvarSpec(
        "oral_meds_staged", "oms", "oral", "current"
    ),
    "oral_meds_change_staged": GradingCvarSpec(
        "oral_meds_change_staged", "omcs", "oral", "change"
    ),
}

GRADING_ACRONYM_TO_CVAR: dict[str, str] = {
    spec.acronym: cvar for cvar, spec in GRADING_CVAR_SPECS.items()
}

GRADING_AI_DIAGNOSIS_COL = "AI_Diagnosis"

# --------------------------------------------------
# Logging setup
# --------------------------------------------------

logger = logging.getLogger("med_excel_standardizer")
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# --------------------------------------------------
# Column config
# --------------------------------------------------

PLAIN_COLUMN_SPECS = {
    "current_od_col": {"med_type": "OD", "label_type": "current"},
    "current_os_col": {"med_type": "OS", "label_type": "current"},
    "current_oral_col": {"med_type": "oral", "label_type": "current"},
    "change_od_col": {"med_type": "OD", "label_type": "change"},
    "change_os_col": {"med_type": "OS", "label_type": "change"},
    "change_oral_col": {"med_type": "oral", "label_type": "change"},
}

JSON_COLUMN_SPECS = {
    "current_oral_col_json": {"json_kind": "oral", "label_type": "current"},
    "change_oral_col_json": {"json_kind": "oral", "label_type": "change"},
    "current_topical_col_json": {"json_kind": "topical", "label_type": "current"},
    "change_topical_col_json": {"json_kind": "topical", "label_type": "change"},
}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standardize medication-label columns from an Excel file."
    )

    parser.add_argument("--input", required=True, help="Path to input Excel file.")
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Path to output Excel file. Required for the general column mode; "
            "optional with --grading-results (defaults to "
            "grading_results_{acronym}_standardized.xlsx beside the input)."
        ),
    )
    parser.add_argument(
        "--sheet-name",
        default=0,
        help="Sheet name or index to read from the input workbook. Default: 0",
    )

    parser.add_argument(
        "--grading-results",
        action="store_true",
        help=(
            "Convenience mode for inference outputs: take "
            "grading_results_{cvar}.xlsx (or grading_results_{acronym}.xlsx), "
            "standardize the AI_Diagnosis JSON column for that cvar, and write "
            "grading_results_{acronym}_standardized.xlsx in the same directory. "
            "Column names match evaluation/column_map.py. "
            "Does not require --*-col arguments."
        ),
    )
    parser.add_argument(
        "--cvar",
        default=None,
        choices=sorted(GRADING_CVAR_SPECS),
        help=(
            "Optional cvar override for --grading-results "
            "(otherwise inferred from the input filename)."
        ),
    )
    parser.add_argument(
        "--acronym",
        default=None,
        choices=sorted(GRADING_ACRONYM_TO_CVAR),
        help=(
            "Optional acronym override for --grading-results "
            "(tms/tmcs/oms/omcs; otherwise inferred from the input filename)."
        ),
    )

    # plain text columns
    parser.add_argument("--current-od-col", dest="current_od_col", nargs="+", help="Column name for current OD medications.")
    parser.add_argument("--current-os-col", dest="current_os_col", nargs="+", help="Column name for current OS medications.")
    parser.add_argument("--current-oral-col", dest="current_oral_col", nargs="+", help="Column name for current oral medications.")
    parser.add_argument("--change-od-col", dest="change_od_col", nargs="+", help="Column name for change OD medications.")
    parser.add_argument("--change-os-col", dest="change_os_col", nargs="+", help="Column name for change OS medications.")
    parser.add_argument("--change-oral-col", dest="change_oral_col", nargs="+", help="Column name for change oral medications.")

    # JSON columns
    parser.add_argument("--current-oral-col-json", dest="current_oral_col_json", nargs="+", help="Column name for current oral medications stored as JSON.")
    parser.add_argument("--change-oral-col-json", dest="change_oral_col_json", nargs="+", help="Column name for change oral medications stored as JSON.")
    parser.add_argument("--current-topical-col-json", dest="current_topical_col_json", nargs="+", help="Column name for current topical medications stored as JSON with OD and OS keys.")
    parser.add_argument("--change-topical-col-json", dest="change_topical_col_json", nargs="+", help="Column name for change topical medications stored as JSON with OD and OS keys.")

    parser.add_argument(
        "--use-combined-wrapper",
        action="store_true",
        help=(
            "Use standardize_medication_label(...) for all routed calls. "
            "Default behavior calls current/change functions directly."
        ),
    )

    return parser.parse_args()


def resolve_grading_spec(
    input_path: Path,
    *,
    cvar: str | None = None,
    acronym: str | None = None,
) -> GradingCvarSpec:
    """Resolve cvar/acronym for grading-results mode from CLI and/or filename.

    Accepts basenames:
      grading_results_{cvar}.xlsx
      grading_results_{acronym}.xlsx
    Rejects already-standardized names (*_standardized.xlsx).
    """
    basename = input_path.name
    match = re.fullmatch(
        r"grading_results_(.+)\.xlsx", basename, flags=re.IGNORECASE
    )
    if not match:
        raise ValueError(
            f"Expected input basename grading_results_<cvar|acronym>.xlsx, "
            f"got {basename!r}"
        )
    token = match.group(1)
    if token.lower().endswith("_standardized") or token.lower().endswith(
        "standardized"
    ):
        raise ValueError(
            f"Input looks already standardized ({basename!r}). "
            "Pass the raw grading_results_{cvar}.xlsx from inference."
        )

    if cvar and acronym:
        if GRADING_CVAR_SPECS[cvar].acronym != acronym:
            raise ValueError(
                f"--cvar {cvar!r} and --acronym {acronym!r} disagree "
                f"(expected acronym {GRADING_CVAR_SPECS[cvar].acronym!r})"
            )
    elif cvar:
        acronym = GRADING_CVAR_SPECS[cvar].acronym
    elif acronym:
        cvar = GRADING_ACRONYM_TO_CVAR[acronym]
    else:
        if token in GRADING_CVAR_SPECS:
            cvar = token
            acronym = GRADING_CVAR_SPECS[cvar].acronym
        elif token in GRADING_ACRONYM_TO_CVAR:
            acronym = token
            cvar = GRADING_ACRONYM_TO_CVAR[acronym]
        else:
            raise ValueError(
                f"Cannot infer cvar/acronym from {basename!r}. "
                f"Expected cvar in {sorted(GRADING_CVAR_SPECS)} or "
                f"acronym in {sorted(GRADING_ACRONYM_TO_CVAR)}, "
                "or pass --cvar / --acronym."
            )

    assert cvar is not None
    return GRADING_CVAR_SPECS[cvar]


def default_grading_output_path(input_path: Path, acronym: str) -> Path:
    """Same directory as input: grading_results_{acronym}_standardized.xlsx."""
    return input_path.parent / f"grading_results_{acronym}_standardized.xlsx"


def run_grading_results_standardization(
    input_path: Path,
    *,
    output_path: Path | None = None,
    sheet_name: Any = 0,
    cvar: str | None = None,
    acronym: str | None = None,
    use_combined_wrapper: bool = False,
) -> Path:
    """Standardize inference ``grading_results_{cvar}.xlsx`` for evaluation.

    Only the ``AI_Diagnosis`` JSON prediction column is standardized (gold
    target columns are merged later by evaluate.py from the adjudicated file).
    """
    spec = resolve_grading_spec(input_path, cvar=cvar, acronym=acronym)
    if output_path is None:
        output_path = default_grading_output_path(input_path, spec.acronym)

    logger.info(
        "Grading-results mode: cvar=%s acronym=%s json_kind=%s label_type=%s",
        spec.cvar,
        spec.acronym,
        spec.json_kind,
        spec.label_type,
    )
    logger.info("Reading input workbook: %s", input_path)
    df = pd.read_excel(input_path, sheet_name=sheet_name)

    if GRADING_AI_DIAGNOSIS_COL not in df.columns:
        raise ValueError(
            f"Grading-results input must contain column "
            f"{GRADING_AI_DIAGNOSIS_COL!r}; found {list(df.columns)}"
        )

    standardizer = get_standardizer(use_combined_wrapper)
    if spec.json_kind == "topical":
        df = standardize_json_topical_column(
            df=df,
            input_col=GRADING_AI_DIAGNOSIS_COL,
            label_type=spec.label_type,
            standardizer=standardizer,
        )
    else:
        df = standardize_json_oral_column(
            df=df,
            input_col=GRADING_AI_DIAGNOSIS_COL,
            label_type=spec.label_type,
            standardizer=standardizer,
        )

    logger.info("Writing output workbook: %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    logger.info("Done.")
    return output_path


def normalize_cell_value(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def call_standardizer_direct(medication_string: str, med_type: str, label_type: str) -> Dict[str, Any]:
    if label_type == "current":
        return standardize_medication_list(med_list=medication_string, med_list_type=med_type)
    return standardize_medication_change_list(med_list=medication_string, med_list_type=med_type)


def call_standardizer_combined(medication_string: str, med_type: str, label_type: str) -> Dict[str, Any]:
    return standardize_medication_label(
        medication_string=medication_string,
        medication_type=med_type,
        label_type=label_type,
    )


def get_standardizer(use_combined_wrapper: bool) -> Callable[[str, str, str], Dict[str, Any]]:
    return call_standardizer_combined if use_combined_wrapper else call_standardizer_direct


def get_output_value(result: Dict[str, Any], label_type: str) -> str:
    if label_type == "current":
        return result.get("standardized_medication_list", "")
    return result.get("standardized_medication_change_list", "")

def get_output_value(result: Dict[str, Any], label_type: str) -> str:
    if label_type == "current":
        value = result.get("standardized_medication_list", "")
    else:
        value = result.get("standardized_medication_change_list", "")

    if value in {"None", "", None}:
        return "None"

    return value


def build_output_prefix(input_col: str, label_type: str, med_type: str) -> str:
    return f"{input_col}__standardized_{label_type}_{med_type.lower()}"

def is_passthrough_status(text: str) -> bool:
    return isinstance(text, str) and text.strip().lower() == "none (failed)"

def safe_json_loads(text: str) -> Dict[str, Any]:
    if text is None:
        return None
    
    if isinstance(text, str) and text.strip() == "":
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        raise ValueError("JSON cell must contain an object/dictionary.")

    return data

def extract_med_only(parsed_items: list[Dict[str, Any]]) -> str:
    if not parsed_items:
        return "None"

    meds = []
    for item in parsed_items:
        drug = item.get("drug_name")
        if drug:
            if item.get("change_phrase"):
                drug = f"{item.get('change_phrase')} {drug}"
            meds.append(drug)

    if not meds:
        return "None"

    return ", ".join(meds)

def extract_change_phrase_only(parsed_items: list[Dict[str, Any]]) -> str:
    if not parsed_items:
        return "None"

    changes = []
    for item in parsed_items:
        change = item.get("change_phrase")
        if change:
            changes.append(change)

    if not changes:
        return "None"

    return ", ".join(changes)


def insert_columns_next_to_input(
    df: pd.DataFrame,
    input_col: str,
    column_data: Dict[str, list[Any]],
) -> pd.DataFrame:
    for col in list(column_data.keys()):
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    insert_idx = df.columns.get_loc(input_col) + 1

    for offset, (col_name, values) in enumerate(column_data.items()):
        df.insert(insert_idx + offset, col_name, values)

    return df


def standardize_one_column(
    df: pd.DataFrame,
    input_col: str,
    med_type: str,
    label_type: str,
    standardizer: Callable[[str, str, str], Dict[str, Any]],
) -> pd.DataFrame:
    if input_col not in df.columns:
        raise ValueError(f"Column '{input_col}' was not found in the input sheet.")

    output_prefix = build_output_prefix(input_col, label_type, med_type)
    standardized_col = f"{output_prefix}_output"
    failed_match_col = f"{output_prefix}_failed_match"
    #med_only_col = f"{output_prefix}_med_only"
    parsed_items_col = f"{output_prefix}_parsed_items"
    error_col = f"{output_prefix}_error"

    outputs = []
    failed_matches = []
    #med_only = []
    parsed_items_json = []
    errors = []

    logger.info(
        "Processing plain-text column '%s' as label_type=%s, med_type=%s",
        input_col,
        label_type,
        med_type,
    )

    for idx, raw_value in df[input_col].items():
        text = normalize_cell_value(raw_value)

        if text is None:
            outputs.append("None")
            failed_matches.append(None)
            #med_only.append("None")
            parsed_items_json.append(None)
            errors.append(None)
            continue

        try:
            result = standardizer(text, med_type, label_type)
            parsed_items = result.get("parsed_items", [])
            #valid_items = result.get("valid_items", [])

            outputs.append(get_output_value(result, label_type))
            failed_matches.append(result.get("failed_match"))
            #med_only.append(extract_med_only(valid_items))
            parsed_items_json.append(json.dumps(parsed_items, ensure_ascii=False))
            errors.append(None)
        except Exception as exc:
            outputs.append(None)
            failed_matches.append(None)
            #med_only.append(None)
            parsed_items_json.append(None)
            errors.append(str(exc))
            logger.exception("Failed on row index %s, column '%s'", idx, input_col)

    return insert_columns_next_to_input(
        df,
        input_col,
        {
            standardized_col: outputs,
            failed_match_col: failed_matches,
            #med_only_col: med_only,
            parsed_items_col: parsed_items_json, # Uncomment if you want to include the parsed items as a JSON string in the output
            #error_col: errors,
        },
    )


def standardize_json_oral_column(
    df: pd.DataFrame,
    input_col: str,
    label_type: str,
    standardizer: Callable[[str, str, str], Dict[str, Any]],
) -> pd.DataFrame:
    if input_col not in df.columns:
        raise ValueError(f"Column '{input_col}' was not found in the input sheet.")

    output_prefix = build_output_prefix(input_col, label_type, "oral_json")
    standardized_col = f"{output_prefix}_output"
    failed_match_col = f"{output_prefix}_failed_match"
    #med_only_col = f"{output_prefix}_med_only"
    parsed_items_col = f"{output_prefix}_parsed_items"
    error_col = f"{output_prefix}_error"

    outputs = []
    failed_matches = []
    #med_only = []
    parsed_items_json = []
    errors = []

    logger.info("Processing JSON oral column '%s' as label_type=%s", input_col, label_type)

    for idx, raw_value in df[input_col].items():
        text = normalize_cell_value(raw_value)

        if text is None:
            outputs.append("None")
            failed_matches.append(None)
            #med_only.append("None")
            parsed_items_json.append(None)
            errors.append(None)
            continue

        if is_passthrough_status(text):
            outputs.append(text)
            failed_matches.append(False)
            #med_only.append("None")
            parsed_items_json.append(None)
            errors.append(None)
            continue

        try:
            payload = safe_json_loads(text)
            
            if payload is None:
                logger.warning(
                    f"Skipping row index {idx}, JSON topical column '{input_col}': invalid or empty JSON"
                )
                outputs.append(None)
                failed_matches.append(None)
                parsed_items_json.append(None)
                #med_only.append(None)
                errors.append("Invalid or empty JSON")
                continue

            oral_text = normalize_cell_value(payload.get("Oral"))

            if oral_text is None:
                outputs.append(None)
                failed_matches.append(None)
                #med_only.append(None)
                parsed_items_json.append(None)
                errors.append("JSON did not contain a usable 'Oral' value.")
                continue

            result = standardizer(oral_text, "oral", label_type)

            parsed_items = result.get("parsed_items", [])
            #valid_items = result.get("valid_items", [])

            outputs.append(get_output_value(result, label_type))
            failed_matches.append(result.get("failed_match"))
            #med_only.append(extract_med_only(valid_items))
            parsed_items_json.append(json.dumps(parsed_items, ensure_ascii=False))
            errors.append(None)

        except Exception as exc:
            outputs.append(None)
            failed_matches.append(None)
            #med_only.append(None)
            parsed_items_json.append(None)
            errors.append(str(exc))
            logger.exception("Failed on row index %s, JSON oral column '%s'", idx, input_col)

    return insert_columns_next_to_input(
        df,
        input_col,
        {
            standardized_col: outputs,
            failed_match_col: failed_matches,
            #med_only_col: med_only,
            parsed_items_col: parsed_items_json,
            #error_col: errors,
        },
    )


def standardize_json_topical_column(
    df: pd.DataFrame,
    input_col: str,
    label_type: str,
    standardizer: Callable[[str, str, str], Dict[str, Any]],
) -> pd.DataFrame:
    if input_col not in df.columns:
        raise ValueError(f"Column '{input_col}' was not found in the input sheet.")

    od_prefix = build_output_prefix(input_col, label_type, "od_json")
    os_prefix = build_output_prefix(input_col, label_type, "os_json")

    od_output_col = f"{od_prefix}_output"
    od_failed_match_col = f"{od_prefix}_failed_match"
    #od_med_only_col = f"{od_prefix}_med_only"
    od_parsed_col = f"{od_prefix}_parsed_items"
    od_error_col = f"{od_prefix}_error"

    os_output_col = f"{os_prefix}_output"
    os_failed_match_col = f"{os_prefix}_failed_match"
    #os_med_only_col = f"{os_prefix}_med_only"
    os_parsed_col = f"{os_prefix}_parsed_items"
    os_error_col = f"{os_prefix}_error"

    od_outputs, od_failed_matches, od_med_only, od_parsed, od_errors = [], [], [], [], []
    os_outputs, os_failed_matches, os_med_only, os_parsed, os_errors = [], [], [], [], []

    logger.info("Processing JSON topical column '%s' as label_type=%s", input_col, label_type)

    for idx, raw_value in df[input_col].items():
        text = normalize_cell_value(raw_value)

        if text is None:
            od_outputs.append("None")
            od_failed_matches.append(None)
            #od_med_only.append("None")
            od_parsed.append(None)
            od_errors.append(None)

            os_outputs.append("None")
            os_failed_matches.append(None)
            #os_med_only.append("None")
            os_parsed.append(None)
            os_errors.append(None)
            continue

        if is_passthrough_status(text):
            od_outputs.append(text)
            od_failed_matches.append(False)
            #od_med_only.append("None")
            od_parsed.append(None)
            od_errors.append(None)

            os_outputs.append(text)
            os_failed_matches.append(False)
            #os_med_only.append("None")
            os_parsed.append(None)
            os_errors.append(None)
            continue

        try:
            payload = safe_json_loads(text)

            if payload is None:
                logger.warning(
                    f"Skipping row index {idx}, JSON topical column '{input_col}': invalid or empty JSON"
                )
                od_outputs.append(None)
                od_failed_matches.append(None)
                #od_med_only.append(None)
                od_parsed.append(None)
                od_errors.append("Invalid or empty JSON")
                os_outputs.append(None)
                os_failed_matches.append(None)
                #os_med_only.append(None)
                os_parsed.append(None)
                os_errors.append("Invalid or empty JSON")
                continue

            od_text = normalize_cell_value(payload.get("OD"))
            os_text = normalize_cell_value(payload.get("OS"))

            # OD
            if od_text is None:
                od_outputs.append("None")
                od_failed_matches.append(None)
                #od_med_only.append("None")
                od_parsed.append(None)
                od_errors.append(None)
            else:
                od_result = standardizer(od_text, "OD", label_type)

                od_parsed_items = od_result.get("parsed_items", [])
                #od_valid_items = od_result.get("valid_items", [])

                od_outputs.append(get_output_value(od_result, label_type))
                od_failed_matches.append(od_result.get("failed_match"))
                #od_med_only.append(extract_med_only(od_valid_items))
                od_parsed.append(json.dumps(od_parsed_items, ensure_ascii=False))
                od_errors.append(None)

            # OS
            if os_text is None:
                os_outputs.append("None")
                os_failed_matches.append(None)
                #os_med_only.append("None")
                os_parsed.append(None)
                os_errors.append(None)
            else:
                os_result = standardizer(os_text, "OS", label_type)

                os_parsed_items = os_result.get("parsed_items", [])
                #os_valid_items = os_result.get("valid_items", [])

                os_outputs.append(get_output_value(os_result, label_type))
                os_failed_matches.append(os_result.get("failed_match"))
                #os_med_only.append(extract_med_only(os_valid_items))
                os_parsed.append(json.dumps(os_parsed_items, ensure_ascii=False))
                os_errors.append(None)

        except Exception as exc:
            od_outputs.append(None)
            od_failed_matches.append(None)
            #od_med_only.append(None)
            od_parsed.append(None)
            od_errors.append(str(exc))

            os_outputs.append(None)
            os_failed_matches.append(None)
            #os_med_only.append(None)
            os_parsed.append(None)
            os_errors.append(str(exc))

            logger.exception("Failed on row index %s, JSON topical column '%s'", idx, input_col)

    return insert_columns_next_to_input(
        df,
        input_col,
        {
            od_output_col: od_outputs,
            od_failed_match_col: od_failed_matches,
            #od_med_only_col: od_med_only,
            od_parsed_col: od_parsed,
            #od_error_col: od_errors,
            os_output_col: os_outputs,
            os_failed_match_col: os_failed_matches,
            #os_med_only_col: os_med_only,
            os_parsed_col: os_parsed,
            #os_error_col: os_errors,
        },
    )


def validate_requested_columns(args: argparse.Namespace) -> tuple[Dict[str, list[str]], Dict[str, list[str]]]:
    plain_selected: Dict[str, list[str]] = {}
    json_selected: Dict[str, list[str]] = {}

    for arg_name in PLAIN_COLUMN_SPECS:
        value = getattr(args, arg_name)
        if value:
            plain_selected[arg_name] = value if isinstance(value, list) else [value]

    for arg_name in JSON_COLUMN_SPECS:
        value = getattr(args, arg_name)
        if value:
            json_selected[arg_name] = value if isinstance(value, list) else [value]

    if not plain_selected and not json_selected:
        raise ValueError(
            "You must provide at least one medication column argument, such as "
            "--current-oral-col, --change-od-col, or --current-oral-col-json. "
            "Or use --grading-results for inference grading_results_{cvar}.xlsx files."
        )

    return plain_selected, json_selected


def main() -> None:
    args = parse_args()

    # --- Additional convenience path (does not replace the column-driven mode) ---
    if args.grading_results:
        input_path = Path(args.input)
        if not input_path.is_file():
            raise FileNotFoundError(f"Input not found: {input_path}")
        output_path = Path(args.output) if args.output else None
        run_grading_results_standardization(
            input_path,
            output_path=output_path,
            sheet_name=args.sheet_name,
            cvar=args.cvar,
            acronym=args.acronym,
            use_combined_wrapper=args.use_combined_wrapper,
        )
        return

    if not args.output:
        raise ValueError("--output is required unless --grading-results is set.")

    plain_selected, json_selected = validate_requested_columns(args)

    input_path = Path(args.input)
    output_path = Path(args.output)

    logger.info("Reading input workbook: %s", input_path)
    df = pd.read_excel(input_path, sheet_name=args.sheet_name)

    standardizer = get_standardizer(args.use_combined_wrapper)

    # plain text columns
    for arg_name, input_cols in plain_selected.items():
        spec = PLAIN_COLUMN_SPECS[arg_name]
        for input_col in input_cols:
            df = standardize_one_column(
                df=df,
                input_col=input_col,
                med_type=spec["med_type"],
                label_type=spec["label_type"],
                standardizer=standardizer,
            )

    # JSON columns
    for arg_name, input_cols in json_selected.items():
        spec = JSON_COLUMN_SPECS[arg_name]

        for input_col in input_cols:
            if spec["json_kind"] == "oral":
                df = standardize_json_oral_column(
                    df=df,
                    input_col=input_col,
                    label_type=spec["label_type"],
                    standardizer=standardizer,
                )
            else:
                df = standardize_json_topical_column(
                    df=df,
                    input_col=input_col,
                    label_type=spec["label_type"],
                    standardizer=standardizer,
                )

    logger.info("Writing output workbook: %s", output_path)
    df.to_excel(output_path, index=False)
    logger.info("Done.")


if __name__ == "__main__":
    main()