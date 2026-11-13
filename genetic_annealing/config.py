from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchConfig:
    """Deterministic configuration for one Kick-Separate-Shrink run on a single n.

    `penalty_weight` is lambda in the search-only fitness F = L + lambda * P. It is never
    a score and never a legality proof. Every random decision in the search consumes a
    draw from the injected np.random.Generator seeded with `seed`.

    Kick parameters drive large-neighbourhood moves. Repair parameters define the fixed
    target box and SAT separation sweeps. `annealing_steps` is the single local annealing
    budget applied to repaired candidates before certification.
    """

    n: int
    population_size: int = 24
    generations: int = 100
    annealing_steps: int = 20
    seed: int = 42
    tournament_size: int = 3
    elite_count: int = 2
    crossover_probability: float = 0.9
    center_mutation_probability: float = 0.6
    center_mutation_sigma: float = 0.05
    angle_mutation_probability: float = 0.6
    angle_mutation_sigma: float = 0.05
    compression_probability: float = 0.2
    compression_sigma: float = 0.03
    initial_center_jitter: float = 0.05
    initial_angle_jitter: float = 0.05
    initial_large_angle_probability: float = 0.25
    initial_large_angle_sigma: float = 0.6
    initial_scale_sigma: float = 0.02
    penalty_weight: float = 10.0
    initial_temperature: float = 0.02
    cooling_rate: float = 0.9
    minimum_temperature: float = 1e-6
    annealing_center_sigma: float = 0.01
    annealing_angle_sigma: float = 0.01
    annealing_compression_sigma: float = 0.01

    kick_min_squares: int = 1
    kick_max_squares: int = 3
    kick_rotation_probability: float = 0.75
    kick_relocation_sigma: float = 0.35
    kick_swap_probability: float = 0.3
    kick_cluster_probability: float = 0.3
    kick_cluster_sigma: float = 0.2

    repair_rho: float = 0.02
    repair_margin: float = 1e-6
    repair_sweeps: int = 30
    repair_stagnation_limit: int = 5

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("n must be at least 1")
        if self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if not 1 <= self.elite_count < self.population_size:
            raise ValueError("elite_count must be in 1..population_size-1")
        if not 1 <= self.tournament_size <= self.population_size:
            raise ValueError("tournament_size must be in 1..population_size")
        if self.generations < 0 or self.annealing_steps < 0:
            raise ValueError("generations and annealing_steps must be non-negative")
        if self.penalty_weight <= 0.0:
            raise ValueError("penalty_weight must be positive")
        if self.initial_temperature <= 0.0 or self.minimum_temperature <= 0.0:
            raise ValueError("temperatures must be positive")
        if not 0.0 < self.cooling_rate < 1.0:
            raise ValueError("cooling_rate must be in (0, 1)")
        if not 1 <= self.kick_min_squares <= self.kick_max_squares:
            raise ValueError("kick_min_squares must be between 1 and kick_max_squares")
        if not 0.0 <= self.kick_rotation_probability <= 1.0:
            raise ValueError("kick_rotation_probability must be in [0, 1]")
        if self.kick_relocation_sigma < 0.0 or self.kick_cluster_sigma < 0.0:
            raise ValueError("kick sigmas must be non-negative")
        if not 0.0 <= self.kick_swap_probability <= 1.0:
            raise ValueError("kick_swap_probability must be in [0, 1]")
        if not 0.0 <= self.kick_cluster_probability <= 1.0:
            raise ValueError("kick_cluster_probability must be in [0, 1]")
        if not 0.0 <= self.repair_rho < 1.0:
            raise ValueError("repair_rho must be in [0, 1)")
        if self.repair_margin < 0.0:
            raise ValueError("repair_margin must be non-negative")
        if self.repair_sweeps < 1:
            raise ValueError("repair_sweeps must be at least 1")
        if self.repair_stagnation_limit < 1:
            raise ValueError("repair_stagnation_limit must be at least 1")
