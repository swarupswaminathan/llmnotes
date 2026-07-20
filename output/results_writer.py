"""Persist grading xlsx, stats, failure logs, and trackers under results_dir."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import RunContext


class ResultsWriter:
    """Filesystem writer for a single inference run's artifacts."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.results_dir = Path(ctx.results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.server_fail_log = self.results_dir / "server_failures.txt"

    def write_grading_xlsx(self, grading_df: pd.DataFrame, cvar: str) -> None:
        path = self.results_dir / f"grading_results_{cvar}.xlsx"
        grading_df.to_excel(path, index=False)

    def write_max_count_tracker(self, cvar: str, global_max_count: int) -> None:
        path = self.results_dir / "max_count_tracker.txt"
        with open(path, "w") as f:
            f.write(f"Config: {cvar}, Max Count: {global_max_count}\n")

    def log_server_failure(self, idx: int, error: Exception) -> None:
        with open(self.server_fail_log, "a") as f:
            f.write(f"{idx}\n")

    def log_error(self, idx: int, error: Exception) -> None:
        with open(self.ctx.logger_path, "a") as f:
            f.write(f"Error processing note {idx + 1}: {error}\n")

    def write_stats(
        self,
        *,
        cvar: str,
        target_columns,
        bilateral: bool,
        acc: float,
        token_drought_acc: float,
        prompt_drought_acc: float,
        max_count: int,
    ) -> None:
        stats_path = self.results_dir / "stats.txt"
        with open(stats_path, "w") as f:
            f.write(f"Config: {cvar}\n")
            f.write(f"Target columns: {target_columns}\n")
            f.write(f"Is bilateral: {bilateral}\n")
            f.write(
                f"acc: {acc:.2f}, token_drought_acc: {token_drought_acc:.2f}, "
                f"prompt_drought_acc: {prompt_drought_acc:.2f}, total misses: {max_count}\n"
            )
