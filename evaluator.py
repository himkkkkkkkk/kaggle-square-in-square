"""Public layout-validation and target-relative scoring API for search agents."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

from squares_metric import Square, evaluate_squares
from squares_metric.scoring import invalid_puzzle_result

ROOT = Path(__file__).resolve().parent


def evaluate_layout(n: int, layout: Sequence[Sequence[object]]):
    """Validate one layout of ``[x, y, angle]`` triples; never raises for bad layouts."""
    try:
        if len(layout) != n:
            return invalid_puzzle_result(n, f"expected {n} squares, received {len(layout)}")
        squares = tuple(Square(*(str(value) for value in square)) for square in layout)
    except (TypeError, ValueError) as error:
        return invalid_puzzle_result(n, str(error))
    return evaluate_squares(n, squares)


def score_layouts(
    layouts: Mapping[str, Sequence[Sequence[object]]],
    targets: Mapping[str, Mapping[str, object]],
    weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Return normalized weighted side-length gaps; lower scores are better.

    Invalid or missing layouts use the grid side length. Improvements over the target
    produce negative gaps. The weights are normalized, so the initial all-ones file
    is an unweighted mean rather than a sum whose scale depends on puzzle count.
    """
    extra = layouts.keys() - targets.keys()
    if extra:
        raise ValueError(f"results contain n values absent from aim.json: {sorted(extra, key=int)}")
    weights = {n: 1.0 for n in targets} if weights is None else weights
    try:
        normalized_weights = {n: float(weights.get(n, 0.0)) for n in targets}
        total_weight = sum(normalized_weights.values())
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid weights: {error}") from error
    if not math.isfinite(total_weight) or total_weight <= 0:
        raise ValueError("weights must have a finite, positive sum")

    results = []
    total_score = 0.0
    for key in sorted(targets, key=int):
        n = int(key)
        target_side = float(targets[key]["s"])
        if not math.isfinite(target_side) or target_side <= 0:
            raise ValueError(f"invalid target side length for n={n}")
        weight = normalized_weights[key]
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"invalid weight for n={n}")
        if key not in layouts:
            result = invalid_puzzle_result(n, "missing")
        else:
            result = evaluate_layout(n, layouts[key])
        side = float(result.side_length) if result.valid else math.ceil(math.sqrt(n))
        gap = (side - target_side) / target_side
        total_score += weight * gap
        results.append(
            {
                "n": n,
                "valid": result.valid,
                "side_length": side,
                "target_side_length": target_side,
                "gap": gap,
                "weight": weight,
                "reason": result.reason,
            }
        )
    return {
        "total_score": total_score / total_weight,
        "valid_puzzles": sum(item["valid"] for item in results),
        "puzzle_count": len(results),
        "results": results,
    }


def score_file(
    result_path: str | Path = ROOT / "search/result.json",
    aim_path: str | Path = ROOT / "aim.json",
    weights_path: str | Path = ROOT / "weights.json",
) -> dict[str, object]:
    layouts = json.loads(Path(result_path).read_text())
    targets = json.loads(Path(aim_path).read_text())
    weights = json.loads(Path(weights_path).read_text())
    return score_layouts(layouts, targets, weights)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?", type=Path, default=ROOT / "search/result.json")
    parser.add_argument("--aim", type=Path, default=ROOT / "aim.json")
    parser.add_argument("--weights", type=Path, default=ROOT / "weights.json")
    parser.add_argument("--output", type=Path, help="also write the full JSON report here")
    arguments = parser.parse_args()
    report = score_file(arguments.results, arguments.aim, arguments.weights)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(text)
    print(
        f"total_score={report['total_score']:.12f} "
        f"valid={report['valid_puzzles']}/{report['puzzle_count']} (lower is better)"
    )


if __name__ == "__main__":
    main()
