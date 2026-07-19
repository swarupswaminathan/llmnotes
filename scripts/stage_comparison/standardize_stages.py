"""Phase 2: standardize stage_1_output and stage_3_output via med_standardization."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Allow importing med_standardization/run.py helpers
_MED_STD_DIR = Path(__file__).resolve().parents[1] / "med_standardization"
if str(_MED_STD_DIR) not in sys.path:
    sys.path.insert(0, str(_MED_STD_DIR))

from run import (  # noqa: E402
    get_standardizer,
    standardize_json_oral_column,
    standardize_json_topical_column,
)

STAGE_COLS = ["stage_1_output", "stage_3_output"]


def _label_type(category: str) -> str:
    return "change" if "change" in category else "current"


def _is_topical(category: str) -> bool:
    return category.startswith("top_meds")


def standardize_dataframe(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Standardize both stage columns, keeping raw values."""
    label_type = _label_type(category)
    standardizer = get_standardizer(use_combined_wrapper=False)
    out = df.copy()

    for col in STAGE_COLS:
        if col not in out.columns:
            raise ValueError(f"Missing column {col}")

        if _is_topical(category):
            out = standardize_json_topical_column(
                df=out,
                input_col=col,
                label_type=label_type,
                standardizer=standardizer,
            )
        else:
            out = standardize_json_oral_column(
                df=out,
                input_col=col,
                label_type=label_type,
                standardizer=standardizer,
            )

    return out


def output_path_for(source_xlsx: Path) -> Path:
    return source_xlsx.with_name(
        source_xlsx.stem + "_standardized_stage_comp.xlsx"
    )


def save_standardized(df: pd.DataFrame, source_xlsx: Path) -> Path:
    out_path = output_path_for(source_xlsx)
    df.to_excel(out_path, index=False)
    return out_path
