"""
src/succession_engine.py — the Temporal Succession Engine (V2.21).

Turns the growth timeline from a purely *visual* scaling into an ecological
simulation. Today the year slider scales the procedural plant meshes but the
plants are otherwise frozen: a sun-loving prairie perennial placed under a
Trembling Aspen still reads as healthy at year 15, even though the aspen's
expanding canopy would have shaded it out years earlier. This module supplies
the missing biology so the year-N scene shows the *climax community* — the
survivors — rather than every plant held at full health forever.

Three pieces, each built on the existing single-source-of-truth machinery so
nothing drifts from what the 2D map and 3D viewer already draw:

  * **Growth matrix** — each plant's height and canopy radius at year N, read
    from :func:`src.scene3d.plant_3d_state` (the very growth curve + colony
    spread the timeline already uses). See :meth:`SuccessionEngine.growth_matrix`.

  * **Dynamic shade caster** — the shade experienced *at each plant's own
    location* from every taller neighbour scaled to year N, using
    :mod:`src.shade` / :mod:`src.solar`'s shadow geometry (the same capsule /
    tapering-crown model as the 2D shade overlay), sampled over the season /
    day sun envelope. Point-sampled at the receivers rather than rasterised
    over a grid, so it is ``O(years · casters · receivers · moments)`` with the
    caster↔receiver pairs pruned to those that can ever physically interact —
    not bound to a grid resolution.

  * **Survival evaluator** — cumulative shade *stress* against each plant's
    ``sun_requirement`` tolerance, integrated over the growth trajectory
    (years 1..N), giving a monotone health coefficient: ``1.0`` healthy →
    *declining* → ``0.0`` *dead*. Because a caster's footprint only ever grows,
    experienced shade is non-decreasing in year, so decline never spuriously
    reverses as the slider moves — an over-topped plant that dies stays dead.

Pure, Qt-free, DB-free (``get_plant`` is injected). No shapely and no network
are required: the point-in-shadow test uses the always-available capsule /
tree-taper geometry shared with :mod:`src.shade`, so it runs identically in
headless CI and in the packaged app.

Design principle P4 (time is the most undervalued design variable — the design
is a *trajectory*, not an install-day snapshot); also P3 (relationships over
components — the competitive edge between an overstory and the understory it
shades is precisely what is modelled here) and P9 (uncertainty is a feature —
health ships as a 0–1 coefficient with honest declining/dead bands and defaults
to "no mortality" where a plant's light needs are unknown, never a false-precise
alive/dead flip). See docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from src.projection import M_PER_DEG_LAT
from src.plant_conditions import condition_tokens
from src.scene3d import plant_3d_state
from src import shade as _shade
from src.solar import sun_position, shadow_azimuth, shadow_length_factor

# ── Tuning constants ─────────────────────────────────────────────────────────
# Shade-fraction a plant of each sun requirement can sit in before it starts to
# accrue stress. Aligned with src/placement_score._shade_match / shade_zones'
# tags: full-sun species fail as soon as the shade tag would tip past full_sun
# (~0.35); partial-shade generalists tolerate real understory shade; full-shade
# species are never shade-stressed. A multi-value sun_requirement (V1.84, e.g.
# "full_sun,partial_shade") takes the MOST tolerant ceiling — the plant "fits"
# if ANY token does, matching how the rest of the app reads the field.
_SHADE_CEILING = {"full_sun": 0.35, "partial_shade": 0.70, "full_shade": 1.0}
# Unknown light needs → lean generalist and, crucially, forgiving: we do not
# invent mortality for a plant whose requirement we cannot read (P9).
_DEFAULT_CEILING = 0.65

# Shade fraction assigned to a plant sitting *under* an overtopping crown. Not a
# flat 1.0: even a dense summer canopy leaks sky/side light, and we prefer to
# under-claim mortality over inventing it (P9). This is the evergreen / unknown
# value — a crown that is opaque all season.
_UNDER_CANOPY_SHADE = 0.9

# A declared-*deciduous* crown is bare for the shoulders of the growing season
# (leaf-out ~mid-May, drop ~late-Sept in the prairies), so an understory plant
# banks real spring + fall light beneath it — spring ephemerals live on exactly
# this. Its effective growing-season shade is a fraction of an evergreen's, so a
# part-shade plant thrives under a deciduous tree where it would struggle under a
# spruce. Coarse and honest (P9), mirroring the leaf-off idea in src/shade.py
# (`_LEAF_OFF_WEIGHT`) without pretending to per-day precision. Only crowns that
# *declare* foliage="deciduous" get the break — unknown stays opaque, never
# invented-transparent.
_DECIDUOUS_LEAF_ON = 0.6

# Cumulative "stress-years" (stress in [0,1] summed over the trajectory) that
# take a plant from full health to dead. ~5 means a fully-over-shaded plant
# dies in about five seasons, and half-over-shaded in about ten — the gradual
# decline of a shaded-out understory, not an instant flip.
_LETHAL_STRESS_YEARS = 5.0

# Health-coefficient → state bands.
_DECLINING_BELOW = 0.66     # below this: visibly struggling
_DEAD_BELOW = 0.20          # below this: gone from the climax community

# Canopy trees are *suppressed* by crowding, not shaded to death like an
# understory forb: a young tree overtopped in a gap grows into the canopy rather
# than being culled. So a tree receiver's health is floored here — it can read
# "declining" (visibly crowded) but never "dead". Understory layers stay fully
# mortal. Above _DEAD_BELOW, below _DECLINING_BELOW.
_TREE_HEALTH_FLOOR = 0.3

# A caster must overtop a receiver's crown by at least this much (metres) to
# shade it — a plant is not shaded by a neighbour no taller than itself.
_OVERTOP_MARGIN_M = 0.5

# Discrete growth-matrix reporting nodes (the brief's "Year 1/3/5/10/15/30").
GROWTH_MATRIX_YEARS = (1, 3, 5, 10, 15, 30)

_HEALTHY, _DECLINING, _DEAD = "healthy", "declining", "dead"


def shade_ceiling(sun_requirement) -> float:
    """Max seasonal shade fraction a plant tolerates before accruing stress.

    Reads the (possibly multi-value) ``sun_requirement`` field and returns the
    most tolerant matching ceiling; unknown/empty → :data:`_DEFAULT_CEILING`."""
    tokens = condition_tokens(sun_requirement)
    if not tokens:
        return _DEFAULT_CEILING
    return max(_SHADE_CEILING.get(t, _DEFAULT_CEILING) for t in tokens)


def _leaf_weight(foliage) -> float:
    """How much of an evergreen's shade a crown of this foliage casts over the
    understory's growing season. A declared-*deciduous* crown is bare for the
    season's shoulders → :data:`_DECIDUOUS_LEAF_ON`; everything else (evergreen,
    semi-evergreen, unknown) stays fully opaque (1.0) — unknown ≠ transparent."""
    return _DECIDUOUS_LEAF_ON if (foliage or "").strip().lower() == "deciduous" \
        else 1.0


def _state_for(health: float) -> str:
    if health < _DEAD_BELOW:
        return _DEAD
    if health < _DECLINING_BELOW:
        return _DECLINING
    return _HEALTHY


def static_casters_from_project(project: dict) -> list[dict]:
    """The design's *non-growing* shade casters — existing trees, buildings and
    user-drawn canopy/structure footprints — as :mod:`src.shade` caster dicts.

    These are already mature and fixed in size, so the engine treats them as
    constant across the timeline (an understory plant under an existing mature
    tree is shaded from year one). Reuses ``shade.casters_from_project`` on the
    project with placed-plant features removed, so the parsing (heights, radii,
    tree vs building kind, footprints) stays identical to the 2D shade engine."""
    feats = [f for f in (project or {}).get("features", [])
             if (f.get("properties") or {}).get("element_type") != "plant"]
    try:
        return _shade.casters_from_project({"features": feats})
    except Exception:  # noqa: BLE001 — static casters are best-effort
        return []


class SuccessionEngine:
    """Compute shade-driven decline for a design's placed plants over time.

    ``placed`` is a list of placed-plant records (``plant_id`` / ``lat`` /
    ``lng`` — the shape :func:`src.project_store.plant_record_from_feature`
    returns). ``get_plant`` is injectable for tests (defaults to the DB).
    ``static_casters`` are non-growing casters (see
    :func:`static_casters_from_project`). ``origin`` pins the local metric
    frame + sun position (defaults to the receiver/caster centroid).

    Results are aligned by the *index* of ``placed`` so a caller iterating the
    same feature list can join them positionally.
    """

    def __init__(self, placed, get_plant: Optional[Callable] = None, *,
                 static_casters: Optional[list] = None,
                 origin: Optional[tuple] = None,
                 lethal_stress_years: float = _LETHAL_STRESS_YEARS):
        if get_plant is None:
            from src.db.plants import get_plant as _gp
            get_plant = _gp
        self._lethal = max(0.5, float(lethal_stress_years))

        rec_cache: dict = {}

        def _rec(pid):
            if pid not in rec_cache:
                rec_cache[pid] = get_plant(pid) or {}
            return rec_cache[pid]

        # ── Receivers (the design's growing plants) ──────────────────────────
        self._plants: list = []     # per-plant static context
        lat_acc: list = []
        lng_acc: list = []
        for p in placed or []:
            lat = p.get("lat")
            lng = p.get("lng")
            if lat is None or lng is None:
                # Keep the slot so indices stay aligned with the caller's list,
                # but mark it un-evaluable (no position → never shaded).
                self._plants.append(None)
                continue
            pid = p.get("plant_id")
            rec = _rec(pid)
            # Mature dimensions (year 0 = full size) for reach pruning.
            mature = plant_3d_state(rec, lat, lng, 0)
            self._plants.append({
                "plant_id": pid,
                "common_name": p.get("common_name") or rec.get("common_name", ""),
                "rec": rec,
                "lat": lat, "lng": lng,
                "sun_requirement": rec.get("sun_requirement") or "",
                "ceiling": shade_ceiling(rec.get("sun_requirement")),
                "mature_h": mature["height_m"],
                "mature_r": max(0.1, mature["canopy_m"] / 2.0),
                # Foliage drives the leaf-off shade break this plant casts as a
                # neighbour; is_tree exempts it from being shaded to *death*.
                "foliage": (rec.get("deciduous_evergreen") or "").strip().lower(),
                "is_tree": (rec.get("plant_type") or "").strip().lower() == "tree",
            })
            lat_acc.append(lat)
            lng_acc.append(lng)

        # ── Static casters ───────────────────────────────────────────────────
        self._statics: list = []
        for c in static_casters or []:
            self._statics.append({
                "lat": c["lat"], "lng": c["lng"],
                "height_m": float(c.get("height_m") or 0.0),
                "radius_m": max(0.1, float(c.get("radius_m") or 0.5)),
                "is_tree": c.get("kind") == "tree",
                # shade.casters_from_project carries foliage for declared trees;
                # unknown stays opaque (leaf weight 1.0).
                "foliage": c.get("foliage"),
            })
            lat_acc.append(c["lat"])
            lng_acc.append(c["lng"])

        # ── Local metric frame ────────────────────────────────────────────────
        if origin is not None:
            self._lat0, self._lng0 = origin
        elif lat_acc:
            self._lat0 = sum(lat_acc) / len(lat_acc)
            self._lng0 = sum(lng_acc) / len(lng_acc)
        else:
            self._lat0 = self._lng0 = 0.0
        self._cos_lat = math.cos(math.radians(self._lat0)) or 1e-9

        for pl in self._plants:
            if pl is not None:
                pl["x"], pl["y"] = self._to_xy(pl["lat"], pl["lng"])
        for s in self._statics:
            s["x"], s["y"] = self._to_xy(s["lat"], s["lng"])

        # ── Sun-moment envelope (year-independent) ────────────────────────────
        # (sin(shadow_dir), cos(shadow_dir), shadow_length_factor) per sampled
        # moment where the sun is high enough to cast — matches shade.shade_grid's
        # season/day spread so the two agree on which moments count.
        self._moments: list = []
        from datetime import datetime, timedelta
        for mo, day in _shade._SAMPLE_MONTHS_DAYS:
            for hr in _shade._SAMPLE_HOURS_LOCAL:
                dt = datetime(2025, mo, day) + timedelta(
                    hours=hr - self._lng0 / 15.0)
                sun = sun_position(self._lat0, self._lng0, dt)
                if sun.altitude < _shade._MIN_SUN_ALT:
                    continue
                sd = math.radians(shadow_azimuth(sun.azimuth))
                self._moments.append((math.sin(sd), math.cos(sd),
                                      shadow_length_factor(sun.altitude)))

        # ── Prune caster↔receiver pairs to those that can ever interact ───────
        # Longest a shadow reaches: the lowest sampled sun × its height, clamped.
        max_lf = max((m[2] for m in self._moments), default=0.0)
        self._cands: list = []      # per receiver index → list of (kind, j)
        for i, pl in enumerate(self._plants):
            cands: list = []
            if pl is not None and pl["ceiling"] < 1.0 and self._moments:
                cands = self._candidates_for(i, pl, max_lf)
            self._cands.append(cands)

        # Memo caches: growth dims per (kind,idx,year); shade fraction per
        # (receiver, year). Both are pure functions of their keys, so repeated
        # evaluate_year() calls (e.g. a slider drag or flyover) stay cheap.
        self._grow_cache: dict = {}
        self._shade_cache: dict = {}

    # ── frame helpers ──────────────────────────────────────────────────────
    def _to_xy(self, lat: float, lng: float) -> tuple:
        return ((lng - self._lng0) * M_PER_DEG_LAT * self._cos_lat,
                (lat - self._lat0) * M_PER_DEG_LAT)

    def _candidates_for(self, i: int, pl: dict, max_lf: float) -> list:
        """Casters that could ever overtop and reach receiver ``i`` at maturity.
        Prunes the O(N²) pair space to physically plausible interactions."""
        rx, ry = pl["x"], pl["y"]
        rh = pl["mature_h"]
        out: list = []
        for j, other in enumerate(self._plants):
            if j == i or other is None:
                continue
            if other["mature_h"] <= rh + _OVERTOP_MARGIN_M:
                continue
            reach = (min(other["mature_h"] * max_lf, _shade._MAX_SHADOW_M)
                     + other["mature_r"])
            if (rx - other["x"]) ** 2 + (ry - other["y"]) ** 2 <= reach * reach:
                out.append(("g", j))
        for j, s in enumerate(self._statics):
            if s["height_m"] <= rh + _OVERTOP_MARGIN_M:
                continue
            reach = (min(s["height_m"] * max_lf, _shade._MAX_SHADOW_M)
                     + s["radius_m"])
            if (rx - s["x"]) ** 2 + (ry - s["y"]) ** 2 <= reach * reach:
                out.append(("s", j))
        return out

    # ── growth matrix ──────────────────────────────────────────────────────
    def _dims(self, kind: str, idx: int, year: int) -> tuple:
        """(height_m, canopy_radius_m, is_tree) of a caster/receiver at ``year``.
        Growing plants scale via ``plant_3d_state``; statics are constant."""
        if kind == "s":
            s = self._statics[idx]
            return s["height_m"], s["radius_m"], s["is_tree"]
        key = (idx, year)
        cached = self._grow_cache.get(key)
        if cached is None:
            pl = self._plants[idx]
            # Year >= 1 for the growth trajectory (year 0 is the mature preview).
            st = plant_3d_state(pl["rec"], pl["lat"], pl["lng"], max(1, year))
            cached = (st["height_m"], max(0.05, st["canopy_m"] / 2.0), True)
            self._grow_cache[key] = cached
        return cached

    def growth_matrix(self, index: int,
                      years: tuple = GROWTH_MATRIX_YEARS) -> dict:
        """A plant's canopy height + radius at discrete years — the "growth
        matrix" the design brief describes, exposed for scripting / analysis /
        the timeline UI. ``{year: {"height_m", "canopy_radius_m"}}``."""
        pl = self._plants[index] if 0 <= index < len(self._plants) else None
        if pl is None:
            return {}
        out: dict = {}
        for y in years:
            h, r, _ = self._dims("g", index, y)
            out[int(y)] = {"height_m": round(h, 3),
                           "canopy_radius_m": round(r, 3)}
        return out

    # ── dynamic shade at a receiver ──────────────────────────────────────────
    def experienced_shade(self, index: int, year: int) -> float:
        """Growing-season shade fraction (0..1) at plant ``index`` at ``year``.

        Two mechanisms, combined by taking the stronger:

          * **Overhead canopy cover** — if the plant sits *under* an overtopping
            caster's canopy disk (horizontal offset ≤ the caster's year-N canopy
            radius) it is in deep shade essentially all day; the crown occupies
            the sky between it and the sun for nearly every sun position. This is
            the dominant understory-suppression term and the one a pure ground-
            shadow grid misses (its noon shadow falls *north* of the trunk, not
            under it).
          * **Cast shadow** — for plants near but not under a crown, the fraction
            of sampled sun-moments the point lies in the swept down-sun shadow,
            using the same capsule / tapering-crown geometry as ``src.shade``.

        Casters shorter than (or level with) the receiver at ``year`` do not
        count — a plant is only shaded by a neighbour that overtops it."""
        pl = self._plants[index] if 0 <= index < len(self._plants) else None
        if pl is None:
            return 0.0
        cands = self._cands[index]
        moments = self._moments
        if not cands or not moments or year <= 0:
            return 0.0
        key = (index, year)
        cached = self._shade_cache.get(key)
        if cached is not None:
            return cached

        rx, ry = pl["x"], pl["y"]
        rh, _, _ = self._dims("g", index, year)
        # Resolve each candidate caster's year-N dims + foliage weight once.
        active: list = []
        for kind, j in cands:
            ch, cr, is_tree = self._dims(kind, j, year)
            if ch <= rh + _OVERTOP_MARGIN_M:
                continue
            src = self._statics[j] if kind == "s" else self._plants[j]
            lw = _leaf_weight(src.get("foliage"))
            active.append((src["x"], src["y"], ch, cr, is_tree, lw))
        if not active:
            self._shade_cache[key] = 0.0
            return 0.0

        # Overhead canopy cover — moment-independent. Under an overtopping crown
        # the sky above is blocked, which a ground-cast shadow alone can't
        # express. A deciduous crown blocks less over the season (leaf weight),
        # so take the strongest overhead cover among the crowns the plant sits
        # beneath — an evergreen overhead beats a deciduous one.
        under = 0.0
        for cx, cy, ch, cr, _is_tree, lw in active:
            if (rx - cx) ** 2 + (ry - cy) ** 2 <= cr * cr:
                under = max(under, _UNDER_CANOPY_SHADE * lw)

        # Cast shadow — fraction of sampled sun-moments the point lies in a swept
        # down-sun shadow, each caster weighted by its foliage (a bare deciduous
        # crown intercepts less). Per moment, keep the strongest-weighted hit.
        wsum = 0.0
        for sin_d, cos_d, lf in moments:
            best = 0.0
            for cx, cy, ch, cr, is_tree, lw in active:
                if lw <= best:
                    continue          # can't beat a stronger hit already found
                shadow_len = ch * lf
                if shadow_len > _shade._MAX_SHADOW_M:
                    shadow_len = _shade._MAX_SHADOW_M
                if shadow_len <= 1e-6:
                    continue
                # Receiver offset from caster, metres (east, north).
                pe = rx - cx
                pn = ry - cy
                tip_e = shadow_len * sin_d
                tip_n = shadow_len * cos_d
                seg2 = shadow_len * shadow_len          # = tip_e² + tip_n²
                t = (pe * tip_e + pn * tip_n) / seg2
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                de = pe - t * tip_e
                dn = pn - t * tip_n
                d2 = de * de + dn * dn
                # Trees taper (thin trunk → full crown → 0 at the tip); a
                # building-like caster is a constant-radius capsule.
                w = _shade._tree_halfwidth(t, cr) if is_tree else cr
                if d2 <= w * w:
                    best = lw
            wsum += best
        cast = wsum / len(moments)

        # The two mechanisms combine by taking the stronger.
        frac = max(under, cast)
        self._shade_cache[key] = frac
        return frac

    # ── survival evaluator ───────────────────────────────────────────────────
    def health_at(self, index: int, year: int) -> tuple:
        """``(health, shade_fraction_at_year, overtopped)`` for plant ``index``.

        Health is ``1 - S/lethal`` where ``S`` is cumulative shade stress
        integrated over years 1..year: each year contributes
        ``min(1, (shade - ceiling) / (1 - ceiling))`` when the plant is shaded
        past its tolerance. Monotone (shade only grows), so a plant that dies
        stays dead as the slider advances."""
        pl = self._plants[index] if 0 <= index < len(self._plants) else None
        if pl is None:
            return 1.0, 0.0, False
        ceiling = pl["ceiling"]
        if year <= 0 or ceiling >= 1.0 or not self._cands[index]:
            return 1.0, 0.0, False
        inv = 1.0 / (1.0 - ceiling)
        stress = 0.0
        overtopped = False
        for y in range(1, int(year) + 1):
            over = self.experienced_shade(index, y) - ceiling
            if over > 0:
                overtopped = True
                stress += over * inv if over * inv < 1.0 else 1.0
                if stress >= self._lethal:
                    stress = self._lethal
                    break
        health = max(0.0, 1.0 - stress / self._lethal)
        # Canopy trees are suppressed by crowding, not shaded to death like an
        # understory forb: a young tree overtopped in a gap grows into the
        # canopy. Floor a tree's health so it can read "declining" but never
        # drop out of the design.
        if pl.get("is_tree"):
            health = max(health, _TREE_HEALTH_FLOOR)
        return health, self.experienced_shade(index, int(year)), overtopped

    def evaluate_year(self, year: int) -> dict:
        """The succession state of the whole design at ``year``.

        Returns a JSON-serialisable dict::

            {
              "year": int,
              "counts": {"healthy", "declining", "dead"},
              "plants": [ {index, plant_id, common_name, health, state,
                           shade_fraction, sun_requirement, overtopped}, ... ],
              "delta":  [ ...the subset whose state != "healthy"... ],
            }

        ``plants`` is aligned to the input ``placed`` list by ``index``;
        ``delta`` is the "diminished health coefficients" the brief asks for —
        exactly the plants the growing canopy has pushed into decline or death."""
        year = int(year)
        plants: list = []
        counts = {_HEALTHY: 0, _DECLINING: 0, _DEAD: 0}
        for i, pl in enumerate(self._plants):
            if pl is None:
                continue
            health, frac, overtopped = self.health_at(i, year)
            state = _state_for(health)
            counts[state] += 1
            plants.append({
                "index": i,
                "plant_id": pl["plant_id"],
                "common_name": pl["common_name"],
                "health": round(health, 3),
                "state": state,
                "shade_fraction": round(frac, 3),
                "sun_requirement": pl["sun_requirement"],
                "overtopped": overtopped,
            })
        return {
            "year": year,
            "counts": counts,
            "plants": plants,
            "delta": [p for p in plants if p["state"] != _HEALTHY],
        }


def evaluate_project(project: dict, year: int,
                     get_plant: Optional[Callable] = None,
                     origin: Optional[tuple] = None) -> dict:
    """Convenience wrapper: build a :class:`SuccessionEngine` for ``project``
    (placed plants + its static casters) and return :meth:`evaluate_year`.
    Mirrors ``shade.shade_grid_for_design`` for the scripting facade / tests."""
    from src.project_store import plant_record_from_feature
    placed = [r for r in
              (plant_record_from_feature(f)
               for f in (project or {}).get("features", []))
              if r is not None]
    engine = SuccessionEngine(
        placed, get_plant=get_plant,
        static_casters=static_casters_from_project(project), origin=origin)
    return engine.evaluate_year(year)
