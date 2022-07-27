from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import pyvista as pv
from pyvista import _vtk
from pyvista.core.filters import _get_output
from vtk import vtkObject

from .common import (
    GV_CELL_IDS,
    GV_POINT_IDS,
    GV_REMESH_POINT_IDS,
    REMESH_JOIN,
    REMESH_SEAM,
    calculate_radius,
    sanitize_data,
    to_xy0,
    triangulated,
    wrap,
)
from .log import get_logger

__all__ = [
    "REMESH_SEAM_EAST",
    "VTK_BAD_TRIANGLE_MASK",
    "VTK_BOUNDARY_MASK",
    "VTK_FREE_EDGE_MASK",
    "cast_UnstructuredGrid_to_PolyData",
    "logger",
    "remesh",
]

# Configure the logger.
logger = get_logger(__name__)

#: Marker for remesh filter eastern cell boundary point.
REMESH_SEAM_EAST: int = REMESH_SEAM - 1

#: vtkIntersectionPolyDataFilter bad triangle cell array name.
VTK_BAD_TRIANGLE_MASK: str = "BadTriangle"

#: vtkIntersectionPolyDataFilter intersection point array name.
VTK_BOUNDARY_MASK: str = "BoundaryPoints"

#: vtkIntersectionPolyDataFilter free edge cell array name.
VTK_FREE_EDGE_MASK: str = "FreeEdge"

# Type aliases.
Remesh = Tuple[pv.PolyData, pv.PolyData, pv.PolyData]


def cast_UnstructuredGrid_to_PolyData(
    mesh: pv.UnstructuredGrid,
    clean: Optional[bool] = False,
) -> pv.PolyData:
    """
    TODO

    Notes
    -----
    .. versionadded:: 0.1.0

    """
    if not isinstance(mesh, pv.UnstructuredGrid):
        dtype = type(mesh).split(" ")[1][:-1]
        emsg = f"Expected a 'pyvista.UnstructuredGrid', got {dtype}."
        raise TypeError(emsg)

    # see https://vtk.org/pipermail/vtkusers/2011-March/066506.html
    alg = _vtk.vtkGeometryFilter()
    alg.AddInputData(mesh)
    alg.Update()
    result = _get_output(alg)

    if clean:
        result = result.clean()

    return result


def remesh(
    mesh: pv.PolyData,
    meridian: float,
    boundary: Optional[bool] = False,
    check: Optional[bool] = False,
    warnings: Optional[bool] = False,
) -> Remesh:
    """
    TODO

    Notes
    -----
    .. versionadded :: 0.1.0

    """
    if not warnings:
        # https://public.kitware.com/pipermail/vtkusers/2004-February/022390.html
        vtkObject.GlobalWarningDisplayOff()

    if mesh.n_cells == 0:
        emsg = "Cannot remesh an empty mesh"
        raise ValueError(emsg)

    meridian = wrap(meridian)[0]
    radius = calculate_radius(mesh)
    logger.debug(
        "meridian=%s, radius=%s",
        meridian,
        radius,
    )

    poly0: pv.PolyData = mesh.copy(deep=True)

    if GV_CELL_IDS not in poly0.cell_data:
        poly0.cell_data[GV_CELL_IDS] = np.arange(poly0.n_cells)

    if GV_POINT_IDS not in poly0.point_data:
        poly0.point_data[GV_POINT_IDS] = np.arange(poly0.n_points)

    if not triangulated(poly0):
        start = datetime.now()
        poly0.triangulate(inplace=True)
        end = datetime.now()
        logger.debug(
            "mesh: triangulated [%s secs]",
            (end - start).total_seconds(),
        )

    poly1 = pv.Plane(
        center=(radius / 2, 0, 0),
        i_resolution=1,
        j_resolution=1,
        i_size=radius,
        j_size=radius * 2,
        direction=(0, 1, 0),
    )
    poly1.rotate_z(meridian, inplace=True)
    poly1.triangulate(inplace=True)

    # https://vtk.org/doc/nightly/html/classvtkIntersectionPolyDataFilter.html
    alg = _vtk.vtkIntersectionPolyDataFilter()
    alg.SetInputDataObject(0, poly0)
    alg.SetInputDataObject(1, poly1)
    # BoundaryPoints (points) mask array
    alg.SetComputeIntersectionPointArray(True)
    # BadTriangle and FreeEdge (cells) mask arrays
    alg.SetCheckMesh(check)
    alg.SetSplitFirstOutput(True)
    alg.SetSplitSecondOutput(False)
    start = datetime.now()
    alg.Update()
    end = datetime.now()
    logger.debug(
        "remeshed: lines=%s, points=%s [%s secs]",
        alg.GetNumberOfIntersectionLines(),
        alg.GetNumberOfIntersectionPoints(),
        (end - start).total_seconds(),
    )

    remeshed: pv.PolyData = _get_output(alg, oport=1)

    if not warnings:
        vtkObject.GlobalWarningDisplayOn()

    if remeshed.n_cells == 0:
        # no remeshing has been performed as the meridian does not intersect the mesh
        remeshed_west, remeshed_east = pv.PolyData(), pv.PolyData()
        logger.debug(
            "no remesh performed using meridian=%s",
            meridian,
        )
    else:
        # split the triangulated remesh into its two halves, west and east of the meridian
        centers = remeshed.cell_centers()
        lons = to_xy0(centers)[:, 0]
        delta = lons - meridian
        lower_mask = (delta < 0) & (delta > -180)
        upper_mask = delta > 180
        west_mask = lower_mask | upper_mask
        east_mask = ~west_mask
        logger.debug(
            "split: lower=%s, upper=%s, west=%s, east=%s, total=%s",
            lower_mask.sum(),
            upper_mask.sum(),
            west_mask.sum(),
            east_mask.sum(),
            remeshed.n_cells,
        )

        # the vtkIntersectionPolyDataFilter is configured to *always* generate the boundary mask point array
        # as we require it internally, regardless of whether the caller wants it or not afterwards
        boundary_mask = np.asarray(remeshed.point_data[VTK_BOUNDARY_MASK], dtype=bool)
        if not boundary:
            del remeshed.point_data[VTK_BOUNDARY_MASK]

        remeshed.point_data[GV_REMESH_POINT_IDS] = remeshed[GV_POINT_IDS].copy()

        remeshed[GV_REMESH_POINT_IDS][boundary_mask] = REMESH_SEAM
        remeshed_west = cast_UnstructuredGrid_to_PolyData(
            remeshed.extract_cells(west_mask)
        )
        join_mask = np.where(remeshed_west[GV_REMESH_POINT_IDS] != REMESH_SEAM)[0]
        remeshed_west[GV_REMESH_POINT_IDS][join_mask] = REMESH_JOIN

        remeshed[GV_REMESH_POINT_IDS][boundary_mask] = REMESH_SEAM_EAST
        remeshed_east = cast_UnstructuredGrid_to_PolyData(
            remeshed.extract_cells(east_mask)
        )
        join_mask = np.where(remeshed_east[GV_REMESH_POINT_IDS] != REMESH_SEAM_EAST)[0]
        remeshed_east[GV_REMESH_POINT_IDS][join_mask] = REMESH_JOIN

        del remeshed.point_data[GV_REMESH_POINT_IDS]
        sanitize_data(remeshed, remeshed_west, remeshed_east)

    return remeshed, remeshed_west, remeshed_east
