# utils.py

import re
from typing import Tuple, Optional, List

from .models import ParsedMedication, ParsedMedicationChange
from .constants import (
    ARTIFICIAL_TEAR_SYNONYMS,
    CHANGE_PRIORITY,
    CHANGE_SYNONYMS,
    FREQUENCY_MAP,
    LATERALITY_MAP,
    LATERALITY_UNKNOWN_PLACEHOLDER,
    NONE_TOKENS,
    NONESSENTIAL_MED_WORDS,
    SERUM_TEAR_PATTERNS,
    UNSPECIFIED_TOKEN,
)

# ============================================================
# Utility functions
# ============================================================

def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def remove_nonessential_words(text: str) -> str:
    """
    Remove filler words that should not affect medication parsing.
    Example:
        'generic Cosopt BID' -> 'Cosopt BID'
    """
    for word in NONESSENTIAL_MED_WORDS:
        text = re.sub(rf"\b{re.escape(word)}\b", "", text, flags=re.I)

    return normalize_whitespace(text)

def preprocess_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"(?<!\d)\.(?=\s)", ",", text)
    text = re.sub(r"\bb\.?\s*i\.?\s*d\.?\b", "bid", text)
    text = re.sub(r"\bt\.?\s*i\.?\s*d\.?\b", "tid", text)
    text = re.sub(r"\bq\.?\s*i\.?\s*d\.?\b", "qid", text)
    text = re.sub(r"\bxr\b", "XE", text, flags=re.I)
    text = re.sub(r"\bxe\b", "XE", text, flags=re.I)
    text = re.sub(r"\bgfs\b", "XE", text, flags=re.I)
    text = re.sub(r"\b(PO|SR|ER)\b", "", text, flags=re.I)
    text = remove_nonessential_words(text)
    return normalize_whitespace(text)

def split_medication_chunks(text: str) -> List[str]:
    return [c.strip() for c in re.split(r"\s*,\s*", text) if c.strip()]

def dedupe_adjacent_tokens(text: str) -> str:
    tokens = text.split()
    out = []
    for tok in tokens:
        if not out or out[-1] != tok:
            out.append(tok)
    return " ".join(out)

def strip_trailing_punctuation(text: str) -> str:
    """
    Remove trailing punctuation that is acting as sentence punctuation,
    not part of the medication string.
    """
    return normalize_whitespace(re.sub(r"[.,;:]+$", "", text))

def detect_special_cases(text: str) -> Optional[str]:
    t = normalize_whitespace(text.lower())
    if t == UNSPECIFIED_TOKEN:
        return "Unspecified"
    if t in NONE_TOKENS:
        return "None"
    return None

def remove_extra_parenthetical_verbiage(text: str) -> Tuple[str, bool]:
    has_laterality_unknown = LATERALITY_UNKNOWN_PLACEHOLDER in text.lower()

    text = re.sub(r"\([^)]*\)", "", text)
    return normalize_whitespace(text), has_laterality_unknown

