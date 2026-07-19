"""Generate validation revision pass report (Steps 0–3 task3_ran denominators)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from .discovery import discover_all
from .extract_filter import (
    _coerce_bool,
    _parse_ai_explanation,
    filter_used_in_examples,
    find_used_in_examples_col,
)

REPORT_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/reports/validation_revision_pass_report.md"
)

CAT_LABELS = {
    "top_meds_staged": "CTM",
    "top_meds_change_staged": "ΔTM",
    "oral_meds_staged": "COM",
    "oral_meds_change_staged": "ΔOM",
}

MODEL_ORDER = [
    "Claude Opus 4.6",
    "GPT-5.2",
    "DeepSeek V3.2",
    "Grok-4-1-fast-non-reasoning",
    "Qwen3.6-35B-A3B",
]

CAT_ORDER = [
    "top_meds_staged",
    "top_meds_change_staged",
    "oral_meds_staged",
    "oral_meds_change_staged",
]


def count_task3_ran(df: pd.DataFrame) -> int:
    n = 0
    for raw in df["AI_Explanation"]:
        parsed = _parse_ai_explanation(raw)
        if parsed and _coerce_bool(parsed.get("task3_ran")):
            n += 1
    return n


def collect_stats():
    resolved = [r for r in discover_all() if r.status == "ok" and r.path]
    rows = []
    for rf in resolved:
        df_raw = pd.read_excel(rf.path)
        pre = len(df_raw)
        col = find_used_in_examples_col(df_raw)
        df_eval = filter_used_in_examples(df_raw)
        post = len(df_eval)
        t3 = count_task3_ran(df_eval)
        rows.append(
            {
                "category": rf.category,
                "model": rf.model,
                "path": str(rf.path),
                "pre_filter": pre,
                "post_filter": post,
                "post_filter_ok": post == 992,
                "task3_ran_true": t3,
            }
        )
    return rows


def generate_report(rows: list[dict]) -> str:
    lines = [
        "# Validation Revision Pass Report",
        "",
        "Denominator and `task3_ran == true` counts for the 20 model × category files.",
        "Base evaluation set: `UsedinExamples == False` (992 rows per file).",
        "",
        "---",
        "",
        "## Step 0: Denominator confirmation (`UsedinExamples == False`)",
        "",
        "| Category | Model | Before | After | Flag |",
        "|----------|-------|--------|-------|------|",
    ]

    for r in rows:
        flag = "OK" if r["post_filter_ok"] else f"**EXPECTED 992 GOT {r['post_filter']}**"
        lines.append(
            f"| {r['category']} | {r['model']} | {r['pre_filter']} | {r['post_filter']} | {flag} |"
        )

    all_ok = all(r["post_filter_ok"] for r in rows)
    lines.extend(
        [
            "",
            f"**Result:** {'All 20 files post-filter = 992.' if all_ok else 'WARNING: one or more files ≠ 992.'}",
            "",
            "---",
            "",
            "## Step 1: `task3_ran == true` counts (within 992-row eval set)",
            "",
            "Format: `count/992`",
            "",
        ]
    )

    # Matrix: categories as rows, models as columns
    by_cat_model = {(r["category"], r["model"]): r for r in rows}
    header = "| Category | " + " | ".join(MODEL_ORDER) + " |"
    sep = "|----------|" + "|".join(["--------"] * len(MODEL_ORDER)) + "|"
    lines.extend([header, sep])
    for cat in CAT_ORDER:
        cells = [CAT_LABELS[cat]]
        for model in MODEL_ORDER:
            r = by_cat_model[(cat, model)]
            cells.append(f"{r['task3_ran_true']}/992")
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(["", "### Full 20-row table", ""])
    lines.extend(
        [
            "| Category | Model | task3_ran | Rate |",
            "|----------|-------|-----------|------|",
        ]
    )
    for r in rows:
        rate = r["task3_ran_true"] / r["post_filter"] if r["post_filter"] else 0
        lines.append(
            f"| {r['category']} | {r['model']} | {r['task3_ran_true']}/992 | {rate:.1%} |"
        )

    # Step 2
    lines.extend(["", "---", "", "## Step 2: Per-model average (across 4 categories)", ""])
    lines.extend(
        [
            "| Model | Avg count | Avg rate | Sum (4 cats) |",
            "|-------|-----------|----------|--------------|",
        ]
    )
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    for model in MODEL_ORDER:
        items = by_model[model]
        counts = [x["task3_ran_true"] for x in items]
        avg_c = sum(counts) / len(counts)
        avg_r = sum(c / 992 for c in counts) / len(counts)
        lines.append(
            f"| {model} | {avg_c:.1f} | {avg_r:.1%} | {sum(counts)} |"
        )

    # Step 3
    lines.extend(["", "---", "", "## Step 3: Pooled per category (5 models × 992 = 4,960)", ""])
    lines.extend(
        [
            "| Label | Category | Pooled task3_ran | Denominator |",
            "|-------|----------|------------------|-------------|",
        ]
    )
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    for cat in CAT_ORDER:
        items = by_cat[cat]
        total_t3 = sum(x["task3_ran_true"] for x in items)
        total_denom = sum(x["post_filter"] for x in items)
        expected = 5 * 992
        denom_note = f"{total_denom} (expected {expected})"
        if total_denom != expected:
            denom_note += " **FLAG**"
        lines.append(
            f"| {CAT_LABELS[cat]} | {cat} | {total_t3}/{total_denom} | {denom_note} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Notes",
            "",
            "- Column on disk: `UsedinExamples` (not `UsedInExamples`).",
            "- All `task3_ran == true` rows fall within the 992-row eval set; "
            "no revision-ran rows are in the `UsedinExamples == True` holdout.",
            "- Phase 3/4 metrics in `stage_comparison_report.md` are unchanged "
            "after applying this denominator upstream.",
            "",
            "## Source files",
            "",
        ]
    )
    for r in rows:
        lines.append(f"- `{r['path']}`")

    return "\n".join(lines) + "\n"


def main() -> None:
    rows = collect_stats()
    report = generate_report(rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
