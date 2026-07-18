"""Synthetic fixtures (spec §11.3 test artifacts) exercising every check band."""

from datetime import UTC, datetime

import pandas as pd

from erda_contracts.ledger import LedgerEntry
from erda_contracts.registry import SourceEntry
from erda_validation import checks

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def test_reconcile_eia_jodi_bands():
    eia = pd.DataFrame(
        {
            "country": ["SA", "US", "RU"],
            "month": ["2026-05"] * 3,
            "production_kbd": [9000.0, 13200.0, 9500.0],
        }
    )
    jodi = pd.DataFrame(
        {
            "country": ["SA", "US", "RU"],
            "month": ["2026-05"] * 3,
            # SA: +3.4% → pass · US: +8.2% → warn · RU: −13.6% → fail
            "production_kbd": [8700.0, 12200.0, 11000.0],
        }
    )
    out = checks.reconcile_eia_jodi(eia, jodi)
    by = out.set_index("country")["status"]
    assert by["SA"] == "pass" and by["US"] == "warn" and by["RU"] == "fail"
    # both values always shown (§8)
    assert {"production_kbd_eia", "production_kbd_jodi"} <= set(out.columns)


def test_wpsr_internal_consistency():
    wpsr = pd.DataFrame(
        {
            "week": pd.to_datetime(["2026-06-26", "2026-07-03", "2026-07-10"]),
            "stocks_kbbl": [420_000.0, 424_300.0, 421_100.0],
            # reported: +4300 (matches) then −3000 (computed −3200 → off by 200 → fail)
            "reported_change_kbbl": [0.0, 4_300.0, -3_000.0],
        }
    )
    out = checks.wpsr_internal_consistency(wpsr)
    assert list(out["status"]) == ["pass", "fail"]


def test_curve_checks_stale_and_monotonic():
    curve = pd.DataFrame(
        {
            "contract": ["CLQ26", "CLU26", "CLV26"],
            "month_index": [1, 2, 3],
            "expiry": ["2026-07-01", "2026-08-20", "2026-09-21"],  # first already expired
            "settle_usd_bbl": [80.0, 79.5, 79.0],
        }
    )
    out = checks.curve_checks(curve, NOW)
    assert list(out["status"]) == ["fail", "pass", "pass"]
    assert out.attrs["monotonic_expiry"] is True


def _entry(source_id: str, table: str, when: datetime) -> LedgerEntry:
    return LedgerEntry(
        source_id=source_id,
        table=table,
        path=f"{table}.parquet",
        rows=10,
        content_sha256="0" * 64,
        retrieved_at=when,
        source_url="https://example.com",
        transform_version=f"{source_id}:1.0.0",
    )


def _source(source_id: str, sla_days: float) -> SourceEntry:
    return SourceEntry(
        source_id=source_id,
        name=source_id,
        access="rest",
        base_url="https://example.com",
        cadence="weekly",
        sla_days=sla_days,
        verified_at="2026-07-18",
    )


def test_freshness_pass_fail_and_missing():
    latest = {
        "fresh_table": _entry("fresh_src", "fresh_table", datetime(2026, 7, 17, tzinfo=UTC)),
        "stale_table": _entry("stale_src", "stale_table", datetime(2026, 6, 1, tzinfo=UTC)),
    }
    registry = {
        "fresh_src": _source("fresh_src", sla_days=8),
        "stale_src": _source("stale_src", sla_days=8),
        "absent_src": _source("absent_src", sla_days=8),
    }
    out = checks.freshness(latest, registry, NOW).set_index("source_id")
    assert out.loc["fresh_src", "status"] == "pass"
    assert out.loc["stale_src", "status"] == "fail"
    assert out.loc["absent_src", "status"] == "fail"
    assert out.loc["absent_src", "detail"] == "no data written"
