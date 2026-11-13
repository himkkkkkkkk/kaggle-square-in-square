from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict
from pathlib import Path

from squares_metric import grid_fallback_score

from .baseline import OptimizationResult
from .config import SearchConfig
from .genome import COORDINATE_FORMAT, Layout

LAYOUT_COLUMNS = ("n", "square_id", "x", "y", "angle")


def layout_rows(layout: Layout) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            str(layout.n),
            str(square_id),
            format(float(layout.centers[square_id, 0]), COORDINATE_FORMAT),
            format(float(layout.centers[square_id, 1]), COORDINATE_FORMAT),
            format(float(layout.angles[square_id]), COORDINATE_FORMAT),
        )
        for square_id in range(layout.n)
    )


def write_layout_csv(path: Path, layout: Layout) -> None:
    with path.open("w", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(LAYOUT_COLUMNS)
        writer.writerows(layout_rows(layout))


def metrics_payload(
    result: OptimizationResult,
    config: SearchConfig,
    runtime_seconds: float | None = None,
) -> dict[str, object]:
    """Certified metrics only; grid_side_length is the exact k x k grid span, k = ceil(sqrt n).

    `runtime_seconds` is written only when the caller measured it, so the payload never
    contains a fabricated timing value. `structural_seed_improved` and `search_improved`
    separate the analytic n=5 seed benefit from any improvement found by the search.
    """
    payload: dict[str, object] = {
        "n": result.n,
        "valid": result.valid,
        "side_length": result.side_length,
        "score": result.score,
        "grid_side_length": float(math.ceil(math.sqrt(result.n))),
        "grid_score": float(grid_fallback_score(result.n)),
        "improved_from_grid": result.improved_from_grid,
        "structural_seed_score": result.structural_seed_score,
        "structural_seed_improved": result.structural_seed_improved,
        "search_improved": result.search_improved,
        "seed": result.seed,
        "certified_evaluations": result.certified_evaluations,
        "fast_rejections": result.fast_rejections,
        "parameters": asdict(config),
    }
    if runtime_seconds is not None:
        payload["runtime_seconds"] = float(runtime_seconds)
    return payload


def write_run(
    output_dir: Path,
    result: OptimizationResult,
    config: SearchConfig,
    runtime_seconds: float | None = None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    layout_path = output_dir / "layout.csv"
    metrics_path = output_dir / "metrics.json"
    config_path = output_dir / "config.json"
    write_layout_csv(layout_path, result.layout)
    metrics_path.write_text(
        json.dumps(metrics_payload(result, config, runtime_seconds), indent=2, sort_keys=True) + "\n"
    )
    config_path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n")
    return layout_path, metrics_path, config_path
