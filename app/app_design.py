"""
원룸 월세 적정가 진단 — Streamlit 화면 (디자인 시스템 적용 시안)
app.py와 계산은 같고, 화면만 '적정월세' 디자인 시스템(흰 바탕 + 잉크 + Rausch 한 색)으로 바꾼 버전입니다.
실행:  streamlit run app_design.py --theme.base=light --theme.primaryColor=#ff385c
"""
from pathlib import Path
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

import rent_core as rc

DATA_PATH = Path(__file__).parent / "data" / "raw_3년.csv"

# ── 디자인 토큰 ────────────────────────────────────────────────
PRIMARY = "#ff385c"          # Rausch: 진단하기 버튼, '내 월세' 표시에만
INK, BODY, MUTED = "#222222", "#3f3f3f", "#6a6a6a"
HAIRLINE, HAIRLINE_SOFT, BORDER_STRONG = "#dddddd", "#ebebeb", "#c1c1c1"
SURFACE_SOFT, SURFACE_STRONG = "#f7f7f7", "#f2f2f2"
FONT = '"Inter", "Noto Sans KR", -apple-system, system-ui, "Malgun Gothic", sans-serif'
SIGNAL = {   # 신호 색은 항상 글자와 함께 (색만으로 구분하지 않음)
    "저렴": {"fg": "#006c70", "bg": "#e6f3f3", "text": "보다 낮아요"},
    "적정": {"fg": INK,       "bg": SURFACE_STRONG, "text": " 안에 있어요"},
    "비쌈": {"fg": "#c13515", "bg": "#fff0ec", "text": "보다 높아요"},
}
TILDE = "&#126;"   # 마크다운이 ~ 를 취소선으로 읽지 않게

