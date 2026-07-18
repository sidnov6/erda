"""Discovery Monitor series (spec §8.7): computed from the label DB, never
asserted from a news claim.

Pure functions over the harmonized decision-point table. Creaming curves are
COUNT-based for now — cumulative discoveries vs cumulative wildcats per
province — because public per-discovery volumes await the registration-gated
GOGET XLSX; the label says so (§0 rule 4: no invented volumes).
"""

from __future__ import annotations

import pandas as pd


def wells_per_year(primary: pd.DataFrame) -> pd.DataFrame:
    """[spud_year, wildcats, discoveries, success_rate] — the §8.7 headline."""
    grouped = primary.groupby("spud_year").agg(
        wildcats=("well_id", "count"), discoveries=("label", "sum")
    )
    grouped["success_rate"] = grouped["discoveries"] / grouped["wildcats"]
    return grouped.reset_index()


def creaming_curve(primary: pd.DataFrame, by: str = "province") -> pd.DataFrame:
    """Cumulative discoveries vs cumulative wildcats, ordered by spud year.

    Input needs a `province` column (well → USGS province assignment happens in
    the build step, one global basin definition across regulators). Output:
    [province, spud_year, cum_wildcats, cum_discoveries] — a flattening curve
    is basin maturity (§8.7).
    """
    if by not in primary.columns:
        raise ValueError(f"missing column {by!r} — assign provinces before creaming")
    df = primary.sort_values(["spud_year", "well_id"]).copy()
    df["_one"] = 1
    grouped = df.groupby([by, "spud_year"]).agg(
        wildcats=("_one", "sum"), discoveries=("label", "sum")
    )
    out = grouped.groupby(level=0).cumsum().rename(
        columns={"wildcats": "cum_wildcats", "discoveries": "cum_discoveries"}
    )
    return out.reset_index()
