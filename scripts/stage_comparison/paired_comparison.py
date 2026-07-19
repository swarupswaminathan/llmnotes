"""Phase 4: paired statistical comparison of stage 1 vs stage 3."""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy import stats
from scipy.stats import rankdata


def mcnemar_test(stage1_correct: list[bool], stage3_correct: list[bool]) -> dict:
    """McNemar's test on paired binary correctness."""
    assert len(stage1_correct) == len(stage3_correct)
    # b = s1 wrong, s3 right; c = s1 right, s3 wrong
    b = sum(1 for s1, s3 in zip(stage1_correct, stage3_correct) if not s1 and s3)
    c = sum(1 for s1, s3 in zip(stage1_correct, stage3_correct) if s1 and not s3)
    n_discordant = b + c
    if n_discordant == 0:
        return {
            "test": "mcnemar",
            "statistic": 0.0,
            "p_value": 1.0,
            "wrong_to_right": b,
            "right_to_wrong": c,
            "no_change": len(stage1_correct) - b - c,
        }
    # Exact binomial test (equivalent to McNemar for 2x2)
    result = stats.binomtest(b, n_discordant, 0.5, alternative="two-sided")
    return {
        "test": "mcnemar",
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "wrong_to_right": b,
        "right_to_wrong": c,
        "no_change": len(stage1_correct) - b - c,
    }


def paired_continuous_tests(
    stage1_scores: list[float], stage3_scores: list[float]
) -> dict:
    """Wilcoxon signed-rank (primary) and paired t-test (secondary) on stage3 - stage1."""
    diffs = np.array(stage3_scores, dtype=float) - np.array(stage1_scores, dtype=float)
    n_total = len(diffs)
    if n_total == 0:
        return _empty_wilcoxon_result(n_total=0)

    n_zero = int(np.sum(diffs == 0))
    nonzero = diffs[diffs != 0]
    n_ranked = len(nonzero)
    n_improved = int(np.sum(nonzero > 0))
    n_worsened = int(np.sum(nonzero < 0))
    max_rank_sum = n_ranked * (n_ranked + 1) / 2 if n_ranked else 0.0

    if n_ranked == 0:
        return {
            **_empty_wilcoxon_result(n_total=n_total),
            "n_zero_diff": n_zero,
            "mean_diff": 0.0,
        }

    abs_ranks = rankdata(np.abs(nonzero))
    w_plus = float(abs_ranks[nonzero > 0].sum())
    w_minus = float(abs_ranks[nonzero < 0].sum())

    wilcoxon = stats.wilcoxon(
        stage3_scores, stage1_scores, alternative="two-sided", zero_method="wilcox"
    )
    ttest = stats.ttest_rel(stage3_scores, stage1_scores)
    w_min = float(wilcoxon.statistic)

    return {
        "wilcoxon_statistic": w_min,
        "wilcoxon_p": float(wilcoxon.pvalue),
        "wilcoxon_w_plus": w_plus,
        "wilcoxon_w_minus": w_minus,
        "wilcoxon_n_total": n_total,
        "wilcoxon_n_ranked": n_ranked,
        "wilcoxon_n_zero_diff": n_zero,
        "wilcoxon_n_improved": n_improved,
        "wilcoxon_n_worsened": n_worsened,
        "wilcoxon_max_rank_sum": max_rank_sum,
        "ttest_statistic": float(ttest.statistic),
        "ttest_p": float(ttest.pvalue),
        "mean_diff": float(np.mean(diffs)),
    }


def _empty_wilcoxon_result(n_total: int) -> dict:
    return {
        "wilcoxon_statistic": None,
        "wilcoxon_p": None,
        "wilcoxon_w_plus": None,
        "wilcoxon_w_minus": None,
        "wilcoxon_n_total": n_total,
        "wilcoxon_n_ranked": 0,
        "wilcoxon_n_zero_diff": n_total,
        "wilcoxon_n_improved": 0,
        "wilcoxon_n_worsened": 0,
        "wilcoxon_max_rank_sum": 0.0,
        "ttest_statistic": None,
        "ttest_p": None,
        "mean_diff": 0.0,
    }