st.set_page_config(page_title="적정월세 · 원룸 월세 적정가 진단", page_icon="🏠", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap');
:root{--primary:#ff385c;--primary-active:#e00b41;--ink:#222;--body:#3f3f3f;--muted:#6a6a6a;
  --hairline:#ddd;--hairline-soft:#ebebeb;--surface-soft:#f7f7f7;--surface-strong:#f2f2f2;
  --shadow-float:rgba(0,0,0,.02) 0 0 0 1px, rgba(0,0,0,.04) 0 2px 6px 0, rgba(0,0,0,.1) 0 4px 8px 0;}
html, body, [class*="st-"], .stMarkdown, button, input, textarea, select {
  font-family: "Inter","Noto Sans KR",-apple-system,system-ui,"Malgun Gothic",sans-serif !important; }
[data-testid="stIconMaterial"], .material-symbols-rounded{font-family:"Material Symbols Rounded" !important}
.stApp{background:#fff;color:var(--ink)}
[data-testid="stHeader"]{background:transparent;height:0}
[data-testid="stMainBlockContainer"], .block-container{max-width:1080px;padding-top:0 !important;padding-bottom:64px}

/* 상단 내비 */
.fr-nav{display:flex;align-items:center;justify-content:space-between;height:80px;
  border-bottom:1px solid var(--hairline);margin:0 0 40px}
.fr-wordmark{color:var(--primary);font-weight:700;font-size:22px;letter-spacing:-.4px}
.fr-nav-meta{color:var(--muted);font-size:14px}
.fr-hero h1{font-size:28px !important;font-weight:700 !important;line-height:1.43 !important;margin:0 !important;padding:0 !important;color:var(--ink)}
.fr-hero p{color:var(--muted);font-size:14px;margin:4px 0 24px}

/* 탭: 잉크 밑줄 */
[data-baseweb="tab-list"]{gap:32px;border-bottom:1px solid var(--hairline)}
[data-baseweb="tab"]{padding:12px 0 !important;background:transparent !important}
[data-baseweb="tab"] p{font-size:16px !important;font-weight:600 !important;color:var(--muted)}
[data-testid="stTab"] p{font-size:16px !important;font-weight:600 !important;color:var(--muted) !important}
[data-testid="stTab"][aria-selected="true"], [data-testid="stTab"][aria-selected="true"] *{color:var(--ink) !important}
.react-aria-SelectionIndicator{background:var(--ink) !important;border-color:var(--ink) !important}
[data-baseweb="tab-highlight"]{background:var(--ink) !important;height:2px !important}
[data-baseweb="tab-border"]{display:none}

/* 입력 카드 */
[data-testid="stForm"]{border:none !important;border-radius:32px;box-shadow:var(--shadow-float);padding:24px 28px 20px !important;margin-top:24px}
[data-testid="stWidgetLabel"] p{font-size:14px !important;font-weight:500 !important;color:var(--ink)}
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"]{
  border-radius:8px !important;background:#fff !important}
[data-baseweb="input"]{border:1px solid var(--hairline) !important}
[data-baseweb="input"] *, [data-baseweb="select"] *, [data-baseweb="base-input"] *, [data-testid="stNumberInputContainer"] button{background:#fff !important}
[data-baseweb="input"]:focus-within{border:2px solid var(--ink) !important}
[data-baseweb="select"] > div{border:1px solid var(--hairline) !important;min-height:48px}
[data-testid="stNumberInputContainer"] input{height:46px}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]{background:#fff !important}

/* 버튼 */
button[kind="primary"], button[kind="primaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"]{
  background:var(--primary) !important;border:none !important;border-radius:8px !important;
  min-height:48px;font-size:16px !important;font-weight:500 !important;color:#fff !important}
button[kind="primaryFormSubmit"]:active{background:var(--primary-active) !important}
button[kind="primaryFormSubmit"] p{font-size:16px !important;font-weight:500 !important}

/* 결과 카드 (VerdictCard) */
.fr-verdict{border:1px solid var(--hairline);border-radius:14px;box-shadow:var(--shadow-float);padding:24px;background:#fff}
.fr-badge{display:inline-flex;align-items:center;gap:6px;border-radius:9999px;padding:6px 12px;font-size:14px;font-weight:600}
.fr-badge i{width:8px;height:8px;border-radius:50%;display:inline-block}
.fr-label{color:var(--muted);font-size:14px;font-weight:500;margin:20px 0 2px}
.fr-big{font-size:64px;font-weight:700;line-height:1.1;letter-spacing:-1px;color:var(--ink);font-variant-numeric:tabular-nums}
.fr-big small{font-size:20px;font-weight:600;letter-spacing:0;margin-left:6px}
.fr-sentence{font-size:16px;line-height:1.6;color:var(--ink);margin:12px 0 0}
.fr-stats{display:grid;grid-template-columns:1fr 1.15fr .9fr;border-top:1px solid var(--hairline);margin-top:20px;padding-top:16px}
.fr-stats div{padding-right:8px}
.fr-stats div + div{border-left:1px solid var(--hairline);padding-left:12px}
.fr-stats b{display:block;white-space:nowrap;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--ink)}
.fr-stats span{font-size:12px;color:var(--muted);white-space:nowrap}
.fr-fee{margin-top:16px;font-size:13px;color:var(--muted)}

/* 알림 */
.fr-notice{border-radius:14px;padding:12px 16px;font-size:14px;line-height:1.5;margin:12px 0 0}
.fr-notice.info{background:var(--surface-soft);color:var(--ink)}
.fr-notice.warn{background:#fff0ec;color:#c13515}
.fr-notice b{font-weight:600}

/* 구역 제목 */
.fr-h2{font-size:21px;font-weight:700;line-height:1.43;margin:0 0 2px;color:var(--ink)}
.fr-h1{font-size:22px;font-weight:500;letter-spacing:-.44px;margin:8px 0 4px}
.fr-sub{font-size:14px;color:var(--muted);margin:0 0 8px}
.fr-section{margin-top:48px}

/* 표 */
.fr-table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.fr-table th{text-align:left;font-weight:500;color:var(--muted);padding:10px 8px;border-bottom:1px solid var(--hairline)}
.fr-table th, .fr-table td{border-left:none !important;border-right:none !important;border-top:none !important}
.fr-table{border:none !important}
.fr-table td{padding:12px 8px;border-bottom:1px solid var(--hairline-soft);color:var(--ink)}
.fr-table td.num, .fr-table th.num{text-align:right}
.fr-table tr.ours td{font-weight:600}
.fr-list{padding-left:18px;color:var(--body);line-height:1.8}

[data-testid="stExpander"] details{border:1px solid var(--hairline);border-radius:14px}
hr{border-color:var(--hairline-soft)}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@alt.theme.register("fair_rent", enable=True)
def chart_theme():
    return alt.theme.ThemeConfig({"config": {
        "font": FONT, "background": "#ffffff",
        "view": {"stroke": None},
        "axis": {"labelColor": MUTED, "titleColor": MUTED, "labelFontSize": 12, "titleFontSize": 12,
                 "titleFontWeight": 500, "domainColor": HAIRLINE, "tickColor": HAIRLINE, "grid": False},
        "axisY": {"grid": True, "gridColor": HAIRLINE_SOFT, "domain": False, "ticks": False},
    }})


# ---------------------------------------------------------------
# 데이터·모델 준비 (app.py와 동일)
# ---------------------------------------------------------------
@st.cache_resource(show_spinner="데이터를 정리하고 모델을 학습하는 중입니다 (10초 정도)...")
def load_all():
    raw = pd.read_csv(DATA_PATH, dtype=str)
    data, log = rc.clean(raw)
    score, period = rc.evaluate(data)
    model = rc.RentModel().fit(data)
    train_b = rc.add_bins(data)
    tables = rc.build_tables(train_b)
    return data, log, score, period, model, train_b, tables


data, log, score, period, model, train_b, tables = load_all()
dongs = data["동"].value_counts().index.tolist()

st.markdown(
    f"""<div class="fr-nav"><span class="fr-wordmark">적정월세</span>
    <span class="fr-nav-meta">인천 미추홀구 · 원룸 {len(data):,}건 실거래 기준</span></div>
    <div class="fr-hero"><h1>이 월세, 적정한가요?</h1>
    <p>국토교통부 전월세 실거래가 {data['계약일'].min():%Y.%m}{TILDE}{data['계약일'].max():%Y.%m} ·
    원룸(33㎡ 이하) 실제 계약으로 학습한 AI가 적정 범위를 알려드려요.</p></div>""",
    unsafe_allow_html=True)

tab_dx, tab_score, tab_data = st.tabs(["진단하기", "예측 성적표", "데이터와 한계"])


def notice(text, kind="info"):
    st.markdown(f'<div class="fr-notice {kind}">{text}</div>', unsafe_allow_html=True)


def position_text(pct):
    if np.isnan(pct):
        return "—"
    if pct >= 99:
        return "가장 비싼 편"
    if pct <= 1:
        return "가장 싼 편"
    return f"하위 {pct:.0f}%" if pct <= 50 else f"상위 {100 - pct:.0f}%"


# ---------------------------------------------------------------
# 탭 1. 진단하기
# ---------------------------------------------------------------
with tab_dx:
    with st.form("input"):
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
            st.markdown("<div style='height:34px'></div>", unsafe_allow_html=True)
            unknown_by = st.checkbox("건축년도 모름", value=True)
        st.form_submit_button("진단하기", type="primary", use_container_width=True)

    r = rc.diagnose(model, train_b, tables, dong, kind, area, deposit, rent,
                    floor=floor or None, build_year=None if unknown_by else build_year)
    s = SIGNAL[r["signal"]]
    lo, mid, hi = int(r["lo"]), int(r["mid"]), int(r["hi"])

    st.markdown(f'<div class="fr-section"></div><div class="fr-h1">{dong} · {kind} · {area:g}㎡</div>'
                f'<div class="fr-sub">보증금 {deposit:,}만 원 · 월세 {rent}만 원'
                f'{"" if unknown_by else f" · {build_year}년 준공"}</div>', unsafe_allow_html=True)

    left, right = st.columns([1.75, 1], gap="large")

    # ── 오른쪽: 결과 카드 ─────────────────────────────────────
    with right:
        st.markdown(
            f"""<div class="fr-verdict">
              <span class="fr-badge" style="background:{s['bg']};color:{s['fg']}"><i style="background:{s['fg']}"></i>{r['signal']}</span>
              <div class="fr-label">AI 적정 범위</div>
              <div class="fr-big">{lo}{TILDE}{hi}<small>만 원</small></div>
              <p class="fr-sentence">입력하신 월세 <b>{rent}만 원</b>은 AI 적정 범위{s['text']}.</p>
              <div class="fr-stats">
                <div><b>{mid}만 원</b><span>AI 예상 중앙값</span></div>
                <div><b>{position_text(r['pct'])}</b><span>비슷한 계약 중</span></div>
                <div><b>{r['n']:,}건</b><span>근거 거래</span></div>
              </div>
              <div class="fr-fee">관리비 별도 · 신호는 AI 범위로만 정해요</div>
            </div>""", unsafe_allow_html=True)
        if r["n"] < rc.WARN_N:
            notice(f"<b>근거가 부족해요.</b> 비슷한 실제 계약이 {r['n']}건뿐이라 참고만 하세요.", "warn")
        if not r["know_build_year"]:
            notice("건축년도를 넣으면 평균 오차가 약 5.0만 원 → 4.5만 원으로 줄어요.")
        if kind == "단독다가구" and floor:
            notice("단독다가구는 실거래 데이터에 층이 없어 층은 반영되지 않았어요.")

    # ── 왼쪽: 범위 막대 + 분포 + 근거 목록 ───────────────────────
    with left:
        st.markdown('<div class="fr-h2">내 월세는 범위의 어디쯤일까?</div>'
                    '<div class="fr-sub">검은 띠가 AI 적정 범위, 빨간 점이 입력하신 월세예요.</div>',
                    unsafe_allow_html=True)
        x_min, x_max = min(lo, rent) - 8, max(hi, rent) + 8
        x = alt.X("v:Q", scale=alt.Scale(domain=[x_min, x_max], nice=False),
                  axis=alt.Axis(grid=False, tickCount=8, format="d", title="월세 (만 원)", domain=False))
        y = alt.Y("y:Q", scale=alt.Scale(domain=[0, 1]), axis=None)
        track = alt.Chart(pd.DataFrame([{"v": x_min, "v2": x_max, "y": .42, "y2": .54}])).mark_rect(
            color=HAIRLINE_SOFT, cornerRadius=6).encode(x=x, x2="v2:Q", y=y, y2="y2:Q")
        band = alt.Chart(pd.DataFrame([{"v": lo, "v2": hi, "y": .42, "y2": .54}])).mark_rect(
            color=INK, cornerRadius=6).encode(x=x, x2="v2:Q", y=y, y2="y2:Q",
            tooltip=[alt.Tooltip("v:Q", title="범위 시작"), alt.Tooltip("v2:Q", title="범위 끝")])
        ends = alt.Chart(pd.DataFrame([{"v": lo, "y": .18, "t": f"{lo}"}, {"v": hi, "y": .18, "t": f"{hi}"}])
                         ).mark_text(color=INK, fontSize=12, fontWeight=700).encode(x=x, y=y, text="t:N")
        me = pd.DataFrame([{"v": rent, "y": .48, "label": f"내 월세 {rent}"}])
        dot = alt.Chart(me).mark_circle(size=320, color=PRIMARY, stroke="white", strokeWidth=3,
                                        opacity=1).encode(x=x, y=y, tooltip=[alt.Tooltip("v:Q", title="입력 월세")])
        dot_label = alt.Chart(me.assign(y=.85)).mark_text(fontWeight=700, color=INK, fontSize=13).encode(
            x=x, y=y, text="label:N")
        st.altair_chart((track + band + ends + dot + dot_label).properties(height=130),
                        use_container_width=True, theme=None)

        same = r["same"]
        if len(same):
            st.markdown(f'<div class="fr-section"></div><div class="fr-h2">비슷한 실제 계약 {len(same):,}건</div>'
                        f'<div class="fr-sub">조건: {r["level"]} (보증금 구간 포함) · 국토교통부 실거래가</div>',
                        unsafe_allow_html=True)
            step = 2
            b = (np.floor(same["월세"] / step) * step).value_counts().sort_index().reset_index()
            b.columns = ["s", "n"]
            b["e"] = b["s"] + step
            my_bin = np.floor(rent / step) * step
            b["구분"] = np.where(b["s"] == my_bin, "내 월세",
                               np.where((b["e"] > lo) & (b["s"] <= hi), "AI 적정 범위", "범위 밖"))
            hist = alt.Chart(b).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("s:Q", title="월세 (만 원)", axis=alt.Axis(format="d")),
                x2="e:Q",
                y=alt.Y("n:Q", title="계약 건수", axis=alt.Axis(tickCount=4)), y2=alt.datum(0),
                color=alt.Color("구분:N", scale=alt.Scale(domain=["범위 밖", "AI 적정 범위", "내 월세"],
                                                        range=[HAIRLINE, INK, PRIMARY]),
                                legend=alt.Legend(orient="top", title=None, labelColor=MUTED, symbolType="circle")),
                tooltip=[alt.Tooltip("s:Q", title="월세 구간 시작"), alt.Tooltip("n:Q", title="건수")])
            st.altair_chart(hist.properties(height=220), use_container_width=True, theme=None)

            with st.expander("근거 거래 목록 보기 (최근 계약 20건)"):
                show = same.head(20)[["계약일", "동", "유형", "면적", "층", "건축년도", "보증금", "월세"]].copy()
                show["계약일"] = show["계약일"].dt.strftime("%Y.%m.%d")
                st.dataframe(show, hide_index=True, use_container_width=True)

    st.markdown('<div class="fr-sub" style="margin-top:32px">관리비는 실거래 데이터에 없어서 반영되지 않았어요. '
                '이 결과는 참고용이며 실제 계약 전 현장 확인이 필요합니다.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------
# 탭 2. 예측 성적표
# ---------------------------------------------------------------
with tab_score:
    st.markdown('<div style="height:24px"></div><div class="fr-h2">예측이 실제 계약과 얼마나 맞았나</div>'
                f'<div class="fr-sub">{period.replace("~", TILDE)} · 과거 거래로만 학습하고 이후 계약으로 시험했어요.</div>',
                unsafe_allow_html=True)
    cols = ["평균 오차(만원)", "±5만원 이내(%)", "범위 적중(%)"]
    rows = "".join(
        f'<tr class="{"ours" if row["방법"].startswith("LightGBM") else ""}"><td>{row["방법"]}</td>'
        f'<td class="num">{row["시험건수"]:,}</td>' + "".join(f'<td class="num">{row[c]}</td>' for c in cols) + "</tr>"
        for _, row in score.iterrows())
    st.markdown(f'<table class="fr-table"><tr><th>방법</th><th class="num">시험 건수</th>'
                f'<th class="num">평균 오차 (만 원)</th><th class="num">±5만 원 이내 (%)</th>'
                f'<th class="num">범위 적중 (%)</th></tr>{rows}</table>', unsafe_allow_html=True)
    st.markdown('<ul class="fr-list" style="margin-top:16px">'
                '<li><b>평균 오차</b>: 예측 월세와 실제 월세의 차이 평균이에요.</li>'
                '<li><b>범위 적중</b>: 실제 월세가 예측 범위 안에 들어간 비율이에요. AI 범위는 실제 계약의 '
                '<b>약 절반</b>이 들어오도록 맞춘 범위라 50% 근처가 목표예요.</li></ul>', unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown('<div class="fr-section"></div><div class="fr-h2">평균 오차</div>'
                    '<div class="fr-sub">낮을수록 좋아요</div>', unsafe_allow_html=True)
        mae = score[["방법", "평균 오차(만원)"]].assign(
            구분=lambda d: np.where(d["방법"].str.startswith("LightGBM"), "AI", "비교"))
        bars = alt.Chart(mae).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=18).encode(
            x=alt.X("평균 오차(만원):Q", title=None),
            y=alt.Y("방법:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelColor=INK)),
            color=alt.Color("구분:N", scale=alt.Scale(domain=["AI", "비교"], range=[INK, BORDER_STRONG]),
                            legend=None),
            tooltip=["방법", "평균 오차(만원)"])
        labels = bars.mark_text(align="left", dx=4, color=INK, fontWeight=600).encode(
            text=alt.Text("평균 오차(만원):Q", format=".2f"), color=alt.value(INK))
        st.altair_chart((bars + labels).properties(height=alt.Step(36)), use_container_width=True, theme=None)
    with c2:
        st.markdown('<div class="fr-section"></div><div class="fr-h2">AI가 많이 참고한 정보</div>'
                    '<div class="fr-sub">중요도 (%)</div>', unsafe_allow_html=True)
        imp = model.importance().round(1).reset_index()
        imp.columns = ["정보", "중요도(%)"]
        ibars = alt.Chart(imp).mark_bar(color=INK, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                        height=14).encode(
            x=alt.X("중요도(%):Q", title=None),
            y=alt.Y("정보:N", sort="-x", title=None, axis=alt.Axis(labelColor=INK)),
            tooltip=["정보", "중요도(%)"])
        ilabels = ibars.mark_text(align="left", dx=4, color=INK).encode(text="중요도(%):Q")
        st.altair_chart((ibars + ilabels).properties(height=alt.Step(28)), use_container_width=True, theme=None)

# ---------------------------------------------------------------
# 탭 3. 데이터와 한계
# ---------------------------------------------------------------
with tab_data:
    c1, c2 = st.columns([1, 1.2], gap="large")
    with c1:
        st.markdown('<div style="height:24px"></div><div class="fr-h2">데이터 정제 과정</div>'
                    '<div class="fr-sub">원본에서 원룸 월세 계약만 남기기까지</div>', unsafe_allow_html=True)
        rows = "".join(f'<tr><td>{a}</td><td class="num">{int(b):,}</td></tr>' for a, b in log.values)
        st.markdown(f'<table class="fr-table"><tr><th>단계</th><th class="num">남은 건수</th></tr>{rows}</table>',
                    unsafe_allow_html=True)
    with c2:
        st.markdown('<div style="height:24px"></div><div class="fr-h2">알고 쓰세요</div>'
                    '<div class="fr-sub">이 서비스가 아직 모르는 것</div>'
                    '<ul class="fr-list">'
                    '<li>관리비·옵션·역까지 거리는 실거래 데이터에 없어 반영되지 않아요.</li>'
                    '<li>단독다가구는 데이터에 층과 지번이 없어요.</li>'
                    '<li>보증금 6천만 원 이하이면서 월세 30만 원 이하인 계약은 신고 의무가 없어 일부만 들어 있어요.</li>'
                    '<li>최근 1~2개월 계약은 신고 지연으로 덜 반영되어 있을 수 있어요.</li>'
                    '<li>"보증금을 바꾸면 월세가 얼마?" 계산은 AI 모델로 하지 않아요 (7주차에 전환율 공식으로 추가 예정).</li>'
                    '</ul>'.replace("1~2", f"1{TILDE}2"), unsafe_allow_html=True)
    st.markdown('<div class="fr-sub" style="margin-top:48px;padding-top:16px;border-top:1px solid #ebebeb">'
                '출처: 국토교통부 단독/다가구·연립다세대·오피스텔 전월세 실거래가 자료 (공공데이터포털)</div>',
                unsafe_allow_html=True)
