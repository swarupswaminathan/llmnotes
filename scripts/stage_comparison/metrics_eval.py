"""Phase 3: metrics evaluation adapted from metrics_standardized_topmeds staged.ipynb."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

# med_standardization for fallback drug extraction
_MED_STD_DIR = Path(__file__).resolve().parents[1] / "med_standardization"
if str(_MED_STD_DIR) not in sys.path:
    sys.path.insert(0, str(_MED_STD_DIR))
from src.current_med_standardization import standardize_medication_list  # noqa: E402

ADJUDICATED_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/labels/adjudicated_meds_last_final_standardized.xlsx"
)


def build_column_map(category: str, pred_prefix: str) -> list[str]:
    """Mirror file_column_map from metrics notebook, swapping AI_Diagnosis for stage col."""
    label_type = "change" if "change" in category else "current"
    is_top = category.startswith("top_meds")

    if is_top:
        if label_type == "change":
            gt_os = "Change in Topical Treatment OS_adjudicated__standardized_change_os_output"
            gt_od = "Change in Topical Treatment OD_adjudicated__standardized_change_od_output"
            gt_checker_os = "Change in Topical Treatment OS_adjudicated__standardized_change_os_manual_review_required"
            gt_checker_od = "Change in Topical Treatment OD_adjudicated__standardized_change_od_manual_review_required"
            gt_json_os = "Change in Topical Treatment OS_adjudicated__standardized_change_os_parsed_items"
            gt_json_od = "Change in Topical Treatment OD_adjudicated__standardized_change_od_parsed_items"
        else:
            gt_os = "Topical Meds OS_adjudicated__standardized_current_os_output"
            gt_od = "Topical Meds OD_adjudicated__standardized_current_od_output"
            gt_checker_os = "Topical Meds OS_adjudicated__standardized_current_os_manual_review_required"
            gt_checker_od = "Topical Meds OD_adjudicated__standardized_current_od_manual_review_required"
            gt_json_os = "Topical Meds OS_adjudicated__standardized_current_os_parsed_items"
            gt_json_od = "Topical Meds OD_adjudicated__standardized_current_od_parsed_items"

        return [
            gt_os,
            gt_od,
            f"{pred_prefix}__standardized_{label_type}_os_json_output",
            f"{pred_prefix}__standardized_{label_type}_od_json_output",
            gt_checker_os,
            gt_checker_od,
            f"{pred_prefix}__standardized_{label_type}_os_json_manual_review_required",
            f"{pred_prefix}__standardized_{label_type}_od_json_manual_review_required",
            gt_json_os,
            gt_json_od,
            f"{pred_prefix}__standardized_{label_type}_os_json_parsed_items",
            f"{pred_prefix}__standardized_{label_type}_od_json_parsed_items",
        ]

    gt_prefix = (
        "Change in Oral Meds_adjudicated"
        if label_type == "change"
        else "Oral Meds_adjudicated"
    )
    return [
        f"{gt_prefix}__standardized_{label_type}_oral_output",
        f"{pred_prefix}__standardized_{label_type}_oral_json_output",
        f"{gt_prefix}__standardized_{label_type}_oral_manual_review_required",
        f"{pred_prefix}__standardized_{label_type}_oral_json_manual_review_required",
        f"{gt_prefix}__standardized_{label_type}_oral_parsed_items",
        f"{pred_prefix}__standardized_{label_type}_oral_json_parsed_items",
    ]


def has_medications(val: Any) -> bool:
    if isinstance(val, list):
        return not (len(val) == 0 or all(v in ("no", "unspecified") for v in val))
    return val not in ("no", "unspecified") and not pd.isna(val)


def count_medications(med_list: Any) -> int:
    if not isinstance(med_list, list):
        return 0 if med_list in ("no", "unspecified") or pd.isna(med_list) else 1
    return sum(
        1 for med in med_list if med not in ("no", "unspecified") and not pd.isna(med)
    )


def wilson_confidence_interval(successes: int, trials: int, alpha: float = 0.05):
    if trials == 0:
        return 0.0, 0.0, 0.0
    z = stats.norm.ppf(1 - alpha / 2)
    p = successes / trials
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials) / denominator
    return p, max(0, center - margin), min(1, center + margin)


def jaccard_index(set1, set2) -> float:
    set1 = set(set1) if isinstance(set1, list) else set1
    set2 = set(set2) if isinstance(set2, list) else set2
    if not set1 and not set2:
        return 1.0
    union = len(set1 | set2)
    return len(set1 & set2) / union if union > 0 else 0.0


def bootstrap_jaccard_ci(true_lists, pred_lists, n_bootstrap: int = 1000, alpha: float = 0.05):
    n = len(true_lists)
    if n == 0:
        return 0.0, 0.0, 0.0
    scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        scores.append(
            np.mean([jaccard_index(true_lists[i], pred_lists[i]) for i in idx])
        )
    scores = np.array(scores)
    return float(np.mean(scores)), float(np.percentile(scores, (alpha / 2) * 100)), float(
        np.percentile(scores, (1 - alpha / 2) * 100)
    )


def bootstrap_f1_ci(true_meds, pred_meds, n_bootstrap: int = 1000, alpha: float = 0.05):
    n = len(true_meds)
    if n == 0:
        return 0.0, 0.0, 0.0
    f1_scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        bt = [true_meds[i] for i in idx]
        bp = [pred_meds[i] for i in idx]
        tp = sum(1 for t, p in zip(bt, bp) if has_medications(t) and has_medications(p))
        fp = sum(1 for t, p in zip(bt, bp) if not has_medications(t) and has_medications(p))
        fn = sum(1 for t, p in zip(bt, bp) if has_medications(t) and not has_medications(p))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_scores.append(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0)
    f1_scores = np.array(f1_scores)
    return float(np.mean(f1_scores)), float(np.percentile(f1_scores, (alpha / 2) * 100)), float(
        np.percentile(f1_scores, (1 - alpha / 2) * 100)
    )


def gwet_ac1(rater1, rater2) -> float:
    r1 = [tuple(x) if isinstance(x, list) else x for x in rater1]
    r2 = [tuple(x) if isinstance(x, list) else x for x in rater2]
    n = len(r1)
    if n == 0:
        return 0.0
    po = sum(a == b for a, b in zip(r1, r2)) / n
    categories = set(r1) | set(r2)
    q = len(categories)
    if q <= 1:
        return 1.0
    c1 = Counter(r1)
    c2 = Counter(r2)
    pe = sum(
        ((c1[k] / n + c2[k] / n) / 2) * (1 - (c1[k] / n + c2[k] / n) / 2)
        for k in categories
    ) / (q - 1)
    if pe >= 1:
        return 1.0
    return (po - pe) / (1 - pe)


def extract_drug_names_only(cell_value, eye: str):
    if isinstance(cell_value, list):
        items = [
            str(i)
            for i in cell_value
            if str(i).strip().lower() not in ["no", "none", "nan", ""]
        ]
        if not items:
            return ["no"]
        cell_value = ", ".join(items)
    try:
        if pd.isna(cell_value):
            return ["no"]
    except (ValueError, TypeError):
        pass
    if str(cell_value).strip().lower() in ["", "no", "none", "nan"]:
        return ["no"]
    result = standardize_medication_list(str(cell_value), eye)
    if result["standardized_medication_list"] in {"Unspecified", "unspecified"}:
        return ["unspecified"]
    drug_names = []
    seen = set()
    for item in result["parsed_items"]:
        drug = item.get("drug_name")
        if drug and drug not in {None, "None"}:
            drug_lower = drug.lower().strip()
            if drug_lower == "unspecified":
                drug_names.append("unspecified")
            elif drug_lower not in seen:
                drug_names.append(drug_lower)
            seen.add(drug_lower)
    return sorted(drug_names) if drug_names else ["no"]


def extract_from_json(json_val, change: bool = False, oral: bool = False):
    empty = (["no"], ["no"], ["no"]) if not oral else (["no"], ["no"], ["no"], ["no"])
    if pd.isna(json_val) or str(json_val).strip().lower() in ["", "none", "nan"]:
        return empty
    try:
        items = json.loads(json_val) if isinstance(json_val, str) else json_val
        if not isinstance(items, list) or len(items) == 0:
            return empty
        drug_names, frequencies, terms, doses = [], [], [], []
        seen = set()
        for item in items:
            drug = item.get("drug_name")
            freq = item.get("frequency")
            dose = item.get("dose")
            term = item.get("change_phrase") if change else None
            if drug and str(drug).lower() not in {"none", "nan", "unspecified"}:
                drug_lower = drug.lower().strip()
                if drug_lower not in seen:
                    drug_names.append(drug_lower)
                    frequencies.append(freq.lower().strip() if freq else "unspecified")
                    doses.append(dose.lower().strip() if dose else "unspecified")
                    terms.append(term.lower().strip() if term else "unspecified")
                seen.add(drug_lower)
        if oral:
            return (
                sorted(drug_names) if drug_names else ["no"],
                frequencies if frequencies else ["no"],
                doses if doses else ["no"],
                terms if terms else ["no"],
            )
        return (
            sorted(drug_names) if drug_names else ["no"],
            frequencies if frequencies else ["no"],
            terms if terms else ["no"],
        )
    except (json.JSONDecodeError, AttributeError, TypeError):
        return (None, None, None) if not oral else (None, None, None, None)


def get_drugs_and_freqs_and_terms(json_val, raw_val, eye: str, change: bool = False, oral: bool = False):
    parsed = extract_from_json(json_val, change=change, oral=oral)
    if oral:
        drug_names, frequencies, doses, terms = parsed
        if drug_names is None:
            drug_names = extract_drug_names_only(raw_val, eye)
            return drug_names, None, None, None
        return drug_names, frequencies, doses, terms
    drug_names, frequencies, terms = parsed
    if drug_names is None:
        drug_names = extract_drug_names_only(raw_val, eye)
        return drug_names, None, None
    return drug_names, frequencies, terms


def _preprocess_lists(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        out[col] = out[col].astype(str).str.lower().fillna("no")
        out[col] = out[col].apply(
            lambda x: sorted([item.strip() for item in re.split(r"[,;]", x)])
            if isinstance(x, str) and ("," in x or ";" in x)
            else [x]
            if isinstance(x, str)
            else x
        )
    return out


def gwet_ac1_bootstrap(
    rater1, rater2, n_iter: int = 1000, alpha: float = 0.05, random_state=None
):
    if random_state is not None:
        np.random.seed(random_state)
    n = len(rater1)
    if n == 0:
        return 0.0, 0.0
    ac1_samples = []
    for _ in range(n_iter):
        idx = np.random.choice(n, n, replace=True)
        sampled_rater1 = [rater1[i] for i in idx]
        sampled_rater2 = [rater2[i] for i in idx]
        ac1_samples.append(gwet_ac1(sampled_rater1, sampled_rater2))
    lower = float(np.percentile(ac1_samples, 100 * alpha / 2))
    upper = float(np.percentile(ac1_samples, 100 * (1 - alpha / 2)))
    return lower, upper


def evaluate_scenario(
    all_true, all_pred, scenario_name: str, n_bootstrap: int = 1000, alpha: float = 0.05
):
    true_pos_mask = [has_medications(t) for t in all_true]
    pred_pos_mask = [has_medications(p) for p in all_pred]
    tp = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and p)
    fp = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and p)
    tn = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and not p)
    fn = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and not p)
    n = len(all_true)
    pos_idx = [i for i, t in enumerate(true_pos_mask) if t]
    neg_idx = [i for i, t in enumerate(true_pos_mask) if not t]
    exact_matches = sum(1 for t, p in zip(all_true, all_pred) if t == p)
    em_accuracy = wilson_confidence_interval(exact_matches, n, alpha)
    em_sens = (
        wilson_confidence_interval(
            sum(1 for i in pos_idx if all_true[i] == all_pred[i]), len(pos_idx), alpha
        )
        if pos_idx
        else (None, None, None)
    )
    em_spec = (
        wilson_confidence_interval(
            sum(1 for i in neg_idx if all_true[i] == all_pred[i]), len(neg_idx), alpha
        )
        if neg_idx and scenario_name not in ("med_name", "freq_only", "positives_only", "change_term")
        else (None, None, None)
    )
    precision = (
        wilson_confidence_interval(tp, tp + fp, alpha) if (tp + fp) > 0 else (None, None, None)
    )
    recall = (
        wilson_confidence_interval(tp, tp + fn, alpha) if (tp + fn) > 0 else (None, None, None)
    )
    f1 = bootstrap_f1_ci(all_true, all_pred, n_bootstrap, alpha)
    jaccard = bootstrap_jaccard_ci(all_true, all_pred, n_bootstrap, alpha)
    ac1 = gwet_ac1(all_true, all_pred)
    ac1_lower, ac1_upper = gwet_ac1_bootstrap(
        all_true, all_pred, n_iter=n_bootstrap, alpha=alpha
    )
    return {
        "scenario": scenario_name,
        "N": n,
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "em_accuracy": em_accuracy,
        "em_sensitivity": em_sens,
        "em_specificity": em_spec,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "jaccard": jaccard,
        "ac1": ac1,
        "ac1_ci": (ac1_lower, ac1_upper),
    }


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
        df = df[df["UsedinExamples"] == False]
    return df


def compute_paired_lists(
    df: pd.DataFrame,
    category: str,
    pred_prefix: str,
) -> tuple[list, list, list, list]:
    """Return (true_diagnosis, pred_diagnosis, true_meds, pred_meds) at eye/row level."""
    cols = build_column_map(category, pred_prefix)
    is_top = category.startswith("top_meds")
    has_change = "change" in category
    # Copy so repeated stage_1 / stage_3 metric calls on the same frame cannot interfere.
    df = _load_and_merge(df.copy(), cols, is_top)

    if is_top:
        target_os, target_od, pred_os, pred_od = cols[0], cols[1], cols[2], cols[3]
        target_checker_os, target_checker_od = cols[4], cols[5]
        pred_checker_os, pred_checker_od = cols[6], cols[7]
        target_json_os, target_json_od = cols[8], cols[9]
        pred_json_os, pred_json_od = cols[10], cols[11]

        df = _preprocess_lists(df, [pred_os, pred_od, target_os, target_od])
        df = df[df[pred_os] != "none (failed)"]
        df = df[df[pred_od] != "none (failed)"]

        for eye, suffix in [("OD", "od"), ("OS", "os")]:
            tj = target_json_od if suffix == "od" else target_json_os
            pj = pred_json_od if suffix == "od" else pred_json_os
            tr = target_od if suffix == "od" else target_os
            pr = pred_od if suffix == "od" else pred_os
            df[f"target_drugs_{suffix}"], df[f"target_freqs_{suffix}"], df[f"target_change_{suffix}"] = zip(
                *df.apply(
                    lambda row, tj=tj, tr=tr: get_drugs_and_freqs_and_terms(
                        row[tj], row[tr], eye, change=has_change
                    ),
                    axis=1,
                )
            )
            df[f"pred_drugs_{suffix}"], df[f"pred_freqs_{suffix}"], df[f"pred_change_{suffix}"] = zip(
                *df.apply(
                    lambda row, pj=pj, pr=pr: get_drugs_and_freqs_and_terms(
                        row[pj], row[pr], eye, change=has_change
                    ),
                    axis=1,
                )
            )

        all_true_diag, all_pred_diag, all_true_meds, all_pred_meds = [], [], [], []
        for _, row in df.iterrows():
            for suffix, tr, pr in [("od", target_od, pred_od), ("os", target_os, pred_os)]:
                all_true_diag.append(row[tr])
                all_pred_diag.append(row[pr])
                all_true_meds.append(row[f"target_drugs_{suffix}"])
                all_pred_meds.append(row[f"pred_drugs_{suffix}"])
        return all_true_diag, all_pred_diag, all_true_meds, all_pred_meds

    target, pred = cols[0], cols[1]
    target_checker, pred_checker = cols[2], cols[3]
    target_json, pred_json = cols[4], cols[5]

    df = _preprocess_lists(df, [pred, target])
    df = df[df[pred] != "none (failed)"]

    df["target_drugs"], df["target_freqs"], df["target_doses"], df["target_change"] = zip(
        *df.apply(
            lambda row: get_drugs_and_freqs_and_terms(
                row[target_json], row[target], "oral", change=has_change, oral=True
            ),
            axis=1,
        )
    )
    df["pred_drugs"], df["pred_freqs"], df["pred_doses"], df["pred_change"] = zip(
        *df.apply(
            lambda row: get_drugs_and_freqs_and_terms(
                row[pred_json], row[pred], "oral", change=has_change, oral=True
            ),
            axis=1,
        )
    )

    return (
        df[target].tolist(),
        df[pred].tolist(),
        df["target_drugs"].tolist(),
        df["pred_drugs"].tolist(),
    )


def run_metrics_for_stage(
    df: pd.DataFrame,
    category: str,
    stage_prefix: str,
    n_bootstrap: int = 1000,
) -> dict:
    """Compute overall-scenario metrics for one stage column set."""
    true_diag, pred_diag, true_meds, pred_meds = compute_paired_lists(
        df, category, stage_prefix
    )
    overall = evaluate_scenario(true_diag, pred_diag, "overall", n_bootstrap)
    pos_idx = [i for i, t in enumerate(true_diag) if has_medications(t)]
    pos_true = [true_diag[i] for i in pos_idx]
    pos_pred = [pred_diag[i] for i in pos_idx]
    pos_true_meds = [true_meds[i] for i in pos_idx]
    pos_pred_meds = [pred_meds[i] for i in pos_idx]
    med_name = evaluate_scenario(pos_true_meds, pos_pred_meds, "med_name", n_bootstrap)
    positives = evaluate_scenario(pos_true, pos_pred, "positives_only", n_bootstrap)
    return {
        "stage": stage_prefix,
        "overall": overall,
        "med_name": med_name,
        "positives_only": positives,
        "true_diag": true_diag,
        "pred_diag": pred_diag,
    }


def fmt_metric_triple(triple: tuple | None) -> str:
    if triple is None or triple[0] is None:
        return "undefined"
    v, lo, hi = triple
    return f"{v:.3f} (95% CI: {lo:.3f} - {hi:.3f})"


def fmt_ac1(overall: dict) -> str:
    ac1 = overall["ac1"]
    lo, hi = overall["ac1_ci"]
    return f"{ac1:.3f} (95% CI: {lo:.3f} - {hi:.3f})"


def format_overall_metrics_lines(overall: dict, *, heading: str) -> list[str]:
    """Format all 8 overall-scenario metrics with 95% CIs."""
    return [
        f"**{heading}** (N={overall['N']}, scenario=overall)",
        f"- EM Accuracy: {fmt_metric_triple(overall['em_accuracy'])}",
        f"- EM Sensitivity: {fmt_metric_triple(overall['em_sensitivity'])}",
        f"- EM Specificity: {fmt_metric_triple(overall['em_specificity'])}",
        f"- Precision: {fmt_metric_triple(overall['precision'])}",
        f"- Recall: {fmt_metric_triple(overall['recall'])}",
        f"- F1 Score: {fmt_metric_triple(overall['f1'])}",
        f"- Jaccard Index: {fmt_metric_triple(overall['jaccard'])}",
        f"- Gwet AC1 Score: {fmt_ac1(overall)}",
    ]


def pool_overall_metrics(results: list[dict], stage: str, n_bootstrap: int = 1000) -> dict:
    """Recompute overall metrics on pooled true/pred lists across result rows."""
    key = "stage1_metrics" if stage == "stage_1" else "stage3_metrics"
    all_true: list = []
    all_pred: list = []
    for r in results:
        all_true.extend(r[key]["true_diag"])
        all_pred.extend(r[key]["pred_diag"])
    return evaluate_scenario(all_true, all_pred, "overall", n_bootstrap)


def format_metric_summary(metrics: dict) -> str:
    o = metrics["overall"]
    acc = o["em_accuracy"][0]
    f1 = o["f1"][0]
    jac = o["jaccard"][0]
    return f"N={o['N']} EM_acc={acc:.3f} F1={f1:.3f} Jaccard={jac:.3f} AC1={o['ac1']:.3f}"
