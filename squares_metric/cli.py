from __future__ import annotations

import argparse
import csv
from pathlib import Path

import mpmath

from .scoring import score_submission_file

SIDE_LENGTH_DECIMAL_PLACES = 50


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and score a Squares in Squares submission.")
    parser.add_argument("submission", type=Path)
    parser.add_argument("--details", type=Path, default=Path("submission_details.csv"))
    arguments = parser.parse_args()
    report = score_submission_file(arguments.submission)
    write_details(arguments.details, report.puzzles)
    print(f"total_score={report.total_score:.12f}")
    print(f"valid_puzzles={sum(result.valid for result in report.puzzles)}/{len(report.puzzles)}")
    print(f"details={arguments.details}")


def write_details(path: Path, puzzles) -> None:
    with path.open("w", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(("n", "valid", "L", "score", "reason"))
        for result in puzzles:
            side_length = (
                mpmath.nstr(result.side_length, SIDE_LENGTH_DECIMAL_PLACES + 2)
                if result.side_length is not None
                else ""
            )
            writer.writerow((result.n, result.valid, side_length, result.score, result.reason))


if __name__ == "__main__":
    main()
