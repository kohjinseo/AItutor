"""Solve a deliberately small, allowlisted subset of OCR LaTeX without eval."""

import re

import sympy as sp


_X = sp.Symbol("x", real=True)
_MAX_LENGTH = 4096
_MAX_TOKENS = 512
_MAX_DEPTH = 48
_NUMBER = r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
_TOKEN = re.compile(rf"{_NUMBER}|[x+*()=-]")
_COMMAND = re.compile(r"\\([A-Za-z]+|.)", re.DOTALL)
_FORMATTING = {"mathbf", "mathsf", "mathrm", "mathit", "mathtt", "boldsymbol"}
_SPACING = {",", ";", ":", "!", " ", "quad", "qquad", "enspace", "thinspace"}


class UnsupportedEquation(ValueError):
    """The OCR output is outside the supported grammar."""


def _unwrap(text, opening, closing):
    """Remove only groups that enclose the entire input."""
    text = text.strip()
    while text.startswith(opening) and text.endswith(closing):
        depth = 0
        for index, char in enumerate(text):
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
            if depth == 0:
                break
        if index != len(text) - 1:
            break
        text = text[1:-1].strip()
    return text


def _select_equation(latex):
    """Select one equation cell; never join cells into an invented equation."""
    text = latex.strip()
    for opening, closing in (("$$", "$$"), ("$", "$"), (r"\[", r"\]"), (r"\(", r"\)")):
        if text.startswith(opening) and text.endswith(closing):
            text = text[len(opening):-len(closing)].strip()
            break
    text = _unwrap(text, "{", "}")
    if not text.startswith(r"\begin{array}"):
        return text, None
    match = re.fullmatch(
        r"\\begin\{array\}\{[lcr|\s]+\}(.*?)\\end\{array\}", text, re.DOTALL
    )
    if not match:
        raise UnsupportedEquation("지원하지 않거나 닫히지 않은 array 구조입니다.")
    body = match.group(1)
    cells = []
    depth = 0
    start = index = 0
    while index < len(body):
        char = body[index]
        if char == "{":
            depth += 1
            if depth > _MAX_DEPTH:
                raise UnsupportedEquation("중괄호 중첩이 너무 깊습니다.")
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise UnsupportedEquation("array의 중괄호 짝이 맞지 않습니다.")
        separator = depth == 0 and (char == "&" or body.startswith(r"\\", index))
        if separator:
            cells.append(body[start:index].strip())
            index += 2 if body.startswith(r"\\", index) else 1
            start = index
        else:
            index += 1
    if depth:
        raise UnsupportedEquation("array의 중괄호 짝이 맞지 않습니다.")
    cells.append(body[start:].strip())
    candidates = [index for index, cell in enumerate(cells) if "=" in cell]
    if len(candidates) != 1:
        # Keep every cell when there is no unambiguous selection.
        return None, cells
    selected = candidates[0]
    return cells[selected], [cell for index, cell in enumerate(cells) if index != selected]


def _normalize_latex(text):
    """Allow known presentation commands and preserve mathematical grouping."""
    def replace_command(match):
        command = match.group(1)
        if command in _FORMATTING:
            if not text[match.end():].lstrip().startswith("{"):
                raise UnsupportedEquation("글꼴 명령 뒤에는 중괄호가 필요합니다.")
            return " "
        if command in _SPACING or command in {"left", "right"}:
            return " "
        if command in {"times", "cdot"}:
            return "*"
        raise UnsupportedEquation(f"지원하지 않는 LaTeX 명령입니다: \\{command}")

    text = text.replace("−", "-").replace("×", "*").replace("·", "*")
    text = _COMMAND.sub(replace_command, text)
    # Empty OCR groups are presentation placeholders, not operands.
    for _ in range(_MAX_DEPTH + 1):
        reduced = re.sub(r"\{\s*\}", " ", text)
        if reduced == text:
            break
        text = reduced
    text = _unwrap(text, "{", "}")

    def group(start, depth):
        if depth > _MAX_DEPTH:
            raise UnsupportedEquation("중괄호 중첩이 너무 깊습니다.")
        parts = []
        index = start
        while index < len(text):
            char = text[index]
            if char == "{":
                inside, index = group(index + 1, depth + 1)
                inside = inside.strip()
                if re.fullmatch(rf"{_NUMBER}|x", inside):
                    # Spaces prevent {1}{2} or 1{.2} from silently becoming 12 or 1.2.
                    parts.append(f" {inside} ")
                else:
                    parts.append(f"({inside})")
            elif char == "}":
                if depth == 0:
                    raise UnsupportedEquation("중괄호 짝이 맞지 않습니다.")
                return "".join(parts), index + 1
            else:
                parts.append(char)
                index += 1
        if depth:
            raise UnsupportedEquation("중괄호 짝이 맞지 않습니다.")
        return "".join(parts), index

    return _unwrap(group(0, 0)[0], "(", ")")


def _tokenize(text):
    tokens = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise UnsupportedEquation(f"허용하지 않는 수식 문자입니다: {text[index]!r}")
        token = match.group()
        if len(token) > 100:
            raise UnsupportedEquation("숫자가 너무 깁니다.")
        tokens.append(token)
        if len(tokens) > _MAX_TOKENS:
            raise UnsupportedEquation("수식 토큰이 너무 많습니다.")
        index = match.end()
    return tokens


