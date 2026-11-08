"""Compare OCR on an identical image with and without retained crop margins."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from PIL import Image
import torch

from pix2tex.cli import LatexOCR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Image containing one equation")
    parser.add_argument("--margin", type=int, default=20)
    parser.add_argument("--expected", help="Optional reference LaTeX, compared without whitespace")
    parser.add_argument("--solve", action="store_true", help="Solve each OCR result as a linear equation in x")
    args = parser.parse_args()
    if args.margin < 1:
        parser.error("--margin must be at least 1")
    if not args.image.is_file():
        parser.error(f"Image not found: {args.image}")
    if args.solve:
        try:
            from linear_solver import solve_latex
        except ModuleNotFoundError as error:
            if error.name != "sympy":
                raise
            parser.error("--solve requires SymPy. Run: .\\.venv\\Scripts\\python.exe -m pip install sympy==1.13.1")

    with Image.open(args.image) as source:
        image = source.copy()
    ocr = LatexOCR()
    results = {}
    for margin in (0, args.margin):
        # Match the initial random state so sampling alone does not cause disagreements.
        torch.manual_seed(0)
        started = perf_counter()
        latex = ocr(image, crop_margin=margin, copy_to_clipboard=False)
        result = {
            "latex": latex,
            "crop_margin": margin,
            "seconds": round(perf_counter() - started, 3),
        }
        if args.expected is not None:
            result["matches_reference"] = "".join(latex.split()) == "".join(args.expected.split())
        if args.solve:
            result["solution"] = solve_latex(latex)
        results["original" if margin == 0 else "modified"] = result

    original = "".join(results["original"]["latex"].split())
    modified = "".join(results["modified"]["latex"].split())
    results["needs_review"] = not original or original != modified
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
