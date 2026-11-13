from __future__ import annotations

import argparse
import time
from pathlib import Path

from .baseline import optimize
from .config import INIT_CHOICES, SearchConfig
from .serialization import write_run


def parse_arguments(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Memetic genetic algorithm baseline (vendored sqpack core) for Squares in Squares.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n", type=int, default=5, help="number of unit squares")
    parser.add_argument("--population-size", type=int, default=96, help="total individuals across all islands")
    parser.add_argument("--generations", type=int, default=600, help="maximum number of generations")
    parser.add_argument("--relax-steps", type=int, default=300, help="FIRE relaxation steps per individual")
    parser.add_argument("--compress-attempts", type=int, default=3, help="Lamarckian compress attempts")
    parser.add_argument("--islands", type=int, default=4, help="number of island sub-populations")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--output-dir", type=Path, default=Path("runs"), help="root result directory (runs/nNNN/)")
    parser.add_argument("--init", choices=INIT_CHOICES, default="random", help="initial population")
    parser.add_argument("--polish-rounds", type=int, default=30, help="final polishing rounds")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    arguments = parse_arguments(argv)
    config = SearchConfig(
        n=arguments.n,
        population_size=arguments.population_size,
        generations=arguments.generations,
        relax_steps=arguments.relax_steps,
        compress_attempts=arguments.compress_attempts,
        islands=arguments.islands,
        seed=arguments.seed,
        init=arguments.init,
        polish_rounds=arguments.polish_rounds,
    )
    start_time = time.perf_counter()
    result = optimize(config)
    runtime_seconds = time.perf_counter() - start_time
    layout_path, metrics_path, config_path = write_run(
        arguments.output_dir,
        result,
        config,
        runtime_seconds=runtime_seconds,
    )
    print(f"n={result.n}")
    print(f"valid={result.valid}")
    print(f"side_length={result.side_length:.12f}")
    print(f"score={result.score:.12f}")
    print(f"improved_from_grid={result.improved_from_grid}")
    print(f"upstream_side={result.upstream_side:.12f}")
    print(f"generations_run={result.generations_run}")
    print(f"evaluations={result.evaluations}")
    print(f"certified_evaluations={result.certified_evaluations}")
    print(f"snapshots={len(result.snapshots)}")
    print(f"runtime_seconds={runtime_seconds:.6f}")
    print(f"directory={layout_path.parent}")
    print(f"layout={layout_path}")
    print(f"metrics={metrics_path}")
    print(f"config={config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
