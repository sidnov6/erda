"""Synthetic fixtures (spec §11.3) exercising every §5 harmonization decision."""

from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation
from erda_labels import harmonize

FRAGMENTS = Path(__file__).parents[3] / "data" / "curated" / "outcome_map.d"


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


def test_outcome_map_rejects_duplicate_code_rows(tmp_path):
    # two curated rows for the same (source_id, content_raw) — a conflicting
    # duplicate could silently pick a label; it must raise instead
    path = tmp_path / "outcome_map.csv"
    path.write_text(
        "source_id,content_raw,label,shows,source_url\n"
        "sodir,OIL,1,false,https://example.com/doc\n"
        "sodir,OIL,0,false,https://example.com/doc\n"
    )
    with pytest.raises(ContractViolation, match="duplicate"):
        harmonize.load_outcome_map(path)


def test_blank_content_code_survives_load_and_maps(tmp_path):
    # the curated excluded-class rows use content_raw == "" — default NA
    # parsing would turn them into NaN and every connector's "" would then
    # fail as unmapped (keep_default_na=False is load-bearing)
    path = tmp_path / "outcome_map.csv"
    path.write_text(
        "source_id,content_raw,label,shows,source_url\n"
        "sodir,,0,false,https://example.com/doc\n"
    )
    loaded = harmonize.load_outcome_map(path)
    assert loaded["content_raw"].tolist() == [""]
    wells = _wells().assign(content_raw="")
    mapped = harmonize.map_outcomes(wells, loaded, "sodir")
    assert (mapped["label"] == 0).all()
    assert (~mapped["shows"]).all()


def test_real_outcome_fragments_load_and_never_label_ambiguity_positive():
    """Every checked-in fragment loads; ambiguity is never a positive label.

    Blank/unknown/water/indications-style codes must carry label 0, and a
    label-1 row must never carry the shows flag (shows drives the 0-label
    sensitivity exclusion).
    """
    fragments = sorted(FRAGMENTS.glob("*.csv"))
    assert len(fragments) == 5  # sodir, nsta, nlog, boem_bsee, nopims
    ambiguous = {"", "UNK", "Unknown", "NOT AVAILABLE", "NOT APPLICABLE", "WATER", "FLR"}
    # no recorded geological outcome → must be excluded from training entirely
    no_outcome = {"", "UNK", "Unknown", "NOT AVAILABLE", "NOT APPLICABLE", "FLR"}
    for path in fragments:
        frag = harmonize.load_outcome_map(path)
        assert not frag["content_raw"].isna().any(), f"{path.stem}: NaN code leaked"
        assert frag["label"].isin([0, 1]).all()
        # label-1 never flagged shows anywhere in the curated map
        assert frag[(frag["label"] == 1) & frag["shows"]].empty, path.stem
        amb = frag[frag["content_raw"].isin(ambiguous)]
        assert (amb["label"] == 0).all(), f"{path.stem}: ambiguous code labelled 1"
        assert (~amb["shows"]).all(), f"{path.stem}: ambiguous code flagged shows"
        unknown = frag[frag["content_raw"].isin(no_outcome)]
        assert unknown["excluded"].all(), f"{path.stem}: no-outcome code not excluded"
        # excluded rows never carry a positive label (loader enforces; belt+braces)
        assert frag[frag["excluded"] & (frag["label"] == 1)].empty, path.stem
        if path.stem != "boem_bsee":  # boem's proxy has no blank code
            assert "" in set(frag["content_raw"]), f"{path.stem}: blank code missing"


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


def test_dedupe_raises_on_missing_coordinates_never_silently_drops():
    # pandas groupby drops NaN keys: without the guard, a well with missing
    # lat/lon would vanish from the label set with no trace
    mapped = harmonize.map_outcomes(_wells(), _outcome_map(), "sodir")
    mapped.loc[0, "lat"] = float("nan")
    with pytest.raises(ContractViolation, match="lack lat/lon"):
        harmonize.dedupe_decision_points(mapped)


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
