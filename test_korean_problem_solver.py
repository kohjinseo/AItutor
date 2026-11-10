import subprocess
import unittest
from unittest.mock import patch

from korean_problem_solver import read_korean_image, solve_problem


class KoreanProblemTests(unittest.TestCase):
    def test_word_problems(self):
        for text, answer in [
            ("어떤 수의 두 배에 3을 더하면 11이다. 그 수를 구하시오.", "x = 4"),
            ("어떤 수의 세 배에서 5를 빼면 10이다.", "x = 5"),
            ("어떤 수에 0.2를 더하면 0.3이다.", "x = 0.1"),
            ("어떤 수에서 -2를 빼면 5이다.", "x = 3"),
            ("어떤 수의 3배에 0을 더하면 1이다.", "x = 1/3"),
            ("다음 일차방정식을 풀어라. 2x+3=11", "x = 4"),
        ]:
            with self.subTest(text=text):
                result = solve_problem(text)
                self.assertEqual(result["status"], "solved", result)
                self.assertEqual(result["solution"]["answer"], answer)
                self.assertTrue(result["solution"]["check"]["matches"])
                self.assertEqual(result["solution"]["check"]["basis"], "generated_equation")

    def test_extra_conditions_are_not_discarded(self):
        for text in [
            "", "사과 3개와 배 2개의 가격은 1000원이다.",
            "어떤 수의 두 배에 3을 더하면 11이다. 단, 그 수는 10보다 크다.",
            "x+1=2 그리고 x>5", "x*x=4", "__import__('os')", "x" * 4097,
        ]:
            with self.subTest(text=text):
                self.assertEqual(solve_problem(text)["status"], "needs_review")

    @patch("korean_problem_solver.shutil.which", return_value="tesseract.exe")
    @patch("korean_problem_solver.subprocess.run")
    @patch("korean_problem_solver.Path.is_file", return_value=True)
    def test_ocr_to_solution(self, exists, run, which):
        run.return_value = subprocess.CompletedProcess([], 0, "어떤 수의 두 배에 3을 더하면 11이다.", "")
        result = solve_problem(read_korean_image("photo.png"), "tesseract")
        self.assertEqual(result["solution"]["answer"], "x = 4")
        self.assertIn("kor+eng", run.call_args.args[0])
        run.return_value = subprocess.CompletedProcess([], 1, "", "missing kor")
        with self.assertRaisesRegex(ValueError, "kor"):
            read_korean_image("photo.png")


if __name__ == "__main__":
    unittest.main()
