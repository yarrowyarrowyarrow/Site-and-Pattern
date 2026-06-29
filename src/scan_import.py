"""
src/scan_import.py — phone-scan (point cloud) import → nDSM → footprints
(V1.62).

The "scan your yard" path. Site & Pattern doesn't capture scans — phones do
that far better (Polycam, Scaniverse, any LiDAR/photogrammetry app). This
module turns their *exports* into design data:

  1. :func:`read_points` — load a point cloud: ``.ply`` (ASCII or
     binary-little-endian, the universal phone-scan export), ``.xyz`` /
     ``.txt`` / ``.csv`` text, or ``.las``/``.laz`` via the optional
     ``laspy``.
  2. :func:`similarity_transform_2d` / :func:`align_scan` — georeference
     the scan's arbitrary local coordinates with 2+ control-point pairs
     ("this scan corner is this map spot"): a least-squares 2D similarity
     (scale + rotation + translation, Horn's method), so a tape-measure
     scale error or a rotated scan both come out right.
  3. :func:`rasterize_ndsm` — bin the aligned cloud to a height-above-
     ground grid (per-cell max z minus the cloud's low-percentile ground).
  4. :func:`scan_to_footprints` — feed that grid through the existing
     :func:`src.footprint_ndsm.vectorize_ndsm` and return
     ``(ring_lnglat, height_m)`` footprints, ready for
     :func:`src.footprint_extract.add_extracted_footprints` — at which
     point the scanned shed/tree casts shade in the 2D engine and extrudes
     in the 3D preview with no further wiring.

Qt-free; needs ``numpy`` (and shapely for the vectorize step) like the
rest of the footprint pipeline — both already optional deps.
"""

from __future__ import annotations

import os
import struct
from typing import Optional

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:  # pragma: no cover
    _HAVE_NUMPY = False


# ── readers ──────────────────────────────────────────────────────────────────

_PLY_TYPES = {
    "float": ("f", 4), "float32": ("f", 4),
    "double": ("d", 8), "float64": ("d", 8),
    "char": ("b", 1), "int8": ("b", 1),
    "uchar": ("B", 1), "uint8": ("B", 1),
    "short": ("h", 2), "int16": ("h", 2),
    "ushort": ("H", 2), "uint16": ("H", 2),
    "int": ("i", 4), "int32": ("i", 4),
    "uint": ("I", 4), "uint32": ("I", 4),
}

# struct char → little-endian numpy dtype, for the fast binary path.
_PLY_NP_DTYPE = {
    "f": "<f4", "d": "<f8", "b": "i1", "B": "u1",
    "h": "<i2", "H": "<u2", "i": "<i4", "I": "<u4",
}

# Vertex properties that betray a 3D Gaussian-splat PLY (Scaniverse /
# Polycam / Luma / INRIA export): spherical-harmonic DC term, per-gaussian
# scale, and rotation quaternion. The x/y/z of such a file are the gaussian
# centres, so the same georeference flow aligns them like any point cloud.
_SPLAT_MARKER_PROPS = ("f_dc_0", "scale_0", "rot_0")


def _parse_ply_header(f) -> tuple:
    """Read a PLY header from an open binary file positioned at the start.
    Returns ``(fmt, n_vertex, props)`` where ``props`` is the list of
    ``(name, struct_char, size)`` for the vertex element. Leaves ``f`` at
    the first byte of the body."""
    if f.readline().strip() != b"ply":
        raise ValueError("not a PLY file")
    fmt = None
    n_vertex = 0
    props: list = []          # (name, struct_char, size) of element vertex
    in_vertex = False
    while True:
        line = f.readline()
        if not line:
            raise ValueError("PLY header never ended")
        parts = line.decode("ascii", "replace").strip().split()
        if not parts:
            continue
        if parts[0] == "format":
            fmt = parts[1]
        elif parts[0] == "element":
            in_vertex = parts[1] == "vertex"
            if in_vertex:
                n_vertex = int(parts[2])
        elif parts[0] == "property" and in_vertex:
            if parts[1] == "list":
                raise ValueError("list property on vertex element is "
                                 "unsupported")
            ch, size = _PLY_TYPES.get(parts[1], (None, 0))
            if ch is None:
                raise ValueError(f"unknown PLY type {parts[1]}")
            props.append((parts[2], ch, size))
        elif parts[0] == "end_header":
            break
    return fmt, n_vertex, props


