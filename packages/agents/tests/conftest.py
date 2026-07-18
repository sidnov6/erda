"""Shared synthetic-snapshot fixture (spec §11.3) for agents tests."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from erda_agents.tools.base import SnapshotContext
from erda_geo.grid import GridSpec


@pytest.fixture()
def ctx(tmp_path) -> SnapshotContext:
    (tmp_path / "data" / "parquet").mkdir(parents=True)
    (tmp_path / "data" / "curated" / "fiscal").mkdir(parents=True)
    (tmp_path / "data" / "zarr").mkdir(parents=True)

    wells = pd.DataFrame(
        {
            "well_id": ["sodir:1", "sodir:2", "nsta:3"],
            "source_id": ["sodir", "sodir", "nsta"],
            "lat": [60.0, 60.1, 60.2],
            "lon": [2.0, 2.1, 2.2],
            "spud_year": [1990, 2000, 2010],
            "purpose": ["wildcat"] * 3,
            "content_raw": ["OIL", "DRY", "GAS"],
            "label": [1, 0, 1],
            "shows": [False] * 3,
            "excluded": [False] * 3,
            "td_m": [3000.0] * 3,
            "discovery_id": [None] * 3,
            "n_wellbores": [1] * 3,
        }
    )
    wells.to_parquet(tmp_path / "data" / "parquet" / "wells_harmonized.parquet")
    primary = wells.assign(province_code=42, province_name="Test Basin")
    primary.to_parquet(tmp_path / "data" / "parquet" / "wells_primary.parquet")

    # tiny stack: coarse grid with the needed channels
    spec = GridSpec(res_deg=10.0)
    shape = spec.shape
    ds = xr.Dataset(
        {
            "score_mask": (("lat", "lon"), np.ones(shape, dtype="f4")),
            "province_code": (("lat", "lon"), np.full(shape, 42.0, dtype="f4")),
            "elevation_m": (("lat", "lon"), np.full(shape, -350.0, dtype="f4")),
        },
        coords={"lat": spec.lat_centers(), "lon": spec.lon_centers()},
    )
    ds.to_zarr(tmp_path / "data" / "zarr" / "stack.zarr")

    (tmp_path / "data" / "curated" / "cost_benchmarks.csv").write_text(
        "concept,capex_usd_boe_low,capex_usd_boe_high,opex_usd_bbl_low,opex_usd_bbl_high,"
        "well_cost_musd_low,well_cost_musd_high,schedule_years_low,schedule_years_high,"
        "source_url,retrieved_at,notes\n"
        "shelf_tieback,8,15,10,18,25,60,2,4,https://example.com,2026-07-19,synthetic test row\n"
    )
    (tmp_path / "data" / "curated" / "fiscal" / "TST.yaml").write_text(
        "iso3: TST\nregime_type: tax_royalty\nroyalty_rate: 0.1\ncit_rate: 0.3\n"
        "source_urls: [https://example.com/tax]\n"
    )
    (tmp_path / "data" / "curated" / "financing_exclusions.csv").write_text(
        "institution,type,policy_scope,upstream_oil_excluded,policy_url,date_checked,notes\n"
        "TestBank,bank,new upstream,true,https://example.com/policy,2026-07-19,synthetic\n"
        "OtherBank,bank,none,false,https://example.com/p2,2026-07-19,synthetic\n"
    )
    wgi = pd.DataFrame(
        {
            "iso3": ["TST"] * 2,
            "indicator": ["RL.EST", "CC.EST"],
            "year": [2024, 2024],
            "value": [1.2, 0.8],
        }
    )
    wgi.to_parquet(tmp_path / "data" / "parquet" / "wgi_governance.parquet")
    sanc = pd.DataFrame(
        {
            "iso3": ["BAD"],
            "country_name": ["Badland"],
            "program": ["COMPREHENSIVE"],
            "list_source": ["OFAC"],
        }
    )
    sanc.to_parquet(tmp_path / "data" / "parquet" / "sanctions_programs.parquet")
    return SnapshotContext(repo_root=tmp_path)


