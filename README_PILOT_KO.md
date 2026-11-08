# 토크라테스 AI 수식 인식 파일럿

사진에서 수식 한 줄을 읽는 오픈소스 pix2tex의 이미지 전처리를 수정했다. 원본은 [LaTeX-OCR](https://github.com/lukas-blecher/LaTeX-OCR)의 커밋 `5c1ac929bd19a7ecf86d5fb8d94771c8969fcb80`이다. 모델 가중치는 공식 릴리스의 `v0.0.1`을 사용했다.

## 우리가 바꾼 코드

| 파일 | 변경 내용 |
| --- | --- |
| `pix2tex/utils/utils.py` | `pad()`가 진한 픽셀로 수식의 경계를 찾은 다음, `crop_margin`만큼 경계를 넓혀 그 주변 픽셀을 함께 남긴다. 이미지 가장자리에서는 범위를 이미지 크기 안으로 제한한다. 기본값은 `0`이다. |
| `pix2tex/cli.py` | `LatexOCR`에서 옵션을 받아 첫 전처리와 이후 크기 조절 경로의 잘라내기에 전달한다. 비교 중에는 클립보드 복사를 끌 수 있다. |
| `compare_crop.py` | 같은 사진을 같은 CPU 모델과 초기 난수 설정으로 읽는다. 기존 여백 `0`과 지정한 여백의 LaTeX, 실행 시간, 결과 차이를 출력한다. |
| `upstream_changes.patch` | 오픈소스 원본에서 바꾼 부분을 한 파일에서 확인할 수 있다. |

수식 왼쪽의 마이너스가 흐리면 기존 알고리즘이 잡은 경계 바깥으로 빠질 수 있다. 넓어진 경계 안에 있으면 그 픽셀이 첫 전처리 후에도 남는다. 모델에 전달되는 입력이 바뀌므로 잘려 나갔던 기호를 읽을 기회가 생긴다.

## CPU 실험 결과

Python 3.12와 PyTorch CPU로 직접 만든 수식 이미지 3장을 비교했다. 아래 표는 LaTeX의 글꼴 표기를 제외한 수식 내용이다.

| 입력 | 기존 처리 0픽셀 | 수정 처리 20픽셀 |
| --- | --- | --- |
| 마이너스 없는 수식 | `2x+3=11` | `2x+3=11` |
| 선명한 마이너스가 있는 수식 | `-2x+3=11` | `-2x+3=11` |
| 흐린 마이너스가 있는 수식 | `2x+3=11` | `-2x+3=11` |

흐린 이미지에서 마이너스 색과 같은 픽셀 39개가 20픽셀 설정의 첫 전처리 후에 남았다. 기존 처리 후에는 0개였다. 또 세 이미지 모두에서 수정 코드의 기본값 `0`이 원본 코드와 픽셀 단위로 같은 전처리 결과를 냈다.

20픽셀은 이 예시들에서 여백을 바꿔 보며 정한 실험용 값이다. 같은 흐린 사진에 24픽셀을 적용했을 때는 `-2x+3=111`이 나왔다. 실제 촬영 이미지와 다양한 해상도에서의 정확도는 별도로 평가해야 한다.

## Windows PowerShell에서 실행

압축을 풀고 VS Code에서 `pix2tex_margin_pilot` 폴더를 연다. 터미널에서 `compare_crop.py`가 보이는 폴더에서 다음을 실행한다. Python 3.12를 기준으로 작성했다. 실제 CPU 검증 환경은 Linux다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1
.\.venv\Scripts\python.exe -m pip install -e . numpy==1.26.4 opencv-python-headless==4.11.0.86 transformers==4.46.3 pandas==2.2.3 albumentations==1.4.24 Pillow==11.3.0
$env:NO_ALBUMENTATIONS_UPDATE = "1"
.\.venv\Scripts\python.exe compare_crop.py pilot_examples/faint_minus.png --margin 20
```

처음 실행할 때는 공식 모델 파일 2개를 내려받으므로 인터넷이 필요하다. 이후 사진 인식은 PC의 CPU에서 실행된다. 압축 파일에는 모델 가중치가 포함되어 있지 않다.

직접 찍은 사진은 수식 한 줄 주변을 잘라 `my_equation.png`로 저장하고 다음처럼 비교한다. 비교하려는 흐린 기호가 사진 안에 남아 있어야 한다.

```powershell
.\.venv\Scripts\python.exe compare_crop.py my_equation.png --margin 20
```

- `latex`는 모델이 읽은 수식이다. 예를 들어 `\mathbf{x}`는 굵은 글씨로 표시된 `x`다.
- `needs_review`가 `true`이면 결과가 비어 있거나 두 출력이 다르다. 두 결과가 같아도 정확하다고 판정할 수 없으며, LaTeX 글꼴 표기만 달라도 이 값은 `true`가 될 수 있다.
- `--expected=-2x+3=11`을 붙이면 공백을 제외한 LaTeX 문자열을 그대로 비교한다. 수학적으로 동일해도 표기가 다르면 `matches_reference`는 `false`다.

이 파일럿의 입력은 수식이 잘려 있는 이미지 한 장이다. 한국어 문제 본문 인식, 도형 속 외각·내각 판별, 풀이 및 학습 경로 결정은 각각 별도 기능으로 설계해야 한다.
