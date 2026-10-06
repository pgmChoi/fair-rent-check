# =========================================================
# 2단계: 3년치 수집 → 정제 → 첫 기준선 성능 측정 (Google Colab용)
# - "# %%" 구분선마다 Colab 셀 하나에 붙여넣고 위에서부터 실행하세요.
# - 수집(셀 2~4)은 한 번만 하고, 이후에는 셀 5부터 CSV를 읽어서 쓰면 됩니다.
# =========================================================

# %% [셀 1] 설치 + 구글 드라이브 연결 (Colab은 끄면 파일이 사라지므로 드라이브에 저장)
!pip install -q requests pandas
from google.colab import drive
drive.mount("/content/drive")

import os
SAVE_DIR = "/content/drive/MyDrive/원룸월세"   # 팀 공유 폴더로 바꿔도 됨
os.makedirs(SAVE_DIR, exist_ok=True)

# %% [셀 2] 설정
import requests, time
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np

SERVICE_KEY = "여기에_Decoding_인증키를_붙여넣기"

# 수집할 구 (법정동코드 앞 5자리). 주변 구를 더하려면 코드를 추가하세요 (code.go.kr에서 확인).
REGIONS = {"미추홀구": "28177"}

# 3년치: 2023년 10월 ~ 2026년 9월 (36개월)
MONTHS = [f"{y}{m:02d}" for y in range(2023, 2027) for m in range(1, 13)
          if "202310" <= f"{y}{m:02d}" <= "202609"]

APIS = {
    "단독다가구": "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
    "연립다세대": "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "오피스텔":   "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
}
print(f"{len(REGIONS)}개 구 x {len(APIS)}종 x {len(MONTHS)}개월 = {len(REGIONS)*len(APIS)*len(MONTHS)}번 호출 예정")

# %% [셀 3] 한 달치 가져오는 함수 (실패하면 3번까지 다시 시도)
def fetch_month(url, lawd_cd, deal_ymd, rows=1000, retry=3):
    items, page = [], 1
    while True:
        params = {"serviceKey": SERVICE_KEY, "LAWD_CD": lawd_cd,
                  "DEAL_YMD": deal_ymd, "pageNo": page, "numOfRows": rows}
        for attempt in range(retry):
            try:
                res = requests.get(url, params=params, timeout=30)
                root = ET.fromstring(res.content)
                break
            except Exception as e:
                if attempt == retry - 1:
                    raise
                time.sleep(2)

        code = root.findtext(".//resultCode")
        if code not in ("000", "00"):
            raise RuntimeError(f"API 오류 ({deal_ymd}): {res.text[:300]}")

        for it in root.iter("item"):
            items.append({c.tag: (c.text or "").strip() for c in it})

        total = int(root.findtext(".//totalCount") or 0)
        if page * rows >= total:
            return items
        page += 1

# %% [셀 4] 3년치 수집 → 드라이브에 원본 CSV 저장 (5~10분 정도 걸릴 수 있음)
frames = []
for region, code in REGIONS.items():
    for name, url in APIS.items():
        for ym in MONTHS:
            df = pd.DataFrame(fetch_month(url, code, ym))
            df["구"], df["유형"], df["수집월"] = region, name, ym
            frames.append(df)
            print(f"{region} {name} {ym}: {len(df)}건")
            time.sleep(0.2)

raw = pd.concat(frames, ignore_index=True)
raw.to_csv(f"{SAVE_DIR}/raw_3년.csv", index=False, encoding="utf-8-sig")
print("원본 저장 완료:", raw.shape)

# %% [셀 5] 정제 — 단계마다 몇 건이 빠졌는지 기록 (보고서에 그대로 쓸 수 있음)
raw = pd.read_csv(f"{SAVE_DIR}/raw_3년.csv", dtype=str)

