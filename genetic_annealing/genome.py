from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from squares_metric import Square

COORDINATE_FORMAT = ".17g"
MINIMUM_COMPRESSION_SCALE = 0.5


@dataclass(frozen=True, eq=False)
class Layout:
    """Centres (n, 2) and rotation angles (n,) of n unit squares.

    The arrays are treated as immutable: every operator returns a new Layout and copies
    before writing, so no function mutates a parent or a caller array. `eq=False` avoids
    elementwise array comparison in dataclass equality.
    """

    centers: NDArray[np.float64]
    angles: NDArray[np.float64]

    @property
    def n(self) -> int:
        return int(self.centers.shape[0])


def make_layout(centers, angles) -> Layout:
    center_array = np.array(centers, dtype=np.float64, copy=True)
    angle_array = np.array(angles, dtype=np.float64, copy=True)
    if center_array.ndim != 2 or center_array.shape[1] != 2:
        raise ValueError("centers must have shape (n, 2)")
    if angle_array.shape != (center_array.shape[0],):
        raise ValueError("angles must have shape (n,)")
    return Layout(center_array, angle_array)


def centroid(centers: NDArray[np.float64]) -> NDArray[np.float64]:
    return centers.mean(axis=0)


def recenter(layout: Layout) -> Layout:
    """Translate the layout so its centroid is the origin; L and overlaps are unchanged."""
    return Layout(layout.centers - centroid(layout.centers), layout.angles)


def wrap_angles(angles: NDArray[np.float64]) -> NDArray[np.float64]:
    """Shortest representative in [-pi, pi]: atan2(sin, cos)."""
    return np.arctan2(np.sin(angles), np.cos(angles))


def angle_difference(first: NDArray[np.float64], second: NDArray[np.float64]) -> NDArray[np.float64]:
    """Wrapped second - first, the shortest signed angular difference."""
    return wrap_angles(np.asarray(second) - np.asarray(first))


def compress_centers(
    centers: NDArray[np.float64],
    rng: np.random.Generator,
    sigma: float,
) -> NDArray[np.float64]:
    """Scale centres toward the centroid by a random factor in (0, 1]."""
    scale = max(MINIMUM_COMPRESSION_SCALE, 1.0 - abs(float(rng.normal(0.0, sigma))))
    centre = centroid(centers)
    return centre + scale * (centers - centre)


def to_squares(layout: Layout) -> tuple[Square, ...]:
    """Decimal input for the existing high-precision validator; .17g round-trips a float."""
    return tuple(
        Square(
            format(float(x), COORDINATE_FORMAT),
            format(float(y), COORDINATE_FORMAT),
            format(float(angle), COORDINATE_FORMAT),
        )
        for x, y, angle in zip(layout.centers[:, 0], layout.centers[:, 1], layout.angles)
    )
