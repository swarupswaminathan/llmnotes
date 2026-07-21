#!/usr/bin/env python3
"""CLI entry for staged medication inference.

Resolves model adapter + prompt config from registries, then runs the grading
loop over clinical notes and writes artifacts under results/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure repo root is on sys.path when invoked as `python main.py`
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config import (  
    DEFAULT_FEWSHOT_XLSX,
    DEFAULT_GRADING_XLSX,
    RESULTS_ROOT,
    RunContext,
    SUPPORTED_CVARS,
    get_model_spec,
)
from models.registry import create_adapter, list_models  
from prompts.registry import get_prompt_config, list_cvars  
from tasks.runner import load_grading_df, run_grading_loop  


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run staged EHR meds inference (config-driven)."
    )
    parser.add_argument(
        "--model_name",
        required=True,
        choices=list_models(),
        help="Model alias from the registry (e.g. qwen, gpt, grok_n).",
    )
    parser.add_argument(
        "--cvar",
        required=True,
        choices=list_cvars(),
        help="Staged prompt type.",
    )
    parser.add_argument("--tok_num", type=int, default=750, help="Token limit.")
    parser.add_argument(
        "--reasoning_effort",
        default="none",
        help="Reasoning effort (validated against model registry).",
    )
    parser.add_argument(
        "--grading_xlsx",
        default=DEFAULT_GRADING_XLSX,
        help="Path to grading labels xlsx.",
    )
    parser.add_argument(
        "--fewshot_xlsx",
        default=DEFAULT_FEWSHOT_XLSX,
        help="Path to few-shot / UsedinExamples xlsx.",
    )
    parser.add_argument(
        "--results_root",
        default=str(RESULTS_ROOT),
        help="Root for output dirs (default: results/).",
    )
    return parser.parse_args(argv)


def make_results_dir(
    results_root: Path, cvar: str, model_name: str, reasoning_effort: str, tok_num: int
) -> Path:
    """Create ``results/{cvar}/{model}/{effort}/{tok_num}_{timestamp}/``."""
    ts = datetime.now().strftime("%m-%d_%H:%M")
    results_dir = results_root / cvar / model_name / reasoning_effort / f"{tok_num}_{ts}"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.cvar not in SUPPORTED_CVARS:
        print(f"Unsupported cvar: {args.cvar}", file=sys.stderr)
        return 2

    spec = get_model_spec(args.model_name)
    task = get_prompt_config(args.cvar)

    results_dir = make_results_dir(
        Path(args.results_root),
        args.cvar,
        spec.model_name,
        args.reasoning_effort,
        args.tok_num,
    )

    with open(results_dir / "prompt_snapshot.txt", "w") as f:
        json.dump(task.prompts, f, indent=2)

    ctx = RunContext(
        results_dir=results_dir,
        logger_path=results_dir / "response_log.txt",
        model_alias=args.model_name,
        model_name=spec.model_name,
        reasoning_effort=args.reasoning_effort,
        tok_num=args.tok_num,
        cvar=args.cvar,
    )

    print(f"Config: {args.cvar}")
    print(f"Model alias: {args.model_name} → {spec.model_name}")
    print(f"Reasoning effort: {args.reasoning_effort}")
    print(f"Token limit: {args.tok_num}")
    print(f"Target columns: {task.target_columns}")
    print(f"Is bilateral: {task.bilateral}")
    print(f"Results dir: {results_dir}")
    print(f"Logging responses to: {ctx.logger_path}")

    adapter = create_adapter(args.model_name, ctx)
    grading_df = load_grading_df(args.grading_xlsx, args.fewshot_xlsx)

    run_grading_loop(
        adapter=adapter,
        task=task,
        ctx=ctx,
        grading_df=grading_df,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
