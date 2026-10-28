"""붙여넣기 파서 시험:  (저장소 맨 위 폴더에서)  python -m pytest tests -q"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from listing_parser import parse_listing, parse_money, check_scope

# 사용자가 실제로 직방 '더보기' 창을 드래그해서 붙여 넣은 글자 (2026-10-28)
MORE = """전용 23.14m²
분리형원룸 (욕실 1개)
단일동 3층/4층
주차 불가능
2026.11.15 이후 입주 가능
남향 (안방 주실 기준)
엘리베이터 없음
다가구주택
20020605 준공
미추홀구 용현동 83-13
등록번호 50661280
위반건축물 여부: 해당 없음
중개사무소가 등록한 매물"""

# 같은 매물의 상세 화면 위쪽 (캡처 화면을 보고 옮겨 적음)
TOP = """등록번호 50661280
17일 전
월세 300/45
인천시 미추홀구 용현동 · 관리비 5만원
베란다 | 넓은방 | 리모델링 | 풀옵션
전용 23.14m²
분리형원룸 (욕실 1개)
주차 불가능
단일동 3층/4층
2026.11.15 이후 입주 가능"""


def test_more_only():
    r = parse_listing(MORE)
    v = r["values"]
    assert v == {"면적": 23.14, "층": 3, "유형": "단독다가구", "건축년도": 2002, "동": "용현동", "지번": "83-13"}
    assert r["missing"] == ["보증금", "월세"]          # 더보기 창에는 가격이 없다
    assert r["extra"]["등록번호"] == "50661280"
    assert r["extra"]["주차"] == "불가능" and r["extra"]["엘리베이터"] == "없음"
    assert r["extra"]["위반건축물"] == "없음"


def test_top_and_more():
    r = parse_listing(TOP + "\n" + MORE)
    v = r["values"]
    assert r["missing"] == []
    assert (v["보증금"], v["월세"], v["지번"], v["건축년도"]) == (300, 45, "83-13", 2002)
    assert r["extra"]["관리비"] == 5.0


def test_top_only():
    r = parse_listing(TOP)
    assert r["missing"] == ["유형"]
    assert "지번" not in r["values"] and r["values"]["동"] == "용현동"


def test_money_and_kinds():
    assert parse_money("1,000") == 1000 and parse_money("1억") == 10000 and parse_money("1억 2,000") == 12000
    r = parse_listing("월세 1억 2,000/30\n다세대주택\n전용 19.8㎡\nB1층/5층\n2015.03.02 준공\n주안1동")
    v = r["values"]
    assert (v["보증금"], v["월세"], v["유형"], v["층"], v["건축년도"]) == (12000, 30, "연립다세대", -1, 2015)
    assert "오피스텔" == parse_listing("오피스텔\n월세 500/50")["values"]["유형"]


def test_warnings():
    assert parse_listing("전세 1억 5,000")["warnings"]
    assert "유형" not in parse_listing("도시형생활주택 월세 300/40")["values"]
    assert parse_listing("위반건축물 여부: 해당")["extra"]["위반건축물"] == "있음"
    assert check_scope({"동": "송도동", "면적": 40}, ["용현동"]) and not check_scope({"동": "용현동", "면적": 20}, ["용현동"])


def test_garbage():
    r = parse_listing("아무 글자나 붙여 넣음")
    assert r["values"] == {} and len(r["missing"]) == 5