def extract_duration(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract and standardize duration to:
      xN day(s)
      xN week(s)
      xN month(s)

    Supports:
      - x2 weeks, x 2 wks, x2 wk
      - for 2 weeks, for 2 wk, for 2 wks
      - for 1 mo, for 3 mos
      - x10 d
    """

    pattern = r"\b(?:x|for)\s*(\d+)\s*(weeks?|wks?|months?|mos?|days?|d)\b"

    m = re.search(pattern, text, flags=re.I)
    if not m:
        return normalize_whitespace(text), None

    n = int(m.group(1))
    raw_unit = m.group(2).lower()

    # normalize unit
    if raw_unit.startswith("d"):
        unit = "day" if n == 1 else "days"
    elif raw_unit.startswith("w"):
        unit = "week" if n == 1 else "weeks"
    elif raw_unit.startswith("m"):
        unit = "month" if n == 1 else "months"
    else:
        unit = raw_unit  # fallback (shouldn't happen)

    duration = f"x{n} {unit}"

    # remove matched portion
    text = re.sub(pattern, "", text, count=1, flags=re.I)

    return normalize_whitespace(text), duration

def extract_percentage(text: str) -> Tuple[str, Optional[str]]:
    m = re.search(r"\b\d+(?:\.\d+)?%", text)
    if not m:
        return text, None
    pct = m.group(0)
    text = re.sub(r"\b\d+(?:\.\d+)?%", "", text, count=1)
    return normalize_whitespace(text), pct

def extract_pf(text: str) -> Tuple[str, bool]:
    has_pf = bool(re.search(r"\bpf\b|\bpreservative[- ]?free\b", text, flags=re.I))
    text = re.sub(r"\bpf\b", "", text, flags=re.I)
    text = re.sub(r"\bpreservative[- ]?free\b", "", text, flags=re.I)
    return normalize_whitespace(text), has_pf

def extract_extended_release_suffix(text: str) -> Tuple[str, Optional[str]]:
    """
    Standardize XR/XE suffixes to formulation='XE' and remove them from the
    text before drug-name mapping.
    """
    has_xe_or_xr = bool(re.search(r"\b(?:xe|xr|gfs)\b", text, flags=re.I))

    if not has_xe_or_xr:
        return normalize_whitespace(text), None

    text = re.sub(r"\b(?:xe|xr|gfs)\b", "", text, flags=re.I)

    return normalize_whitespace(text), "XE"

def extract_laterality(text: str) -> Tuple[str, str]:
    laterality = "unspecified"
    for pat, canon in sorted(LATERALITY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(pat)}\b", text, flags=re.I):
            laterality = canon
            text = re.sub(rf"\b{re.escape(pat)}\b", "", text, flags=re.I)
            break
    return normalize_whitespace(text), laterality

def extract_frequency(text: str) -> tuple[str, str | None]:
    for pat, standardized in sorted(FREQUENCY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(pat)}\b", text, flags=re.I):
            text = re.sub(rf"\b{re.escape(pat)}\b", "", text, count=1, flags=re.I)
            return normalize_whitespace(text), standardized
    return normalize_whitespace(text), None

def extract_oral_dose(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract:
    - 25mg
    - 25 mg
    - 250 (no unit → will fix later)
    """
    # first try full unit match
    pattern_with_unit = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|g|gram|grams)\b", re.I)
    m = pattern_with_unit.search(text)

    if m:
        dose = normalize_whitespace(m.group(0))
        text = pattern_with_unit.sub("", text, count=1)
        return normalize_whitespace(text), dose

    # fallback: number only (no unit)
    pattern_number_only = re.compile(r"\b\d+(\.\d+)?\b")
    m2 = pattern_number_only.search(text)

    if m2:
        dose = m2.group(0)  # e.g., "250"
        text = pattern_number_only.sub("", text, count=1)
        return normalize_whitespace(text), dose

    return text, None

def ensure_mg_unit(dose: Optional[str]) -> Optional[str]:
    """
    Normalize oral dose:
    - 500 mg -> 500mg
    - 500mg -> 500mg
    - 0.5 g -> 0.5g
    - 250 -> 250mg
    """
    if dose is None:
        return None

    dose = normalize_whitespace(dose.strip().lower())

    # number + unit, with optional space
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|gram|grams)", dose)
    if m:
        number, unit = m.groups()
        return f"{number}{unit}"

    # numeric only → append mg
    if re.fullmatch(r"\d+(?:\.\d+)?", dose):
        return f"{dose}mg"

    return dose

def standardize_serum_tears(text: str) -> Tuple[str, bool]:
    for pat in sorted(SERUM_TEAR_PATTERNS, key=lambda x: len(x), reverse=True):
        if re.search(pat, text, flags=re.I):
            text = re.sub(pat, "autologous serum tears", text, flags=re.I)
            return normalize_whitespace(text), True
    return text, False

def standardize_artificial_tears(text: str) -> Tuple[str, bool]:
    for synonym, canon in sorted(ARTIFICIAL_TEAR_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(synonym)}\b", text, flags=re.I):
            text = re.sub(rf"\b{re.escape(synonym)}\b", canon, text, flags=re.I)
            return normalize_whitespace(text), True
    return text, False

def canonicalize_combo_order(drug_name: str) -> str:
    if "/" not in drug_name:
        return drug_name
    parts = [p.strip() for p in drug_name.split("/")]
    return "/".join(sorted(parts, key=str.lower))

def sort_key(parsed: ParsedMedication) -> str:
    return parsed.drug_name or "zzz"

def sort_key_change(parsed: ParsedMedicationChange) -> Tuple[int, str]:
    return (CHANGE_PRIORITY.get(parsed.change_phrase or "", 99), parsed.drug_name or "zzz")

def detect_change_phrase(text: str) -> Tuple[str, Optional[str]]:
    for raw, canon in sorted(CHANGE_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"^\s*{re.escape(raw)}\b", text, flags=re.I):
            text = re.sub(rf"^\s*{re.escape(raw)}\b", "", text, count=1, flags=re.I)
            return normalize_whitespace(text), canon
    return text, None

def get_leading_drug_candidates(text: str) -> list[str]:
    tokens = normalize_whitespace(text.lower()).split()

    tokens = [t for t in tokens]

    candidates = []
    if len(tokens) >= 1:
        candidates.append(tokens[0])
    if len(tokens) >= 2:
        candidates.append(" ".join(tokens[:2]))
    if len(tokens) >= 3:
        candidates.append(" ".join(tokens[:3]))

    candidates.reverse()    # longest first
    return candidates

