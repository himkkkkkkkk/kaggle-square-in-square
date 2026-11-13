"""Tests for the genetic_annealing adapter around the vendored sqpack memetic GA."""

import contextlib
import csv
import importlib
import io
import json
import math
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path
from unittest import mock

import numpy as np

import genetic_annealing
import main as batch_main
from genetic_annealing import (
    CertifiedLayout,
    Layout,
    OptimizationResult,
    SearchConfig,
    Snapshot,
    certify_improvement,
    certify_layout,
    grid_layout,
    layout_from_configuration,
    make_layout,
    optimize,
    to_squares,
)
from genetic_annealing import certification
from genetic_annealing.__main__ import main as cli_main
from genetic_annealing.__main__ import parse_arguments
from genetic_annealing.serialization import metrics_payload, write_run
from squares_metric import evaluate_squares, grid_fallback_score, score_submission_text
from squares_metric.validation import DECIMAL_LITERAL
from sqpack.diversity import d4_perms, raster, raster_dist
from sqpack.geometry import make_feasible, pair_depth, repair_scale, side
from sqpack.operators import apply_d4, crossover_cut, mutate, seed_rng
from sqpack.validate import validate

SEARCH_BUDGET = SearchConfig(n=5, population_size=32, generations=80, seed=1)


def tiny_config(n: int, seed: int = 7) -> SearchConfig:
    return SearchConfig(n=n, population_size=4, generations=2, relax_steps=10, compress_attempts=1, islands=2, seed=seed)


def snapshot_config(n: int = 5, seed: int = 17) -> SearchConfig:
    """Cheap but long enough to cross two snapshot boundaries (generations 10 and 20)."""
    return SearchConfig(n=n, population_size=4, generations=20, relax_steps=10, compress_attempts=1, islands=2, seed=seed)


@lru_cache(maxsize=None)
def cached_optimize(config: SearchConfig) -> OptimizationResult:
    """One real search per distinct config, shared across tests to keep the suite quick."""
    return optimize(config)


def random_configuration(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), rng.uniform(-0.7, 0.7, n)])


