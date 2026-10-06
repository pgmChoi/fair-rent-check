# =========================================================
# 6단계: 연립다세대·오피스텔 원룸 건물의 표제부 전체 수집 → 실거래와 연결 (Google Colab용)
# - 05 노트북의 셀 1, 3을 먼저 실행하세요 (SERVICE_KEY, TITLE_URL, split_jibun 이 필요합니다).
# - 대상: 원룸 신규 월세 거래가 있는 건물 약 335곳 → API 약 340번 호출 (10분 이내)
# =========================================================

# %% [셀 7] 표제부 조회 함수 v2: 일시적 오류는 다시 시도, 오류 메시지는 전부 기록
import os, time, json
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import requests

def get_title_v2(bjdong_cd, jibun, retry=3):
    bun, ji = split_jibun(jibun)
    params = {"serviceKey": SERVICE_KEY, "sigunguCd": "28177", "bjdongCd": bjdong_cd,
              "platGbCd": "0", "bun": bun, "ji": ji, "numOfRows": 50, "pageNo": 1}
    last = ""
    for attempt in range(retry):
        try:
            res = requests.get(TITLE_URL, params=params, timeout=30)
            text = res.text.strip()
            if text.startswith("{"):
                items = json.loads(text)["response"]["body"].get("items") or {}
                items = items.get("item", []) if isinstance(items, dict) else []
                return ([items] if isinstance(items, dict) else items), ""
            root = ET.fromstring(res.content)
            if root.findtext(".//resultCode") in ("00", "000"):
                return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")], ""
            last = (root.findtext(".//returnAuthMsg") or root.findtext(".//resultMsg") or text[:200])
        except Exception as e:
            last = f"{type(e).__name__}: {e}"[:200]
        time.sleep(2 * (attempt + 1))      # 잠깐 쉬었다가 다시
    return [], last

# %% [셀 8] 미추홀구 법정동 코드 확인
# 주안동(10500)만 확인된 값이고 나머지는 "추정"입니다.
# 동마다 실제 지번 하나로 조회해서, 응답 주소(platPlc)에 그 동 이름이 들어 있으면 맞는 코드로 인정합니다.
GUESS = {"숭의동": "10100", "용현동": "10200", "학익동": "10300", "도화동": "10400",
         "주안동": "10500", "관교동": "10600", "문학동": "10700"}

raw = pd.read_csv(f"{SAVE_DIR}/raw_3년.csv", dtype=str)
for c in ["excluUseAr", "monthlyRent"]:
    raw[c] = pd.to_numeric(raw[c].str.replace(",", ""), errors="coerce")
target = raw[raw["유형"].isin(["연립다세대", "오피스텔"]) & (raw["monthlyRent"] > 0)
             & raw["excluUseAr"].between(8, 33) & (raw["contractType"] != "갱신") & raw["jibun"].notna()]

BJDONG, rows = {}, []
for dong, code in GUESS.items():
    jibuns = target.loc[target["umdNm"] == dong, "jibun"].drop_duplicates().head(3)
    ok, addr = False, ""
    for j in jibuns:                                # 지번 3개까지 시도
        items, err = get_title_v2(code, j)
        if items:
            addr = items[0].get("platPlc", "")
            ok = dong in addr
            break
    if ok:
        BJDONG[dong] = code
    status = "맞음" if ok else ("대상 거래 없음" if jibuns.empty else "확인 필요")
    rows.append({"동": dong, "추정 코드": code, "확인": status, "응답 주소": addr})
    time.sleep(0.3)
print(pd.DataFrame(rows).to_string(index=False))
print("\n사용할 코드:", BJDONG)

# %% [셀 9] 건물 목록 만들고 표제부 전체 수집 (중간 저장 → 끊겨도 이어서 진행)
buildings = target[target["umdNm"].isin(BJDONG)][["umdNm", "jibun"]].drop_duplicates()
CACHE = f"{SAVE_DIR}/표제부_원본.csv"
done = pd.read_csv(CACHE, dtype=str) if os.path.exists(CACHE) else pd.DataFrame(columns=["q_dong", "q_jibun"])
done_keys = set(zip(done["q_dong"], done["q_jibun"]))
todo = [b for b in buildings.itertuples(index=False) if (b.umdNm, b.jibun) not in done_keys]
print(f"대상 건물 {len(buildings)}곳 / 이미 수집 {len(done_keys)}곳 / 이번에 수집 {len(todo)}곳")

