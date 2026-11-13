from __future__ import annotations

from dataclasses import dataclass, replace

from squares_metric import PuzzleResult, evaluate_squares

from .fast_geometry import rotated_corners, side_length
from .genome import Layout, to_squares


@dataclass(frozen=True)
class CertifiedIncumbent:
    """Best layout that passed evaluate_squares; only valid results are ever stored."""

    n: int
    layout: Layout
    result: PuzzleResult
    certified_evaluations: int
    fast_rejections: int = 0

    @property
    def score(self) -> float:
        return float(self.result.score)

    @property
    def side_length(self) -> float:
        return float(self.result.side_length)


def certify_candidate(candidate: Layout, incumbent: CertifiedIncumbent) -> CertifiedIncumbent:
    """Sole champion-update entry: fast screen, then evaluate_squares, then strict improvement.

    The fast screen only skips candidates whose search-side L is not smaller than the
    incumbent's certified L, because score = L / sqrt(n) - 1 is monotone in L and such a
    candidate can never strictly improve the score. Every candidate whose fast L is strictly
    smaller goes to evaluate_squares, which alone decides validity and strict score
    improvement: the float screen is never used as proof of infeasibility or non-improvement,
    and there is no tolerance window that could hide a genuinely smaller candidate.
    """
    if candidate.n != incumbent.n:
        raise ValueError("candidate and incumbent sizes must match")
    candidate_side_length = side_length(rotated_corners(candidate.centers, candidate.angles))
    if candidate_side_length >= incumbent.side_length:
        return replace(incumbent, fast_rejections=incumbent.fast_rejections + 1)
    result = evaluate_squares(incumbent.n, to_squares(candidate))
    certified_evaluations = incumbent.certified_evaluations + 1
    if result.valid and result.score < incumbent.score:
        return CertifiedIncumbent(
            n=incumbent.n,
            layout=candidate,
            result=result,
            certified_evaluations=certified_evaluations,
            fast_rejections=incumbent.fast_rejections,
        )
    return replace(incumbent, certified_evaluations=certified_evaluations)
