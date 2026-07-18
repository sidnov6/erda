"""Label harmonization (spec §5): one schema over five regulators.

These decisions are science, documented in the dataset card:
1. Wildcats only in the primary dataset (appraisal wells confirm known
   discoveries — including them is label leakage; sensitivity run keeps them).
2. Outcome map: {OIL, GAS, OIL/GAS} → 1; {DRY} → 0; {SHOWS} → 0 in primary
   (sensitivity: excluded). Per-regulator raw codes live in
   data/curated/outcome_map.csv — an unmapped code RAISES; it is never guessed.
3. Re-entries/sidetracks dedupe to one decision point per surface location:
   any hydrocarbon success in the cluster → success (the location's exploration
   decision found oil); earliest spud year is kept (the decision date).
4. Every well keeps spud_year — wells without one are dropped and counted.

All functions are pure; the only I/O is the caller's.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation

SOURCE_IDS = ["sodir", "nsta", "nlog", "boem_bsee", "nopims"]

PURPOSES = ["wildcat", "appraisal", "other"]

HARMONIZED_SCHEMA = pa.DataFrameSchema(
    {
        "well_id": pa.Column(str, nullable=False),
        "source_id": pa.Column(str, pa.Check.isin(SOURCE_IDS), nullable=False),
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=False),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=False),
        "spud_year": pa.Column(int, pa.Check.in_range(1900, 2100), nullable=False),
        "purpose": pa.Column(str, pa.Check.isin(PURPOSES), nullable=False),
        "content_raw": pa.Column(str, nullable=False),
        "label": pa.Column(int, pa.Check.isin([0, 1]), nullable=False),
        "shows": pa.Column(bool, nullable=False),
        "excluded": pa.Column(bool, nullable=False),
        "td_m": pa.Column(float, pa.Check.ge(0), nullable=True),
        "discovery_id": pa.Column(str, nullable=True),
        "n_wellbores": pa.Column(int, pa.Check.ge(1), nullable=False),
    },
    unique=["well_id"],
)


def load_outcome_map(path: Path) -> pd.DataFrame:
    """Load the curated outcome map; §7: every row must carry its citation.

    ``keep_default_na=False`` is load-bearing: the curated blank-code rows
    (``content_raw == ""``, the explicit excluded-class for a missing outcome)
    must load as empty strings — default NA parsing would turn them into NaN,
    and every connector's ``""`` code would then fail as unmapped.
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"source_id", "content_raw", "label", "shows", "source_url"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise ContractViolation("outcome_map", f"missing columns {sorted(missing_cols)}")
    dup = df.duplicated(["source_id", "content_raw"])
    if dup.any():
        rows = df.loc[dup, ["source_id", "content_raw"]].to_dict("records")
        raise ContractViolation(
            "outcome_map", f"duplicate (source_id, content_raw) rows: {rows}"
        )
    uncited = df[df["source_url"].isna() | (df["source_url"].str.strip() == "")]
    if len(uncited):
        raise ContractViolation(
            "outcome_map", f"uncited rows (spec §7): {uncited['content_raw'].tolist()}"
        )
    df["label"] = df["label"].astype(int)
    df["shows"] = df["shows"].str.lower().map({"true": True, "false": False})
    if df["shows"].isna().any():
        raise ContractViolation("outcome_map", "shows must be 'true' or 'false'")
    if not df["label"].isin([0, 1]).all():
        raise ContractViolation("outcome_map", "label must be 0 or 1")
    # excluded: no recorded geological outcome — these wells leave the training
    # set instead of masquerading as dry holes. Optional column, default false.
    if "excluded" in df.columns:
        df["excluded"] = df["excluded"].str.lower().map({"true": True, "false": False})
        if df["excluded"].isna().any():
            raise ContractViolation("outcome_map", "excluded must be 'true' or 'false'")
    else:
        df["excluded"] = False
    bad = df[df["excluded"] & (df["label"] != 0)]
    if len(bad):
        raise ContractViolation(
            "outcome_map", f"excluded rows must carry label 0: {bad['content_raw'].tolist()}"
        )
    return df


