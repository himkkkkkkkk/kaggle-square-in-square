from __future__ import annotations

from dataclasses import dataclass

from sqpack import GAConfig

INIT_CHOICES = ("random", "lattice")


@dataclass(frozen=True)
class SearchConfig:
    """Parameters of one certified search run on a single n, mapped onto sqpack's GAConfig.

    The search itself is the vendored memetic GA (`sqpack`): FIRE relaxation, exact
    centre-scaling repair, Lamarckian compression, geometric cut crossover, five
    structural mutations, D4 raster clearing and the island model. This dataclass only
    carries the knobs the CLI exposes; none of its values are scores or proofs.
    """

    n: int
    population_size: int = 96
    generations: int = 600
    relax_steps: int = 300
    compress_attempts: int = 3
    islands: int = 4
    migrate_every: int = 25
    restart_after: int = 60
    clearing: float = 0.06
    init: str = "random"
    polish_rounds: int = 30
    seed: int = 0

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("n must be at least 1")
        if self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if self.generations < 0:
            raise ValueError("generations must be non-negative")
        if self.relax_steps < 0:
            raise ValueError("relax_steps must be non-negative")
        if self.compress_attempts < 1:
            raise ValueError("compress_attempts must be at least 1")
        if self.islands < 1:
            raise ValueError("islands must be at least 1")
        if self.migrate_every < 0:
            raise ValueError("migrate_every must be non-negative")
        if self.restart_after < 0:
            raise ValueError("restart_after must be non-negative")
        if not 0.0 <= self.clearing <= 1.0:
            raise ValueError("clearing must be in [0, 1]")
        if self.init not in INIT_CHOICES:
            raise ValueError(f"init must be one of {INIT_CHOICES}")
        if self.polish_rounds < 0:
            raise ValueError("polish_rounds must be non-negative")

    def to_ga_config(self) -> GAConfig:
        """Map onto the reference configuration; every algorithm default stays theirs."""
        return GAConfig(
            n=self.n,
            pop_size=self.population_size,
            generations=self.generations,
            relax_steps=self.relax_steps,
            compress_attempts=self.compress_attempts,
            islands=self.islands,
            migrate_every=self.migrate_every,
            restart_after=self.restart_after,
            clearing=self.clearing,
            init=self.init,
            polish_rounds=self.polish_rounds,
            seed=self.seed,
        )
