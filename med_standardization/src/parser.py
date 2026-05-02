# parser.py

import re
from typing import List

from .models import ParsedMedication, ParsedMedicationChange
from .matching import bounded_fuzzy_map_drug, normalize_combination_drug_name
from .fda_lookup import lookup_openfda_name
from .constants import (
    CANONICAL_ORAL_DRUGS,
    CANONICAL_TOP_DRUGS,
    EXCLUDED_DRUGS,
    ORAL_DRUG_SYNONYMS,
    TOP_DRUG_SYNONYMS,
    ARTIFICIAL_TEAR_SYNONYMS,
    PROSTAGLANDINS,
)
from .utils import (
    canonicalize_combo_order,
    dedupe_adjacent_tokens,
    detect_change_phrase, 
    detect_special_cases, 
    ensure_mg_unit, 
    extract_duration,
    extract_extended_release_suffix, extract_frequency,
    extract_oral_dose, 
    extract_percentage, extract_pf,
    get_leading_drug_candidates,
    normalize_whitespace, preprocess_text,
    remove_extra_parenthetical_verbiage,
    split_and_expand_same_action,
    split_and_expand_switch,
    split_change_chunks, 
    split_medication_chunks, 
    standardize_artificial_tears, 
    standardize_serum_tears,
    strip_trailing_punctuation,
)



def resolve_drug_name(
    chunk: str,
    canonical_drugs: set,
    synonym_map: dict,
    extra_map: dict | None = None,
):
    best = None
    best_flag = "unmapped"
    best_note = None
    best_score = float("inf")

    for candidate in get_leading_drug_candidates(chunk):
        canon, flag, note, score = bounded_fuzzy_map_drug(
            token=candidate,
            canonical_drugs=canonical_drugs,
            synonym_map=synonym_map,
            extra_map=extra_map or {},
        )

        if score < best_score:
            best_score = score
            best = canon
            best_flag = flag
            best_note = note

    return best, best_flag, best_note

# ============================================================
# Parser -- Current
# ============================================================

