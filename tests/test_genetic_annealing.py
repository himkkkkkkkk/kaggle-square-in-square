"""Tests for the Kick-Separate-Shrink genetic plus simulated annealing baseline."""

import csv
import json
import math
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path
from unittest import mock

import numpy as np

from genetic_annealing import (
    CertifiedIncumbent,
    OptimizationResult,
    SearchConfig,
    certify_candidate,
    clamp_to_box,
    evaluate_search,
    fit_angle_to_box,
    grid_layout,
    kick,
    make_layout,
    n5_structural_layout,
    optimize,
    separate_overlaps,
    target_box_side,
    to_squares,
    wrap_angles,
)
from genetic_annealing import certification
from genetic_annealing.__main__ import parse_arguments
from genetic_annealing.annealing import anneal
from genetic_annealing.fast_geometry import penetration, rotated_corners, side_length
from genetic_annealing.genetic import (
    arithmetic_crossover,
    mutate,
    next_generation,
    uniform_crossover,
)
from genetic_annealing.serialization import metrics_payload, write_run
from squares_metric import evaluate_squares, grid_fallback_score, score_submission_text
from squares_metric.validation import DECIMAL_LITERAL


def small_config(n: int, seed: int = 7) -> SearchConfig:
    return SearchConfig(n=n, population_size=6, generations=2, annealing_steps=2, seed=seed)


@lru_cache(maxsize=None)
def certified_n5_result() -> OptimizationResult:
    return optimize(small_config(5, seed=9))


class GridTests(unittest.TestCase):
    def test_n1_returns_unit_grid(self):
        result = optimize(small_config(1, seed=3))
        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.side_length, 1.0, places=12)
        self.assertEqual(result.score, 0.0)
        self.assertFalse(result.improved_from_grid)
        np.testing.assert_allclose(result.layout.centers, grid_layout(1).centers)

    def test_n4_is_not_worse_than_two_by_two_grid(self):
        result = optimize(small_config(4, seed=5))
        self.assertTrue(result.valid)
        self.assertLessEqual(result.score, grid_fallback_score(4))
        certified = evaluate_squares(4, to_squares(result.layout))
        self.assertTrue(certified.valid)
        self.assertAlmostEqual(certified.score, result.score, places=12)

    def test_n2_grid_side_and_penalty(self):
        grid = grid_layout(2)
        grid_corners = rotated_corners(grid.centers, grid.angles)
        self.assertAlmostEqual(side_length(grid_corners), 2.0, places=12)
        self.assertEqual(penetration(grid_corners, grid.angles), 0.0)

        overlapping = make_layout(np.array([[0.5, 0.5], [0.6, 0.5]]), np.zeros(2))
        overlapping_corners = rotated_corners(overlapping.centers, overlapping.angles)
        self.assertAlmostEqual(side_length(overlapping_corners), 1.1, places=12)
        overlapping_penetration = penetration(overlapping_corners, overlapping.angles)
        self.assertGreater(overlapping_penetration, 0.0)

        config = small_config(2, seed=1)
        evaluation = evaluate_search(overlapping, config)
        self.assertAlmostEqual(evaluation.penetration, overlapping_penetration, places=12)
        self.assertAlmostEqual(
            evaluation.fitness,
            evaluation.side_length + config.penalty_weight * evaluation.penetration,
            places=12,
        )
        self.assertGreater(evaluation.fitness, evaluation.side_length)


