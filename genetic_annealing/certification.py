from __future__ import annotations

from dataclasses import dataclass, replace

from squares_metric import PuzzleResult, evaluate_squares

from .genome import Layout, to_squares


@dataclass(frozen=True)
class CertifiedLayout:
    """A layout together with the high-precision verdict it was certified with.

    Only layouts that passed `evaluate_squares` are ever handed on as a champion. The
    search side length, sqpack's float validator and the search fitness are never
    substitutes for this verdict.
    """

    n: int
    layout: Layout
    result: PuzzleResult
    certified_evaluations: int

    @property
    def valid(self) -> bool:
        return bool(self.result.valid)

    @property
    def score(self) -> float:
        return float(self.result.score)

    @property
    def side_length(self) -> float:
        if self.result.side_length is None:
            raise ValueError(f"layout for n={self.n} is not certified: {self.result.reason}")
        return float(self.result.side_length)


def certify_layout(layout: Layout, previous_evaluations: int = 0) -> CertifiedLayout:
    """Run the project evaluator once and count that evaluation."""
    result = evaluate_squares(layout.n, to_squares(layout))
    return CertifiedLayout(layout.n, layout, result, previous_evaluations + 1)


def certify_improvement(candidate: CertifiedLayout, incumbent: CertifiedLayout) -> CertifiedLayout:
    """Sole champion-update entry: keep the incumbent unless the candidate is valid and strictly better.

    Strictness matters: an equal-scoring candidate is not an improvement, so a search that
    cannot beat the grid leaves the grid in place. Every candidate's evaluation is counted,
    whether or not it wins.
    """
    if candidate.n != incumbent.n:
        raise ValueError("candidate and incumbent sizes must match")
    if candidate.valid and candidate.score < incumbent.score:
        return candidate
    return replace(incumbent, certified_evaluations=candidate.certified_evaluations)
