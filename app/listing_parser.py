"""
직방 매물 정보 붙여넣기 → 진단 입력값으로 바꾸기 (규칙 기반, AI/LLM 사용 안 함)

사용 방법 (PC 직방 웹)
  1) 매물 상세 화면 위쪽(월세 300/45 ~ 입주 가능일)을 드래그해서 복사
  2) '더보기' → 매물 정보 창 전체를 드래그해서 복사
  두 덩어리를 한 칸에 이어서 붙여 넣으면 된다. 둘 중 하나만 있어도 읽을 수 있는 값은 읽는다.

주의
- 크롤링이 아니다. 사용자가 자기 화면에서 직접 복사한 글자만 읽는다.
- 직방이 화면 문구를 바꾸면 일부 값을 못 읽을 수 있다 → 못 읽은 값은 missing에 담고 화면에서 직접 고치게 한다.
"""
import re

# 직방 표기 → 우리 데이터(국토부 실거래)의 주택 유형
KIND_MAP = [
    ("오피스텔", "오피스텔"),
    ("다가구", "단독다가구"),
    ("단독주택", "단독다가구"),
    ("다세대", "연립다세대"),
    ("연립", "연립다세대"),
    ("빌라", "연립다세대"),
]
# 도시형생활주택·근린생활시설 등은 실거래 분류가 건물마다 달라서 자동으로 정하지 않는다
AMBIGUOUS_KINDS = ["도시형생활주택", "근린생활시설", "생활숙박시설"]


def _num(s):
    return float(s.replace(",", ""))


def parse_money(s):
    """'300' → 300, '1,000' → 1000, '1억' → 10000, '1억 2,000' → 12000 (단위: 만 원)"""
    s = s.replace(" ", "")
    m = re.fullmatch(r"(?:(\d+)억)?([\d,]*)", s)
    if not m or (not m.group(1) and not m.group(2)):
        return None
    eok = int(m.group(1)) * 10000 if m.group(1) else 0
    man = int(m.group(2).replace(",", "")) if m.group(2) else 0
    return eok + man


