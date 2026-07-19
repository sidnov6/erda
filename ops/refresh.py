"""Nightly refresh: run every connector, then build the validation report.

Failure semantics (§0 rule 4, applied per source): a failing source raises
inside its slot, is recorded as a failure, and the run continues so one outage
cannot silence the other feeds — but the process exits non-zero and the
freshness table shows the gap. Nothing is ever invented to paper over a miss.

Usage: uv run python ops/refresh.py [--sources fred,jodi,...] [--root data/parquet]
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value and key not in os.environ:
            os.environ[key] = value


def connector_jobs() -> list[dict]:
    """One job per persisted table. Imported lazily so --sources stays cheap."""
    from erda_ingestion import (
        baker_hughes,
        comtrade,
        eia_v2,
        fred,
        gdelt,
        gem_infra,
        jodi,
        ofac_eu,
        opec,
        wb_pinksheet,
        wgi,
        yf_curve,
    )

    today = date.today()
    return [
        {"source": "fred", "table": fred.TABLE, "schema": fred.SCHEMA, "fetch": fred.fetch,
         "version": fred.TRANSFORM_VERSION},
        {"source": "eia_v2", "table": eia_v2.TABLE, "schema": eia_v2.SCHEMA,
         "fetch": eia_v2.fetch, "version": eia_v2.TRANSFORM_VERSION},
        {"source": "eia_v2", "table": eia_v2.TABLE_INTL, "schema": eia_v2.SCHEMA_INTL,
         "fetch": eia_v2.fetch_international, "version": eia_v2.TRANSFORM_VERSION},
        {"source": "yf_curve", "table": yf_curve.TABLE_FRONT_MONTHS,
         "schema": yf_curve.FRONT_SCHEMA, "fetch": lambda: yf_curve.fetch_front_months(today),
         "version": yf_curve.TRANSFORM_VERSION},
        {"source": "yf_curve", "table": yf_curve.TABLE_CURVE_STRIP,
         "schema": yf_curve.STRIP_SCHEMA, "fetch": lambda: yf_curve.fetch_curve_strip(today),
         "version": yf_curve.TRANSFORM_VERSION},
        {"source": "jodi", "table": jodi.TABLE, "schema": jodi.SCHEMA, "fetch": jodi.fetch,
         "version": jodi.TRANSFORM_VERSION},
        {"source": "baker_hughes", "table": baker_hughes.TABLE, "schema": baker_hughes.SCHEMA,
         "fetch": baker_hughes.fetch, "version": baker_hughes.TRANSFORM_VERSION},
        {"source": "opec", "table": opec.TABLE, "schema": opec.SCHEMA, "fetch": opec.fetch,
         "version": opec.TRANSFORM_VERSION},
        {"source": "wb_pinksheet", "table": wb_pinksheet.TABLE, "schema": wb_pinksheet.SCHEMA,
         "fetch": wb_pinksheet.fetch, "version": wb_pinksheet.TRANSFORM_VERSION},
        {"source": "comtrade", "table": comtrade.TABLE, "schema": comtrade.SCHEMA,
         "fetch": comtrade.fetch, "version": comtrade.TRANSFORM_VERSION},
        {"source": "gdelt", "table": gdelt.TABLE, "schema": gdelt.SCHEMA, "fetch": gdelt.fetch,
         "version": gdelt.TRANSFORM_VERSION},
        {"source": "wgi", "table": wgi.TABLE, "schema": wgi.SCHEMA, "fetch": wgi.fetch,
         "version": wgi.TRANSFORM_VERSION},
        {"source": "ofac_eu", "table": ofac_eu.TABLE, "schema": ofac_eu.SCHEMA,
         "fetch": ofac_eu.fetch, "version": ofac_eu.TRANSFORM_VERSION},
        {"source": "gem_infra", "table": gem_infra.TABLE, "schema": gem_infra.SCHEMA,
         "fetch": gem_infra.fetch, "version": gem_infra.TRANSFORM_VERSION},
        # wdpa is a monthly 1.75 GB download that writes a geoparquet directly
        # (two-file design); it is refreshed on its own cadence, not nightly.
    ]


#: EIA pins are ISO3; JODI REF_AREA is ISO2. Only pinned countries reconcile.
ISO2_TO_ISO3 = {
    "SA": "SAU", "RU": "RUS", "US": "USA", "IQ": "IRQ", "AE": "ARE", "KW": "KWT",
    "KZ": "KAZ", "NG": "NGA", "DZ": "DZA", "OM": "OMN", "MX": "MEX", "NO": "NOR",
}


#: The reconciliation judges CURRENT cross-source agreement, not six decades of
#: definitional history — trailing window over the months both sources cover.
RECON_WINDOW_MONTHS = 24


def _eia_jodi_frames(root: Path) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    eia_path = root / "eia_intl_production.parquet"
    jodi_path = root / "jodi_oil.parquet"
    if not (eia_path.exists() and jodi_path.exists()):
        return None
    eia = pd.read_parquet(eia_path)
    eia_frame = pd.DataFrame(
        {
            "country": eia["country_iso3"],
            "month": eia["period"].dt.strftime("%Y-%m"),
            "production_kbd": eia["value"],
        }
    )
    jodi = pd.read_parquet(jodi_path)
    jodi = jodi[(jodi["flow_breakdown"] == "INDPROD") & (jodi["unit_measure"] == "KBD")]
    jodi = jodi[jodi["ref_area"].isin(ISO2_TO_ISO3)]
    jodi_frame = pd.DataFrame(
        {
            "country": jodi["ref_area"].map(ISO2_TO_ISO3),
            "month": jodi["period"].dt.strftime("%Y-%m"),
            "production_kbd": jodi["value"],
        }
    )
    if eia_frame.empty or jodi_frame.empty:
        return None
    common = sorted(set(eia_frame["month"]) & set(jodi_frame["month"]))[-RECON_WINDOW_MONTHS:]
    return (
        eia_frame[eia_frame["month"].isin(common)],
        jodi_frame[jodi_frame["month"].isin(common)],
    )


def _wpsr_frame(root: Path) -> pd.DataFrame | None:
    """Crude stocks ex-SPR → consistency input.

    P1 note (honest scope): EIA v2 serves the stock *levels*; the reported
    build/draw here is recomputed from the stored series, so this check guards
    the pipeline (ordering, units, dedup) rather than cross-checking two
    independently published numbers. The section is labelled accordingly.
    """
    path = root / "eia_v2_weekly.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df = df[df["metric"] == "crude_stocks_excl_spr_kbbl"].sort_values("period")
    if df.empty:
        return None
    out = pd.DataFrame({"week": df["period"], "stocks_kbbl": df["value"]})
    out["reported_change_kbbl"] = out["stocks_kbbl"].diff().fillna(0.0)
    return out.tail(53)


def _curve_frame(root: Path) -> pd.DataFrame | None:
    path = root / "yf_curve_strip.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    latest = df["asof_date"].max()
    df = df[df["asof_date"] == latest]
    return df[["contract", "month_index", "expiry", "settle_usd_bbl"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="", help="comma-separated subset of source_ids")
    parser.add_argument("--root", default=str(REPO / "data" / "parquet"))
    args = parser.parse_args()

    load_dotenv(REPO / ".env")
    root = Path(args.root)
    only = {s.strip() for s in args.sources.split(",") if s.strip()}

    from erda_contracts.errors import ErdaDataError
    from erda_ingestion.base import run_connector
    from erda_validation.report import build_report, write_report

    failures: list[tuple[str, str]] = []
    for job in connector_jobs():
        if only and job["source"] not in only:
            continue
        label = f"{job['source']}:{job['table']}"
        try:
            entry = run_connector(
                source_id=job["source"],
                transform_version=job["version"],
                schema=job["schema"],
                fetch=job["fetch"],
                table=job["table"],
                root=root,
            )
            print(f"[ok]   {label}: {entry.rows} rows")
        except ErdaDataError as exc:
            failures.append((label, str(exc)))
            print(f"[FAIL] {label}: {exc}")
        except Exception as exc:  # unexpected — still honest, still continues
            failures.append((label, f"unexpected: {exc}"))
            print(f"[FAIL] {label}: unexpected error")
            traceback.print_exc()

    report = build_report(
        root,
        REPO / "data" / "curated" / "source_registry.yaml",
        datetime.now(UTC),
        eia_jodi=_eia_jodi_frames(root),
        wpsr=_wpsr_frame(root),
        curve=_curve_frame(root),
    )
    path = write_report(report, root)
    print(f"[report] {path} — overall: {report['summary']['overall']} "
          f"(pass {report['summary']['pass']} / warn {report['summary']['warn']} / "
          f"fail {report['summary']['fail']})")

    if failures:
        print(f"\n{len(failures)} source failure(s):")
        for label, detail in failures:
            print(f"  - {label}: {detail[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