def format_wilcoxon_jaccard_line(w: dict) -> str:
    """Human-readable Wilcoxon signed-rank summary for Jaccard (stage3 - stage1)."""
    if w.get("wilcoxon_p") is None:
        return "- Wilcoxon (Jaccard): not computed (no ranked pairs)"

    n_ranked = w["wilcoxon_n_ranked"]
    n_total = w["wilcoxon_n_total"]
    n_zero = w["wilcoxon_n_zero_diff"]
    w_plus = w["wilcoxon_w_plus"]
    w_minus = w["wilcoxon_w_minus"]
    w_min = w["wilcoxon_statistic"]
    w_max = w["wilcoxon_max_rank_sum"]
    pct = (w_min / w_max * 100) if w_max else 0.0
    smaller = "W−" if w_minus <= w_plus else "W+"

    return (
        f"- Wilcoxon (Jaccard, Δ=stage3−stage1): "
        f"ranked pairs={n_ranked}/{n_total} "
        f"(zero Δ={n_zero}; improved={w['wilcoxon_n_improved']}, worsened={w['wilcoxon_n_worsened']}); "
        f"W+={w_plus:.1f}, W−={w_minus:.1f}, min(W+,W−)={w_min:.1f} ({smaller}, "
        f"{pct:.1f}% of max {w_max:.0f}); "
        f"mean ΔJaccard={w['mean_diff']:+.3f}, p={w['wilcoxon_p']:.4g}"
    )


def jaccard_per_pair(true_val, pred_val) -> float:
    from .metrics_eval import jaccard_index

    if isinstance(true_val, list) and isinstance(pred_val, list):
        return jaccard_index(true_val, pred_val)
    return 1.0 if true_val == pred_val else 0.0


def run_paired_comparison(
    true_diag: list,
    stage1_pred: list,
    stage3_pred: list,
) -> dict:
    """Compare stage 1 vs stage 3 on the same ground truth."""
    n = len(true_diag)
    s1_correct = [t == p for t, p in zip(true_diag, stage1_pred)]
    s3_correct = [t == p for t, p in zip(true_diag, stage3_pred)]
    s1_jaccard = [jaccard_per_pair(t, p) for t, p in zip(true_diag, stage1_pred)]
    s3_jaccard = [jaccard_per_pair(t, p) for t, p in zip(true_diag, stage3_pred)]

    mcnemar = mcnemar_test(s1_correct, s3_correct)
    wilcoxon = paired_continuous_tests(s1_jaccard, s3_jaccard)

    s1_acc = sum(s1_correct) / n if n else 0.0
    s3_acc = sum(s3_correct) / n if n else 0.0
    net_flip = (mcnemar["wrong_to_right"] - mcnemar["right_to_wrong"]) / n if n else 0.0

    return {
        "N": n,
        "stage1_accuracy": s1_acc,
        "stage3_accuracy": s3_acc,
        "stage1_mean_jaccard": float(np.mean(s1_jaccard)) if n else 0.0,
        "stage3_mean_jaccard": float(np.mean(s3_jaccard)) if n else 0.0,
        "mcnemar": mcnemar,
        "wilcoxon_jaccard": wilcoxon,
        "net_flip_rate": net_flip,
    }


def interpret_result(paired: dict, alpha: float = 0.05) -> str:
    n = paired["N"]
    p = paired["mcnemar"]["p_value"]
    net = paired["net_flip_rate"]
    s1 = paired["stage1_accuracy"]
    s3 = paired["stage3_accuracy"]

    if n < 10:
        conf = "low confidence (small N)"
    elif p >= alpha:
        conf = "no significant difference"
    elif abs(net) < 0.02:
        conf = "significant but tiny effect"
    else:
        conf = "moderate confidence" if n >= 30 else " modest confidence"

    if p >= alpha:
        direction = "no significant difference"
    elif s3 > s1:
        direction = "revision appears to help"
    elif s3 < s1:
        direction = "revision appears to hurt"
    else:
        direction = "mixed/no clear direction"

    return (
        f"{direction} (stage1 acc={s1:.3f}, stage3 acc={s3:.3f}, "
        f"net flip={net:+.3f}, McNemar p={p:.4f}, N={n}; {conf})"
    )
