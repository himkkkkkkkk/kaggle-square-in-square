from __future__ import annotations

import math

import numpy as np

from .config import SearchConfig
from .fitness import SearchEvaluation, evaluate_search
from .genome import Layout, compress_centers, make_layout, recenter, wrap_angles


def propose(layout: Layout, rng: np.random.Generator, config: SearchConfig) -> Layout:
    centers = layout.centers + rng.normal(0.0, config.annealing_center_sigma, size=layout.centers.shape)
    angles = wrap_angles(layout.angles + rng.normal(0.0, config.annealing_angle_sigma, size=layout.angles.shape))
    if rng.random() < config.compression_probability:
        centers = compress_centers(centers, rng, config.annealing_compression_sigma)
    return recenter(make_layout(centers, angles))


def anneal(
    layout: Layout,
    evaluation: SearchEvaluation,
    rng: np.random.Generator,
    config: SearchConfig,
    steps: int | None = None,
) -> tuple[Layout, SearchEvaluation]:
    """Short local search; accepting a worse search candidate is never a legality decision.

    `steps` overrides `config.annealing_steps` for the short post-repair polish while
    keeping the original four-argument call signature valid.
    """
    total_steps = config.annealing_steps if steps is None else steps
    current = layout
    current_evaluation = evaluation
    temperature = config.initial_temperature
    for _ in range(total_steps):
        candidate = propose(current, rng, config)
        candidate_evaluation = evaluate_search(candidate, config)
        delta = candidate_evaluation.fitness - current_evaluation.fitness
        if delta <= 0.0 or rng.random() < math.exp(-delta / temperature):
            current = candidate
            current_evaluation = candidate_evaluation
        temperature = max(config.minimum_temperature, temperature * config.cooling_rate)
    return current, current_evaluation