def clean(raw):
    d = raw.copy()
    log = [("원본", len(d))]

    # 1) 숫자로 바꾸기 ("10,000" → 10000)
    for col in ["deposit", "monthlyRent", "excluUseAr", "totalFloorAr", "floor",
                "buildYear", "dealYear", "dealMonth", "dealDay"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col].astype(str).str.replace(",", ""), errors="coerce")

    # 2) 면적 하나로 합치기: 연립·오피스텔은 전용면적, 단독다가구는 연면적(=계약면적)
    d["면적"] = d["excluUseAr"].fillna(d["totalFloorAr"])
    d["계약일"] = pd.to_datetime(dict(year=d.dealYear, month=d.dealMonth, day=d.dealDay), errors="coerce")

    # 3) 전세 제외 (월세 0원)
    d = d[d["monthlyRent"] > 0];               log.append(("전세 제외", len(d)))
    # 4) 갱신 계약 제외 (인상률 상한 때문에 시세보다 낮게 잡힘)
    d = d[d["contractType"] != "갱신"];        log.append(("갱신 계약 제외", len(d)))
    # 5) 원룸만: 면적 33㎡(약 10평) 이하, 너무 작은 이상값(8㎡ 미만) 제외
    d = d[d["면적"].between(8, 33)];           log.append(("원룸(8~33㎡)만", len(d)))
    # 6) 월세 이상값 제외 (원룸 월세 10만 원 미만 또는 150만 원 초과)
    d = d[d["monthlyRent"].between(10, 150)];  log.append(("월세 이상값 제외", len(d)))
    # 7) 계약일이 없는 행 제외
    d = d[d["계약일"].notna()];                 log.append(("계약일 없음 제외", len(d)))

    keep = ["구", "유형", "umdNm", "면적", "floor", "buildYear", "deposit", "monthlyRent",
            "계약일", "contractTerm", "jibun", "mhouseNm", "offiNm", "houseType"]
    d = d[[c for c in keep if c in d.columns]].rename(columns={
        "umdNm": "동", "floor": "층", "buildYear": "건축년도",
        "deposit": "보증금", "monthlyRent": "월세"})
    return d.reset_index(drop=True), pd.DataFrame(log, columns=["단계", "남은 건수"])

data, log = clean(raw)
print(log.to_string(index=False))
data.to_csv(f"{SAVE_DIR}/원룸_정제.csv", index=False, encoding="utf-8-sig")
print("\n월별 건수 (마지막 달이 적으면 신고 지연):")
print(data.groupby(data["계약일"].dt.to_period("M")).size().tail(6).to_string())

# %% [셀 6] 시간 순서로 나누기: 과거로 "학습", 최근 6개월로 "시험"
# 마지막 달(2026-09)은 신고가 덜 들어와서 시험에서 뺀다
TEST_START, TEST_END = "2026-03-01", "2026-08-31"

train = data[data["계약일"] < TEST_START].copy()
test  = data[(data["계약일"] >= TEST_START) & (data["계약일"] <= TEST_END)].copy()
print(f"학습: {len(train)}건 ({train['계약일'].min().date()} ~ {train['계약일'].max().date()})")
print(f"시험: {len(test)}건 ({test['계약일'].min().date()} ~ {test['계약일'].max().date()})")

# %% [셀 7] 기준선: "비슷한 조건 거래의 중앙값"
# 조건을 좁은 것부터 넓은 것 순서로 시도하고, 거래가 MIN_N건 이상 모이는 첫 단계를 쓴다
AREA_BINS = [0, 15, 20, 25, 33]
DEP_BINS  = [-1, 100, 300, 500, 1000, 3000, 1e9]
MIN_N = 5

def add_bins(df):
    df = df.copy()
    df["면적구간"] = pd.cut(df["면적"], AREA_BINS).astype(str)
    df["보증금구간"] = pd.cut(df["보증금"], DEP_BINS).astype(str)
    return df

