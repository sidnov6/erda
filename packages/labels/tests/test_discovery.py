"""Synthetic fixtures (spec §11.3) for the Discovery Monitor series."""

import pandas as pd
import pytest

from erda_labels import discovery


def _primary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "well_id": [f"w{i}" for i in range(6)],
            "spud_year": [2000, 2000, 2001, 2001, 2001, 2002],
            "label": [1, 0, 1, 0, 0, 0],
            "province": ["A", "A", "A", "A", "B", "B"],
        }
    )


def test_wells_per_year():
    out = discovery.wells_per_year(_primary()).set_index("spud_year")
    assert out.loc[2000, "wildcats"] == 2
    assert out.loc[2000, "discoveries"] == 1
    assert out.loc[2000, "success_rate"] == pytest.approx(0.5)
    assert out.loc[2001, "wildcats"] == 3
    assert out.loc[2001, "success_rate"] == pytest.approx(1 / 3)
    assert out.loc[2002, "discoveries"] == 0


def test_creaming_curve_cumulative_per_province():
    out = discovery.creaming_curve(_primary())
    a = out[out["province"] == "A"].set_index("spud_year")
    # province A: 2000 → 2 wildcats 1 discovery; 2001 → cumulative 4 and 2
    assert a.loc[2000, "cum_wildcats"] == 2 and a.loc[2000, "cum_discoveries"] == 1
    assert a.loc[2001, "cum_wildcats"] == 4 and a.loc[2001, "cum_discoveries"] == 2
    b = out[out["province"] == "B"].set_index("spud_year")
    assert b.loc[2002, "cum_wildcats"] == 2 and b.loc[2002, "cum_discoveries"] == 0

    with pytest.raises(ValueError, match="province"):
        discovery.creaming_curve(_primary().drop(columns=["province"]))
