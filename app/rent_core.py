"""
원룸 월세 적정가 진단 — 핵심 로직 (정제, 기준선, LightGBM, 진단)
노트북 02~04에서 실험한 내용을 화면(app.py)에서 쓰기 좋게 모은 파일입니다.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb

# ---------------------------------------------------------------
# 실험에서 정한 값들 (바꾸면 성적표가 달라지니 팀과 상의 후 변경)
# ---------------------------------------------------------------
LO_A, HI_A = 0.20, 0.80          # 04단계 셀 17: 검증 데이터에서 실제 적중률 51%로 고른 범위
TEST_START, TEST_END = "2026-03-01", "2026-08-31"   # 실험 노트북(01~09)용 고정 시험 기간 — 발표 숫자의 기준
TEST_MONTHS = 6                  # 앱 성적표: 가장 최근 6개월로 시험 (데이터가 갱신되면 따라 움직임)
LAG_MONTHS = 1                   # 마지막 1개월은 신고 지연(계약 후 30일 이내 신고)으로 덜 들어와서 시험에서 뺌
WARN_N = 20                      # 근거 거래가 이보다 적으면 화면에 경고
MIN_N = 5                        # 기준선에서 한 조건에 필요한 최소 거래 수
BAIT_RATIO = 0.65                # 08단계: AI 중앙값의 0.65배 이하면 미끼매물 의심 (시험기간 오경보 약 2%)
BAIT_DEP_MAX = 3000              # 08단계: 보증금 3,000만 원 초과(반전세)는 AI가 덜 배워서 경고 제외
REC_MONTHS = 12                  # 예산 추천: 최근 몇 개월 계약으로 볼지 (3년간 월세가 10~13% 올라서 최근만)
REC_MIN_N = 10                   # 예산 추천: 한 조합에 필요한 최소 계약 수
BASE_RATE = 3.00                 # 한국은행 기준금리 (2026-08-27 결정). 금통위 결과가 바뀌면 여기만 고친다
LEGAL_CAP = min(10.0, BASE_RATE + 2.0)   # 주택임대차보호법 시행령 제9조: 연 10%와 기준금리+2%p 중 낮은 값
SMALL_DEP_DIFF = 1000            # 보증금 차이가 이보다 작으면 실제로는 월세가 거의 안 바뀜 (같은 건물 거래 비교, 중앙값 0%)

PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=15,
              min_child_samples=20, random_state=42, verbose=-1)
FEATS = ["동", "유형", "면적", "보증금", "층", "건축년도", "경과월"]
FEATS_NB = [f for f in FEATS if f != "건축년도"]     # 건축년도 모를 때 쓰는 모델
CATS = ["동", "유형"]

# 건축물대장(건축HUB 표제부) — 팀 합의(2026-10): 연립다세대에만 적용
BLD_KIND = "연립다세대"
BLD_FEATS = ["지상층수", "승강기수", "주차대수", "세대수", "주차_세대비", "연면적", "용적률"]
FEATS_BLD = FEATS + BLD_FEATS

AREA_BINS = [0, 15, 20, 25, 33]
DEP_BINS = [-1, 100, 300, 500, 1000, 3000, 1e9]
LEVELS = [
    ("동+유형+면적+보증금", ["동", "유형", "면적구간", "보증금구간"]),
    ("동+유형+면적",        ["동", "유형", "면적구간"]),
    ("동+면적",             ["동", "면적구간"]),
    ("구 전체+면적",        ["면적구간"]),
]


# ---------------------------------------------------------------
# 1. 정제
# ---------------------------------------------------------------
def clean(raw: pd.DataFrame):
    d = raw.copy()
    log = [("원본", len(d))]
    for col in ["deposit", "monthlyRent", "excluUseAr", "totalFloorAr", "floor",
                "buildYear", "dealYear", "dealMonth", "dealDay"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col].astype(str).str.replace(",", ""), errors="coerce")
    d["면적"] = d["excluUseAr"].fillna(d["totalFloorAr"])
    d["계약일"] = pd.to_datetime(dict(year=d.dealYear, month=d.dealMonth, day=d.dealDay), errors="coerce")

    d = d[d["monthlyRent"] > 0];               log.append(("전세 제외", len(d)))
    d = d[d["contractType"] != "갱신"];        log.append(("갱신 계약 제외", len(d)))
    d = d[d["면적"].between(8, 33)];           log.append(("원룸(8~33㎡)만", len(d)))
    d = d[d["monthlyRent"].between(10, 150)];  log.append(("월세 이상값 제외", len(d)))
    d = d[d["계약일"].notna()];                 log.append(("계약일 없음 제외", len(d)))

    if "jibun" not in d.columns:
        d["jibun"] = np.nan
    keep = ["유형", "umdNm", "jibun", "면적", "floor", "buildYear", "deposit", "monthlyRent", "계약일"]
    d = d[keep].rename(columns={"umdNm": "동", "jibun": "지번", "floor": "층", "buildYear": "건축년도",
                                "deposit": "보증금", "monthlyRent": "월세"})
    # 건축년도 0 같은 잘못된 값은 빈칸으로
    d.loc[d["건축년도"] < 1900, "건축년도"] = np.nan
    return d.reset_index(drop=True), pd.DataFrame(log, columns=["단계", "남은 건수"])


# ---------------------------------------------------------------
# 2. 기준선 (비슷한 조건 거래의 중앙값)
# ---------------------------------------------------------------
def add_bins(df):
    df = df.copy()
    df["면적구간"] = pd.cut(df["면적"], AREA_BINS).astype(str)
    df["보증금구간"] = pd.cut(df["보증금"], DEP_BINS).astype(str)
    return df


def build_tables(train_b):
    tables = {}
    for name, keys in LEVELS:
        g = train_b.groupby(keys)["월세"]
        tables[name] = pd.DataFrame({"중앙값": g.median(), "하위": g.quantile(LO_A),
                                     "상위": g.quantile(HI_A), "건수": g.size()})
    return tables


def baseline_predict(row, tables):
    for name, keys in LEVELS:
        key = tuple(row[k] for k in keys)
        key = key[0] if len(key) == 1 else key
        t = tables[name]
        if key in t.index and t.loc[key, "건수"] >= MIN_N:
            r = t.loc[key]
            return r["중앙값"], r["하위"], r["상위"], int(r["건수"]), name
    return np.nan, np.nan, np.nan, 0, "없음"


def comparables(train_b, row, level_name):
    """기준선이 사용한 조건과 똑같은 실제 거래 목록"""
    same = train_b
    for k in dict(LEVELS).get(level_name, []):
        same = same[same[k] == row[k]]
    return same


# ---------------------------------------------------------------
# 3. LightGBM 분위수 모델
# ---------------------------------------------------------------
class RentModel:
    def fit(self, train):
        self.cat_levels = {c: sorted(train[c].dropna().unique()) for c in CATS}
        self.now = train["계약일"].max()        # "지금" 시점 = 학습 데이터의 마지막 계약일
        X, y = self.make_X(train), train["월세"]
        self.full = {k: self._fit(X[FEATS], y, a) for k, a in [("lo", LO_A), ("mid", 0.5), ("hi", HI_A)]}
        self.nb = {k: self._fit(X[FEATS_NB], y, a) for k, a in [("lo", LO_A), ("mid", 0.5), ("hi", HI_A)]}
        return self

    @staticmethod
    def _fit(X, y, alpha):
        return lgb.LGBMRegressor(objective="quantile", alpha=alpha, **PARAMS).fit(X, y)

    def make_X(self, df):
        X = df.copy()
        if "계약일" not in X:
            X["계약일"] = self.now
        X["경과월"] = (X["계약일"].dt.year - 2023) * 12 + X["계약일"].dt.month
        for c in CATS:
            X[c] = pd.Categorical(X[c], categories=self.cat_levels[c])
        for c in ["층", "건축년도"]:
            X[c] = pd.to_numeric(X[c], errors="coerce")
        return X

    def predict(self, df, use_build_year=True):
        """하위/중앙/상위 예측. 건축년도를 모르면 건축년도 없이 학습한 모델을 쓴다."""
        X = self.make_X(df)
        models, feats = (self.full, FEATS) if use_build_year else (self.nb, FEATS_NB)
        out = np.column_stack([models[k].predict(X[feats]) for k in ["lo", "mid", "hi"]])
        out = np.sort(out, axis=1)          # 드물게 뒤집히는 경우 정렬
        return out[:, 0], out[:, 1], out[:, 2]

    def importance(self):
        imp = pd.Series(self.full["mid"].booster_.feature_importance("gain"), index=FEATS)
        return (imp / imp.sum() * 100).sort_values(ascending=False)


# ---------------------------------------------------------------
# 4. 성적표 (시간 순서로 나눈 시험 데이터 기준)
# ---------------------------------------------------------------
def _score(y, pred, lo, hi, label):
    err = np.abs(y - pred)
    return {"방법": label, "시험건수": len(y),
            "평균 오차(만원)": round(err.mean(), 2),
            "평균 오차율(%)": round((err / y).mean() * 100, 1),
            "±5만원 이내(%)": round((err <= 5).mean() * 100, 1),
            "범위 적중(%)": round(((y >= lo) & (y <= hi)).mean() * 100, 1)}


def test_window(data, months=TEST_MONTHS, lag=LAG_MONTHS):
    """데이터의 가장 최근 달을 기준으로 시험 기간을 자동으로 정한다.
    예) 마지막 계약이 2026-09 → 9월은 빼고(신고 지연) 2026-03-01 ~ 2026-08-31"""
    last = data["계약일"].max().to_period("M")
    end_m = last - lag
    start_m = end_m - (months - 1)
    return start_m.start_time.normalize(), end_m.end_time.normalize()


def evaluate(data, window=None):
    start, end = window or test_window(data)
    train = data[data["계약일"] < start]
    test = data[(data["계약일"] >= start) & (data["계약일"] <= end)]
    y = test["월세"].values

    naive = np.full(len(test), train["월세"].median())
    rows = [_score(y, naive, train["월세"].quantile(LO_A), train["월세"].quantile(HI_A), "전체 중앙값 하나")]

    tb, sb = add_bins(train), add_bins(test)
    tables = build_tables(tb)
    bp = np.array([baseline_predict(r, tables)[:3] for _, r in sb.iterrows()], dtype=float)
    ok = ~np.isnan(bp[:, 0])
    rows.append(_score(y[ok], bp[ok, 0], bp[ok, 1], bp[ok, 2], "비슷한 조건 중앙값 (기준선)"))

    m = RentModel().fit(train)
    lo, mid, hi = m.predict(test, use_build_year=True)
    rows.append(_score(y, mid, lo, hi, "LightGBM (건축년도 앎)"))
    lo, mid, hi = m.predict(test, use_build_year=False)
    rows.append(_score(y, mid, lo, hi, "LightGBM (건축년도 모름)"))

    period = f"학습 {train['계약일'].min():%Y.%m}~{train['계약일'].max():%Y.%m} ({len(train):,}건) / " \
             f"시험 {test['계약일'].min():%Y.%m}~{test['계약일'].max():%Y.%m} ({len(test):,}건)"
    return pd.DataFrame(rows), period


# ---------------------------------------------------------------
# 5. 진단 (화면에서 부르는 함수)
# ---------------------------------------------------------------
def diagnose(model, train_b, tables, dong, kind, area, deposit, rent, floor=None, build_year=None,
             jibun=None, bmodel=None, bld=None):
    know_by = build_year is not None and not pd.isna(build_year)
    row = pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit,
                         "층": floor if floor else np.nan,
                         "건축년도": build_year if know_by else np.nan}])

    # 건축물대장: 연립다세대 + 지번 입력 + 목록에서 건물을 찾았을 때만 '건물정보 모델' 사용
    building, jibun_status, by_from_ledger = None, None, False
    jj = norm_jibun(jibun)
    if jj and kind == BLD_KIND and bld is not None and bmodel is not None:
        hit = bld[(bld["동"] == dong) & (bld["지번"] == jj)]
        jibun_status = "found" if len(hit) else "notfound"
        if len(hit):
            building = hit.iloc[0].to_dict()
            for c in BLD_FEATS:
                row[c] = building[c]
            if not know_by and not pd.isna(building["승인연도"]):   # 건축년도 모르면 대장 승인연도로 채움
                row["건축년도"] = building["승인연도"]
                know_by, by_from_ledger = True, True
    elif jj:
        jibun_status = "not_used"          # 연립다세대가 아니면 지번은 쓰지 않음

    if building is not None:
        lo, mid, hi = (v[0] for v in bmodel.predict(row))
    else:
        lo, mid, hi = (v[0] for v in model.predict(row, use_build_year=know_by))
    # 화면에 보이는 숫자(만 원 단위 정수)와 판정 기준을 똑같이 맞춘다
    lo, mid, hi = round(lo), round(mid), round(hi)

    # 신호는 AI 범위 하나로만 정한다 (팀 결정)
    signal = "저렴" if rent < lo else ("비쌈" if rent > hi else "적정")

    # 미끼매물 의심: 시세보다 지나치게 싸면 경고 (판정과 별개로 띄움)
    bait_cut = round(mid * BAIT_RATIO)
    bait = (rent <= bait_cut) and (deposit <= BAIT_DEP_MAX)

    # 근거: 비슷한 실제 계약 중 몇 % 위치인가 (참고용)
    rb = add_bins(row).iloc[0]
    *_, n, level = baseline_predict(rb, tables)
    same = comparables(train_b, rb, level) if level != "없음" else train_b.iloc[0:0]
    pct = (same["월세"] <= rent).mean() * 100 if len(same) else np.nan

    return {"signal": signal, "lo": lo, "mid": mid, "hi": hi,
            "bait": bait, "bait_cut": bait_cut,
            "building": building, "jibun_status": jibun_status, "jibun": jj, "by_from_ledger": by_from_ledger,
            "know_build_year": know_by, "pct": pct, "n": len(same),
            "level": level, "same": same.sort_values("계약일", ascending=False)}


# ---------------------------------------------------------------
# 6. 같은 예산 추천 (실제 계약 기준)
# ---------------------------------------------------------------
AREA_LABEL = {"(0, 15]": "15㎡ 이하", "(15, 20]": "15~20㎡", "(20, 25]": "20~25㎡", "(25, 33]": "25~33㎡"}


def recommend(data, max_deposit, max_rent, kinds=None, min_area=0, months=REC_MONTHS,
              min_n=REC_MIN_N, top=8, end=None):
    """예산(보증금·월세 상한) 안에서 실제로 계약이 많이 이뤄진 동·유형·면적 조합을 찾는다.

    - 최근 months개월 계약만 본다 (월세가 계속 올라서 오래된 계약은 지금 시세와 다름)
    - 보증금이 예산 이하인 계약만 비교 대상 (보증금을 더 낼 수 없으니까)
    - '예산 안 비율' = 그 조합의 계약 중 월세가 예산 이하였던 비율 → 높을수록 구하기 쉬움
    """
    end = pd.Timestamp(end) if end is not None else data["계약일"].max()
    d = data[(data["계약일"] > end - pd.DateOffset(months=months)) & (data["계약일"] <= end)]
    d = d[(d["보증금"] <= max_deposit) & (d["면적"] >= min_area)]
    if kinds:
        d = d[d["유형"].isin(kinds)]
    d = add_bins(d)
    g = d.groupby(["동", "유형", "면적구간"])
    t = pd.DataFrame({
        "계약수": g.size(),
        "월세 중앙값": g["월세"].median(),
        "예산 안 비율": g["월세"].apply(lambda x: (x <= max_rent).mean() * 100),
        "예산 안 계약": g["월세"].apply(lambda x: int((x <= max_rent).sum())),
        "평균 면적": g["면적"].mean(),
        "건축년도 중앙값": g["건축년도"].median(),
    }).reset_index()
    t = t[(t["계약수"] >= min_n) & (t["예산 안 계약"] > 0)]
    t["면적"] = t["면적구간"].map(AREA_LABEL).fillna(t["면적구간"])
    # 구하기 쉬운 순서(예산 안 비율), 같으면 넓은 방 먼저
    t = t.sort_values(["예산 안 비율", "평균 면적"], ascending=[False, False])
    return t.head(top).reset_index(drop=True), len(d), end


# ---------------------------------------------------------------
# 7. 건축물대장 (연립다세대 전용) — notebooks/05~07, docs/팀합의_건축물대장_적용.md
# ---------------------------------------------------------------
def norm_jibun(j):
    """'222-23', ' 222 - 23 ', '222-0' → 비교하기 쉬운 형태로"""
    if j is None or (isinstance(j, float) and np.isnan(j)):
        return None
    j = str(j).replace(" ", "").strip()
    if not j:
        return None
    if j.endswith("-0"):
        j = j[:-2]
    return j


def load_buildings(path):
    bld = pd.read_csv(path, dtype={"지번": str})
    bld["지번"] = bld["지번"].map(norm_jibun)
    return bld.drop_duplicates(["동", "지번"])


def attach_buildings(df, bld):
    """실거래(또는 입력 한 줄)에 동+지번으로 건물정보를 붙인다. 못 찾으면 빈칸."""
    out = df.drop(columns=[c for c in BLD_FEATS + ["승인연도"] if c in df.columns]).copy()
    out["지번"] = out["지번"].map(norm_jibun)
    return out.merge(bld[["동", "지번", "승인연도"] + BLD_FEATS], on=["동", "지번"], how="left")


class BuildingModel(RentModel):
    """연립다세대·오피스텔 거래로 학습한 '건물정보 포함' 분위수 모델 (실험 07과 같은 설정).
    화면에서는 연립다세대 + 지번으로 건물을 찾았을 때만 쓴다."""
    def fit(self, train_bld):
        tr = train_bld[train_bld["유형"].isin([BLD_KIND, "오피스텔"])]
        self.cat_levels = {c: sorted(tr[c].dropna().unique()) for c in CATS}
        self.now = tr["계약일"].max()
        X, y = self.make_X(tr), tr["월세"]
        self.full = {k: self._fit(X[FEATS_BLD], y, a) for k, a in [("lo", LO_A), ("mid", 0.5), ("hi", HI_A)]}
        return self

    def predict(self, df, use_build_year=True):
        X = self.make_X(df)
        for c in BLD_FEATS:
            X[c] = pd.to_numeric(X[c], errors="coerce")
        out = np.column_stack([self.full[k].predict(X[FEATS_BLD]) for k in ["lo", "mid", "hi"]])
        out = np.sort(out, axis=1)
        return out[:, 0], out[:, 1], out[:, 2]


def evaluate_building(data_bld, window=None):
    """성적표용: 연립다세대 + 건물 연결된 시험 계약에서 '지금 모델' vs '건물정보 모델'"""
    start, end = window or test_window(data_bld)
    train = data_bld[data_bld["계약일"] < start]
    test = data_bld[(data_bld["계약일"] >= start) & (data_bld["계약일"] <= end)]
    test = test[(test["유형"] == BLD_KIND) & test["지상층수"].notna()]
    y = test["월세"].values
    base = RentModel().fit(train)
    lo, mid, hi = base.predict(test, use_build_year=True)
    rows = [_score(y, mid, lo, hi, "지금 모델 (건축년도 앎)")]
    bm = BuildingModel().fit(train)
    lo, mid, hi = bm.predict(test)
    rows.append(_score(y, mid, lo, hi, "건물정보 추가 모델"))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# 8. 보증금 바꾸면? (전월세 전환율 공식 — 모델은 쓰지 않음, 보증금 역설 때문)
# ---------------------------------------------------------------
def load_conv(path):
    """한국부동산원 인천 전월세 전환율 (notebooks/10에서 받음). {유형: {전환율, 기준월, 출처}}"""
    t = pd.read_csv(path)
    return {r["유형"]: r.to_dict() for _, r in t.iterrows()}


def convert_rent(rent, deposit, new_deposit, rate):
    """보증금을 new_deposit으로 바꿀 때의 월세 = 지금 월세 - (보증금 차이 × 전환율 ÷ 12)
    보증금을 올리면 월세가 줄고, 내리면 늘어난다. (금액 단위: 만 원, 전환율 단위: %)"""
    return max(0.0, rent - (new_deposit - deposit) * rate / 100 / 12)
