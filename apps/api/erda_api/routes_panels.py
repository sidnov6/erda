"""Panel endpoints: every number ships with provenance; every derived value
comes from a tested pure function in erda_ingestion.derived (§0 rules 3/5).

Absent tables produce {"available": false, ...} — the panel keeps its honest
AWAITING FEED state; nothing is invented server-side.
"""

from __future__ import annotations

import csv
from typing import Any

import pandas as pd
from fastapi import APIRouter

from erda_api import data
from erda_ingestion import derived

router = APIRouter(prefix="/api/panels")

ABSENT = {"available": False}


def _absent(reason: str) -> dict:
    return {**ABSENT, "reason": reason}


def _latest_two(series: pd.DataFrame, value_col: str = "value") -> tuple[float, float | None]:
    vals = series[value_col].tolist()
    return vals[-1], (vals[-2] if len(vals) > 1 else None)


def _fred_metric(fred: pd.DataFrame, metric: str) -> pd.DataFrame:
    return fred[fred["metric"] == metric].sort_values("date")


@router.get("/ticker")
def ticker() -> dict:
    """Ticker tape (§8.1): BRENT · WTI · B–W · 3-2-1 · M1–M12 · RIGS · USD."""
    instruments: list[dict[str, Any]] = []

    fred = data.read_table("fred_series")
    if fred is not None:
        prov = data.provenance_of(fred)
        for metric, label, unit in [
            ("brent_usd_bbl", "BRENT", "$/bbl"),
            ("wti_usd_bbl", "WTI", "$/bbl"),
        ]:
            series = _fred_metric(fred, metric)
            if not series.empty:
                last, prev = _latest_two(series)
                instruments.append(
                    {
                        "label": label,
                        "value": round(last, 2),
                        "unit": unit,
                        "delta": round(last - prev, 2) if prev is not None else None,
                        "asof": series["date"].iloc[-1].date().isoformat(),
                        "provenance": prov,
                    }
                )
        brent = _fred_metric(fred, "brent_usd_bbl")
        wti = _fred_metric(fred, "wti_usd_bbl")
        if not brent.empty and not wti.empty:
            merged = brent.merge(wti, on="date", suffixes=("_b", "_w")).sort_values("date")
            if not merged.empty:
                row = merged.iloc[-1]
                instruments.append(
                    {
                        "label": "B–W",
                        "value": round(
                            derived.brent_wti_spread(row["value_b"], row["value_w"]), 2
                        ),
                        "unit": "$/bbl",
                        "asof": row["date"].date().isoformat(),
                        "provenance": prov,
                    }
                )
        usd = _fred_metric(fred, "usd_broad_index")
        if not usd.empty:
            last, prev = _latest_two(usd)
            instruments.append(
                {
                    # Fed broad dollar index — NOT ICE DXY (registry note)
                    "label": "USD·BROAD",
                    "value": round(last, 1),
                    "unit": "index",
                    "delta": round(last - prev, 1) if prev is not None else None,
                    "asof": usd["date"].iloc[-1].date().isoformat(),
                    "provenance": prov,
                }
            )

    front = data.read_table("yf_front_months")
    if front is not None:
        prov = data.provenance_of(front)
        by = front.set_index("ticker")
        needed = {"CL=F", "RB=F", "HO=F"}
        if needed <= set(by.index):
            cl = by.loc["CL=F", "settle_usd_bbl"]
            rb = by.loc["RB=F", "settle_usd_gal"]
            ho = by.loc["HO=F", "settle_usd_gal"]
            if pd.notna(cl) and pd.notna(rb) and pd.notna(ho):
                instruments.append(
                    {
                        "label": "3-2-1",
                        "value": round(derived.crack_spread_321(rb, ho, cl), 2),
                        "unit": "$/bbl",
                        "asof": pd.Timestamp(front["asof_date"].max()).date().isoformat(),
                        "indicative": True,
                        "provenance": prov,
                    }
                )

    strip = data.read_table("yf_curve_strip")
    if strip is not None:
        latest = strip[strip["asof_date"] == strip["asof_date"].max()]
        m1 = latest[latest["month_index"] == 1]["settle_usd_bbl"]
        m12 = latest[latest["month_index"] == 12]["settle_usd_bbl"]
        if len(m1) and len(m12):
            slope = derived.curve_slope_m1_m12(float(m1.iloc[0]), float(m12.iloc[0]))
            instruments.append(
                {
                    "label": "M1–M12",
                    "value": round(slope, 2),
                    "unit": "$/bbl",
                    "note": derived.curve_structure(float(m1.iloc[0]), float(m12.iloc[0])),
                    "asof": pd.Timestamp(latest["asof_date"].max()).date().isoformat(),
                    "indicative": True,
                    "provenance": data.provenance_of(strip),
                }
            )

    rigs = data.read_table("baker_rigs")
    if rigs is not None:
        us = rigs[rigs["region"] == "us"].groupby("week")["rig_count"].sum().sort_index()
        if len(us):
            delta = int(us.iloc[-1] - us.iloc[-2]) if len(us) > 1 else None
            instruments.append(
                {
                    "label": "US RIGS",
                    "value": int(us.iloc[-1]),
                    "unit": "rigs",
                    "delta": delta,
                    "asof": us.index[-1].date().isoformat(),
                    "provenance": data.provenance_of(rigs),
                }
            )

    if not instruments:
        return _absent("no market tables written yet — run ops/refresh.py")
    return {"available": True, "instruments": instruments}


