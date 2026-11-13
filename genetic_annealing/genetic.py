from __future__ import annotations

import math

import numpy as np

from .config import SearchConfig
from .fitness import SearchEvaluation
from .genome import (
    Layout,
    angle_difference,
    compress_centers,
    make_layout,
    recenter,
    wrap_angles,
)


def tournament(
    population: tuple[Layout, ...],
    evaluations: tuple[SearchEvaluation, ...],
    rng: np.random.Generator,
    config: SearchConfig,
) -> Layout:
    indices = rng.integers(0, len(population), size=config.tournament_size)
    best = min((int(index) for index in indices), key=lambda index: evaluations[index].fitness)
    return population[best]


def uniform_crossover(first: Layout, second: Layout, rng: np.random.Generator) -> Layout:
    centers = np.where(rng.random((first.n, 1)) < 0.5, first.centers, second.centers)
    angles = np.where(rng.random(first.n) < 0.5, first.angles, second.angles)
    return recenter(make_layout(centers, angles))


def arithmetic_crossover(first: Layout, second: Layout, rng: np.random.Generator) -> Layout:
    center_blend = rng.random((first.n, 1))
    centers = center_blend * first.centers + (1.0 - center_blend) * second.centers
    angle_blend = rng.random(first.n)
    angles = wrap_angles(first.angles + angle_blend * angle_difference(first.angles, second.angles))
    return recenter(make_layout(centers, angles))


def crossover(
    first: Layout,
    second: Layout,
    rng: np.random.Generator,
    config: SearchConfig,
) -> Layout:
    if rng.random() < config.crossover_probability:
        if rng.random() < 0.5:
            return arithmetic_crossover(first, second, rng)
        return uniform_crossover(first, second, rng)
    return make_layout(first.centers, first.angles)


def mutate(layout: Layout, rng: np.random.Generator, config: SearchConfig) -> Layout:
    centers = layout.centers
    if rng.random() < config.center_mutation_probability:
        centers = centers + rng.normal(0.0, config.center_mutation_sigma, size=centers.shape)
    angles = layout.angles
    if rng.random() < config.angle_mutation_probability:
        angles = wrap_angles(angles + rng.normal(0.0, config.angle_mutation_sigma, size=angles.shape))
    if rng.random() < config.compression_probability:
        centers = compress_centers(centers, rng, config.compression_sigma)
    return recenter(make_layout(centers, angles))


def kick(layout: Layout, rng: np.random.Generator, config: SearchConfig) -> Layout:
    """Large-neighbourhood move: rotate, relocate, swap or translate a small cluster.

    At least one and at most min(kick_max_squares, n) squares are selected. Rotations
    include +/- pi/4 and arbitrary angles; relocation and cluster shifts are large
    compared with the small Gaussian mutations. The parent Layout is never modified.
    """
    n = layout.n
    lower = min(config.kick_min_squares, n)
    upper = min(config.kick_max_squares, n)
    count = int(rng.integers(lower, upper + 1))
    selected = rng.choice(n, size=count, replace=False)

    centers = layout.centers.copy()
    angles = layout.angles.copy()

    if rng.random() < config.kick_rotation_probability:
        for index in selected:
            if rng.random() < 0.5:
                angles[index] = angles[index] + float(rng.choice((-1.0, 1.0))) * math.pi / 4.0
            else:
                angles[index] = float(rng.uniform(-math.pi, math.pi))
        angles = wrap_angles(angles)

    centers[selected] += rng.normal(
        0.0,
        config.kick_relocation_sigma,
        size=(count, 2),
    )

    if count >= 2 and rng.random() < config.kick_swap_probability:
        first, second = int(selected[0]), int(selected[1])
        centers[[first, second]] = centers[[second, first]]

    if count >= 2 and rng.random() < config.kick_cluster_probability:
        cluster = selected[: min(count, 3)]
        centers[cluster] += rng.normal(0.0, config.kick_cluster_sigma, size=2)

    return recenter(make_layout(centers, angles))


def next_generation(
    population: tuple[Layout, ...],
    evaluations: tuple[SearchEvaluation, ...],
    rng: np.random.Generator,
    config: SearchConfig,
) -> tuple[Layout, ...]:
    """Elites survive unchanged; the rest is tournament + crossover + mutation."""
    order = np.argsort(np.array([evaluation.fitness for evaluation in evaluations]), kind="stable")
    elites = tuple(population[int(index)] for index in order[: config.elite_count])
    children: list[Layout] = []
    while len(elites) + len(children) < config.population_size:
        first = tournament(population, evaluations, rng, config)
        second = tournament(population, evaluations, rng, config)
        children.append(mutate(crossover(first, second, rng, config), rng, config))
    return elites + tuple(children)