# ============================================================
# Change-specific chunk expansion
# ============================================================

def split_change_chunks(text: str) -> List[str]:
    return [c.strip() for c in re.split(r"\s*,\s*", text) if c.strip()]

def split_and_expand_same_action(chunk: str) -> List[str]:
    """
    Expand:
      Start X and Y to TID -> [Start X TID, Start Y TID]
      Start X and Y TID    -> [Start X TID, Start Y TID]
      Start X TID and Y QHS -> [Start X TID, Start Y QHS]
      Start Diamox 250mg BID and methazolamide 25mg BID
                           -> [Start Diamox 250mg BID, Start methazolamide 25mg BID]

    Truncate:
      Start X or Y -> [Start X]
    """
    chunk = normalize_whitespace(chunk)

    # truncate "or ..."
    chunk = re.sub(r"\s+or\s+.+$", "", chunk, flags=re.I)

    m = re.match(
        r"^(start|stop|increase|decrease|add|begin|initiate|discontinue|dc|reduce|lower)\b\s+(.+)$",
        chunk,
        flags=re.I,
    )
    if not m:
        return [chunk]

    action = normalize_whitespace(m.group(1))
    rest = normalize_whitespace(m.group(2))

    freq_pattern = r"(?:qhs|daily|qam|qpm|bid|tid|qid|q2h|q3h|q4h|weekly|prn|qod)"
    dur_pattern = r"(?:\s+x\d+\s*(?:day|days|week|weeks|month|months))?"
    tail_pattern = rf"{freq_pattern}{dur_pattern}"

    # X and Y to FREQ
    m_and_to = re.match(r"^(.+?)\s+and\s+(.+?)\s+to\s+(.+)$", rest, flags=re.I)
    if m_and_to:
        left = normalize_whitespace(m_and_to.group(1))
        right = normalize_whitespace(m_and_to.group(2))
        tail = normalize_whitespace(m_and_to.group(3))
        return [f"{action} {left} {tail}", f"{action} {right} {tail}"]

    # X and Y FREQ  -> shared frequency applied to both
    m_and_freq = re.match(
        rf"^(.+?)\s+and\s+(.+?)\s+({tail_pattern})$",
        rest,
        flags=re.I,
    )
    if m_and_freq:
        left = normalize_whitespace(m_and_freq.group(1))
        right = normalize_whitespace(m_and_freq.group(2))
        tail = normalize_whitespace(m_and_freq.group(3))
        return [f"{action} {left} {tail}", f"{action} {right} {tail}"]

    # X FREQ1 and Y FREQ2  -> each med keeps its own frequency
    m_both_tails = re.match(
        rf"^(.+?\s+{tail_pattern})\s+and\s+(.+?\s+{tail_pattern})$",
        rest,
        flags=re.I,
    )
    if m_both_tails:
        left = normalize_whitespace(m_both_tails.group(1))
        right = normalize_whitespace(m_both_tails.group(2))
        return [f"{action} {left}", f"{action} {right}"]

    # generic X and Y
    if re.search(r"\band\b", rest, flags=re.I):
        parts = [
            normalize_whitespace(p)
            for p in re.split(r"\band\b", rest, flags=re.I)
            if normalize_whitespace(p)
        ]
        if len(parts) > 1:
            return [f"{action} {p}" for p in parts]

    return [chunk]

def split_and_expand_switch(chunk: str) -> list[str]:
    """
    Expand:
      Switch timolol BID to Cosopt BID
        -> ["Stop timolol", "Start Cosopt BID"]

      Switch Xalatan to Lumigan nightly
        -> ["Stop Xalatan", "Start Lumigan nightly"]

    Frequency on the old med is discarded in the Stop output.
    Frequency on the new med is retained.
    """
    chunk = normalize_whitespace(chunk)

    m = re.match(r"^switch\s+(.+?)\s+to\s+(.+)$", chunk, flags=re.I)
    if not m:
        return [chunk]

    old_part = normalize_whitespace(m.group(1))
    new_part = normalize_whitespace(m.group(2))

    # remove frequency/duration from the medication being stopped
    old_no_duration, _ = extract_duration(old_part)
    old_no_freq, _ = extract_frequency(old_no_duration)

    # remove common topical words after stripping freq
    old_no_freq = re.sub(r"\b(drop|drops|gtt|gtts)\b", "", old_no_freq, flags=re.I)
    old_no_freq = normalize_whitespace(old_no_freq)

    return [
        f"Stop {old_no_freq}",
        f"Start {new_part}",
    ]

