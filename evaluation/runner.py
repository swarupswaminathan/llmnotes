"""Orchestrate load → topical/oral evaluation → tee report to disk.

Pipeline position (do not re-run inference or standardization here):
  Inference → grading_results_{cvar}.xlsx
  → standardization → grading_results_{acronym}_standardized.xlsx
  → this evaluation → {acronym}_results.txt
"""

from __future__ import annotations

import sys
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

from evaluation.column_map import resolve_eval_spec
from evaluation.load import load_and_merge
from evaluation.oral import run_oral_evaluation
from evaluation.topical import run_topical_evaluation

warnings.filterwarnings("ignore")


class _Tee:
    """Write to multiple streams (console + results file)."""

    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for s in self.streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self.streams:
            s.flush()


@contextmanager
def tee_stdout(path: Path) -> Iterator[Path]:
    """Temporarily tee stdout to ``path`` as well as the console."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        old = sys.stdout
        sys.stdout = _Tee(old, fh)  # type: ignore[assignment]
        try:
            yield path
        finally:
            sys.stdout = old


def run_evaluation(
    input_path: str | Path,
    adjudicated_path: str | Path,
    *,
    cvar: str | None = None,
    acronym: str | None = None,
    verbose: bool = False,
    output_path: str | Path | None = None,
) -> Path:
    """Run evaluation and write ``{acronym}_results.txt`` beside the input xlsx."""
    input_path = Path(input_path)
    adjudicated_path = Path(adjudicated_path)
    spec = resolve_eval_spec(input_path, cvar=cvar, acronym=acronym)

    if output_path is None:
        output_path = input_path.parent / f"{spec.acronym}_results.txt"
    else:
        output_path = Path(output_path)

    with tee_stdout(output_path):
        print(f"Input: {input_path}")
        print(f"Adjudicated labels: {adjudicated_path}")
        print(f"cvar={spec.cvar} acronym={spec.acronym}")
        print(f"is_topical={spec.is_topical} has_change={spec.has_change}")
        print(f"column map key: {spec.map_key}")
        print(f"Report: {output_path}")
        print()

        loaded = load_and_merge(input_path, adjudicated_path, spec)

        if spec.is_topical:
            run_topical_evaluation(loaded, verbose=verbose)
        else:
            run_oral_evaluation(loaded, verbose=verbose)

    return output_path
