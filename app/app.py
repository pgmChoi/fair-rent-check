"""
원룸 월세 적정가 진단 — Streamlit 화면 (화면 순서만 담당)
실행:  cd app  →  python -m streamlit run app.py

파일 역할
- rent_core.py : 정제·모델·진단 계산
- ui.py        : 색·CSS·차트·화면 부품 (어떻게 보이는지)
- app.py       : 무엇을 어떤 순서로 보여줄지 (이 파일)
"""
from pathlib import Path
import pandas as pd
import streamlit as st

import rent_core as rc
import ui

DATA_PATH = Path(__file__).parent / "data" / "raw_3년.csv"

st.set_page_config(page_title="적정월세 · 원룸 월세 적정가 진단", page_icon="🏠", layout="wide")
ui.setup()


# ---------------------------------------------------------------
# 데이터·모델 준비 (처음 한 번만 실행되고 이후에는 저장된 결과를 씀)
# ---------------------------------------------------------------
@st.cache_resource(show_spinner="데이터를 정리하고 모델을 학습하는 중입니다 (10초 정도)...")
def load_all():
    raw = pd.read_csv(DATA_PATH, dtype=str)
    data, log = rc.clean(raw)
    score, period = rc.evaluate(data)            # 성적표: 과거로 학습, 최근 6개월로 시험
    model = rc.RentModel().fit(data)             # 서비스용: 3년치 전체로 학습
    train_b = rc.add_bins(data)
    tables = rc.build_tables(train_b)
    return data, log, score, period, model, train_b, tables


data, log, score, period, model, train_b, tables = load_all()
dongs = data["동"].value_counts().index.tolist()          # 거래 많은 동부터

ui.header(len(data), f"{data['계약일'].min():%Y.%m}", f"{data['계약일'].max():%Y.%m}")
tab_dx, tab_score, tab_data = st.tabs(["진단하기", "예측 성적표", "데이터와 한계"])

# ---------------------------------------------------------------
# 탭 1. 진단하기
# ---------------------------------------------------------------
with tab_dx:
    # ① 매물 정보 입력
    with st.form("input"):
        ui.form_title()
        c1, c2, c3, c4 = st.columns(4)
        dong = c1.selectbox("동", dongs, index=dongs.index("용현동") if "용현동" in dongs else 0)
        kind = c2.selectbox("주택 유형", ["단독다가구", "연립다세대", "오피스텔"],
                            help="직방의 '다가구주택'은 단독다가구, '빌라·다세대'는 연립다세대입니다.")
        area = c3.number_input("전용면적 (㎡)", min_value=8.0, max_value=33.0, value=16.0, step=0.5)
        floor = c4.number_input("층 (모르면 0)", min_value=0, max_value=30, value=0, step=1,
                                help="단독다가구는 실거래 데이터에 층이 없어서 결과에 반영되지 않습니다.")
        c5, c6, c7, c8 = st.columns(4)
        deposit = c5.number_input("보증금 (만 원)", min_value=0, max_value=20000, value=300, step=50)
        rent = c6.number_input("월세 (만 원, 관리비 제외)", min_value=1, max_value=200, value=32, step=1)
        build_year = c7.number_input("건축(준공)년도", min_value=1960, max_value=2026, value=2005, step=1,
                                     help="직방 매물 정보의 '준공' 날짜를 넣으세요.")
        with c8:
            ui.spacer(36)
            unknown_by = st.checkbox("건축년도 모름", value=True)
        st.form_submit_button("진단하기", type="primary", width="stretch")

    # ② 진단 (계산은 rent_core가 한다)
    r = rc.diagnose(model, train_b, tables, dong, kind, area, deposit, rent,
                    floor=floor or None, build_year=None if unknown_by else build_year)

    # ③ 결과 보여주기
    ui.listing_title(dong, kind, area, deposit, rent,
                     build_year=None if unknown_by else build_year, floor=floor or None)
    left, right = st.columns([1.7, 1], gap="large")

    with right:                                  # 결과 카드 + 주의 문구
        ui.verdict_card(r, rent)
        if r["n"] < rc.WARN_N:
            ui.notice(f"<b>근거가 부족해요.</b> 비슷한 실제 계약이 {r['n']}건뿐이라 참고만 하세요.", "warn")
        if not r["know_build_year"]:
            ui.notice("건축년도를 넣으면 평균 오차가 약 5.0만 원 → 4.5만 원으로 줄어요.")
        if kind == "단독다가구" and floor:
            ui.notice("단독다가구는 실거래 데이터에 층이 없어 층은 반영되지 않았어요.")

    with left:                                   # 범위 막대 → 분포 → 근거 목록
        ui.range_bar(r, rent)
        if len(r["same"]):
            ui.histogram(r, rent)
            with st.expander(f"근거 거래 목록 보기 (최근 계약 {min(20, len(r['same']))}건)"):
                ui.comparables_table(r["same"], rent)
        else:
            ui.notice("비슷한 조건의 실제 계약을 찾지 못했어요. AI 범위만 참고하세요.", "warn")

    ui.disclaimer()

# ---------------------------------------------------------------
# 탭 2. 예측 성적표
# ---------------------------------------------------------------
with tab_score:
    ui.title("예측이 실제 계약과 얼마나 맞았나",
             f"{period.replace('~', ui.T)} · 과거 거래로만 학습하고 이후 계약으로 시험했어요.", gap="tab")
    ui.kpi_cards(score)
    ui.score_table(score)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        ui.title("평균 오차", "낮을수록 좋아요 · 검은 막대가 AI")
        ui.mae_chart(score)
    with c2:
        ui.title("AI가 많이 참고한 정보", "중요도 (%)")
        imp = model.importance().round(1).reset_index()
        imp.columns = ["정보", "중요도(%)"]
        ui.importance_chart(imp)

# ---------------------------------------------------------------
# 탭 3. 데이터와 한계
# ---------------------------------------------------------------
with tab_data:
    c1, c2 = st.columns([1, 1.2], gap="large")
    with c1:
        ui.title("데이터 정제 과정", "원본에서 원룸 월세 계약만 남기기까지", gap="tab")
        ui.funnel_table(log)
    with c2:
        ui.title("알고 쓰세요", "이 서비스가 아직 모르는 것", gap="tab")
        ui.limits_list()

ui.footer()