def lattice_configuration(n: int, spacing: float = 1.2) -> np.ndarray:
    """Axis-aligned k x k lattice centred on the origin, so every D4 image is itself."""
    width = math.ceil(math.sqrt(n))
    identifiers = np.arange(n)
    offset = 0.5 * (width - 1) * spacing
    return np.column_stack(
        [
            (identifiers % width) * spacing - offset,
            (identifiers // width) * spacing - offset,
            np.zeros(n),
        ]
    )


class ReferenceCoreTests(unittest.TestCase):
    """The vendored geometry/operator core keeps the upstream semantics."""

    def test_pair_depth_axis_aligned_and_touching(self):
        self.assertAlmostEqual(pair_depth(0.0, 0.0, 0.0, 0.9, 0.0, 0.0), 0.1, places=12)
        self.assertAlmostEqual(pair_depth(0.0, 0.0, 0.0, 1.0, 0.0, 0.0), 0.0, places=12)
        self.assertEqual(pair_depth(0.0, 0.0, 0.0, 1.2, 0.3, 0.0), 0.0)

    def test_diamond_square_touches_without_penetration(self):
        distance = 0.5 + math.sqrt(2.0) / 2.0
        self.assertAlmostEqual(pair_depth(0.0, 0.0, 0.0, distance, 0.0, math.pi / 4), 0.0, places=12)
        self.assertAlmostEqual(
            pair_depth(0.0, 0.0, 0.0, distance - 0.05, 0.0, math.pi / 4), 0.05, places=12
        )

    def test_exact_repair_separates_random_overlaps(self):
        rng = np.random.default_rng(3)
        for _ in range(5):
            configuration = np.column_stack(
                [rng.uniform(-1.5, 1.5, 8), rng.uniform(-1.5, 1.5, 8), rng.uniform(-0.7, 0.7, 8)]
            )
            self.assertGreaterEqual(repair_scale(configuration), 1.0)
            repaired_side = make_feasible(configuration)
            self.assertTrue(np.isfinite(repaired_side))
            self.assertTrue(validate(configuration).valid)
            self.assertAlmostEqual(repaired_side, side(configuration), places=12)

    def test_geometric_crossover_keeps_the_square_count(self):
        seed_rng(0)
        for offset in range(10):
            first = random_configuration(11, offset)
            second = random_configuration(11, offset + 100)
            child = np.empty_like(first)
            crossover_cut(first, second, child)
            self.assertEqual(child.shape, first.shape)
            self.assertTrue(np.isfinite(child).all())

    def test_crossover_of_identical_packings_reproduces_them(self):
        seed_rng(1)
        base = lattice_configuration(9)
        child = np.empty_like(base)
        crossover_cut(base, base.copy(), child)
        np.testing.assert_allclose(np.sort(child, axis=0), np.sort(base, axis=0), atol=1e-12)

    def test_all_five_mutations_act_and_stay_finite(self):
        base = lattice_configuration(9)
        for op, name in enumerate(("jitter", "reinsert", "rotate", "cluster-turn", "row-shift"), start=1):
            with self.subTest(mutation=name):
                seed_rng(0)
                configuration = base.copy()
                mutate(configuration, op, 0.5 * side(base))
                self.assertTrue(np.isfinite(configuration).all())
                changed = np.flatnonzero(np.abs(configuration - base).max(axis=1) > 0.0)
                self.assertGreaterEqual(changed.size, 1)
                if op == 1:
                    self.assertEqual(changed.size, base.shape[0])
                if op == 2:
                    self.assertLessEqual(changed.size, 2)
                if op == 3:
                    self.assertEqual(changed.size, 1)
                    self.assertLessEqual(abs(configuration[changed[0], 2]), 0.25 * math.pi + 1e-12)
                if op == 4:
                    deltas = configuration[changed, 2] - base[changed, 2]
                    self.assertTrue(np.allclose(deltas, deltas[0], atol=1e-12))
                if op == 5:
                    delta = configuration[changed] - base[changed]
                    shifted_one_axis = np.allclose(delta[:, 0], 0.0) or np.allclose(delta[:, 1], 0.0)
                    self.assertTrue(shifted_one_axis)

    def test_d4_symmetries_preserve_raster_fingerprints(self):
        perms = d4_perms(16)
        configuration = random_configuration(6, 3)
        reference = raster(configuration, 16)
        transformed = np.empty_like(configuration)
        for symmetry in range(8):
            apply_d4(configuration, symmetry, transformed)
            distance, _ = raster_dist(reference, raster(transformed, 16), perms)
            self.assertLess(distance, 0.02)


class ConfigTests(unittest.TestCase):
    def test_defaults_match_the_reference_settings(self):
        config = SearchConfig(n=5)
        self.assertEqual(
            (config.population_size, config.generations, config.relax_steps, config.compress_attempts),
            (96, 600, 300, 3),
        )
        self.assertEqual((config.islands, config.migrate_every, config.restart_after), (4, 25, 60))
        self.assertEqual((config.clearing, config.init, config.polish_rounds, config.seed), (0.06, "random", 30, 0))

    def test_config_maps_onto_the_reference_ga_config(self):
        config = SearchConfig(
            n=7,
            population_size=11,
            generations=5,
            relax_steps=7,
            compress_attempts=2,
            islands=3,
            migrate_every=4,
            restart_after=6,
            clearing=0.05,
            init="lattice",
            polish_rounds=9,
            seed=13,
        )
        ga = config.to_ga_config()
        self.assertEqual((ga.n, ga.pop_size, ga.generations), (7, 11, 5))
        self.assertEqual((ga.relax_steps, ga.compress_attempts, ga.islands), (7, 2, 3))
        self.assertEqual((ga.migrate_every, ga.restart_after, ga.clearing), (4, 6, 0.05))
        self.assertEqual((ga.init, ga.polish_rounds, ga.seed), ("lattice", 9, 13))

    def test_invalid_configuration_is_rejected(self):
        for kwargs in (
            {"n": 0},
            {"n": 5, "population_size": 1},
            {"n": 5, "generations": -1},
            {"n": 5, "compress_attempts": 0},
            {"n": 5, "init": "hex"},
            {"n": 5, "clearing": 1.5},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    SearchConfig(**kwargs)


class GenomeTests(unittest.TestCase):
    def test_grid_layout_is_a_legal_unit_grid(self):
        for n in (1, 2, 4, 5, 9):
            with self.subTest(n=n):
                layout = grid_layout(n)
                result = evaluate_squares(n, to_squares(layout))
                self.assertTrue(result.valid)
                self.assertAlmostEqual(float(result.side_length), float(math.ceil(math.sqrt(n))), places=12)

    def test_layout_from_configuration_splits_centres_and_angles(self):
        genome = np.array([[1.0, 2.0, 0.25], [-3.0, 0.5, -0.75]])
        layout = layout_from_configuration(genome)
        self.assertIsInstance(layout, Layout)
        np.testing.assert_array_equal(layout.centers, genome[:, :2])
        np.testing.assert_array_equal(layout.angles, genome[:, 2])
        genome[0, 0] = 99.0
        self.assertEqual(float(layout.centers[0, 0]), 1.0)
        with self.assertRaises(ValueError):
            layout_from_configuration(np.zeros((2, 2)))

    def test_to_squares_round_trips_floats_exactly(self):
        centers = np.array([[0.1, -0.2], [1e-9, 3.0], [-4.0, 0.0]])
        angles = np.array([1.0 / 3.0, -math.pi / 7.0, 0.0])
        squares = to_squares(make_layout(centers, angles))
        self.assertEqual([float(square.x) for square in squares], list(centers[:, 0]))
        self.assertEqual([float(square.y) for square in squares], list(centers[:, 1]))
        self.assertEqual([float(square.angle) for square in squares], list(angles))


class AdapterTests(unittest.TestCase):
    def test_n1_returns_the_unit_grid(self):
        result = cached_optimize(tiny_config(1, seed=3))
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.side_length, 1.0, places=12)
        self.assertEqual(result.score, 0.0)
        self.assertFalse(result.improved_from_grid)
        np.testing.assert_array_equal(result.layout.centers, grid_layout(1).centers)

    def test_n4_keeps_the_two_by_two_grid_when_search_cannot_improve(self):
        result = cached_optimize(tiny_config(4, seed=5))
        self.assertTrue(result.valid)
        self.assertLessEqual(result.score, grid_fallback_score(4))
        # the grid is optimal for four squares, so a strict improvement is impossible
        self.assertFalse(result.improved_from_grid)
        np.testing.assert_array_equal(result.layout.centers, grid_layout(4).centers)

    def test_n5_small_budget_run_is_certified(self):
        result = cached_optimize(tiny_config(5, seed=13))
        self.assertIsInstance(result, OptimizationResult)
        self.assertEqual(result.layout.centers.shape, (5, 2))
        self.assertEqual(result.layout.angles.shape, (5,))
        self.assertTrue(result.valid)
        self.assertLessEqual(result.score, grid_fallback_score(5))
        certified = evaluate_squares(5, to_squares(result.layout))
        self.assertTrue(certified.valid)
        self.assertAlmostEqual(certified.score, result.score, places=12)

    def test_records_real_evaluation_counts_and_upstream_fields(self):
        config = tiny_config(4, seed=5)
        with mock.patch.object(certification, "evaluate_squares", wraps=evaluate_squares) as patched:
            result = optimize(config)
        # grid guard + one candidate + one final re-certification, and nothing fabricated
        self.assertEqual(patched.call_count, result.certified_evaluations)
        self.assertGreaterEqual(result.certified_evaluations, 3)
        self.assertEqual(result.generations_run, config.generations)
        self.assertGreaterEqual(result.evaluations, config.population_size)
        self.assertGreater(result.upstream_side, 0.0)

    def test_same_seed_reproduces_the_layout(self):
        config = tiny_config(5, seed=11)
        first = optimize(config)
        second = optimize(config)
        np.testing.assert_array_equal(first.layout.centers, second.layout.centers)
        np.testing.assert_array_equal(first.layout.angles, second.layout.angles)
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.upstream_side, second.upstream_side)
        self.assertEqual(first.evaluations, second.evaluations)

    def test_invalid_candidate_cannot_become_champion(self):
        grid = grid_layout(2)
        incumbent = certify_layout(grid)
        self.assertIsInstance(incumbent, CertifiedLayout)
        self.assertTrue(incumbent.valid)

        overlapping = make_layout(np.array([[0.5, 0.5], [0.6, 0.5]]), np.zeros(2))
        candidate = certify_layout(overlapping, incumbent.certified_evaluations)
        self.assertFalse(candidate.valid)

        updated = certify_improvement(candidate, incumbent)
        self.assertEqual(updated.score, incumbent.score)
        np.testing.assert_array_equal(updated.layout.centers, grid.centers)
        self.assertEqual(updated.certified_evaluations, incumbent.certified_evaluations + 1)

    def test_equal_score_candidate_is_not_an_improvement(self):
        grid = grid_layout(3)
        incumbent = certify_layout(grid)
        candidate = certify_layout(make_layout(grid.centers, grid.angles), incumbent.certified_evaluations)
        updated = certify_improvement(candidate, incumbent)
        self.assertIs(updated.layout, incumbent.layout)
        self.assertEqual(updated.certified_evaluations, incumbent.certified_evaluations + 1)

    def test_strictly_better_valid_candidate_replaces_incumbent(self):
        spread = make_layout(np.array([[0.5, 0.5], [2.5, 0.5]]), np.zeros(2))
        incumbent = certify_layout(spread)
        self.assertTrue(incumbent.valid)

        candidate = certify_layout(grid_layout(2), incumbent.certified_evaluations)
        self.assertTrue(candidate.valid)
        self.assertLess(candidate.score, incumbent.score)

        updated = certify_improvement(candidate, incumbent)
        self.assertIs(updated.layout, candidate.layout)
        self.assertLess(updated.score, incumbent.score)
        self.assertEqual(updated.certified_evaluations, 2)


