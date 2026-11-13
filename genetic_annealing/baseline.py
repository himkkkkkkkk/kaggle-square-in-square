from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sqpack
from squares_metric import PuzzleResult

from .certification import certify_improvement, certify_layout
from .config import SearchConfig
from .genome import Layout, grid_layout, layout_from_configuration

SNAPSHOT_INTERVAL = 10


@dataclass(frozen=True)
class Snapshot:
    """One in-memory process snapshot of the search, certified by the project evaluator.

    `index` counts from 1 and names the file (`no-5-1.csv` is the generation-10 snapshot),
    `generation` is the real sqpack generation the population was sampled at. An invalid
    snapshot is kept and reported as invalid - it is never dropped or passed off as legal.
    """

    index: int
    generation: int
    layout: Layout
    result: PuzzleResult
    certified_evaluations: int

    @property
    def valid(self) -> bool:
        return bool(self.result.valid)

    @property
    def reason(self) -> str:
        return str(self.result.reason)

    @property
    def score(self) -> float:
        return float(self.result.score)

    @property
    def side_length(self) -> float | None:
        return None if self.result.side_length is None else float(self.result.side_length)


@dataclass(frozen=True)
class OptimizationResult:
    """Certified champion plus the honest provenance of the run that produced it.

    `upstream_side` is sqpack's own float side length for the same packing; it is reported
    for comparison only and is never used as a legality proof or as the score.
    `snapshots` are the certified intermediate bests collected every `SNAPSHOT_INTERVAL`
    generations; they are learning material, never champions.
    """

    n: int
    layout: Layout
    side_length: float
    score: float
    valid: bool
    improved_from_grid: bool
    certified_evaluations: int
    seed: int
    upstream_side: float
    generations_run: int
    evaluations: int
    snapshots: tuple[Snapshot, ...] = ()


def optimize(config: SearchConfig, snapshot_interval: int = SNAPSHOT_INTERVAL) -> OptimizationResult:
    """Run the vendored memetic GA and certify its champion; never returns an invalid layout.

    `snapshot_interval <= 0` disables snapshots. Snapshot genomes are copied out of the live
    population inside the callback and certified there, so the search core still does no IO
    and the populations it hands over are never aliased.
    """
    grid = grid_layout(config.n)
    incumbent = certify_layout(grid)
    if not incumbent.valid:
        raise RuntimeError(f"grid layout for n={config.n} failed certification: {incumbent.result.reason}")
    grid_score = incumbent.score

    certified_evaluations = incumbent.certified_evaluations
    snapshots: list[Snapshot] = []

    def collect_snapshot(generation: int, population: np.ndarray, fitness: np.ndarray) -> None:
        nonlocal certified_evaluations
        if snapshot_interval <= 0 or generation % snapshot_interval != 0:
            return
        best = int(np.argmin(fitness))
        certified = certify_layout(layout_from_configuration(population[best]), certified_evaluations)
        certified_evaluations = certified.certified_evaluations
        snapshots.append(
            Snapshot(
                len(snapshots) + 1,
                int(generation),
                certified.layout,
                certified.result,
                certified.certified_evaluations,
            )
        )

    upstream = sqpack.run(config.to_ga_config(), verbose=False, callback=collect_snapshot)
    candidate = certify_layout(layout_from_configuration(upstream.best_cfg), certified_evaluations)
    incumbent = certify_improvement(candidate, incumbent)

    final = certify_layout(incumbent.layout, incumbent.certified_evaluations)
    if not final.valid:
        final = certify_layout(grid, final.certified_evaluations)
        if not final.valid:
            raise RuntimeError(f"grid fallback for n={config.n} failed certification: {final.result.reason}")

    return OptimizationResult(
        n=config.n,
        layout=final.layout,
        side_length=final.side_length,
        score=final.score,
        valid=final.valid,
        improved_from_grid=final.score < grid_score,
        certified_evaluations=final.certified_evaluations,
        seed=config.seed,
        upstream_side=float(upstream.side),
        generations_run=int(upstream.history.final["generations_run"]),
        evaluations=int(upstream.history.final["evaluations"]),
        snapshots=tuple(snapshots),
    )