def map_outcomes(df: pd.DataFrame, outcome_map: pd.DataFrame, source_id: str) -> pd.DataFrame:
    """Attach label + shows from the curated map. Unmapped codes raise —
    a silently mis-mapped outcome is a label bug, the worst kind (§5)."""
    mapping = outcome_map[outcome_map["source_id"] == source_id]
    lookup = mapping.set_index("content_raw")[["label", "shows"]]
    unmapped = sorted(set(df["content_raw"]) - set(lookup.index))
    if unmapped:
        raise ContractViolation(
            source_id,
            f"unmapped content codes {unmapped} — add cited rows to outcome_map.csv",
        )
    out = df.copy()
    out["label"] = out["content_raw"].map(lookup["label"]).astype(int)
    out["shows"] = out["content_raw"].map(lookup["shows"]).astype(bool)
    if "excluded" in mapping.columns:
        out["excluded"] = (
            out["content_raw"].map(mapping.set_index("content_raw")["excluded"]).astype(bool)
        )
    else:
        out["excluded"] = False
    return out


#: 3 decimal degrees ≈ 110 m in latitude — clusters sidetracks/re-entries
#: sharing a surface location without merging distinct offset wells. Documented
#: limitation: dense multi-slot pads can still merge; n_wellbores exposes it.
DEDUPE_PRECISION = 3


def dedupe_decision_points(df: pd.DataFrame, precision: int = DEDUPE_PRECISION) -> pd.DataFrame:
    """One exploration decision point per surface location (§5 rule 3).

    Within a (source_id, rounded lat/lon) cluster: label = max (any success in
    the cluster means the location's exploration succeeded), shows = any,
    spud_year = min (the decision date), representative row = earliest spud
    (ties broken by well_id for determinism).

    Missing coordinates RAISE: groupby drops NaN keys, so a well without
    lat/lon would silently vanish here — the caller must drop-and-count
    coordinate-less wells explicitly before deduping (§5 rule 4 analogue).
    """
    missing_coords = df["lat"].isna() | df["lon"].isna()
    if missing_coords.any():
        raise ContractViolation(
            "harmonize",
            f"{int(missing_coords.sum())} wells lack lat/lon — drop-and-count them "
            "before dedupe; grouping would silently discard NaN keys "
            f"(e.g. {df.loc[missing_coords, 'well_id'].head(5).tolist()})",
        )
    df = df.copy()
    df["_lat_key"] = df["lat"].round(precision)
    df["_lon_key"] = df["lon"].round(precision)
    df = df.sort_values(["spud_year", "well_id"]).reset_index(drop=True)
    grouped = df.groupby(["source_id", "_lat_key", "_lon_key"], sort=False)

    rep = grouped.head(1).set_index(["source_id", "_lat_key", "_lon_key"])
    agg = grouped.agg(
        label=("label", "max"),
        shows=("shows", "any"),
        # a cluster is unlabeled only if EVERY wellbore in it lacks an outcome
        excluded=("excluded", "all"),
        spud_year=("spud_year", "min"),
        n_wellbores=("well_id", "count"),
    )
    rep = rep.drop(columns=["label", "shows", "excluded", "spud_year"]).join(agg).reset_index()
    return rep.drop(columns=["_lat_key", "_lon_key"])


def primary_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Wildcats with a recorded outcome (§5 rule 1 + excluded-class policy).

    SHOWS stay, labelled 0; wells with NO recorded outcome (excluded) leave the
    training set — an unknown outcome is not a dry hole.
    """
    return df[(df["purpose"] == "wildcat") & ~df["excluded"]].reset_index(drop=True)


def sensitivity_variants(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The documented sensitivity runs (§5): appraisal included; shows excluded."""
    labeled = df[~df["excluded"]]
    return {
        "primary": primary_dataset(df),
        "with_appraisal": labeled[labeled["purpose"].isin(["wildcat", "appraisal"])].reset_index(
            drop=True
        ),
        "shows_excluded": primary_dataset(df)[~primary_dataset(df)["shows"]].reset_index(
            drop=True
        ),
    }


def validate_harmonized(df: pd.DataFrame, source_id: str = "harmonized") -> pd.DataFrame:
    try:
        return HARMONIZED_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        detail = f"{len(exc.failure_cases)} failures:\n{exc.failure_cases.head(10)}"
        raise ContractViolation(source_id, detail) from exc
