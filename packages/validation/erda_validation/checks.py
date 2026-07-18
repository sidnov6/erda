"""Reconciliation + freshness checks (spec §8, rendered on /validation).

Pure functions over frames/ledger entries. Bands are the spec's, verbatim:
EIA↔JODI |Δ| ≤ 5% pass · 5–10% warn · > 10% fail (both values always shown).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from erda_contracts.ledger import LedgerEntry
from erda_contracts.registry import SourceEntry

PASS, WARN, FAIL = "pass", "warn", "fail"


def _band(delta_pct: float) -> str:
    a = abs(delta_pct)
    if a <= 5.0:
        return PASS
    if a <= 10.0:
        return WARN
    return FAIL


def reconcile_eia_jodi(eia: pd.DataFrame, jodi: pd.DataFrame) -> pd.DataFrame:
    """Country-month crude production cross-check.

    Inputs: frames with [country, month, production_kbd]. Output keeps BOTH
    values (§8: 'with both values shown') plus delta % and band.
    """
    merged = eia.merge(jodi, on=["country", "month"], suffixes=("_eia", "_jodi"), how="inner")
    merged["delta_pct"] = (
        100.0
        * (merged["production_kbd_eia"] - merged["production_kbd_jodi"])
        / merged["production_kbd_jodi"]
    )
    merged["status"] = merged["delta_pct"].map(_band)
    return merged[
        ["country", "month", "production_kbd_eia", "production_kbd_jodi", "delta_pct", "status"]
    ]


def wpsr_internal_consistency(wpsr: pd.DataFrame, tolerance_kbbl: float = 1.0) -> pd.DataFrame:
    """WoW stock change must equal the reported build/draw (§8).

    Input: [week, stocks_kbbl, reported_change_kbbl] sorted by week.
    First week has no prior → excluded from judgement.
    """
    df = wpsr.sort_values("week").reset_index(drop=True).copy()
    df["computed_change_kbbl"] = df["stocks_kbbl"].diff()
    df = df.dropna(subset=["computed_change_kbbl"])
    df["delta_kbbl"] = (df["computed_change_kbbl"] - df["reported_change_kbbl"]).abs()
    df["status"] = (df["delta_kbbl"] <= tolerance_kbbl).map({True: PASS, False: FAIL})
    return df[
        ["week", "stocks_kbbl", "reported_change_kbbl", "computed_change_kbbl", "status"]
    ]


def curve_checks(curve: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Futures-strip sanity: expiry strictly increasing along the strip, and no
    stale contracts (expiry in the past) presented as live (§8).

    Input: [contract, month_index, expiry, settle_usd_bbl] one row per contract.
    """
    df = curve.sort_values("month_index").reset_index(drop=True).copy()
    expiry = pd.to_datetime(df["expiry"])
    monotonic = expiry.is_monotonic_increasing
    df["stale"] = expiry < pd.Timestamp(now).tz_localize(None)
    df["status"] = df["stale"].map({True: FAIL, False: PASS})
    if not monotonic:
        df["status"] = FAIL
    df.attrs["monotonic_expiry"] = monotonic
    return df


def freshness(
    latest: dict[str, LedgerEntry],
    registry: dict[str, SourceEntry],
    now: datetime,
) -> pd.DataFrame:
    """Per-source age vs SLA from the provenance ledger (spec §8 SLAs).

    Sources with no ledger entry are reported as missing/fail — a silent absence
    is exactly what this table exists to expose.
    """
    by_source: dict[str, LedgerEntry] = {}
    for entry in latest.values():
        cur = by_source.get(entry.source_id)
        if cur is None or entry.retrieved_at > cur.retrieved_at:
            by_source[entry.source_id] = entry

    rows = []
    for source_id, meta in registry.items():
        entry = by_source.get(source_id)
        if entry is None:
            rows.append(
                {
                    "source_id": source_id,
                    "age_days": None,
                    "sla_days": meta.sla_days,
                    "retrieved_at": None,
                    "status": FAIL,
                    "detail": "no data written",
                }
            )
            continue
        age = (now - entry.retrieved_at).total_seconds() / 86400.0
        status = PASS if age <= meta.sla_days else FAIL
        rows.append(
            {
                "source_id": source_id,
                "age_days": round(age, 2),
                "sla_days": meta.sla_days,
                "retrieved_at": entry.retrieved_at.isoformat(),
                "status": status,
                "detail": "",
            }
        )
    return pd.DataFrame(rows)
