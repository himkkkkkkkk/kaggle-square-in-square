import unittest

from evolve import advance_weights, extract_source, improved_sizes, reweight_report, summary, validate_source


class EvolveTests(unittest.TestCase):
    def test_extracts_complete_source_from_markdown(self):
        self.assertEqual(extract_source("```python\nprint('ok')\n```"), "print('ok')\n")
        self.assertEqual(extract_source("print('ok')"), "print('ok')\n")

    def test_source_validation_only_checks_syntax(self):
        validate_source("pass\n" * 1000)
        with self.assertRaises(SyntaxError):
            validate_source("not valid python")

    def test_stagnation_weights_reset_only_for_retained_improvements(self):
        previous = {"results": [
            {"n": 5, "valid": True, "side_length": 3.0, "gap": 0.1},
            {"n": 10, "valid": True, "side_length": 4.0, "gap": 0.2},
        ]}
        candidate = {"results": [
            {"n": 5, "valid": True, "side_length": 2.9, "gap": 0.05},
            {"n": 10, "valid": True, "side_length": 4.0, "gap": 0.2},
        ]}
        improved = improved_sizes(previous, candidate)
        self.assertEqual(improved, {5})
        weights = advance_weights({"5": 1.04, "10": 1.03}, improved)
        self.assertEqual(weights["5"], 1.0)
        self.assertAlmostEqual(weights["10"], 1.0403)
        report = reweight_report({**candidate, "total_score": 0.15}, weights)
        self.assertAlmostEqual(report["total_score"], (0.05 + 1.0403 * 0.2) / 2.0403)

    def test_summary_limits_feedback_to_twenty_worst(self):
        results = [
            {"n": n, "valid": True, "gap": float(n), "weight": 1.0, "reason": "feasible", "target_side_length": 123}
            for n in range(30)
        ]
        report = {"total_score": 1.0, "valid_puzzles": 30, "puzzle_count": 30, "results": results}
        feedback = summary(report)
        self.assertEqual(len(feedback["worst_weighted_gaps"]), 20)
        self.assertEqual(feedback["worst_weighted_gaps"][0]["gap"], 29.0)
        self.assertNotIn("target_side_length", feedback["worst_weighted_gaps"][0])


if __name__ == "__main__":
    unittest.main()
