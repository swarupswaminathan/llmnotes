"""Evaluate standardized grading results against adjudicated labels.

Modules:
  column_map — cvar/acronym resolution and column name maps
  load       — merge grading xlsx with adjudicated labels
  extract    — pull drug/freq/change lists from cells or JSON
  metrics    — agreement metrics (EM, Jaccard, Gwet AC1, etc.)
  topical    — bilateral OD/OS evaluation
  oral       — note-level oral evaluation
  runner     — CLI orchestration and report tee
"""

from evaluation.runner import run_evaluation

__all__ = ["run_evaluation"]
