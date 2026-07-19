#!/usr/bin/env python3
"""Compute Start/Stop vs Increase/Decrease distribution in ground-truth medication-change labels."""

from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ADJUDICATED_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/labels/adjudicated_meds_last_final_standardized.xlsx"
)
FEWSHOT_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/labels/notes_fewshot_final_complete.xlsx"
)
REPORT_FULL_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/reports/ground_truth_change_distribution_report_full.md"
)
REPORT_TEST_PATH = Path(
    "/media/zyflo/shared_files/slm_ehr/reports/ground_truth_change_distribution_report_test.md"
)

TOPICAL_OS_RAW = "Change in Topical Treatment OS_adjudicated"
TOPICAL_OD_RAW = "Change in Topical Treatment OD_adjudicated"
TOPICAL_OS_COL = (
    "Change in Topical Treatment OS_adjudicated__standardized_change_os_parsed_items"
)
TOPICAL_OD_COL = (
    "Change in Topical Treatment OD_adjudicated__standardized_change_od_parsed_items"
)

ORAL_RAW = "Change in Oral Meds_adjudicated"
ORAL_CHANGE_COL = (
    "Change in Oral Meds_adjudicated__standardized_change_oral_parsed_items"
)
ORAL_COL_AS_SPECIFIED = (
    "Oral Meds_adjudicated__standardized_current_oral_parsed_items"
)

TOPICAL_EYE_PAIRS = [
    ("OD", TOPICAL_OD_RAW, TOPICAL_OD_COL),
    ("OS", TOPICAL_OS_RAW, TOPICAL_OS_COL),
]
ORAL_PAIRS = [("oral", ORAL_RAW, ORAL_CHANGE_COL)]

START_STOP = frozenset({"start", "stop"})
INCREASE_DECREASE = frozenset({"increase", "decrease"})

# Mirror metrics_standardized_topmeds staged.ipynb positive-class rules.
PLACEHOLDER_RAW_VALUES = frozenset({"no", "unspecified"})
PLACEHOLDER_DRUG_NAMES = frozenset({"none", "nan", "unspecified", ""})


@dataclass
class StandardizationFailure:
    note_id: object
    eye: str
    raw_text: str

    def as_row(self) -> dict:
        return {"NOTE_ID": self.note_id, "eye": self.eye, "raw_adjudicated": self.raw_text}


@dataclass
class StandardizationAudit:
    label: str
    pairs: list[tuple[str, str, str]]
    raw_nonempty_cells: int = 0
    parsed_success_cells: int = 0
    failures: list[StandardizationFailure] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def failure_rate_pct(self) -> float:
        if self.raw_nonempty_cells == 0:
            return 0.0
        return 100.0 * self.failure_count / self.raw_nonempty_cells

    @property
    def od_os_summed_valid_eye_rows(self) -> int:
        return self.parsed_success_cells


@dataclass
class CellParseStats:
    total_cells: int = 0
    empty_or_nan: int = 0
    empty_list: int = 0
    unparseable: int = 0
    parsed_with_entries: int = 0
    standardization_failures_excluded: int = 0
    placeholder_only_excluded: int = 0


@dataclass
class CategoryStats:
    label: str
    columns: list[str]
    row_count: int
    cell_stats: CellParseStats = field(default_factory=CellParseStats)
    phrase_counts: Counter = field(default_factory=Counter)
    rows_with_any_entry: int = 0

    @property
    def total_entries(self) -> int:
        return sum(self.phrase_counts.values())

    def bucket_count(self, bucket: frozenset[str]) -> int:
        return sum(c for phrase, c in self.phrase_counts.items() if phrase in bucket)

    def other_phrases(self) -> Counter:
        known = START_STOP | INCREASE_DECREASE
        return Counter(
            {phrase: count for phrase, count in self.phrase_counts.items() if phrase not in known}
        )

    def pct(self, count: int) -> float:
        if self.total_entries == 0:
            return 0.0
        return 100.0 * count / self.total_entries