@router.get("/curve")
def curve() -> dict:
    """CRV: futures strip + spot history. Curve ghosts (1M/1Y ago) accumulate
    from nightly snapshots and appear once history exists — not before."""
    strip = data.read_table("yf_curve_strip")
    fred = data.read_table("fred_series")
    if strip is None and fred is None:
        return _absent("curve/spot tables not written yet")

    payload: dict[str, Any] = {"available": True}
    if strip is not None:
        latest = strip[strip["asof_date"] == strip["asof_date"].max()].sort_values("month_index")
        m1 = float(latest[latest["month_index"] == 1]["settle_usd_bbl"].iloc[0])
        m2 = float(latest[latest["month_index"] == 2]["settle_usd_bbl"].iloc[0])
        m12 = float(latest[latest["month_index"] == 12]["settle_usd_bbl"].iloc[0])
        payload["strip"] = {
            "asof": pd.Timestamp(latest["asof_date"].max()).date().isoformat(),
            "indicative": True,
            "contracts": [
                {
                    "month_index": int(r.month_index),
                    "contract": r.contract,
                    "expiry": pd.Timestamp(r.expiry).date().isoformat(),
                    "settle_usd_bbl": float(r.settle_usd_bbl),
                }
                for r in latest.itertuples()
            ],
            "prompt_spread": round(derived.prompt_spread(m1, m2), 2),
            "slope_m1_m12": round(derived.curve_slope_m1_m12(m1, m12), 2),
            "structure": derived.curve_structure(m1, m12),
            "provenance": data.provenance_of(strip),
        }
    if fred is not None:
        hist: dict[str, Any] = {}
        for metric, key in [("brent_usd_bbl", "brent"), ("wti_usd_bbl", "wti")]:
            series = _fred_metric(fred, metric).tail(520)  # ~2y of dailies
            hist[key] = [
                {"date": d.date().isoformat(), "value": float(v)}
                for d, v in zip(series["date"], series["value"], strict=True)
            ]
        payload["spot_history"] = hist
        payload["spot_provenance"] = data.provenance_of(fred)
    return payload


@router.get("/inventories")
def inventories() -> dict:
    """INV: WPSR weekly stocks vs 5-yr band, WoW change, days of cover."""
    eia = data.read_table("eia_v2_weekly")
    if eia is None:
        return _absent("eia_v2_weekly not written yet")
    prov = data.provenance_of(eia)
    out: dict[str, Any] = {"available": True, "provenance": prov, "series": {}}

    for metric in ["crude_stocks_excl_spr_kbbl", "gasoline_stocks_kbbl", "distillate_stocks_kbbl"]:
        series = eia[eia["metric"] == metric].sort_values("period")
        if series.empty:
            continue
        weekly = pd.Series(series["value"].values, index=pd.DatetimeIndex(series["period"]))
        asof = weekly.index[-1]
        band = derived.five_year_band(weekly, asof)
        recent = weekly.tail(56)
        out["series"][metric] = {
            "asof": asof.date().isoformat(),
            "latest_kbbl": float(weekly.iloc[-1]),
            "wow_change_kbbl": (
                float(derived.wow_stock_change(weekly.iloc[-1], weekly.iloc[-2]))
                if len(weekly) > 1
                else None
            ),
            "weekly": [
                {"week": d.date().isoformat(), "value_kbbl": float(v)}
                for d, v in recent.items()
            ],
            "five_year_band": band.to_dict(orient="records"),
        }

    crude = eia[eia["metric"] == "crude_stocks_excl_spr_kbbl"].sort_values("period")
    supplied = eia[eia["metric"] == "product_supplied_kbd"].sort_values("period")
    if not crude.empty and not supplied.empty:
        out["days_of_cover"] = round(
            derived.days_of_forward_cover(
                float(crude["value"].iloc[-1]), float(supplied["value"].iloc[-1])
            ),
            1,
        )
    return out


