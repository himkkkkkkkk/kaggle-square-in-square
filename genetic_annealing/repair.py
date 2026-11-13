from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import SearchConfig
from .fast_geometry import candidate_pairs, overlap_depths, penetration_axis, rotated_corners
from .genome import Layout, make_layout, wrap_angles

HALF_TURN_QUARTERS = math.pi / 4.0
RIGHT_ANGLE = math.pi / 2.0
DIAGONAL = math.sqrt(2.0)


@dataclass(frozen=True)
class RepairResult:
    """Fast repair output; `separated` is not a high-precision legality proof."""

    layout: Layout
    penetration: float
    separated: bool
    sweeps: int


def rotated_half_width(angle: float) -> float:
    """Half of the axis-aligned bounding-box width of a unit square rotated by angle."""
    return 0.5 * (abs(math.cos(angle)) + abs(math.sin(angle)))


def fit_angle_to_box(angle: float, target_side: float) -> float:
    """Reduce an angle so its rotated bounding box fits inside the target square.

    A square has pi/2 rotational symmetry, so reduce to [-pi/4, pi/4] first. For target
    sides below sqrt(2), the angle is clamped to the feasible interval; for target 1
    the only feasible orientation is axis-aligned.
    """
    if target_side <= 0.0:
        raise ValueError("target_side must be positive")

    reduced = (
        float(wrap_angles(np.asarray([angle]))[0]) + HALF_TURN_QUARTERS
    ) % RIGHT_ANGLE - HALF_TURN_QUARTERS
    if target_side >= DIAGONAL:
        return reduced

    ratio = min(1.0, max(-1.0, target_side / DIAGONAL))
    limit = max(0.0, HALF_TURN_QUARTERS - math.acos(ratio))
    return float(np.clip(reduced, -limit, limit))


def clamp_to_box(layout: Layout, target_side: float) -> Layout:
    """Place every rotated square inside [0, target_side]^2 without changing its shape."""
    if target_side <= 0.0:
        raise ValueError("target_side must be positive")

    angles = np.array(
        [fit_angle_to_box(float(angle), target_side) for angle in layout.angles],
        dtype=np.float64,
    )
    half_widths = 0.5 * (np.abs(np.cos(angles)) + np.abs(np.sin(angles)))
    if np.any(2.0 * half_widths > target_side + 1e-12):
        raise ValueError("target box is too small for a unit square")

    lower = half_widths[:, None]
    upper = (target_side - half_widths)[:, None]
    centers = np.clip(layout.centers, lower, upper)
    return make_layout(centers, angles)


def _positive_pairs(
    layout: Layout,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    NDArray[np.int64],
    NDArray[np.float64],
]:
    corners = rotated_corners(layout.centers, layout.angles)
    first, second = candidate_pairs(corners)
    if first.size == 0:
        return corners, first, second, np.empty(0, dtype=np.float64)
    depths = overlap_depths(corners, layout.angles, first, second)
    keep = depths > 0.0
    return corners, first[keep], second[keep], depths[keep]


def separate_overlaps(
    layout: Layout,
    target_side: float,
    config: SearchConfig,
) -> RepairResult:
    """Fixed-target-box SAT separation repair.

    Every sweep finds the shallowest penetration axis of each overlapping pair and moves
    the pair apart along that axis by half the depth plus `repair_margin`, then clamps all
    centres back into the target box. Sweeps are finite and a stagnant penetration total
    causes an early failure exit. The returned `separated` flag only means the fast SAT
    screen found no positive penetration; the caller must still certify the layout with
    `certify_candidate()` / `evaluate_squares()`.
    """
    current = clamp_to_box(layout, target_side)
    best_penetration = math.inf
    stagnant = 0
    sweeps_done = 0

    for _ in range(config.repair_sweeps):
        corners, first, second, depths = _positive_pairs(current)
        if first.size == 0:
            return RepairResult(current, 0.0, True, sweeps_done)

        total = float(depths.sum())
        if total < best_penetration - 1e-12:
            best_penetration = total
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= config.repair_stagnation_limit:
            break

        displacement = np.zeros_like(current.centers)
        for position in np.argsort(depths)[::-1]:
            first_id = int(first[position])
            second_id = int(second[position])
            axis, depth, direction = penetration_axis(
                corners,
                current.angles,
                first_id,
                second_id,
            )
            if depth <= 0.0:
                continue
            push = 0.5 * depth + config.repair_margin
            displacement[first_id] += direction * push * axis
            displacement[second_id] -= direction * push * axis

        current = clamp_to_box(
            make_layout(current.centers + displacement, current.angles),
            target_side,
        )
        sweeps_done += 1

    corners, first, second, depths = _positive_pairs(current)
    final_penetration = 0.0 if first.size == 0 else float(depths.sum())
    return RepairResult(current, final_penetration, first.size == 0, sweeps_done)


def target_box_side(n: int, incumbent_side_length: float, config: SearchConfig) -> float:
    """T = max(sqrt(n), (1 - rho) * incumbent L), never below the area lower bound."""
    return max(math.sqrt(n), (1.0 - config.repair_rho) * float(incumbent_side_length))
