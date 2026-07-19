"""One generalized staged-meds routine parameterized by PromptConfig."""

from __future__ import annotations

import json
from typing import Any

from config import RunContext, ServerFailureError
from extraction.extractor import extract_json_content, join_fields
from models.base import BaseAdapter
from prompts.registry import PromptConfig


def _format_citations(task: PromptConfig, parsed: dict) -> str | None:
    """Build citation string(s) from extract/revise JSON."""
    parts = []
    for label_key, json_key in task.citation_json_keys.items():
        parts.append(
            f"{label_key} {task.citation_label}: {parsed.get(json_key, '')}"
        )
    if task.bilateral:
        return join_fields(*parts)
    return parts[0] if parts else None


def _format_validation_reasons(task: PromptConfig, parsed: dict) -> str | None:
    parts = []
    for label_key, json_key in task.validation_reason_keys.items():
        # Oral uses "Oral Reason:"; bilateral uses "OD Reason:"
        suffix = "Reason" if task.bilateral else "Reason"
        parts.append(f"{label_key} {suffix}: {parsed.get(json_key, '')}")
    if task.bilateral:
        return join_fields(*parts)
    return parts[0] if parts else None


def _format_validation_labels(task: PromptConfig, parsed: dict) -> str | None:
    parts = [f"{k}: {parsed.get(k, '')}" for k in task.label_keys]
    if task.bilateral:
        return join_fields(*parts)
    return parts[0] if parts else None


def _extract_labels(task: PromptConfig, parsed: dict) -> dict[str, str]:
    return {k: parsed.get(k, "") for k in task.label_keys}


def _validation_passed(task: PromptConfig, t2_valid: bool, t2_json: dict) -> bool:
    if not t2_valid:
        return False
    return all(t2_json.get(k) == "Yes" for k in task.label_keys)


def _t3_succeeded(task: PromptConfig, t3_valid: bool, t3_json: dict) -> bool:
    if not t3_valid:
        return False
    return all(t3_json.get(k) != "None (failed)" for k in task.label_keys)


def _build_ai_reasoning(
    task: PromptConfig,
    *,
    initial_citation: str | None,
    initial_reasoning: str | None,
    validation_citations: str | None,
    final_citations: str | None,
    final_reasoning: str | None,
) -> str:
    if task.reasoning_json_key:
        # top_meds_staged shape
        return json.dumps(
            {
                "task1_reasoning": initial_reasoning,
                "task1_citation": initial_citation,
                "task2_reasoning": validation_citations,
                "task3_reasoning": final_reasoning,
                "task3_citation": final_citations,
            }
        )
    # top_meds_change / oral shape
    return json.dumps(
        {
            "task1_reasoning": initial_citation,
            "task2_reasoning": validation_citations,
            "task3_reasoning": final_citations,
        }
    )


