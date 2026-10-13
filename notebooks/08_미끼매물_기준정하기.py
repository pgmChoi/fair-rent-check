# ============================================================
# 08. 미끼매물 의심 경고 — "얼마나 싸면 경고할까" 기준 정하기
#   Colab에서 셀 단위로 나눠 실행하세요 (# %% 가 셀 구분)
#   필요한 파일 2개: app/rent_core.py, app/data/raw_3년.csv
# ============================================================

# %% [셀 1] 설치 + 파일 올리기
!pip -q install lightgbm pandas numpy

from google.colab import files
up = files.upload()          # rent_core.py, raw_3년.csv 두 개를 함께 선택
print(list(up.keys()))

# %% [셀 2] 데이터 정리 + 기간 나누기
import numpy as np, pandas as pd
import rent_core as rc
pd.set_option("display.width", 200)

raw = pd.read_csv("raw_3년.csv", dtype=str)
data, _ = rc.clean(raw)

# 기준은 '기준 정하기 기간'에서 정하고, '시험 기간'은 확인만 한다 (시험 데이터로 기준을 고르면 반칙)
CAL_START = "2025-12-01"
pre   = data[data["계약일"] < CAL_START]                                           # 기준 정하기용 학습
cal   = data[(data["계약일"] >= CAL_START) & (data["계약일"] < rc.TEST_START)]       # 기준 정하기 (3개월)
train = data[data["계약일"] < rc.TEST_START]                                       # 최종 학습 (앱과 동일)
test  = data[(data["계약일"] >= rc.TEST_START) & (data["계약일"] <= rc.TEST_END)]    # 시험 (2026.03~08)
print("기준 정하기용 학습", len(pre), "/ 기준 정하기", len(cal), "/ 최종 학습", len(train), "/ 시험", len(test))

# %% [셀 3] 실제 계약마다 '월세 ÷ AI 예상 중앙값' 계산
m_cal  = rc.RentModel().fit(pre)     # 기준 정하기 기간을 예측하는 모델
m_test = rc.RentModel().fit(train)   # 시험 기간을 예측하는 모델 (앱과 같은 모델)

def add_ratio(m, df):
    out = df.copy()
    for tag, use in [("모름", False), ("앎", True)]:          # 건축년도 모름/앎 두 경우
        lo, mid, hi = m.predict(df, use_build_year=use)
        out[f"중앙_{tag}"] = mid
        out[f"비율_{tag}"] = df["월세"].values / mid          # 1.0 = AI 예상과 같음, 0.6 = 40% 쌈
    return out

c = add_ratio(m_cal, cal)
t = add_ratio(m_test, test)
for tag in ["모름", "앎"]:
    print(f"\n[건축년도 {tag}] 실제 계약의 '월세 ÷ AI 중앙값' (기준 정하기 기간)")
    print(c[f"비율_{tag}"].quantile([.005, .01, .02, .05, .10, .5]).round(3).to_string())

# %% [셀 4] 목표 오경보율별 기준 + 시험 기간에서 확인
#   실제 계약은 '진짜 거래'이므로, 여기에 경고가 뜨면 = 잘못된 경고(오경보)
def table(cc, tt):
    rows = []
    for target in [0.01, 0.02, 0.05]:
        for tag in ["모름", "앎"]:
            th = cc[f"비율_{tag}"].quantile(target)
            rows.append({"목표 오경보율": f"{target:.0%}", "건축년도": tag,
                         "기준(중앙값의 몇 배 이하)": round(th, 3),
                         "중앙값보다 몇 % 이상 쌀 때": f"{(1-th)*100:.0f}%",
                         "기준기간 경고율": f"{(cc[f'비율_{tag}'] <= th).mean():.1%}",
                         "시험기간 경고율": f"{(tt[f'비율_{tag}'] <= th).mean():.1%}"})
    return pd.DataFrame(rows)

print(table(c, t).to_string(index=False))

# %% [셀 5] 경고가 뜬 실제 계약은 어떤 방인가? (2% 기준, 건축년도 모름)
th = c["비율_모름"].quantile(0.02)
flag = t[t["비율_모름"] <= th]
print(f"시험 기간 경고 {len(flag)}건 / {len(t)}건\n")
tb, fb = rc.add_bins(t), rc.add_bins(flag)
print(pd.DataFrame({"전체": tb["보증금구간"].value_counts(normalize=True).round(2),
                    "경고": fb["보증금구간"].value_counts(normalize=True).round(2)}))
print(flag[["유형", "동", "면적", "보증금", "월세", "중앙_모름"]].round(1).sort_values("월세").head(10).to_string(index=False))

# %% [셀 6] 보증금 3,000만 원 초과(반전세)를 빼고 다시
DEP_MAX = 3000
c2, t2 = c[c["보증금"] <= DEP_MAX], t[t["보증금"] <= DEP_MAX]
print("고액 보증금 비율: 기준기간", f"{(c['보증금'] > DEP_MAX).mean():.1%}",
      "/ 시험기간", f"{(t['보증금'] > DEP_MAX).mean():.1%}\n")
print(table(c2, t2).to_string(index=False))

# %% [셀 7] 기억하기 쉬운 숫자로 반올림한 최종 규칙 확인
RATIO = 0.65     # AI 예상 중앙값보다 35% 이상 싸면
for tag in ["모름", "앎"]:
    print(f"건축년도 {tag}: 기준기간 {(c2[f'비율_{tag}'] <= RATIO).mean():.1%}"
          f" / 시험기간 {(t2[f'비율_{tag}'] <= RATIO).mean():.1%} ({(t2[f'비율_{tag}'] <= RATIO).sum()}건)")
