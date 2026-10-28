# React 화면 실행과 Google Cloud Run 배포 (2026-10-28)

교수님 피드백("Streamlit은 일반 사용자 서비스에 안 맞음 → React + 구글 클라우드")에 따라 화면을 React로 옮겼다.
**계산 코드는 하나도 바꾸지 않았다.** `app/rent_core.py`를 FastAPI 서버가 그대로 불러 쓴다.

```
[브라우저: React 화면 web/] ──/api/...──▶ [FastAPI 서버 api/main.py] ──▶ app/rent_core.py, app/listing_parser.py
         북마크는 브라우저 저장(localStorage)        서버가 켜질 때 데이터 정제 + 모델 학습 (약 3~5초)
```

## 1. 내 컴퓨터에서 실행

준비물: Python 3.13, Node.js 22 (확인: `python --version`, `node -v`)

```bash
# 터미널 1 — API 서버 (저장소 맨 위 폴더에서)
pip install -r api/requirements.txt
python -m uvicorn api.main:app --reload --port 8000
# → http://localhost:8000/docs 에서 API를 화면으로 시험할 수 있음

# 터미널 2 — React 화면
cd web
npm install          # 처음 한 번만
npm run dev          # → http://localhost:5173 접속
```

**나와야 하는 결과:** 5173 화면 위쪽에 "인천 미추홀구 · 실거래 4,312건 · 2023.10~2026.09"가 보이면 서버와 연결된 것.

**흔한 에러**
| 증상 | 원인 | 해결 |
|---|---|---|
| 화면에 "서버에 연결하지 못했어요" | 터미널 1(API)을 안 켰거나 8000이 아닌 포트로 켬 | 터미널 1 명령을 그대로 실행 |
| `ModuleNotFoundError: rent_core` | `api/` 폴더 안에서 실행함 | 저장소 **맨 위 폴더**에서 `python -m uvicorn api.main:app` |
| `OSError: libgomp.so.1` (리눅스/맥) | LightGBM이 쓰는 라이브러리 없음 | 리눅스 `sudo apt install libgomp1`, 맥 `brew install libomp` |
| `npm` 명령 없음 | Node.js 미설치 | nodejs.org에서 LTS 설치 |

시험: 저장소 맨 위에서 `pip install pytest httpx` 후 `python -m pytest tests -q` → `12 passed`

## 2. Google Cloud Run 배포

화면(React 빌드 결과)과 API를 **컨테이너 하나**로 묶어 올린다(`Dockerfile`). 주소가 하나라 CORS 설정이 필요 없다.

> 계정 로그인, 결제 계정(카드) 등록, 프로젝트 만들기는 **본인이 직접** 해야 한다.
> 무료 사용량·요금은 바뀔 수 있으니 반드시 공식 문서(cloud.google.com/run/pricing)에서 확인할 것. 확실하지 않은 숫자는 여기 적지 않았다.

```bash
# 0) gcloud 설치: cloud.google.com/sdk/docs/install (설치 후 터미널 새로 열기)
gcloud auth login                                  # 브라우저에서 본인이 로그인
gcloud config set project <내-프로젝트-ID>          # 콘솔에서 만든 프로젝트 ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# 1) 저장소 맨 위 폴더에서 배포 (Dockerfile로 클라우드에서 빌드됨, 처음엔 5~10분)
gcloud run deploy fair-rent --source . --region asia-northeast3 --allow-unauthenticated --memory 1Gi
```

- `asia-northeast3` = 서울 리전
- `--allow-unauthenticated` = 로그인 없이 누구나 접속 (시연용)
- 끝나면 `Service URL: https://fair-rent-....run.app` 이 나온다 → 그 주소가 서비스 주소

**끄기/지우기:** Cloud Run은 접속이 없으면 실행 중인 서버 수가 0으로 줄어든다(기본값). 완전히 지우려면
`gcloud run services delete fair-rent --region asia-northeast3`. 빌드된 이미지는 Artifact Registry에 남으니 콘솔에서 함께 지운다.

**흔한 에러**
| 증상 | 원인 | 해결 |
|---|---|---|
| `Billing account ... not found` | 결제 계정 미연결 | 콘솔 → 결제 → 프로젝트에 결제 계정 연결 |
| 배포 후 `Container failed to start` | 메모리 부족 또는 시작 시간 초과 | `--memory 1Gi` 확인, 콘솔 로그에서 에러 확인 |
| 첫 접속이 몇 초 느림 | 서버 수 0에서 새로 켜지며 모델 학습 | 정상. 시연 직전에 한 번 접속해 두기 |

## 3. Streamlit은?

`app/app.py`는 **내부 검증용**으로 남긴다(같은 rent_core를 쓰므로 숫자가 같아야 함). Streamlit Community Cloud 배포는 Cloud Run이 뜨면 내린다.

## 교수님이 물어보실 만한 질문

**Q1. 왜 앱(React Native)이 아니라 웹인가요?**
남은 기간에 앱 빌드와 스토어 배포까지는 어렵습니다. 대신 휴대폰 화면에서도 깨지지 않게 만들었고, 방을 비교할 때는 PC로 보는 경우가 많아 PC 붙여넣기 흐름을 먼저 만들었습니다.

**Q2. 화면과 서버를 왜 나눴나요?**
모델 계산은 파이썬(LightGBM)에 그대로 두고 화면만 바꾸려고요. API로 나눠 두면 나중에 앱을 만들어도 같은 서버를 씁니다. 계산 규칙이 한 곳(rent_core.py)에만 있어서 화면마다 결과가 달라질 일도 없습니다.

**Q3. 북마크를 왜 서버에 저장하지 않나요?**
서버에 저장하려면 회원가입·로그인과 개인정보 관리가 필요합니다. 비교 기능의 목적에는 내 브라우저 저장으로 충분하고, 사용자가 본 매물 정보를 서버에 남기지 않는 쪽이 안전합니다. 대신 기기를 바꾸면 보이지 않는 한계가 있습니다.