def run_staged_meds(
    adapter: BaseAdapter,
    task: PromptConfig,
    ctx: RunContext,
    *,
    note: str,
    idx: int,
    verbose: bool,
    max_count: int,
    prompt_count: int,
) -> dict[str, Any]:
    """
    Pipeline per note:
        Task 1: Extract initial labels with citations
        Task 2: Validate those labels
        Task 3: Revise only if Task 2 flagged errors (skipped otherwise)
    """
    model = ctx.model_name

    def log(msg: str) -> None:
        if not verbose:
            return
        if task.log_idx_limit is not None and idx > task.log_idx_limit:
            return
        print(f"[{model}] idx={idx} {msg}")
        with open(ctx.logger_path, "a") as f:
            f.write(f"[{model}] idx={idx} {msg}\n")

    def run_task(
        cfg_key: str, note_input: str, prev: dict, stage_num: int
    ) -> tuple[dict, dict, bool]:
        schema = task.schema_for_stage(stage_num)
        schema_key = 1 if stage_num in (1, 3) else 2
        print(
            f"Stage {'1 or 3 - extraction or revision' if schema_key == 1 else '2 - validation'}"
        )
        result = adapter.generate(
            note=note_input,
            cfg=task.prompts[cfg_key],
            schema_properties=schema.properties,
            schema_required=schema.required,
            stage=stage_num,
            verbose=verbose,
            max_count=prev["max_count"],
            prompt_count=prev["prompt_count"],
        )
        parsed, valid = extract_json_content(result["response"], task.cvar)
        return result, parsed, valid

    current = {"max_count": max_count, "prompt_count": prompt_count}

    try:
        # ── Task 1: Label extraction ──────────────────────────────────────
        log("Task 1: extracting labels...")
        t1_result, t1_json, t1_valid = run_task(
            "task1_label", f"Original note:\n{note}", current, stage_num=1
        )
        current = t1_result

        initial_labels: dict[str, str]
        initial_citation = None
        initial_reasoning = None
        if t1_valid:
            initial_labels = _extract_labels(task, t1_json)
            initial_citation = _format_citations(task, t1_json)
            if task.reasoning_json_key:
                initial_reasoning = t1_json.get(task.reasoning_json_key)
        else:
            log("Task 1: failed to extract valid JSON, defaulting labels to None (failed)")
            initial_labels = task.failed_labels()

        # ── Task 2: Validation ────────────────────────────────────────────
        log(
            f"Task 2: validating... initial={initial_labels}, "
            f"citation={initial_citation}, reasoning={initial_reasoning}"
            if task.t2_includes_reasoning
            else f"Task 2: validating... initial={initial_labels}"
        )
        if task.t2_includes_reasoning:
            t2_input = (
                f"Original note:\n{note}\n\n"
                f"Extracted labels:\n{initial_labels}\n\n"
                f"Extracted citations:\n{initial_citation}\n\n"
                f"Extracted reasoning:\n{initial_reasoning}\n\n"
            )
        else:
            t2_input = (
                f"Original note:\n{note}\n\n"
                f"Extracted labels:\n{initial_labels}\n\n"
                f"Extracted citations and reasoning:\n{initial_citation}\n\n"
            )
        t2_result, t2_json, t2_valid = run_task(
            "task2_validate", t2_input, current, stage_num=2
        )
        current = t2_result

        validation_labels = None
        validation_citations = None
        if t2_valid:
            validation_labels = _format_validation_labels(task, t2_json)
            validation_citations = _format_validation_reasons(task, t2_json)
            print(f"Validation explanation: {validation_citations}")

        # ── Task 3: Revision (only if validation flagged errors) ──────────
        task3_ran = False
        final_labels = initial_labels
        final_citations = None
        final_reasoning = None

        if not _validation_passed(task, t2_valid, t2_json):
            log(f"Task 3: revising... validation={validation_labels}")
            t3_input = (
                f"Labels requiring Revision:\n{initial_labels}\n\n"
                f"Validation results:\n{validation_labels}\n\n"
                f"Revision Rationale:\n{validation_citations}\n\n"
                f"Original note:\n{note}"
            )
            print(
                f"Labels requiring revision: {initial_labels}, \n"
                f"Validation: {validation_labels}, \n"
                f"Citation: {validation_citations}"
            )
            t3_result, t3_json, t3_valid = run_task(
                "task3_revise", t3_input, current, stage_num=3
            )
            current = t3_result
            task3_ran = True

            if not task.bilateral:
                print(f"Task 3 revision result: {t3_json}, succeeded: {_t3_succeeded(task, t3_valid, t3_json)}")

            if _t3_succeeded(task, t3_valid, t3_json):
                final_labels = _extract_labels(task, t3_json)
                final_citations = _format_citations(task, t3_json)
                if task.reasoning_json_key:
                    final_reasoning = t3_json.get(task.reasoning_json_key)
            elif t3_valid and not t1_valid:
                final_labels = task.none_labels()
                final_citations = _format_citations(task, t3_json)
                if task.reasoning_json_key:
                    final_reasoning = t3_json.get(task.reasoning_json_key)
                log("Task 3: revision echoed failed input, defaulting to None")
            elif t1_valid:
                final_labels = initial_labels
                log("Task 3: revision response invalid, keeping initial labels")
            else:
                final_labels = task.failed_labels()
        else:
            log("Task 3: skipped — validation passed")
            if not t1_valid and t2_valid:
                final_labels = task.none_labels()

        return {
            "idx": idx,
            "model": model,
            "ai_diag": json.dumps(final_labels),
            "ai_overview": json.dumps(
                {
                    "task1_initial": initial_labels,
                    "task2_validation": validation_labels,
                    "task3_final": final_labels,
                    "task3_ran": task3_ran,
                }
            ),
            "ai_reasoning": _build_ai_reasoning(
                task,
                initial_citation=initial_citation,
                initial_reasoning=initial_reasoning,
                validation_citations=validation_citations,
                final_citations=final_citations,
                final_reasoning=final_reasoning,
            ),
            "max_count": current["max_count"],
            "prompt_count": current["prompt_count"],
            "error": None,
        }

    except ServerFailureError:
        raise
    except Exception as e:
        print(f"Error — staged note {idx + 1}, model {model}: {e}")
        return {
            "idx": idx,
            "model": model,
            "ai_diag": None,
            "ai_overview": None,
            "ai_reasoning": None,
            "max_count": max_count,
            "prompt_count": prompt_count,
            "error": str(e),
        }
