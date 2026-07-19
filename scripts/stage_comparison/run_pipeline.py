"""Orchestrate extraction vs revision stage comparison pipeline (Phases 0-5)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .discovery import discover_all
from .extract_filter import print_filter_summary, process_file
from .metrics_eval import (
    format_metric_summary,
    format_overall_metrics_lines,
    pool_overall_metrics,
    run_metrics_for_stage,
)
from .paired_comparison import format_wilcoxon_jaccard_line, interpret_result, run_paired_comparison
from .standardize_stages import output_path_for, save_standardized, standardize_dataframe

REPORT_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/reports/stage_comparison_report.md"
)


def run_phase0():
    return discover_all()


def run_phases1_5(resolved_files, *, checkpoint_only: bool = False):
    all_stats = []
    all_results = []

    for rf in resolved_files:
        if rf.status != "ok" or rf.path is None:
            print(f"Skipping unresolved: {rf.category} / {rf.model}")
            continue

        print(f"\n--- Processing {rf.category} / {rf.model} ---")
        filtered_df, stats = process_file(rf)
        all_stats.append(stats)

        if checkpoint_only and len(all_stats) == 1:
            print(f"Sample filter stats: {stats}")

        std_df = standardize_dataframe(filtered_df, rf.category)
        out_path = save_standardized(std_df, rf.path)
        # Metrics read from saved file so report always matches on-disk outputs.
        std_df = pd.read_excel(out_path)

        if len(all_results) == 0:
            print(f"\nCheckpoint Phase 2 columns ({out_path.name}):")
            stage_cols = [c for c in std_df.columns if "stage_" in c]
            print(stage_cols[:20])
            print(f"... total {len(stage_cols)} stage-related columns")

        m1 = run_metrics_for_stage(std_df, rf.category, "stage_1_output")
        m3 = run_metrics_for_stage(std_df, rf.category, "stage_3_output")

        if len(all_results) == 0:
            print("\nCheckpoint Phase 3 metrics (first file):")
            print(f"  Stage 1: {format_metric_summary(m1)}")
            print(f"  Stage 3: {format_metric_summary(m3)}")

        paired = run_paired_comparison(
            m1["true_diag"], m1["pred_diag"], m3["pred_diag"]
        )

        all_results.append(
            {
                "category": rf.category,
                "model": rf.model,
                "source_path": str(rf.path),
                "output_path": str(out_path),
                "stats": stats,
                "stage1_metrics": m1,
                "stage3_metrics": m3,
                "paired": paired,
                "interpretation": interpret_result(paired),
            }
        )

    print_filter_summary(all_stats)
    report = generate_report(all_results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"\nReport saved to {REPORT_PATH}")
    print("\n" + "=" * 80)
    print(report)
    return all_results


def generate_report(results: list[dict]) -> str:
    lines = [
        "# Extraction vs Revision Stage Comparison Report",
        "",
        "> **Caveat:** These results measure association on rows where revision ran "
        "(`task3_ran == true`), within the evaluation set (`UsedinExamples == False`, "
        "992 rows per file). They do not isolate causal effects of revision logic "
        "versus a no-revision second-attempt baseline.",
        "",
        "Metrics follow `metrics_standardized_topmeds staged.ipynb` (`overall` scenario): "
        "Wilson 95% CIs for EM Accuracy/Sensitivity/Specificity, Precision, Recall; "
        "percentile bootstrap (1000 resamples) for F1, Jaccard, and Gwet AC1.",
        "",
    ]

    # Per model x category
    lines.append("## Per Model × Category\n")
    for r in results:
        s = r["stats"]
        p = r["paired"]
        m1 = r["stage1_metrics"]["overall"]
        m3 = r["stage3_metrics"]["overall"]
        mc = p["mcnemar"]
        lines.extend(
            [
                f"### {r['model']} — {r['category']}",
                "",
                f"- Rows: {s['total_rows']} raw, {s['eval_rows']} eval (UsedinExamples=False), "
                f"{s['filtered_rows']} with task3_ran ({s['task3_ran_rate']:.1%} of eval)",
                "",
            ]
        )
        lines.extend(format_overall_metrics_lines(m1, heading="Stage 1 (extraction)"))
        lines.append("")
        lines.extend(format_overall_metrics_lines(m3, heading="Stage 3 (revision)"))
        lines.extend(
            [
                "",
                "**Paired comparison (Stage 1 vs Stage 3, same ground truth)**",
                f"- Flips: wrong→right={mc['wrong_to_right']}, "
                f"right→wrong={mc['right_to_wrong']}, no change={mc['no_change']}",
                f"- McNemar p={mc['p_value']:.4f}, net flip rate={p['net_flip_rate']:+.3f}",
                format_wilcoxon_jaccard_line(p["wilcoxon_jaccard"]),
                f"- Takeaway: {r['interpretation']}",
                "",
            ]
        )

    # Aggregate by model
    lines.append("## Aggregated by Model\n")
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    for model, rows in sorted(by_model.items()):
        total_n = sum(r["paired"]["N"] for r in rows)
        w2r = sum(r["paired"]["mcnemar"]["wrong_to_right"] for r in rows)
        r2w = sum(r["paired"]["mcnemar"]["right_to_wrong"] for r in rows)
        net = (w2r - r2w) / total_n if total_n else 0
        lines.extend(
            [
                f"### {model}",
                f"- Pooled paired N (eye/row level): {total_n}",
                f"- Pooled flips: wrong→right={w2r}, right→wrong={r2w}, net flip={net:+.3f}",
                "",
            ]
        )
        s1_pool = pool_overall_metrics(rows, "stage_1")
        s3_pool = pool_overall_metrics(rows, "stage_3")
        lines.extend(format_overall_metrics_lines(s1_pool, heading="Stage 1 (pooled)"))
        lines.append("")
        lines.extend(format_overall_metrics_lines(s3_pool, heading="Stage 3 (pooled)"))
        lines.append("")

    # Aggregate by category
    lines.append("## Aggregated by Category\n")
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)

    for cat, rows in sorted(by_cat.items()):
        total_n = sum(r["paired"]["N"] for r in rows)
        w2r = sum(r["paired"]["mcnemar"]["wrong_to_right"] for r in rows)
        r2w = sum(r["paired"]["mcnemar"]["right_to_wrong"] for r in rows)
        lines.extend(
            [
                f"### {cat}",
                f"- Pooled paired N (eye/row level): {total_n}",
                f"- Pooled flips: wrong→right={w2r}, right→wrong={r2w}",
                "",
            ]
        )
        s1_pool = pool_overall_metrics(rows, "stage_1")
        s3_pool = pool_overall_metrics(rows, "stage_3")
        lines.extend(format_overall_metrics_lines(s1_pool, heading="Stage 1 (pooled)"))
        lines.append("")
        lines.extend(format_overall_metrics_lines(s3_pool, heading="Stage 3 (pooled)"))
        lines.append("")

    # Overall
    total_n = sum(r["paired"]["N"] for r in results)
    w2r = sum(r["paired"]["mcnemar"]["wrong_to_right"] for r in results)
    r2w = sum(r["paired"]["mcnemar"]["right_to_wrong"] for r in results)
    lines.append("## Overall Cross-Model, Cross-Category Takeaway\n")
    lines.extend(
        [
            f"- Total paired comparisons: {total_n}",
            f"- Total wrong→right: {w2r}, right→wrong: {r2w}",
            f"- Net improvement rate: {(w2r - r2w) / total_n:+.3f}" if total_n else "",
            "",
        ]
    )
    s1_all = pool_overall_metrics(results, "stage_1")
    s3_all = pool_overall_metrics(results, "stage_3")
    lines.extend(format_overall_metrics_lines(s1_all, heading="Stage 1 (all pooled)"))
    lines.append("")
    lines.extend(format_overall_metrics_lines(s3_all, heading="Stage 3 (all pooled)"))
    lines.extend(
        [
            "",
            "Revision stage outcomes should be interpreted as associative, not causal. "
            "Where McNemar p-values are non-significant or N is small, treat differences as inconclusive.",
        ]
    )
    return "\n".join(lines)


def run_report_only(resolved_files):
    """Regenerate report from existing *_standardized_stage_comp.xlsx files."""
    all_results = []
    for rf in resolved_files:
        if rf.status != "ok" or rf.path is None:
            continue
        out_path = output_path_for(rf.path)
        if not out_path.exists():
            raise FileNotFoundError(f"Missing standardized output: {out_path}")
        _, stats = process_file(rf)
        std_df = pd.read_excel(out_path)
        m1 = run_metrics_for_stage(std_df, rf.category, "stage_1_output")
        m3 = run_metrics_for_stage(std_df, rf.category, "stage_3_output")
        paired = run_paired_comparison(m1["true_diag"], m1["pred_diag"], m3["pred_diag"])
        all_results.append(
            {
                "category": rf.category,
                "model": rf.model,
                "source_path": str(rf.path),
                "output_path": str(out_path),
                "stats": stats,
                "stage1_metrics": m1,
                "stage3_metrics": m3,
                "paired": paired,
                "interpretation": interpret_result(paired),
            }
        )
    report = generate_report(all_results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"Report saved to {REPORT_PATH}")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Stage 1 vs Stage 3 comparison pipeline")
    parser.add_argument(
        "--phase",
        choices=["0", "all", "report"],
        default="all",
        help="Run discovery (0), full pipeline (all), or report-only from existing outputs (report)",
    )
    args = parser.parse_args()

    resolved = run_phase0()
    if args.phase == "0":
        return
    if args.phase == "report":
        run_report_only([r for r in resolved if r.status == "ok"])
        return

    run_phases1_5(resolved)


if __name__ == "__main__":
    main()
