# matching.py

import re
from typing import Tuple, Optional, Dict
from rapidfuzz.distance import DamerauLevenshtein

from .utils import normalize_whitespace


# ============================================================
# Bounded fuzzy matching
# ============================================================
AUTO_CORRECT_DISTANCE_CUTOFF = 0.25
AMBIGUOUS_DISTANCE_CUTOFF = 0.32
MIN_SCORE_GAP = 0.06


def normalized_dl_distance(a: str, b: str) -> float:
    """
    Returns normalized Damerau-Levenshtein distance in [0, 1].
    0 = exact match
    1 = maximally different
    """
    if not a and not b:
        return 0.0
    dist = DamerauLevenshtein.distance(a, b)
    return dist / max(len(a), len(b), 1)

def score_candidate(token: str, candidate: str) -> float:
    """
    Lower score is better.
    Base score is normalized Damerau-Levenshtein distance, with penalties
    for weak prefix agreement to reduce bad fuzzy matches.
    """
    score = normalized_dl_distance(token, candidate)

    # Small penalty for large length mismatch
    len_diff = abs(len(token) - len(candidate))
    if len_diff >= 4:
        score += 0.08
    elif len_diff >= 2:
        score += 0.03

    return score


def bounded_fuzzy_map_drug(
    token: str,
    canonical_drugs: set,
    synonym_map: Dict[str, str],
    extra_map: Optional[Dict[str, str]] = None
) -> Tuple[Optional[str], str, Optional[str], float]:
    token = normalize_whitespace(token.lower())
    if not token:
        return None, "unmapped", "empty token", float("inf")

    extra_map = extra_map or {}
    all_candidates = sorted(set(synonym_map.keys()) | set(canonical_drugs) | set(extra_map.keys()))

    if token in synonym_map:
        canon = synonym_map[token]
        if canon != token:
            return canon, "corrected", f"exact synonym/brand mapping: {token} -> {canon}", 0.0
        return canon, "clean", None, 0.0

    if token in extra_map:
        canon = extra_map[token]
        if canon != token:
            return canon, "corrected", f"exact extra mapping: {token} -> {canon}", 0.0
        return canon, "clean", None, 0.0

    if token in canonical_drugs:
        return token, "clean", None, 0.0

    # Score every candidate
    scored = []
    for cand in all_candidates:
        score = score_candidate(token, cand)
        scored.append((cand, score))

    scored.sort(key=lambda x: x[1])

    best_term, best_score = scored[0]
    second_term, second_score = scored[1] if len(scored) > 1 else (None, float("inf"))

    canon = synonym_map.get(best_term, extra_map.get(best_term, best_term))
    if canon not in canonical_drugs:
        return None, "ambiguous", f"best fuzzy match '{best_term}' did not map cleanly", best_score

    if best_score <= AUTO_CORRECT_DISTANCE_CUTOFF and (second_score - best_score >= MIN_SCORE_GAP): 
        return (
            canon,
            "corrected",
            f"fuzzy corrected: {token} -> {best_term} -> {canon} "
            f"(distance_score={best_score:.3f}, second={second_score:.3f})",
            best_score,
        )
    
    if best_score <= AMBIGUOUS_DISTANCE_CUTOFF:
        return (
            None,
            "ambiguous",
            f"ambiguous fuzzy match for '{token}'; "
            f"best='{best_term}' score={best_score:.3f}; "
            f"second='{second_term}' score={second_score:.3f}",
            best_score,
        )

    return (
        None,
        "unmapped",
        f"low-confidence fuzzy match for '{token}'; "
        f"best='{best_term}' score={best_score:.3f} second='{second_term}' second_score={second_score:.3f}",
        best_score,
    )


def normalize_combination_drug_name(
    token: str,
    canonical_drugs: set,
    synonym_map: Dict[str, str],
    extra_map: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], str, Optional[str], float]:
    """
    Normalize generic combination strings like:
    - timolol/dorzolamide
    - dorzolamide-timolol
    - brimonidine + timolol

    Returns:
        canonical_combo_name, confidence_flag, correction_note, score
    """
    extra_map = extra_map or {}
    token = normalize_whitespace(token.lower())

    # split only if looks like combination
    if not re.search(r"[\/\-\+]", token):
        return None, "unmapped", None, float("inf")

    parts = [normalize_whitespace(p) for p in re.split(r"[\/\-\+]", token) if normalize_whitespace(p)]
    if len(parts) < 2:
        return None, "unmapped", None, float("inf")

    normalized_parts = []
    confidence_flags = []
    notes = []
    scores = []

    for part in parts:
        canon, flag, note, score = bounded_fuzzy_map_drug(
            token=part,
            canonical_drugs=canonical_drugs,
            synonym_map=synonym_map,
            extra_map=extra_map,
        )
        if canon is None:
            return None, "ambiguous", f"could not normalize combo component '{part}'", score

        # combo components should be single drugs, not full combos
        if "/" in canon:
            return None, "ambiguous", f"combo component '{part}' mapped to combo '{canon}'", score

        normalized_parts.append(canon)
        confidence_flags.append(flag)
        scores.append(score)
        if note:
            notes.append(note)

    combo_name = "/".join(sorted(normalized_parts, key=str.lower))
    combo_score = max(scores) if scores else float("inf")

    if all(flag == "clean" for flag in confidence_flags):
        confidence = "clean"
    elif any(flag in {"ambiguous", "unmapped"} for flag in confidence_flags):
        confidence = "ambiguous"
    else:
        confidence = "corrected"

    correction_note = "; ".join(notes) if notes else f"normalized combo ordering -> {combo_name}"
    return combo_name, confidence, correction_note, combo_score
