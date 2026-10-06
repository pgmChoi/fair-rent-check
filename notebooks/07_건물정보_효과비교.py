# =========================================================
# 7단계: 건축물대장 정보를 넣으면 예측이 좋아지는가? (Google Colab용)
# - 준비물: 드라이브 "원룸월세" 폴더의 raw_3년.csv (02단계), 건물정보.csv (06단계)
# - 이 노트북 하나로 실행됩니다 (앞 노트북을 다시 돌릴 필요 없음).
# - 비교 대상: 연립다세대·오피스텔 원룸만 (단독다가구는 지번이 없어 연결 불가)
# =========================================================

# %% [셀 1] 설치 + 드라이브 연결
!pip install -q lightgbm pandas
from google.colab import drive
drive.mount("/content/drive")

import numpy as np
import pandas as pd
import lightgbm as lgb

SAVE_DIR = "/content/drive/MyDrive/원룸월세"
TEST_START, TEST_END = "2026-03-01", "2026-08-31"     # 지금까지와 같은 시험 기간
PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=15,
              min_child_samples=20, random_state=42, verbose=-1)

# %% [셀 2] 실거래 정제 (02단계와 같은 규칙) + 건물정보 붙이기
raw = pd.read_csv(f"{SAVE_DIR}/raw_3년.csv", dtype=str)
for c in ["deposit", "monthlyRent", "excluUseAr", "floor", "buildYear", "dealYear", "dealMonth", "dealDay"]:
    raw[c] = pd.to_numeric(raw[c].astype(str).str.replace(",", ""), errors="coerce")
d = raw[raw["유형"].isin(["연립다세대", "오피스텔"])].copy()
d["계약일"] = pd.to_datetime(dict(year=d.dealYear, month=d.dealMonth, day=d.dealDay), errors="coerce")
d = d[(d["monthlyRent"] > 0) & (d["contractType"] != "갱신") & d["excluUseAr"].between(8, 33)
      & d["monthlyRent"].between(10, 150) & d["계약일"].notna()]
d = d.rename(columns={"umdNm": "동", "jibun": "지번", "excluUseAr": "면적", "floor": "층",
                      "buildYear": "건축년도", "deposit": "보증금", "monthlyRent": "월세"})

bld = pd.read_csv(f"{SAVE_DIR}/건물정보.csv", dtype={"지번": str})
bld["주차_세대비"] = bld["주차대수"] / bld["세대수"].replace(0, np.nan)   # 세대당 주차 대수
d = d.merge(bld.drop(columns=["연도차", "승인연도", "구조"], errors="ignore"), on=["동", "지번"], how="left")

print(f"연립다세대·오피스텔 원룸 {len(d)}건, 건물정보 연결 {d['지상층수'].notna().mean():.0%}")
print(d.groupby("유형")[["승강기수", "지상층수", "주차_세대비"]].median())

# %% [셀 3] 학습/시험 나누기 (지금까지와 같은 기간)
train = d[d["계약일"] < TEST_START].copy()
test  = d[(d["계약일"] >= TEST_START) & (d["계약일"] <= TEST_END)].copy()
print(f"학습 {len(train)}건 / 시험 {len(test)}건")

BASE = ["동", "유형", "면적", "보증금", "층", "건축년도", "경과월"]          # 지금 모델
PLUS = BASE + ["지상층수", "승강기수", "주차대수", "세대수", "주차_세대비", "연면적", "용적률"]
cats = {c: sorted(train[c].unique()) for c in ["동", "유형"]}

def make_X(df, feats):
    X = df.copy()
    X["경과월"] = (X["계약일"].dt.year - 2023) * 12 + X["계약일"].dt.month
    for c in cats:
        X[c] = pd.Categorical(X[c], categories=cats[c])
    return X[feats]

# %% [셀 4] 두 모델 학습 → 같은 시험 데이터로 비교
def fit_predict(feats):
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, **PARAMS)
    m.fit(make_X(train, feats), train["월세"])
    return m, m.predict(make_X(test, feats))

m_base, p_base = fit_predict(BASE)
m_plus, p_plus = fit_predict(PLUS)

y = test["월세"].values
def score(p, name):
    e = np.abs(y - p)
    return {"모델": name, "평균 오차(만원)": round(e.mean(), 2),
            "평균 오차율(%)": round((e / y).mean() * 100, 1), "±5만원 이내(%)": round((e <= 5).mean() * 100, 1)}

print(pd.DataFrame([score(p_base, "지금 모델"), score(p_plus, "+ 건축물대장 정보")]).to_string(index=False))

print("\n[유형별 평균 오차]")
for t in ["연립다세대", "오피스텔"]:
    k = (test["유형"] == t).values
    print(f"  {t}: 지금 {np.abs(y[k]-p_base[k]).mean():.2f} → 건물정보 추가 {np.abs(y[k]-p_plus[k]).mean():.2f}만 원")

