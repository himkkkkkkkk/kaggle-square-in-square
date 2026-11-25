import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("search_algorithm", ROOT / "search/algorithm.py")
algorithm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(algorithm)


class SearchAlgorithmTests(unittest.TestCase):
    def test_overlap_energy(self):
        first, second = np.triu_indices(2, 1)
        separated = np.array([[-0.5, 0, 0], [0.5, 0, 0]]).ravel()
        overlapping = np.array([[0, 0, 0], [0, 0, 0]]).ravel()
        separated_energy, _ = algorithm.energy_grad(separated, 2, first, second, 1.0)
        overlapping_energy, _ = algorithm.energy_grad(overlapping, 2, first, second, 1.0)
        self.assertAlmostEqual(separated_energy, 0.0)
        self.assertGreater(overlapping_energy, 0.0)

    def test_loads_a_previous_layout_and_rejects_invalid_cache(self):
        valid = algorithm.grid_layout(2)
        layout, result = algorithm.load_incumbent(2, {"2": valid})
        self.assertTrue(result.valid)
        self.assertEqual(layout, valid)
        layout, result = algorithm.load_incumbent(2, {"2": [[0, 0, 0], [0, 0, 0]]})
        self.assertTrue(result.valid)
        self.assertEqual(layout, valid)

    def test_lbfgs_returns_a_shaped_layout(self):
        first, second = np.triu_indices(10, 1)
        layout, optimization = algorithm.relax_energy(algorithm.grid_layout(10), 4.0, 10, first, second, maxiter=1)
        self.assertEqual(layout.shape, (10, 3))
        self.assertGreaterEqual(optimization.nit, 0)


if __name__ == "__main__":
    unittest.main()
