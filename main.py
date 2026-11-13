"""Batch runner: compute and save the certified baseline for every n in a range.

`uv run python main.py` walks n=1..1000 in order and writes `runs/nNNN/no-n-final.csv`,
the per-10-generation snapshots `runs/nNNN/no-n-<i>.csv`, plus `history.jsonl`,
`metrics.json` and `config.json` in the same directory. A full sweep is long; use
`--start`/`--end` for a smoke range.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from genetic_annealing import SearchConfig, optimize, write_run

MIN_N = 1
MAX_N = 1000


def parse_arguments(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the certified memetic GA baseline for every n in [start, end].",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start", type=int, default=MIN_N, help="first n")
    parser.add_argument("--end", type=int, default=MAX_N, help="last n, inclusive")
    parser.add_argument("--output-dir", type=Path, default=Path("runs"), help="root result directory")
    parser.add_argument("--population-size", type=int, default=None, help="override SearchConfig.population_size")
    parser.add_argument("--generations", type=int, default=None, help="override SearchConfig.generations")
    parser.add_argument("--relax-steps", type=int, default=None, help="override SearchConfig.relax_steps")
    parser.add_argument("--seed", type=int, default=None, help="override SearchConfig.seed")
    arguments = parser.parse_args(argv)
    if not MIN_N <= arguments.start <= arguments.end <= MAX_N:
        parser.error(f"need {MIN_N} <= start <= end <= {MAX_N}")
    return arguments


def selected_sizes(arguments: argparse.Namespace) -> range:
    return range(arguments.start, arguments.end + 1)


def search_config(n: int, arguments: argparse.Namespace) -> SearchConfig:
    """Only the flags that were given override SearchConfig; everything else stays default."""
    overrides = {
        "population_size": arguments.population_size,
        "generations": arguments.generations,
        "relax_steps": arguments.relax_steps,
        "seed": arguments.seed,
    }
    return SearchConfig(n=n, **{key: value for key, value in overrides.items() if value is not None})


def run_puzzle(n: int, arguments: argparse.Namespace):
    config = search_config(n, arguments)
    start_time = time.perf_counter()
    result = optimize(config)
    runtime_seconds = time.perf_counter() - start_time
    paths = write_run(arguments.output_dir, result, config, runtime_seconds=runtime_seconds)
    return result, paths, runtime_seconds


def main(argv=None) -> int:
    arguments = parse_arguments(argv)
    sizes = selected_sizes(arguments)
    total = len(sizes)
    for position, n in enumerate(sizes, start=1):
        result, (layout_path, _, _), runtime_seconds = run_puzzle(n, arguments)
        print(
            f"[{position}/{total}] n={n} valid={result.valid} "
            f"side={result.side_length:.12f} score={result.score:.12f} "
            f"improved={result.improved_from_grid} {runtime_seconds:.2f}s -> {layout_path}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
