"""Shared agreement metrics for topical and oral evaluation.

Provides Gwet AC1, Wilson CIs, Jaccard/F1 bootstraps, and scenario printers
(EM Acc/Sens/Spec, precision/recall/F1). No AUPRC or dose-only scenarios.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats


def gwet_ac1(rater1: Sequence[Any], rater2: Sequence[Any]) -> float:
    """Gwet's AC1 chance-corrected agreement between two raters."""
    r1 = [tuple(x) if isinstance(x, list) else x for x in rater1]
    r2 = [tuple(x) if isinstance(x, list) else x for x in rater2]

    n = len(r1)
    if n == 0:
        return 0

    Po = sum(a == b for a, b in zip(r1, r2)) / n

    categories = set(r1) | set(r2)
    q = len(categories)

    if q <= 1:
        return 1.0

    c1 = Counter(r1)
    c2 = Counter(r2)

    Pe = sum(
        ((c1[k] / n + c2[k] / n) / 2) * (1 - (c1[k] / n + c2[k] / n) / 2)
        for k in categories
    ) / (q - 1)

    if Pe >= 1:
        return 1.0

    return (Po - Pe) / (1 - Pe)


def gwet_ac1_bootstrap(
    rater1: Sequence[Any],
    rater2: Sequence[Any],
    n_iter: int = 1000,
    alpha: float = 0.05,
    random_state: int | None = None,
) -> tuple[float, float]:
    """Bootstrap confidence interval for Gwet AC1."""
    if random_state is not None:
        np.random.seed(random_state)
    n = len(rater1)
    if n == 0:
        return 0, 0
    ac1_samples = []
    for _ in range(n_iter):
        idx = np.random.choice(n, n, replace=True)
        sampled_rater1 = [rater1[i] for i in idx]
        sampled_rater2 = [rater2[i] for i in idx]
        ac1_samples.append(gwet_ac1(sampled_rater1, sampled_rater2))
    lower = np.percentile(ac1_samples, 100 * alpha / 2)
    upper = np.percentile(ac1_samples, 100 * (1 - alpha / 2))
    return lower, upper


# Presence / count / Wilson / Jaccard / bootstrap


def has_medications(val: Any) -> bool:
    """True if val contains at least one real medication (not 'no'/'unspecified')."""
    if isinstance(val, list):
        return not (
            len(val) == 0 or all(v in ("no", "unspecified") for v in val)
        )
    return val not in ("no", "unspecified") and not pd.isna(val)


def count_medications(med_list: Any) -> int:
    """Count real (non-'no', non-'unspecified') medications in a list."""
    if not isinstance(med_list, list):
        return 0 if med_list in ("no", "unspecified") or pd.isna(med_list) else 1
    return sum(
        1
        for med in med_list
        if med not in ("no", "unspecified") and not pd.isna(med)
    )