class SearchTests(unittest.TestCase):
    def test_same_seed_and_config_are_reproducible(self):
        config = small_config(5, seed=11)
        first = optimize(config)
        second = optimize(config)
        np.testing.assert_array_equal(first.layout.centers, second.layout.centers)
        np.testing.assert_array_equal(first.layout.angles, second.layout.angles)
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.certified_evaluations, second.certified_evaluations)
        self.assertEqual(first.structural_seed_improved, second.structural_seed_improved)
        self.assertEqual(first.search_improved, second.search_improved)

    def test_operators_do_not_modify_parents(self):
        config = small_config(3, seed=2)
        first = make_layout(
            np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
            np.array([0.0, 0.3, -0.3]),
        )
        second = make_layout(
            np.array([[0.1, 0.2], [0.9, 0.4], [1.8, -0.2]]),
            np.array([0.4, -0.2, 1.0]),
        )
        first_centers, first_angles = first.centers.copy(), first.angles.copy()
        second_centers, second_angles = second.centers.copy(), second.angles.copy()

        arithmetic_crossover(first, second, np.random.default_rng(0))
        uniform_crossover(first, second, np.random.default_rng(1))
        mutate(first, np.random.default_rng(2), config)
        kick(first, np.random.default_rng(5), config)
        anneal(first, evaluate_search(first, config), np.random.default_rng(3), config)
        population = (first, second)
        evaluations = tuple(evaluate_search(layout, config) for layout in population)
        next_generation(population, evaluations, np.random.default_rng(4), config)

        np.testing.assert_array_equal(first.centers, first_centers)
        np.testing.assert_array_equal(first.angles, first_angles)
        np.testing.assert_array_equal(second.centers, second_centers)
        np.testing.assert_array_equal(second.angles, second_angles)

    def test_wrap_uses_shortest_angle_difference(self):
        angles = np.array([math.pi - 1e-9, math.pi + 1e-9, -math.pi - 1e-9, 3.0 * math.pi + 0.1, 0.0])
        wrapped = wrap_angles(angles)
        self.assertAlmostEqual(wrapped[0], math.pi - 1e-9, places=12)
        self.assertAlmostEqual(wrapped[1], -math.pi + 1e-9, places=12)
        self.assertAlmostEqual(wrapped[2], math.pi - 1e-9, places=12)
        self.assertAlmostEqual(wrapped[3], -math.pi + 0.1, places=12)
        self.assertEqual(wrapped[4], 0.0)
        self.assertTrue(np.all(np.abs(wrapped) <= math.pi + 1e-15))

    def test_overlapping_candidate_cannot_become_champion(self):
        config = small_config(2, seed=4)
        grid = grid_layout(2)
        grid_result = evaluate_squares(2, to_squares(grid))
        self.assertTrue(grid_result.valid)
        incumbent = CertifiedIncumbent(2, grid, grid_result, 1)

        overlapping = make_layout(np.array([[0.5, 0.5], [0.6, 0.5]]), np.zeros(2))
        self.assertLess(evaluate_search(overlapping, config).side_length, incumbent.side_length)

        updated = certify_candidate(overlapping, incumbent)
        self.assertEqual(updated.score, incumbent.score)
        np.testing.assert_array_equal(updated.layout.centers, grid.centers)
        self.assertEqual(updated.certified_evaluations, 2)
        self.assertEqual(updated.fast_rejections, 0)
        self.assertTrue(updated.result.valid)

    def test_tiny_fast_improvement_is_still_certified(self):
        # Incumbent certified L = 2 + 1e-10; the candidate fast L is smaller by only 5e-11,
        # well inside any fixed exclusion margin, so the screen must not skip it.
        incumbent_layout = make_layout(
            np.array([[0.5, 0.5], [1.5 + 1e-10, 0.5]]),
            np.zeros(2),
        )
        incumbent_result = evaluate_squares(2, to_squares(incumbent_layout))
        self.assertTrue(incumbent_result.valid)
        incumbent = CertifiedIncumbent(2, incumbent_layout, incumbent_result, 1)

        candidate = make_layout(
            np.array([[0.5, 0.5], [1.5 + 5e-11, 0.5]]),
            np.zeros(2),
        )
        candidate_fast_side = side_length(rotated_corners(candidate.centers, candidate.angles))
        self.assertLess(candidate_fast_side, incumbent.side_length)
        self.assertGreater(candidate_fast_side, incumbent.side_length - 1e-9)

        # wraps= keeps the production certification logic: the call is recorded, not replaced.
        with mock.patch.object(certification, "evaluate_squares", wraps=evaluate_squares) as certified:
            updated = certify_candidate(candidate, incumbent)

        self.assertEqual(certified.call_count, 1)
        self.assertEqual(updated.certified_evaluations, incumbent.certified_evaluations + 1)
        self.assertEqual(updated.fast_rejections, incumbent.fast_rejections)
        self.assertTrue(updated.result.valid)
        self.assertLess(updated.score, incumbent.score)
        np.testing.assert_array_equal(updated.layout.centers, candidate.centers)

    def test_final_layout_passes_high_precision_validation(self):
        result = certified_n5_result()
        self.assertTrue(result.valid)
        self.assertTrue(evaluate_squares(5, to_squares(result.layout)).valid)

    def test_final_score_is_not_worse_than_grid(self):
        result = certified_n5_result()
        self.assertLessEqual(result.score, grid_fallback_score(5))

    def test_n5_smoke_runs_with_small_budget(self):
        result = optimize(small_config(5, seed=13))
        self.assertIsInstance(result, OptimizationResult)
        self.assertEqual(result.layout.centers.shape, (5, 2))
        self.assertEqual(result.layout.angles.shape, (5,))
        self.assertGreaterEqual(result.certified_evaluations, 2)
        self.assertLessEqual(result.certified_evaluations, 8)

    def test_no_improvement_does_not_overwrite_incumbent(self):
        grid = grid_layout(2)
        grid_result = evaluate_squares(2, to_squares(grid))
        incumbent = CertifiedIncumbent(2, grid, grid_result, 1)

        spread = make_layout(np.array([[0.5, 0.5], [2.5, 0.5]]), np.zeros(2))
        updated = certify_candidate(spread, incumbent)
        self.assertEqual(updated.score, incumbent.score)
        np.testing.assert_array_equal(updated.layout.centers, grid.centers)
        self.assertEqual(updated.certified_evaluations, 1)
        self.assertEqual(updated.fast_rejections, 1)
        self.assertTrue(evaluate_squares(2, to_squares(updated.layout)).valid)

    def test_post_repair_anneal_uses_configured_annealing_steps(self):
        # CLI --annealing-steps must drive the real post-repair polish: one generation
        # performs exactly two anneal calls (elite and kicked elite), both budgeted by
        # config.annealing_steps. Injected steps would silently disconnect the flag again.
        config = SearchConfig(n=4, population_size=4, generations=1, annealing_steps=7, seed=5)
        with mock.patch("genetic_annealing.baseline.anneal", wraps=anneal) as patched:
            optimize(config)

        self.assertEqual(patched.call_count, 2)
        for call in patched.call_args_list:
            self.assertEqual(call.kwargs["steps"], 7)
            self.assertEqual(call.kwargs["steps"], config.annealing_steps)


