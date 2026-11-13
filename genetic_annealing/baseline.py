from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from squares_metric import evaluate_squares

from .annealing import anneal
from .certification import CertifiedIncumbent, certify_candidate
from .config import SearchConfig
from .fitness import evaluate_search
from .genetic import kick, next_generation
from .genome import Layout, to_squares
from .initialization import grid_layout, initial_population, structural_seeds
from .repair import separate_overlaps, target_box_side


@dataclass(frozen=True)
class OptimizationResult:
    n: int
    layout: Layout
    side_length: float
    score: float
    valid: bool
    improved_from_grid: bool
    certified_evaluations: int
    fast_rejections: int
    seed: int
    structural_seed_score: float | None = None
    structural_seed_improved: bool = False
    search_improved: bool = False


def optimize(config: SearchConfig) -> OptimizationResult:
    """Kick-Separate-Shrink search that never returns an uncertified layout."""
    rng = np.random.default_rng(config.seed)
    grid = grid_layout(config.n)
    grid_result = evaluate_squares(config.n, to_squares(grid))
    if not grid_result.valid:
        raise RuntimeError(f"grid layout for n={config.n} failed certification: {grid_result.reason}")

    grid_score = float(grid_result.score)
    incumbent = CertifiedIncumbent(config.n, grid, grid_result, 1)

    structural_seed_score: float | None = None
    for seed_layout in structural_seeds(config.n):
        previous_score = incumbent.score
        incumbent = certify_candidate(seed_layout, incumbent)
        if incumbent.score < previous_score:
            structural_seed_score = (
                incumbent.score
                if structural_seed_score is None
                else min(structural_seed_score, incumbent.score)
            )

    population = initial_population(config.n, rng, config)
    evaluations = tuple(evaluate_search(layout, config) for layout in population)

    for _ in range(config.generations):
        population = next_generation(population, evaluations, rng, config)
        evaluations = tuple(evaluate_search(layout, config) for layout in population)
        best_index = int(np.argmin(np.array([evaluation.fitness for evaluation in evaluations])))
        elite = population[best_index]

        target_side = target_box_side(config.n, incumbent.side_length, config)

        repaired_elite = separate_overlaps(elite, target_side, config).layout
        kicked = kick(elite, rng, config)
        repaired_kick = separate_overlaps(kicked, target_side, config).layout

        polished_elite, _ = anneal(
            repaired_elite,
            evaluate_search(repaired_elite, config),
            rng,
            config,
            steps=config.annealing_steps,
        )
        polished_kick, _ = anneal(
            repaired_kick,
            evaluate_search(repaired_kick, config),
            rng,
            config,
            steps=config.annealing_steps,
        )

        incumbent = certify_candidate(polished_elite, incumbent)
        incumbent = certify_candidate(polished_kick, incumbent)

    final_result = evaluate_squares(config.n, to_squares(incumbent.layout))
    certified_evaluations = incumbent.certified_evaluations + 1
    if final_result.valid:
        champion_layout = incumbent.layout
    else:
        champion_layout = grid
        final_result = evaluate_squares(config.n, to_squares(grid))
        certified_evaluations += 1
        if not final_result.valid:
            raise RuntimeError(f"grid fallback for n={config.n} failed certification")

    side_length = final_result.side_length
    if side_length is None:
        raise RuntimeError("certified result is missing a side length")

    score = float(final_result.score)
    baseline_score = grid_score if structural_seed_score is None else structural_seed_score
    return OptimizationResult(
        n=config.n,
        layout=champion_layout,
        side_length=float(side_length),
        score=score,
        valid=final_result.valid,
        improved_from_grid=score < grid_score,
        certified_evaluations=certified_evaluations,
        fast_rejections=incumbent.fast_rejections,
        seed=config.seed,
        structural_seed_score=structural_seed_score,
        structural_seed_improved=(
            structural_seed_score is not None and structural_seed_score < grid_score
        ),
        search_improved=score < baseline_score,
    )