def is_gaussian_splat_ply(path: str) -> bool:
    """True if ``path`` is a PLY whose vertex element carries 3D Gaussian
    splat attributes (``f_dc_*`` / ``scale_*`` / ``rot_*``) — i.e. a
    photoreal capture, not a plain point cloud. Header-only; never reads the
    (large) body. Returns False for non-PLY or unreadable files."""
    if os.path.splitext(path)[1].lower() != ".ply":
        return False
    try:
        with open(path, "rb") as f:
            _fmt, _n, props = _parse_ply_header(f)
    except (OSError, ValueError):
        return False
    names = {p[0] for p in props}
    return all(m in names for m in _SPLAT_MARKER_PROPS)


def _read_ply(path: str) -> "np.ndarray":
    """Parse a PLY file's vertex x/y/z. Supports ``format ascii`` and
    ``format binary_little_endian`` (what phone-scan apps export).

    Splat PLYs carry 50+ float properties per vertex over millions of
    vertices, so the binary path reads the whole body in one
    ``np.frombuffer`` against a structured dtype (a per-vertex Python loop
    would take minutes); only x/y/z are kept."""
    with open(path, "rb") as f:
        try:
            fmt, n_vertex, props = _parse_ply_header(f)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from None

        names = [p[0] for p in props]
        for need in ("x", "y", "z"):
            if need not in names:
                raise ValueError(f"{path}: vertex element lacks '{need}'")
        ix, iy, iz = names.index("x"), names.index("y"), names.index("z")

        if fmt == "ascii":
            pts = np.empty((n_vertex, 3), dtype="float64")
            for i in range(n_vertex):
                vals = f.readline().split()
                pts[i] = (float(vals[ix]), float(vals[iy]), float(vals[iz]))
            return pts
        if fmt == "binary_little_endian":
            rec = struct.Struct("<" + "".join(ch for (_n, ch, _s) in props))
            raw = f.read(rec.size * n_vertex)
            if len(raw) < rec.size * n_vertex:
                raise ValueError(f"{path}: truncated PLY body")
            # One structured read for the whole body, then slice x/y/z — orders
            # of magnitude faster than per-vertex unpack on million-point splats.
            dt = np.dtype([(p[0], _PLY_NP_DTYPE[p[1]]) for p in props])
            arr = np.frombuffer(raw, dtype=dt, count=n_vertex)
            return np.column_stack([
                arr["x"].astype("float64"),
                arr["y"].astype("float64"),
                arr["z"].astype("float64")]).copy()
        raise ValueError(f"{path}: unsupported PLY format {fmt!r} "
                         "(use ascii or binary_little_endian)")