def parse_listing(text: str) -> dict:
    """붙여 넣은 글자에서 진단에 필요한 값을 뽑는다.

    돌려주는 값
      values  : 진단 입력값 (동, 유형, 면적, 보증금, 월세, 층, 건축년도, 지번)
      extra   : 화면 참고용 (관리비, 등록번호, 엘리베이터, 주차, 위반건축물 등)
      missing : 못 찾은 필수 값 이름
      warnings: 사용자에게 보여줄 주의 문구
    """
    t = (text or "").replace("\r", "")
    v, extra, warnings = {}, {}, []

    # 1) 보증금/월세: '월세 300/45'
    m = re.search(r"월세\s*([\d,억\s]+?)\s*/\s*([\d,]+)", t)
    if m:
        dep = parse_money(m.group(1))
        if dep is not None:
            v["보증금"] = dep
            v["월세"] = int(_num(m.group(2)))
    elif re.search(r"전세\s*[\d,억]", t):
        warnings.append("전세 매물이에요. 이 서비스는 월세만 진단해요.")

    # 2) 관리비: '관리비 5만원' / '관리비 없음'
    m = re.search(r"관리비\s*([\d.,]+)\s*만\s*원", t)
    if m:
        extra["관리비"] = _num(m.group(1))
    elif re.search(r"관리비\s*없음", t):
        extra["관리비"] = 0.0

    # 3) 전용면적: '전용 23.14m²' (없으면 '23.14m²' 첫 번째 값)
    m = re.search(r"전용\s*([\d.]+)\s*(?:m²|㎡|m2)", t) or re.search(r"([\d.]+)\s*(?:m²|㎡|m2)", t)
    if m:
        v["면적"] = round(_num(m.group(1)), 2)

    # 4) 층: '3층/4층', 'B1층/4층', '반지하/4층', '저층/4층'(정확한 층 아님)
    m = re.search(r"(B\d+|반지하|지하|저|중|고|\d+)\s*층?\s*/\s*(\d+)\s*층", t)
    if m:
        f = m.group(1)
        extra["전체층"] = int(m.group(2))
        if f.isdigit():
            v["층"] = int(f)
        elif f in ("반지하", "지하") or f.startswith("B"):
            v["층"] = -1
        else:
            warnings.append(f"층이 '{f}층'으로만 나와 있어 정확한 층은 넣지 않았어요.")

    # 5) 주택 유형
    if any(a in t for a in AMBIGUOUS_KINDS):
        warnings.append("도시형생활주택·근린생활시설은 실거래 분류가 건물마다 달라요. 주택 유형을 직접 골라 주세요.")
    else:
        for key, kind in KIND_MAP:
            if key in t:
                v["유형"] = kind
                break

    # 6) 준공(건축)년도: '20020605 준공', '2002.06.05 준공', '2002년 준공'
    m = (re.search(r"(\d{4})\d{4}\s*준공", t)
         or re.search(r"(\d{4})\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]?\s*(?:\d{1,2}\s*일?)?\s*준공", t)
         or re.search(r"(\d{4})\s*년\s*준공", t)
         or re.search(r"(?:사용승인|준공)\D{0,6}(\d{4})", t))
    if m and 1900 <= int(m.group(1)) <= 2100:
        v["건축년도"] = int(m.group(1))

    # 7) 주소: '미추홀구 용현동 83-13' → 구, 동, 지번 / '인천시 미추홀구 용현동' → 구, 동
    # 위쪽 화면은 '용현동'까지만, 더보기는 '용현동 83-13'까지 나오므로 지번이 있는 쪽을 우선
    found = list(re.finditer(r"([가-힣]+구)\s+([가-힣]+\d*동|[가-힣]+\d*가)(?:\s*(\d+(?:-\d+)?)(?![\d.]))?", t))
    found.sort(key=lambda x: x.group(3) is None)
    m = found[0] if found else None
    if m:
        extra["구"] = m.group(1)
        v["동"] = re.sub(r"(\D)\d+동$", r"\1동", m.group(2))     # '주안1동' → '주안동' (실거래는 법정동)
        if m.group(3):
            v["지번"] = m.group(3)

    # 8) 참고 정보 (진단에는 안 쓰고 화면/북마크에만)
    m = re.search(r"등록번호\s*(\d+)", t)
    if m:
        extra["등록번호"] = m.group(1)
    if re.search(r"엘리베이터\s*없음", t):
        extra["엘리베이터"] = "없음"
    elif re.search(r"엘리베이터\s*있음", t):
        extra["엘리베이터"] = "있음"
    if re.search(r"주차\s*불가", t):
        extra["주차"] = "불가능"
    elif re.search(r"주차\s*가능", t):
        extra["주차"] = "가능"
    m = re.search(r"위반건축물\s*여부\s*[:：]?\s*(해당\s*없음|해당|있음)", t)
    if m:
        extra["위반건축물"] = "없음" if "없음" in m.group(1) else "있음"
        if extra["위반건축물"] == "있음":
            warnings.append("위반건축물로 표시된 매물이에요. 전세자금대출·보증보험이 거절될 수 있으니 꼭 확인하세요.")
    m = re.search(r"([동서남북]{1,2}향)", t)
    if m:
        extra["방향"] = m.group(1)
    m = re.search(r"(\d{4}\.\d{1,2}\.\d{1,2})\s*이후\s*입주", t)
    if m:
        extra["입주가능일"] = m.group(1)
    elif "즉시 입주" in t or "즉시입주" in t:
        extra["입주가능일"] = "즉시"

    required = ["동", "유형", "면적", "보증금", "월세"]
    missing = [k for k in required if k not in v]
    return {"values": v, "extra": extra, "missing": missing, "warnings": warnings}


def check_scope(values: dict, dongs: list, area_min=8, area_max=33) -> list:
    """우리 모델이 배운 범위를 벗어나면 알려준다 (진단은 막지 않음)."""
    msgs = []
    if "동" in values and values["동"] not in dongs:
        msgs.append(f"'{values['동']}'은 아직 학습 데이터(인천 미추홀구 {len(dongs)}개 동)에 없어요. 동을 직접 골라 주세요.")
    if "면적" in values and not (area_min <= values["면적"] <= area_max):
        msgs.append(f"전용 {values['면적']}㎡는 원룸 범위({area_min}~{area_max}㎡)를 벗어나 정확도가 낮아요.")
    return msgs