@router.get("/opec")
def opec() -> dict:
    """OPEC: MOMR delivered production (secondary sources) vs curated targets."""
    production = data.read_table("opec_production")
    if production is None:
        return _absent("opec_production not written yet")
    latest_month = production["month"].max()
    latest = production[production["month"] == latest_month]
    prod_prov = data.provenance_of(production)

    targets_path = data.repo_root() / "data" / "curated" / "opec_targets.csv"
    targets: dict[str, dict] = {}
    with targets_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            targets[row["country"].strip()] = row

    rows = []
    for r in latest.itertuples():
        target_row = targets.get(r.country)
        target_kbd = None
        if target_row and target_row["target_kbd"].strip():
            target_kbd = float(target_row["target_kbd"])
        entry: dict[str, Any] = {
            "country": r.country,
            "production_kbd": float(r.production_kbd),
            "target_kbd": target_kbd,
            "pct_of_target": (
                round(derived.opec_compliance_pct(target_kbd, float(r.production_kbd)), 1)
                if target_kbd
                else None
            ),
            "notes": (target_row or {}).get("notes", ""),
            "target_source_url": (target_row or {}).get("source_url"),
        }
        rows.append(entry)

    return {
        "available": True,
        "month": str(latest_month)[:7],
        "extraction": "semi_automated",
        "rows": sorted(rows, key=lambda x: -x["production_kbd"]),
        "production_provenance": prod_prov,
        "targets_provenance": {
            "source_id": "curated_opec_targets",
            "retrieved_at": next(iter(targets.values()))["retrieved_at"] if targets else None,
            "source_url": "data/curated/opec_targets.csv (per-row citations)",
            "transform_version": "curated:manual",
        },
    }


@router.get("/discovery")
def discovery_monitor() -> dict:
    """DISC (§8.7): wells/year + success rate + creaming curves, computed from
    the harmonized label DB — never asserted from a news claim. Creaming curves
    are count-based (volumes await the registration-gated GOGET XLSX)."""
    import json

    from erda_labels import discovery

    primary_path = data.parquet_root() / "wells_primary.parquet"
    summary_path = data.parquet_root() / "labels_summary.json"
    if not primary_path.exists():
        return _absent("wells_primary not built yet — run ops/build_labels.py")
    primary = pd.read_parquet(primary_path)
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    per_year = discovery.wells_per_year(primary)
    per_year = per_year[per_year["spud_year"] >= 1950]

    top_provinces = (
        primary[primary["province_name"] != "(unassigned)"]
        .groupby("province_name").size().sort_values(ascending=False).head(6).index.tolist()
    )
    creaming = discovery.creaming_curve(
        primary[primary["province_name"].isin(top_provinces)].rename(
            columns={"province_name": "province"}
        )
    )

    prov = {
        "source_id": "labels_harmonized",
        "retrieved_at": summary.get("generated_at", ""),
        "source_url": "sodir · nsta · nlog · boem_bsee · nopims (see dataset card)",
        "transform_version": "harmonize:1.1.0",
    }
    return {
        "available": True,
        "provenance": prov,
        "n_primary": int(len(primary)),
        "success_rate": round(float(primary["label"].mean()), 4),
        "boem_proxy_note": "BOEM outcomes are a lease→field proxy (see dataset card)",
        "volumes": "count-based — per-discovery volumes await gated GOGET XLSX",
        "per_year": per_year.to_dict(orient="records"),
        "creaming": {
            p: creaming[creaming["province"] == p].drop(columns=["province"]).to_dict(
                orient="records"
            )
            for p in top_provinces
        },
    }


@router.get("/events")
def events() -> dict:
    """EVENTS: GDELT feed — honestly absent while the source is throttled."""
    gdelt = data.read_table("gdelt_events")
    if gdelt is None:
        return _absent("gdelt_events not written yet (source IP-throttled at last refresh)")
    recent = gdelt.sort_values("seen_at", ascending=False).head(50)
    return {
        "available": True,
        "provenance": data.provenance_of(gdelt),
        "events": [
            {
                "seen_at": pd.Timestamp(r.seen_at).isoformat() if pd.notna(r.seen_at) else None,
                "title": r.title if isinstance(r.title, str) else None,
                "url": r.url if isinstance(r.url, str) else None,
                "domain": r.domain if isinstance(r.domain, str) else None,
            }
            for r in recent.itertuples()
        ],
    }