class _Parser:
    """Recursive descent: addition, multiplication, unary signs, and atoms only."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def expression(self, depth=0):
        value = self.term(depth)
        while self.peek() in ("+", "-"):
            operator = self.peek()
            self.index += 1
            right = self.term(depth)
            value = value + right if operator == "+" else value - right
        return value

    def term(self, depth):
        value = self.unary(depth)
        while self.peek() == "*" or self.peek() in ("x", "("):
            if self.peek() == "*":
                self.index += 1
            value *= self.unary(depth)
        return value

    def unary(self, depth):
        if depth > _MAX_DEPTH:
            raise UnsupportedEquation("괄호 또는 부호 중첩이 너무 깊습니다.")
        token = self.peek()
        if token in ("+", "-"):
            self.index += 1
            value = self.unary(depth + 1)
            return value if token == "+" else -value
        if token == "(":
            self.index += 1
            value = self.expression(depth + 1)
            if self.peek() != ")":
                raise UnsupportedEquation("괄호 짝이 맞지 않습니다.")
            self.index += 1
            return value
        if token == "x":
            self.index += 1
            return _X
        if token is not None and re.fullmatch(_NUMBER, token):
            self.index += 1
            return sp.Rational(token)
        raise UnsupportedEquation("숫자, x 또는 괄호가 필요한 위치에 다른 토큰이 있습니다.")

    def parse(self):
        value = self.expression()
        if self.peek() is not None:
            raise UnsupportedEquation("연산자가 없거나 지원하지 않는 토큰 배열입니다.")
        return value


def _format_rational(value):
    """Print terminating decimals exactly; retain fractions otherwise."""
    numerator, denominator = map(int, value.as_numer_denom())
    rest = denominator
    twos = fives = 0
    while rest % 2 == 0:
        rest //= 2
        twos += 1
    while rest % 5 == 0:
        rest //= 5
        fives += 1
    if rest != 1:
        return f"{numerator}/{denominator}"
    digits = max(twos, fives)
    if not digits:
        return str(numerator)
    scaled = abs(numerator) * 2 ** (digits - twos) * 5 ** (digits - fives)
    text = str(scaled).zfill(digits + 1)
    return ("-" if numerator < 0 else "") + (text[:-digits] + "." + text[-digits:]).rstrip("0").rstrip(".")


def solve_latex(latex):
    """Return a JSON-ready solution; verification applies only to the OCR equation.

    Status is solved, no_solution, infinite_solutions, or unsupported.
    Exact numerical output uses strings so JSON floats cannot introduce rounding.
    """
    result = {"equation": None, "status": "unsupported", "answer": None, "check": None}
    try:
        if not isinstance(latex, str) or not latex.strip():
            raise UnsupportedEquation("OCR 결과가 비어 있거나 문자열이 아닙니다.")
        if len(latex) > _MAX_LENGTH:
            raise UnsupportedEquation("OCR 문자열이 너무 깁니다.")
        selected, other_cells = _select_equation(latex)
        if other_cells is not None:
            result["other_array_cells"] = other_cells
        if selected is None:
            raise UnsupportedEquation("등호가 있는 array 칸이 정확히 하나여야 합니다. 칸을 합치거나 임의로 고르지 않습니다.")
        tokens = _tokenize(_normalize_latex(selected))
        if tokens.count("=") != 1:
            raise UnsupportedEquation("완성된 방정식에는 등호가 정확히 하나 필요합니다.")
        split = tokens.index("=")
        left_tokens, right_tokens = tokens[:split], tokens[split + 1:]
        lhs = _Parser(left_tokens).parse()
        rhs = _Parser(right_tokens).parse()
        result["equation"] = "".join(left_tokens) + " = " + "".join(right_tokens)
        if "x" not in tokens:
            raise UnsupportedEquation("미지수 x가 포함된 방정식만 지원합니다.")
        if any(sp.Poly(side, _X).degree() > 1 for side in (lhs, rhs)):
            raise UnsupportedEquation("각 변이 x에 대한 일차식이어야 합니다. 이차 이상의 식은 지원하지 않습니다.")
        solutions = sp.solveset(lhs - rhs, _X, domain=sp.S.Reals)
        if solutions is sp.S.EmptySet:
            result.update(status="no_solution", answer="해 없음", reason="양변을 정리하면 모순이 됩니다.")
        elif solutions is sp.S.Reals:
            result.update(status="infinite_solutions", answer="모든 실수 x", reason="양변을 정리하면 항상 같은 식입니다.")
        else:
            value, = solutions
            left_value, right_value = lhs.subs(_X, value), rhs.subs(_X, value)
            result.update(
                status="solved",
                answer="x = " + _format_rational(value),
                check={
                    "lhs": _format_rational(left_value),
                    "rhs": _format_rational(right_value),
                    "matches": bool(left_value == right_value),
                    "basis": "ocr_equation",
                },
            )
    except UnsupportedEquation as error:
        result["reason"] = str(error)
    return result