def parse_single_chunk(chunk: str, med_list_type: str) -> ParsedMedication:
    original_chunk = chunk
    chunk = preprocess_text(chunk)
    chunk = dedupe_adjacent_tokens(chunk)
    chunk = strip_trailing_punctuation(chunk)

    special = detect_special_cases(chunk)
    if special == "None":
        return ParsedMedication(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            drug_name="None",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )
    if special == "Unspecified":
        return ParsedMedication(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            drug_name="Unspecified",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )

    laterality_unknown_placeholder = False
    has_pf = False
    pct = None

    if med_list_type in {"OD", "OS"}:
        chunk, laterality_unknown_placeholder = remove_extra_parenthetical_verbiage(chunk)
        chunk, _ = standardize_serum_tears(chunk)
        chunk, _ = standardize_artificial_tears(chunk)
        chunk, has_pf = extract_pf(chunk)
        chunk, duration = extract_duration(chunk)

        # For a single OD/OS list, laterality is inherited from the input type,
        # not extracted from the chunk.
        laterality = med_list_type

        chunk, frequency = extract_frequency(chunk)
        chunk, pct = extract_percentage(chunk)
        chunk = re.sub(r"\b(drop|drops|gtt|gtts)\b", "", chunk, flags=re.I)
        chunk = normalize_whitespace(chunk)

        drug_name, confidence_flag, note = resolve_drug_name(
            chunk=chunk,
            canonical_drugs=CANONICAL_TOP_DRUGS,
            synonym_map=TOP_DRUG_SYNONYMS,
            extra_map=ARTIFICIAL_TEAR_SYNONYMS,
        )

        # Remove artifical tears from medication list
        if drug_name in EXCLUDED_DRUGS:
            return None

        # If direct mapping failed, try normalizing a generic combo string
        if drug_name is None and re.search(r"[\/\-\+]", chunk):
            drug_name, confidence_flag, note, combo_score = normalize_combination_drug_name(
                token=chunk,
                canonical_drugs=CANONICAL_TOP_DRUGS,
                synonym_map=TOP_DRUG_SYNONYMS,
                extra_map=ARTIFICIAL_TEAR_SYNONYMS,
            )

        if drug_name:
            drug_name = canonicalize_combo_order(drug_name)

        if drug_name is None:
            for candidate in get_leading_drug_candidates(chunk):
                fda_name = lookup_openfda_name(candidate)
                if fda_name:
                    drug_name = fda_name
                    confidence_flag = "corrected"
                    note = f'openFDA lookup: {candidate} -> {fda_name}'
                    break

        if drug_name in {"prednisolone", "atropine"}:
            pct = None

        if drug_name in PROSTAGLANDINS and frequency == "daily":
            frequency = "QHS"

        return ParsedMedication(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            drug_name=drug_name,
            laterality=laterality,
            frequency=frequency,
            formulation=None,
            percentage=pct,
            duration=duration,
            preservative_free=has_pf,
            laterality_unknown_placeholder=laterality_unknown_placeholder,
            confidence_flag=confidence_flag,
            correction_notes=note,
        )
    
    elif med_list_type == "oral":
        chunk = normalize_whitespace(chunk)
        
        chunk, _ = remove_extra_parenthetical_verbiage(chunk)
        chunk, duration = extract_duration(chunk)
        chunk, frequency = extract_frequency(chunk)
        chunk, dose = extract_oral_dose(chunk)
        dose = ensure_mg_unit(dose)

        # remove oral formulation words after extraction
        chunk = re.sub(
            r"\b(tab|tabs|tablet|tablets|cap|caps|capsule|capsules|po|oral)\b",
            "",
            chunk,
            flags=re.I
        )
        chunk = normalize_whitespace(chunk)

        drug_name, confidence_flag, note = resolve_drug_name(
            chunk=chunk,
            canonical_drugs=CANONICAL_ORAL_DRUGS,
            synonym_map=ORAL_DRUG_SYNONYMS,
        )

        if drug_name is None:
            for candidate in get_leading_drug_candidates(chunk):
                fda_name = lookup_openfda_name(candidate)
                if fda_name:
                    drug_name = fda_name
                    confidence_flag = "corrected"
                    note = f'openFDA lookup: {candidate} -> {fda_name}'
                    break

        return ParsedMedication(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            drug_name=drug_name,
            laterality="not_applicable",
            frequency=frequency,
            formulation="oral",
            percentage=None,
            duration=duration,
            preservative_free=False,
            laterality_unknown_placeholder=False,
            dose=dose,
            confidence_flag=confidence_flag,
            correction_notes=note,
        )

    else:
        raise ValueError("med_list_type must be one of: 'OD', 'OS', 'oral'")


def parse_medication_list(med_list: str, med_list_type: str) -> List[ParsedMedication]:
    med_list_type = med_list_type.strip()

    if med_list_type not in {"OD", "OS", "oral"}:
        raise ValueError("med_list_type must be one of: 'OD', 'OS', 'oral'")

    text = preprocess_text(med_list)
    special = detect_special_cases(text)
    if special == "None":
        return [ParsedMedication(
            raw_chunk=med_list,
            medication_type=med_list_type,
            drug_name="None",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )]
    if special == "Unspecified":
        return [ParsedMedication(
            raw_chunk=med_list,
            medication_type=med_list_type,
            drug_name="Unspecified",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )]

    chunks = split_medication_chunks(text)
    parsed = [parse_single_chunk(chunk, med_list_type=med_list_type) for chunk in chunks]

    # remove None entries
    parsed = [p for p in parsed if p is not None]

    return parsed


# ============================================================
# Render standardized output -- Current
# ============================================================

def render_standardized_med(parsed: ParsedMedication) -> str:
    if parsed.drug_name in {"None", "Unspecified"}:
        return parsed.drug_name

    pieces = [parsed.drug_name]

    if parsed.medication_type in {"OD", "OS"}:
        if parsed.preservative_free:
            pieces.append("PF")
        if parsed.percentage:
            pieces.append(parsed.percentage)

        if parsed.frequency:
            pieces.append(parsed.frequency)
        if parsed.duration:
            pieces.append(parsed.duration)

        if parsed.laterality_unknown_placeholder:
            pieces.append("(laterality unknown)")

        return " ".join(pieces)

    elif parsed.medication_type == "oral":
        if parsed.dose:
            pieces.append(parsed.dose)
        if parsed.frequency:
            pieces.append(parsed.frequency)
        if parsed.duration:
            pieces.append(parsed.duration)

        return " ".join(pieces)

    return " ".join(pieces)