class SnapshotTests(unittest.TestCase):
    def test_snapshots_are_taken_every_ten_generations(self):
        result = cached_optimize(snapshot_config())
        self.assertEqual([snapshot.index for snapshot in result.snapshots], [1, 2])
        self.assertEqual([snapshot.generation for snapshot in result.snapshots], [10, 20])
        for snapshot in result.snapshots:
            self.assertIsInstance(snapshot, Snapshot)
            self.assertEqual(snapshot.layout.n, 5)
            self.assertIsInstance(snapshot.valid, bool)
            self.assertAlmostEqual(snapshot.score, float(snapshot.result.score), places=12)

    def test_short_runs_collect_no_snapshots(self):
        result = cached_optimize(tiny_config(3, seed=2))
        self.assertEqual(result.snapshots, ())

    def test_every_snapshot_is_certified_and_counted(self):
        config = snapshot_config(seed=21)
        with mock.patch.object(certification, "evaluate_squares", wraps=evaluate_squares) as patched:
            result = optimize(config)
        self.assertEqual(len(result.snapshots), 2)
        self.assertEqual(patched.call_count, result.certified_evaluations)
        # grid guard + 2 snapshots + final candidate + final re-certification
        self.assertGreaterEqual(result.certified_evaluations, 5)
        self.assertEqual(
            result.snapshots[-1].certified_evaluations,
            result.certified_evaluations - 2,
        )

    def test_write_run_stores_every_snapshot_and_a_matching_history(self):
        config = snapshot_config()
        result = cached_optimize(config)
        self.assertEqual(len(result.snapshots), 2)
        with tempfile.TemporaryDirectory() as directory:
            stale_path = Path(directory) / "n005" / "no-5-99.csv"
            stale_path.parent.mkdir(parents=True)
            stale_path.write_text("stale\n")
            layout_path, _, _ = write_run(Path(directory), result, config)
            run_dir = layout_path.parent
            self.assertFalse(stale_path.exists())
            self.assertEqual(run_dir.name, "n005")
            self.assertEqual(layout_path.name, "no-5-final.csv")
            self.assertEqual(
                sorted(path.name for path in run_dir.glob("no-5-*.csv")),
                ["no-5-1.csv", "no-5-2.csv", "no-5-final.csv"],
            )

            history = [json.loads(line) for line in (run_dir / "history.jsonl").read_text().splitlines()]
            self.assertEqual([entry["index"] for entry in history], [1, 2])
            self.assertEqual([entry["generation"] for entry in history], [10, 20])
            self.assertEqual([entry["filename"] for entry in history], ["no-5-1.csv", "no-5-2.csv"])

            for entry in history:
                self.assertEqual(
                    set(entry),
                    {"index", "generation", "filename", "valid", "side_length", "score", "reason"},
                )
                snapshot_path = run_dir / entry["filename"]
                self.assertTrue(snapshot_path.exists())
                puzzle = score_submission_text(snapshot_path.read_text(), puzzle_sizes=(5,)).puzzles[0]
                self.assertEqual(puzzle.valid, entry["valid"])
                self.assertAlmostEqual(puzzle.score, entry["score"], places=12)
                if entry["valid"]:
                    self.assertAlmostEqual(float(puzzle.side_length), entry["side_length"], places=9)
                else:
                    self.assertIsNone(entry["side_length"])

    def test_invalid_snapshot_is_stored_and_flagged_not_hidden(self):
        overlapping = make_layout(np.array([[0.5, 0.5], [0.6, 0.5]]), np.zeros(2))
        invalid = certify_layout(overlapping)
        self.assertFalse(invalid.valid)
        snapshot = Snapshot(1, 10, invalid.layout, invalid.result, invalid.certified_evaluations)

        base = cached_optimize(tiny_config(2, seed=5))
        result = OptimizationResult(
            n=base.n,
            layout=base.layout,
            side_length=base.side_length,
            score=base.score,
            valid=base.valid,
            improved_from_grid=base.improved_from_grid,
            certified_evaluations=snapshot.certified_evaluations,
            seed=base.seed,
            upstream_side=base.upstream_side,
            generations_run=10,
            evaluations=base.evaluations,
            snapshots=(snapshot,),
        )
        config = SearchConfig(n=2)
        with tempfile.TemporaryDirectory() as directory:
            layout_path, _, _ = write_run(Path(directory), result, config)
            run_dir = layout_path.parent
            self.assertTrue((run_dir / "no-2-1.csv").exists())
            entry = json.loads((run_dir / "history.jsonl").read_text().splitlines()[0])
            self.assertFalse(entry["valid"])
            self.assertIsNone(entry["side_length"])
            self.assertNotEqual(entry["reason"], "feasible")
            self.assertEqual((entry["index"], entry["generation"]), (1, 10))
            self.assertEqual(
                score_submission_text((run_dir / "no-2-1.csv").read_text(), puzzle_sizes=(2,)).puzzles[0].valid,
                False,
            )


