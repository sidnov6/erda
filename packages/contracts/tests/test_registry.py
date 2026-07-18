from pathlib import Path

import pytest

from erda_contracts.registry import load_registry

REGISTRY = Path(__file__).parents[3] / "data" / "curated" / "source_registry.yaml"

EXPECTED_SOURCES = {
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


def test_registry_loads_and_covers_p1_sources():
    reg = load_registry(REGISTRY)
    assert set(reg) == EXPECTED_SOURCES
    for entry in reg.values():
        assert entry.sla_days > 0
        assert entry.verified_at == "2026-07-18"


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