@dataclass
class TopicalRowBreakdown:
    label: str
    row_count: int
    od_only: int = 0
    os_only: int = 0
    both: int = 0
    neither: int = 0

    @property
    def union(self) -> int:
        return self.od_only + self.os_only + self.both

    @property
    def od_valid_eye_rows(self) -> int:
        return self.od_only + self.both

    @property
    def os_valid_eye_rows(self) -> int:
        return self.os_only + self.both

    @property
    def summed_valid_eye_rows(self) -> int:
        return self.od_valid_eye_rows + self.os_valid_eye_rows

    def pct(self, count: int) -> float:
        if self.row_count == 0:
            return 0.0
        return 100.0 * count / self.row_count


@dataclass
class RowOverlapStats:
    label: str
    row_count: int
    topical_only: int = 0
    oral_only: int = 0
    both: int = 0
    neither: int = 0

    @property
    def topical_any(self) -> int:
        return self.topical_only + self.both

    @property
    def oral_any(self) -> int:
        return self.oral_only + self.both

    def pct_of_rows(self, count: int) -> float:
        if self.row_count == 0:
            return 0.0
        return 100.0 * count / self.row_count


def raw_has_real_entry(value) -> bool:
    """Mirror has_medications() for plain-text adjudicated cells."""
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    normalized = str(value).strip().lower()
    if not normalized:
        return False
    return normalized not in PLACEHOLDER_RAW_VALUES


def is_real_medication_item(item: dict) -> bool:
    """Mirror extract_from_json drug filter from metrics notebook."""
    drug = item.get("drug_name")
    if drug is None:
        return False
    drug_text = str(drug).strip().lower()
    if not drug_text:
        return False
    return drug_text not in PLACEHOLDER_DRUG_NAMES


def real_parsed_items(parsed_value) -> list[dict]:
    items, status = parse_cell(parsed_value)
    if status != "ok" or not items:
        return []
    return [item for item in items if is_real_medication_item(item)]


def parsed_has_real_medications(parsed_value) -> bool:
    return bool(real_parsed_items(parsed_value))


def parse_cell(value) -> tuple[list[dict] | None, str]:
    """Return (items, status) where status is ok | empty_nan | empty_list | unparseable."""
    if value is None:
        return None, "empty_nan"
    try:
        if pd.isna(value):
            return None, "empty_nan"
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in {"", "nan", "none", "[]"}:
            return None, "empty_nan" if stripped.lower() in {"", "nan", "none"} else "empty_list"
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(stripped)
            except (SyntaxError, ValueError):
                return None, "unparseable"
    elif isinstance(value, list):
        parsed = value
    else:
        return None, "unparseable"

    if not isinstance(parsed, list):
        return None, "unparseable"
    if len(parsed) == 0:
        return None, "empty_list"

    items: list[dict] = []
    for item in parsed:
        if isinstance(item, dict):
            items.append(item)
        else:
            return None, "unparseable"
    return items, "ok"


def is_standardization_failure(raw_value, parsed_value) -> bool:
    """Raw has a real change but standardization yielded no real medication."""
    return raw_has_real_entry(raw_value) and not parsed_has_real_medications(parsed_value)


def cell_has_real_medication(raw_value, parsed_value) -> bool:
    if is_standardization_failure(raw_value, parsed_value):
        return False
    return parsed_has_real_medications(parsed_value)


def audit_standardization(
    df: pd.DataFrame, pairs: list[tuple[str, str, str]], label: str
) -> StandardizationAudit:
    audit = StandardizationAudit(label=label, pairs=pairs)
    for eye, raw_col, parsed_col in pairs:
        for _, row in df.iterrows():
            raw_value = row[raw_col]
            parsed_value = row[parsed_col]
            if is_standardization_failure(raw_value, parsed_value):
                audit.failures.append(
                    StandardizationFailure(
                        note_id=row.get("NOTE_ID"),
                        eye=eye,
                        raw_text=str(raw_value).strip(),
                    )
                )
                if raw_has_real_entry(raw_value):
                    audit.raw_nonempty_cells += 1
                continue
            if raw_has_real_entry(raw_value):
                audit.raw_nonempty_cells += 1
            if cell_has_real_medication(raw_value, parsed_value):
                audit.parsed_success_cells += 1
    return audit


