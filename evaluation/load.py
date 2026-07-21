"""Load grading results, merge with adjudicated labels, and apply the eval filter.

Branches on topical vs oral column layouts from ``EvalSpec``. Filters to rows
where ``UsedinExamples == False`` (held-out set; distinct from inference's
``UsedinExamples == "Val"`` check).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from evaluation.column_map import EvalSpec


@dataclass
class TopicalColumns:
    target_os: str
    target_od: str
    pred_os: str
    pred_od: str
    target_checker_os: str
    target_checker_od: str
    pred_checker_os: str
    pred_checker_od: str
    target_json_os: str
    target_json_od: str
    pred_json_os: str
    pred_json_od: str


@dataclass
class OralColumns:
    target: str
    pred: str
    target_checker: str
    pred_checker: str
    target_json: str
    pred_json: str


@dataclass
class LoadedEvalData:
    df: pd.DataFrame
    spec: EvalSpec
    topical: TopicalColumns | None = None
    oral: OralColumns | None = None


def _unpack_topical(cols: list[str]) -> TopicalColumns:
    return TopicalColumns(
        target_os=cols[0],
        target_od=cols[1],
        pred_os=cols[2],
        pred_od=cols[3],
        target_checker_os=cols[4],
        target_checker_od=cols[5],
        pred_checker_os=cols[6],
        pred_checker_od=cols[7],
        target_json_os=cols[8],
        target_json_od=cols[9],
        pred_json_os=cols[10],
        pred_json_od=cols[11],
    )


def _unpack_oral(cols: list[str]) -> OralColumns:
    return OralColumns(
        target=cols[0],
        pred=cols[1],
        target_checker=cols[2],
        pred_checker=cols[3],
        target_json=cols[4],
        pred_json=cols[5],
    )


def load_and_merge(
    input_path: str | Path,
    adjudicated_path: str | Path,
    spec: EvalSpec,
) -> LoadedEvalData:
    """Load grading + gold, rename glaucoma cols, merge on encounter keys, filter."""
    df_adjudicated = pd.read_excel(adjudicated_path)
    df = pd.read_excel(input_path)
    df.rename(
        columns={
            "Glaucoma OD": "Glaucoma Diagnosis OD",
            "Glaucoma OS": "Glaucoma Diagnosis OS",
        },
        inplace=True,
    )

    if spec.has_change:
        print("Change version")
    if spec.is_topical:
        print("Topical version")
    else:
        print("Oral version")

    original_len = len(df)
    topical_cols: TopicalColumns | None = None
    oral_cols: OralColumns | None = None

    if spec.is_topical:
        topical_cols = _unpack_topical(spec.columns)
        print(f"Ai Prediction: {topical_cols.pred_os}, {topical_cols.pred_od}")
        print(f"Target: {topical_cols.target_os}, {topical_cols.target_od}")
        print(
            f"Checker column 1: {topical_cols.target_checker_os}, "
            f"{topical_cols.target_checker_od}"
        )
        print(
            f"Checker column 2: {topical_cols.pred_checker_os}, "
            f"{topical_cols.pred_checker_od}"
        )
        print(
            f"Target JSON colummn: {topical_cols.target_json_os}, "
            f"{topical_cols.target_json_od}"
        )
        print(
            f"Pred JSON colummn: {topical_cols.pred_json_os}, "
            f"{topical_cols.pred_json_od}"
        )
        gold_cols = [
            "PAT_ENC_CSN_ID",
            "NOTE_ID",
            topical_cols.target_os,
            topical_cols.target_od,
            topical_cols.target_checker_os,
            topical_cols.target_checker_od,
            topical_cols.target_json_od,
            topical_cols.target_json_os,
        ]
    else:
        oral_cols = _unpack_oral(spec.columns)
        print(f"Ai Prediction: {oral_cols.pred}")
        print(f"Target: {oral_cols.target}")
        print(f"Checker column target: {oral_cols.target_checker}")
        print(f"Checker column pred: {oral_cols.pred_checker}")
        print(f"Target JSON colummn: {oral_cols.target_json}")
        print(f"Pred JSON colummn: {oral_cols.pred_json}")
        gold_cols = [
            "PAT_ENC_CSN_ID",
            "NOTE_ID",
            oral_cols.target,
            oral_cols.target_checker,
            oral_cols.target_json,
        ]

    dupes = df_adjudicated.duplicated(subset=["PAT_ENC_CSN_ID", "NOTE_ID"])
    assert not dupes.any(), f"Duplicate keys in df_adjudicated: {dupes.sum()} rows"

    df = df.merge(
        df_adjudicated[gold_cols],
        on=["PAT_ENC_CSN_ID", "NOTE_ID"],
        how="left",
    )

    keys_in_adjudicated = df_adjudicated.set_index(
        ["PAT_ENC_CSN_ID", "NOTE_ID"]
    ).index
    df_keys = df.set_index(["PAT_ENC_CSN_ID", "NOTE_ID"]).index
    unmatched_keys = ~df_keys.isin(keys_in_adjudicated)
    assert not unmatched_keys.any(), (
        f"{unmatched_keys.sum()} rows had no matching key in df_adjudicated:\n"
        f"{df.loc[unmatched_keys.values, ['PAT_ENC_CSN_ID', 'NOTE_ID']].head()}"
    )

    assert len(df) == original_len, "Row count changed after merge!"

    df = df[df["UsedinExamples"] == False]  # noqa: E712

    return LoadedEvalData(
        df=df,
        spec=spec,
        topical=topical_cols,
        oral=oral_cols,
    )