class SearchQualityTests(unittest.TestCase):
    def test_n5_small_budget_reaches_the_tilted_side_in_the_reference_validator(self):
        # Same budget as the upstream test suite: 2 + sqrt(2)/2 = 2.7071... needs a tilt.
        result = cached_optimize(SEARCH_BUDGET)
        self.assertTrue(result.valid)
        self.assertLess(result.upstream_side, 2.0 + math.sqrt(2.0) / 2.0 + 2e-3)

    def test_champion_is_high_precision_legal_and_not_worse_than_the_grid(self):
        result = cached_optimize(SEARCH_BUDGET)
        certified = evaluate_squares(5, to_squares(result.layout))
        self.assertTrue(certified.valid)
        self.assertAlmostEqual(certified.score, result.score, places=12)
        self.assertLessEqual(result.score, grid_fallback_score(5))
        self.assertGreaterEqual(result.certified_evaluations, 3)


class LegacyRemovalTests(unittest.TestCase):
    def test_legacy_kss_and_annealing_modules_are_gone(self):
        for name in ("annealing", "fast_geometry", "fitness", "genetic", "initialization", "repair"):
            with self.subTest(module=name):
                with self.assertRaises(ImportError):
                    importlib.import_module(f"genetic_annealing.{name}")

    def test_public_api_has_no_hand_made_seed(self):
        self.assertFalse(hasattr(genetic_annealing, "n5_structural_layout"))
        self.assertFalse(hasattr(genetic_annealing, "structural_seeds"))


