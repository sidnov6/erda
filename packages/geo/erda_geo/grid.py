"""The master grid (spec §6): EPSG:4326, 0.05° (~5 km), global.

DETERMINISTIC CORE — pure functions of their inputs, no I/O, no randomness.
Convention: row 0 is the northernmost band (lat descending), column 0 at
180°W, cell values registered to cell centers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

RES_DEG = 0.05
EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius


@dataclass(frozen=True)
class GridSpec:
    res_deg: float = RES_DEG

    @property
    def n_rows(self) -> int:
        return round(180.0 / self.res_deg)

    @property
    def n_cols(self) -> int:
        return round(360.0 / self.res_deg)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.n_rows, self.n_cols)

    def lat_centers(self) -> np.ndarray:
        """Descending: +89.975 … −89.975 for the default 0.05° grid."""
        half = self.res_deg / 2.0
        return 90.0 - half - self.res_deg * np.arange(self.n_rows)

    def lon_centers(self) -> np.ndarray:
        """Ascending: −179.975 … +179.975 for the default 0.05° grid."""
        half = self.res_deg / 2.0
        return -180.0 + half + self.res_deg * np.arange(self.n_cols)

    def latlon_to_rowcol(self, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Cell indices containing the given points (lon wrapped to [−180, 180))."""
        lat = np.asarray(lat, dtype=float)
        lon = np.mod(np.asarray(lon, dtype=float) + 180.0, 360.0) - 180.0
        row = np.floor((90.0 - lat) / self.res_deg).astype(int)
        col = np.floor((lon + 180.0) / self.res_deg).astype(int)
        return np.clip(row, 0, self.n_rows - 1), np.clip(col, 0, self.n_cols - 1)


def unit_vectors(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    """(N, 3) unit vectors on the sphere — basis for exact great-circle distance."""
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    return np.column_stack(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    )


def chord_to_arc_km(chord: np.ndarray) -> np.ndarray:
    """Chord length between unit vectors → great-circle distance in km."""
    return 2.0 * np.arcsin(np.clip(chord / 2.0, 0.0, 1.0)) * EARTH_RADIUS_KM
