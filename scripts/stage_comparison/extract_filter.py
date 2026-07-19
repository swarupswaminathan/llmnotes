"""Phase 1: extract stage outputs from AI_Explanation and filter to task3_ran rows."""

from __future__ import annotations

import json
from typing import Any, Optional

import pandas as pd

from .discovery import ResolvedFile

USED_IN_EXAMPLES_COL = "UsedinExamples"


def find_used_in_examples_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.lower().replace("_", "") == "usedinexamples":
            return col
    return None


def filter_used_in_examples(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only evaluation rows (UsedinExamples == False)."""
    col = find_used_in_examples_col(df)
    if col is None:
        raise ValueError("UsedinExamples column not found in input sheet.")
    return df[df[col] == False].copy()


def _parse_ai_explanation(raw: Any) -> Optional[dict]:
    if pd.isna(raw):
        return None
    text = str(raw).strip()
    if text in ("", "None (failed)", "nan"):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def extract_stage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add stage_1_output / stage_3_output JSON columns from AI_Explanation."""
    if "AI_Explanation" not in df.columns:
        raise ValueError("AI_Explanation column not found")

    stage1_vals = []
    stage3_vals = []
    task3_ran_vals = []

    for raw in df["AI_Explanation"]:
        parsed = _parse_ai_explanation(raw)
        if parsed is None:
            stage1_vals.append(None)
            stage3_vals.append(None)
            task3_ran_vals.append(False)
            continue

        t1 = parsed.get("task1_initial")
        t3 = parsed.get("task3_final")
        ran = _coerce_bool(parsed.get("task3_ran"))

        stage1_vals.append(json.dumps(t1) if isinstance(t1, dict) else None)
        stage3_vals.append(json.dumps(t3) if isinstance(t3, dict) else None)
        task3_ran_vals.append(ran)

    df = df.copy()
    df["task3_ran_parsed"] = task3_ran_vals
    df["stage_1_output"] = stage1_vals
    df["stage_3_output"] = stage3_vals
    return df


def filter_task3_ran(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["task3_ran_parsed"] == True].copy()


def process_file(resolved: ResolvedFile) -> tuple[pd.DataFrame, dict]:
    """Return filtered dataframe and row-count stats."""
    if resolved.path is None:
        raise FileNotFoundError(resolved.status)

    df = pd.read_excel(resolved.path)
    total_rows = len(df)
    df = filter_used_in_examples(df)
    eval_rows = len(df)
    df = extract_stage_columns(df)
    filtered = filter_task3_ran(df)
    stats = {
        "category": resolved.category,
        "model": resolved.model,
        "total_rows": total_rows,
        "eval_rows": eval_rows,
        "filtered_rows": len(filtered),
        "task3_ran_rate": len(filtered) / eval_rows if eval_rows else 0.0,
    }
    return filtered, stats


def print_filter_summary(all_stats: list[dict]) -> None:
    print("\n" + "=" * 105)
    print(
        f"{'Category':<28} {'Model':<35} {'Raw':>6} {'Eval':>6} "
        f"{'task3_ran':>10} {'Rate':>8}"
    )
    print("=" * 105)
    for s in all_stats:
        print(
            f"{s['category']:<28} {s['model']:<35} "
            f"{s['total_rows']:>6} {s['eval_rows']:>6} "
            f"{s['filtered_rows']:>10} {s['task3_ran_rate']:>7.1%}"
        )
    print("=" * 105)
