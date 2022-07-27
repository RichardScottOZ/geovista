"""
This module contains convenience functions to download, cache and load
geovista sample data, which can then be used by the :mod:`geovista.bridge`
to generate a mesh.

"""

from dataclasses import dataclass, field
from typing import Optional

import netCDF4 as nc
import numpy as np
import numpy.typing as npt
import pooch

from .cache import CACHE

__all__ = [
    "fesom",
    "fvcom_tamar",
    "hexahedron",
    "lam",
    "lfric_orog",
    "lfric_sst",
    "oisst_avhrr_sst",
    "um_orca2",
    "ww3_global_smc",
    "ww3_global_tri",
]


@dataclass(frozen=True)
class SampleStructuredXY:
    lons: npt.ArrayLike
    lats: npt.ArrayLike
    data: npt.ArrayLike = field(default=None)
    name: str = field(default=None)
    units: str = field(default=None)
    steps: int = field(default=None)
    ndim: int = 2


@dataclass(frozen=True)
class SampleUnstructuredXY:
    lons: npt.ArrayLike
    lats: npt.ArrayLike
    connectivity: npt.ArrayLike
    data: npt.ArrayLike = field(default=None)
    face: npt.ArrayLike = field(default=None)
    node: npt.ArrayLike = field(default=None)
    start_index: int = field(default=None)
    name: str = field(default=None)
    units: str = field(default=None)
    steps: int = field(default=None)
    ndim: int = 2


def capitalise(title: str) -> str:
    """
    Format the title by capitalising each word and replacing
    inappropriate characters.

    Returns
    -------
    str

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    title = title.replace("_", " ")
    title = title.split(" ")
    title = " ".join([word.capitalize() for word in title])

    return title


def fesom(step: Optional[int] = None) -> SampleUnstructuredXY:
    """
    Load AWI-CM FESOM 1.4 unstructured mesh.

    Parameters
    ----------
    step : int
        Timeseries index offset.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "tos_Omon_AWI-ESM-1-1-LR_historical_r1i1p1f1_gn_185001-185012.nc"
    resource = CACHE.fetch(f"{fname}")
    ds = nc.Dataset(resource)

    # load the lon/lat cell grid
    lons = ds.variables["lon_bnds"][:]
    lats = ds.variables["lat_bnds"][:]

    # load the mesh payload
    data = ds.variables["tos"]
    name = capitalise(data.standard_name)
    units = data.units

    # deal with the timeseries step
    steps = ds.dimensions["time"].size
    idx = 0 if step is None else (step % steps)

    sample = SampleUnstructuredXY(
        lons, lats, lons.shape, data=data[idx], name=name, units=units, steps=steps
    )

    return sample


def fvcom_tamar() -> SampleUnstructuredXY:
    """
    Load PML FVCOM unstructured mesh.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "fvcom_tamar.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat cell grid
    lons = ds.variables["lon"][:]
    lats = ds.variables["lat"][:]

    # load the face/node connectivity
    offset = 1  # minimum connectivity index offset
    connectivity = ds.variables["nv"][:] - offset

    # load the mesh payload
    face = ds.variables["h_center"]
    name = capitalise(face.standard_name)
    units = face.units
    node = ds.variables["h"][:]

    sample = SampleUnstructuredXY(
        lons, lats, connectivity.T, face=face[:], node=node, name=name, units=units
    )

    return sample


def hexahedron() -> SampleUnstructuredXY:
    """
    Load DYNAMICO hexahedron unstructured mesh.

    Returns
    -------
    SampleUnstructuredXY
        The hexagonal unstructured spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "hexahedron.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat hex cell grid
    lons = ds.variables["bounds_lon_i"][:]
    lats = ds.variables["bounds_lat_i"][:]

    # load the mesh payload
    data = ds.variables["phis"][:]
    name = capitalise("synthetic")
    units = 1

    sample = SampleUnstructuredXY(
        lons, lats, lons.shape, data=data, name=name, units=units
    )

    return sample


