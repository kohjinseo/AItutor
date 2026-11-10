# 한국어 문제 사진에서 일차방정식 풀이까지

## 1. 구현 파일

- `korean_problem_solver.py`: 사진을 Tesseract `kor+eng`로 읽고, 정해진 문장 규칙으로 식을 생성한 다음 기존 `linear_solver.solve_latex()`로 풀이합니다.
- `test_korean_problem_solver.py`: 문장 풀이, 추가 조건 거절, OCR 연결 대역 테스트입니다.
- 기존 pix2tex 및 풀이 파일은 변경하지 않았습니다.

## 2. 먼저 텍스트로 실행

프로젝트 루트에서 SymPy가 설치된 Python으로 실행합니다. pix2tex와 모델 가중치는 이 경로에 필요하지 않습니다.

```powershell
python -m pip install sympy==1.13.1
python .\korean_problem_solver.py --text "어떤 수의 두 배에 3을 더하면 11이다. 그 수를 구하시오."
```

이미 `.venv`에 SymPy가 있다면 `python` 대신 `.\.venv\Scripts\python.exe`를 사용하세요.

출력의 `interpretation`은 어떤 수를 x로 두고 `2x+(3)=11`을 생성한 이유를 보여 줍니다. `solution.answer`는 `x = 4`, `solution.check`는 생성한 식에 대입한 검산 결과입니다. 계산 과정 전체를 자연어로 설명하는 기능은 없습니다.

## 3. 한국어 사진 실행

Tesseract 프로그램과 `kor`, `eng` 언어 데이터가 별도로 필요합니다. Python 패키지만 설치해서는 Tesseract 실행 파일이 생기지 않습니다.

```powershell
tesseract --list-langs
python .\korean_problem_solver.py --image .\problem.png
```

PATH에 없다면 설치 위치를 직접 지정합니다. 다음 경로는 예시이므로 실제 설치 위치와 맞춰 주세요.

```powershell
python .\korean_problem_solver.py --image .\problem.png --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

`--list-langs`에 `kor`와 `eng`가 있어야 합니다. 인쇄된 한 문제만 보이도록 잘라 사용하세요. 분수나 지수 등 복잡한 수식은 이 OCR 경로로 정확하게 복원하지 못할 수 있습니다. 한국어 영역과 수식 영역을 나눠 pix2tex 결과와 합치는 기능은 포함하지 않았습니다.

## 4. 지원 범위

일반 한국어 전체를 이해하는 AI가 아니라 문장 규칙 기반입니다. 외부 API, API 키, 문장 전송은 사용하지 않습니다.

- `어떤 수의 두 배에 3을 더하면 11이다. 그 수를 구하시오.`
- `어떤 수의 세 배에서 5를 빼면 10이다.`
- `어떤 수에 0.2를 더하면 0.3이다.`
- `다음 일차방정식을 풀어라. 2x+3=11`
- 배수는 한~열 또는 숫자 표기이며, 수치는 정수와 소수를 지원합니다.

속력·거리, 나이, 가격, 도형, 여러 조건이 있는 문제와 표현이 다른 문장은 `needs_review`로 반환합니다. 한 문장 속 수치만 임의로 추출해 답을 만들지 않습니다. 지원 표현은 `interpret()`에 규칙을 추가해 확장할 수 있습니다.

`solved`는 생성한 식의 계산이 끝났다는 뜻입니다. 원본 사진의 인식과 문장 해석이 정확하다는 보장은 아니므로 `recognized_text`와 `interpretation.equation`을 원문과 비교하세요.

## 5. 테스트

```powershell
python -m unittest -v test_korean_problem_solver test_linear_solver
```

OCR 연결 테스트는 Tesseract 출력 대역을 사용합니다. 실제 사진 인식 품질은 Tesseract와 한국어 데이터를 설치한 PC에서 확인해야 합니다.