def analyze_column_pairs(
    df: pd.DataFrame,
    pairs: list[tuple[str, str, str]],
    label: str,
) -> CategoryStats:
    stats = CategoryStats(
        label=label,
        columns=[parsed_col for _, _, parsed_col in pairs],
        row_count=len(df),
    )
    row_has_entry = {idx: False for idx in df.index}

    for eye, raw_col, parsed_col in pairs:
        for idx, row in df.iterrows():
            stats.cell_stats.total_cells += 1
            raw_value = row[raw_col]
            parsed_value = row[parsed_col]

            if is_standardization_failure(raw_value, parsed_value):
                stats.cell_stats.standardization_failures_excluded += 1
                continue

            real_items = real_parsed_items(parsed_value)
            if not real_items:
                items, status = parse_cell(parsed_value)
                if status == "empty_nan":
                    stats.cell_stats.empty_or_nan += 1
                elif status == "empty_list":
                    stats.cell_stats.empty_list += 1
                elif status == "unparseable":
                    stats.cell_stats.unparseable += 1
                else:
                    stats.cell_stats.placeholder_only_excluded += 1
                continue

            stats.cell_stats.parsed_with_entries += 1
            row_has_entry[idx] = True
            for item in real_items:
                stats.phrase_counts[normalize_phrase(item.get("change_phrase"))] += 1

    stats.rows_with_any_entry = sum(1 for has in row_has_entry.values() if has)
    return stats


def analyze_topical_row_breakdown(df: pd.DataFrame, label: str) -> TopicalRowBreakdown:
    stats = TopicalRowBreakdown(label=label, row_count=len(df))
    for _, row in df.iterrows():
        has_od = cell_has_real_medication(row[TOPICAL_OD_RAW], row[TOPICAL_OD_COL])
        has_os = cell_has_real_medication(row[TOPICAL_OS_RAW], row[TOPICAL_OS_COL])
        if has_od and has_os:
            stats.both += 1
        elif has_od:
            stats.od_only += 1
        elif has_os:
            stats.os_only += 1
        else:
            stats.neither += 1
    return stats


def analyze_row_overlap(df: pd.DataFrame, label: str) -> RowOverlapStats:
    stats = RowOverlapStats(label=label, row_count=len(df))
    for _, row in df.iterrows():
        has_topical = any(
            cell_has_real_medication(row[raw_col], row[parsed_col])
            for _, raw_col, parsed_col in TOPICAL_EYE_PAIRS
        )
        has_oral = any(
            cell_has_real_medication(row[raw_col], row[parsed_col])
            for _, raw_col, parsed_col in ORAL_PAIRS
        )
        if has_topical and has_oral:
            stats.both += 1
        elif has_topical:
            stats.topical_only += 1
        elif has_oral:
            stats.oral_only += 1
        else:
            stats.neither += 1
    return stats


def normalize_phrase(raw) -> str:
    if raw is None:
        return "<missing>"
    text = str(raw).strip()
    if not text:
        return "<missing>"
    return text.lower()


def format_failure_table(audit: StandardizationAudit) -> str:
    lines = [
        f"### {audit.label}",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Raw adjudicated cells with a real entry | {audit.raw_nonempty_cells} |",
        f"| Standardization failures (raw real entry → no real parsed medication) | {audit.failure_count} |",
        f"| Cells with real parsed medications used in analysis | {audit.parsed_success_cells} |",
        f"| **Failure rate** (failures / raw with entry) | **{audit.failure_rate_pct:.2f}%** |",
    ]
    if audit.failures:
        lines.extend(["", "| NOTE_ID | Eye | Raw adjudicated |", "|---|---|---|"])
        for failure in audit.failures:
            raw = failure.raw_text.replace("|", "\\|")
            lines.append(f"| {failure.note_id} | {failure.eye} | {raw} |")
    else:
        lines.append("")
        lines.append("_No standardization failures detected._")
    return "\n".join(lines)


