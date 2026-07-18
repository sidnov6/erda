"""Tool law (spec §10.3): every tool is a typed function over the LOCAL
snapshot — no live internet at memo time; every return includes source_ids;
absence raises or returns an explicit absent marker, never an invented value.

SnapshotContext pins the paths once; a memo run resolves everything through it,
which is what makes the §11.3 re-run hash meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pandas as pd
import xarray as xr


class ToolDataMissing(Exception):
    """The snapshot lacks the table/file a tool needs — honest absence."""


@dataclass(frozen=True)
class SnapshotContext:
    repo_root: Path

    @property
    def parquet(self) -> Path:
        return self.repo_root / "data" / "parquet"

    @property
    def curated(self) -> Path:
        return self.repo_root / "data" / "curated"

    @property
    def stack_path(self) -> Path:
        return self.repo_root / "data" / "zarr" / "stack.zarr"

    def table(self, name: str) -> pd.DataFrame:
        path = self.parquet / f"{name}.parquet"
        if not path.exists():
            raise ToolDataMissing(f"snapshot table missing: {name}")
        return pd.read_parquet(path)

    @cached_property
    def stack(self) -> xr.Dataset:
        if not self.stack_path.exists():
            raise ToolDataMissing("raster stack missing: data/zarr/stack.zarr")
        return xr.open_zarr(self.stack_path)

    @cached_property
    def grid_spec(self):
        """GridSpec inferred from the stack's own latitude axis — tools never
        assume a resolution the snapshot doesn't have."""
        from erda_geo.grid import GridSpec

        lats = self.stack["lat"].values
        return GridSpec(res_deg=float(abs(lats[0] - lats[1])))