class StructuralSeedTests(unittest.TestCase):
    def test_n5_structural_seed_is_valid_and_better_than_grid(self):
        seed = n5_structural_layout()
        result = evaluate_squares(5, to_squares(seed))
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.side_length)
        self.assertLess(float(result.side_length), 2.708)
        self.assertLess(result.score, grid_fallback_score(5))

    def test_n5_zero_generations_returns_non_grid_structural_seed(self):
        config = SearchConfig(
            n=5,
            population_size=4,
            generations=0,
            annealing_steps=0,
            seed=42,
        )
        result = optimize(config)
        self.assertTrue(result.valid)
        self.assertLess(result.side_length, 2.708)
        self.assertTrue(result.improved_from_grid)
        self.assertTrue(result.structural_seed_improved)
        self.assertFalse(result.search_improved)
        self.assertFalse(np.allclose(result.layout.centers, grid_layout(5).centers))

    def test_small_grid_sizes_do_not_regress(self):
        for n, seed in ((1, 1), (4, 2), (9, 3)):
            result = optimize(
                SearchConfig(
                    n=n,
                    population_size=4,
                    generations=1,
                    annealing_steps=1,
                    seed=seed,
                )
            )
            self.assertTrue(result.valid)
            self.assertLessEqual(result.score, grid_fallback_score(n) + 1e-12)
            self.assertGreaterEqual(result.certified_evaluations, 1)


class RepairTests(unittest.TestCase):
    def test_repair_reduces_penetration_and_terminates(self):
        config = SearchConfig(
            n=2,
            population_size=4,
            generations=0,
            annealing_steps=0,
            seed=1,
            repair_sweeps=30,
            repair_stagnation_limit=5,
        )
        overlapping = make_layout(np.array([[0.5, 0.5], [0.6, 0.5]]), np.zeros(2))
        before = penetration(
            rotated_corners(overlapping.centers, overlapping.angles),
            overlapping.angles,
        )
        repaired = separate_overlaps(overlapping, 2.0, config)

        self.assertLessEqual(repaired.sweeps, config.repair_sweeps)
        self.assertTrue(repaired.separated)
        self.assertLess(repaired.penetration, before)
        self.assertEqual(repaired.penetration, 0.0)
        self.assertTrue(evaluate_squares(2, to_squares(repaired.layout)).valid)

    def test_repair_fits_angle_inside_tight_box(self):
        self.assertAlmostEqual(fit_angle_to_box(math.pi / 4.0, 1.0), 0.0, places=12)

        tight = make_layout(np.array([[5.0, -5.0]]), np.array([math.pi / 4.0]))
        clamped = clamp_to_box(tight, 1.0)
        np.testing.assert_allclose(clamped.centers, np.array([[0.5, 0.5]]), atol=1e-12)
        self.assertAlmostEqual(float(clamped.angles[0]), 0.0, places=12)

    def test_target_box_uses_area_bound_and_incumbent_shrink(self):
        config = SearchConfig(n=5, population_size=4, generations=0, annealing_steps=0, seed=1)
        self.assertAlmostEqual(target_box_side(5, 3.0, config), 2.94, places=12)
        # incumbent 2.0 -> (1 - 0.02) * 2.0 = 1.96 < sqrt(5), so the area bound wins.
        self.assertAlmostEqual(target_box_side(5, 2.0, config), math.sqrt(5.0), places=12)


