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
TEST_START, TEST_END = "2026-03-01", "2026-08-31"   # 성적표용 시험 기간 (9월은 신고 지연으로 제외)
WARN_N = 20                      # 근거 거래가 이보다 적으면 화면에 경고
MIN_N = 5                        # 기준선에서 한 조건에 필요한 최소 거래 수

PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=15,
              min_child_samples=20, random_state=42, verbose=-1)
FEATS = ["동", "유형", "면적", "보증금", "층", "건축년도", "경과월"]
FEATS_NB = [f for f in FEATS if f != "건축년도"]     # 건축년도 모를 때 쓰는 모델
CATS = ["동", "유형"]

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

    keep = ["유형", "umdNm", "면적", "floor", "buildYear", "deposit", "monthlyRent", "계약일"]
    d = d[keep].rename(columns={"umdNm": "동", "floor": "층", "buildYear": "건축년도",
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


def evaluate(data):
    train = data[data["계약일"] < TEST_START]
    test = data[(data["계약일"] >= TEST_START) & (data["계약일"] <= TEST_END)]
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
def diagnose(model, train_b, tables, dong, kind, area, deposit, rent, floor=None, build_year=None):
    know_by = build_year is not None and not pd.isna(build_year)
    row = pd.DataFrame([{"동": dong, "유형": kind, "면적": area, "보증금": deposit,
                         "층": floor if floor else np.nan,
                         "건축년도": build_year if know_by else np.nan}])
    lo, mid, hi = (v[0] for v in model.predict(row, use_build_year=know_by))
    # 화면에 보이는 숫자(만 원 단위 정수)와 판정 기준을 똑같이 맞춘다
    lo, mid, hi = round(lo), round(mid), round(hi)

    # 신호는 AI 범위 하나로만 정한다 (팀 결정)
    signal = "저렴" if rent < lo else ("비쌈" if rent > hi else "적정")

    # 근거: 비슷한 실제 계약 중 몇 % 위치인가 (참고용)
    rb = add_bins(row).iloc[0]
    *_, n, level = baseline_predict(rb, tables)
    same = comparables(train_b, rb, level) if level != "없음" else train_b.iloc[0:0]
    pct = (same["월세"] <= rent).mean() * 100 if len(same) else np.nan

    return {"signal": signal, "lo": lo, "mid": mid, "hi": hi,
            "know_build_year": know_by, "pct": pct, "n": len(same),
            "level": level, "same": same.sort_values("계약일", ascending=False)}
