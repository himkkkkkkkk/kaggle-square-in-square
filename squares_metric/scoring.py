from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import mpmath

from .geometry import Square, measure_side_length
from .validation import (
    parse_submission,
    puzzle_structure_error,
    squares_from_rows,
    validate_decimal_literals,
    verify_no_overlaps,
)

AREA_LOWER_BOUND_TOLERANCE = 1e-7
DEFAULT_PUZZLE_SIZES = tuple(range(1, 1001))


@dataclass(frozen=True)
class PuzzleResult:
    n: int
    valid: bool
    score: float
    side_length: mpmath.mpf | None
    reason: str


@dataclass(frozen=True)
class ScoreReport:
    total_score: float
    puzzles: tuple[PuzzleResult, ...]


def score_from_side_length(n: int, side_length: float) -> float:
    return side_length / math.sqrt(n) - 1.0


def grid_fallback_score(n: int) -> float:
    return math.ceil(math.sqrt(n)) / math.sqrt(n) - 1.0


def invalid_puzzle_result(n: int, reason: str) -> PuzzleResult:
    return PuzzleResult(n, False, grid_fallback_score(n), None, reason)


def evaluate_squares(n: int, squares: Sequence[Square]) -> PuzzleResult:
    if len(squares) != n:
        return invalid_puzzle_result(n, f"expected {n} squares, received {len(squares)}")
    try:
        for square_id, square in enumerate(squares):
            validate_decimal_literals(square, square_id)
    except ValueError as error:
        return invalid_puzzle_result(n, str(error))
    feasible, reason = verify_no_overlaps(squares)
    if not feasible:
        return invalid_puzzle_result(n, reason)
    side_length = measure_side_length(squares)
    if float(side_length) < math.sqrt(n) - AREA_LOWER_BOUND_TOLERANCE:
        return invalid_puzzle_result(n, "bounding side is below the area lower bound")
    puzzle_score = max(0.0, score_from_side_length(n, float(side_length)))
    return PuzzleResult(n, True, puzzle_score, side_length, "feasible")


def evaluate_puzzle(n: int, rows: Sequence[dict[str, str]]) -> PuzzleResult:
    try:
        structure_error = puzzle_structure_error(n, rows)
        squares = squares_from_rows(n, rows) if structure_error is None else ()
    except ValueError as error:
        return invalid_puzzle_result(n, str(error))
    if structure_error:
        return invalid_puzzle_result(n, structure_error)
    return evaluate_squares(n, squares)


def score_submission_text(text: str, puzzle_sizes: Iterable[int] = DEFAULT_PUZZLE_SIZES) -> ScoreReport:
    requested_sizes = frozenset(puzzle_sizes)
    submitted_rows = parse_submission(text)
    results = tuple(
        evaluate_puzzle(n, submitted_rows[n]) if n in submitted_rows else invalid_puzzle_result(n, "missing")
        for n in sorted(requested_sizes)
    )
    return ScoreReport(sum(result.score for result in results), results)


def score_submission_file(
    submission_path: str | Path,
    puzzle_sizes: Iterable[int] = DEFAULT_PUZZLE_SIZES,
) -> ScoreReport:
    return score_submission_text(Path(submission_path).read_text(), puzzle_sizes)