def _read_xyz_text(path: str) -> "np.ndarray":
    """Whitespace- or comma-separated x y z per line; '#' comments OK."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) >= 3:
                try:
                    rows.append((float(parts[0]), float(parts[1]),
                                 float(parts[2])))
                except ValueError:
                    continue
    return np.asarray(rows, dtype="float64").reshape(-1, 3)


def _read_las(path: str) -> "np.ndarray":
    try:
        import laspy
    except ImportError as exc:
        raise RuntimeError(
            "Reading LAS/LAZ needs the optional 'laspy' package "
            "(pip install laspy). PLY and XYZ exports need no extras."
        ) from exc
    las = laspy.read(path)
    return np.column_stack([np.asarray(las.x, dtype="float64"),
                            np.asarray(las.y, dtype="float64"),
                            np.asarray(las.z, dtype="float64")])


def read_points(path: str, *, up: str = "z") -> "np.ndarray":
    """Load a point cloud as an ``(N, 3)`` float array of x/y/z metres.

    ``up`` names the file's vertical axis: ``"z"`` (LiDAR/LAS convention,
    most Polycam LiDAR exports) or ``"y"`` (GLTF/photogrammetry meshes) —
    ``"y"`` swaps so the returned cloud is always z-up.
    """
    if not _HAVE_NUMPY:
        raise RuntimeError("Point-cloud import needs the optional 'numpy' "
                           "package (pip install numpy).")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ply":
        pts = _read_ply(path)
    elif ext in (".las", ".laz"):
        pts = _read_las(path)
    elif ext in (".xyz", ".txt", ".csv"):
        pts = _read_xyz_text(path)
    else:
        raise ValueError(f"unsupported point-cloud format {ext!r} "
                         "(use .ply, .xyz, .las/.laz)")
    if pts.size == 0:
        raise ValueError(f"{path}: no points found")
    if up.lower() == "y":
        # y-up → z-up: (x, y_up, z_fwd) → (x, -z, y)
        pts = np.column_stack([pts[:, 0], -pts[:, 2], pts[:, 1]])
    return pts


# ── alignment ────────────────────────────────────────────────────────────────

def similarity_transform_2d(src_xy: list, dst_xy: list) -> tuple:
    """Least-squares 2D similarity mapping ``src_xy`` onto ``dst_xy``
    (Horn's closed form): returns ``(scale, theta_rad, tx, ty)`` such that

        dst ≈ scale * R(theta) @ src + (tx, ty)

    Needs at least 2 point pairs (2 pairs → exact fit)."""
    if not _HAVE_NUMPY:
        raise RuntimeError("alignment needs numpy")
    src = np.asarray(src_xy, dtype="float64")
    dst = np.asarray(dst_xy, dtype="float64")
    if src.shape != dst.shape or src.shape[0] < 2 or src.shape[1] != 2:
        raise ValueError("need >= 2 matching (x, y) control-point pairs")
    sc, dc = src.mean(axis=0), dst.mean(axis=0)
    s0, d0 = src - sc, dst - dc
    sxx = float(np.sum(s0[:, 0] * d0[:, 0] + s0[:, 1] * d0[:, 1]))
    sxy = float(np.sum(s0[:, 0] * d0[:, 1] - s0[:, 1] * d0[:, 0]))
    denom = float(np.sum(s0 * s0))
    if denom <= 0:
        raise ValueError("control points are coincident")
    theta = float(np.arctan2(sxy, sxx))
    scale = float(np.hypot(sxx, sxy)) / denom
    if scale <= 0:
        raise ValueError("degenerate alignment (zero scale)")
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    tx = float(dc[0] - scale * (cos_t * sc[0] - sin_t * sc[1]))
    ty = float(dc[1] - scale * (sin_t * sc[0] + cos_t * sc[1]))
    return scale, theta, tx, ty


def apply_similarity_2d(points: "np.ndarray", transform: tuple) -> "np.ndarray":
    """Apply a :func:`similarity_transform_2d` result to an ``(N, 3)`` cloud:
    x/y are mapped, z is scaled (a scan whose plan is 2% small is 2% short
    too)."""
    scale, theta, tx, ty = transform
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    return np.column_stack([
        scale * (cos_t * x - sin_t * y) + tx,
        scale * (sin_t * x + cos_t * y) + ty,
        z * scale,
    ])


def align_scan(points: "np.ndarray", control_scan_xy: list,
               control_latlng: list):
    """Georeference a scan: map its local coords into local *map* metres.

    ``control_scan_xy`` are 2+ ``(x, y)`` spots in the scan;
    ``control_latlng`` the matching ``(lat, lng)`` spots on the map.
    Returns ``(aligned_points, projector)`` — aligned x/y are metres in the
    :class:`src.projection.Projector` frame whose origin is the control
    points' centroid (so the same projector turns the rasterized result
    back into lng/lat)."""
    from src.projection import Projector
    if len(control_latlng) < 2:
        raise ValueError("need >= 2 control points to georeference a scan")
    proj = Projector.for_positions([(la, ln) for (la, ln) in control_latlng])
    dst = [proj.to_xy(la, ln) for (la, ln) in control_latlng]
    transform = similarity_transform_2d(control_scan_xy, dst)
    return apply_similarity_2d(points, transform), proj


# ── rasterize → nDSM ─────────────────────────────────────────────────────────

def rasterize_ndsm(points: "np.ndarray", *, cell_m: float = 0.25,
                   ground_percentile: float = 2.0,
                   max_height_m: float = 40.0):
    """Bin an aligned (z-up, metre) cloud into a height-above-ground grid.

    Per cell: max z minus the cloud-wide low-percentile ground estimate
    (yards are near-flat at scan scale; a percentile shrugs off the odd
    below-ground noise point). Heights are clipped to ``max_height_m`` to
    kill fliers. Empty cells are NaN — :func:`vectorize_ndsm` treats them
    as ground.

    Returns ``(ndsm, extent)`` where ``ndsm`` is rows×cols with **row 0 =
    north (max y)** and ``extent`` is ``(min_x, min_y, max_x, max_y)``.
    """
    if points.shape[0] < 10:
        raise ValueError("too few points to rasterize")
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    ground = float(np.percentile(z, ground_percentile))
    min_x, max_x = float(x.min()), float(x.max())
    min_y, max_y = float(y.min()), float(y.max())
    cols = max(1, int(np.ceil((max_x - min_x) / cell_m)))
    rows = max(1, int(np.ceil((max_y - min_y) / cell_m)))
    if rows * cols > 16_000_000:
        raise ValueError("scan area too large for the cell size — "
                         "increase cell_m")

    ci = np.clip(((x - min_x) / cell_m).astype("int64"), 0, cols - 1)
    ri = np.clip(((max_y - y) / cell_m).astype("int64"), 0, rows - 1)
    flat = ri * cols + ci

    # Accumulate against -inf (np.maximum propagates NaN), then mark the
    # never-touched cells as NaN for the vectorizer.
    ndsm = np.full(rows * cols, -np.inf)
    h = np.clip(z - ground, 0.0, max_height_m)
    np.maximum.at(ndsm, flat, h)
    ndsm[np.isneginf(ndsm)] = np.nan
    return ndsm.reshape(rows, cols), (min_x, min_y, max_x, max_y)


# ── end to end ───────────────────────────────────────────────────────────────

def scan_to_footprints(points: "np.ndarray", projector, extent_cell_m: float = 0.25,
                       *, min_height_m: float = 2.0,
                       min_area_m2: float = 1.0,
                       simplify_m: float = 0.3) -> list:
    """Aligned cloud → ``(ring_lnglat, height_m)`` footprints.

    ``points`` must already be in ``projector``'s local-metre frame (see
    :func:`align_scan`). Thresholds default tighter than the aerial nDSM
    path (min 1 m², 0.3 m simplify) — a phone scan resolves a bee-hotel
    post, not just a house."""
    from src.footprint_ndsm import vectorize_ndsm
    ndsm, (min_x, _min_y, _max_x, max_y) = rasterize_ndsm(
        points, cell_m=extent_cell_m)

    # GeoTransform straight to lng/lat: pixel (col, row) → degrees. The
    # raster is north-up (row 0 = max y), so the row step is negative.
    from src.projection import metres_per_deg
    lat0, _lng0 = projector.lat0, projector.lng0
    m_lat, m_lng = metres_per_deg(lat0)
    top_lat, west_lng = projector.to_latlng(min_x, max_y)
    gt = (west_lng, extent_cell_m / m_lng, 0.0,
          top_lat, 0.0, -extent_cell_m / m_lat)

    return vectorize_ndsm(ndsm, gt, min_height_m=min_height_m,
                          min_area_m2=min_area_m2, simplify_m=simplify_m,
                          pixel_size_m=extent_cell_m)


def sample_for_scene(points: "np.ndarray", projector, *,
                     max_points: int = 120_000,
                     ground_percentile: float = 2.0) -> dict:
    """Downsample an aligned cloud for the 3D viewer's point layer.

    Returns ``{"origin": {"lat", "lng"}, "points": [[x, y, z], ...]}`` —
    x/y in ``projector``'s local-metre frame, z relative to the cloud's
    ground estimate (so the scan sits on the scene's ground plane). The
    cloud is uniformly subsampled to ``max_points`` so the JSON push to
    the viewer stays a few MB at most. Feed the result to
    ``scene_contract.build_scene(scan=...)``."""
    n = points.shape[0]
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype("int64")
        pts = points[idx]
    else:
        pts = points
    ground = float(np.percentile(points[:, 2], ground_percentile))
    out = np.column_stack([pts[:, 0], pts[:, 1],
                           np.clip(pts[:, 2] - ground, -0.5, 60.0)])
    return {
        "origin": {"lat": projector.lat0, "lng": projector.lng0},
        "points": np.round(out, 2).tolist(),
    }


def import_scan(path: str, project_dict: dict, control_scan_xy: list,
                control_latlng: list, *, up: str = "z",
                cell_m: float = 0.25, min_height_m: float = 2.0) -> dict:
    """One call from file to project: read, georeference, rasterize,
    vectorize, and append the footprints as shade-casting
    ``canopy_footprint`` features (via
    :func:`src.footprint_extract.add_extracted_footprints`).

    Returns ``{"features": [...], "scan_sample": {...}}`` — the feature
    dicts added (the scanned structures now shade the 2D design and
    extrude in the 3D preview automatically) plus a
    :func:`sample_for_scene` point sample for the 3D viewer's
    ground-truth scan layer."""
    from src.footprint_extract import add_extracted_footprints
    points = read_points(path, up=up)
    aligned, proj = align_scan(points, control_scan_xy, control_latlng)
    rings = scan_to_footprints(aligned, proj, cell_m,
                               min_height_m=min_height_m)
    return {
        "features": add_extracted_footprints(rings, project_dict,
                                             source="scan"),
        "scan_sample": sample_for_scene(aligned, proj),
    }
