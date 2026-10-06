# =========================================================
# 1단계: 전월세 실거래가 데이터 직접 까보기 (Google Colab용)
# - 셀 구분선(# %%)마다 Colab 셀 하나에 붙여넣고 위에서부터 실행하세요.
# =========================================================

# %% [셀 1] 설치
!pip install -q requests pandas

# %% [셀 2] 설정 — 여기만 고치면 됩니다
import requests, time
import xml.etree.ElementTree as ET
import pandas as pd

# 공공데이터포털 > 마이페이지 > 데이터활용 > Open API > 활용신청 현황 > "일반 인증키(Decoding)" 값
SERVICE_KEY = "여기에_Decoding_인증키를_붙여넣기"

LAWD_CD = "28177"  # 인천 미추홀구 (법정동코드 앞 5자리, code.go.kr에서 확인 가능)

# 최근 12개월 (2025년 10월 ~ 2026년 9월)
MONTHS = [f"2025{m:02d}" for m in range(10, 13)] + [f"2026{m:02d}" for m in range(1, 10)]

# 기술문서(hwp)에 적힌 주소 그대로
APIS = {
    "단독다가구": "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
    "연립다세대": "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "오피스텔":   "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
}

# %% [셀 3] API 한 달치 가져오는 함수
def fetch_month(url, lawd_cd, deal_ymd, rows=1000):
    """한 지역, 한 달치 거래를 모두 가져와서 dict 목록으로 돌려준다."""
    items, page = [], 1
    while True:
        params = {"serviceKey": SERVICE_KEY, "LAWD_CD": lawd_cd,
                  "DEAL_YMD": deal_ymd, "pageNo": page, "numOfRows": rows}
        res = requests.get(url, params=params, timeout=30)
        root = ET.fromstring(res.content)

        code = root.findtext(".//resultCode")
        if code not in ("000", "00"):
            # 인증키 오류 등은 형식이 다른 XML로 오므로 원문을 그대로 보여준다
            raise RuntimeError(f"API 오류 ({deal_ymd}): {res.text[:300]}")

        for it in root.iter("item"):
            items.append({child.tag: (child.text or "").strip() for child in it})

        total = int(root.findtext(".//totalCount") or 0)
        if page * rows >= total:
            return items
        page += 1

# %% [셀 4] 먼저 1건만 시험 호출 (인증키가 되는지 확인)
test = fetch_month(APIS["연립다세대"], LAWD_CD, "202609", rows=5)
print(f"시험 호출 성공: {len(test)}건")
print(test[:2])

# %% [셀 5] 3종 x 12개월 전체 수집 후 CSV 저장
frames = []
for name, url in APIS.items():
    for ym in MONTHS:
        rows = fetch_month(url, LAWD_CD, ym)
        df = pd.DataFrame(rows)
        df["유형"] = name
        frames.append(df)
        print(f"{name} {ym}: {len(df)}건")
        time.sleep(0.2)  # 서버에 부담 주지 않도록 잠깐 쉬기

raw = pd.concat(frames, ignore_index=True)
raw.to_csv("미추홀구_전월세_12개월.csv", index=False, encoding="utf-8-sig")
print("저장 완료:", raw.shape)

# %% [셀 6] 숫자 정리 ("10,000" 같은 쉼표 제거)
data = raw.copy()
for col in ["deposit", "monthlyRent", "excluUseAr", "totalFloorAr", "floor", "buildYear"]:
    if col in data.columns:
        data[col] = pd.to_numeric(data[col].str.replace(",", ""), errors="coerce")

wolse = data[data["monthlyRent"] > 0]  # 월세 0원 = 전세이므로 제외
print("전체:", len(data), "/ 월세만:", len(wolse))

# %% [셀 7] 확인 ① 학교 주변 동별 월세 거래 건수
print(wolse.groupby(["유형", "umdNm"]).size().unstack(0).fillna(0).astype(int)
      .sort_values("단독다가구", ascending=False).head(15))

# %% [셀 8] 확인 ② 소액 월세(보증금 6천만 원 이하 + 월세 30만 원 이하)가 데이터에 있는가
small = wolse[(wolse["deposit"] <= 6000) & (wolse["monthlyRent"] <= 30)]
print(f"소액 월세 거래: {len(small)}건 / 월세 전체 {len(wolse)}건 "
      f"({len(small) / max(len(wolse), 1):.1%})")

# %% [셀 9] 확인 ③ 단독다가구의 면적은 '방 면적'인가 '건물 전체 면적'인가
sh = wolse[wolse["유형"] == "단독다가구"]
print(sh["totalFloorAr"].describe())
# 대부분 15~40이면 → 방(계약) 면적일 가능성
# 대부분 100 이상이면 → 건물 전체 연면적 → 원룸 크기를 알 수 없음

# %% [셀 10] 확인 ④ 유형별로 어떤 칸이 비어 있는지
for name in APIS:
    sub = wolse[wolse["유형"] == name]
    print(f"\n[{name}] {len(sub)}건")
    print((sub.replace("", pd.NA).notna().mean() * 100).round(0).astype(int).to_string())
