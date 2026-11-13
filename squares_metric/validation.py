from __future__ import annotations

import csv
import io
import math
import re
from collections import defaultdict
from collections.abc import Sequence

from .geometry import (
    Square,
    candidate_pairs,
    certify_pair_separation,
    float_pair_status,
    prepare_float_squares,
)

MAXIMUM_PUZZLE_SIZE = 1000
MAXIMUM_COORDINATE_MAGNITUDE = 1e4
MAXIMUM_ANGLE_MAGNITUDE = 100.0
MAXIMUM_DECIMAL_LITERAL_LENGTH = 100
REQUIRED_SUBMISSION_COLUMNS = frozenset(("n", "square_id", "x", "y", "angle"))
DECIMAL_LITERAL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def parse_submission(text: str) -> dict[int, tuple[dict[str, str], ...]]:
    reader = csv.DictReader(io.StringIO(text))
    missing_columns = REQUIRED_SUBMISSION_COLUMNS.difference(reader.fieldnames or ())
    if missing_columns:
        raise ValueError(f"missing columns: {sorted(missing_columns)}")
    rows_by_puzzle = defaultdict(list)
    for row_number, row in enumerate(reader, start=2):
        puzzle_size = int(row["n"])
        if not 1 <= puzzle_size <= MAXIMUM_PUZZLE_SIZE:
            raise ValueError(f"row {row_number}: n={puzzle_size} is outside 1..{MAXIMUM_PUZZLE_SIZE}")
        rows_by_puzzle[puzzle_size].append(row)
    return {n: tuple(rows) for n, rows in rows_by_puzzle.items()}


def puzzle_structure_error(n: int, rows: Sequence[dict[str, str]]) -> str | None:
    if len(rows) != n:
        return f"expected {n} rows, received {len(rows)}"
    square_ids = {int(row["square_id"]) for row in rows}
    expected_ids = set(range(n))
    if square_ids != expected_ids:
        return f"square_id values must be 0..{n - 1}"
    return None


def squares_from_rows(n: int, rows: Sequence[dict[str, str]]) -> tuple[Square, ...]:
    rows_by_id = {int(row["square_id"]): row for row in rows}
    return tuple(
        Square(
            rows_by_id[square_id]["x"].strip(),
            rows_by_id[square_id]["y"].strip(),
            rows_by_id[square_id]["angle"].strip(),
        )
        for square_id in range(n)
    )


def validate_decimal_literals(square: Square, square_id: int) -> None:
    for field_name, literal in (("x", square.x), ("y", square.y), ("angle", square.angle)):
        if len(literal) > MAXIMUM_DECIMAL_LITERAL_LENGTH or not DECIMAL_LITERAL.fullmatch(literal):
            raise ValueError(f"square {square_id}: {field_name} is not a decimal literal")
        value = float(literal)
        if not math.isfinite(value):
            raise ValueError(f"square {square_id}: {field_name} is outside float range")
    if max(abs(float(square.x)), abs(float(square.y))) > MAXIMUM_COORDINATE_MAGNITUDE:
        raise ValueError(f"square {square_id}: coordinate magnitude exceeds {MAXIMUM_COORDINATE_MAGNITUDE:g}")
    if abs(float(square.angle)) > MAXIMUM_ANGLE_MAGNITUDE:
        raise ValueError(f"square {square_id}: angle magnitude exceeds {MAXIMUM_ANGLE_MAGNITUDE:g}")


def verify_no_overlaps(squares: Sequence[Square]) -> tuple[bool, str]:
    float_squares = prepare_float_squares(squares)
    undecided_pairs = []
    for first_id, second_id in candidate_pairs(float_squares):
        status = float_pair_status(float_squares[first_id], float_squares[second_id])
        if status == "overlapping":
            return False, f"squares {first_id} and {second_id} overlap"
        if status == "undecided":
            undecided_pairs.append((first_id, second_id))
    for first_id, second_id in undecided_pairs:
        separated = certify_pair_separation(squares[first_id], squares[second_id])
        if separated is False:
            return False, f"squares {first_id} and {second_id} overlap"
        if separated is None:
            return False, f"squares {first_id} and {second_id} are undecidable at maximum precision"
    return True, "feasible"