# ============================================================
# Parser -- Change
# ============================================================

def parse_single_change_chunk(chunk: str, med_list_type: str) -> ParsedMedicationChange:
    original_chunk = chunk
    chunk = preprocess_text(chunk)
    chunk = dedupe_adjacent_tokens(chunk)
    chunk = strip_trailing_punctuation(chunk)
    chunk = re.sub(r"\s+to\s+", " ", chunk, flags=re.I)

    special = detect_special_cases(chunk)
    if special == "None":
        return ParsedMedicationChange(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            change_phrase=None,
            drug_name="None",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )
    if special == "Unspecified":
        return ParsedMedicationChange(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            change_phrase=None,
            drug_name="Unspecified",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )

    chunk, change_phrase = detect_change_phrase(chunk)

    if med_list_type in {"OD", "OS"}:
        chunk, laterality_unknown_placeholder = remove_extra_parenthetical_verbiage(chunk)
        chunk, _ = standardize_serum_tears(chunk)
        chunk, _ = standardize_artificial_tears(chunk)
        chunk, has_pf = extract_pf(chunk)
        chunk, duration = extract_duration(chunk)
        chunk, frequency = extract_frequency(chunk)
        chunk, pct = extract_percentage(chunk)
        chunk, has_xe = extract_extended_release_suffix(chunk)
        chunk = re.sub(r"\b(drop|drops|gtt|gtts)\b", "", chunk, flags=re.I)
        chunk = normalize_whitespace(chunk)

        drug_name, confidence_flag, note = resolve_drug_name(
            chunk=chunk,
            canonical_drugs=CANONICAL_TOP_DRUGS,
            synonym_map=TOP_DRUG_SYNONYMS,
            extra_map=ARTIFICIAL_TEAR_SYNONYMS,
        )

        # Remove artifical tears from medication list
        if drug_name in EXCLUDED_DRUGS:
            return None

        if drug_name is None and re.search(r"[\/\-\+]", chunk):
            drug_name, confidence_flag, note, combo_score = normalize_combination_drug_name(
                token=chunk,
                canonical_drugs=CANONICAL_TOP_DRUGS,
                synonym_map=TOP_DRUG_SYNONYMS,
                extra_map=ARTIFICIAL_TEAR_SYNONYMS,
            )

        if drug_name:
            drug_name = canonicalize_combo_order(drug_name)
        
        if drug_name is None:
            for candidate in get_leading_drug_candidates(chunk):
                fda_name = lookup_openfda_name(candidate)
                if fda_name:
                    drug_name = fda_name
                    confidence_flag = "corrected"
                    note = f'openFDA lookup: {candidate} -> {fda_name}'
                    break

        if drug_name in {"prednisolone", "atropine"}:
            pct = None

        if drug_name in PROSTAGLANDINS and frequency == "daily":
            frequency = "QHS"

        if change_phrase == "Stop":
            frequency = None
            duration = None

        return ParsedMedicationChange(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            change_phrase=change_phrase,
            drug_name=drug_name,
            laterality=med_list_type,
            frequency=frequency,
            formulation=has_xe,
            percentage=pct,
            duration=duration,
            preservative_free=has_pf,
            laterality_unknown_placeholder=laterality_unknown_placeholder,
            confidence_flag=confidence_flag,
            correction_notes=note,
        )

    elif med_list_type == "oral":
        chunk, _ = remove_extra_parenthetical_verbiage(chunk)
        chunk, duration = extract_duration(chunk)
        chunk, frequency = extract_frequency(chunk)
        chunk, dose = extract_oral_dose(chunk)
        dose = ensure_mg_unit(dose)

        chunk = re.sub(
            r"\b(tab|tabs|tablet|tablets|cap|caps|capsule|capsules|po|oral|sr|sq|by mouth|orally|sequels|taken this am|taken with food|with food)\b",
            "",
            chunk,
            flags=re.I
        )
        chunk = normalize_whitespace(chunk)

        drug_name, confidence_flag, note = resolve_drug_name(
            chunk=chunk,
            canonical_drugs=CANONICAL_ORAL_DRUGS,
            synonym_map=ORAL_DRUG_SYNONYMS,
        )

        if drug_name is None:
            for candidate in get_leading_drug_candidates(chunk):
                fda_name = lookup_openfda_name(candidate)
                if fda_name:
                    drug_name = fda_name
                    confidence_flag = "corrected"
                    note = f'openFDA lookup: {candidate} -> {fda_name}'
                    break

        if change_phrase == "Stop":
            frequency = None
            duration = None

        return ParsedMedicationChange(
            raw_chunk=original_chunk,
            medication_type=med_list_type,
            change_phrase=change_phrase,
            drug_name=drug_name,
            laterality="not_applicable",
            frequency=frequency,
            formulation=None,
            percentage=None,
            duration=duration,
            preservative_free=False,
            laterality_unknown_placeholder=False,
            dose=dose,
            confidence_flag=confidence_flag,
            correction_notes=note,
        )

    else:
        raise ValueError("med_list_type must be one of: 'OD', 'OS', 'oral'")

