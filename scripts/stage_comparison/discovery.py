"""Phase 0: discover grading result files for all model x category combos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_RESULTS = Path("/media/zyflo/shared_files/slm_ehr/test_results")

CATEGORIES = [
    "top_meds_staged",
    "top_meds_change_staged",
    "oral_meds_staged",
    "oral_meds_change_staged",
]

MODELS = [
    "Claude Opus 4.6",
    "GPT-5.2",
    "DeepSeek V3.2",
    "Grok-4-1-fast-non-reasoning",
    "Qwen3.6-35B-A3B",
]

# Substrings used to match top-level model folders (all must match, case-insensitive).
MODEL_FOLDER_PATTERNS: dict[str, list[str]] = {
    "Claude Opus 4.6": ["claude", "opus", "4"],
    "GPT-5.2": ["gpt", "5.2"],
    "DeepSeek V3.2": ["deepseek", "v3.2"],
    "Grok-4-1-fast-non-reasoning": ["grok", "4", "fast", "non-reasoning"],
    "Qwen3.6-35B-A3B": ["qwen"],
}

# Folders that look like a model name but belong to a different model.
EXCLUDE_FOLDER_PATTERNS: dict[str, list[str]] = {
    "DeepSeek V3.2": ["v4"],
    "Grok-4-1-fast-non-reasoning": ["fast-reasoning"],
    "Qwen3.6-35B-A3B": ["3.5"],
}

SETTINGS_BY_MODEL: dict[str, str] = {
    "DeepSeek V3.2": "minimal",
}
DEFAULT_SETTINGS = "none"

QWEN_VERSION_SUBFOLDER = "qwen3.6-35b-a3b"


@dataclass
class ResolvedFile:
    category: str
    model: str
    model_folder: str
    settings_folder: str
    timestamp_folder: str
    path: Optional[Path]
    status: str  # "ok" or error description


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-").replace(" ", "")


def _matches_model(folder_name: str, model: str) -> bool:
    norm = _normalize(folder_name)
    for pat in MODEL_FOLDER_PATTERNS[model]:
        if _normalize(pat) not in norm:
            return False
    for pat in EXCLUDE_FOLDER_PATTERNS.get(model, []):
        if _normalize(pat) in norm:
            return False
    return True


def _find_model_folder(category_path: Path, model: str) -> Optional[Path]:
    candidates = [
        d for d in category_path.iterdir()
        if d.is_dir() and _matches_model(d.name, model)
    ]
    if model == "Qwen3.6-35B-A3B":
        # Qwen lives under Qwen/<version>/...
        qwen_roots = [d for d in candidates if "qwen" in d.name.lower()]
        if not qwen_roots:
            return None
        qwen_root = qwen_roots[0]
        version_dirs = [
            d for d in qwen_root.iterdir()
            if d.is_dir()
            and QWEN_VERSION_SUBFOLDER in d.name.lower()
            and "3.5" not in d.name.lower()
        ]
        if len(version_dirs) == 1:
            return version_dirs[0]
        if len(version_dirs) > 1:
            # Prefer exact 3.6 match
            exact = [d for d in version_dirs if "3.6" in d.name]
            return exact[0] if len(exact) == 1 else None
        return None

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return None  # ambiguous
    return None


def parse_timestamp_folder(name: str, default_year: int = 2025) -> datetime:
    """Parse MM-DD_HH:MM from names like ``750_04-24_02:42``."""
    m = re.search(r"(\d{2})-(\d{2})_(\d{2}):(\d{2})", name)
    if not m:
        return datetime.min
    month, day, hour, minute = (int(x) for x in m.groups())
    return datetime(default_year, month, day, hour, minute)


def _latest_timestamp_dir(settings_path: Path) -> Optional[Path]:
    ts_dirs = [d for d in settings_path.iterdir() if d.is_dir()]
    if not ts_dirs:
        return None
    return max(ts_dirs, key=lambda d: parse_timestamp_folder(d.name))


def _find_grading_xlsx(ts_dir: Path, category: str) -> Optional[Path]:
    expected = ts_dir / f"grading_results_{category}.xlsx"
    if expected.exists():
        return expected
    matches = sorted(ts_dir.glob("grading_results_*.xlsx"))
    # Prefer non-standardized source file
    non_std = [p for p in matches if "standardized" not in p.name.lower()]
    if non_std:
        return non_std[0]
    return matches[0] if matches else None


def resolve_file(category: str, model: str) -> ResolvedFile:
    category_path = BASE_RESULTS / category
    model_folder_path = _find_model_folder(category_path, model)

    if model_folder_path is None:
        return ResolvedFile(
            category=category,
            model=model,
            model_folder="?",
            settings_folder="?",
            timestamp_folder="?",
            path=None,
            status="Could not match model folder",
        )

    settings_name = SETTINGS_BY_MODEL.get(model, DEFAULT_SETTINGS)
    settings_path = model_folder_path / settings_name
    if not settings_path.is_dir():
        return ResolvedFile(
            category=category,
            model=model,
            model_folder=model_folder_path.name,
            settings_folder=settings_name,
            timestamp_folder="?",
            path=None,
            status=f"Settings folder '{settings_name}' not found",
        )

    ts_dir = _latest_timestamp_dir(settings_path)
    if ts_dir is None:
        return ResolvedFile(
            category=category,
            model=model,
            model_folder=model_folder_path.name,
            settings_folder=settings_name,
            timestamp_folder="?",
            path=None,
            status=f"No timestamp folders under {settings_name}",
        )

    xlsx = _find_grading_xlsx(ts_dir, category)
    if xlsx is None:
        return ResolvedFile(
            category=category,
            model=model,
            model_folder=model_folder_path.name,
            settings_folder=settings_name,
            timestamp_folder=ts_dir.name,
            path=None,
            status="grading_results xlsx not found",
        )

    return ResolvedFile(
        category=category,
        model=model,
        model_folder=model_folder_path.name,
        settings_folder=settings_name,
        timestamp_folder=ts_dir.name,
        path=xlsx,
        status="ok",
    )


def discover_all() -> list[ResolvedFile]:
    results = []
    for category in CATEGORIES:
        folder_map: dict[str, str] = {}
        print(f"\n=== {category} ===")
        print("Model -> matched folder:")
        for model in MODELS:
            rf = resolve_file(category, model)
            results.append(rf)
            folder_map[model] = rf.model_folder
            print(f"  {model:40s} -> {rf.model_folder}")
        print()

    print("\n" + "=" * 120)
    print(f"{'Category':<28} {'Model':<35} {'Status':<8} {'Path'}")
    print("=" * 120)
    for rf in results:
        path_str = str(rf.path) if rf.path else f"UNRESOLVED ({rf.status})"
        print(f"{rf.category:<28} {rf.model:<35} {rf.status:<8} {path_str}")
    print("=" * 120)

    unresolved = [rf for rf in results if rf.status != "ok"]
    if unresolved:
        print(f"\nWARNING: {len(unresolved)} file(s) could not be resolved.")
    else:
        print("\nAll 20 files resolved successfully.")

    return results