def format_topical_row_breakdown(stats: TopicalRowBreakdown) -> str:
    return "\n".join(
        [
            f"### {stats.label}",
            "",
            "Valid parsed topical change per note (OD and/or OS); placeholders and "
            "standardization failures excluded.",
            "",
            "| Row category | Count | % of rows |",
            "|---|---:|---:|",
            f"| OD only | {stats.od_only} | {stats.pct(stats.od_only):.1f}% |",
            f"| OS only | {stats.os_only} | {stats.pct(stats.os_only):.1f}% |",
            f"| Both OD and OS | {stats.both} | {stats.pct(stats.both):.1f}% |",
            f"| **Any topical (union)** | **{stats.union}** | **{stats.pct(stats.union):.1f}%** |",
            f"| Neither | {stats.neither} | {stats.pct(stats.neither):.1f}% |",
            f"| **Total rows** | **{stats.row_count}** | **100.0%** |",
            "",
            "| Eye-row totals (summed, not union) | Count |",
            "|---|---:|",
            f"| Valid OD eye-rows | {stats.od_valid_eye_rows} |",
            f"| Valid OS eye-rows | {stats.os_valid_eye_rows} |",
            f"| **OD + OS summed** | **{stats.summed_valid_eye_rows}** |",
        ]
    )


def format_row_overlap_section(stats: RowOverlapStats) -> str:
    return "\n".join(
        [
            f"## {stats.label}",
            "",
            "Row-level counts after excluding placeholders and standardization failures.",
            "",
            "| Row category | Count | % of rows |",
            "|---|---:|---:|",
            f"| Topical change only | {stats.topical_only} | {stats.pct_of_rows(stats.topical_only):.1f}% |",
            f"| Oral change only | {stats.oral_only} | {stats.pct_of_rows(stats.oral_only):.1f}% |",
            f"| **Both topical and oral** | **{stats.both}** | **{stats.pct_of_rows(stats.both):.1f}%** |",
            f"| Neither | {stats.neither} | {stats.pct_of_rows(stats.neither):.1f}% |",
            f"| Any topical change (OD and/or OS) | {stats.topical_any} | {stats.pct_of_rows(stats.topical_any):.1f}% |",
            f"| Any oral change | {stats.oral_any} | {stats.pct_of_rows(stats.oral_any):.1f}% |",
            f"| **Total rows** | **{stats.row_count}** | **100.0%** |",
        ]
    )


def format_phrase_table(phrase_counts: Counter) -> str:
    if not phrase_counts:
        return "_No entries._\n"
    lines = ["| change_phrase | Count | % of entries |", "|---|---:|---:|"]
    total = sum(phrase_counts.values())
    for phrase, count in phrase_counts.most_common():
        pct = 100.0 * count / total if total else 0.0
        display = phrase if phrase != "<missing>" else "`<missing>`"
        lines.append(f"| {display} | {count} | {pct:.1f}% |")
    return "\n".join(lines) + "\n"


def format_bucket_table(stats: CategoryStats) -> str:
    start_stop = stats.bucket_count(START_STOP)
    inc_dec = stats.bucket_count(INCREASE_DECREASE)
    other = stats.other_phrases()
    other_count = sum(other.values())
    total = stats.total_entries

    lines = [
        "| Bucket | Count | % of entries |",
        "|---|---:|---:|",
        f"| Start/Stop (combined) | {start_stop} | {stats.pct(start_stop):.1f}% |",
        f"| Increase/Decrease (combined) | {inc_dec} | {stats.pct(inc_dec):.1f}% |",
        f"| Other / unrecognized | {other_count} | {stats.pct(other_count):.1f}% |",
        f"| **Total entries** | **{total}** | **100.0%** |",
        "",
        f"- Rows in scope: **{stats.row_count}**",
        f"- Rows with at least one real medication entry: **{stats.rows_with_any_entry}**",
        f"- Cells scanned: **{stats.cell_stats.total_cells}** "
        f"(empty/NaN: {stats.cell_stats.empty_or_nan}, "
        f"empty list: {stats.cell_stats.empty_list}, "
        f"unparseable: {stats.cell_stats.unparseable}, "
        f"placeholder-only parsed: {stats.cell_stats.placeholder_only_excluded}, "
        f"stdz failures excluded: {stats.cell_stats.standardization_failures_excluded}, "
        f"real-medication cells: {stats.cell_stats.parsed_with_entries})",
    ]
    if other:
        detail = ", ".join(f"{p}: {c}" for p, c in other.most_common())
        lines.append(f"- Other phrase breakdown: {detail}")
    return "\n".join(lines)


