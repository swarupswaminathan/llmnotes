"""Provider adapter base interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config import RunContext, ServerFailureError


class BaseAdapter(ABC):
    """Common interface: generate(prompt/note) -> response dict."""

    def __init__(self, client: Any, ctx: RunContext, spec: Any):
        self.client = client
        self.ctx = ctx
        self.spec = spec

    @abstractmethod
    def generate(
        self,
        note: str,
        cfg: str,
        *,
        schema_properties: dict,
        schema_required: list[str],
        stage: int | None = None,
        verbose: bool = False,
        max_count: int = 0,
        prompt_count: int = 0,
    ) -> dict:
        """Call the provider and return {response, explanation, max_count, prompt_count, ...}."""

    def _maybe_log_params(self, params_log: dict) -> None:
        if self.ctx.params_logged:
            return
        import json

        path = self.ctx.results_dir / "params_log.json"
        with open(path, "w") as f:
            json.dump(params_log, f, indent=2)
        self.ctx.params_logged = True

    def _log_verbose(self, msg: str) -> None:
        print(msg)
        with open(self.ctx.logger_path, "a") as f:
            f.write(msg + "\n")


__all__ = ["BaseAdapter", "ServerFailureError"]
