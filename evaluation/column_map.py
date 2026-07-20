"""Column maps and cvar/acronym resolution for evaluation inputs.

Maps standardized grading filenames to ordered column lists used when merging
predictions with adjudicated gold. Column name strings must match the
standardization output exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Topical (12 cols): target_os/od, pred_os/od, checkers, parsed JSON.
# Oral (6 cols): target, pred, checkers, parsed JSON.

FILE_COLUMN_MAP: dict[str, list[str]] = {
    "grading_results_oms_standardized.xlsx": [
        "Oral Meds_adjudicated__standardized_current_oral_output",
        "AI_Diagnosis__standardized_current_oral_json_output",
        "Oral Meds_adjudicated__standardized_current_oral_failed_match",
        "AI_Diagnosis__standardized_current_oral_json_failed_match",
        "Oral Meds_adjudicated__standardized_current_oral_parsed_items",
        "AI_Diagnosis__standardized_current_oral_json_parsed_items",
    ],
    "grading_results_oral_meds_staged_standardized.xlsx": [
        "Oral Meds_adjudicated__standardized_current_oral_output",
        "AI_Diagnosis__standardized_current_oral_json_output",
        "Oral Meds_adjudicated__standardized_current_oral_failed_match",
        "AI_Diagnosis__standardized_current_oral_json_failed_match",
        "Oral Meds_adjudicated__standardized_current_oral_parsed_items",
        "AI_Diagnosis__standardized_current_oral_json_parsed_items",
    ],
    "grading_results_omcs_standardized.xlsx": [
        "Change in Oral Meds_adjudicated__standardized_change_oral_output",
        "AI_Diagnosis__standardized_change_oral_json_output",
        "Change in Oral Meds_adjudicated__standardized_change_oral_failed_match",
        "AI_Diagnosis__standardized_change_oral_json_failed_match",
        "Change in Oral Meds_adjudicated__standardized_change_oral_parsed_items",
        "AI_Diagnosis__standardized_change_oral_json_parsed_items",
    ],
    "grading_results_oral_meds_change_staged_standardized.xlsx": [
        "Change in Oral Meds_adjudicated__standardized_change_oral_output",
        "AI_Diagnosis__standardized_change_oral_json_output",
        "Change in Oral Meds_adjudicated__standardized_change_oral_failed_match",
        "AI_Diagnosis__standardized_change_oral_json_failed_match",
        "Change in Oral Meds_adjudicated__standardized_change_oral_parsed_items",
        "AI_Diagnosis__standardized_change_oral_json_parsed_items",
    ],
    "grading_results_tms_standardized.xlsx": [
        "Topical Meds OS_adjudicated__standardized_current_os_output",
        "Topical Meds OD_adjudicated__standardized_current_od_output",
        "AI_Diagnosis__standardized_current_os_json_output",
        "AI_Diagnosis__standardized_current_od_json_output",
        "Topical Meds OS_adjudicated__standardized_current_os_failed_match",
        "Topical Meds OD_adjudicated__standardized_current_od_failed_match",
        "AI_Diagnosis__standardized_current_os_json_failed_match",
        "AI_Diagnosis__standardized_current_od_json_failed_match",
        "Topical Meds OS_adjudicated__standardized_current_os_parsed_items",
        "Topical Meds OD_adjudicated__standardized_current_od_parsed_items",
        "AI_Diagnosis__standardized_current_os_json_parsed_items",
        "AI_Diagnosis__standardized_current_od_json_parsed_items",
    ],
    "grading_results_topical_meds_staged_standardized.xlsx": [
        "Topical Meds OS_adjudicated__standardized_current_os_output",
        "Topical Meds OD_adjudicated__standardized_current_od_output",
        "AI_Diagnosis__standardized_current_os_json_output",
        "AI_Diagnosis__standardized_current_od_json_output",
        "Topical Meds OS_adjudicated__standardized_current_os_failed_match",
        "Topical Meds OD_adjudicated__standardized_current_od_failed_match",
        "AI_Diagnosis__standardized_current_os_json_failed_match",
        "AI_Diagnosis__standardized_current_od_json_failed_match",
        "Topical Meds OS_adjudicated__standardized_current_os_parsed_items",
        "Topical Meds OD_adjudicated__standardized_current_od_parsed_items",
        "AI_Diagnosis__standardized_current_os_json_parsed_items",
        "AI_Diagnosis__standardized_current_od_json_parsed_items",
    ],
    "grading_results_tmcs_standardized.xlsx": [
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_output",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_output",
        "AI_Diagnosis__standardized_change_os_json_output",
        "AI_Diagnosis__standardized_change_od_json_output",
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_failed_match",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_failed_match",
        "AI_Diagnosis__standardized_change_os_json_failed_match",
        "AI_Diagnosis__standardized_change_od_json_failed_match",
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_parsed_items",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_parsed_items",
        "AI_Diagnosis__standardized_change_os_json_parsed_items",
        "AI_Diagnosis__standardized_change_od_json_parsed_items",
    ],
    "grading_results_topical_meds_change_staged_standardized.xlsx": [
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_output",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_output",
        "AI_Diagnosis__standardized_change_os_json_output",
        "AI_Diagnosis__standardized_change_od_json_output",
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_failed_match",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_failed_match",
        "AI_Diagnosis__standardized_change_os_json_failed_match",
        "AI_Diagnosis__standardized_change_od_json_failed_match",
        "Change in Topical Treatment OS_adjudicated__standardized_change_os_parsed_items",
        "Change in Topical Treatment OD_adjudicated__standardized_change_od_parsed_items",
        "AI_Diagnosis__standardized_change_os_json_parsed_items",
        "AI_Diagnosis__standardized_change_od_json_parsed_items",
    ],
}

# cvar <-> acronym registry (do NOT infer via fragile path substrings)
CVAR_TO_ACRONYM: dict[str, str] = {
    "top_meds_staged": "tms",
    "top_meds_change_staged": "tmcs",
    "oral_meds_staged": "oms",
    "oral_meds_change_staged": "omcs",
}

ACRONYM_TO_CVAR: dict[str, str] = {v: k for k, v in CVAR_TO_ACRONYM.items()}

TOPICAL_CVARS = frozenset({"top_meds_staged", "top_meds_change_staged"})
CHANGE_CVARS = frozenset({"top_meds_change_staged", "oral_meds_change_staged"})

# Basename → acronym (includes long-form and short-form standardized names)
BASENAME_TO_ACRONYM: dict[str, str] = {
    "grading_results_tms_standardized.xlsx": "tms",
    "grading_results_tmcs_standardized.xlsx": "tmcs",
    "grading_results_oms_standardized.xlsx": "oms",
    "grading_results_omcs_standardized.xlsx": "omcs",
    "grading_results_oral_meds_staged_standardized.xlsx": "oms",
    "grading_results_oral_meds_change_staged_standardized.xlsx": "omcs",
    "grading_results_topical_meds_staged_standardized.xlsx": "tms",
    "grading_results_topical_meds_change_staged_standardized.xlsx": "tmcs",
}


@dataclass(frozen=True)
class EvalSpec:
    """Resolved evaluation configuration for one standardized grading file."""

    cvar: str
    acronym: str
    is_topical: bool
    has_change: bool
    columns: list[str]  # ordered list from FILE_COLUMN_MAP
    map_key: str  # basename used to look up FILE_COLUMN_MAP


def resolve_eval_spec(
    input_path: str | Path,
    *,
    cvar: str | None = None,
    acronym: str | None = None,
) -> EvalSpec:
    """Resolve cvar/acronym/columns from CLI args or input filename registry.

    Detection is registry-based (``--cvar`` / ``--acronym`` / basename map),
    never fragile substring checks like ``'top' in path``.
    """
    basename = Path(input_path).name

    if cvar and acronym:
        if CVAR_TO_ACRONYM.get(cvar) != acronym:
            raise ValueError(
                f"--cvar {cvar!r} and --acronym {acronym!r} disagree "
                f"(expected acronym {CVAR_TO_ACRONYM.get(cvar)!r})"
            )
    elif cvar:
        if cvar not in CVAR_TO_ACRONYM:
            raise ValueError(
                f"Unknown cvar {cvar!r}. Expected one of {sorted(CVAR_TO_ACRONYM)}"
            )
        acronym = CVAR_TO_ACRONYM[cvar]
    elif acronym:
        if acronym not in ACRONYM_TO_CVAR:
            raise ValueError(
                f"Unknown acronym {acronym!r}. Expected one of {sorted(ACRONYM_TO_CVAR)}"
            )
        cvar = ACRONYM_TO_CVAR[acronym]
    else:
        if basename not in BASENAME_TO_ACRONYM:
            raise ValueError(
                f"Cannot infer modality from filename {basename!r}. "
                f"Pass --cvar / --acronym, or use a known basename: "
                f"{sorted(BASENAME_TO_ACRONYM)}"
            )
        acronym = BASENAME_TO_ACRONYM[basename]
        cvar = ACRONYM_TO_CVAR[acronym]

    assert cvar is not None and acronym is not None

    # Prefer exact basename key when present; else canonical acronym basename.
    if basename in FILE_COLUMN_MAP:
        map_key = basename
    else:
        map_key = f"grading_results_{acronym}_standardized.xlsx"
        if map_key not in FILE_COLUMN_MAP:
            raise ValueError(
                f"No FILE_COLUMN_MAP entry for {basename!r} or {map_key!r}"
            )

    return EvalSpec(
        cvar=cvar,
        acronym=acronym,
        is_topical=cvar in TOPICAL_CVARS,
        has_change=cvar in CHANGE_CVARS,
        columns=list(FILE_COLUMN_MAP[map_key]),
        map_key=map_key,
    )