class SerializationTests(unittest.TestCase):
    def test_layout_csv_and_metrics_round_trip(self):
        config = tiny_config(5, seed=6)
        result = cached_optimize(config)
        with tempfile.TemporaryDirectory() as directory:
            layout_path, metrics_path, config_path = write_run(Path(directory), result, config)
            run_dir = Path(directory) / "n005"
            self.assertEqual(layout_path, run_dir / "no-5-final.csv")
            self.assertEqual(metrics_path, run_dir / "metrics.json")
            self.assertEqual(config_path, run_dir / "config.json")
            self.assertTrue((run_dir / "history.jsonl").exists())

            with layout_path.open(newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(len(rows), 5)
            self.assertEqual({int(row["square_id"]) for row in rows}, set(range(5)))
            self.assertEqual({int(row["n"]) for row in rows}, {5})
            for row in rows:
                for field in ("x", "y", "angle"):
                    self.assertIsNotNone(DECIMAL_LITERAL.fullmatch(row[field]))

            report = score_submission_text(layout_path.read_text(), puzzle_sizes=(5,))
            self.assertTrue(report.puzzles[0].valid)
            self.assertAlmostEqual(report.puzzles[0].score, result.score, places=12)
            self.assertLessEqual(report.puzzles[0].score, grid_fallback_score(5))

            metrics = json.loads(metrics_path.read_text())
            self.assertEqual(metrics["n"], 5)
            self.assertEqual(metrics["seed"], config.seed)
            self.assertEqual(metrics["valid"], result.valid)
            self.assertEqual(metrics["improved_from_grid"], result.improved_from_grid)
            self.assertEqual(metrics["certified_evaluations"], result.certified_evaluations)
            self.assertEqual(metrics["snapshots"], len(result.snapshots))
            self.assertEqual(metrics["upstream_side"], result.upstream_side)
            self.assertEqual(metrics["generations_run"], result.generations_run)
            self.assertEqual(metrics["evaluations"], result.evaluations)
            self.assertIn("grid_side_length", metrics)
            self.assertIn("grid_score", metrics)
            self.assertNotIn("runtime_seconds", metrics)
            self.assertEqual(metrics["parameters"]["population_size"], config.population_size)
            self.assertEqual(metrics["parameters"]["relax_steps"], config.relax_steps)
            self.assertNotIn("annealing_steps", metrics["parameters"])

            stored_config = json.loads(config_path.read_text())
            self.assertEqual(stored_config["n"], 5)
            self.assertEqual(stored_config["seed"], config.seed)
            self.assertEqual(stored_config["islands"], config.islands)
            self.assertEqual(stored_config["compress_attempts"], config.compress_attempts)
            self.assertNotIn("annealing_steps", stored_config)

    def test_metrics_record_runtime_only_when_measured(self):
        config = tiny_config(3, seed=8)
        result = cached_optimize(config)
        self.assertNotIn("runtime_seconds", metrics_payload(result, config))
        self.assertEqual(metrics_payload(result, config, 1.25)["runtime_seconds"], 1.25)

        with tempfile.TemporaryDirectory() as directory:
            _, unmeasured_path, _ = write_run(Path(directory), result, config)
            unmeasured = json.loads(unmeasured_path.read_text())
            _, measured_path, _ = write_run(Path(directory), result, config, runtime_seconds=1.25)
            measured = json.loads(measured_path.read_text())
        self.assertNotIn("runtime_seconds", unmeasured)
        self.assertEqual(measured["runtime_seconds"], 1.25)
        self.assertEqual(measured["n"], config.n)
        self.assertEqual(measured["certified_evaluations"], result.certified_evaluations)


class CommandLineTests(unittest.TestCase):
    def test_defaults_match_the_documented_defaults(self):
        with mock.patch("sys.argv", ["genetic-annealing"]):
            arguments = parse_arguments()
        self.assertEqual(arguments.n, 5)
        self.assertEqual(arguments.population_size, 96)
        self.assertEqual(arguments.generations, 600)
        self.assertEqual(arguments.relax_steps, 300)
        self.assertEqual(arguments.compress_attempts, 3)
        self.assertEqual(arguments.islands, 4)
        self.assertEqual(arguments.seed, 0)
        self.assertEqual(arguments.output_dir, Path("runs"))
        self.assertEqual(arguments.init, "random")
        self.assertEqual(arguments.polish_rounds, 30)

    def test_annealing_steps_flag_is_removed(self):
        with mock.patch("sys.argv", ["genetic-annealing", "--annealing-steps", "20"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_arguments()

    def test_single_puzzle_cli_writes_the_per_n_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "genetic-annealing",
                "--n", "2",
                "--population-size", "4",
                "--generations", "2",
                "--relax-steps", "10",
                "--output-dir", directory,
            ]
            with mock.patch("sys.argv", argv):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = cli_main()
            run_dir = Path(directory) / "n002"
            self.assertEqual(exit_code, 0)
            self.assertTrue((run_dir / "no-2-final.csv").exists())
            self.assertTrue((run_dir / "history.jsonl").exists())
            self.assertIn("snapshots=0", output.getvalue())
            self.assertIn(str(run_dir / "no-2-final.csv"), output.getvalue())


class BatchMainTests(unittest.TestCase):
    def test_defaults_cover_one_to_one_thousand(self):
        arguments = batch_main.parse_arguments([])
        self.assertEqual(arguments.start, 1)
        self.assertEqual(arguments.end, 1000)
        self.assertEqual(arguments.output_dir, Path("runs"))
        self.assertIsNone(arguments.population_size)
        self.assertIsNone(arguments.generations)
        self.assertIsNone(arguments.relax_steps)
        self.assertIsNone(arguments.seed)
        sizes = batch_main.selected_sizes(arguments)
        self.assertEqual(len(sizes), 1000)
        self.assertEqual((sizes[0], sizes[-1]), (1, 1000))

    def test_range_is_validated(self):
        for argv in (["--start", "0"], ["--end", "1001"], ["--start", "5", "--end", "4"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        batch_main.parse_arguments(argv)

    def test_overrides_reach_the_search_config_and_defaults_survive(self):
        arguments = batch_main.parse_arguments(
            ["--population-size", "8", "--generations", "3", "--relax-steps", "5", "--seed", "11"]
        )
        config = batch_main.search_config(4, arguments)
        self.assertEqual((config.n, config.population_size, config.generations), (4, 8, 3))
        self.assertEqual((config.relax_steps, config.seed), (5, 11))

        defaults = batch_main.search_config(4, batch_main.parse_arguments([]))
        self.assertEqual(
            (defaults.population_size, defaults.generations, defaults.relax_steps, defaults.seed),
            (96, 600, 300, 0),
        )

    def test_small_real_batch_writes_one_directory_per_n(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "--start", "1",
                "--end", "2",
                "--population-size", "4",
                "--generations", "2",
                "--relax-steps", "10",
                "--output-dir", directory,
            ]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = batch_main.main(argv)
            self.assertEqual(exit_code, 0)
            self.assertEqual(output.getvalue().count("n="), 2)

            for n in (1, 2):
                run_dir = Path(directory) / f"n{n:03d}"
                layout_path = run_dir / f"no-{n}-final.csv"
                self.assertTrue(layout_path.exists())
                self.assertTrue((run_dir / "metrics.json").exists())
                self.assertTrue((run_dir / "config.json").exists())
                self.assertTrue((run_dir / "history.jsonl").exists())
                puzzle = score_submission_text(layout_path.read_text(), puzzle_sizes=(n,)).puzzles[0]
                self.assertTrue(puzzle.valid)
                self.assertAlmostEqual(
                    puzzle.score,
                    json.loads((run_dir / "metrics.json").read_text())["score"],
                    places=12,
                )


if __name__ == "__main__":
    unittest.main()
