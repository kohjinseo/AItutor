"""Korean printed text OCR and a deliberately limited word-problem solver."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata

from linear_solver import solve_latex


NUMBER = r"-?\d+(?:\.\d+)?"
COUNT = r"(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|\d+(?:\.\d+)?)"
COUNTS = dict(zip(("한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"), range(1, 11)))


def read_korean_image(path, executable="tesseract"):
    """Run Tesseract without a shell; preserve its original recognized text."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"사진 파일이 없습니다: {path}")
    command = shutil.which(executable)
    if command is None:
        raise ValueError("Tesseract를 설치하고 PATH 또는 --tesseract로 실행 파일을 지정하세요.")
    result = subprocess.run(
        [command, str(path.resolve()), "stdout", "-l", "kor+eng", "--psm", "6"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if result.returncode:
        raise ValueError("한국어 OCR 실패. kor/eng 언어 데이터를 확인하세요. " + result.stderr.strip())
    return result.stdout.strip()


def interpret(text):
    """Accept complete known prompts rather than extracting arbitrary numbers."""
    text = unicodedata.normalize("NFKC", text).replace("−", "-")
    compact = re.sub(r"\s+", "", text).rstrip(".!?。")
    # Full match prevents silently discarding additional conditions or subproblems.
    direct = re.fullmatch(
        r"(?:다음(?:일차)?방정식을(?:풀어라|푸시오|풀어보세요)[.:]?)?"
        r"(?P<equation>[0-9xX().+*\-=]+)", compact,
    )
    if direct and "=" in direct["equation"]:
        return {
            "rule": "explicit_equation", "unknown": "x",
            "equation": direct["equation"].lower(),
            "explanation": "문장에 주어진 방정식에서 x의 값을 구합니다.",
        }

    suffix = r"(?:이다|입니다)?(?:[.,]?)(?:(?:이때)?(?:어떤수|그수|이수)(?:의값)?(?:을|를)구하(?:여라|시오|세요))?"
    match = re.fullmatch(
        rf"어떤수(?:의)?(?:(?P<factor>{COUNT})배)?"
        rf"(?:(?:에|에서)(?P<amount>{NUMBER})(?:을|를)(?P<operation>더하면|빼면))?"
        rf"(?P<target>{NUMBER}){suffix}", compact,
    )
    if not match:
        return None
    # Require an actual operation so unrelated numeric strings are not accepted.
    if match["factor"] is None and match["operation"] is None:
        return None
    factor = match["factor"] or "1"
    factor = str(COUNTS.get(factor, factor))
    expression = f"{factor}x"
    if match["operation"]:
        operator = "+" if match["operation"] == "더하면" else "-"
        expression += f"{operator}({match['amount']})"
    equation = expression + "=" + match["target"]
    return {
        "rule": "number_multiple_add_subtract", "unknown": "어떤 수를 x로 둡니다.",
        "equation": equation,
        "explanation": f"어떤 수의 배수를 {factor}x로 나타내고, 더하기·빼기와 결과를 식으로 옮깁니다: {equation}",
    }


def solve_problem(text, source="text"):
    result = {
        "recognized_text": text, "source": source, "status": "needs_review",
        "interpretation": None, "solution": None,
        "review_notes": ["원본 사진·문장의 조건과 생성한 식이 일치하는지 확인하세요."],
    }
    if not isinstance(text, str) or not text.strip():
        result["reason"] = "인식된 글자가 없습니다."
        return result
    if len(text) > 4096:
        result["reason"] = "문장이 너무 깁니다. 한 문제씩 입력하세요."
        return result
    interpretation = interpret(text)
    result["interpretation"] = interpretation
    if interpretation is None:
        result["reason"] = "지원하는 문장 형식이 아닙니다. 조건을 추측해 식을 만들지 않았습니다."
        return result
    solution = solve_latex(interpretation["equation"])
    if solution["check"]:
        solution["check"]["basis"] = "generated_equation"
    result["solution"] = solution
    result["status"] = solution["status"] if solution["status"] != "unsupported" else "needs_review"
    return result


def main():
    parser = argparse.ArgumentParser(description="한국어 OCR → 지원 문장 해석 → 식 생성 → 일차방정식 풀이")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--image", type=Path)
    inputs.add_argument("--text", help="OCR 설치 없이 문장 해석과 풀이 시험")
    parser.add_argument("--tesseract", default="tesseract", help="Tesseract 실행 파일 경로")
    args = parser.parse_args()
    try:
        text = read_korean_image(args.image, args.tesseract) if args.image else args.text
        result = solve_problem(text, "tesseract" if args.image else "text")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"오류: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
