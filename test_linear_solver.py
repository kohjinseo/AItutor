r"""Run with: .\.venv\Scripts\python.exe -m unittest -v test_linear_solver"""

import json
import unittest
from unittest.mock import patch

from linear_solver import solve_latex


PHOTO_LATEX = r"\begin{array}{r l}{{\dot{\alpha}}{\mit\Psi}_{*}\ }&{{}{}1.2(x+2)=0.8(3-x)}\end{array}"


class LinearSolverTests(unittest.TestCase):
    def test_actual_photo_latex(self):
        result = solve_latex(PHOTO_LATEX)
        self.assertEqual(result["status"], "solved")
        self.assertEqual(result["equation"], "1.2(x+2) = 0.8(3-x)")
        self.assertEqual(result["answer"], "x = 0")
        self.assertEqual(result["check"], {
            "lhs": "2.4", "rhs": "2.4", "matches": True, "basis": "ocr_equation",
        })
        self.assertEqual(result["other_array_cells"], [r"{{\dot{\alpha}}{\mit\Psi}_{*}\ }"])
        json.dumps(result, ensure_ascii=False)  # Output must remain JSON serializable.

    def test_supported_arithmetic_and_exact_answers(self):
        cases = {
            "2x+3=11": ("x = 4", "11"),
            "-2x+3=11": ("x = -4", "11"),
            "0.1x+0.2=0.3": ("x = 1", "0.3"),
            "0.01x=0.0001": ("x = 0.01", "0.0001"),
            "3x=1": ("x = 1/3", "1"),
            "3x=-1": ("x = -1/3", "-1"),
            "x=0.125": ("x = 0.125", "0.125"),
            "x=-0.125": ("x = -0.125", "-0.125"),
            "x=100.0": ("x = 100", "100"),
            ".5(x+2)=1.": ("x = 0", "1"),
            "2*(x+3)-x=9": ("x = 3", "9"),
            "-(x-2)=+3": ("x = -1", "3"),
            "(2+3)x=10": ("x = 2", "10"),
            "2{x+1}=6": ("x = 2", "6"),
            r"2\mathbf{x}+3=11": ("x = 4", "11"),
            r"\left(2\mathsf{x}+3\right)=11": ("x = 4", "11"),
            r"2\times x+3=11": ("x = 4", "11"),
            r"2\cdot x+3=11": ("x = 4", "11"),
            "−2×x+3=11": ("x = -4", "11"),
            r"\(2x+3=11\)": ("x = 4", "11"),
            "$$2x+3=11$$": ("x = 4", "11"),
        }
        for latex, (answer, check_value) in cases.items():
            with self.subTest(latex=latex):
                result = solve_latex(latex)
                self.assertEqual(result["status"], "solved", result)
                self.assertEqual(result["answer"], answer)
                self.assertEqual(result["check"]["lhs"], check_value)
                self.assertEqual(result["check"]["rhs"], check_value)
                self.assertIs(result["check"]["matches"], True)

    def test_degenerate_equations(self):
        for latex in ("x+1=x+2", "0x=1", "2(x+1)=2x+3"):
            with self.subTest(latex=latex):
                result = solve_latex(latex)
                self.assertEqual(result["status"], "no_solution")
                self.assertIsNone(result["check"])
        for latex in ("x=x", "0x=0", "2(x+1)=2x+2", "x-x=0"):
            with self.subTest(latex=latex):
                result = solve_latex(latex)
                self.assertEqual(result["status"], "infinite_solutions")
                self.assertIsNone(result["check"])

    def test_unsupported_syntax_and_code_are_rejected(self):
        cases = [
            "", None, "1=1", "y+1=2", "x+y=2", "x^2=1", "x*x=1",
            "x(x+1)=2", "x*x=x*x+x", "x/2=1", r"\frac{x}{2}=1",
            r"\sqrt{x}=1", r"\sin(x)=0", "x<1", "x=1=2", "x=", "=1",
            "2(x+1=2", "x+()=1", "x+{1=2", "x+1}=2", "x**2=1",
            "1 2x=4", "1{}2x=4", "{1}{2}x=4", "1{.2}x=4", "1.2.3x=1",
            "x=nan", "x=inf", "x=1e3", "x=__import__('os').getcwd()",
            "x=Symbol('x')", "x=[1][0]", r"x=\input{secrets}",
            r"\text{x+1}=2", r"\unknown{x}=1", r"\mathbf x=1",
            "x=" + "9" * 101, "x=" + "+" * 100 + "1",
            "x=" + "(" * 100 + "x+1" + ")" * 100,
            "x=" + "1+" * 300 + "1", "x=" + "1" * 4096,
        ]
        with patch("builtins.eval", side_effect=AssertionError("eval must not be used")):
            for latex in cases:
                with self.subTest(latex=latex):
                    result = solve_latex(latex)
                    self.assertEqual(result["status"], "unsupported", result)
                    self.assertTrue(result["reason"])
                    self.assertIsNone(result["answer"])
                    self.assertIsNone(result["check"])

    def test_array_selection_and_ambiguity(self):
        for latex in (
            r"\begin{array}{lr}x=1&x=2\end{array}",
            r"\begin{array}{lr}x+1&2\end{array}",
            r"\begin{array}{lr}x&=2\end{array}",
            r"\begin{array}{lr}x=&2\end{array}",
            r"\begin{array}{lr}{x=1&2\end{array}",
        ):
            with self.subTest(latex=latex):
                self.assertEqual(solve_latex(latex)["status"], "unsupported")
        result = solve_latex(r"\begin{array}{lr}1.&2x=8\\\text{note}&{}\end{array}")
        self.assertEqual(result["answer"], "x = 4")
        self.assertEqual(result["other_array_cells"], ["1.", r"\text{note}", "{}"])

    def test_both_photo_ocr_variants(self):
        # Fixtures copied from the existing result.json, without depending on a mutable output file.
        variants = [
            r"\begin{array}{r l}{{\mathbf{4}}{\mathsf{1}}.}&{{}\ 1.2(x+2)=0.8(3-x)}\end{array}",
            PHOTO_LATEX,
        ]
        for latex in variants:
            with self.subTest(latex=latex):
                result = solve_latex(latex)
                self.assertEqual(result["equation"], "1.2(x+2) = 0.8(3-x)")
                self.assertEqual(result["answer"], "x = 0")


if __name__ == "__main__":
    unittest.main()