def lam() -> SampleUnstructuredXY:
    """
    Load CF UGRID LAM unstructured mesh.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes:
    .. versionadded:: 0.1.0

    """
    fname = "lam.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat cell grid
    lons = ds.variables["Mesh2d_face_node_x"][:]
    lats = ds.variables["Mesh2d_face_node_y"][:]

    # load the face/node connectivity
    connectivity = ds.variables["Mesh2d_face_face_nodes"]
    start_index = connectivity.start_index

    # load the mesh payload
    data = ds.variables["theta"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleUnstructuredXY(
        lons,
        lats,
        connectivity[:],
        data=data[:],
        start_index=start_index,
        name=name,
        units=units,
    )

    return sample


def lfric_orog() -> SampleUnstructuredXY:
    """
    Load CF UGRID global nodal orography unstructured mesh.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes:
    .. versionadded:: 0.1.0

    """
    fname = "qrparam_shared.orog.ugrid.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat cell grid
    lons = ds.variables["dynamics_node_x"][:]
    lats = ds.variables["dynamics_node_y"][:]

    # load the face/node connectivity
    connectivity = ds.variables["dynamics_face_nodes"]
    start_index = connectivity.start_index

    # load the mesh payload
    data = ds.variables["nodal_surface_altitude"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleUnstructuredXY(
        lons,
        lats,
        connectivity[:],
        data=data[:],
        start_index=start_index,
        name=name,
        units=units,
    )

    return sample


def lfric_sst() -> SampleUnstructuredXY:
    """
    Load CF UGRID global unstructured mesh.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes:
    .. versionadded:: 0.1.0

    """
    fname = "qrclim.sst.ugrid.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat cell grid
    lons = ds.variables["dynamics_node_x"][:]
    lats = ds.variables["dynamics_node_y"][:]

    # load the face/node connectivity
    connectivity = ds.variables["dynamics_face_nodes"]
    start_index = connectivity.start_index

    # load the mesh payload
    data = ds.variables["surface_temperature"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleUnstructuredXY(
        lons,
        lats,
        connectivity[:],
        data=data[:],
        start_index=start_index,
        name=name,
        units=units,
    )

    return sample


def oisst_avhrr_sst() -> SampleStructuredXY:
    """
    Load NOAA/NCEI OISST AVHRR rectilinear mesh.

    Returns
    -------
    SampleStructuredXY
        The curvilinear spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "oisst-avhrr.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat grid
    lons = ds.variables["lon_bnds"][:]
    lats = ds.variables["lat_bnds"][:]

    # load the mesh payload
    data = ds.variables["sst"]
    name = capitalise(data.long_name)
    units = data.units

    sample = SampleStructuredXY(lons, lats, data=data[0, 0], name=name, units=units)

    return sample


def um_orca2() -> SampleStructuredXY:
    """
    Load Met Office Unified Model ORCA2 curvilinear mesh.

    Returns
    -------
    SampleStructuredXY
        The curvilinear spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "votemper.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat grid
    lons = ds.variables["lont_bounds"][:]
    lats = ds.variables["latt_bounds"][:]

    # load the mesh payload
    data = ds.variables["votemper"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleStructuredXY(lons, lats, data=data[0, 0], name=name, units=units)

    return sample


def ww3_global_smc(step: Optional[int] = None) -> SampleUnstructuredXY:
    """
    Load the WAVEWATCH III (WW3) unstructured Spherical Multi-Cell (SMC) mesh.

    Parameters
    ----------
    step : int
        Timeseries index offset.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "ww3_gbl_smc_hs.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/ww3/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat grid cell centres
    cc_lons = ds.variables["longitude"][:]
    cc_lats = ds.variables["latitude"][:]

    # load integer scaling factor for the grid cells
    cx = ds.variables["cx"][:]
    cy = ds.variables["cy"][:]
    base_lon_size = ds.getncattr("base_lon_size")
    base_lat_size = ds.getncattr("base_lat_size")

    # construct the grid cells
    dlon = cx * base_lon_size
    dlat = cy * base_lat_size
    fac = 0.5
    x1 = (cc_lons - fac * dlon).reshape(-1, 1)
    x2 = (cc_lons + fac * dlon).reshape(-1, 1)
    y1 = (cc_lats - fac * dlat).reshape(-1, 1)
    y2 = (cc_lats + fac * dlat).reshape(-1, 1)

    lons = np.hstack([x1, x2, x2, x1])
    lats = np.hstack([y1, y1, y2, y2])

    # deal with the timeseries step
    steps = ds.dimensions["time"].size
    idx = 0 if step is None else (step % steps)

    # load mesh payload
    data = ds.variables["hs"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleUnstructuredXY(
        lons, lats, lons.shape, data=data[idx], name=name, units=units, steps=steps
    )

    return sample


def ww3_global_tri() -> SampleUnstructuredXY:
    """
    Load the WAVEWATCH III (WW3) unstructured triangular mesh.

    Returns
    -------
    SampleUnstructuredXY
        The unstructured spatial coordinates and data payload.

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    fname = "ww3_gbl_tri_hs.nc"
    processor = pooch.Decompress(method="auto", name=fname)
    resource = CACHE.fetch(f"pantry/ww3/{fname}.bz2", processor=processor)
    ds = nc.Dataset(resource)

    # load the lon/lat points
    lons = ds.variables["longitude"][:]
    lats = ds.variables["latitude"][:]

    # load the face/node connectivity
    offset = 1  # minimum connectivity index offset
    connectivity = ds.variables["tri"][:] - offset

    # we know this is a single step timeseries, a priori
    idx = 0

    # load mesh payload
    data = ds.variables["hs"]
    name = capitalise(data.standard_name)
    units = data.units

    sample = SampleUnstructuredXY(
        lons, lats, connectivity, data=data[idx], name=name, units=units
    )

    return sample
