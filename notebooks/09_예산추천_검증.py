# ============================================================
# 09. 같은 예산 추천 — 과거로 추천하면 다음 6개월에도 맞는가?
#   Colab에서 셀 단위로 실행 (# %% 가 셀 구분)
#   필요한 파일 2개: app/rent_core.py, app/data/raw_3년.csv
# ============================================================

# %% [셀 1] 설치 + 파일 올리기
!pip -q install lightgbm pandas numpy

from google.colab import files
up = files.upload()          # rent_core.py, raw_3년.csv 두 개를 함께 선택

# %% [셀 2] 데이터 정리
import numpy as np, pandas as pd
import rent_core as rc
data, _ = rc.clean(pd.read_csv("raw_3년.csv", dtype=str))
test = rc.add_bins(data[(data["계약일"] >= rc.TEST_START) & (data["계약일"] <= rc.TEST_END)])
print("시험 기간 계약", len(test))

# %% [셀 3] 2026-02-28까지의 최근 1년으로 추천 → 2026.03~08 실제 계약으로 확인
#   예산 20가지(보증금 4 × 월세 5)마다 상위 5개 조합을 추천하고,
#   그 조합의 시험 기간 계약 중 예산 안에 든 비율을 잰다.
rows = []
for dep in [100, 300, 500, 1000]:
    for rent in [25, 30, 35, 40, 45]:
        rec, _, _ = rc.recommend(data, dep, rent, end="2026-02-28", top=5)
        for _, r in rec.iterrows():
            s = test[(test["동"] == r["동"]) & (test["유형"] == r["유형"]) &
                     (test["면적구간"] == r["면적구간"]) & (test["보증금"] <= dep)]
            if len(s) >= 5:                                   # 시험 기간 계약이 너무 적은 조합은 제외
                rows.append({"예산": f"{dep}/{rent}", "과거 비율": r["예산 안 비율"],
                             "시험기간 실제 비율": (s["월세"] <= rent).mean() * 100, "시험 건수": len(s)})
res = pd.DataFrame(rows)
print("확인한 추천 조합", len(res))
print("과거 비율 평균", res["과거 비율"].mean().round(1), "/ 시험기간 실제 비율 평균", res["시험기간 실제 비율"].mean().round(1))
print("평균 차이(%p)", (res["과거 비율"] - res["시험기간 실제 비율"]).abs().mean().round(1))

# %% [셀 4] 비교: 추천 없이 같은 예산의 아무 방이나 골랐다면?
base = [(test[test["보증금"] <= dep]["월세"] <= rent).mean() * 100
        for dep in [100, 300, 500, 1000] for rent in [25, 30, 35, 40, 45]]
print("같은 예산 전체 계약 중 예산 안 비율 평균", round(np.mean(base), 1))
# 기대 결과: 추천 조합 약 64% vs 전체 약 45% → 추천이 도움이 됨
#           다만 과거 비율(약 78%)은 실제(약 64%)보다 높게 나옴 → 화면에 '시세 기준, 실제는 더 낮을 수 있음' 안내