# %% [셀 5] 우연이 아닌지 확인: 시험 거래를 1,000번 다시 뽑아서 차이를 재본다 (부트스트랩)
rng = np.random.default_rng(0)
diff = np.abs(y - p_base) - np.abs(y - p_plus)        # 양수면 건물정보 쪽이 더 잘 맞춘 거래
boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(1000)]
lo, hi = np.percentile(boots, [2.5, 97.5])
print(f"평균 개선: {diff.mean():+.2f}만 원 (95% 범위 {lo:+.2f} ~ {hi:+.2f})")
if lo > 0:
    print("→ 범위 전체가 0보다 큼: 건물정보가 실제로 도움이 된다고 볼 수 있음")
elif hi < 0:
    print("→ 범위 전체가 0보다 작음: 건물정보를 넣으면 오히려 나빠짐")
else:
    print("→ 범위가 0을 포함: 좋아졌다고 말하기 어려움 (우연일 수 있음)")

# %% [셀 6] 건물정보 중 무엇이 쓰였나
imp = pd.Series(m_plus.booster_.feature_importance("gain"), index=PLUS)
print((imp / imp.sum() * 100).round(1).sort_values(ascending=False).to_string())

# %% [셀 7] 확인 실험: 연립다세대 효과가 "다른 기간"에서도 나오는가?
# 셀 4에서 연립다세대만 크게 좋아졌는데, 이건 결과를 보고 나서 찾은 패턴이다.
# 우연이 아닌지 보려면, 이번 시험 기간과 겹치지 않는 "더 이전 기간"으로 한 번 더 시험해야 한다.
def compare(test_start, test_end, kind="연립다세대", n_boot=1000):
    tr = d[d["계약일"] < test_start]
    te = d[(d["계약일"] >= test_start) & (d["계약일"] <= test_end) & (d["유형"] == kind)]
    preds = {}
    for name, feats in [("지금", BASE), ("건물정보", PLUS)]:
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, **PARAMS).fit(make_X(tr, feats), tr["월세"])
        preds[name] = m.predict(make_X(te, feats))
    yy = te["월세"].values
    diff = np.abs(yy - preds["지금"]) - np.abs(yy - preds["건물정보"])
    r = np.random.default_rng(0)
    b = [diff[r.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)]
    lo, hi = np.percentile(b, [2.5, 97.5])
    return {"시험 기간": f"{test_start[:7]}~{test_end[:7]}", "유형": kind, "시험건수": len(te),
            "지금 오차": round(np.abs(yy - preds["지금"]).mean(), 2),
            "건물정보 오차": round(np.abs(yy - preds["건물정보"]).mean(), 2),
            "개선": round(diff.mean(), 2), "95% 범위": f"{lo:+.2f} ~ {hi:+.2f}"}

rows = []
for kind in ["연립다세대", "오피스텔"]:
    rows.append(compare("2025-09-01", "2026-02-28", kind))   # 확인용: 이전 6개월 (새로 보는 기간)
    rows.append(compare("2026-03-01", "2026-08-31", kind))   # 원래 시험 기간
print(pd.DataFrame(rows).to_string(index=False))

# %% [셀 8] 데이터 고치기: "기록 안 됨"인 0을 빈칸으로 바꾸고 확인 실험 다시 하기
# - 용적률 0: 실제로는 있을 수 없는 값 → 옛날 대장에 안 적힌 것
# - 세대수 0: 주거용 건물에서 있을 수 없음 → 오피스텔은 '호'로 세서 0으로 나온 것
# - 주차 0: 작은 옛 빌라는 진짜 0일 수 있어서 그대로 두고,
#           10층 이상 또는 연면적 3,000㎡ 이상인 큰 건물의 0만 "기록 안 됨"으로 본다
bld2 = pd.read_csv(f"{SAVE_DIR}/건물정보.csv", dtype={"지번": str})
fix = {
    "용적률 0": bld2["용적률"] == 0,
    "세대수 0": bld2["세대수"] == 0,
    "큰 건물 주차 0": (bld2["주차대수"] == 0) & ((bld2["지상층수"] >= 10) | (bld2["연면적"] >= 3000)),
}
for name, mask in fix.items():
    print(f"{name}: {mask.sum()}곳 → 빈칸으로")
bld2.loc[fix["용적률 0"], "용적률"] = np.nan
bld2.loc[fix["세대수 0"], "세대수"] = np.nan
bld2.loc[fix["큰 건물 주차 0"], "주차대수"] = np.nan
bld2["주차_세대비"] = bld2["주차대수"] / bld2["세대수"]
bld2.to_csv(f"{SAVE_DIR}/건물정보_정리.csv", index=False, encoding="utf-8-sig")

# 정리한 건물정보로 d를 다시 만들고, 셀 7과 똑같은 확인 실험을 다시 한다
base_cols = [c for c in d.columns if c not in bld2.columns or c in ["동", "지번"]]
d = d[base_cols].merge(bld2.drop(columns=["연도차", "승인연도", "구조"], errors="ignore"),
                       on=["동", "지번"], how="left")
rows = []
for kind in ["연립다세대", "오피스텔"]:
    rows.append(compare("2025-09-01", "2026-02-28", kind))
    rows.append(compare("2026-03-01", "2026-08-31", kind))
print("\n[정리 후 확인 실험]")
print(pd.DataFrame(rows).to_string(index=False))
