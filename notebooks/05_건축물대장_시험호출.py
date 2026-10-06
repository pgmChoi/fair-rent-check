# =========================================================
# 5단계: 건축물대장 표제부 시험 호출 (Google Colab용)
# - 목적: 실거래 데이터의 지번으로 건물을 찾을 수 있는지, 항목 이름이 맞는지 확인
# - "# %%" 구분선마다 Colab 셀 하나에 붙여넣고 위에서부터 실행하세요.
# - 준비물: 구글 드라이브 "원룸월세" 폴더의 raw_3년.csv (02 노트북에서 저장한 파일)
# =========================================================

# %% [셀 1] 설치 + 드라이브 연결 + 설정
!pip install -q requests pandas
from google.colab import drive
drive.mount("/content/drive")

import json, time
import requests
import xml.etree.ElementTree as ET
import pandas as pd

SAVE_DIR = "/content/drive/MyDrive/원룸월세"
SERVICE_KEY = "여기에_Decoding_인증키를_붙여넣기"   # 실거래가 API와 같은 키 (계정 하나에 키 하나)

# 기술문서에 적힌 주소와 다르면 기술문서 쪽으로 고치세요
TITLE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

SIGUNGU = "28177"   # 인천 미추홀구
# 법정동 코드 뒤 5자리. 시험은 주안동(2817710500)으로 한다.
# 다른 동 코드는 code.go.kr의 법정동 코드표에서 찾아 추가하세요.
BJDONG = {"주안동": "10500"}

# %% [셀 2] 시험할 거래 고르기: 주안동 연립다세대 원룸 중 서로 다른 건물 5곳
raw = pd.read_csv(f"{SAVE_DIR}/raw_3년.csv", dtype=str)
for c in ["excluUseAr", "monthlyRent"]:
    raw[c] = pd.to_numeric(raw[c].str.replace(",", ""), errors="coerce")

cand = raw[(raw["유형"] == "연립다세대") & (raw["umdNm"] == "주안동")
           & (raw["monthlyRent"] > 0) & (raw["excluUseAr"] <= 33) & raw["jibun"].notna()]
samples = cand.drop_duplicates("jibun").head(5)[["umdNm", "jibun", "mhouseNm", "buildYear", "floor"]]
print(f"주안동 연립다세대 원룸 거래 {len(cand)}건, 서로 다른 건물 {cand['jibun'].nunique()}곳")
print(samples.to_string(index=False))

def split_jibun(jibun):
    """'104-37' → ('0104', '0037'),  '132' → ('0132', '0000')"""
    bun, _, ji = str(jibun).partition("-")
    return bun.zfill(4), (ji or "0").zfill(4)

print(split_jibun("104-37"), split_jibun("132"))

# %% [셀 3] 표제부 조회 함수 (XML·JSON 어느 쪽으로 와도 읽게 함)
def get_title(dong, jibun):
    bun, ji = split_jibun(jibun)
    params = {"serviceKey": SERVICE_KEY, "sigunguCd": SIGUNGU, "bjdongCd": BJDONG[dong],
              "platGbCd": "0", "bun": bun, "ji": ji, "numOfRows": 10, "pageNo": 1}
    res = requests.get(TITLE_URL, params=params, timeout=30)
    text = res.text.strip()

    if text.startswith("{"):                       # JSON으로 온 경우
        body = json.loads(text)["response"]["body"]
        items = body.get("items") or {}
        items = items.get("item", []) if isinstance(items, dict) else []
        return [items] if isinstance(items, dict) else items

    root = ET.fromstring(res.content)              # XML로 온 경우
    code = root.findtext(".//resultCode")
    if code not in ("00", "000"):
        raise RuntimeError(f"API 오류: {text[:300]}")
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]

# %% [셀 4] 1건 시험: 응답에 어떤 항목이 오는지 전부 보기
first = samples.iloc[0]
items = get_title(first["umdNm"], first["jibun"])
print(f"{first['umdNm']} {first['jibun']} ({first['mhouseNm']}) → 표제부 {len(items)}건")
if items:
    for k, v in items[0].items():
        print(f"  {k:25s} {v}")

# %% [셀 5] 우리가 쓰려는 항목이 실제로 있는지 확인
WANT = {
    "useAprDay": "사용승인일", "grndFlrCnt": "지상 층수", "rideUseElvtCnt": "승강기 수",
    "hhldCnt": "세대 수", "fmlyCnt": "가구 수", "strctCdNm": "구조",
    "mainPurpsCdNm": "주용도", "indrAutoUtcnt": "옥내 자주식 주차", "oudrAutoUtcnt": "옥외 자주식 주차",
}
if items:
    for k, name in WANT.items():
        print(f"{'있음' if k in items[0] else '없음'}  {k:18s} {name}: {items[0].get(k, '-')}")

# %% [셀 6] 5개 건물로 연결 성공률 + 실거래 건축년도와 비교
rows = []
for _, s in samples.iterrows():
    try:
        its = get_title(s["umdNm"], s["jibun"])
    except Exception as e:
        its, err = [], str(e)[:60]
    else:
        err = ""
    t = its[0] if its else {}
    rows.append({"지번": s["jibun"], "실거래 건물명": s["mhouseNm"], "실거래 건축년도": s["buildYear"],
                 "표제부 건수": len(its), "대장 사용승인일": t.get("useAprDay", ""),
                 "지상층수": t.get("grndFlrCnt", ""), "승강기": t.get("rideUseElvtCnt", ""),
                 "오류": err})
    time.sleep(0.3)
check = pd.DataFrame(rows)
print(check.to_string(index=False))
print(f"\n연결 성공: {(check['표제부 건수'] > 0).sum()} / {len(check)}곳")
