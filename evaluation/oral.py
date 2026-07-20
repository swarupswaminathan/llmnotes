"""Oral (note-level) medication evaluation against adjudicated gold.

Drops rows with missing labels flagged for failed_match, extracts drugs /
frequencies / change terms, then prints agreement scenarios (no AUPRC).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from evaluation.extract import get_drugs_freqs_terms_oral
from evaluation.load import LoadedEvalData, OralColumns
from evaluation.metrics import (
    bootstrap_error_metrics,
    bootstrap_jaccard_ci,
    count_medications,
    evaluate_scenario,
    has_medications,
)


def _preprocess_oral(df: pd.DataFrame, cols: OralColumns) -> pd.DataFrame:
    """Normalize oral columns and drop missing / failed-prediction rows."""
    df = df.copy()
    df["original_index"] = df.index
    before = len(df)

    missing_rows = ((df[cols.target_checker] == 1) & df[cols.target].isna()) | (
        (df[cols.pred_checker] == 1) & df[cols.pred].isna()
    )

    df = df[~missing_rows].reset_index(drop=True)
    after = len(df)
    print(
        f"Removed {before - after} rows with missing AI_Meds for both eyes. "
        f"Remaining rows: {after}"
    )

    for col in [cols.pred, cols.target]:
        df[col] = df[col].str.lower().fillna("no")

    df = df[df[cols.pred] != "none (failed)"]
    new_after = len(df)
    print(
        f"Removed {after - new_after} rows with 'none (failed)' predictions. "
        f"Remaining rows: {new_after}"
    )

    for col in [cols.pred, cols.target]:
        df[col] = df[col].apply(
            lambda x: sorted(
                [item.strip() for item in re.split(r"[,;]", x)]
            )
            if isinstance(x, str) and ("," in x or ";" in x)
            else [x]
            if isinstance(x, str)
            else x
        )
    print("Data preprocessing completed.")
    return df


def _extract_oral(
    df: pd.DataFrame, cols: OralColumns, has_change: bool
) -> pd.DataFrame:
    """Attach target/pred drug, frequency, and change columns (note-level)."""
    (
        df["target_drugs"],
        df["target_freqs"],
        df["target_change"],
    ) = zip(
        *df.apply(
            lambda row: get_drugs_freqs_terms_oral(
                row[cols.target_json],
                row[cols.target],
                "oral",
                change=has_change,
            ),
            axis=1,
        )
    )
    (
        df["pred_drugs"],
        df["pred_freqs"],
        df["pred_change"],
    ) = zip(
        *df.apply(
            lambda row: get_drugs_freqs_terms_oral(
                row[cols.pred_json],
                row[cols.pred],
                "oral",
                change=has_change,
            ),
            axis=1,
        )
    )
    return df


def run_oral_evaluation(
    loaded: LoadedEvalData, *, verbose: bool = False
) -> None:
    """Run full oral analysis and print metric scenarios to stdout."""
    if loaded.oral is None:
        raise ValueError("LoadedEvalData.oral is required for oral eval")

    cols = loaded.oral
    has_change = loaded.spec.has_change
    df = _preprocess_oral(loaded.df, cols)
    df = _extract_oral(df, cols, has_change)

    print("Starting comprehensive analysis for both eyes combined...")

    all_true_diagnosis: list = []
    all_pred_diagnosis: list = []
    all_true_meds: list = []
    all_pred_meds: list = []
    all_true_freqs: list = []
    all_pred_freqs: list = []
    all_true_changes: list = []
    all_pred_changes: list = []
    all_indices: list = []

    for _idx, row in df.iterrows():
        all_true_diagnosis.append(row[cols.target])
        all_pred_diagnosis.append(row[cols.pred])
        all_true_meds.append(row["target_drugs"])
        all_pred_meds.append(row["pred_drugs"])
        all_true_freqs.append(row["target_freqs"])
        all_pred_freqs.append(row["pred_freqs"])
        if has_change:
            all_true_changes.append(row["target_change"])
            all_pred_changes.append(row["pred_change"])
        all_indices.append(row["NOTE_ID"])

    print(f"Total samples (both eyes combined): {len(all_true_diagnosis)}")

    if verbose:
        print("\n=== Cases Where Predicted != True ===")
        for idx, t, p in zip(all_indices, all_true_diagnosis, all_pred_diagnosis):
            if t != p:
                print(f"Row {idx} | True: {t} | Pred: {p}")

    true_has_meds = [has_medications(t) for t in all_true_diagnosis]
    positive_indices = [i for i, h in enumerate(true_has_meds) if h]
    negative_indices = [i for i, h in enumerate(true_has_meds) if not h]
    positive_true = [all_true_diagnosis[i] for i in positive_indices]
    positive_pred = [all_pred_diagnosis[i] for i in positive_indices]
    total_samples = len(all_true_diagnosis)
    exact_matches = sum(
        1 for t, p in zip(all_true_diagnosis, all_pred_diagnosis) if t == p
    )

    positive_exact_matches = 0
    negative_exact_matches = 0
    if positive_indices:
        positive_exact_matches = sum(
            1
            for i in positive_indices
            if all_true_diagnosis[i] == all_pred_diagnosis[i]
        )
    if negative_indices:
        negative_exact_matches = sum(
            1
            for i in negative_indices
            if all_true_diagnosis[i] == all_pred_diagnosis[i]
        )

    print("\n" + "=" * 60)
    print("Breakdown:")
    print("=" * 60)
    print(f"Total samples (eye-level): {total_samples}")
    print(f"Eyes with medications (positive class): {len(positive_indices)}")
    print(f"Eyes without medications (negative class): {len(negative_indices)}")
    if positive_indices:
        print(
            f"Exact matches in positive eyes: "
            f"{positive_exact_matches}/{len(positive_indices)}"
        )
    if negative_indices:
        print(
            f"Exact matches in negative eyes: "
            f"{negative_exact_matches}/{len(negative_indices)}"
        )
    print(f"Total exact matches: {exact_matches}/{total_samples}")

    pos_true_meds = [all_true_meds[i] for i in positive_indices]
    pos_pred_meds = [all_pred_meds[i] for i in positive_indices]
    pos_true_freqs = [all_true_freqs[i] for i in positive_indices]
    pos_pred_freqs = [all_pred_freqs[i] for i in positive_indices]

    evaluate_scenario(all_true_diagnosis, all_pred_diagnosis, "overall")
    evaluate_scenario(positive_true, positive_pred, "positives_only")
    evaluate_scenario(pos_true_meds, pos_pred_meds, "med_name")
    evaluate_scenario(pos_true_freqs, pos_pred_freqs, "freq_only")

    if has_change:
        pos_true_changes = [all_true_changes[i] for i in positive_indices]
        pos_pred_changes = [all_pred_changes[i] for i in positive_indices]
        evaluate_scenario(pos_true_changes, pos_pred_changes, "change_term")

    print("\n" + "=" * 60)
    print("JACCARD INDEX BY MEDICATION COUNT SUBGROUP")
    print("=" * 60)

    subgroups = {
        "Exactly 1 medication": lambda c: c == 1,
        "Exactly 2 medications": lambda c: c == 2,
        "Exactly 3 medications": lambda c: c == 3,
        "4 or more medications": lambda c: c >= 4,
    }

    for label, condition in subgroups.items():
        filtered = [
            (t, p)
            for t, p in zip(all_true_diagnosis, all_pred_diagnosis)
            if condition(count_medications(t))
        ]
        n = len(filtered)
        if n == 0:
            print(f"{label} (n=0): No samples found")
            continue
        ft, fp = zip(*filtered)
        j_mean, j_lower, j_upper = bootstrap_jaccard_ci(list(ft), list(fp))
        print(
            f"{label} (n={n}): {j_mean:.3f} "
            f"(95% CI: {j_lower:.3f} - {j_upper:.3f})"
        )

    print("\n" + "=" * 60)
    print("MSE AND MAE FOR MEDICATION COUNTS (PATIENTS WITH MEDICATIONS)")
    print("=" * 60)

    med_positive_indices = [
        i for i, tm in enumerate(all_true_meds) if has_medications(tm)
    ]

    counts = [
        (count_medications(all_true_meds[i]), count_medications(all_pred_meds[i]))
        for i in med_positive_indices
    ]

    freq_counts = [
        (
            count_medications(all_true_freqs[i]),
            count_medications(all_pred_freqs[i]),
        )
        for i in med_positive_indices
    ]

    if counts:
        true_counts, pred_counts = zip(*counts)
        print(f"Patients with medications: {len(true_counts)}")
        (mae_mean, mae_lower, mae_upper), (mse_mean, mse_lower, mse_upper) = (
            bootstrap_error_metrics(list(true_counts), list(pred_counts))
        )
        print(
            f"MAE: {mae_mean:.3f} (95% CI: {mae_lower:.3f} - {mae_upper:.3f})"
        )
        print(
            f"MSE: {mse_mean:.3f} (95% CI: {mse_lower:.3f} - {mse_upper:.3f})"
        )
        print(
            f"True count  (mean ± std): "
            f"{np.mean(true_counts):.3f} ± {np.std(true_counts):.3f}"
        )
        print(
            f"Pred count  (mean ± std): "
            f"{np.mean(pred_counts):.3f} ± {np.std(pred_counts):.3f}"
        )
        true_freq_counts, pred_freq_counts = zip(*freq_counts)
        print("\nFrequency term counts (for patients with medications):")
        print(
            f"True frequency count  (mean ± std): "
            f"{np.mean(true_freq_counts):.3f} ± {np.std(true_freq_counts):.3f}"
        )
        print(
            f"Pred frequency count  (mean ± std): "
            f"{np.mean(pred_freq_counts):.3f} ± {np.std(pred_freq_counts):.3f}"
        )
    else:
        print("No patients with medications found in the dataset.")

    overall_counts = [
        (count_medications(t), count_medications(p))
        for t, p in zip(all_true_meds, all_pred_meds)
    ]

    overall_freq_counts = [
        (count_medications(t), count_medications(p))
        for t, p in zip(all_true_freqs, all_pred_freqs)
    ]

    if overall_counts:
        true_counts, pred_counts = zip(*overall_counts)
        print(f"All patients: {len(true_counts)}")
        (mae_mean, mae_lower, mae_upper), (mse_mean, mse_lower, mse_upper) = (
            bootstrap_error_metrics(list(true_counts), list(pred_counts))
        )
        print(
            f"MAE: {mae_mean:.3f} (95% CI: {mae_lower:.3f} - {mae_upper:.3f})"
        )
        print(
            f"MSE: {mse_mean:.3f} (95% CI: {mse_lower:.3f} - {mse_upper:.3f})"
        )
        print(
            f"True count  (mean ± std): "
            f"{np.mean(true_counts):.3f} ± {np.std(true_counts):.3f}"
        )
        print(
            f"Pred count  (mean ± std): "
            f"{np.mean(pred_counts):.3f} ± {np.std(pred_counts):.3f}"
        )
        true_freq_counts, pred_freq_counts = zip(*overall_freq_counts)
        print("\nOverall frequency term counts:")
        print(
            f"True frequency count  (mean ± std): "
            f"{np.mean(true_freq_counts):.3f} ± {np.std(true_freq_counts):.3f}"
        )
        print(
            f"Pred frequency count  (mean ± std): "
            f"{np.mean(pred_freq_counts):.3f} ± {np.std(pred_freq_counts):.3f}"
        )
    else:
        print("No patients found in the dataset.")

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
