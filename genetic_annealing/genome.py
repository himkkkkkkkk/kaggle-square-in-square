from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from squares_metric import Square

COORDINATE_FORMAT = ".17g"
GRID_OFFSET = 0.5


@dataclass(frozen=True, eq=False)
class Layout:
    """Centres (n, 2) and rotation angles (n,) of n unit squares.

    The arrays are treated as immutable: every conversion copies first, so a Layout never
    aliases a caller array and no function can mutate an existing layout in place.
    `eq=False` avoids elementwise array comparison in dataclass equality.
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


def layout_from_configuration(configuration) -> Layout:
    """Split a sqpack (n, 3) genome of (x, y, theta) rows into centres and angles."""
    genome = np.array(configuration, dtype=np.float64, copy=True)
    if genome.ndim != 2 or genome.shape[1] != 3:
        raise ValueError("configuration must have shape (n, 3)")
    return make_layout(genome[:, :2], genome[:, 2])


def grid_layout(n: int) -> Layout:
    """Legal fallback and reference baseline: the first n cells of the ceil(sqrt n) grid."""
    if n < 1:
        raise ValueError("n must be at least 1")
    width = math.ceil(math.sqrt(n))
    identifiers = np.arange(n)
    centers = np.stack(
        (identifiers % width + GRID_OFFSET, identifiers // width + GRID_OFFSET),
        axis=1,
    )
    return make_layout(centers, np.zeros(n))


def to_squares(layout: Layout) -> tuple[Square, ...]:
    """Decimal input for the high-precision validator; .17g round-trips a float exactly."""
    return tuple(
        Square(
            format(float(x), COORDINATE_FORMAT),
            format(float(y), COORDINATE_FORMAT),
            format(float(angle), COORDINATE_FORMAT),
        )
        for x, y, angle in zip(layout.centers[:, 0], layout.centers[:, 1], layout.angles)
    )
