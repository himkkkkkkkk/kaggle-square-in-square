from __future__ import annotations

from dataclasses import dataclass

from .config import SearchConfig
from .fast_geometry import penetration, rotated_corners, side_length
from .genome import Layout


@dataclass(frozen=True)
class SearchEvaluation:
    side_length: float
    penetration: float
    fitness: float


def evaluate_search(layout: Layout, config: SearchConfig) -> SearchEvaluation:
    """Search-only ranking value F = L + lambda * P; never an official score or proof."""
    corners = rotated_corners(layout.centers, layout.angles)
    layout_side_length = side_length(corners)
    layout_penetration = penetration(corners, layout.angles)
    return SearchEvaluation(
        side_length=layout_side_length,
        penetration=layout_penetration,
        fitness=layout_side_length + config.penalty_weight * layout_penetration,
    )
