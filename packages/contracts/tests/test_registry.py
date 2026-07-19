from pathlib import Path

import pytest

from erda_contracts.registry import load_registry

REGISTRY = Path(__file__).parents[3] / "data" / "curated" / "source_registry.yaml"

P1_SOURCES = {
    "eia_v2",
    "fred",
    "yf_curve",
    "jodi",
    "baker_hughes",
    "opec",
    "wb_pinksheet",
    "comtrade",
    "gdelt",
}

P2_SOURCES = {
    "sodir",
    "nsta",
    "nlog",
    "boem_bsee",
    "nopims",
    "gem_goget",
    "grav_sandwell",
    "emag2",
    "globsed",
    "crust1",
    "etopo2022",
    "ihfc_heatflow",
    "usgs_provinces",
}

P5_SOURCES = {
    "wgi",
    "ofac_eu",
    "gem_infra",
    "wdpa",
}


def test_registry_loads_and_covers_all_sources():
    reg = load_registry(REGISTRY)
    assert set(reg) == P1_SOURCES | P2_SOURCES | P5_SOURCES
    for entry in reg.values():
        assert entry.sla_days > 0
        # every source records the live-verify date it was pinned on
        assert entry.verified_at in {"2026-07-18", "2026-07-19"}


def test_keyed_sources_declare_env_var():
    reg = load_registry(REGISTRY)
    assert reg["eia_v2"].requires_key and reg["eia_v2"].key_env == "EIA_API_KEY"
    assert reg["fred"].requires_key and reg["fred"].key_env == "FRED_API_KEY"


def test_registry_rejects_http_urls(tmp_path: Path):
    bad = tmp_path / "reg.yaml"
    bad.write_text(
        "sources:\n"
        "  x:\n"
        "    name: X\n"
        "    access: rest\n"
        "    base_url: http://insecure.example\n"
        "    cadence: daily\n"
        "    sla_days: 1\n"
        '    verified_at: "2026-07-18"\n'
    )
    with pytest.raises(ValueError):
        load_registry(bad)
