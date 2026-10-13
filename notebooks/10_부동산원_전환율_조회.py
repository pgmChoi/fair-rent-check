# ============================================================
# 10. 한국부동산원(R-ONE) 지역별 전월세 전환율 찾기 — 1단계: 통계표 ID와 지역 항목 확인
#   Colab에서 셀 단위로 실행 (# %% 가 셀 구분)
#   준비물: R-ONE 오픈API 인증키 (R-ONE 홈페이지에서 신청, 공공데이터포털 키와 다름)
#   ※ 키를 넣은 채로 깃허브에 올리지 마세요.
# ============================================================

# %% [셀 1] 설치 + 인증키
!pip -q install requests pandas

import json, requests, pandas as pd
R_ONE_KEY = "여기에_R-ONE_인증키를_붙여넣기"
BASE = "https://www.reb.or.kr/r-one/openapi"

def find_rows(obj):
    """응답 JSON 안에서 '행 목록'(dict들의 list)을 찾아 꺼낸다.
    응답 구조를 문서에서 확인하지 못해서, 구조가 조금 달라도 찾을 수 있게 짰다."""
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj) and any(len(x) > 3 for x in obj):
            return obj
        for x in obj:
            r = find_rows(x)
            if r: return r
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_rows(v)
            if r: return r
    return None

def call(service, **params):
    p = {"Key": R_ONE_KEY, "Type": "json", "pIndex": 1, "pSize": 1000, **params}
    res = requests.get(f"{BASE}/{service}.do", params=p, timeout=30)
    res.raise_for_status()
    data = res.json()
    rows = find_rows(data)
    if rows is None:                                  # 에러 메시지(코드 290 등)를 그대로 보여주기
        print(json.dumps(data, ensure_ascii=False)[:500])
        return pd.DataFrame()
    return pd.DataFrame(rows)

# %% [셀 2] 통계표 목록에서 '전월세 전환율' 통계표 ID 찾기 (명세서: SttsApiTbl)
tbl = call("SttsApiTbl")
print("통계표 수:", len(tbl))
conv = tbl[tbl["STATBL_NM"].str.contains("전환율", na=False)]
print(conv[["STATBL_ID", "STATBL_NM", "DTACYCLE_NM", "DATA_START_YY", "DATA_END_YY"]].to_string(index=False))

# %% [셀 3] 통계표의 지역·항목 코드 보기 (명세서: SttsApiTblItm)
#   확인 결과(2026-10): 지역은 시도 단위까지만 있음(미추홀구 없음) → 인천 사용
#   연립/다세대 A_2024_00157, 단독 A_2024_00158 : 인천 = 분류(CLS_ID) 500009
#   오피스텔 T241163133546529 : 인천 = 그룹(GRP_ID) 60001, 40㎡이하 = 분류(CLS_ID) 50001
IDS = {"연립다세대": "A_2024_00157", "단독다가구": "A_2024_00158", "오피스텔": "T241163133546529"}
for name, sid in IDS.items():
    itm = call("SttsApiTblItm", STATBL_ID=sid)
    hit = itm[itm.astype(str).apply(lambda r: r.str.contains("인천|40㎡이하").any(), axis=1)]
    print(f"[{name}]"); print(hit[["ITM_TAG", "ITM_ID", "ITM_NM"]].to_string(index=False))

# %% [셀 4] 인천 월별 전환율 받기 (SttsApiTblData — 2026-10 실행해서 동작 확인)
def get_rate(sid, **extra):
    df = call("SttsApiTblData", STATBL_ID=sid, DTACYCLE_CD="MM", **extra)
    df["DTA_VAL"] = pd.to_numeric(df["DTA_VAL"], errors="coerce")
    return df.sort_values("WRTTIME_IDTFR_ID")

rates = {
    "연립다세대": get_rate("A_2024_00157", CLS_ID="500009"),
    "단독다가구": get_rate("A_2024_00158", CLS_ID="500009"),
    "오피스텔":   get_rate("T241163133546529", GRP_ID="60001", CLS_ID="50001"),
}
for k, df in rates.items():
    print(k, df[["WRTTIME_DESC", "DTA_VAL"]].tail(3).to_string(index=False))
# 기대 결과(2026-10 기준): 연립다세대 2026년 7월 8.84 / 단독 2026년 7월 9.19 / 오피스텔(40㎡이하) 2026년 8월 7.30

# %% [셀 5] 가장 최근 값으로 앱용 파일 만들기 → app/data/전환율_인천.csv 로 저장(교체)
SRC = {"연립다세대": "한국부동산원 지역별 전월세 전환율_연립/다세대 · 인천",
       "단독다가구": "한국부동산원 지역별 전월세 전환율_단독주택 · 인천",
       "오피스텔":   "한국부동산원 오피스텔 전월세전환율 · 인천 · 40㎡이하"}
rows = []
for k, df in rates.items():
    last = df.dropna(subset=["DTA_VAL"]).iloc[-1]
    w = str(last["WRTTIME_IDTFR_ID"])
    rows.append({"유형": k, "전환율": round(last["DTA_VAL"], 6), "기준월": f"{w[:4]}-{w[4:6]}",
                 "통계표ID": last["STATBL_ID"], "출처": SRC[k]})
out = pd.DataFrame(rows)
print(out.to_string(index=False))
out.to_csv("전환율_인천.csv", index=False, encoding="utf-8")
from google.colab import files
files.download("전환율_인천.csv")
