"""Fiscal, political-risk, environment, financeability tools (§10.2).

All read the local snapshot (curated files + ingested tables). Missing data
raises ToolDataMissing — an honest absence the agent must report, never paper
over (§0 rule 4).
"""

from __future__ import annotations

import csv

import yaml

from erda_agents.tools.base import SnapshotContext, ToolDataMissing


def get_fiscal_regime(ctx: SnapshotContext, iso3: str) -> dict:
    path = ctx.curated / "fiscal" / f"{iso3.upper()}.yaml"
    if not path.exists():
        raise ToolDataMissing(
            f"no curated fiscal regime for {iso3} — add data/curated/fiscal/{iso3}.yaml (§7 cited)"
        )
    regime = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("regime_type", "cit_rate", "source_urls"):
        if key not in regime:
            raise ToolDataMissing(f"fiscal file {path.name} missing required field {key!r}")
    regime["source_ids"] = ["curated_fiscal"]
    return regime


def get_governance(ctx: SnapshotContext, iso3: str) -> dict:
    """WGI six dimensions + FSI score from ingested tables."""
    wgi = ctx.table("wgi_governance")
    rows = wgi[wgi["iso3"] == iso3.upper()]
    if rows.empty:
        raise ToolDataMissing(f"no WGI rows for {iso3}")
    latest_year = int(rows["year"].max())
    latest = rows[rows["year"] == latest_year]
    dims = {r.indicator: round(float(r.value), 3) for r in latest.itertuples()}

    out = {
        "iso3": iso3.upper(),
        "wgi_year": latest_year,
        "wgi_estimates": dims,  # −2.5 … +2.5 scale
        "source_ids": ["wgi"],
    }
    try:
        fsi = ctx.table("fsi_scores")
        frow = fsi[fsi["iso3"] == iso3.upper()]
        if not frow.empty:
            latest_fsi = frow.sort_values("year").iloc[-1]
            out["fsi_total"] = round(float(latest_fsi["total"]), 1)
            out["fsi_year"] = int(latest_fsi["year"])
            out["source_ids"] = ["wgi", "fsi"]
    except ToolDataMissing:
        out["fsi_total"] = None
        out["fsi_note"] = "FSI table absent from snapshot"
    return out


def screen_sanctions(ctx: SnapshotContext, iso3: str, country_name: str) -> dict:
    """Country-level presence on OFAC comprehensive-program lists / EU regimes.

    ERDA screens jurisdictions, not entities (screening tool, §1). The flag
    drives the deterministic NO_GO rule; details stay cited.
    """
    sanc = ctx.table("sanctions_programs")
    hits = sanc[
        (sanc["iso3"] == iso3.upper())
        | (sanc["country_name"].str.lower() == country_name.lower())
    ]
    return {
        "iso3": iso3.upper(),
        "sanctioned": bool(len(hits) > 0),
        "programs": sorted(hits["program"].unique().tolist()),
        "lists": sorted(hits["list_source"].unique().tolist()),
        "source_ids": ["ofac_eu"],
    }


def get_protected_overlap(
    ctx: SnapshotContext, lat: float, lon: float, radius_km: float = 25.0
) -> dict:
    """WDPA overlap of the block + buffer. Requires the ingested WDPA subset;
    absence raises (the Environment agent reports the gap, the verdict then
    treats overlap as unknown → CONDITIONAL wording by the Chair)."""
    import geopandas as gpd
    from shapely.geometry import Point

    path = ctx.parquet / "wdpa_areas.parquet"
    if not path.exists():
        raise ToolDataMissing("wdpa_areas.parquet missing from snapshot")
    gdf = gpd.read_parquet(path)
    block = (
        gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
        .to_crs(3857)
        .buffer(radius_km * 1000.0)
        .to_crs(4326)
    )
    inter = gdf[gdf.intersects(block.iloc[0])]
    if inter.empty:
        return {
            "radius_km": radius_km,
            "overlap_pct": 0.0,
            "areas": [],
            "source_ids": ["wdpa"],
        }
    block_m = block.to_crs(3857).iloc[0]
    overlap_area = sum(
        geom.intersection(block_m).area
        for geom in inter.geometry.to_crs(3857)
    )
    return {
        "radius_km": radius_km,
        "overlap_pct": round(100.0 * overlap_area / block_m.area, 2),
        "areas": sorted(inter["name"].head(10).tolist()),
        "source_ids": ["wdpa"],
    }


def screen_financing(ctx: SnapshotContext) -> dict:
    path = ctx.curated / "financing_exclusions.csv"
    if not path.exists():
        raise ToolDataMissing("curated financing_exclusions.csv missing")
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    excluded = [
        r for r in rows if r["upstream_oil_excluded"].strip().lower() in ("true", "partial")
    ]
    return {
        "n_institutions_checked": len(rows),
        "n_restricting_upstream": len(excluded),
        "restricting": [
            {"institution": r["institution"], "type": r["type"], "policy_url": r["policy_url"]}
            for r in excluded
        ],
        "capital_note": "European bank/insurer restrictions push financing toward "
        "NOC partnerships, trading-house prepay, or private equity",
        "source_ids": ["curated_exclusions"],
    }
