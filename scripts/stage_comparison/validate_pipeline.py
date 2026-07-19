"""Validation checks for the stage comparison pipeline.

Run after the main pipeline to confirm internal consistency:

    .venv/bin/python -m scripts.stage_comparison.validate_pipeline
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .discovery import discover_all
from .extract_filter import (
    extract_stage_columns,
    filter_task3_ran,
    filter_used_in_examples,
    process_file,
)
from .metrics_eval import run_metrics_for_stage
from .paired_comparison import run_paired_comparison
from .standardize_stages import output_path_for


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class FileValidation:
    category: str
    model: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)


def _parse_json_dict(val: Any) -> dict | None:
    if pd.isna(val):
        return None
    try:
        data = json.loads(val) if isinstance(val, str) else val
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _expected_std_columns(category: str) -> list[str]:
    cols = []
    label_type = "change" if "change" in category else "current"
    is_top = category.startswith("top_meds")
    for prefix in ("stage_1_output", "stage_3_output"):
        if is_top:
            for eye in ("od", "os"):
                cols.append(f"{prefix}__standardized_{label_type}_{eye}_json_output")
                cols.append(f"{prefix}__standardized_{label_type}_{eye}_json_error")
        else:
            cols.append(f"{prefix}__standardized_{label_type}_oral_json_output")
            cols.append(f"{prefix}__standardized_{label_type}_oral_json_error")
    return cols


def validate_one(resolved) -> FileValidation:
    fv = FileValidation(category=resolved.category, model=resolved.model)
    out_path = output_path_for(resolved.path)

    # --- output file exists ---
    fv.checks.append(
        CheckResult(
            "output_file_exists",
            out_path.exists(),
            str(out_path) if out_path.exists() else f"missing: {out_path}",
        )
    )
    if not out_path.exists():
        return fv

    df_out = pd.read_excel(out_path)
    df_src = pd.read_excel(resolved.path)

    # --- phase 1: re-extract row count matches saved output ---
    extracted, stats = process_file(resolved)
    fv.checks.append(
        CheckResult(
            "filter_row_count",
            len(extracted) == len(df_out),
            f"re-extract={len(extracted)} saved={len(df_out)}",
        )
    )
    fv.checks.append(
        CheckResult(
            "eval_rows_992",
            stats.get("eval_rows") == 992,
            f"eval_rows={stats.get('eval_rows')}",
        )
    )

    # --- phase 1: all rows have task3_ran ---
    if "task3_ran_parsed" in df_out.columns:
        all_ran = bool(df_out["task3_ran_parsed"].eq(True).all())
        fv.checks.append(
            CheckResult("all_task3_ran", all_ran, f"non-true={ (~df_out['task3_ran_parsed']).sum() }")
        )

    # --- phase 1: stage_3 raw == AI_Diagnosis (final pipeline output) ---
    s3_mismatch = 0
    s1_null = 0
    s3_null = 0
    s1_eq_s3 = 0
    for _, row in df_out.iterrows():
        ai = _parse_json_dict(row.get("AI_Diagnosis"))
        s1 = _parse_json_dict(row.get("stage_1_output"))
        s3 = _parse_json_dict(row.get("stage_3_output"))
        if s1 is None:
            s1_null += 1
        if s3 is None:
            s3_null += 1
        if ai != s3:
            s3_mismatch += 1
        if s1 == s3:
            s1_eq_s3 += 1

    fv.checks.append(
        CheckResult(
            "stage3_matches_ai_diagnosis",
            s3_mismatch == 0,
            f"mismatches={s3_mismatch}/{len(df_out)}",
        )
    )
    fv.checks.append(
        CheckResult(
            "stage_outputs_parseable",
            s1_null == 0 and s3_null == 0,
            f"stage1_null={s1_null} stage3_null={s3_null}",
        )
    )
    fv.checks.append(
        CheckResult(
            "revision_changed_something",
            s1_eq_s3 < len(df_out),
            f"identical s1/s3 rows={s1_eq_s3}/{len(df_out)} (expect <100% when task3 ran)",
        )
    )

    # --- phase 1: filter matches source AI_Explanation (eval rows only) ---
    src_eval = filter_used_in_examples(df_src)
    src_extracted = filter_task3_ran(extract_stage_columns(src_eval))
    src_ids = set(src_extracted["NOTE_ID"].astype(str))
    out_ids = set(df_out["NOTE_ID"].astype(str))
    fv.checks.append(
        CheckResult(
            "note_id_set_matches_source",
            src_ids == out_ids,
            f"only_in_src={len(src_ids-out_ids)} only_in_out={len(out_ids-src_ids)}",
        )
    )

    # --- phase 2: standardized columns present ---
    expected_cols = _expected_std_columns(resolved.category)
    missing = [c for c in expected_cols if c not in df_out.columns]
    fv.checks.append(
        CheckResult(
            "standardized_columns_present",
            len(missing) == 0,
            f"missing={missing[:4]}" + ("..." if len(missing) > 4 else ""),
        )
    )

    # --- phase 2: standardization error rate ---
    err_cols = [c for c in df_out.columns if c.endswith("_json_error") and "stage_" in c]
    err_rows = 0
    for col in err_cols:
        err_rows += df_out[col].notna().sum()
    fv.checks.append(
        CheckResult(
            "standardization_errors_low",
            err_rows == 0,
            f"non-null errors across stage std cols={err_rows}",
        )
    )

    # --- phase 3: metrics run without exception + internal counts ---
    try:
        m1 = run_metrics_for_stage(df_out, resolved.category, "stage_1_output")
        m3 = run_metrics_for_stage(df_out, resolved.category, "stage_3_output")
        n1 = m1["overall"]["N"]
        n3 = m3["overall"]["N"]
        is_top = resolved.category.startswith("top_meds")
        expected_n_min = len(df_out) if not is_top else len(df_out)  # eye-level >= row count
        fv.checks.append(
            CheckResult(
                "metrics_runs",
                n1 > 0 and n3 > 0 and n1 == n3,
                f"stage1_N={n1} stage3_N={n3} rows={len(df_out)}",
            )
        )

        # --- phase 4: paired stats arithmetic ---
        paired = run_paired_comparison(m1["true_diag"], m1["pred_diag"], m3["pred_diag"])
        mc = paired["mcnemar"]
        flip_sum = mc["wrong_to_right"] + mc["right_to_wrong"] + mc["no_change"]
        acc_ok = abs(paired["stage1_accuracy"] - sum(t == p for t, p in zip(m1["true_diag"], m1["pred_diag"])) / paired["N"]) < 1e-9
        fv.checks.append(
            CheckResult(
                "paired_flip_arithmetic",
                flip_sum == paired["N"],
                f"w2r+r2w+same={flip_sum} N={paired['N']}",
            )
        )
        fv.checks.append(
            CheckResult("paired_accuracy_consistent", acc_ok, f"stage1_acc={paired['stage1_accuracy']:.4f}")
        )
    except Exception as exc:
        fv.checks.append(CheckResult("metrics_runs", False, f"exception: {exc}"))

    return fv


def print_report(results: list[FileValidation]) -> int:
    failures = 0
    print("\n" + "=" * 100)
    print("STAGE COMPARISON PIPELINE VALIDATION")
    print("=" * 100)

    for fv in results:
        status = "PASS" if fv.ok else "FAIL"
        if not fv.ok:
            failures += 1
        print(f"\n[{status}] {fv.category} / {fv.model}")
        for c in fv.checks:
            mark = "ok" if c.passed else "FAIL"
            detail = f" — {c.detail}" if c.detail else ""
            print(f"  [{mark}] {c.name}{detail}")

    print("\n" + "=" * 100)
    passed_files = sum(1 for fv in results if fv.ok)
    print(f"Summary: {passed_files}/{len(results)} files passed all checks")
    if failures:
        print(f"WARNING: {failures} file(s) had failing checks — review above before trusting results.")
    else:
        print("All checks passed. Pipeline outputs are internally consistent.")
    print("=" * 100)
    return failures


def main() -> None:
    resolved = discover_all()
    ok_files = [r for r in resolved if r.status == "ok" and r.path is not None]
    if len(ok_files) != 20:
        print(f"WARNING: expected 20 resolved files, got {len(ok_files)}", file=sys.stderr)

    results = [validate_one(r) for r in ok_files]
    n_fail = print_report(results)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
