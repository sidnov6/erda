import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from erda_contracts.contracts import attach_provenance
from erda_contracts.ledger import write_with_ledger
from erda_contracts.provenance import Provenance
from erda_validation.report import REPORT_NAME, build_report, write_report

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

REGISTRY_YAML = """
sources:
  demo_src:
    name: Demo
    access: rest
    base_url: https://example.com
    cadence: weekly
    sla_days: 8
    verified_at: "2026-07-18"
"""


def test_build_and_write_report(tmp_path: Path):
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(REGISTRY_YAML)

    prov = Provenance(
        source_id="demo_src",
        retrieved_at=NOW,
        source_url="https://example.com/data",
        transform_version="demo_src:1.0.0",
    )
    df = attach_provenance(pd.DataFrame({"v": [1.0]}), prov)
    write_with_ledger(df, prov, "demo_table", tmp_path)

    wpsr = pd.DataFrame(
        {
            "week": pd.to_datetime(["2026-07-03", "2026-07-10"]),
            "stocks_kbbl": [424_300.0, 421_100.0],
            "reported_change_kbbl": [0.0, -3_200.0],
        }
    )
    report = build_report(tmp_path, registry_path, NOW, wpsr=wpsr)

    assert report["summary"]["overall"] == "pass"
    assert report["sections"]["freshness"][0]["status"] == "pass"
    assert report["sections"]["wpsr_consistency"][0]["status"] == "pass"
    assert report["transform_version"] == "validation_report:1.0.0"

    path = write_report(report, tmp_path)
    assert path.name == REPORT_NAME
    assert json.loads(path.read_text())["generated_at"] == NOW.isoformat()


def test_report_flags_missing_source(tmp_path: Path):
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(REGISTRY_YAML)
    report = build_report(tmp_path, registry_path, NOW)
    assert report["summary"]["overall"] == "fail"
    assert report["sections"]["freshness"][0]["detail"] == "no data written"
