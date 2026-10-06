# =========================================================
# 3단계: 시점 효과 확인 → LightGBM으로 기준선 이기기 (Google Colab용)
# - 02 노트북의 셀 9 아래에 이어서 붙여넣으세요.
# - 런타임이 끊겼다면 02의 셀 1, 2, 5, 6, 7, 8을 먼저 다시 실행하세요.
#   (train, test, add_bins, build_tables, predict, report 가 필요합니다)
# =========================================================

# %% [셀 10] 시점 효과 확인 ①: 반기별 원룸 월세 중앙값
data["반기"] = data["계약일"].dt.year.astype(str) + np.where(data["계약일"].dt.month <= 6, "-상", "-하")
print(data.pivot_table(index="반기", columns="유형", values="월세", aggfunc="median"))
# 아래로 갈수록 숫자가 커지면 → 월세가 오르는 중 → 오래된 거래는 지금 시세보다 싸게 나옴

# %% [셀 11] 시점 효과 확인 ②: 기준선을 "최근 12개월 거래"로만 만들면 더 잘 맞는가?
recent_start = pd.Timestamp(TEST_START) - pd.DateOffset(months=12)
train_recent = add_bins(train[train["계약일"] >= recent_start])
tables_recent = build_tables(train_recent)
pred_recent = test_b.join(test_b.apply(predict, axis=1, tables=tables_recent))

print(pd.DataFrame([
    report(pred, "기준선 (학습 전체)"),
    report(pred_recent, "기준선 (최근 12개월만)"),
]).to_string(index=False))

# %% [셀 12] LightGBM 준비
!pip install -q lightgbm
import lightgbm as lgb

FEATS = ["동", "유형", "면적", "보증금", "층", "건축년도", "경과월"]
CATS = ["동", "유형"]
cat_levels = {c: sorted(train[c].dropna().unique()) for c in CATS}  # 학습에 있던 값만 범주로 인정

def make_X(df):
    X = df.copy()
    X["경과월"] = (X["계약일"].dt.year - 2023) * 12 + X["계약일"].dt.month  # 시간 흐름
    for c in CATS:
        X[c] = pd.Categorical(X[c], categories=cat_levels[c])
    return X[FEATS]

X_train, y_train = make_X(train), train["월세"]
X_test = make_X(test)
print(X_train.head())

# %% [셀 13] 분위수 모델 3개 학습: 하위 25%, 중앙값, 상위 75%
PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=15,
              min_child_samples=20, random_state=42, verbose=-1)
models = {}
for name, a in [("하위25", 0.25), ("예측", 0.5), ("상위75", 0.75)]:
    models[name] = lgb.LGBMRegressor(objective="quantile", alpha=a, **PARAMS).fit(X_train, y_train)

pred_lgb = test.copy()
for name, m in models.items():
    pred_lgb[name] = m.predict(X_test)
# 드물게 하위25 > 상위75로 뒤집히는 경우가 있어 정렬해 둔다
q = np.sort(pred_lgb[["하위25", "예측", "상위75"]].values, axis=1)
pred_lgb["하위25"], pred_lgb["예측"], pred_lgb["상위75"] = q[:, 0], q[:, 1], q[:, 2]

# %% [셀 14] 성적표: 세 방법 비교
print(pd.DataFrame([
    report(naive, "전체 중앙값 하나"),
    report(pred, "비슷한 조건 중앙값"),
    report(pred_lgb, "LightGBM"),
]).to_string(index=False))

print("\n[LightGBM 유형별]")
print(pd.DataFrame([report(g, k) for k, g in pred_lgb.groupby("유형")]).to_string(index=False))

# %% [셀 15] 어떤 정보가 예측에 많이 쓰였나 (발표용)
imp = pd.Series(models["예측"].booster_.feature_importance("gain"), index=FEATS)
print((imp / imp.sum() * 100).round(1).sort_values(ascending=False).to_string())

# %% [셀 16] 시연: 직방 매물을 LightGBM으로 진단
def diagnose_lgb(dong, kind, area, deposit, rent, floor=np.nan, build_year=np.nan):
    row = pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit,
                         "층": floor, "건축년도": build_year,
                         "계약일": test["계약일"].max()}])  # "지금" 계약한다고 가정
    lo, mid, hi = np.sort([models[k].predict(make_X(row))[0] for k in ["하위25", "예측", "상위75"]])
    signal = "저렴" if rent < lo else ("비쌈" if rent > hi else "적정")
    print(f"[{signal}] LightGBM 적정 범위: {lo:.0f} ~ {hi:.0f}만 원 (중앙값 {mid:.0f}만 원)")
    print(f"  입력한 월세 {rent}만 원 (관리비 별도)")

diagnose_lgb("용현동", "단독다가구", 16, 300, 32)
