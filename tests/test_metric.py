import math
import unittest

from squares_metric import (
    Square,
    evaluate_squares,
    grid_fallback_score,
    measure_side_length,
    score_submission_text,
    verify_no_overlaps,
)


def grid_rows(n):
    grid_width = math.ceil(math.sqrt(n))
    return [
        {
            "n": str(n),
            "square_id": str(square_id),
            "x": str(square_id % grid_width + 0.5),
            "y": str(square_id // grid_width + 0.5),
            "angle": "0",
        }
        for square_id in range(n)
    ]


def submission_text(puzzles):
    lines = ["n,square_id,x,y,angle"]
    for rows in puzzles:
        lines.extend(
            f"{row['n']},{row['square_id']},{row['x']},{row['y']},{row['angle']}"
            for row in rows
        )
    return "\n".join(lines)


class GeometryTests(unittest.TestCase):
    def test_unit_square_has_unit_side(self):
        self.assertEqual(measure_side_length((Square("0.5", "0.5", "0"),)), 1)

    def test_rotated_square_has_sqrt_two_side(self):
        square = Square("0", "0", "0.78539816339744830961566084581987572104929234984378")
        self.assertAlmostEqual(float(measure_side_length((square,))), math.sqrt(2), places=14)

    def test_translation_does_not_change_side(self):
        squares = (Square("0.5", "0.5", "0"), Square("1.5", "0.5", "0"))
        translated = (Square("1000.5", "-2000.5", "0"), Square("1001.5", "-2000.5", "0"))
        self.assertEqual(measure_side_length(squares), measure_side_length(translated))

    def test_edge_contact_is_legal(self):
        squares = (Square("0.5", "0.5", "0"), Square("1.5", "0.5", "0"))
        self.assertEqual(verify_no_overlaps(squares), (True, "feasible"))

    def test_area_overlap_is_illegal(self):
        squares = (Square("0.5", "0.5", "0"), Square("0.6", "0.5", "0"))
        self.assertFalse(verify_no_overlaps(squares)[0])

    def test_tiny_overlap_is_illegal(self):
        squares = (Square("0", "0", "0"), Square("0.99999999999999999999999999999999999999999999999999", "0", "0"))
        self.assertFalse(verify_no_overlaps(squares)[0])

    def test_separated_rotated_squares_are_legal(self):
        angle = "0.78539816339744830961566084581987572104929234984378"
        squares = (Square("0", "0", angle), Square("1.4142135624", "0", angle))
        self.assertTrue(verify_no_overlaps(squares)[0])


class ScoringTests(unittest.TestCase):
    def test_perfect_square_grid_scores_zero(self):
        result = evaluate_squares(4, tuple(Square(row["x"], row["y"], row["angle"]) for row in grid_rows(4)))
        self.assertTrue(result.valid)
        self.assertEqual(result.score, 0)

    def test_two_square_grid_matches_formula(self):
        result = evaluate_squares(2, tuple(Square(row["x"], row["y"], row["angle"]) for row in grid_rows(2)))
        self.assertAlmostEqual(result.score, math.sqrt(2) - 1)

    def test_overlap_receives_grid_fallback(self):
        result = evaluate_squares(2, (Square("0", "0", "0"), Square("0", "0", "0")))
        self.assertFalse(result.valid)
        self.assertIsNone(result.side_length)
        self.assertEqual(result.score, grid_fallback_score(2))

    def test_missing_puzzle_receives_grid_fallback(self):
        report = score_submission_text(submission_text((grid_rows(1),)), puzzle_sizes=(1, 2))
        self.assertEqual(report.puzzles[0].score, 0)
        self.assertEqual(report.puzzles[1].score, grid_fallback_score(2))
        self.assertEqual(report.total_score, grid_fallback_score(2))

    def test_invalid_square_ids_receive_grid_fallback(self):
        rows = grid_rows(2)
        rows[1]["square_id"] = "0"
        result = score_submission_text(submission_text((rows,)), puzzle_sizes=(2,)).puzzles[0]
        self.assertFalse(result.valid)
        self.assertEqual(result.score, grid_fallback_score(2))

    def test_symbolic_coordinate_receives_grid_fallback(self):
        rows = grid_rows(1)
        rows[0]["x"] = "sqrt(2)"
        result = score_submission_text(submission_text((rows,)), puzzle_sizes=(1,)).puzzles[0]
        self.assertFalse(result.valid)
        self.assertEqual(result.score, 0)

    def test_scientific_notation_is_accepted(self):
        rows = grid_rows(1)
        rows[0]["x"] = "5e-1"
        result = score_submission_text(submission_text((rows,)), puzzle_sizes=(1,)).puzzles[0]
        self.assertTrue(result.valid)
        self.assertEqual(result.score, 0)


if __name__ == "__main__":
    unittest.main()
