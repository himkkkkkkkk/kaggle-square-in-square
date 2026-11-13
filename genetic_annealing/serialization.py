from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict
from pathlib import Path

from squares_metric import grid_fallback_score

from .baseline import OptimizationResult, Snapshot
from .config import SearchConfig
from .genome import COORDINATE_FORMAT, Layout

LAYOUT_COLUMNS = ("n", "square_id", "x", "y", "angle")
HISTORY_FILENAME = "history.jsonl"
DIRECTORY_DIGITS = 3


def run_directory(output_dir: Path, n: int) -> Path:
    """One directory per n: `runs/n005` for n=5."""
    return Path(output_dir) / f"n{n:0{DIRECTORY_DIGITS}d}"


def final_layout_filename(n: int) -> str:
    return f"no-{n}-final.csv"


def snapshot_filename(n: int, index: int) -> str:
    """Snapshot index counts from 1: generation 10 -> no-5-1.csv, generation 20 -> no-5-2.csv."""
    return f"no-{n}-{index}.csv"


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


def snapshot_payload(n: int, snapshot: Snapshot) -> dict[str, object]:
    """One history line: enough to pick snapshots for imitation learning without re-scoring."""
    return {
        "index": int(snapshot.index),
        "generation": int(snapshot.generation),
        "filename": snapshot_filename(n, snapshot.index),
        "valid": snapshot.valid,
        "side_length": snapshot.side_length,
        "score": float(snapshot.score),
        "reason": snapshot.reason,
    }


def write_history(path: Path, result: OptimizationResult) -> None:
    """Every collected snapshot gets a line, invalid ones included and marked as such."""
    lines = [json.dumps(snapshot_payload(result.n, snapshot), sort_keys=True) for snapshot in result.snapshots]
    path.write_text("".join(line + "\n" for line in lines))


def metrics_payload(
    result: OptimizationResult,
    config: SearchConfig,
    runtime_seconds: float | None = None,
) -> dict[str, object]:
    """Certified metrics only; grid_side_length is the exact k x k grid span, k = ceil(sqrt n).

    `runtime_seconds` is written only when the caller measured it, so the payload never
    contains a fabricated timing value. `upstream_side` is the reference algorithm's own
    float side length and `parameters` is the complete effective configuration.
    """
    payload: dict[str, object] = {
        "n": result.n,
        "valid": result.valid,
        "side_length": float(result.side_length),
        "score": float(result.score),
        "grid_side_length": float(math.ceil(math.sqrt(result.n))),
        "grid_score": float(grid_fallback_score(result.n)),
        "improved_from_grid": result.improved_from_grid,
        "upstream_side": float(result.upstream_side),
        "generations_run": int(result.generations_run),
        "evaluations": int(result.evaluations),
        "certified_evaluations": int(result.certified_evaluations),
        "snapshots": len(result.snapshots),
        "seed": result.seed,
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
    """Write one puzzle into `output_dir/nNNN/`: final layout, every snapshot, history, metrics, config."""
    directory = run_directory(output_dir, result.n)
    directory.mkdir(parents=True, exist_ok=True)
    for stale_layout in directory.glob(f"no-{result.n}-*.csv"):
        stale_layout.unlink()

    layout_path = directory / final_layout_filename(result.n)
    write_layout_csv(layout_path, result.layout)
    for snapshot in result.snapshots:
        write_layout_csv(directory / snapshot_filename(result.n, snapshot.index), snapshot.layout)
    write_history(directory / HISTORY_FILENAME, result)

    metrics_path = directory / "metrics.json"
    config_path = directory / "config.json"
    metrics_path.write_text(
        json.dumps(metrics_payload(result, config, runtime_seconds), indent=2, sort_keys=True) + "\n"
    )
    config_path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n")
    return layout_path, metrics_path, config_path
