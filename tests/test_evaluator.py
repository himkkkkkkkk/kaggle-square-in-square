import unittest

from evaluator import evaluate_layout, score_layouts


class EvaluatorTests(unittest.TestCase):
    def test_valid_layout_and_improvement(self):
        result = evaluate_layout(1, [[0, 0, 0]])
        self.assertTrue(result.valid)
        self.assertEqual(float(result.side_length), 1.0)
        report = score_layouts({"1": [[0, 0, 0]]}, {"1": {"s": 2.0}}, {"1": 1.0})
        self.assertEqual(report["total_score"], -0.5)

    def test_overlap_and_malformed_layout_are_invalid(self):
        self.assertFalse(evaluate_layout(2, [[0, 0, 0], [0, 0, 0]]).valid)
        self.assertFalse(evaluate_layout(1, None).valid)

    def test_missing_layout_and_normalized_weights(self):
        targets = {"1": {"s": 1.0}, "2": {"s": 1.5}}
        report = score_layouts({"1": [[0, 0, 0]]}, targets, {"1": 1.0, "2": 3.0})
        self.assertEqual(report["valid_puzzles"], 1)
        self.assertAlmostEqual(report["total_score"], 0.25)
        self.assertEqual(report["results"][1]["reason"], "missing")

    def test_unknown_puzzle_is_rejected(self):
        with self.assertRaises(ValueError):
            score_layouts({"3": []}, {"1": {"s": 1.0}})


if __name__ == "__main__":
    unittest.main()
