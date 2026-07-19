#!/usr/bin/env python3
"""
Stratified LLM error rate by grader agreement (Naomi vs Gustavo).

Splits notes into agreed / disagreed strata per medication field, then compares
each model's error rate in each stratum against adjudicated ground truth.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

# ---------------------------------------------------------------------------
# Paths & imports from existing project modules
# ---------------------------------------------------------------------------

REPO = Path("/media/zyflo/shared_files/slm_ehr")
SCRIPTS = REPO / "scripts"
LABELS = REPO / "labels"
TEST_RESULTS = REPO / "test_results"
REPORTS = REPO / "reports"
_MED_STD_DIR = SCRIPTS / "med_standardization"
if str(_MED_STD_DIR) not in sys.path:
    sys.path.insert(0, str(_MED_STD_DIR))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run import (  # noqa: E402
    get_standardizer,
    standardize_json_oral_column,
    standardize_json_topical_column,
    standardize_one_column,
)
from stage_comparison.metrics_eval import (  # noqa: E402
    build_column_map,
    evaluate_scenario,
    get_drugs_and_freqs_and_terms,
    has_medications,
)

NAOMI_PATH = LABELS / "final_sampled_df - Naomi_V2.xlsx"
GUSTAVO_PATH = LABELS / "final_sampled_df - Gustavo.xlsx"
FEWSHOT_PATH = LABELS / "notes_fewshot_final_complete.xlsx"
ADJUDICATED_PATH = LABELS / "adjudicated_meds_last_final_standardized.xlsx"

NAOMI_STD_PATH = LABELS / "final_sampled_df - Naomi_V2_standardized.xlsx"
GUSTAVO_STD_PATH = LABELS / "final_sampled_df - Gustavo_standardized.xlsx"

OUTPUT_DIR = REPO / "reports" / "grader_agreement_stratified"
REPORT_PATH = OUTPUT_DIR / "grader_agreement_stratified_report.md"

CATEGORIES = [
    "top_meds_staged",
    "top_meds_change_staged",
    "oral_meds_staged",
    "oral_meds_change_staged",
]

MODEL_FOLDERS = {
    "Claude Opus 4.6": "claude-opus-4-6",
    "GPT-5.2": "gpt-5.2",
    "DeepSeek V3.2": "DeepSeek-V3.2",
    "Grok 4.1 Fast (non-reasoning)": "grok-4-1-fast-non-reasoning",
    "Qwen3.6-35B-A3B": "Qwen/Qwen3.6-35B-A3B",
}

# Six independent stratification fields
STRAT_FIELDS = [
    {
        "name": "Topical Meds OD",
        "raw_col": "Topical Meds OD",
        "med_type": "OD",
        "label_type": "current",
        "eye": "od",
        "category_keys": ["top_meds_staged"],
    },
    {
        "name": "Topical Meds OS",
        "raw_col": "Topical Meds OS",
        "med_type": "OS",
        "label_type": "current",
        "eye": "os",
        "category_keys": ["top_meds_staged"],
    },
    {
        "name": "Change in Topical Treatment OD",
        "raw_col": "Change in Topical Treatment OD",
        "med_type": "OD",
        "label_type": "change",
        "eye": "od",
        "category_keys": ["top_meds_change_staged"],
    },
    {
        "name": "Change in Topical Treatment OS",
        "raw_col": "Change in Topical Treatment OS",
        "med_type": "OS",
        "label_type": "change",
        "eye": "os",
        "category_keys": ["top_meds_change_staged"],
    },
    {
        "name": "Oral Meds",
        "raw_col": "Oral Meds",
        "med_type": "oral",
        "label_type": "current",
        "eye": "oral",
        "category_keys": ["oral_meds_staged"],
    },
    {
        "name": "Change in Oral Meds",
        "raw_col": "Change in Oral Meds",
        "med_type": "oral",
        "label_type": "change",
        "eye": "oral",
        "category_keys": ["oral_meds_change_staged"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_timestamp(folder_name: str) -> Optional[datetime]:
    m = re.search(r"(\d{2})-(\d{2})_(\d{2}):(\d{2})$", folder_name)
    if not m:
        return None
    month, day, hour, minute = map(int, m.groups())
    return datetime(2025, month, day, hour, minute)


def find_latest_run(settings_dir: Path) -> Optional[Path]:
    runs: list[tuple[datetime, Path]] = []
    if not settings_dir.exists():
        return None
    for d in settings_dir.iterdir():
        if d.is_dir():
            ts = parse_timestamp(d.name)
            if ts:
                runs.append((ts, d))
    if not runs:
        return None
    runs.sort(key=lambda x: x[0], reverse=True)
    return runs[0][1]


def get_settings_dir(cat_dir: Path, model_folder: str) -> Path:
    model_path = cat_dir / model_folder
    if "DeepSeek" in model_folder or "deepseek" in model_folder.lower():
        settings = model_path / "minimal"
        if not settings.exists():
            settings = model_path / "none"
    else:
        settings = model_path / "none"
    return settings


def resolve_grading_file(category: str, model_folder: str) -> tuple[Optional[Path], str]:
    cat_dir = TEST_RESULTS / category
    settings = get_settings_dir(cat_dir, model_folder)
    latest = find_latest_run(settings)
    if latest is None:
        return None, f"no run folder under {settings}"
    fpath = latest / f"grading_results_{category}.xlsx"
    if not fpath.exists():
        return None, f"missing {fpath.name}"
    return fpath, "OK"


def std_output_col(raw_col: str, label_type: str, med_type: str) -> str:
    return f"{raw_col}__standardized_{label_type}_{med_type.lower()}_output"


def normalize_std_value(val: Any) -> frozenset[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return frozenset(["none"])
    s = str(val).strip().lower()
    if s in ("", "none", "nan"):
        return frozenset(["none"])
    if "," in s or ";" in s:
        items = sorted(item.strip() for item in re.split(r"[,;]", s) if item.strip())
        return frozenset(items) if items else frozenset(["none"])
    return frozenset([s])


def values_agree(a: Any, b: Any) -> bool:
    return normalize_std_value(a) == normalize_std_value(b)


def fmt_val(v: Any, decimals: int = 3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{decimals}f}"


def _glaucoma_od_col(df: pd.DataFrame) -> str:
    """Naomi uses 'OD Glaucoma'; Gustavo uses 'Glaucoma OD' (per file inspection)."""
    if "Glaucoma OD" in df.columns:
        return "Glaucoma OD"
    if "OD Glaucoma" in df.columns:
        return "OD Glaucoma"
    raise KeyError("No glaucoma OD column found (expected 'Glaucoma OD' or 'OD Glaucoma')")


def preprocess_grader_df(path: Path, name: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    few_shot = pd.read_excel(FEWSHOT_PATH)
    before = len(df)
    glaucoma_col = _glaucoma_od_col(df)
    df = df[df[glaucoma_col].notna()]
    df = df.merge(
        few_shot[["PAT_ENC_CSN_ID", "NOTE_ID", "UsedinExamples"]],
        on=["PAT_ENC_CSN_ID", "NOTE_ID"],
        how="left",
    )
    df = df[df["UsedinExamples"] == False]  # noqa: E712
    print(f"{name}: {before} -> {len(df)} rows after Glaucoma OD + UsedinExamples==False filter")
    return df.reset_index(drop=True)


def standardize_grader_file(df: pd.DataFrame, out_path: Path) -> pd.DataFrame:
    standardizer = get_standardizer(use_combined_wrapper=False)
    out = df.copy()
    for field in STRAT_FIELDS:
        out = standardize_one_column(
            df=out,
            input_col=field["raw_col"],
            med_type=field["med_type"],
            label_type=field["label_type"],
            standardizer=standardizer,
        )
    out.to_excel(out_path, index=False)
    print(f"Saved standardized grader file: {out_path}")
    return out


def build_stratifications(
    naomi: pd.DataFrame, gustavo: pd.DataFrame
) -> dict[str, dict[str, set[int]]]:
    merged = naomi[["NOTE_ID", "PAT_ENC_CSN_ID"]].merge(
        gustavo[["NOTE_ID", "PAT_ENC_CSN_ID"]],
        on="NOTE_ID",
        how="outer",
        suffixes=("_naomi", "_gustavo"),
        indicator=True,
    )
    naomi_ids = set(naomi["NOTE_ID"])
    gustavo_ids = set(gustavo["NOTE_ID"])
    common_ids = naomi_ids & gustavo_ids

    strata: dict[str, dict[str, set[int]]] = {}
    for field in STRAT_FIELDS:
        col = std_output_col(field["raw_col"], field["label_type"], field["med_type"])
        agreed: set[int] = set()
        disagreed: set[int] = set()
        uncomparable: set[int] = set()

        naomi_map = naomi.set_index("NOTE_ID")[col].to_dict()
        gustavo_map = gustavo.set_index("NOTE_ID")[col].to_dict()

        all_note_ids = naomi_ids | gustavo_ids
        for nid in all_note_ids:
            in_n = nid in naomi_ids
            in_g = nid in gustavo_ids
            if not (in_n and in_g):
                uncomparable.add(nid)
                continue
            if values_agree(naomi_map.get(nid), gustavo_map.get(nid)):
                agreed.add(nid)
            else:
                disagreed.add(nid)

        strata[field["name"]] = {
            "agreed": agreed,
            "disagreed": disagreed,
            "uncomparable": uncomparable,
        }
        print(
            f"{field['name']}: agreed={len(agreed)}, "
            f"disagreed={len(disagreed)}, uncomparable={len(uncomparable)}"
        )
    return strata


def standardize_grading_results(df: pd.DataFrame, category: str) -> pd.DataFrame:
    label_type = "change" if "change" in category else "current"
    standardizer = get_standardizer(use_combined_wrapper=False)
    out = df.copy()
    if category.startswith("top_meds"):
        out = standardize_json_topical_column(
            df=out,
            input_col="AI_Diagnosis",
            label_type=label_type,
            standardizer=standardizer,
        )
    else:
        out = standardize_json_oral_column(
            df=out,
            input_col="AI_Diagnosis",
            label_type=label_type,
            standardizer=standardizer,
        )
    return out


def _preprocess_lists(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Lowercase and list-split standardized med strings; treat NaN/None/no as equivalent empty."""
    out = df.copy()

    def _normalize_empty_scalar(x: Any) -> str:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return "none"
        s = str(x).strip().lower()
        if s in ("", "no", "none", "nan"):
            return "none"
        return s

    for col in cols:
        out[col] = out[col].apply(_normalize_empty_scalar)
        out[col] = out[col].apply(
            lambda x: sorted({_normalize_empty_scalar(item) for item in re.split(r"[,;]", x) if item.strip()})
            if isinstance(x, str) and ("," in x or ";" in x)
            else [_normalize_empty_scalar(x)]
            if isinstance(x, str)
            else x
        )
    return out


