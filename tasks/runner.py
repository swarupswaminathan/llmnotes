"""Entry that runs the staged path for the selected cvar over the grading set."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config import RunContext, ServerFailureError
from extraction.extractor import (
    extract_json_content,
    is_bilateral,
    normalize_value,
    output_keys_for,
    target_columns_for,
)
from models.base import BaseAdapter
from output.results_writer import ResultsWriter
from prompts.registry import PromptConfig
from tasks.staged import run_staged_meds


def load_grading_df(grading_xlsx: str | Path, fewshot_xlsx: str | Path) -> pd.DataFrame:
    """Load and filter grading notes (Cell 6)."""
    grading_df = pd.read_excel(grading_xlsx)
    few_shot_df = pd.read_excel(fewshot_xlsx)
    grading_df = grading_df[grading_df["Glaucoma OD"].notna()]
    grading_df = grading_df.merge(
        few_shot_df[["PAT_ENC_CSN_ID", "NOTE_ID", "UsedinExamples"]],
        on=["PAT_ENC_CSN_ID", "NOTE_ID"],
        how="left",
    )
    return grading_df


def run_grading_loop(
    *,
    adapter: BaseAdapter,
    task: PromptConfig,
    ctx: RunContext,
    grading_df: pd.DataFrame,
) -> None:
    """Main loop lifted from Cell 28 (staged path only)."""
    writer = ResultsWriter(ctx)
    scores: list = []
    max_count = 0
    prompt_count = 0
    acc = 0.0
    token_drought_acc = 1.0
    prompt_drought_acc = 1.0
    target_columns = task.target_columns
    if isinstance(target_columns, str):
        # Cell 28 unary path indexes with the string column name directly
        pass

    for idx, (note, contact_date, used_in_examples) in enumerate(
        tqdm(
            zip(
                grading_df["Combined_NOTE_TEXT"],
                grading_df["ENC_CONTACT_DATE"],
                grading_df["UsedinExamples"],
            ),
            desc="Processing Notes",
            total=len(grading_df),
        )
    ):
        verbose = True

        if used_in_examples != "Val":  # noqa: E712 — match notebook
            grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Diagnosis"] = None
            continue

        note_changed = (
            f"The encounter date corresponding to this note is: {contact_date}:\n {note}"
        )
        print(f"\nProcessing note {idx + 1}/{len(grading_df)} (used_in_examples={used_in_examples})")

        try:
            final_results = run_staged_meds(
                adapter,
                task,
                ctx,
                note=note_changed,
                idx=idx,
                verbose=verbose,
                max_count=max_count,
                prompt_count=prompt_count,
            )
            ai_diag = final_results["ai_diag"]
            ai_overview = final_results["ai_overview"]
            ai_reasoning = final_results["ai_reasoning"]
            max_count = final_results["max_count"]
            prompt_count = final_results["prompt_count"]

        except ServerFailureError as e:
            print(f"Server failure on note {idx + 1}: {e}")
            writer.log_server_failure(idx, e)
            continue
        except Exception as e:
            print(f"Error processing note {idx + 1}: {e}")
            writer.log_error(idx, e)
            grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Diagnosis"] = "None (failed)"
            grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Explanation"] = "None (failed)"
            grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Reasoning"] = "None (failed)"
            continue

        grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Diagnosis"] = ai_diag
        grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Explanation"] = ai_overview
        grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, "AI_Reasoning"] = ai_reasoning

        writer.write_grading_xlsx(grading_df, ctx.cvar)
        writer.write_max_count_tracker(ctx.cvar, ctx.global_max_count)

        extracted, _ = extract_json_content(ai_diag, ctx.cvar)

        if is_bilateral(ctx.cvar):
            cols = target_columns_for(ctx.cvar)
            target_od = grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, cols[0]].values[0]
            target_os = grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, cols[1]].values[0]
            target_od = "None" if pd.isna(target_od) else target_od
            target_os = "None" if pd.isna(target_os) else target_os
            og_od, og_os = target_od, target_os
            target_od = normalize_value(target_od, ctx.cvar)
            target_os = normalize_value(target_os, ctx.cvar)
            if og_od != target_od or og_os != target_os:
                print(f"Normalized - Original OD: {og_od}, Original OS: {og_os}")

            match_od = 1 if extracted.get("OD") == target_od else 0
            match_os = 1 if extracted.get("OS") == target_os else 0
            scores.append([match_od, match_os])
            acc = (sum(s[0] for s in scores) + sum(s[1] for s in scores)) / (len(scores) * 2)
        else:
            cols = target_columns_for(ctx.cvar)
            target = grading_df.loc[grading_df["Combined_NOTE_TEXT"] == note, cols[0]].values[0]
            target = "None" if pd.isna(target) else target
            target = normalize_value(target, ctx.cvar)
            target_str = str(target).lower() if target is not None else ""

            extracted, _ = extract_json_content(ai_diag, ctx.cvar)
            key = output_keys_for(ctx.cvar)[0]
            extracted_val = extracted.get(key, "")

            if ai_diag is None:
                match = 0
            elif extracted_val:
                match = int(extracted_val.lower() == target_str)
            else:
                match = int(target_str in str(ai_diag).lower())

            scores.append(match)
            acc = sum(scores) / len(scores)
            print(f"Target: {target}, Extracted: {extracted_val}, Match: {match}")

        token_drought_acc = 1 - (max_count / (idx + 1))
        prompt_drought_acc = 1 - (prompt_count / (idx + 1))
        print(
            f"acc: {acc:.2f}, token_drought_acc: {token_drought_acc:.2f}, "
            f"prompt_drought_acc: {prompt_drought_acc:.2f}"
        )
        print(extracted)
        print("-" * 80)

    writer.write_grading_xlsx(grading_df, ctx.cvar)
    writer.write_stats(
        cvar=ctx.cvar,
        target_columns=task.target_columns,
        bilateral=is_bilateral(ctx.cvar),
        acc=acc,
        token_drought_acc=token_drought_acc,
        prompt_drought_acc=prompt_drought_acc,
        max_count=max_count,
    )
    print(f"\nResults saved to {ctx.results_dir}")
