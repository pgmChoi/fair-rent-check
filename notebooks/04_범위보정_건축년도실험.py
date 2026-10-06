# =========================================================
# 4단계: 적정 범위 보정 + "건축년도를 모르면?" 실험 (Google Colab용)
# - 03의 셀 16 아래에 이어서 붙여넣으세요.
# - 런타임이 끊겼다면 02의 셀 1, 2, 5~8과 03의 셀 12~13을 먼저 다시 실행하세요.
# =========================================================

# %% [셀 17] 범위 보정: 몇 % 구간을 써야 실제로 절반이 들어오는가?
# 시험 데이터로 고르면 "답을 보고 고른" 셈이 되므로,
# 학습 데이터의 마지막 3개월을 따로 떼어 "검증용"으로 쓴다.
VAL_START = pd.Timestamp(TEST_START) - pd.DateOffset(months=3)
inner = train[train["계약일"] < VAL_START]
val   = train[train["계약일"] >= VAL_START]
print(f"보정용 학습 {len(inner)}건 / 검증 {len(val)}건")

def fit_q(X, y, alpha):
    return lgb.LGBMRegressor(objective="quantile", alpha=alpha, **PARAMS).fit(X, y)

rows = []
for lo_a, hi_a in [(0.25, 0.75), (0.20, 0.80), (0.15, 0.85), (0.10, 0.90)]:
    lo = fit_q(make_X(inner), inner["월세"], lo_a).predict(make_X(val))
    hi = fit_q(make_X(inner), inner["월세"], hi_a).predict(make_X(val))
    inside = ((val["월세"] >= np.minimum(lo, hi)) & (val["월세"] <= np.maximum(lo, hi))).mean()
    rows.append({"하위": lo_a, "상위": hi_a, "검증 적중(%)": round(inside * 100, 1),
                 "평균 범위폭(만원)": round(np.mean(np.abs(hi - lo)), 1)})
calib = pd.DataFrame(rows)
print(calib.to_string(index=False))

# 목표 50%에 가장 가까운 조합 선택
best = calib.iloc[(calib["검증 적중(%)"] - 50).abs().argmin()]
LO_A, HI_A = best["하위"], best["상위"]
print(f"\n선택: 하위 {LO_A:.0%} ~ 상위 {HI_A:.0%}")

# %% [셀 18] 선택한 구간으로 전체 학습 데이터에 다시 학습 → 시험 성적
models_cal = {"하위25": fit_q(X_train, y_train, LO_A),
              "예측":   models["예측"],
              "상위75": fit_q(X_train, y_train, HI_A)}
pred_cal = test.copy()
for name, m in models_cal.items():
    pred_cal[name] = m.predict(X_test)
q = np.sort(pred_cal[["하위25", "예측", "상위75"]].values, axis=1)
pred_cal["하위25"], pred_cal["예측"], pred_cal["상위75"] = q[:, 0], q[:, 1], q[:, 2]

print(pd.DataFrame([
    report(pred, "비슷한 조건 중앙값"),
    report(pred_lgb, "LightGBM (25~75%)"),
    report(pred_cal, f"LightGBM 보정 ({LO_A:.0%}~{HI_A:.0%})"),
]).to_string(index=False))
print("※ 표의 '25~75% 범위 적중' 칸은 보정 모델에서는 '보정된 범위 적중'으로 읽으세요.")

# %% [셀 19] 실험: 사용자가 건축년도를 모르면 얼마나 나빠지나?
# 방법 A: 지금 모델에 건축년도만 빈칸으로 넣기
X_nb = X_test.copy()
X_nb["건축년도"] = np.nan
mae_a = (test["월세"] - models["예측"].predict(X_nb)).abs().mean()

# 방법 B: 처음부터 건축년도 없이 학습한 모델
FEATS_NB = [f for f in FEATS if f != "건축년도"]
models_nb = {"하위25": fit_q(X_train[FEATS_NB], y_train, LO_A),   # 범위도 건축년도 없이 따로 학습
             "예측":   fit_q(X_train[FEATS_NB], y_train, 0.5),
             "상위75": fit_q(X_train[FEATS_NB], y_train, HI_A)}
mae_b = (test["월세"] - models_nb["예측"].predict(X_test[FEATS_NB])).abs().mean()

mae_full = (test["월세"] - models["예측"].predict(X_test)).abs().mean()
mae_base = (pred.dropna(subset=["예측"])["월세"] - pred.dropna(subset=["예측"])["예측"]).abs().mean()
print(pd.DataFrame({
    "경우": ["건축년도 알 때 (LightGBM)", "A: 같은 모델에 빈칸 입력", "B: 건축년도 없이 학습", "참고: 기준선"],
    "MAE(만원)": [round(mae_full, 2), round(mae_a, 2), round(mae_b, 2), round(mae_base, 2)],
}).to_string(index=False))

# %% [셀 20] 진단 함수 v2: "근거 거래 위치" + "보정된 모델 범위"를 함께 보여준다
def diagnose_v2(dong, kind, area, deposit, rent, floor=np.nan, build_year=np.nan):
    # (1) 근거: 비슷한 실제 계약 중 몇 % 위치인가 (기준선 방식)
    row_b = add_bins(pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit}])).iloc[0]
    p = predict(row_b, tables)
    same = train_b
    for k in dict(LEVELS)[p["사용조건"]]:
        same = same[same[k] == row_b[k]]
    pct = (same["월세"] <= rent).mean() * 100

    # (2) 범위: 보정된 LightGBM (건축년도를 모르면 건축년도 없는 모델 사용)
    row = pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit,
                         "층": floor, "건축년도": build_year, "계약일": test["계약일"].max()}])
    X = make_X(row)
    if np.isnan(build_year):
        # 건축년도가 빈칸이면 건축년도 없이 학습한 모델을 쓴다 (셀 19 결과 참고)
        lo, mid, hi = [models_nb[k].predict(X[FEATS_NB])[0] for k in ["하위25", "예측", "상위75"]]
        note = " (건축년도 모름 → 정확도 낮음)"
    else:
        lo, mid, hi = [models_cal[k].predict(X)[0] for k in ["하위25", "예측", "상위75"]]
        note = ""
    lo, mid, hi = np.sort([lo, mid, hi])
    signal = "저렴" if rent < lo else ("비쌈" if rent > hi else "적정")

    print(f"[{signal}] 월세 {rent}만 원 / 보증금 {deposit}만 원 (관리비 별도)")
    print(f"  · 비슷한 실제 계약 {len(same)}건 중 하위 {pct:.0f}% 위치")
    print(f"  · AI 적정 범위: {lo:.0f} ~ {hi:.0f}만 원 (중앙값 {mid:.0f}만 원){note}")

diagnose_v2("용현동", "단독다가구", 16, 300, 32)
