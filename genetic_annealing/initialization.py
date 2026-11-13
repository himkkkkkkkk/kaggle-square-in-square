from __future__ import annotations

import math

import numpy as np

from .config import SearchConfig
from .genome import Layout, centroid, make_layout, recenter, wrap_angles

GRID_OFFSET = 0.5
MINIMUM_INITIAL_SCALE = 0.5
N5_CONSTRUCTION_GAP = 1e-7


def grid_layout(n: int) -> Layout:
    """Legal fallback: first n cells of the ceil(sqrt(n)) x ceil(sqrt(n)) unit grid."""
    width = math.ceil(math.sqrt(n))
    identifiers = np.arange(n)
    centers = np.stack(
        (identifiers % width + GRID_OFFSET, identifiers // width + GRID_OFFSET),
        axis=1,
    )
    return make_layout(centers, np.zeros(n))


def n5_structural_layout() -> Layout:
    """Analytic non-grid n=5 construction with four axis-aligned corners and a 45-degree centre.

    L = 2 + 1/sqrt(2) + 1e-7 > 2 + 1/sqrt(2), so the central diamond touches the four
    corner squares only across a tiny gap. This is a feasible construction, not a claim
    of optimality.
    """
    side = 2.0 + 1.0 / math.sqrt(2.0) + N5_CONSTRUCTION_GAP
    centers = np.array(
        (
            (0.5, 0.5),
            (side - 0.5, 0.5),
            (0.5, side - 0.5),
            (side - 0.5, side - 0.5),
            (side / 2.0, side / 2.0),
        ),
        dtype=np.float64,
    )
    angles = np.array((0.0, 0.0, 0.0, 0.0, math.pi / 4.0), dtype=np.float64)
    return make_layout(centers, angles)


def staggered_rows_layout(n: int) -> Layout:
    """Cheap heterogeneous seed: every other grid row is shifted half a square.

    Adjacent rows differ by exactly one unit in y, so even the shifted rows touch only
    at boundaries. The seed need not improve L; it only broadens the explored topology.
    """
    width = math.ceil(math.sqrt(n))
    identifiers = np.arange(n)
    rows = identifiers // width
    centers = np.stack(
        (
            identifiers % width + GRID_OFFSET + 0.5 * (rows % 2),
            rows + GRID_OFFSET,
        ),
        axis=1,
    )
    return make_layout(centers, np.zeros(n))


def structural_seeds(n: int) -> tuple[Layout, ...]:
    """Heterogeneous seeds certified before evolution; n=5 gets the analytic construction."""
    seeds: list[Layout] = []
    if n == 5:
        seeds.append(n5_structural_layout())
    if n >= 2:
        seeds.append(staggered_rows_layout(n))
    return tuple(seeds)


def initial_population(n: int, rng: np.random.Generator, config: SearchConfig) -> tuple[Layout, ...]:
    """Grid first, then structural seeds, then perturbed grid copies; members need not be legal."""
    grid = grid_layout(n)
    members = [grid]
    for seed in structural_seeds(n):
        if len(members) >= config.population_size:
            break
        members.append(seed)

    while len(members) < config.population_size:
        centers = grid.centers + rng.normal(0.0, config.initial_center_jitter, size=grid.centers.shape)
        angles = rng.normal(0.0, config.initial_angle_jitter, size=n)
        large_angles = rng.random(n) < config.initial_large_angle_probability
        angles = np.where(
            large_angles,
            rng.normal(0.0, config.initial_large_angle_sigma, size=n),
            angles,
        )
        scale = max(MINIMUM_INITIAL_SCALE, 1.0 + float(rng.normal(0.0, config.initial_scale_sigma)))
        centre = centroid(centers)
        squeezed = centre + scale * (centers - centre)
        members.append(recenter(make_layout(squeezed, wrap_angles(angles))))
    return tuple(members)