def parse_medication_change_list(med_list: str, med_list_type: str) -> List[ParsedMedicationChange]:
    med_list_type = med_list_type.strip()

    if med_list_type not in {"OD", "OS", "oral"}:
        raise ValueError("med_list_type must be one of: 'OD', 'OS', 'oral'")

    text = preprocess_text(med_list)
    special = detect_special_cases(text)
    if special == "None":
        return [ParsedMedicationChange(
            raw_chunk=med_list,
            medication_type=med_list_type,
            change_phrase=None,
            drug_name="None",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )]
    if special == "Unspecified":
        return [ParsedMedicationChange(
            raw_chunk=med_list,
            medication_type=med_list_type,
            change_phrase=None,
            drug_name="Unspecified",
            laterality="not_applicable" if med_list_type == "oral" else med_list_type,
            frequency=None,
            confidence_flag="clean",
        )]

    chunks = split_change_chunks(text)
    expanded_chunks: List[str] = []
    for chunk in chunks:
        switched = split_and_expand_switch(chunk)
        for subchunk in switched:
            expanded_chunks.extend(split_and_expand_same_action(subchunk))

    parsed = [parse_single_change_chunk(chunk, med_list_type=med_list_type) for chunk in expanded_chunks]

    # remove None entries
    parsed = [p for p in parsed if p is not None]

    return parsed


# ============================================================
# Render standardized output -- Change
# ============================================================

def render_standardized_change(parsed: ParsedMedicationChange) -> str:
    if parsed.drug_name in {"None", "Unspecified"}:
        return parsed.drug_name

    pieces = []
    if parsed.change_phrase:
        pieces.append(parsed.change_phrase)
    if parsed.drug_name:
        pieces.append(parsed.drug_name)
    if parsed.formulation:
        pieces.append(parsed.formulation)

    if parsed.medication_type in {"OD", "OS"}:
        if parsed.preservative_free:
            pieces.append("PF")
        if parsed.percentage:
            pieces.append(parsed.percentage)

        if parsed.change_phrase != "Stop":
            if parsed.frequency:
                pieces.append(parsed.frequency)
            if parsed.duration:
                pieces.append(parsed.duration)

        if parsed.laterality_unknown_placeholder:
            pieces.append("(laterality unknown)")

        return " ".join(pieces)

    elif parsed.medication_type == "oral":
        if parsed.dose:
            pieces.append(parsed.dose)

        if parsed.change_phrase != "Stop":
            if parsed.frequency:
                pieces.append(parsed.frequency)
            if parsed.duration:
                pieces.append(parsed.duration)

        return " ".join(pieces)

    return " ".join(pieces)