new_rows, errors = [], []
for i, b in enumerate(todo, 1):
    items, err = get_title_v2(BJDONG[b.umdNm], b.jibun)
    if err:
        errors.append({"동": b.umdNm, "지번": b.jibun, "오류": err})
    for it in items or [{}]:                       # 대장이 없어도 "조회했음" 기록은 남김
        new_rows.append({"q_dong": b.umdNm, "q_jibun": b.jibun, **it})
    if i % 50 == 0 or i == len(todo):
        pd.concat([done, pd.DataFrame(new_rows)], ignore_index=True).to_csv(CACHE, index=False, encoding="utf-8-sig")
        print(f"  {i}/{len(todo)} 저장")
    time.sleep(0.2)

ledger = pd.read_csv(CACHE, dtype=str)
print(f"표제부 원본 {len(ledger)}행 저장 완료, 오류 {len(errors)}곳")
if errors:
    print(pd.DataFrame(errors).head(10).to_string(index=False))

# %% [셀 10] 지번마다 건물 하나 고르기 + 필요한 항목만 숫자로 정리
def num(col):
    """항목을 숫자로. 응답에 그 항목이 없으면 빈칸(NaN)으로 채운다."""
    if col not in ledger:
        return pd.Series(np.nan, index=ledger.index)
    return pd.to_numeric(ledger[col], errors="coerce")
L = ledger.assign(
    승인연도=num("useAprDay") // 10000,
    지상층수=num("grndFlrCnt"),
    승강기수=num("rideUseElvtCnt").fillna(0) + num("emgenUseElvtCnt").fillna(0),
    주차대수=sum(num(c).fillna(0) for c in ["indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"]),
    세대수=num("hhldCnt").fillna(0) + num("fmlyCnt").fillna(0),
    연면적=num("totArea"),
    용적률=num("vlRat"),
)
# 대장을 못 찾은 건물은 승강기·주차·세대수도 "0"이 아니라 "모름(빈칸)"으로 둔다
L.loc[L["승인연도"].isna(), ["승강기수", "주차대수", "세대수"]] = np.nan
L = L[L["mainAtchGbCd"].fillna("0").astype(str) == "0"] if "mainAtchGbCd" in L else L       # 부속건축물(창고 등) 제외, 주건축물만

# 한 지번에 건물이 여러 동이면: 실거래 건축년도와 승인연도가 가장 가까운 동을 고른다
by = (target.assign(by=pd.to_numeric(target["buildYear"], errors="coerce"))
      .groupby(["umdNm", "jibun"])["by"].median().rename("실거래_건축년도").reset_index())
L = L.merge(by, left_on=["q_dong", "q_jibun"], right_on=["umdNm", "jibun"], how="left")
L["연도차"] = (L["승인연도"] - L["실거래_건축년도"]).abs()
L = L.sort_values("연도차").drop_duplicates(["q_dong", "q_jibun"])

FEAT_B = ["승인연도", "지상층수", "승강기수", "주차대수", "세대수", "연면적", "용적률", "strctCdNm"]
bld = L[["q_dong", "q_jibun", "연도차"] + FEAT_B].rename(columns={"q_dong": "동", "q_jibun": "지번", "strctCdNm": "구조"})
bld.to_csv(f"{SAVE_DIR}/건물정보.csv", index=False, encoding="utf-8-sig")
print(bld.describe().round(1).to_string())

# %% [셀 11] 연결 품질 성적표
n_all = len(buildings)
n_hit = bld["승인연도"].notna().sum()
same = (bld["연도차"] <= 1).sum()
print(f"표제부를 찾은 건물: {n_hit} / {n_all}곳 ({n_hit / n_all:.0%})")
print(f"실거래 건축년도와 승인연도가 1년 이내로 일치: {same} / {n_hit}곳 ({same / max(n_hit, 1):.0%})")
print("\n승강기 있는 건물 비율:", f"{(bld['승강기수'] > 0).mean():.0%}")
print("\n연도가 크게 다른 건물 (연결이 틀렸을 수 있음):")
print(bld[bld["연도차"] > 3].head(10).to_string(index=False))