def format_section(stats: CategoryStats) -> str:
    return "\n".join(
        [
            f"## {stats.label}",
            "",
            f"Columns: {', '.join(f'`{c}`' for c in stats.columns)}",
            "",
            "_Cells count as having a real medication only when at least one parsed item has a "
            "non-placeholder `drug_name` (mirrors `has_medications` / `extract_from_json` in "
            "`metrics_standardized_topmeds staged.ipynb`). Raw `no`/`unspecified` and parsed "
            "placeholders (`drug_name` of `None`, `unspecified`, etc.) are excluded. "
            "Standardization failures (raw real entry but no real parsed medication) are also excluded._",
            "",
            "### Combined buckets",
            "",
            format_bucket_table(stats),
            "",
            "### Full `change_phrase` distribution",
            "",
            format_phrase_table(stats.phrase_counts),
        ]
    )


def build_scope_summary(
    scope_label: str,
    row_count: int,
    topical: CategoryStats,
    oral: CategoryStats,
    topical_rows: TopicalRowBreakdown,
    topical_audit: StandardizationAudit,
    oral_audit: StandardizationAudit,
    overlap: RowOverlapStats,
    test_filter_note: str | None = None,
) -> str:
    lines = [
        f"## Summary — {scope_label}",
        "",
    ]
    if test_filter_note:
        lines.extend([test_filter_note, ""])
    lines.extend(
        [
            f"- Total rows in scope: **{row_count}**",
            f"- Topical standardization failures: **{topical_audit.failure_count}** "
            f"({topical_audit.failure_rate_pct:.2f}% of {topical_audit.raw_nonempty_cells} "
            f"raw topical cells with real entries)",
            f"- Oral standardization failures: **{oral_audit.failure_count}** "
            f"({oral_audit.failure_rate_pct:.2f}% of {oral_audit.raw_nonempty_cells} "
            f"raw oral cells with real entries)",
            f"- Topical OD + OS summed eye-rows: **{topical_rows.summed_valid_eye_rows}** "
            f"(OD {topical_rows.od_valid_eye_rows}, OS {topical_rows.os_valid_eye_rows})",
            f"- Notes with any topical change: **{topical_rows.union}**",
            f"- Notes with any oral change: **{overlap.oral_any}**",
            f"- Notes with both topical and oral changes: **{overlap.both}**",
            "",
            "| Category | Start/Stop | Increase/Decrease | Other | Total entries |",
            "|---|---:|---:|---:|---:|",
            f"| Topical (OD+OS) | {topical.pct(topical.bucket_count(START_STOP)):.1f}% | "
            f"{topical.pct(topical.bucket_count(INCREASE_DECREASE)):.1f}% | "
            f"{topical.pct(sum(topical.other_phrases().values())):.1f}% | {topical.total_entries} |",
            f"| Oral | {oral.pct(oral.bucket_count(START_STOP)):.1f}% | "
            f"{oral.pct(oral.bucket_count(INCREASE_DECREASE)):.1f}% | "
            f"{oral.pct(sum(oral.other_phrases().values())):.1f}% | {oral.total_entries} |",
        ]
    )
    topical_other = topical.other_phrases()
    if topical_other:
        lines.append(
            f"- Other topical `change_phrase` among real medications: {dict(topical_other)}"
        )
    if oral.total_entries:
        ratio = topical.total_entries / oral.total_entries
        lines.append(f"- Topical entry count is ~{ratio:.1f}x the oral entry count.")
    return "\n".join(lines)


