"""
적정월세 API 서버 (FastAPI) — React 화면이 부르는 계산 서버
실행:  (저장소 맨 위 폴더에서)  python -m uvicorn api.main:app --reload --port 8000
문서:  http://localhost:8000/docs  (주소별 입력·출력을 화면에서 바로 시험할 수 있음)

원칙
- 계산은 app/rent_core.py, 붙여넣기는 app/listing_parser.py를 그대로 쓴다 (Streamlit과 결과가 같아야 함).
- 이 파일은 '입력 받기 → rent_core 부르기 → JSON으로 돌려주기'만 한다.
- web/dist(React 빌드 결과)가 있으면 같은 서버에서 화면도 같이 보낸다 → Cloud Run 서비스 하나로 배포.
"""
import math
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import rent_core as rc                                   # noqa: E402
from listing_parser import parse_listing, check_scope    # noqa: E402

DATA = ROOT / "app" / "data"
KINDS = ["단독다가구", "연립다세대", "오피스텔"]
S = {}   # 서버가 켜질 때 한 번 만든 데이터·모델을 담아 두는 곳


def load_all():
    """app.py의 load_all과 같은 순서 (데이터 정제 → 성적표 → 서비스용 모델 학습)"""
    raw = pd.read_csv(DATA / "raw_3년.csv", dtype=str)
    data, log = rc.clean(raw)
    score, period = rc.evaluate(data)
    model = rc.RentModel().fit(data)
    train_b = rc.add_bins(data)
    tables = rc.build_tables(train_b)
    bld = rc.load_buildings(DATA / "건물정보_정리.csv")
    data_bld = rc.attach_buildings(data, bld)
    bscore = rc.evaluate_building(data_bld)
    bmodel = rc.BuildingModel().fit(data_bld)
    conv = rc.load_conv(DATA / "전환율_인천.csv")
    S.update(data=data, log=log, score=score, period=period, model=model, train_b=train_b, tables=tables,
             bld=bld, bscore=bscore, bmodel=bmodel, conv=conv,
             dongs=data["동"].value_counts().index.tolist())


@asynccontextmanager
async def lifespan(app):
    load_all()
    yield


app = FastAPI(title="적정월세 API", version="1.0", lifespan=lifespan)

# 개발할 때 React(5173포트)에서 부를 수 있게. 배포 때는 같은 주소라 필요 없음
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])


