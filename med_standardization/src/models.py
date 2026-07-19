# models.py

from dataclasses import dataclass
from typing import Optional

# ============================================================
# Canonical schemas
# ============================================================

@dataclass
class ParsedMedication:
    raw_chunk: str
    medication_type: str                    # OD / OS / oral
    drug_name: Optional[str]
    laterality: str                         # OD / OS / OU / unspecified / not_applicable
    frequency: Optional[str]
    formulation: Optional[str] = None
    percentage: Optional[str] = None
    duration: Optional[str] = None
    preservative_free: bool = False
    laterality_unknown_placeholder: bool = False

    # oral only
    dose: Optional[str] = None

    confidence_flag: str = "clean"          # clean / corrected / ambiguous / unmapped
    correction_notes: Optional[str] = None


@dataclass
class ParsedMedicationChange:
    raw_chunk: str
    medication_type: str                    # OD / OS / oral
    change_phrase: Optional[str]            # Start / Stop / Increase / Decrease
    drug_name: Optional[str]
    laterality: str                         # OD / OS / not_applicable
    frequency: Optional[str]
    formulation: Optional[str] = None
    percentage: Optional[str] = None
    duration: Optional[str] = None
    preservative_free: bool = False
    laterality_unknown_placeholder: bool = False

    # oral only
    dose: Optional[str] = None

    confidence_flag: str = "clean"          # clean / corrected / ambiguous / unmapped
    correction_notes: Optional[str] = None
