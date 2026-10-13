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
BLD_PATH = Path(__file__).parent / "data" / "건물정보_정리.csv"   # 건축물대장 (연립다세대 전용)

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
    bld = rc.load_buildings(BLD_PATH)
    data_bld = rc.attach_buildings(data, bld)
    bscore = rc.evaluate_building(data_bld)      # 성적표: 연립다세대 건물정보 효과
    bmodel = rc.BuildingModel().fit(data_bld)    # 서비스용: 3년치 전체로 학습
    return data, log, score, period, model, train_b, tables, bld, bscore, bmodel


data, log, score, period, model, train_b, tables, bld, bscore, bmodel = load_all()
dongs = data["동"].value_counts().index.tolist()          # 거래 많은 동부터

ui.header(len(data), f"{data['계약일'].min():%Y.%m}", f"{data['계약일'].max():%Y.%m}")
tab_dx, tab_rec, tab_score, tab_data = st.tabs(["진단하기", "예산으로 찾기", "예측 성적표", "데이터와 한계"])

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
        jibun = st.text_input("지번 (연립다세대만, 선택)", placeholder="예: 222-23",
                              help="빌라·다세대 매물 정보의 지번을 넣으면 건축물대장(층수·승강기·세대수 등)을 반영해요. "
                                   "다른 유형은 쓰지 않아요.")
        st.form_submit_button("진단하기", type="primary", **ui.stretch(st.form_submit_button))

    # ② 진단 (계산은 rent_core가 한다)
    r = rc.diagnose(model, train_b, tables, dong, kind, area, deposit, rent,
                    floor=floor or None, build_year=None if unknown_by else build_year,
                    jibun=jibun, bmodel=bmodel, bld=bld)

    # ③ 결과 보여주기
    ui.listing_title(dong, kind, area, deposit, rent,
                     build_year=None if unknown_by else build_year, floor=floor or None)
    left, right = st.columns([1.7, 1], gap="large")

    with right:                                  # 결과 카드 + 주의 문구
        ui.verdict_card(r, rent)
        if r["bait"]:
            ui.bait_alert(r)
        elif deposit > rc.BAIT_DEP_MAX:
            ui.notice("보증금 3,000만 원 초과(반전세)는 거래가 적어 미끼매물 경고를 하지 않아요.")
        if r["n"] < rc.WARN_N:
            ui.notice(f"<b>근거가 부족해요.</b> 비슷한 실제 계약이 {r['n']}건뿐이라 참고만 하세요.", "warn")
        ui.building_notice(r)
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

    with st.expander("계약 전 꼭 확인할 것 4가지", expanded=r["bait"]):
        ui.checklist()
    ui.disclaimer()

# ---------------------------------------------------------------
# 탭 2. 예산으로 찾기
# ---------------------------------------------------------------
with tab_rec:
    with st.form("budget"):
        ui.budget_form_title()
        b1, b2, b3, b4 = st.columns(4)
        max_dep = b1.number_input("보증금 최대 (만 원)", min_value=0, max_value=20000, value=300, step=50)
        max_rent = b2.number_input("월세 최대 (만 원, 관리비 제외)", min_value=10, max_value=150, value=35, step=1)
        min_area = b3.number_input("최소 면적 (㎡, 상관없으면 0)", min_value=0.0, max_value=33.0, value=0.0, step=1.0)
        kinds = b4.multiselect("주택 유형", ["단독다가구", "연립다세대", "오피스텔"],
                               default=["단독다가구", "연립다세대", "오피스텔"])
        st.form_submit_button("찾기", type="primary", **ui.stretch(st.form_submit_button))

    rec, n_pool, end = rc.recommend(data, max_dep, max_rent, kinds=kinds, min_area=min_area)
    ui.title(f"보증금 {max_dep:,}만 원 · 월세 {max_rent}만 원으로 구하기 쉬운 곳",
             f"최근 1년({(end - pd.DateOffset(months=rc.REC_MONTHS)):%Y.%m}{ui.T}{end:%Y.%m}) 실제 계약 중 "
             f"보증금이 예산 이하인 {n_pool:,}건 기준")
    if len(rec):
        ui.rec_cards(rec, max_rent)
        ui.rec_caveat()
    else:
        ui.notice("이 예산으로 최근 1년에 계약된 조합이 없어요. 월세나 보증금 상한을 조금 올려 보세요.", "warn")

# ---------------------------------------------------------------
# 탭 3. 예측 성적표
# ---------------------------------------------------------------
with tab_score:
    ui.title("예측이 실제 계약과 얼마나 맞았나",
             f"{period.replace('~', ui.T)} · 과거 거래로만 학습하고 이후 계약으로 시험했어요. "
             "시험 기간은 데이터가 갱신될 때마다 가장 최근 6개월로 바뀌어요(마지막 1개월은 신고 지연으로 제외).", gap="tab")
    ui.kpi_cards(score)
    ui.score_table(score)

    ui.title("건축물대장 정보를 더하면 (연립다세대)",
             "지번으로 건물을 찾으면 층수·승강기·세대수 등을 함께 넣어 예측해요. 같은 시험 계약끼리 비교했어요.")
    ui.building_score(bscore)

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
# 탭 4. 데이터와 한계
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