def wilson_confidence_interval(
    successes: int, trials: int, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Wilson confidence interval for proportions."""
    if trials == 0:
        return 0, 0, 0
    z = stats.norm.ppf(1 - alpha / 2)
    p = successes / trials
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = (
        z * np.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials) / denominator
    )
    return p, max(0, center - margin), min(1, center + margin)


def jaccard_index(set1: Any, set2: Any) -> float:
    """Jaccard index between two sets or lists."""
    set1 = set(set1) if isinstance(set1, list) else set1
    set2 = set(set2) if isinstance(set2, list) else set2
    if not set1 and not set2:
        return 1.0
    union = len(set1 | set2)
    return len(set1 & set2) / union if union > 0 else 0


def bootstrap_jaccard_ci(
    true_lists: Sequence[Any],
    pred_lists: Sequence[Any],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Bootstrap confidence interval for mean Jaccard index."""
    n = len(true_lists)
    scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        scores.append(
            np.mean([jaccard_index(true_lists[i], pred_lists[i]) for i in idx])
        )
    scores = np.array(scores)
    return (
        np.mean(scores),
        np.percentile(scores, (alpha / 2) * 100),
        np.percentile(scores, (1 - alpha / 2) * 100),
    )


def bootstrap_f1_ci(
    true_meds: Sequence[Any],
    pred_meds: Sequence[Any],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Bootstrap confidence interval for F1 score."""
    n = len(true_meds)
    f1_scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        bt = [true_meds[i] for i in idx]
        bp = [pred_meds[i] for i in idx]
        tp = sum(
            1
            for t, p in zip(bt, bp)
            if has_medications(t) and has_medications(p)
        )
        fp = sum(
            1
            for t, p in zip(bt, bp)
            if not has_medications(t) and has_medications(p)
        )
        fn = sum(
            1
            for t, p in zip(bt, bp)
            if has_medications(t) and not has_medications(p)
        )
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_scores.append(
            2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        )
    f1_scores = np.array(f1_scores)
    return (
        np.mean(f1_scores),
        np.percentile(f1_scores, (alpha / 2) * 100),
        np.percentile(f1_scores, (1 - alpha / 2) * 100),
    )


def bootstrap_error_metrics(
    true_counts: Sequence[float],
    pred_counts: Sequence[float],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Bootstrap confidence intervals for MAE and MSE."""
    n = len(true_counts)
    mae_scores, mse_scores = [], []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        rt = np.array([true_counts[i] for i in idx])
        rp = np.array([pred_counts[i] for i in idx])
        mae_scores.append(np.mean(np.abs(rp - rt)))
        mse_scores.append(np.mean((rp - rt) ** 2))

    def ci(arr: np.ndarray) -> tuple[float, float, float]:
        return np.mean(arr), np.percentile(arr, 2.5), np.percentile(arr, 97.5)

    return ci(np.array(mae_scores)), ci(np.array(mse_scores))


# Scenario names where EM specificity is not reported
_NO_EM_SPEC = frozenset(
    {"med_name", "freq_only", "positives_only", "change_term"}
)


def evaluate_scenario(
    all_true: Sequence[Any],
    all_pred: Sequence[Any],
    scenario_name: str,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compute and print metrics for a given scenario (EM Acc/Sens/Spec, P/R/F1, Jaccard, Gwet AC1)."""
    true_pos_mask = [has_medications(t) for t in all_true]
    pred_pos_mask = [has_medications(p) for p in all_pred]

    TP = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and p)
    FP = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and p)
    TN = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and not p)
    FN = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and not p)
    N = len(all_true)

    pos_idx = [i for i, t in enumerate(true_pos_mask) if t]
    neg_idx = [i for i, t in enumerate(true_pos_mask) if not t]

    exact_matches = sum(1 for t, p in zip(all_true, all_pred) if t == p)
    em_accuracy = wilson_confidence_interval(exact_matches, N, alpha)
    em_sens = (
        wilson_confidence_interval(
            sum(1 for i in pos_idx if all_true[i] == all_pred[i]),
            len(pos_idx),
            alpha,
        )
        if pos_idx
        else (None, None, None)
    )
    em_spec = (
        wilson_confidence_interval(
            sum(1 for i in neg_idx if all_true[i] == all_pred[i]),
            len(neg_idx),
            alpha,
        )
        if neg_idx and scenario_name not in _NO_EM_SPEC
        else (None, None, None)
    )

    precision = (
        wilson_confidence_interval(TP, TP + FP, alpha)
        if (TP + FP) > 0
        else (None, None, None)
    )
    recall = (
        wilson_confidence_interval(TP, TP + FN, alpha)
        if (TP + FN) > 0
        else (None, None, None)
    )
    f1 = bootstrap_f1_ci(all_true, all_pred, n_bootstrap, alpha)
    jaccard = bootstrap_jaccard_ci(all_true, all_pred, n_bootstrap, alpha)

    ac1 = gwet_ac1(all_true, all_pred)
    ac1_lower, ac1_upper = gwet_ac1_bootstrap(
        all_true, all_pred, n_iter=n_bootstrap, alpha=alpha
    )

    def fmt(triple: tuple[Any, Any, Any] | None) -> str:
        if triple is None:
            return "undefined"
        v, lo, hi = triple
        return "undefined" if v is None else f"{v:.3f} (95% CI: {lo:.3f} - {hi:.3f})"

    print("\n" + "=" * 60)
    print(f"SCENARIO: {scenario_name.upper()}")
    print("=" * 60)
    print(
        f"Total samples:    {N}  |  Positives: {len(pos_idx)}  |  "
        f"Negatives: {len(neg_idx)}"
    )
    print(f"TP={TP}  FP={FP}  TN={TN}  FN={FN}")
    print(f"\nEM Accuracy:      {fmt(em_accuracy)}")
    print(f"EM Sensitivity:   {fmt(em_sens)}")
    print(f"EM Specificity:   {fmt(em_spec)}")
    print(f"Precision:        {fmt(precision)}")
    print(f"Recall:           {fmt(recall)}")
    print(f"F1 Score:         {fmt(f1)}")
    print(f"Jaccard Index:    {fmt(jaccard)}")
    print(
        f"Gwet AC1 Score:   {ac1:.3f} (95% CI: {ac1_lower:.3f} - {ac1_upper:.3f})"
    )

    return dict(
        scenario=scenario_name,
        N=N,
        TP=TP,
        FP=FP,
        TN=TN,
        FN=FN,
        em_accuracy=em_accuracy,
        em_sensitivity=em_sens,
        em_specificity=em_spec,
        precision=precision,
        recall=recall,
        f1=f1,
        jaccard=jaccard,
        ac1=ac1,
        ac1_ci=(ac1_lower, ac1_upper),
    )
