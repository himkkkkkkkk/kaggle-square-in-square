from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

UNIT_CORNERS = np.array(
    ((0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)),
    dtype=np.float64,
)


def rotated_corners(
    centers: NDArray[np.float64],
    angles: NDArray[np.float64],
) -> NDArray[np.float64]:
    """True rotated vertices v = c + R(theta) u, shape (n, 4, 2); matches the validator."""
    cosine = np.cos(angles)[:, None]
    sine = np.sin(angles)[:, None]
    offsets_x = cosine * UNIT_CORNERS[:, 0] - sine * UNIT_CORNERS[:, 1]
    offsets_y = sine * UNIT_CORNERS[:, 0] + cosine * UNIT_CORNERS[:, 1]
    return np.stack((centers[:, 0:1] + offsets_x, centers[:, 1:2] + offsets_y), axis=-1)


def side_length(corners: NDArray[np.float64]) -> float:
    x_coordinates = corners[..., 0]
    y_coordinates = corners[..., 1]
    return float(
        max(
            x_coordinates.max() - x_coordinates.min(),
            y_coordinates.max() - y_coordinates.min(),
        )
    )


def candidate_pairs(
    corners: NDArray[np.float64],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """AABB broad phase: only pairs whose axis-aligned boxes overlap can overlap."""
    count = corners.shape[0]
    minimums = corners.min(axis=1)
    maximums = corners.max(axis=1)
    first, second = np.triu_indices(count, 1)
    close = (
        (minimums[first, 0] <= maximums[second, 0])
        & (minimums[second, 0] <= maximums[first, 0])
        & (minimums[first, 1] <= maximums[second, 1])
        & (minimums[second, 1] <= maximums[first, 1])
    )
    return first[close], second[close]


def overlap_depths(
    corners: NDArray[np.float64],
    angles: NDArray[np.float64],
    first: NDArray[np.int64],
    second: NDArray[np.int64],
) -> NDArray[np.float64]:
    """Per-pair SAT depth: the smallest positive projection overlap over the four axes."""
    cosine = np.cos(angles)
    sine = np.sin(angles)
    axes = []
    for index in (first, second):
        axes.append(np.stack((cosine[index], sine[index]), axis=1))
        axes.append(np.stack((-sine[index], cosine[index]), axis=1))
    first_corners = corners[first]
    second_corners = corners[second]
    depths = []
    for axis in axes:
        first_projection = np.einsum("mkc,mc->mk", first_corners, axis)
        second_projection = np.einsum("mkc,mc->mk", second_corners, axis)
        overlap = np.minimum(first_projection.max(axis=1), second_projection.max(axis=1)) - np.maximum(
            first_projection.min(axis=1),
            second_projection.min(axis=1),
        )
        depths.append(overlap)
    return np.maximum(np.min(np.stack(depths, axis=0), axis=0), 0.0)


def penetration(corners: NDArray[np.float64], angles: NDArray[np.float64]) -> float:
    """Non-negative search penalty; 0 means the fast SAT screen found no positive overlap."""
    first, second = candidate_pairs(corners)
    if first.size == 0:
        return 0.0
    return float(overlap_depths(corners, angles, first, second).sum())


def penetration_axis(
    corners: NDArray[np.float64],
    angles: NDArray[np.float64],
    first: int,
    second: int,
) -> tuple[NDArray[np.float64], float, float]:
    """Shallowest SAT axis for one overlapping pair.

    Returns `(unit_axis, depth, direction)`. `direction = +1` means square `first`
    should move along `+axis` and square `second` along `-axis`; `-1` is the reverse.
    `depth` is clamped to zero when the fast screen sees no positive overlap.
    """
    cosine = np.cos(angles)
    sine = np.sin(angles)
    candidate_axes = (
        np.array((cosine[first], sine[first]), dtype=np.float64),
        np.array((-sine[first], cosine[first]), dtype=np.float64),
        np.array((cosine[second], sine[second]), dtype=np.float64),
        np.array((-sine[second], cosine[second]), dtype=np.float64),
    )
    first_corners = corners[first]
    second_corners = corners[second]
    best_axis = candidate_axes[0]
    best_depth = math.inf
    for axis in candidate_axes:
        first_projection = first_corners @ axis
        second_projection = second_corners @ axis
        overlap = float(
            min(first_projection.max(), second_projection.max())
            - max(first_projection.min(), second_projection.min())
        )
        if overlap < best_depth:
            best_depth = overlap
            best_axis = axis

    first_center = first_corners.mean(axis=0)
    second_center = second_corners.mean(axis=0)
    direction = 1.0 if float(np.dot(first_center - second_center, best_axis)) >= 0.0 else -1.0
    return best_axis, max(0.0, best_depth), direction
