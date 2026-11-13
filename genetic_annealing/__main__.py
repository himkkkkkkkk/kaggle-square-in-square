from __future__ import annotations

import argparse
import time
from pathlib import Path

from .baseline import optimize
from .config import SearchConfig
from .serialization import write_run


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kick-Separate-Shrink genetic plus simulated annealing baseline for Squares in Squares.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n", type=int, default=5, help="number of unit squares")
    parser.add_argument("--population-size", type=int, default=24, help="genetic population size")
    parser.add_argument("--generations", type=int, default=100, help="number of generations")
    parser.add_argument("--annealing-steps", type=int, default=20, help="annealing steps per generation")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--output-dir", type=Path, default=Path("runs"), help="result directory")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    config = SearchConfig(
        n=arguments.n,
        population_size=arguments.population_size,
        generations=arguments.generations,
        annealing_steps=arguments.annealing_steps,
        seed=arguments.seed,
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
    print(f"structural_seed_improved={result.structural_seed_improved}")
    print(f"search_improved={result.search_improved}")
    print(f"certified_evaluations={result.certified_evaluations}")
    print(f"fast_rejections={result.fast_rejections}")
    print(f"runtime_seconds={runtime_seconds:.6f}")
    print(f"layout={layout_path}")
    print(f"metrics={metrics_path}")
    print(f"config={config_path}")


if __name__ == "__main__":
    main()
