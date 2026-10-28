"""API 시험:  (저장소 맨 위 폴더에서)  python -m pytest tests -q   (모델 학습 때문에 10초 정도 걸림)"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from api.main import app                       # noqa: E402
from test_listing_parser import TOP, MORE      # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:            # with 안에서 서버 시작(데이터·모델 준비)이 실행됨
        yield client


def test_meta(c):
    m = c.get("/api/meta").json()
    assert "용현동" in m["dongs"] and m["kinds"] == ["단독다가구", "연립다세대", "오피스텔"]
    assert m["legal_cap"] == 5.0


def test_parse_then_diagnose(c):
    p = c.post("/api/parse", json={"text": TOP + "\n" + MORE}).json()
    v = p["values"]
    assert p["missing"] == []
    r = c.post("/api/diagnose", json={"dong": v["동"], "kind": v["유형"], "area": v["면적"], "deposit": v["보증금"],
                                      "rent": v["월세"], "floor": v["층"], "build_year": v["건축년도"],
                                      "jibun": v["지번"]}).json()
    assert r["lo"] <= r["mid"] <= r["hi"] and r["signal"] in ("저렴", "적정", "비쌈")
    assert len(r["comparables"]) <= 20 and r["n"] == len(r["same_rents"])


def test_bait(c):
    r = c.post("/api/diagnose", json={"dong": "용현동", "kind": "단독다가구", "area": 20, "deposit": 300,
                                      "rent": 15}).json()
    assert r["bait"] is True and r["signal"] == "저렴"


def test_building(c):
    r = c.post("/api/diagnose", json={"dong": "주안동", "kind": "연립다세대", "area": 20, "deposit": 500,
                                      "rent": 40, "jibun": "713-2"}).json()
    assert r["used_building"] is True


def test_bad_input(c):
    assert c.post("/api/diagnose", json={"dong": "송도동", "kind": "오피스텔", "area": 20, "deposit": 300,
                                         "rent": 40}).status_code == 400
    assert c.post("/api/diagnose", json={"dong": "용현동", "kind": "오피스텔", "area": 50, "deposit": 300,
                                         "rent": 40}).status_code == 422


def test_convert_recommend_score(c):
    v = c.post("/api/convert", json={"kind": "단독다가구", "rent": 45, "deposit": 300, "new_deposit": 1300}).json()
    assert round(v["market_rent"], 1) == 37.3 and round(v["legal_rent"], 1) == 40.8
    r = c.post("/api/recommend", json={"max_deposit": 300, "max_rent": 35}).json()
    assert r["rows"] and r["n_pool"] > 0
    s = c.get("/api/score").json()
    assert len(s["rows"]) == 4 and s["importance"]