def build_comparison_section(
    topical_full: CategoryStats,
    topical_test: CategoryStats,
    oral_full: CategoryStats,
    oral_test: CategoryStats,
    topical_rows_full: TopicalRowBreakdown,
    topical_rows_test: TopicalRowBreakdown,
    overlap_full: RowOverlapStats,
    overlap_test: RowOverlapStats,
) -> str:
    def delta(full_pct: float, test_pct: float) -> str:
        d = test_pct - full_pct
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.1f} pp"

    topical_ss_full = topical_full.pct(topical_full.bucket_count(START_STOP))
    topical_ss_test = topical_test.pct(topical_test.bucket_count(START_STOP))
    topical_id_full = topical_full.pct(topical_full.bucket_count(INCREASE_DECREASE))
    topical_id_test = topical_test.pct(topical_test.bucket_count(INCREASE_DECREASE))

    return "\n".join(
        [
            "# Full vs Test Comparison",
            "",
            "| Metric | Full | Test |",
            "|---|---:|---:|",
            f"| Rows | {topical_full.row_count} | {topical_test.row_count} |",
            f"| Topical OD+OS summed eye-rows | {topical_rows_full.summed_valid_eye_rows} | "
            f"{topical_rows_test.summed_valid_eye_rows} |",
            f"| Notes with any topical change | {topical_rows_full.union} | {topical_rows_test.union} |",
            f"| Notes with any oral change | {overlap_full.oral_any} | {overlap_test.oral_any} |",
            f"| Both topical and oral | {overlap_full.both} | {overlap_test.both} |",
            f"| Topical Start/Stop | {topical_ss_full:.1f}% | {topical_ss_test:.1f}% |",
            f"| Topical Increase/Decrease | {topical_id_full:.1f}% | {topical_id_test:.1f}% |",
            f"| Topical total entries | {topical_full.total_entries} | {topical_test.total_entries} |",
            f"| Oral total entries | {oral_full.total_entries} | {oral_test.total_entries} |",
            "",
            f"Test-set topical Start/Stop shift vs full: "
            f"{delta(topical_ss_full, topical_ss_test)}; "
            f"Increase/Decrease: {delta(topical_id_full, topical_id_test)}.",
        ]
    )


def report_intro(oral_column_note: str) -> str:
    return "\n".join(
        [
            "Entry-level counts of `change_phrase` in adjudicated ground-truth labels.",
            "",
            "Positive-class rules mirror `metrics_standardized_topmeds staged.ipynb`: raw `no`/`unspecified` "
            "and parsed items without a real `drug_name` do not count. Standardization failures "
            "(raw real entry but no real parsed medication) are excluded and reported separately.",
            "",
            "### Oral column note",
            oral_column_note,
        ]
    )


def build_scope_report(
    title: str,
    topical_audit: StandardizationAudit,
    oral_audit: StandardizationAudit,
    topical_rows: TopicalRowBreakdown,
    overlap: RowOverlapStats,
    topical_combined: CategoryStats,
    topical_od: CategoryStats,
    topical_os: CategoryStats,
    oral: CategoryStats,
    scope_summary: str,
) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Standardization audit",
            "",
            format_failure_table(topical_audit),
            "",
            format_failure_table(oral_audit),
            "",
            "## Topical eye-row and note-row counts",
            "",
            format_topical_row_breakdown(topical_rows),
            "",
            format_section(topical_combined),
            format_section(topical_od),
            format_section(topical_os),
            format_section(oral),
            format_row_overlap_section(overlap),
            scope_summary,
        ]
    )


def verify_oral_column_specified(df: pd.DataFrame) -> str:
    phrases = Counter()
    for value in df[ORAL_COL_AS_SPECIFIED]:
        items, status = parse_cell(value)
        if status != "ok" or not items:
            continue
        for item in items:
            phrases[normalize_phrase(item.get("change_phrase"))] += 1

    if phrases == Counter({"<missing>": sum(phrases.values())}) or not phrases:
        return (
            f"The task text names `{ORAL_COL_AS_SPECIFIED}`, but that column has "
            f"**no populated `change_phrase` values** (only current-medication snapshots). "
            f"This report uses `{ORAL_CHANGE_COL}` paired with `{ORAL_RAW}` instead."
        )
    return f"Using user-specified column `{ORAL_COL_AS_SPECIFIED}`."