LEVELS = [
    ("동+유형+면적+보증금", ["동", "유형", "면적구간", "보증금구간"]),
    ("동+유형+면적",        ["동", "유형", "면적구간"]),
    ("동+면적",             ["동", "면적구간"]),
    ("구 전체+면적",        ["면적구간"]),
]

def build_tables(train):
    """조건 단계마다 '중앙값, 하위25%, 상위75%, 건수' 표를 만들어 둔다."""
    tables = {}
    for name, keys in LEVELS:
        g = train.groupby(keys)["월세"]
        tables[name] = pd.DataFrame({
            "중앙값": g.median(), "하위25": g.quantile(0.25),
            "상위75": g.quantile(0.75), "건수": g.size()})
    return tables

def predict(row, tables):
    for name, keys in LEVELS:
        key = tuple(row[k] for k in keys)
        key = key[0] if len(key) == 1 else key
        t = tables[name]
        if key in t.index and t.loc[key, "건수"] >= MIN_N:
            r = t.loc[key]
            return pd.Series({"예측": r["중앙값"], "하위25": r["하위25"], "상위75": r["상위75"],
                              "근거건수": int(r["건수"]), "사용조건": name})
    return pd.Series({"예측": np.nan, "하위25": np.nan, "상위75": np.nan, "근거건수": 0, "사용조건": "없음"})

train_b, test_b = add_bins(train), add_bins(test)
tables = build_tables(train_b)
pred = test_b.join(test_b.apply(predict, axis=1, tables=tables))
print(pred["사용조건"].value_counts().to_string())

# %% [셀 8] 성적표: 기준선이 얼마나 맞았나
def report(df, label):
    df = df.dropna(subset=["예측"])
    err = (df["월세"] - df["예측"]).abs()
    inside = df["월세"].between(df["하위25"], df["상위75"])
    return {"방법": label, "시험건수": len(df),
            "MAE(만원)": round(err.mean(), 2),
            "MAPE(%)": round((err / df["월세"]).mean() * 100, 1),
            "±5만원 이내(%)": round((err <= 5).mean() * 100, 1),
            "25~75% 범위 적중(%)": round(inside.mean() * 100, 1)}

# 비교용 가장 단순한 예측: 학습 데이터 전체 월세 중앙값 하나로 모두 예측
naive = test_b.copy()
naive["예측"] = train["월세"].median()
naive["하위25"], naive["상위75"] = train["월세"].quantile(0.25), train["월세"].quantile(0.75)

score = pd.DataFrame([report(naive, "전체 중앙값 하나"), report(pred, "비슷한 조건 중앙값")])
print(score.to_string(index=False))

print("\n[유형별 성적]")
print(pd.DataFrame([report(g, k) for k, g in pred.groupby("유형")]).to_string(index=False))

# %% [셀 9] 시연: 직방 매물(용현동 16㎡, 보증금 300, 월세 32)을 진단해 보기
def diagnose(dong, kind, area, deposit, rent):
    row = add_bins(pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit}])).iloc[0]
    p = predict(row, tables)
    if p["사용조건"] == "없음":
        return print("비슷한 거래가 부족해서 판단할 수 없습니다.")
    # 같은 조건의 실제 거래 중 몇 % 위치인지
    keys = dict(LEVELS)[p["사용조건"]]
    same = train_b
    for k in keys:
        same = same[same[k] == row[k]]
    pct = (same["월세"] <= rent).mean() * 100
    signal = "저렴" if rent < p["하위25"] else ("비쌈" if rent > p["상위75"] else "적정")
    print(f"[{signal}] 비슷한 실제 계약 {p['근거건수']}건 ({p['사용조건']}) 기준")
    print(f"  적정 범위: {p['하위25']:.0f} ~ {p['상위75']:.0f}만 원 (중앙값 {p['예측']:.0f}만 원)")
    print(f"  입력한 월세 {rent}만 원은 하위 {pct:.0f}% 위치입니다. (관리비 별도)")

diagnose("용현동", "단독다가구", 16, 300, 32)