def _load_and_merge(df: pd.DataFrame, cols: list[str], is_top: bool) -> pd.DataFrame:
    df_adjudicated = pd.read_excel(ADJUDICATED_PATH)
    dupes = df_adjudicated.duplicated(subset=["PAT_ENC_CSN_ID", "NOTE_ID"])
    if dupes.any():
        raise ValueError(f"Duplicate keys in adjudicated: {dupes.sum()}")

    original_len = len(df)
    if is_top:
        merge_cols = [
            "PAT_ENC_CSN_ID",
            "NOTE_ID",
            cols[0],
            cols[1],
            cols[4],
            cols[5],
            cols[8],
            cols[9],
        ]
    else:
        merge_cols = ["PAT_ENC_CSN_ID", "NOTE_ID", cols[0], cols[2], cols[4]]

    df = df.merge(df_adjudicated[merge_cols], on=["PAT_ENC_CSN_ID", "NOTE_ID"], how="left")
    if len(df) != original_len:
        raise ValueError("Row count changed after adjudicated merge")
    if "UsedinExamples" in df.columns:
        df = df[df["UsedinExamples"] == False]  # noqa: E712
    return df


def compute_stratum_metrics(
    df: pd.DataFrame,
    category: str,
    note_ids: set[int],
    eye: Optional[str],
) -> dict[str, Any]:
    """Compute overall-scenario metrics for a note stratum, optionally one eye."""
    cols = build_column_map(category, "AI_Diagnosis")
    is_top = category.startswith("top_meds")
    has_change = "change" in category

    work = df[df["NOTE_ID"].isin(note_ids)].copy()
    if len(work) == 0:
        return {"N": 0, "exact_matches": 0, "errors": 0, "error_rate": None, "metrics": None}

    work = _load_and_merge(work, cols, is_top)

    if is_top:
        target_os, target_od, pred_os, pred_od = cols[0], cols[1], cols[2], cols[3]
        target_json_os, target_json_od = cols[8], cols[9]
        pred_json_os, pred_json_od = cols[10], cols[11]

        work = _preprocess_lists(work, [pred_os, pred_od, target_os, target_od])
        work = work[work[pred_os] != "none (failed)"]
        work = work[work[pred_od] != "none (failed)"]

        all_true, all_pred = [], []
        for _, row in work.iterrows():
            if eye in (None, "od"):
                all_true.append(row[target_od])
                all_pred.append(row[pred_od])
            if eye in (None, "os"):
                all_true.append(row[target_os])
                all_pred.append(row[pred_os])

        if eye == "od":
            # Re-extract using JSON for drug-level metrics if needed later
            pass
        elif eye == "os":
            pass

    else:
        target, pred = cols[0], cols[1]
        work = _preprocess_lists(work, [pred, target])
        work = work[work[pred] != "none (failed)"]
        all_true = work[target].tolist()
        all_pred = work[pred].tolist()

    n = len(all_true)
    if n == 0:
        return {"N": 0, "exact_matches": 0, "errors": 0, "error_rate": None, "metrics": None}

    exact_matches = sum(1 for t, p in zip(all_true, all_pred) if t == p)
    errors = n - exact_matches
    error_rate = errors / n
    metrics = evaluate_scenario(all_true, all_pred, "overall", n_bootstrap=500)

    return {
        "N": n,
        "exact_matches": exact_matches,
        "errors": errors,
        "error_rate": error_rate,
        "accuracy": metrics["em_accuracy"][0],
        "f1": metrics["f1"][0],
        "metrics": metrics,
        "all_true": all_true,
        "all_pred": all_pred,
    }


