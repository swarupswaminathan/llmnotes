"""Topical (bilateral OD/OS) medication evaluation against adjudicated labels.

Drops rows with missing labels flagged for failed_match, extracts per-eye
drugs / frequencies / change phrases, then prints agreement scenarios.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from evaluation.extract import get_drugs_freqs_terms_topical
from evaluation.load import LoadedEvalData, TopicalColumns
from evaluation.metrics import (
    bootstrap_error_metrics,
    bootstrap_jaccard_ci,
    count_medications,
    evaluate_scenario,
    has_medications,
)


def _preprocess_topical(df: pd.DataFrame, cols: TopicalColumns) -> pd.DataFrame:
    """Normalize OD/OS columns and drop missing / failed-prediction rows."""
    df = df.copy()
    df["original_index"] = df.index

    before = len(df)
    missing_rows = (
        ((df[cols.target_checker_os] == 1) & df[cols.target_os].isna())
        | ((df[cols.target_checker_od] == 1) & df[cols.target_od].isna())
        | ((df[cols.pred_checker_os] == 1) & df[cols.pred_os].isna())
        | ((df[cols.pred_checker_od] == 1) & df[cols.pred_od].isna())
    )
    df = df[~missing_rows].reset_index(drop=True)
    after = len(df)
    print(
        f"Removed {before - after} rows with missing AI_Meds for both eyes. "
        f"Remaining rows: {after}"
    )

    for col in [cols.pred_os, cols.pred_od, cols.target_os, cols.target_od]:
        df[col] = df[col].str.lower().fillna("no")

    df = df[df[cols.pred_os] != "none (failed)"]
    df = df[df[cols.pred_od] != "none (failed)"]
    new_after = len(df)
    print(
        f"Removed {after - new_after} rows with 'none (failed)' predictions. "
        f"Remaining rows: {new_after}"
    )

    for col in [cols.pred_os, cols.pred_od, cols.target_os, cols.target_od]:
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


def _extract_topical(
    df: pd.DataFrame, cols: TopicalColumns, has_change: bool
) -> pd.DataFrame:
    """Attach per-eye target/pred drug, frequency, and change columns."""
    for eye, suffix in [("OD", "od"), ("OS", "os")]:
        target_json = cols.target_json_od if suffix == "od" else cols.target_json_os
        pred_json = cols.pred_json_od if suffix == "od" else cols.pred_json_os
        target_raw = cols.target_od if suffix == "od" else cols.target_os
        pred_raw = cols.pred_od if suffix == "od" else cols.pred_os

        (
            df[f"target_drugs_{suffix}"],
            df[f"target_freqs_{suffix}"],
            df[f"target_change_{suffix}"],
        ) = zip(
            *df.apply(
                lambda row, tj=target_json, tr=target_raw: get_drugs_freqs_terms_topical(
                    row[tj], row[tr], eye, change=has_change
                ),
                axis=1,
            )
        )
        (
            df[f"pred_drugs_{suffix}"],
            df[f"pred_freqs_{suffix}"],
            df[f"pred_change_{suffix}"],
        ) = zip(
            *df.apply(
                lambda row, pj=pred_json, pr=pred_raw: get_drugs_freqs_terms_topical(
                    row[pj], row[pr], eye, change=has_change
                ),
                axis=1,
            )
        )

    print("Medication extraction completed.")
    return df


def run_topical_evaluation(
    loaded: LoadedEvalData, *, verbose: bool = False
) -> None:
    """Run full topical analysis and print metric scenarios to stdout."""
    if loaded.topical is None:
        raise ValueError("LoadedEvalData.topical is required for topical eval")

    cols = loaded.topical
    has_change = loaded.spec.has_change
    df = _preprocess_topical(loaded.df, cols)
    df = _extract_topical(df, cols, has_change)

    print("Starting analysis for both eyes combined...")

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
        for suffix, target_raw, pred_raw in [
            ("od", cols.target_od, cols.pred_od),
            ("os", cols.target_os, cols.pred_os),
        ]:
            all_true_diagnosis.append(row[target_raw])
            all_pred_diagnosis.append(row[pred_raw])
            all_true_meds.append(row[f"target_drugs_{suffix}"])
            all_pred_meds.append(row[f"pred_drugs_{suffix}"])
            all_true_freqs.append(row[f"target_freqs_{suffix}"])
            all_pred_freqs.append(row[f"pred_freqs_{suffix}"])
            if has_change:
                all_true_changes.append(row[f"target_change_{suffix}"])
                all_pred_changes.append(row[f"pred_change_{suffix}"])
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
    evaluate_scenario(pos_true_meds, pos_pred_meds, "med_name")
    evaluate_scenario(pos_true_freqs, pos_pred_freqs, "freq_only")
    evaluate_scenario(positive_true, positive_pred, "positives_only")
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

    counts = [
        (count_medications(t), count_medications(p))
        for t, p in zip(all_true_meds, all_pred_meds)
        if has_medications(t)
    ]

    change_counts = None
    if has_change:
        change_counts = [
            (count_medications(t), count_medications(p))
            for t, p in zip(all_true_changes, all_pred_changes)
            if has_medications(t)
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
        print(
            f"True count  (median [IQR]): {np.median(true_counts):.3f} "
            f"[{np.percentile(true_counts, 25):.3f} – "
            f"{np.percentile(true_counts, 75):.3f}]"
        )
        print(
            f"Pred count  (median [IQR]): {np.median(pred_counts):.3f} "
            f"[{np.percentile(pred_counts, 25):.3f} – "
            f"{np.percentile(pred_counts, 75):.3f}]"
        )
        if has_change and change_counts:
            true_change_counts, pred_change_counts = zip(*change_counts)
            print("\nChange term counts (for patients with medications):")
            print(
                f"True change count  (mean ± std): "
                f"{np.mean(true_change_counts):.3f} ± "
                f"{np.std(true_change_counts):.3f}"
            )
            print(
                f"Pred change count  (mean ± std): "
                f"{np.mean(pred_change_counts):.3f} ± "
                f"{np.std(pred_change_counts):.3f}"
            )
            print(
                f"True change count  (median [IQR]): "
                f"{np.median(true_change_counts):.3f} "
                f"[{np.percentile(true_change_counts, 25):.3f} – "
                f"{np.percentile(true_change_counts, 75):.3f}]"
            )
            print(
                f"Pred change count  (median [IQR]): "
                f"{np.median(pred_change_counts):.3f} "
                f"[{np.percentile(pred_change_counts, 25):.3f} – "
                f"{np.percentile(pred_change_counts, 75):.3f}]"
            )
    else:
        print("No patients with medications found in the dataset.")

    print("\n" + "=" * 60)
    print("MSE AND MAE FOR OVERALL COUNTS (ALL PATIENTS)")
    print("=" * 60)

    overall_counts = [
        (count_medications(t), count_medications(p))
        for t, p in zip(all_true_meds, all_pred_meds)
    ]

    overall_change_counts = (
        [
            (count_medications(t), count_medications(p))
            for t, p in zip(all_true_changes, all_pred_changes)
        ]
        if has_change
        else None
    )

    if overall_counts:
        true_counts, pred_counts = zip(*overall_counts)
        print(f"Overall patients: {len(true_counts)}")
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
        print(
            f"True count  (median [IQR]): {np.median(true_counts):.3f} "
            f"[{np.percentile(true_counts, 25):.3f} – "
            f"{np.percentile(true_counts, 75):.3f}]"
        )
        print(
            f"Pred count  (median [IQR]): {np.median(pred_counts):.3f} "
            f"[{np.percentile(pred_counts, 25):.3f} – "
            f"{np.percentile(pred_counts, 75):.3f}]"
        )
        if has_change and overall_change_counts:
            true_change_counts, pred_change_counts = zip(*overall_change_counts)
            print("\nOverall change term counts:")
            print(
                f"True change count  (mean ± std): "
                f"{np.mean(true_change_counts):.3f} ± "
                f"{np.std(true_change_counts):.3f}"
            )
            print(
                f"Pred change count  (mean ± std): "
                f"{np.mean(pred_change_counts):.3f} ± "
                f"{np.std(pred_change_counts):.3f}"
            )
            print(
                f"True change count  (median [IQR]): "
                f"{np.median(true_change_counts):.3f} "
                f"[{np.percentile(true_change_counts, 25):.3f} – "
                f"{np.percentile(true_change_counts, 75):.3f}]"
            )
            print(
                f"Pred change count  (median [IQR]): "
                f"{np.median(pred_change_counts):.3f} "
                f"[{np.percentile(pred_change_counts, 25):.3f} – "
                f"{np.percentile(pred_change_counts, 75):.3f}]"
            )
    else:
        print("No patients with medications found in the dataset.")

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
