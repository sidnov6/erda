"""Synthetic fixtures (spec §11.3) exercising every §5 harmonization decision."""

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation
from erda_labels import harmonize


def _outcome_map() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["sodir"] * 4 + ["nsta"],
            "content_raw": ["OIL", "GAS", "SHOWS", "DRY", "Gas"],
            "label": [1, 1, 0, 0, 1],
            "shows": [False, False, True, False, False],
            "source_url": ["https://example.com/doc"] * 5,
        }
    )


def _wells() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "well_id": ["sodir:34/10-1", "sodir:34/10-1 A", "sodir:34/10-2", "sodir:34/10-3"],
            "source_id": ["sodir"] * 4,
            # first two share a surface location (sidetrack) — dedupe target
            "lat": [61.1234, 61.12345, 61.2000, 61.3000],
            "lon": [2.1234, 2.12341, 2.2000, 2.3000],
            "spud_year": [1979, 1980, 1981, 1982],
            "purpose": ["wildcat", "wildcat", "wildcat", "appraisal"],
            "content_raw": ["DRY", "OIL", "SHOWS", "GAS"],
            "td_m": [2500.0, 2600.0, 3000.0, 3100.0],
            "discovery_id": [None, "34/10-A", None, "34/10-A"],
        }
    )


def test_map_outcomes_and_unmapped_raises():
    mapped = harmonize.map_outcomes(_wells(), _outcome_map(), "sodir")
    assert mapped["label"].tolist() == [0, 1, 0, 1]
    assert mapped["shows"].tolist() == [False, False, True, False]

    bad = _wells().assign(content_raw=["DRY", "OIL", "CONDENSATE", "GAS"])
    with pytest.raises(ContractViolation, match="CONDENSATE"):
        harmonize.map_outcomes(bad, _outcome_map(), "sodir")


def test_outcome_map_rejects_uncited(tmp_path):
    path = tmp_path / "outcome_map.csv"
    path.write_text(
        "source_id,content_raw,label,shows,source_url\nsodir,OIL,1,false,\n"
    )
    with pytest.raises(ContractViolation, match="uncited"):
        harmonize.load_outcome_map(path)


def test_dedupe_decision_points():
    mapped = harmonize.map_outcomes(_wells(), _outcome_map(), "sodir")
    deduped = harmonize.dedupe_decision_points(mapped)
    # 4 wellbores → 3 decision points (sidetrack merged)
    assert len(deduped) == 3
    cluster = deduped[deduped["well_id"] == "sodir:34/10-1"].iloc[0]
    # any success in the cluster → success; earliest spud kept; both bores counted
    assert cluster["label"] == 1
    assert cluster["spud_year"] == 1979
    assert cluster["n_wellbores"] == 2


def test_primary_and_sensitivity_variants():
    mapped = harmonize.map_outcomes(_wells(), _outcome_map(), "sodir")
    deduped = harmonize.dedupe_decision_points(mapped)
    variants = harmonize.sensitivity_variants(deduped)
    assert len(variants["primary"]) == 2  # wildcats only (appraisal dropped)
    assert len(variants["with_appraisal"]) == 3
    assert len(variants["shows_excluded"]) == 1  # the SHOWS well excluded too


def test_harmonized_schema_roundtrip():
    mapped = harmonize.map_outcomes(_wells(), _outcome_map(), "sodir")
    deduped = harmonize.dedupe_decision_points(mapped)
    out = harmonize.validate_harmonized(deduped)
    assert set(out.columns) >= {"well_id", "label", "shows", "spud_year", "n_wellbores"}

    broken = deduped.copy()
    broken.loc[0, "lat"] = 123.0  # out of range
    with pytest.raises(ContractViolation):
        harmonize.validate_harmonized(broken)
