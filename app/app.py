"""
원룸 월세 적정가 진단 — Streamlit 화면
실행:  streamlit run app.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

import rent_core as rc

DATA_PATH = Path(__file__).parent / "data" / "raw_3년.csv"

# 차트 색 (dataviz 기본 팔레트: 단일 계열은 파랑, 상태색은 신호에만 사용)
BLUE, BLUE_LIGHT = "#2a78d6", "#cde2fb"
INK, INK_2 = "#0b0b0b", "#52514e"
SIGNAL_STYLE = {   # 상태색은 반드시 아이콘 + 글자와 함께
    "저렴": {"color": "#0ca30c", "icon": "▼", "text": "적정 범위보다 낮아요"},
    "적정": {"color": BLUE,      "icon": "●", "text": "적정 범위 안에 있어요"},
    "비쌈": {"color": "#d03b3b", "icon": "▲", "text": "적정 범위보다 높아요"},
}

st.set_page_config(page_title="원룸 월세 적정가 진단", page_icon="🏠", layout="centered")


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

st.title("원룸 월세 적정가 진단")
st.caption(f"인천 미추홀구 · 국토교통부 전월세 실거래가 "
           f"{data['계약일'].min():%Y.%m}\\~{data['계약일'].max():%Y.%m} · 원룸(33㎡ 이하) {len(data):,}건 기준")

tab_dx, tab_score, tab_data = st.tabs(["진단하기", "예측 성적표", "데이터와 한계"])

# ---------------------------------------------------------------
# 탭 1. 진단하기
# ---------------------------------------------------------------
with tab_dx:
    with st.form("input"):
        st.markdown("**매물 정보** — 직방·다방 매물 화면에 나온 값을 그대로 넣으세요.")
        c1, c2 = st.columns(2)
        dong = c1.selectbox("동", dongs, index=dongs.index("용현동") if "용현동" in dongs else 0)
        kind = c2.selectbox("주택 유형", ["단독다가구", "연립다세대", "오피스텔"],
                            help="직방의 '다가구주택'은 단독다가구, '빌라·다세대'는 연립다세대입니다.")
        c3, c4 = st.columns(2)
        area = c3.number_input("전용면적 (㎡)", min_value=8.0, max_value=33.0, value=16.0, step=0.5)
        floor = c4.number_input("층 (모르면 0)", min_value=0, max_value=30, value=0, step=1,
                                help="단독다가구는 실거래 데이터에 층이 없어서 결과에 반영되지 않습니다.")
        c5, c6 = st.columns(2)
        deposit = c5.number_input("보증금 (만 원)", min_value=0, max_value=20000, value=300, step=50)
        rent = c6.number_input("월세 (만 원, 관리비 제외)", min_value=1, max_value=200, value=32, step=1)
        c7, c8 = st.columns([1, 1])
        unknown_by = c8.checkbox("건축년도 모름", value=True)
        build_year = c7.number_input("건축(준공)년도", min_value=1960, max_value=2026, value=2005, step=1,
                                     disabled=False, help="직방 매물 정보의 '준공' 날짜를 넣으세요.")
        submitted = st.form_submit_button("진단하기", type="primary", use_container_width=True)

    r = rc.diagnose(model, train_b, tables, dong, kind, area, deposit, rent,
                    floor=floor or None, build_year=None if unknown_by else build_year)
    s = SIGNAL_STYLE[r["signal"]]

    # ── 결과 카드: 신호(아이콘+글자+색) ───────────────────────────
    st.markdown(
        f"""
        <div style="border:1px solid rgba(128,128,128,.35); border-left:6px solid {s['color']};
                    border-radius:10px; padding:14px 18px; margin:8px 0 4px;">
          <div style="font-size:1.6rem; font-weight:700; color:{s['color']};">{s['icon']} {r['signal']}</div>
          <div style="margin-top:4px;">월세 <b>{rent}만 원</b>(보증금 {deposit:,}만 원)은
               AI가 계산한 적정 범위 <b>{r['lo']:.0f}~{r['hi']:.0f}만 원</b>{'보다 낮아요' if r['signal']=='저렴' else ('보다 높아요' if r['signal']=='비쌈' else ' 안에 있어요')}.</div>
        </div>
        """, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("AI 적정 범위", f"{r['lo']:.0f}~{r['hi']:.0f}만 원")
    m2.metric("AI 예상 중앙값", f"{r['mid']:.0f}만 원")
    def position_text(pct):
        if np.isnan(pct):
            return "—"
        if pct >= 99:
            return "가장 비싼 편"
        if pct <= 1:
            return "가장 싼 편"
        return f"하위 {pct:.0f}%" if pct <= 50 else f"상위 {100 - pct:.0f}%"

    m3.metric("비슷한 실제 계약 중", position_text(r["pct"]),
              help=f"조건: {r['level']} · 근거 {r['n']}건. 신호는 AI 범위로만 정하고, 이 값은 참고용입니다.")

    if not r["know_build_year"]:
        st.info("건축년도를 모르는 상태로 계산했어요. 건축년도를 넣으면 평균 오차가 약 5.0만 원 → 4.5만 원으로 줄어듭니다.")
    if r["n"] < rc.WARN_N:
        st.warning(f"비슷한 실제 계약이 {r['n']}건뿐이라 근거가 부족해요. 결과를 참고만 하세요.")
    if kind == "단독다가구" and floor:
        st.caption("※ 단독다가구는 실거래 데이터에 층이 없어 층은 반영되지 않았어요.")

    # ── 차트 1: 적정 범위 막대 위에 입력 월세 위치 ─────────────────
    st.markdown("##### 내 월세는 적정 범위의 어디쯤일까?")
    x_min = min(r["lo"], rent) - 6
    x_max = max(r["hi"], rent) + 6
    x = alt.X("v:Q", scale=alt.Scale(domain=[x_min, x_max], nice=False),
              axis=alt.Axis(grid=False, tickCount=8, format="d", title="월세 (만 원)"))
    Y = lambda val: alt.Y("y:Q", scale=alt.Scale(domain=[0, 1]), axis=None)  # 세로 위치 고정용
    band_df = pd.DataFrame([{"v": r["lo"], "v2": r["hi"], "y": 0.38, "y2": 0.72,
                             "t": f"AI 적정 범위 {r['lo']:.0f}~{r['hi']:.0f}만 원"}])
    band = alt.Chart(band_df).mark_rect(color=BLUE_LIGHT, cornerRadius=4).encode(
        x=x, x2="v2:Q", y=Y(0), y2="y2:Q",
        tooltip=[alt.Tooltip("v:Q", title="범위 시작", format=".0f"),
                 alt.Tooltip("v2:Q", title="범위 끝", format=".0f")])
    band_label = alt.Chart(band_df.assign(v=(r["lo"] + r["hi"]) / 2, y=0.15)).mark_text(
        color=INK_2, fontSize=12).encode(x=x, y=Y(0), text="t:N")
    median = alt.Chart(pd.DataFrame([{"v": r["mid"], "y": 0.38, "y2": 0.72}])).mark_rule(color=BLUE, strokeWidth=2).encode(
        x=x, y=Y(0), y2="y2:Q",
        tooltip=[alt.Tooltip("v:Q", title="AI 중앙값", format=".0f")])
    me = pd.DataFrame([{"v": rent, "y": 0.55, "label": f"내 월세 {rent}만 원"}])
    dot = alt.Chart(me).mark_point(filled=True, size=220, color=s["color"], stroke="white",
                                   strokeWidth=2, shape="diamond", opacity=1).encode(
        x=x, y=Y(0), tooltip=[alt.Tooltip("v:Q", title="입력 월세")])
    dot_label = alt.Chart(me.assign(y=0.92)).mark_text(fontWeight="bold", color=INK, fontSize=13).encode(
        x=x, y=Y(0), text="label:N")
    st.altair_chart((band + median + dot + dot_label + band_label).properties(height=170),
                    use_container_width=True)

    # ── 차트 2: 비슷한 실제 계약의 월세 분포 ──────────────────────
    same = r["same"]
    if len(same):
        st.markdown(f"##### 비슷한 실제 계약 {len(same)}건의 월세 분포")
        st.caption(f"조건: {r['level']} (보증금 구간 포함) · 국토교통부 실거래가")
        hist = alt.Chart(same).mark_bar(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                        binSpacing=2).encode(
            x=alt.X("월세:Q", bin=alt.Bin(step=2), title="월세 (만 원)", axis=alt.Axis(format="d")),
            y=alt.Y("count():Q", title="계약 건수", axis=alt.Axis(tickCount=4)),
            tooltip=[alt.Tooltip("월세:Q", bin=alt.Bin(step=2), title="월세 구간"),
                     alt.Tooltip("count():Q", title="건수")])
        rule = alt.Chart(pd.DataFrame([{"월세": rent}])).mark_rule(
            color=INK, strokeWidth=2, strokeDash=[4, 3]).encode(x="월세:Q")
        rule_label = alt.Chart(pd.DataFrame([{"월세": rent, "t": f"내 월세 {rent}"}])).mark_text(
            align="left", dx=4, dy=-6, color=INK, fontWeight="bold").encode(
            x="월세:Q", y=alt.value(8), text="t:N")
        st.altair_chart((hist + rule + rule_label).properties(height=220), use_container_width=True)

        with st.expander("근거 거래 목록 보기 (최근 계약 20건)"):
            show = same.head(20)[["계약일", "동", "유형", "면적", "층", "건축년도", "보증금", "월세"]].copy()
            show["계약일"] = show["계약일"].dt.strftime("%Y-%m-%d")
            st.dataframe(show, hide_index=True, use_container_width=True)

    st.caption("※ 관리비는 실거래 데이터에 없어서 반영되지 않았어요. 관리비가 높은 방은 따로 비교하세요. "
               "이 결과는 참고용이며 실제 계약 전 현장 확인이 필요합니다.")

# ---------------------------------------------------------------
# 탭 2. 예측 성적표
# ---------------------------------------------------------------
with tab_score:
    st.markdown("#### 예측이 실제 계약과 얼마나 맞았나")
    st.caption(period.replace("~", "\\~") + " · 과거 거래로만 학습하고 이후 계약으로 시험했습니다.")
    st.dataframe(score, hide_index=True, use_container_width=True)
    st.markdown(
        "- **평균 오차**: 예측 월세와 실제 월세의 차이 평균입니다.\n"
        "- **범위 적중**: 실제 월세가 예측 범위 안에 들어간 비율입니다. AI 범위는 실제 계약의 **약 절반**이 "
        "들어오도록 맞춘 범위라서 50% 근처가 목표입니다. 범위 밖이면 '저렴' 또는 '비쌈'으로 표시합니다.")

    mae = score[["방법", "평균 오차(만원)"]]
    bars = alt.Chart(mae).mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                   height=20).encode(
        x=alt.X("평균 오차(만원):Q", title="평균 오차 (만 원, 낮을수록 좋음)"),
        y=alt.Y("방법:N", sort=None, title=None, axis=alt.Axis(labelLimit=260)),
        tooltip=["방법", "평균 오차(만원)"])
    labels = bars.mark_text(align="left", dx=4, color=INK_2).encode(text=alt.Text("평균 오차(만원):Q", format=".2f"))
    st.altair_chart((bars + labels).properties(height=alt.Step(32)), use_container_width=True)

    st.markdown("#### AI가 많이 참고한 정보")
    imp = model.importance().round(1).reset_index()
    imp.columns = ["정보", "중요도(%)"]
    ibars = alt.Chart(imp).mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                    height=16).encode(
        x=alt.X("중요도(%):Q", title="중요도 (%)"), y=alt.Y("정보:N", sort="-x", title=None),
        tooltip=["정보", "중요도(%)"])
    ilabels = ibars.mark_text(align="left", dx=4, color=INK_2).encode(text="중요도(%):Q")
    st.altair_chart((ibars + ilabels).properties(height=alt.Step(28)), use_container_width=True)

# ---------------------------------------------------------------
# 탭 3. 데이터와 한계
# ---------------------------------------------------------------
with tab_data:
    st.markdown("#### 데이터 정제 과정")
    st.dataframe(log, hide_index=True, use_container_width=True)
    st.markdown("#### 알고 쓰세요")
    st.markdown(
        "- 관리비·옵션·역까지 거리는 실거래 데이터에 없어 반영되지 않습니다.\n"
        "- 단독다가구는 데이터에 층과 지번이 없습니다.\n"
        "- 보증금 6천만 원 이하이면서 월세 30만 원 이하인 계약은 신고 의무가 없어 일부만 들어 있습니다.\n"
        "- 최근 1~2개월 계약은 신고 지연으로 덜 반영되어 있을 수 있습니다.\n"
        "- \"보증금을 바꾸면 월세가 얼마?\" 계산은 AI 모델로 하지 않습니다 (7주차에 전환율 공식으로 추가 예정).")
    st.caption("출처: 국토교통부 단독/다가구·연립다세대·오피스텔 전월세 실거래가 자료 (공공데이터포털)")