class KickTests(unittest.TestCase):
    def test_kick_changes_structure_without_modifying_parent(self):
        config = SearchConfig(
            n=4,
            population_size=4,
            generations=0,
            annealing_steps=0,
            seed=1,
            kick_rotation_probability=1.0,
            kick_relocation_sigma=0.5,
            kick_swap_probability=0.0,
            kick_cluster_probability=0.0,
        )
        parent = grid_layout(4)
        centers = parent.centers.copy()
        angles = parent.angles.copy()

        kicked = kick(parent, np.random.default_rng(3), config)

        np.testing.assert_array_equal(parent.centers, centers)
        np.testing.assert_array_equal(parent.angles, angles)
        self.assertFalse(
            np.array_equal(kicked.centers, parent.centers)
            and np.array_equal(kicked.angles, parent.angles)
        )

    def test_kick_is_reproducible_for_same_seed(self):
        config = SearchConfig(n=4, population_size=4, generations=0, annealing_steps=0, seed=1)
        parent = grid_layout(4)
        first = kick(parent, np.random.default_rng(7), config)
        second = kick(parent, np.random.default_rng(7), config)
        np.testing.assert_array_equal(first.centers, second.centers)
        np.testing.assert_array_equal(first.angles, second.angles)


class SerializationTests(unittest.TestCase):
    def test_layout_csv_rows_and_decimal_format(self):
        config = small_config(5, seed=6)
        result = optimize(config)
        with tempfile.TemporaryDirectory() as directory:
            layout_path, metrics_path, config_path = write_run(Path(directory), result, config)
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
            self.assertEqual(metrics["improved_from_grid"], result.improved_from_grid)
            self.assertEqual(metrics["structural_seed_improved"], result.structural_seed_improved)
            self.assertEqual(metrics["search_improved"], result.search_improved)
            self.assertEqual(metrics["certified_evaluations"], result.certified_evaluations)
            self.assertIn("grid_side_length", metrics)
            self.assertIn("grid_score", metrics)
            self.assertIn("structural_seed_score", metrics)
            self.assertNotIn("runtime_seconds", metrics)
            self.assertEqual(metrics["parameters"]["population_size"], config.population_size)
            self.assertEqual(metrics["parameters"]["repair_rho"], config.repair_rho)

            stored_config = json.loads(config_path.read_text())
            self.assertEqual(stored_config["n"], 5)
            self.assertEqual(stored_config["seed"], config.seed)
            self.assertEqual(stored_config["kick_max_squares"], config.kick_max_squares)

    def test_metrics_record_runtime_only_when_measured(self):
        config = small_config(3, seed=8)
        result = optimize(config)
        self.assertNotIn("runtime_seconds", metrics_payload(result, config))
        self.assertEqual(metrics_payload(result, config, 1.25)["runtime_seconds"], 1.25)

        with tempfile.TemporaryDirectory() as directory:
            _, unreported_metrics_path, _ = write_run(Path(directory), result, config)
            unreported = json.loads(unreported_metrics_path.read_text())
            _, measured_metrics_path, _ = write_run(
                Path(directory), result, config, runtime_seconds=1.25
            )
            measured = json.loads(measured_metrics_path.read_text())

        self.assertNotIn("runtime_seconds", unreported)
        self.assertEqual(measured["runtime_seconds"], 1.25)
        self.assertEqual(measured["n"], config.n)
        self.assertEqual(measured["certified_evaluations"], result.certified_evaluations)


class CommandLineTests(unittest.TestCase):
    def test_default_output_directory_is_runs(self):
        with mock.patch("sys.argv", ["genetic-annealing"]):
            arguments = parse_arguments()
        self.assertEqual(arguments.output_dir, Path("runs"))


if __name__ == "__main__":
    unittest.main()
