"""Offline reader tests on synthetic files (spec §11.3)."""

import io
import tarfile
import zipfile

import numpy as np
import pytest
import rasterio
import xarray as xr
from rasterio.transform import from_origin

from erda_geo import readers


def test_read_netcdf_grid(tmp_path):
    lat = np.array([1.5, 0.5, -0.5])
    lon = np.array([-0.5, 0.5])
    data = np.arange(6, dtype=float).reshape(3, 2)
    xr.Dataset({"z": (("lat", "lon"), data)}, coords={"lat": lat, "lon": lon}).to_netcdf(
        tmp_path / "g.nc"
    )
    rlat, rlon, rdata = readers.read_netcdf_grid(tmp_path / "g.nc", "z")
    np.testing.assert_allclose(rlat, lat)
    np.testing.assert_allclose(rdata, data)
    with pytest.raises(ValueError, match="variable"):
        readers.read_netcdf_grid(tmp_path / "g.nc", "nope")


def test_read_geotiff_grid(tmp_path):
    data = np.array([[1.0, 2.0], [3.0, -9999.0]], dtype="float32")
    path = tmp_path / "g.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        transform=from_origin(-1.0, 1.0, 1.0, 1.0),  # north-up, 1° cells
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)
    lat, lon, out = readers.read_geotiff_grid(path)
    np.testing.assert_allclose(lat, [0.5, -0.5])
    np.testing.assert_allclose(lon, [-0.5, 0.5])
    assert out[0, 0] == 1.0
    assert np.isnan(out[1, 1])  # nodata → NaN


def _crust1_tar(tmp_path, name: str, member: str, text: str):
    path = tmp_path / name
    data = text.encode("ascii")
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(member)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return path


def test_read_crust1_moho_and_types(tmp_path):
    # full-size synthetic: 64800 lines × 9 values, moho = −11.75 everywhere
    line = "0.00 -3.69 -3.69 -4.99 -4.99 -4.99 -5.67 -7.15 -11.75\n"
    tar = _crust1_tar(tmp_path, "crust1.0.tar.gz", "crust1.bnds", line * 64800)
    lat, lon, moho = readers.read_crust1_moho(tar)
    assert moho.shape == (180, 360)
    assert moho[0, 0] == pytest.approx(-11.75)
    assert lat[0] == pytest.approx(89.5) and lon[0] == pytest.approx(-179.5)

    type_line = " ".join(["A1"] * 360) + "\n"
    addon = _crust1_tar(tmp_path, "addon.tar.gz", "CNtype1-1.txt", type_line * 180)
    _, _, types = readers.read_crust1_types(addon)
    assert types.shape == (180, 360)
    assert types[0, 0] == "A1"

    bad = _crust1_tar(tmp_path, "bad.tar.gz", "crust1.bnds", line * 10)
    with pytest.raises(ValueError, match="expected"):
        readers.read_crust1_moho(bad)


def test_read_ghfdb(tmp_path):
    # SYNTHETIC (spec §11.3): preamble rows before the tab header, like the GFZ file
    preamble = "\n".join(f"# preamble {i}" for i in range(12))
    header = "q\tq_uncertainty\tname\tlat_NS\tlong_EW\televation"
    rows = "57.0\t5.0\tSITE-A\t61.5\t2.5\t-300\n120.5\t\tSITE-B\t-20.1\t115.2\t-1500"
    zip_path = tmp_path / "ghfdb.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("IHFC_2024_GHFDB_test.txt", f"{preamble}\n{header}\n{rows}\n")
        zf.writestr("data_description.txt", "not the data")
    df = readers.read_ghfdb(zip_path)
    assert len(df) == 2
    assert df["q"].tolist() == [57.0, 120.5]
    assert df["lat_NS"].tolist() == [61.5, -20.1]

    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("readme.md", "nothing")
    with pytest.raises(ValueError, match="no .txt member"):
        readers.read_ghfdb(empty)
