# 사진에서 일차방정식 풀이까지

기존 `.venv`에서 pix2tex가 실행되는 상태라면 추가로 필요한 패키지는 SymPy입니다.
이 프로젝트의 기존 환경에 있는 SymPy 1.13.1로 검증했습니다.
VS Code PowerShell에서 프로젝트 폴더를 연 다음 실행하세요.

```powershell
.\.venv\Scripts\python.exe -m pip install sympy==1.13.1
$env:NO_ALBUMENTATIONS_UPDATE = "1"
.\.venv\Scripts\python.exe compare_crop.py .\my_equation.png --margin 20 --solve
```

`--solve`를 빼면 종전처럼 OCR 비교 결과만 나옵니다. `--margin`과 `--expected`도
그대로 사용할 수 있습니다. `--expected`는 공백을 제외한 **LaTeX 문자열** 비교이며,
수학적으로 같은 식인지 판정하는 옵션은 아닙니다.

## 코드를 읽는 순서

1. `compare_crop.py`의 `main()`이 사진을 열고 동일한 난수 설정으로 여백 0과
   지정된 여백의 OCR을 실행합니다. `--solve`일 때만 `solve_latex()`를 가져와
   각 결과의 `solution`에 넣습니다. 원래 `latex`와 `needs_review` 계산은 유지합니다.
2. `linear_solver.py`의 `_select_equation()`이 일반 수식 또는 `array`를 처리합니다.
   표라면 등호가 있는 칸이 정확히 하나여야 합니다. 선택하지 않은 칸의 원문은
   `other_array_cells`에 보존합니다. 여러 방정식이 있거나 등호 양쪽이 다른 칸에
   나뉘어 있으면 임의로 합치거나 선택하지 않습니다.
3. `_normalize_latex()`가 알려진 글꼴·간격 명령과 중괄호를 정리합니다.
   `_tokenize()`와 `_Parser`가 숫자, `x`, `+`, `-`, `*`, 괄호만 읽습니다.
   등호는 양변을 나누는 데만 사용합니다. OCR 문자열에 `eval`, `sympify`,
   `parse_expr`를 적용하지 않습니다. 허용하지 않은 문자·명령은 거절합니다.
4. `_Parser.term()`이 `2x`, `1.2(x+2)`, `(2+3)x`처럼 생략된 곱셈을 처리합니다.
   숫자 토큰을 `SymPy.Rational`로 바꾸므로 소수를 이진 부동소수점으로 계산하지 않습니다.
5. `solve_latex()`가 양변의 차수가 1 이하인지 확인하고 SymPy `solveset()`으로
   실수 범위의 해를 구합니다. 유일한 해가 있으면 정리하기 전 양변의 SymPy 식에
   각각 대입해 비교합니다. `_format_rational()`은 유한소수는 정확한 소수로,
   그 외에는 `1/3` 같은 분수로 표시합니다.

지원 범위는 `x` 하나를 포함하는 일차방정식, 정수·소수·괄호·덧셈·뺄셈·곱셈입니다.
분수 입력, 나눗셈, 지수, 함수, 다른 미지수는 이번 범위에 포함하지 않습니다.
계산 결과가 분수인 경우는 지원합니다. 너무 길거나 중첩이 깊은 입력도 거절합니다.

## 출력 읽기

실제 사진에서 나온 아래 LaTeX를 직접 검증하는 테스트가 포함되어 있습니다.

```latex
\begin{array}{r l}{{\dot{\alpha}}{\mit\Psi}_{*}\ }&{{}{}1.2(x+2)=0.8(3-x)}\end{array}
```

이때 `solution`의 핵심 출력은 다음과 같습니다.

```json
{
  "equation": "1.2(x+2) = 0.8(3-x)",
  "status": "solved",
  "answer": "x = 0",
  "check": {
    "lhs": "2.4",
    "rhs": "2.4",
    "matches": true,
    "basis": "ocr_equation"
  },
  "other_array_cells": ["{{\\dot{\\alpha}}{\\mit\\Psi}_{*}\\ }"]
}
```

정확한 수치를 유지하기 위해 `answer`, `check.lhs`, `check.rhs`의 숫자는 문자열입니다.
`check.matches`는 JSON 불리언입니다.

| status | 의미 | check |
| --- | --- | --- |
| `solved` | 유일한 실수 해를 구함 | 양변에 해를 대입한 값과 일치 여부 |
| `no_solution` | 해가 없음 | `null` |
| `infinite_solutions` | 모든 실수가 해 | `null` |
| `unsupported` | 지원 범위 밖이거나 해석할 수 없음 | `null`, `reason`에 이유 |

검산은 **OCR로 읽은 식**에 대한 확인입니다. 사진을 잘못 읽어도 그 잘못 읽은 식의
검산은 통과할 수 있습니다. `check.basis`가 이를 표시하며, 검산 결과로
`needs_review`나 `matches_reference`를 바꾸지 않습니다. 두 OCR 문자열이 다르면
둘 다 같은 답을 얻더라도 기존처럼 `needs_review: true`입니다.

## 확인 명령

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_linear_solver
.\.venv\Scripts\python.exe compare_crop.py .\pilot_examples\clean_equation.png --margin 20 --solve
.\.venv\Scripts\python.exe compare_crop.py .\pilot_examples\clear_minus.png --margin 20 --solve
.\.venv\Scripts\python.exe compare_crop.py .\pilot_examples\faint_minus.png --margin 20 --solve
.\.venv\Scripts\python.exe compare_crop.py .\my_equation.png --margin 20
```

테스트에는 제공된 LaTeX와 기존 `result.json`의 두 OCR 결과를 복사한 고정 예시,
소수의 정확한 계산, 생략된 곱셈, 해 없음·무수히 많은 해, 모호한 표,
잘못된 괄호와 코드 실행 형태의 입력 거절이 포함됩니다.

기존 Windows `.venv`에서 실제 실행해 확인한 결과입니다. 단위 테스트 6개와
각 테스트 안의 여러 입력 사례도 모두 통과했습니다.

| 사진 | original의 답 | modified의 답 | 검산 |
| --- | --- | --- | --- |
| `my_equation.png` | `x = 0` | `x = 0` | 둘 다 `2.4 = 2.4` |
| `pilot_examples/clean_equation.png` | `x = 4` | `x = 4` | 둘 다 `11 = 11` |
| `pilot_examples/clear_minus.png` | `x = -4` | `x = -4` | 둘 다 `11 = 11` |
| `pilot_examples/faint_minus.png` | `x = 4` | `x = -4` | 둘 다 `11 = 11` |

4장 모두 `--solve`를 넣은 실행과 뺀 실행을 비교했습니다. 실행 시간은 매번 달라지지만,
기존 `latex`, `crop_margin`, `needs_review`는 같았고, 샘플의 `--expected` 비교도
유지되었습니다. 흐린 마이너스 샘플은 수정 전 실행에서 기록한 OCR 문자열과도 같았습니다.
이번 실행에서는 4장 모두 원래 LaTeX 문자열에 차이가 있어 `needs_review: true`였습니다.
깨끗한 샘플과 선명한 마이너스 샘플은 글꼴 명령 차이로 표시되었고,
실제 사진은 방정식 왼쪽의 문제 번호 칸이 다르게 인식되었습니다.
