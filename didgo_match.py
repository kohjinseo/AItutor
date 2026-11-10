"""Read a Didgo problem and report the source match or a provisional topic."""

import argparse
import ast
import inspect
import json
import math
import re
import shutil
import subprocess
import unicodedata
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from zipfile import BadZipFile, ZipFile


BANK_NAME = "didgo_m1_s1_full_problem_bank.zip"
TOPICS = {
    (False, False, False): "7103047",
    (False, False, True): "7103048",
    (False, True, False): "7103049",
    (True, False, False): "7103050",
    (True, True, False): "7103051",
}
MARKED_MATH = re.compile(r"\$([^$]+)\$|\\\((.*?)\\\)|\\\[(.*?)\\\]", re.S)
PLAIN_EQUATION = re.compile(r"(?<![a-zA-Z0-9])[0-9x().+\-*/^ \t]+=[0-9x().+\-*/^ \t]+(?![a-zA-Z0-9])")
LATEX_FRACTION = re.compile(r"\\(?:d|t)?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
DIRECT_PROMPT = re.compile(
    r"(?:다음)?(?:일차)?(?:방정식|식)?(?:의|을|를)?"
    r"(?:풀어라|푸시오|풀어보세요|해를구하여라|해를구하시오|해를구해|해를구하세요|x의값을구하여라|x의값을구하시오)"
)
SUPERSCRIPTS = str.maketrans({c: f"^{i}" for i, c in enumerate("⁰¹²³⁴⁵⁶⁷⁸⁹")})
TRANSLATE = str.maketrans({
    "−": "-", "‒": "-", "–": "-", "×": "*", "·": "*", "÷": "/",
    "［": "(", "］": ")", "[": "(", "]": ")", "｛": "(", "｝": ")",
})


def fraction_part(text):
    text = text.strip()
    return text if re.fullmatch(r"[0-9]+|x", text) else f"({text})"


def normalize_symbols(text):
    return unicodedata.normalize("NFKC", text.translate(SUPERSCRIPTS)).translate(TRANSLATE)


def normalize(text):
    text = normalize_symbols(text)
    text = re.sub(r"\\(?:left|right)(?![a-zA-Z])", "", text)
    text = re.sub(r"\\(?:mathbf|mathrm|mathit|mathnormal|mathsf|mathtt|boldsymbol)\s*\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\(?:quad|qquad)(?![a-zA-Z])|\\[ ,!;:>]|~", "", text)
    for source, target in ((r"\times", "*"), (r"\cdot", "*"), (r"\div", "/")):
        text = text.replace(source, target)
    text = LATEX_FRACTION.sub(
        lambda m: f"{fraction_part(m[1])}/{fraction_part(m[2])}", text
    )
    text = re.sub(r"\\[()[\]]|[$]", "", text)
    text = text.replace("{", "(").replace("}", ")")
    return re.sub(r"\s+", "", text).lower()


def affine(node, expression):
    """Return the exact coefficients (a, b) for an expression ax + b."""
    if isinstance(node, ast.Name) and node.id == "x":
        return Fraction(1), Fraction(0)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(0), Fraction(ast.get_source_segment(expression, node))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        a, b = affine(node.operand, expression)
        return (-a, -b) if isinstance(node.op, ast.USub) else (a, b)
    if isinstance(node, ast.BinOp):
        a, b = affine(node.left, expression)
        c, d = affine(node.right, expression)
        if isinstance(node.op, ast.Add):
            return a + c, b + d
        if isinstance(node.op, ast.Sub):
            return a - c, b - d
        if isinstance(node.op, ast.Mult) and not (a and c):
            return a * d + b * c, b * d
        if isinstance(node.op, ast.Div) and not c and d:
            return a / d, b / d
    raise ValueError("Unsupported equation")


def linear_equation(text):
    equation = re.sub(r"(?<=[0-9])\.$", "", normalize(text))
    if len(equation) > 180 or not re.fullmatch(r"[0-9x().+\-*/]+=[0-9x().+\-*/]+", equation):
        return None
    if "**" in equation or "//" in equation:
        return None
    try:
        coefficients = []
        for side in equation.split("="):
            expression = re.sub(r"(?<=[0-9x)])(?=[x(])", "*", side)
            tree = ast.parse(expression, mode="eval")
            coefficients.append(affine(tree.body, expression))
    except (SyntaxError, ValueError, RecursionError):
        return None
    return equation if coefficients[0][0] != coefficients[1][0] else None


def inspect_problem(text):
    marked = [next(g for g in match.groups() if g is not None) for match in MARKED_MATH.finditer(text)]
    equations = [eq for part in marked if (eq := linear_equation(part))]
    remainder = MARKED_MATH.sub(" ", text)
    if not equations:
        plain = re.sub(r"(?<![0-9])\.(?=[ \t])", " ", normalize_symbols(remainder)).lower()
        equations = [eq for m in PLAIN_EQUATION.finditer(plain) if (eq := linear_equation(m[0]))]
        remainder = PLAIN_EQUATION.sub(" ", plain)
    if not equations and (eq := linear_equation(text)):
        equations, remainder = [eq], ""

    # Recognize a bare equation or a short direct-solve instruction.
    prompt = re.sub(r"\([0-9]+\)|[.!?,:]", "", normalize(remainder))
    direct = bool(equations) and (not prompt or bool(DIRECT_PROMPT.fullmatch(prompt)))
    return tuple(dict.fromkeys(equations)), direct


def load_bank(path, unit):
    if path.is_dir():
        rows = [r for f in sorted(path.glob("m1_s1_u*.json")) for r in json.loads(f.read_text(encoding="utf-8-sig"))]
    elif path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            names = [n for n in archive.namelist() if re.fullmatch(r"m1_s1_u0[1-4]\.json", Path(n).name)]
            rows = [r for n in sorted(names) for r in json.loads(archive.read(n))]
    else:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = [r for r in rows if unit is None or r["unit_code"] == unit]
    if not rows:
        raise ValueError("읽을 문항이 없습니다. 문제은행 경로와 --unit 값을 확인하세요.")
    return rows


def read_tesseract(path, language, executable):
    command = shutil.which(executable)
    if command is None:
        raise ValueError("Tesseract를 찾을 수 없습니다. 설치하거나 --tesseract에 실행 파일 경로를 지정하세요.")
    if not path.is_file():
        raise ValueError(f"사진 파일을 찾을 수 없습니다. {path}")
    result = subprocess.run(
        [command, str(path.resolve()), "stdout", "-l", language, "--psm", "6"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=45,
    )
    if result.returncode != 0:
        raise ValueError(f"사진 인식 실패 ({language}). {result.stderr.strip()}")
    return result.stdout.strip()


def read_pix2tex(path, requested_margin):
    """Use the team's pilot when installed and support upstream pix2tex as well."""
    if not path.is_file():
        raise ValueError(f"사진 파일을 찾을 수 없습니다. {path}")
    try:
        from PIL import Image
        from pix2tex.cli import LatexOCR
    except ImportError as exc:
        raise ValueError(
            "pix2tex를 불러올 수 없습니다. 기존 pix2tex 가상환경의 Python으로 실행하세요. "
            f"상세 오류: {exc}"
        ) from exc

    parameters = inspect.signature(LatexOCR.__call__).parameters
    options = {}
    margin = None
    if "crop_margin" in parameters:
        margin = 20 if requested_margin is None else requested_margin
        options["crop_margin"] = margin
    elif requested_margin is not None:
        raise ValueError("--crop-margin은 딛고에서 수정한 pix2tex 파일럿에서 지원됩니다.")
    if "copy_to_clipboard" in parameters:
        options["copy_to_clipboard"] = False
    with Image.open(path) as source:
        image = source.copy()
    ocr = LatexOCR()
    return ocr(image, **options).strip(), margin


def grams(text):
    return Counter(text[i:i+2] for i in range(len(text)-1))


def similarity(query, candidate, query_length):
    if not query or not candidate:
        return 0.0
    dot = sum(count * candidate.get(pair, 0) for pair, count in query.items())
    candidate_length = math.sqrt(sum(n*n for n in candidate.values()))
    return dot / (query_length * candidate_length)


def topic(row):
    return {key: row[key] for key in ("source_topic_code", "source_topic_name")}


def shape_topic(equation):
    fraction = "/" in equation
    decimal = bool(re.search(r"[0-9]\.[0-9]", equation))
    bracket = not (fraction or decimal) and "(" in equation
    return TOPICS[(fraction, decimal, bracket)]


def classify(text, rows, limit=3, *, equation_only=False):
    normalized = normalize(text)
    if equation_only:
        equation = linear_equation(text)
        query_equations = (equation,) if equation else ()
        direct = bool(query_equations)
    else:
        query_equations, direct = inspect_problem(text)
    exact_text = []
    exact_equation = []
    searchable_equations = {}
    for row in rows:
        body = row["question_text"]
        if normalized and normalize(body) == normalized:
            exact_text.append(row)
        if direct and len(query_equations) == 1 and row["unit_code"] == "03":
            bank_equations, bank_direct = inspect_problem(body)
            if bank_direct:
                searchable_equations[row["id"]] = bank_equations
                if query_equations[0] in bank_equations:
                    exact_equation.append(row)

    suggested = None
    matched_id = None
    if not normalized:
        status = "ocr_empty"
        candidates = []
    elif exact_text or exact_equation:
        hits = exact_text or exact_equation
        basis = "text_exact" if exact_text else "equation_exact"
        codes = {row["source_topic_code"] for row in hits}
        status = basis if len(codes) == 1 else "ambiguous"
        if len(codes) == 1:
            suggested = topic(hits[0])
            matched_id = hits[0]["id"] if len(hits) == 1 else None
        candidates = [(1.0, row) for row in hits[:limit]]
    else:
        if direct and len(query_equations) == 1:
            code = shape_topic(query_equations[0])
            suggested = next((topic(r) for r in rows if r["source_topic_code"] == code), None)
        status = "type_candidate" if suggested else "needs_review"
        query = grams(query_equations[0] if direct and len(query_equations) == 1 else normalized)
        query_length = math.sqrt(sum(n*n for n in query.values()))
        ranking = []
        for row in rows:
            if suggested and row["source_topic_code"] != suggested["source_topic_code"]:
                continue
            body = row["question_text"]
            texts = searchable_equations.get(row["id"]) or [normalize(body)]
            score = max(similarity(query, grams(s), query_length) for s in texts)
            if score:
                ranking.append((score, row))
        ranking.sort(key=lambda item: (-item[0], item[1]["id"]))
        candidates = ranking[:limit]

    return {
        "01_recognized_problem": {"text": text, "linear_equations": list(query_equations)},
        "02_bank_candidates": [
            {"id": r["id"], "question_text": r["question_text"], **topic(r), "similarity": round(s, 4)}
            for s, r in candidates
        ],
        "03_classification": {
            "status": status,
            "matched_problem_id": matched_id,
            "source_topic_code": suggested["source_topic_code"] if suggested else None,
            "source_topic_name": suggested["source_topic_name"] if suggested else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="딛고 사진 인식 및 문제 유형 확인")
    parser.add_argument("--bank", type=Path, default=Path(BANK_NAME), help="문제은행 ZIP, 단원 JSON 또는 압축을 푼 폴더")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--image", type=Path, help="학생이 올린 문제 사진")
    inputs.add_argument("--text", help="인식된 문제 텍스트로 검색만 먼저 시험")
    parser.add_argument("--unit", choices=("01", "02", "03", "04"), help="검색할 단원")
    parser.add_argument("--ocr", choices=("pix2tex", "tesseract"), help="사진 인식 엔진. 기본값은 pix2tex")
    parser.add_argument("--crop-margin", type=int, help="수정한 pix2tex의 여백 픽셀 수. 기본값 20")
    parser.add_argument("--lang", default="kor+eng", help="Tesseract 인식 언어")
    parser.add_argument("--tesseract", help="Tesseract 실행 파일 이름 또는 경로")
    args = parser.parse_args()
    engine = args.ocr or ("tesseract" if args.tesseract else "pix2tex")
    if args.crop_margin is not None and (args.crop_margin < 0 or not args.image or engine != "pix2tex"):
        parser.error("--crop-margin에는 pix2tex 사진 모드에서 0 이상의 정수를 넣으세요.")

    try:
        rows = load_bank(args.bank, args.unit)
        if args.image and engine == "pix2tex":
            latex, margin = read_pix2tex(args.image, args.crop_margin)
            result = classify(latex, rows, equation_only=True)
            result["01_recognized_problem"].update(ocr_engine="pix2tex", crop_margin=margin)
        elif args.image:
            text = read_tesseract(args.image, args.lang, args.tesseract or "tesseract")
            result = classify(text, rows)
            result["01_recognized_problem"]["ocr_engine"] = "tesseract"
        else:
            result = classify(args.text, rows)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, BadZipFile, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"오류: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