def fisher_test_independent(err_agreed: int, n_agreed: int, err_disagreed: int, n_disagreed: int):
    if n_agreed == 0 or n_disagreed == 0:
        return None, None
    correct_a = n_agreed - err_agreed
    correct_d = n_disagreed - err_disagreed
    table = [
        [correct_a, err_agreed],
        [correct_d, err_disagreed],
    ]
    odds_ratio, p_value = fisher_exact(table, alternative="two-sided")
    return odds_ratio, p_value


@dataclass
class ResultRow:
    model: str
    category: str
    field: str
    stratum: str
    N: int
    errors: int
    error_rate: Optional[float]
    accuracy: Optional[float]
    f1: Optional[float]
    fisher_or: Optional[float]
    fisher_p: Optional[float]
    small_n: bool


def run_analysis() -> tuple[pd.DataFrame, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Stratified LLM Error Rate by Grader Agreement\n")

    # ---- Phase 0: file resolution checkpoint ----
    lines.append("## Checkpoint: Resolved grading_results paths (20 files)\n")
    lines.append("| Category | Model | Path | Status |")
    lines.append("|---|---|---|---|")
    resolved: dict[tuple[str, str], Path] = {}
    for cat in CATEGORIES:
        lines.append(f"\n### {cat} model folder mapping\n")
        for model, folder in MODEL_FOLDERS.items():
            fpath, status = resolve_grading_file(cat, folder)
            path_str = str(fpath) if fpath else "N/A"
            lines.append(f"| {cat} | {model} | `{path_str}` | {status} |")
            print(f"{cat} / {model} -> {folder} -> {status}")
            if fpath:
                resolved[(cat, model)] = fpath

    # ---- Phase 0: grader preprocessing ----
    print("\n=== Phase 0: Grader file preprocessing ===")
    naomi_raw = pd.read_excel(NAOMI_PATH)
    gustavo_raw = pd.read_excel(GUSTAVO_PATH)
    lines.append("\n## Phase 0: Grader file columns\n")
    lines.append(f"Naomi columns ({len(naomi_raw.columns)}): " + ", ".join(naomi_raw.columns.astype(str).tolist()))
    lines.append(f"\nGustavo columns ({len(gustavo_raw.columns)}): " + ", ".join(gustavo_raw.columns.astype(str).tolist()))

    required_raw = [f["raw_col"] for f in STRAT_FIELDS]
    for col in required_raw:
        assert col in naomi_raw.columns, f"Missing {col} in Naomi"
        assert col in gustavo_raw.columns, f"Missing {col} in Gustavo"
    lines.append(f"\nAll 6 medication columns present in both grader files.\n")

    naomi = preprocess_grader_df(NAOMI_PATH, "Naomi")
    gustavo = preprocess_grader_df(GUSTAVO_PATH, "Gustavo")
    lines.append(f"- Naomi filtered rows: **{len(naomi)}**")
    lines.append(f"- Gustavo filtered rows: **{len(gustavo)}**")
    if abs(len(naomi) - 992) > 5 or abs(len(gustavo) - 992) > 5:
        lines.append(f"\n**WARNING**: Expected ~992 rows; got Naomi={len(naomi)}, Gustavo={len(gustavo)}")

    # Sample raw values
    lines.append("\n### Sample raw grader values (UsedinExamples==False)\n")
    for field in STRAT_FIELDS:
        col = field["raw_col"]
        samples = naomi[col].dropna().head(3).tolist()
        lines.append(f"- **{col}**: {samples}")

    # ---- Phase 1: standardize grader files ----
    print("\n=== Phase 1: Standardizing grader files ===")
    if NAOMI_STD_PATH.exists() and GUSTAVO_STD_PATH.exists():
        print("Loading existing standardized grader files...")
        naomi_std = pd.read_excel(NAOMI_STD_PATH)
        gustavo_std = pd.read_excel(GUSTAVO_STD_PATH)
    else:
        naomi_std = standardize_grader_file(naomi, NAOMI_STD_PATH)
        gustavo_std = standardize_grader_file(gustavo, GUSTAVO_STD_PATH)

    # ---- Phase 2: stratification ----
    print("\n=== Phase 2: Building stratifications ===")
    lines.append("\n## Phase 2: Grader agreement stratification\n")
    lines.append("| Field | Agreed | Disagreed | Uncomparable |")
    lines.append("|---|---:|---:|---:|")
    strata = build_stratifications(naomi_std, gustavo_std)
    for field_name, counts in strata.items():
        lines.append(
            f"| {field_name} | {len(counts['agreed'])} | {len(counts['disagreed'])} | {len(counts['uncomparable'])} |"
        )

    # ---- Phase 3 & 4: per-model metrics ----
    print("\n=== Phase 3: Computing stratified metrics ===")
    results: list[ResultRow] = []
    detail_rows: list[dict] = []

    field_by_name = {f["name"]: f for f in STRAT_FIELDS}

    for cat in CATEGORIES:
        applicable_fields = [f for f in STRAT_FIELDS if cat in f["category_keys"]]
        for model, folder in MODEL_FOLDERS.items():
            fpath = resolved.get((cat, model))
            if fpath is None:
                continue

            print(f"Processing {model} / {cat} ...")
            cache_path = OUTPUT_DIR / "cache" / f"{cat}__{model.replace(' ', '_').replace('/', '_')}.pkl"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if cache_path.exists():
                std_df = pd.read_pickle(cache_path)
            else:
                raw_df = pd.read_excel(fpath)
                if "Glaucoma OD" in raw_df.columns:
                    raw_df = raw_df.rename(
                        columns={
                            "Glaucoma OD": "Glaucoma Diagnosis OD",
                            "Glaucoma OS": "Glaucoma Diagnosis OS",
                        }
                    )
                std_df = standardize_grading_results(raw_df, cat)
                std_df.to_pickle(cache_path)

            for field in applicable_fields:
                field_name = field["name"]
                eye = field["eye"] if cat.startswith("top_meds") else None
                s = strata[field_name]

                agreed_m = compute_stratum_metrics(std_df, cat, s["agreed"], eye)
                disagreed_m = compute_stratum_metrics(std_df, cat, s["disagreed"], eye)

                for stratum_name, m in [("agreed", agreed_m), ("disagreed", disagreed_m)]:
                    detail_rows.append(
                        {
                            "model": model,
                            "category": cat,
                            "field": field_name,
                            "stratum": stratum_name,
                            "N": m["N"],
                            "errors": m["errors"],
                            "error_rate": m["error_rate"],
                            "accuracy": m["accuracy"],
                            "f1": m["f1"],
                        }
                    )

                or_val, p_val = fisher_test_independent(
                    agreed_m["errors"],
                    agreed_m["N"],
                    disagreed_m["errors"],
                    disagreed_m["N"],
                )
                small_n = disagreed_m["N"] < 30
                results.append(
                    ResultRow(
                        model=model,
                        category=cat,
                        field=field_name,
                        stratum="agreed_vs_disagreed",
                        N=agreed_m["N"] + disagreed_m["N"],
                        errors=agreed_m["errors"] + disagreed_m["errors"],
                        error_rate=None,
                        accuracy=None,
                        f1=None,
                        fisher_or=or_val,
                        fisher_p=p_val,
                        small_n=small_n,
                    )
                )

                # store side-by-side for report
                detail_rows.append(
                    {
                        "model": model,
                        "category": cat,
                        "field": field_name,
                        "stratum": "comparison",
                        "N_agreed": agreed_m["N"],
                        "error_rate_agreed": agreed_m["error_rate"],
                        "accuracy_agreed": agreed_m["accuracy"],
                        "f1_agreed": agreed_m["f1"],
                        "N_disagreed": disagreed_m["N"],
                        "error_rate_disagreed": disagreed_m["error_rate"],
                        "accuracy_disagreed": disagreed_m["accuracy"],
                        "f1_disagreed": disagreed_m["f1"],
                        "fisher_or": or_val,
                        "fisher_p": p_val,
                        "small_n_flag": small_n,
                    }
                )

    detail_df = pd.DataFrame(detail_rows)
    detail_csv = OUTPUT_DIR / "stratified_metrics_detail.csv"
    detail_df.to_csv(detail_csv, index=False)

    comp_df = detail_df[detail_df["stratum"] == "comparison"].copy()

    # Report tables per model x category
    lines.append("\n## Phase 3–4: Stratified metrics by model and category\n")
    for cat in CATEGORIES:
        cat_comp = comp_df[comp_df["category"] == cat]
        if cat_comp.empty:
            continue
        lines.append(f"\n### {cat}\n")
        for model in MODEL_FOLDERS:
            mdf = cat_comp[cat_comp["model"] == model]
            if mdf.empty:
                continue
            lines.append(f"\n#### {model}\n")
            lines.append(
                "| Field | N agreed | Err rate agreed | Acc agreed | F1 agreed | "
                "N disagreed | Err rate disagreed | Acc disagreed | F1 disagreed | "
                "Fisher OR | p-value | Small-N flag |"
            )
            lines.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|")
            for _, row in mdf.iterrows():
                def pct(v):
                    return f"{v:.3f}" if v is not None and not (isinstance(v, float) and np.isnan(v)) else "—"

                lines.append(
                    f"| {row['field']} | {int(row['N_agreed'])} | {pct(row['error_rate_agreed'])} | "
                    f"{pct(row['accuracy_agreed'])} | {pct(row['f1_agreed'])} | "
                    f"{int(row['N_disagreed'])} | {pct(row['error_rate_disagreed'])} | "
                    f"{pct(row['accuracy_disagreed'])} | {pct(row['f1_disagreed'])} | "
                    f"{pct(row['fisher_or'])} | {pct(row['fisher_p'])} | "
                    f"{'YES' if row['small_n_flag'] else 'no'} |"
                )

    # Aggregates
    lines.append("\n## Aggregates\n")

    # Per category across models
    lines.append("\n### Across all 5 models per category (pooled errors)\n")
    lines.append("| Category | Field | N agreed | Err rate agreed | N disagreed | Err rate disagreed | Fisher p |")
    lines.append("|---|---|--:|--:|--:|--:|--:|")
    for cat in CATEGORIES:
        for field in [f for f in STRAT_FIELDS if cat in f["category_keys"]]:
            sub = comp_df[(comp_df["category"] == cat) & (comp_df["field"] == field["name"])]
            if sub.empty:
                continue
            # Pool errors across models (independent samples per stratum)
            agreed_sub = detail_df[(detail_df["category"] == cat) & (detail_df["field"] == field["name"]) & (detail_df["stratum"] == "agreed")]
            disagreed_sub = detail_df[(detail_df["category"] == cat) & (detail_df["field"] == field["name"]) & (detail_df["stratum"] == "disagreed")]
            n_a = int(agreed_sub["N"].sum())
            err_a = int(agreed_sub["errors"].sum())
            n_d = int(disagreed_sub["N"].sum())
            err_d = int(disagreed_sub["errors"].sum())
            er_a = err_a / n_a if n_a else None
            er_d = err_d / n_d if n_d else None
            _, p = fisher_test_independent(err_a, n_a, err_d, n_d)
            lines.append(
                f"| {cat} | {field['name']} | {n_a} | {fmt_val(er_a)} | "
                f"{n_d} | {fmt_val(er_d)} | {fmt_val(p, 4)} |"
            )

    # Per model across categories
    lines.append("\n### Across all 4 categories per model (pooled errors)\n")
    lines.append("| Model | N agreed | Err rate agreed | N disagreed | Err rate disagreed | Fisher p |")
    lines.append("|---|--:|--:|--:|--:|--:|")
    for model in MODEL_FOLDERS:
        agreed_sub = detail_df[(detail_df["model"] == model) & (detail_df["stratum"] == "agreed")]
        disagreed_sub = detail_df[(detail_df["model"] == model) & (detail_df["stratum"] == "disagreed")]
        n_a = int(agreed_sub["N"].sum())
        err_a = int(agreed_sub["errors"].sum())
        n_d = int(disagreed_sub["N"].sum())
        err_d = int(disagreed_sub["errors"].sum())
        er_a = err_a / n_a if n_a else None
        er_d = err_d / n_d if n_d else None
        _, p = fisher_test_independent(err_a, n_a, err_d, n_d)
        lines.append(
            f"| {model} | {n_a} | {fmt_val(er_a)} | "
            f"{n_d} | {fmt_val(er_d)} | {fmt_val(p, 4)} |"
        )

    # Grand pooled
    agreed_all = detail_df[detail_df["stratum"] == "agreed"]
    disagreed_all = detail_df[detail_df["stratum"] == "disagreed"]
    n_a = int(agreed_all["N"].sum())
    err_a = int(agreed_all["errors"].sum())
    n_d = int(disagreed_all["N"].sum())
    err_d = int(disagreed_all["errors"].sum())
    er_a = err_a / n_a
    er_d = err_d / n_d
    _, p_all = fisher_test_independent(err_a, n_a, err_d, n_d)

    # Summary
    lines.append("\n## Final summary\n")
    higher_in_disagreed = er_d > er_a
    lines.append(
        f"Pooled across all models and categories: "
        f"error rate **agreed={er_a:.3f}** (N={n_a}) vs **disagreed={er_d:.3f}** (N={n_d}); "
        f"Fisher exact p={p_all:.4f}.\n"
    )
    if higher_in_disagreed and p_all < 0.05:
        conclusion = (
            "**Supported.** LLM error rate is significantly higher in notes where Naomi and Gustavo "
            "disagreed, suggesting model errors cluster in genuinely ambiguous cases rather than at random."
        )
    elif higher_in_disagreed:
        conclusion = (
            "**Directionally supported but not significant.** Disagreed notes show higher LLM error rate "
            f"({er_d:.3f} vs {er_a:.3f}), but the difference is not statistically significant at α=0.05 "
            f"(p={p_all:.4f}). Small disagreement subsets (median N≈{int(comp_df['N_disagreed'].median())}) "
            "limit power."
        )
    else:
        conclusion = (
            "**Not supported.** LLM error rate is not higher in disagreed notes overall; the hypothesis "
            "that model errors concentrate in human-adjudication cases is not borne out in this data."
        )
    lines.append(conclusion)

    # Count how many field-model combos show higher error in disagreed
    comp_df["higher_disagreed"] = comp_df["error_rate_disagreed"] > comp_df["error_rate_agreed"]
    n_higher = comp_df["higher_disagreed"].sum()
    n_total = len(comp_df)
    lines.append(
        f"\nPer model×category×field comparisons: {n_higher}/{n_total} show higher error rate "
        f"in the disagreed stratum."
    )

    small_n_fields = comp_df[comp_df["small_n_flag"]]["field"].value_counts()
    if len(small_n_fields):
        lines.append(
            "\nFields most often flagged small-N (disagreed N<30): "
            + ", ".join(f"{k} ({v})" for k, v in small_n_fields.items())
        )

    report = "\n".join(lines)
    REPORT_PATH.write_text(report)
    print(f"\nReport written to {REPORT_PATH}")
    print(f"Detail CSV: {detail_csv}")
    return comp_df, report


if __name__ == "__main__":
    comp_df, report = run_analysis()
    print("\n" + "=" * 60)
    print(report.split("## Final summary")[-1])