def main() -> None:
    df = pd.read_excel(ADJUDICATED_PATH)
    fewshot = pd.read_excel(FEWSHOT_PATH)
    df = df.merge(
        fewshot[["PAT_ENC_CSN_ID", "NOTE_ID", "UsedinExamples"]],
        on=["PAT_ENC_CSN_ID", "NOTE_ID"],
        how="left",
    )

    oral_column_note = verify_oral_column_specified(df)
    test_df = df[df["UsedinExamples"] == False].copy()
    test_row_count = len(test_df)

    print("=" * 72)
    print("Ground-truth medication change distribution")
    print("=" * 72)
    print(f"Full dataset rows: {len(df)}")
    print(f"Test subset rows (UsedinExamples == False): {test_row_count}")
    if test_row_count != 992:
        print("WARNING: test-set row count does not match expected 992.")
    else:
        print("Test-set row count matches expected 992.")

    topical_audit_full = audit_standardization(df, TOPICAL_EYE_PAIRS, "Topical")
    topical_audit_test = audit_standardization(test_df, TOPICAL_EYE_PAIRS, "Topical")
    oral_audit_full = audit_standardization(df, ORAL_PAIRS, "Oral")
    oral_audit_test = audit_standardization(test_df, ORAL_PAIRS, "Oral")

    topical_rows_full = analyze_topical_row_breakdown(df, "Topical row breakdown")
    topical_rows_test = analyze_topical_row_breakdown(test_df, "Topical row breakdown")
    overlap_full = analyze_row_overlap(df, "Row overlap (topical vs oral)")
    overlap_test = analyze_row_overlap(test_df, "Row overlap (topical vs oral)")

    topical_full = analyze_column_pairs(df, TOPICAL_EYE_PAIRS, "Topical (OD + OS combined)")
    topical_test = analyze_column_pairs(test_df, TOPICAL_EYE_PAIRS, "Topical (OD + OS combined)")
    topical_od_full = analyze_column_pairs(df, [TOPICAL_EYE_PAIRS[0]], "Topical OD only")
    topical_os_full = analyze_column_pairs(df, [TOPICAL_EYE_PAIRS[1]], "Topical OS only")
    topical_od_test = analyze_column_pairs(test_df, [TOPICAL_EYE_PAIRS[0]], "Topical OD only")
    topical_os_test = analyze_column_pairs(test_df, [TOPICAL_EYE_PAIRS[1]], "Topical OS only")
    oral_full = analyze_column_pairs(df, ORAL_PAIRS, "Oral")
    oral_test = analyze_column_pairs(test_df, ORAL_PAIRS, "Oral")

    test_filter_note = (
        "- Test-set filter: `UsedinExamples == False` after merging "
        "`notes_fewshot_final_complete.xlsx` on `PAT_ENC_CSN_ID` + `NOTE_ID` "
        f"(same approach as `metrics_standardized_topmeds staged.ipynb`). "
        f"Row count **{test_row_count}** "
        f"({'matches' if test_row_count == 992 else 'DOES NOT MATCH'} expected 992)."
    )

    full_report = "\n\n".join(
        [
            report_intro(oral_column_note),
            build_scope_report(
                title="Full Dataset",
                topical_audit=topical_audit_full,
                oral_audit=oral_audit_full,
                topical_rows=topical_rows_full,
                overlap=overlap_full,
                topical_combined=topical_full,
                topical_od=topical_od_full,
                topical_os=topical_os_full,
                oral=oral_full,
                scope_summary=build_scope_summary(
                    "full dataset",
                    len(df),
                    topical_full,
                    oral_full,
                    topical_rows_full,
                    topical_audit_full,
                    oral_audit_full,
                    overlap_full,
                ),
            ),
        ]
    )

    test_report = "\n\n".join(
        [
            report_intro(oral_column_note),
            build_scope_report(
                title="Test Dataset",
                topical_audit=topical_audit_test,
                oral_audit=oral_audit_test,
                topical_rows=topical_rows_test,
                overlap=overlap_test,
                topical_combined=topical_test,
                topical_od=topical_od_test,
                topical_os=topical_os_test,
                oral=oral_test,
                scope_summary=build_scope_summary(
                    "test dataset",
                    test_row_count,
                    topical_test,
                    oral_test,
                    topical_rows_test,
                    topical_audit_test,
                    oral_audit_test,
                    overlap_test,
                    test_filter_note=test_filter_note,
                ),
            ),
            build_comparison_section(
                topical_full,
                topical_test,
                oral_full,
                oral_test,
                topical_rows_full,
                topical_rows_test,
                overlap_full,
                overlap_test,
            ),
        ]
    )

    REPORT_FULL_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FULL_PATH.write_text(full_report, encoding="utf-8")
    REPORT_TEST_PATH.write_text(test_report, encoding="utf-8")

    print()
    print("=" * 72)
    print("FULL DATASET REPORT")
    print("=" * 72)
    print(full_report)
    print()
    print("=" * 72)
    print("TEST DATASET REPORT")
    print("=" * 72)
    print(test_report)
    print()
    print(f"Full dataset report saved to: {REPORT_FULL_PATH}")
    print(f"Test dataset report saved to: {REPORT_TEST_PATH}")


if __name__ == "__main__":
    main()
