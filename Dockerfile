# 적정월세 — Google Cloud Run 배포용 (React 화면 + FastAPI 서버를 한 컨테이너로)
# 1단계: React 화면 빌드 → web/dist
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2단계: 파이썬 서버 (LightGBM은 libgomp1이 필요 — Streamlit 때 packages.txt와 같은 이유)
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY app/rent_core.py app/listing_parser.py app/
COPY app/data app/data
COPY api api
COPY --from=web /web/dist web/dist
# Cloud Run이 PORT 환경변수(기본 8080)로 포트를 알려준다
ENV PORT=8080
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
