#!/usr/bin/env python3
"""CLI entry for medication extraction evaluation.

Compares standardized grading_results against adjudicated labels and writes a
text report (exact match, Jaccard, Gwet AC1, etc.).

Example:
  python evaluate.py \\
    --input /path/to/grading_results_tmcs_standardized.xlsx \\
    --adjudicated data/adjudicated_meds_last_final_standardized.xlsx \\
    [--cvar top_meds_change_staged | --acronym tmcs]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.column_map import ACRONYM_TO_CVAR, CVAR_TO_ACRONYM  # noqa: E402
from evaluation.runner import run_evaluation  # noqa: E402

DEFAULT_ADJUDICATED = (
    _REPO_ROOT / "data" / "adjudicated_meds_last_final_standardized.xlsx"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate standardized grading_results against adjudicated labels."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to grading_results_{acronym}_standardized.xlsx",
    )
    parser.add_argument(
        "--adjudicated",
        default=str(DEFAULT_ADJUDICATED),
        help=(
            "Path to adjudicated labels xlsx "
            "(default: data/adjudicated_meds_last_final_standardized.xlsx)"
        ),
    )
    parser.add_argument(
        "--cvar",
        choices=sorted(CVAR_TO_ACRONYM),
        default=None,
        help="Staged cvar (inferred from --acronym or input filename if omitted).",
    )
    parser.add_argument(
        "--acronym",
        choices=sorted(ACRONYM_TO_CVAR),
        default=None,
        help="Short acronym tms/tmcs/oms/omcs (inferred if omitted).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-row mismatches.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional report path (default: {acronym}_results.txt beside input).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2
    adjudicated = Path(args.adjudicated)
    if not adjudicated.is_file():
        print(f"Adjudicated labels not found: {adjudicated}", file=sys.stderr)
        return 2

    out = run_evaluation(
        input_path,
        adjudicated,
        cvar=args.cvar,
        acronym=args.acronym,
        verbose=args.verbose,
        output_path=args.output,
    )
    print(f"Wrote report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