def clean_json(x):
    """NaN·numpy 숫자를 JSON으로 보낼 수 있는 값으로 바꾼다"""
    if isinstance(x, dict):
        return {k: clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(x) else round(float(x), 4)
    if isinstance(x, pd.Timestamp):
        return x.strftime("%Y-%m-%d")
    if isinstance(x, np.bool_):
        return bool(x)
    return x


# ---------------------------------------------------------------
# 입력 형식 (잘못된 값은 FastAPI가 422 에러로 알려줌)
# ---------------------------------------------------------------
class ParseIn(BaseModel):
    text: str = Field(..., max_length=5000)


class DiagnoseIn(BaseModel):
    dong: str
    kind: str
    area: float = Field(..., ge=8, le=33)
    deposit: int = Field(..., ge=0, le=20000)
    rent: int = Field(..., ge=1, le=200)
    floor: Optional[int] = Field(None, ge=-1, le=60)
    build_year: Optional[int] = Field(None, ge=1960, le=2030)
    jibun: Optional[str] = Field(None, max_length=20)


class ConvertIn(BaseModel):
    kind: str
    rent: int = Field(..., ge=1, le=200)
    deposit: int = Field(..., ge=0, le=20000)
    new_deposit: int = Field(..., ge=0, le=20000)


class RecommendIn(BaseModel):
    max_deposit: int = Field(..., ge=0, le=20000)
    max_rent: int = Field(..., ge=10, le=150)
    min_area: float = Field(0, ge=0, le=33)
    kinds: list[str] = KINDS


def check_dong_kind(dong=None, kind=None):
    if dong is not None and dong not in S["dongs"]:
        raise HTTPException(400, f"'{dong}'은 학습 데이터에 없는 동이에요. 가능한 동: {', '.join(S['dongs'])}")
    if kind is not None and kind not in KINDS:
        raise HTTPException(400, f"주택 유형은 {', '.join(KINDS)} 중 하나여야 해요.")


# ---------------------------------------------------------------
# 주소(엔드포인트)
# ---------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": "data" in S}


@app.get("/api/meta")
def meta():
    """화면을 그리기 전에 필요한 기본 정보 (동 목록, 데이터 기간, 고정값)"""
    d = S["data"]
    return clean_json({
        "dongs": S["dongs"], "kinds": KINDS, "n": len(d),
        "date_from": d["계약일"].min().strftime("%Y.%m"), "date_to": d["계약일"].max().strftime("%Y.%m"),
        "bait_ratio": rc.BAIT_RATIO, "bait_dep_max": rc.BAIT_DEP_MAX, "warn_n": rc.WARN_N,
        "base_rate": rc.BASE_RATE, "legal_cap": rc.LEGAL_CAP, "small_dep_diff": rc.SMALL_DEP_DIFF,
        "rec_months": rc.REC_MONTHS, "conv": S["conv"],
    })


@app.post("/api/parse")
def parse(inp: ParseIn):
    """직방 붙여넣기 글자 → 진단 입력값"""
    p = parse_listing(inp.text)
    p["warnings"] = p["warnings"] + check_scope(p["values"], S["dongs"])
    return p


@app.post("/api/diagnose")
def diagnose(inp: DiagnoseIn):
    check_dong_kind(inp.dong, inp.kind)
    r = rc.diagnose(S["model"], S["train_b"], S["tables"], inp.dong, inp.kind, inp.area, inp.deposit, inp.rent,
                    floor=inp.floor or None, build_year=inp.build_year, jibun=inp.jibun,
                    bmodel=S["bmodel"], bld=S["bld"])
    same = r["same"]
    notices = []                    # app.py 오른쪽 안내 문구와 같은 규칙
    if not r["bait"] and inp.deposit > rc.BAIT_DEP_MAX:
        notices.append(("info", "보증금 3,000만 원 초과(반전세)는 거래가 적어 미끼매물 경고를 하지 않아요."))
    if r["n"] < rc.WARN_N:
        notices.append(("warn", f"근거가 부족해요. 비슷한 실제 계약이 {r['n']}건뿐이라 참고만 하세요."))
    if r["jibun_status"] == "found":
        b = r["building"]
        parts = [f"지상 {b['지상층수']:.0f}층"]
        if not pd.isna(b["승강기수"]):
            parts.append("승강기 있음" if b["승강기수"] > 0 else "승강기 없음")
        if not pd.isna(b["세대수"]):
            parts.append(f"{b['세대수']:.0f}세대")
        extra = " 건축년도는 대장의 사용승인연도로 채웠어요." if r["by_from_ledger"] else ""
        notices.append(("info", f"건축물대장 정보를 반영했어요 ({' · '.join(parts)}).{extra}"))
    elif r["jibun_status"] == "notfound":
        notices.append(("info", f"지번 {r['jibun']}의 건물을 건축물대장 목록에서 찾지 못해 기본 방식으로 계산했어요."))
    if not r["know_build_year"]:
        notices.append(("info", "건축년도를 넣으면 평균 오차가 약 5.0만 원 → 4.5만 원으로 줄어요."))
    if inp.kind == "단독다가구" and inp.floor:
        notices.append(("info", "단독다가구는 실거래 데이터에 층이 없어 층은 반영되지 않았어요."))

    cols = ["계약일", "동", "유형", "면적", "층", "건축년도", "보증금", "월세"]
    return clean_json({
        "signal": r["signal"], "lo": r["lo"], "mid": r["mid"], "hi": r["hi"],
        "bait": r["bait"], "bait_cut": r["bait_cut"],
        "pct": r["pct"], "n": r["n"], "level": r["level"],
        "know_build_year": r["know_build_year"], "used_building": r["jibun_status"] == "found",
        "notices": [{"kind": k, "text": t} for k, t in notices],
        "same_rents": same["월세"].tolist(),                       # 분포 그림용
        "comparables": same[cols].head(20).to_dict("records"),     # 근거 거래 최근 20건
    })


@app.post("/api/convert")
def convert(inp: ConvertIn):
    """보증금을 바꿨을 때 월세 (부동산원 전환율 + 법정 상한 참고)"""
    check_dong_kind(kind=inp.kind)
    c = S["conv"][inp.kind]
    return clean_json({
        "market_rate": c["전환율"], "market_rent": rc.convert_rent(inp.rent, inp.deposit, inp.new_deposit, c["전환율"]),
        "legal_rate": rc.LEGAL_CAP, "legal_rent": rc.convert_rent(inp.rent, inp.deposit, inp.new_deposit, rc.LEGAL_CAP),
        "source": c["출처"], "base_month": c["기준월"], "base_rate": rc.BASE_RATE,
        "small_diff": 0 < abs(inp.new_deposit - inp.deposit) < rc.SMALL_DEP_DIFF,
    })


@app.post("/api/recommend")
def recommend(inp: RecommendIn):
    for k in inp.kinds:
        check_dong_kind(kind=k)
    t, n_pool, end = rc.recommend(S["data"], inp.max_deposit, inp.max_rent, kinds=inp.kinds, min_area=inp.min_area)
    start = end - pd.DateOffset(months=rc.REC_MONTHS)
    rows = t[["동", "유형", "면적", "계약수", "예산 안 계약", "예산 안 비율", "월세 중앙값", "건축년도 중앙값"]]
    return clean_json({"rows": rows.to_dict("records"), "n_pool": n_pool,
                       "period": f"{start:%Y.%m}~{end:%Y.%m}"})


@app.get("/api/score")
def score():
    imp = S["model"].importance().round(1)
    return clean_json({"period": S["period"], "rows": S["score"].to_dict("records"),
                       "building_rows": S["bscore"].to_dict("records"),
                       "importance": [{"정보": k, "중요도": v} for k, v in imp.items()],
                       "funnel": S["log"].values.tolist()})


# ---------------------------------------------------------------
# React 빌드 결과(web/dist)를 같은 서버에서 보내기 — 없으면 API만 동작
# ---------------------------------------------------------------
DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")       # 새로고침해도 React 화면이 뜨게
