"""
화면 모양 담당 (색·글꼴·CSS·차트·화면 부품)
- 계산은 rent_core.py, 화면 순서는 app.py, '어떻게 보이는지'는 이 파일.
- 색을 바꾸려면 맨 위 '디자인 토큰'만 고치면 된다.

디자인 규칙 (자세한 이유는 CLAUDE.md)
- 바탕 흰색 + 글자 잉크(#222). 버튼·강조도 잉크.
- 빨강은 '비쌈', 파랑은 '저렴' 신호에만. 신호는 항상 글자와 함께 표시(색만으로 구분하지 않음).
- 그림자는 한 단계(카드)만, 모서리는 둥글게.
"""
import inspect
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

# ── 디자인 토큰 (색은 여기서만 정한다) ─────────────────────────
INK, BODY, MUTED = "#222222", "#3f3f3f", "#6a6a6a"
HAIRLINE, HAIRLINE_SOFT = "#dddddd", "#ebebeb"
SURFACE_SOFT, SURFACE_STRONG = "#f7f7f7", "#f2f2f2"
RANGE_BAND, OUT_OF_RANGE = "#bdbdbd", "#e4e4e4"     # AI 범위(차트), 범위 밖 막대
FONT = '"Inter", "Noto Sans KR", -apple-system, system-ui, "Malgun Gothic", sans-serif'
SIGNAL = {   # 흰 바탕 대비: 파랑 5.5:1, 빨강 5.2:1
    "저렴": {"fg": "#1c64d6", "bg": "#eef4fd"},
    "적정": {"fg": INK,       "bg": SURFACE_STRONG},
    "비쌈": {"fg": "#d0263a", "bg": "#fdeeee"},
}
T = "&#126;"   # 물결표. 마크다운이 ~ 를 취소선으로 읽지 않게

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap');
:root{--ink:#222;--body:#3f3f3f;--muted:#6a6a6a;--hairline:#ddd;--hairline-soft:#ebebeb;
--surface-soft:#f7f7f7;--surface-strong:#f2f2f2;
--shadow:rgba(0,0,0,.02) 0 0 0 1px, rgba(0,0,0,.04) 0 2px 6px 0, rgba(0,0,0,.1) 0 4px 8px 0;}
html, body, .stApp, .stMarkdown, button, input, textarea, select, label, p, li, td, th {
font-family:"Inter","Noto Sans KR",-apple-system,system-ui,"Malgun Gothic",sans-serif !important;}
[data-testid="stIconMaterial"], .material-symbols-rounded{font-family:"Material Symbols Rounded" !important}
.stApp{background:#fff;color:var(--ink)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stMainBlockContainer"]{max-width:1080px;padding:0 24px 0 !important}

.fr-nav{display:flex;align-items:center;justify-content:space-between;height:72px;border-bottom:1px solid var(--hairline);margin-bottom:40px}
.fr-wordmark{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;letter-spacing:-.4px;color:var(--ink)}
.fr-mark{width:28px;height:28px;border-radius:8px;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:14px;font-weight:700}
.fr-chip{border:1px solid var(--hairline);border-radius:9999px;padding:6px 14px;font-size:13px;color:var(--ink)}
.fr-hero h1{font-size:30px !important;font-weight:700 !important;line-height:1.35 !important;letter-spacing:-.6px;margin:0 !important;padding:0 !important;color:var(--ink)}
.fr-hero p{color:var(--muted);font-size:15px;line-height:1.6;margin:8px 0 28px}

[data-testid="stTabs"] [role="tablist"]{gap:28px;border-bottom:1px solid var(--hairline)}
[data-testid="stTab"]{padding:12px 0 !important;background:transparent !important}
[data-testid="stTab"] p{font-size:16px !important;font-weight:600 !important;color:var(--muted) !important}
[data-testid="stTab"][aria-selected="true"] p{color:var(--ink) !important}
.react-aria-SelectionIndicator{background:var(--ink) !important;height:2px !important}

[data-testid="stForm"]{border:none !important;border-radius:24px;box-shadow:var(--shadow);padding:28px 28px 24px !important;margin-top:28px;background:#fff}
[data-testid="stWidgetLabel"] p{font-size:14px !important;font-weight:500 !important;color:var(--ink) !important}
[data-testid="stNumberInputContainer"], [data-baseweb="select"] > div,
[data-testid="stSelectbox"] .react-aria-ComboBox, [data-testid="stSelectbox"] .react-aria-ComboBox > div{min-height:48px}
[data-testid="stFormSubmitButton"] button{min-height:52px;border-radius:8px !important;margin-top:8px}
[data-testid="stFormSubmitButton"] button p{font-size:16px !important;font-weight:600 !important}
[data-testid="stFormSubmitButton"] button:hover{background:#000 !important;border-color:#000 !important}

.fr-section{margin-top:56px}
.fr-h1{font-size:22px;font-weight:600;letter-spacing:-.44px;margin:0 0 4px;color:var(--ink)}
.fr-h2{font-size:20px;font-weight:700;line-height:1.4;letter-spacing:-.2px;margin:0 0 2px;color:var(--ink)}
.fr-sub{font-size:14px;line-height:1.5;color:var(--muted);margin:0 0 12px}

.fr-card{border:1px solid var(--hairline);border-radius:16px;box-shadow:var(--shadow);padding:24px;background:#fff}
.fr-badge{display:inline-flex;align-items:center;gap:6px;border-radius:9999px;padding:6px 12px;font-size:14px;font-weight:700}
.fr-badge i{width:8px;height:8px;border-radius:50%;display:inline-block}
.fr-label{color:var(--muted);font-size:14px;font-weight:500;margin:20px 0 4px}
.fr-big{font-size:60px;font-weight:700;line-height:1.05;letter-spacing:-1.5px;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.fr-big small{font-size:18px;font-weight:600;letter-spacing:0;margin-left:6px}
.fr-sentence{font-size:16px;line-height:1.6;color:var(--ink);margin:14px 0 0}
.fr-stats{display:grid;grid-template-columns:1fr 1.15fr .9fr;border-top:1px solid var(--hairline);margin-top:20px;padding-top:16px}
.fr-stats div + div{border-left:1px solid var(--hairline);padding-left:12px}
.fr-stats b{display:block;font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--ink);white-space:nowrap}
.fr-stats span{font-size:12px;color:var(--muted);white-space:nowrap}
.fr-fee{margin-top:16px;padding-top:12px;border-top:1px solid var(--hairline-soft);font-size:13px;color:var(--muted)}

.fr-legend{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 0}
.fr-legend span{display:inline-flex;align-items:center;gap:6px;border-radius:9999px;padding:4px 10px;font-size:13px;font-weight:500}
.fr-legend i{width:7px;height:7px;border-radius:50%;display:inline-block}
.fr-legend .on{font-weight:700;outline:1.5px solid currentColor}

.fr-notice{border-radius:12px;padding:12px 16px;font-size:14px;line-height:1.55;margin:12px 0 0}
.fr-notice.info{background:var(--surface-soft);color:var(--ink)}
.fr-notice.warn{background:#fdeeee;color:#a51d2d}

.fr-table{width:100%;border-collapse:collapse !important;border:none !important;font-size:14px;font-variant-numeric:tabular-nums;margin:0}
.fr-table th, .fr-table td{border:none !important;border-bottom:1px solid var(--hairline-soft) !important;padding:11px 8px;text-align:left}
.fr-table th{font-weight:500;color:var(--muted);border-bottom:1px solid var(--hairline) !important;white-space:nowrap}
.fr-table td{color:var(--ink)}
.fr-table .num{text-align:right}
.fr-table tr.ours td{font-weight:700}
.fr-table tr.me td{background:var(--surface-soft)}
.fr-list{padding-left:18px;color:var(--body);line-height:1.8;margin:0}

[data-testid="stExpander"] details{border:1px solid var(--hairline) !important;border-radius:12px !important}
[data-testid="stExpander"] summary p{font-weight:600 !important}
[data-testid="stColumn"]:has(.fr-card){position:sticky;top:24px;align-self:flex-start}
.fr-form-title{font-size:18px;font-weight:700;color:var(--ink);margin:0 0 2px}
.fr-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:4px 0 28px}
.fr-kpi{border:1px solid var(--hairline);border-radius:16px;padding:18px 18px 16px}
.fr-kpi b{display:block;font-size:28px;font-weight:700;letter-spacing:-.6px;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1.2}
.fr-kpi b small{font-size:14px;font-weight:600;letter-spacing:0;margin-left:2px}
.fr-kpi span{display:block;font-size:13px;color:var(--muted);margin-top:6px;line-height:1.45}
.fr-kpi .lbl{font-size:13px;font-weight:600;color:var(--ink);margin:0 0 8px}
.fr-bar{height:8px;border-radius:9999px;background:var(--ink);min-width:2px}
.fr-bar-cell{width:45%}
.fr-rec td, .fr-rec th{white-space:nowrap}
.fr-rec .fr-bar-cell{width:26%}
.fr-footer{margin-top:72px;padding:20px 0 40px;border-top:1px solid var(--hairline-soft);font-size:13px;color:var(--muted);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
@media (max-width: 640px){
.fr-kpis{grid-template-columns:repeat(2,1fr)}
.fr-bar-cell{display:none}
.fr-big{font-size:48px}
.fr-hero h1{font-size:24px !important}
.fr-nav .fr-chip{display:none}
}
</style>
"""


# ---------------------------------------------------------------
# 기본 도구
# ---------------------------------------------------------------
def html(s):
    """들여쓴 HTML을 한 줄로 붙여서 출력 (마크다운이 들여쓰기를 코드블록으로 읽지 않게)"""
    st.markdown("".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


@alt.theme.register("fair_rent", enable=True)
def _chart_theme():
    return alt.theme.ThemeConfig({"config": {
        "font": FONT, "background": "#ffffff", "view": {"stroke": None},
        "axis": {"labelColor": MUTED, "titleColor": MUTED, "labelFontSize": 12, "titleFontSize": 12,
                 "titleFontWeight": 500, "domainColor": HAIRLINE, "tickColor": HAIRLINE, "grid": False},
        "axisY": {"grid": True, "gridColor": HAIRLINE_SOFT, "domain": False, "ticks": False},
        "legend": {"labelColor": MUTED, "labelFontSize": 12},
    }})


def stretch(fn):
    """가로로 꽉 채우기 옵션을 Streamlit 버전에 맞게 고른다.
    새 버전은 width="stretch", 옛 버전은 use_container_width=True 만 받는다."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = {}
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


def setup():
    """페이지 맨 처음(st.set_page_config 바로 다음)에 한 번 부른다: CSS 적용"""
    html(CSS)


def show_chart(chart):
    st.altair_chart(chart, theme=None, **stretch(st.altair_chart))


def notice(text, kind="info"):
    """회색 안내(info) 또는 빨간 경고(warn) 상자"""
    html(f'<div class="fr-notice {kind}">{text}</div>')


def title(text, sub="", gap="section"):
    """구역 제목 + 회색 설명. gap: section(넓게) / tab(탭 첫 제목) / none"""
    space = {"section": '<div class="fr-section"></div>',
             "tab": '<div style="height:28px"></div>', "none": ""}[gap]
    html(f'{space}<div class="fr-h2">{text}</div>' + (f'<div class="fr-sub">{sub}</div>' if sub else ""))


def position_text(pct):
    if np.isnan(pct):
        return "—"
    if pct >= 99:
        return "가장 비싼 편"
    if pct <= 1:
        return "가장 싼 편"
    return f"하위 {pct:.0f}%" if pct <= 50 else f"상위 {100 - pct:.0f}%"


# ---------------------------------------------------------------
# 머리와 꼬리
# ---------------------------------------------------------------
def header(n, d_from, d_to):
    html(f"""
    <div class="fr-nav">
      <div class="fr-wordmark"><span class="fr-mark">적</span>적정월세</div>
      <span class="fr-chip">인천 미추홀구 · 원룸 실거래 {n:,}건</span>
    </div>
    <div class="fr-hero">
      <h1>이 월세, 적정한가요?</h1>
      <p>매물 조건을 넣으면 실제 계약 {n:,}건으로 학습한 AI가 적정 월세 범위를 알려드려요.<br>
      국토교통부 전월세 실거래가 {d_from}{T}{d_to} · 원룸(33㎡ 이하)</p>
    </div>
    """)


def footer():
    html('<div class="fr-footer"><span>출처: 국토교통부 단독/다가구·연립다세대·오피스텔 전월세 실거래가 (공공데이터포털)</span>'
         '<span>AI캡스톤디자인 · 적정월세</span></div>')


# ---------------------------------------------------------------
# 탭 1. 진단하기
# ---------------------------------------------------------------
def form_title():
    html('<div class="fr-form-title">매물 정보</div>'
         '<div class="fr-sub">직방·다방 매물 화면에 나온 값을 그대로 넣으세요.</div>')


def paste_help():
    html('<div class="fr-sub">직방(PC)에서 매물 상세 화면 위쪽(<b>월세 300/45 · 관리비</b>)과 '
         '<b>더보기 → 매물 정보</b> 창을 드래그해 복사한 뒤 이어서 붙여 넣으세요. 읽은 값이 아래 칸에 채워져요.</div>')


PASTE_LABEL = {"동": "동", "유형": "주택 유형", "면적": "전용면적", "보증금": "보증금", "월세": "월세",
               "층": "층", "건축년도": "건축년도", "지번": "지번"}


def paste_result(p):
    """붙여넣기에서 읽은 값 / 못 읽은 값 / 주의 문구"""
    f, e = p["found"], p["extra"]
    unit = {"면적": "㎡", "보증금": "만 원", "월세": "만 원", "층": "층", "건축년도": "년"}
    got = " · ".join(f"{PASTE_LABEL[k]} {val}{unit.get(k, '')}" for k, val in f.items())
    ref = " · ".join(f"{k} {val}" for k, val in e.items() if k in ("관리비", "엘리베이터", "주차", "위반건축물", "등록번호"))
    if got:
        notice(f"<b>읽은 값</b>: {got}" + (f"<br><span style='color:var(--muted)'>참고: {ref}</span>" if ref else ""))
    if p["missing"]:
        notice("<b>못 읽은 값</b>: " + ", ".join(PASTE_LABEL[k] for k in p["missing"])
               + " — 아래 칸에서 직접 넣어 주세요.", "warn")
    for m in p["msgs"]:
        notice(m, "warn")


def spacer(px):
    html(f"<div style='height:{px}px'></div>")


def listing_title(dong, kind, area, deposit, rent, build_year=None, floor=None):
    extra = (f" · {build_year}년 준공" if build_year else "") + (f" · {floor}층" if floor else "")
    html(f'<div class="fr-section"></div><div class="fr-h1">{dong} · {kind} · {area:g}㎡</div>'
         f'<div class="fr-sub">보증금 {deposit:,}만 원 · 월세 {rent}만 원{extra}</div>')


def verdict_card(r, rent):
    """오른쪽 결과 카드: 신호 배지, AI 적정 범위, 한 줄 판정, 숫자 3개"""
    sig, s = r["signal"], SIGNAL[r["signal"]]
    lo, mid, hi = int(r["lo"]), int(r["mid"]), int(r["hi"])
    if sig == "저렴":
        verdict = f"AI 적정 범위의 아래쪽 끝보다 <b>{lo - rent}만 원 낮아요</b>."
    elif sig == "비쌈":
        verdict = f"AI 적정 범위의 위쪽 끝보다 <b>{rent - hi}만 원 높아요</b>."
    else:
        verdict = "AI 적정 범위 <b>안에 있어요</b>."
    html(f"""
    <div class="fr-card">
      <span class="fr-badge" style="background:{s['bg']};color:{s['fg']}"><i style="background:{s['fg']}"></i>{sig}</span>
      <div class="fr-label">AI 적정 범위</div>
      <div class="fr-big">{lo}{T}{hi}<small>만 원</small></div>
      <p class="fr-sentence">입력하신 월세 <b>{rent}만 원</b>은 {verdict}</p>
      <div class="fr-stats">
        <div><b>{mid}만 원</b><span>AI 예상 중앙값</span></div>
        <div><b>{position_text(r['pct'])}</b><span>비슷한 계약 중</span></div>
        <div><b>{r['n']:,}건</b><span>근거 거래</span></div>
      </div>
      <div class="fr-fee">관리비 별도 · 신호는 AI 범위로만 정해요</div>
    </div>
    """)


def range_bar(r, rent):
    """회색 띠(AI 범위) 위에 내 월세 점 + 아래에 신호 기준 3칸"""
    sig, s = r["signal"], SIGNAL[r["signal"]]
    lo, mid, hi = int(r["lo"]), int(r["mid"]), int(r["hi"])
    title("내 월세는 범위의 어디쯤일까?",
          "회색 띠가 AI 적정 범위(흰 선은 예상 중앙값), 점이 입력하신 월세예요.", gap="none")
    x_min, x_max = min(lo, rent) - 8, max(hi, rent) + 8
    x = alt.X("v:Q", scale=alt.Scale(domain=[x_min, x_max], nice=False),
              axis=alt.Axis(grid=False, tickCount=8, format="d", title="월세 (만 원)", domain=False))
    y = alt.Y("y:Q", scale=alt.Scale(domain=[0, 1]), axis=None)
    track = alt.Chart(pd.DataFrame([{"v": x_min, "v2": x_max, "y": .40, "y2": .56}])).mark_rect(
        color=HAIRLINE_SOFT, cornerRadius=8).encode(x=x, x2="v2:Q", y=y, y2="y2:Q")
    band = alt.Chart(pd.DataFrame([{"v": lo, "v2": hi, "y": .40, "y2": .56}])).mark_rect(
        color=RANGE_BAND, cornerRadius=8).encode(x=x, x2="v2:Q", y=y, y2="y2:Q",
        tooltip=[alt.Tooltip("v:Q", title="범위 시작"), alt.Tooltip("v2:Q", title="범위 끝")])
    mid_tick = alt.Chart(pd.DataFrame([{"v": mid, "y": .40, "y2": .56}])).mark_rule(
        color="white", strokeWidth=2).encode(x=x, y=y, y2="y2:Q",
        tooltip=[alt.Tooltip("v:Q", title="AI 예상 중앙값")])
    ends = alt.Chart(pd.DataFrame([{"v": lo, "y": .16, "t": f"{lo}"}, {"v": hi, "y": .16, "t": f"{hi}"}])
                     ).mark_text(color=INK, fontSize=12, fontWeight=700).encode(x=x, y=y, text="t:N")
    me = pd.DataFrame([{"v": rent, "y": .48, "label": f"내 월세 {rent}"}])
    dot = alt.Chart(me).mark_circle(size=340, color=s["fg"], stroke="white", strokeWidth=3,
                                    opacity=1).encode(x=x, y=y, tooltip=[alt.Tooltip("v:Q", title="입력 월세")])
    dot_label = alt.Chart(me.assign(y=.86)).mark_text(fontWeight=700, color=s["fg"], fontSize=13).encode(
        x=x, y=y, text="label:N")
    show_chart((track + band + mid_tick + ends + dot + dot_label).properties(height=130))

    def item(name, rule):
        c = SIGNAL[name]
        on = "on" if name == sig else ""
        return (f'<span class="{on}" style="background:{c["bg"]};color:{c["fg"]}">'
                f'<i style="background:{c["fg"]}"></i>{name} {rule}</span>')
    html('<div class="fr-legend">' + item("저렴", f"{lo}만 원 미만")
         + item("적정", f"{lo}{T}{hi}만 원") + item("비쌈", f"{hi}만 원 초과") + '</div>')


def histogram(r, rent, step=2):
    """비슷한 실제 계약의 월세 분포. 범위 밖 연회색 / 범위 안 회색 / 내 월세 신호색"""
    same, s = r["same"], SIGNAL[r["signal"]]
    lo, hi = int(r["lo"]), int(r["hi"])
    title(f"비슷한 실제 계약 {len(same):,}건", f"조건: {r['level']} (보증금 구간 포함) · 국토교통부 실거래가")
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
                                                range=[OUT_OF_RANGE, RANGE_BAND, s["fg"]]),
                        legend=alt.Legend(orient="top", title=None, symbolType="circle")),
        tooltip=[alt.Tooltip("s:Q", title="월세 구간 시작"), alt.Tooltip("n:Q", title="건수")])
    show_chart(hist.properties(height=220))


def comparables_table(same, rent, n=20):
    """근거 거래 목록 (최근 n건). 입력 월세와 같은 계약은 회색 줄"""
    rows = ""
    for _, t in same.head(n).iterrows():
        fl = "—" if pd.isna(t["층"]) else f"{t['층']:.0f}층"
        by = "—" if pd.isna(t["건축년도"]) else f"{t['건축년도']:.0f}"
        me_row = ' class="me"' if round(t["월세"]) == rent else ""
        rows += (f'<tr{me_row}><td>{t["계약일"]:%Y.%m.%d}</td><td>{t["동"]}</td><td>{t["유형"]}</td>'
                 f'<td class="num">{t["면적"]:.1f}㎡</td><td class="num">{fl}</td><td class="num">{by}</td>'
                 f'<td class="num">{t["보증금"]:,.0f}</td><td class="num"><b>{t["월세"]:.0f}</b></td></tr>')
    html('<table class="fr-table"><tr><th>계약일</th><th>동</th><th>유형</th><th class="num">면적</th>'
         '<th class="num">층</th><th class="num">건축</th><th class="num">보증금</th>'
         f'<th class="num">월세</th></tr>{rows}</table>'
         '<div class="fr-sub" style="margin-top:8px">금액 단위: 만 원 · 회색 줄은 입력하신 월세와 같은 계약</div>')


def bait_alert(r):
    """미끼매물 의심 경고 (AI 예상 중앙값의 65% 이하일 때)"""
    notice(f"<b>시세보다 크게 싸요.</b> AI 예상 중앙값 {int(r['mid'])}만 원의 65%인 {r['bait_cut']}만 원 이하예요. "
           "실제 거래에서 이만큼 싼 계약은 약 2%뿐이에요. 허위·미끼매물일 수 있으니 아래 4가지를 꼭 확인하세요.", "warn")


def checklist():
    """계약 전 확인할 것 4가지 (국토부 대학가 광고 단속에서 많이 걸린 유형 기준)"""
    html('<ol class="fr-list">'
         '<li><b>방이 지금도 있나요?</b> 매물번호로 중개사무소에 묻고, 직접 볼 수 있는지 확인하세요. '
         '계약이 끝난 방을 계속 올려 두는 경우가 있어요.</li>'
         '<li><b>전용면적이 맞나요?</b> 건축물대장(정부24에서 열람)의 면적과 광고 면적을 비교하세요.</li>'
         '<li><b>옵션이 실제로 있나요?</b> 광고에 적힌 에어컨·세탁기 등을 방에서 직접 확인하세요.</li>'
         '<li><b>관리비는 얼마이고 무엇이 포함되나요?</b> 금액과 포함 항목(수도·인터넷 등)을 물어보세요. '
         '이 진단은 관리비를 반영하지 않아요.</li></ol>'
         '<div class="fr-sub" style="margin-top:8px">근거: 국토교통부 청년 밀집 대학가 부동산 광고 모니터링(2025.10) — '
         '적발 321건 중 부당표시 52%(면적 과장·없는 옵션·계약 끝난 매물 등), 명시의무 위반 48%(관리비 내역 누락 등)</div>')


def building_notice(r):
    """건축물대장 반영 여부 안내 (연립다세대 + 지번 입력 시)"""
    st_ = r["jibun_status"]
    if st_ == "found":
        b = r["building"]
        parts = [f"지상 {b['지상층수']:.0f}층"]
        if not pd.isna(b["승강기수"]):
            parts.append("승강기 있음" if b["승강기수"] > 0 else "승강기 없음")
        if not pd.isna(b["세대수"]):
            parts.append(f"{b['세대수']:.0f}세대")
        if not pd.isna(b["승인연도"]):
            parts.append(f"{b['승인연도']:.0f}년 사용승인")
        extra = " 건축년도는 대장의 사용승인연도로 채웠어요." if r["by_from_ledger"] else ""
        notice(f"<b>건축물대장 정보를 반영했어요</b> ({' · '.join(parts)}).{extra}")
    elif st_ == "notfound":
        notice(f"지번 {r['jibun']}의 건물을 저장된 건축물대장 목록에서 찾지 못해 기본 방식으로 계산했어요.")
    elif st_ == "not_used":
        notice("지번은 연립다세대 진단에만 써요. 다른 유형은 기본 방식으로 계산했어요.")


def conversion_box(rent, deposit, new_deposit, conv_row, legal_cap, base_rate, small_diff):
    """보증금을 바꿨을 때 월세: 부동산원 지역 전환율(기본) + 법정 상한(참고)"""
    import rent_core as rc
    diff = new_deposit - deposit
    main = rc.convert_rent(rent, deposit, new_deposit, conv_row["전환율"])
    legal = rc.convert_rent(rent, deposit, new_deposit, legal_cap)
    arrow = "올리면" if diff > 0 else "내리면"
    rows = (f'<tr class="ours"><td>시장 전환율 (한국부동산원)</td><td class="num">{conv_row["전환율"]:.1f}%</td>'
            f'<td class="num"><b>{main:.1f}만 원</b></td><td class="num">{main - rent:+.1f}</td></tr>'
            f'<tr><td>법정 상한 (참고)</td><td class="num">{legal_cap:.1f}%</td>'
            f'<td class="num">{legal:.1f}만 원</td><td class="num">{legal - rent:+.1f}</td></tr>')
    html('<table class="fr-table"><tr><th>기준</th><th class="num">전환율</th><th class="num">바뀐 월세</th>'
         f'<th class="num">차이</th></tr>{rows}</table>'
         f'<div class="fr-sub" style="margin-top:8px">보증금을 {abs(diff):,}만 원 {arrow} · 월세 = 지금 월세 − 보증금 차이 × 전환율 ÷ 12 · '
         f'시장 전환율: {conv_row["출처"]} ({conv_row["기준월"]}) · '
         f'법정 상한: 연 10%와 기준금리({base_rate:.2f}%)+2%p 중 낮은 값 — 계약 기간 중 전환에 적용되는 상한이라 새 계약 시세와는 달라요.</div>')
    if 0 < abs(diff) < small_diff:
        notice(f"보증금 차이가 {small_diff:,}만 원보다 작으면, 실제 거래에서는 월세가 거의 안 바뀌는 경우가 많았어요"
               "(같은 건물 거래 비교). 위 숫자는 공식으로 계산한 기준값이에요.")
    if diff > 0:
        notice("보증금을 올리면 월세는 줄지만, 계약이 끝날 때 돌려받아야 할 돈도 커져요. "
               "등기부등본의 근저당 등을 꼭 확인하세요.")


def disclaimer():
    html('<div class="fr-sub" style="margin-top:40px">관리비는 실거래 데이터에 없어서 반영되지 않았어요. '
         '관리비가 높은 방은 따로 비교하세요. 이 결과는 참고용이며 실제 계약 전 현장 확인이 필요합니다.</div>')


# ---------------------------------------------------------------
# 탭 2. 예산으로 찾기
# ---------------------------------------------------------------
def budget_form_title():
    html('<div class="fr-form-title">내 예산</div>'
         '<div class="fr-sub">보증금과 월세 상한을 넣으면, 최근 1년 실제 계약에서 그 예산으로 구하기 쉬웠던 '
         '동·유형·면적을 찾아드려요.</div>')


def rec_cards(t, max_rent):
    """추천 조합 표: 예산 안 비율 막대 + 근거 계약 수"""
    rows = ""
    for i, r in t.iterrows():
        by = "—" if pd.isna(r["건축년도 중앙값"]) else f"{r['건축년도 중앙값']:.0f}"
        rows += (f'<tr><td>{i + 1}</td><td>{r["동"]}</td><td>{r["유형"]}</td>'
                 f'<td>{r["면적"]}</td>'
                 f'<td class="fr-bar-cell"><div class="fr-bar" style="width:{r["예산 안 비율"]:.0f}%"></div></td>'
                 f'<td class="num"><b>{r["예산 안 비율"]:.0f}%</b></td>'
                 f'<td class="num">{int(r["예산 안 계약"])}/{int(r["계약수"])}건</td>'
                 f'<td class="num">{r["월세 중앙값"]:.0f}</td><td class="num">{by}</td></tr>')
    html('<div style="overflow-x:auto"><table class="fr-table fr-rec"><tr><th>순위</th><th>동</th><th>유형</th><th>면적</th>'
         '<th class="fr-bar-cell"></th><th class="num">예산 안 비율</th><th class="num">예산 안/전체</th>'
         '<th class="num">월세 중앙값</th><th class="num">건축(중앙)</th></tr>'
         f'{rows}</table></div>'
         f'<div class="fr-sub" style="margin-top:8px">예산 안 비율 = 그 조합의 최근 1년 계약 중 월세 {max_rent}만 원 이하였던 비율 · '
         '금액 단위: 만 원 · 계약 10건 이상인 조합만</div>')


def rec_caveat():
    notice("<b>실제 매물이 아니라 시세 기준 추천이에요.</b> 지난 계약으로 계산한 비율이라, 과거 데이터로 확인해 보니 "
           "다음 6개월에는 평균 약 15%p 낮게 나왔어요(월세가 계속 오르는 중). 그래도 추천 조합은 같은 예산의 "
           "전체 평균보다 예산 안에 드는 계약이 많았어요(64% vs 45%).")


# ---------------------------------------------------------------
# 탭 3. 예측 성적표
# ---------------------------------------------------------------
def kpi_cards(score, ours_name="LightGBM (건축년도 앎)"):
    """성적표 요약 카드 4개 (우리 모델 기준, 기준선 대비 개선율 포함)"""
    ours = score[score["방법"] == ours_name].iloc[0]
    base = score[score["방법"].str.contains("기준선")].iloc[0]
    cut = (base["평균 오차(만원)"] - ours["평균 오차(만원)"]) / base["평균 오차(만원)"] * 100
    html(f"""
    <div class="fr-kpis">
      <div class="fr-kpi"><div class="lbl">평균 오차</div><b>{ours['평균 오차(만원)']:.2f}<small>만 원</small></b>
        <span>기준선({base['평균 오차(만원)']:.2f}만 원)보다 {cut:.0f}% 작아요</span></div>
      <div class="fr-kpi"><div class="lbl">±5만 원 이내</div><b>{ours['±5만원 이내(%)']:.1f}<small>%</small></b>
        <span>예측이 실제와 5만 원 안쪽으로 맞은 비율</span></div>
      <div class="fr-kpi"><div class="lbl">범위 적중</div><b>{ours['범위 적중(%)']:.1f}<small>%</small></b>
        <span>목표는 약 50% (실제 계약 절반이 들어오는 범위)</span></div>
      <div class="fr-kpi"><div class="lbl">시험 계약</div><b>{int(ours['시험건수']):,}<small>건</small></b>
        <span>학습에 쓰지 않은 최근 계약으로만 채점</span></div>
    </div>
    <div class="fr-sub" style="margin-bottom:4px">{ours_name} 기준 · 방법별 비교</div>
    """)


def score_table(score):
    cols = ["평균 오차(만원)", "±5만원 이내(%)", "범위 적중(%)"]
    rows = "".join(
        f'<tr class="{"ours" if row["방법"].startswith("LightGBM") else ""}"><td>{row["방법"]}</td>'
        f'<td class="num">{row["시험건수"]:,}</td>' + "".join(f'<td class="num">{row[c]}</td>' for c in cols) + "</tr>"
        for _, row in score.iterrows())
    html(f'<table class="fr-table"><tr><th>방법</th><th class="num">시험 건수</th>'
         f'<th class="num">평균 오차 (만 원)</th><th class="num">±5만 원 이내 (%)</th>'
         f'<th class="num">범위 적중 (%)</th></tr>{rows}</table>')
    html('<ul class="fr-list" style="margin-top:16px">'
         '<li><b>평균 오차</b>: 예측 월세와 실제 월세의 차이 평균이에요.</li>'
         '<li><b>범위 적중</b>: 실제 월세가 예측 범위 안에 들어간 비율이에요. AI 범위는 실제 계약의 '
         '<b>약 절반</b>이 들어오도록 맞춘 범위라 50% 근처가 목표예요.</li></ul>')


def building_score(bscore):
    """연립다세대 + 건물 연결된 시험 계약에서 지금 모델 vs 건물정보 모델"""
    cols = ["평균 오차(만원)", "±5만원 이내(%)", "범위 적중(%)"]
    rows = "".join(
        f'<tr class="{"ours" if "건물" in row["방법"] else ""}"><td>{row["방법"]}</td>'
        f'<td class="num">{row["시험건수"]:,}</td>' + "".join(f'<td class="num">{row[c]}</td>' for c in cols) + "</tr>"
        for _, row in bscore.iterrows())
    html(f'<table class="fr-table"><tr><th>방법</th><th class="num">시험 건수</th>'
         f'<th class="num">평균 오차 (만 원)</th><th class="num">±5만 원 이내 (%)</th>'
         f'<th class="num">범위 적중 (%)</th></tr>{rows}</table>'
         '<div class="fr-sub" style="margin-top:8px">대상: 시험 기간 연립다세대 중 건축물대장과 연결된 계약 · '
         '건물정보: 지상층수·승강기·주차·세대수·연면적·용적률 (국토부 건축HUB 표제부) · '
         '오피스텔은 효과가 없어 적용하지 않고, 단독다가구는 실거래에 지번이 없어 연결할 수 없어요.</div>')


def mae_chart(score):
    """방법별 평균 오차 막대 (AI는 검정, 비교 방법은 회색)"""
    mae = score[["방법", "평균 오차(만원)"]].assign(
        구분=lambda d: np.where(d["방법"].str.startswith("LightGBM"), "AI", "비교"))
    bars = alt.Chart(mae).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=18).encode(
        x=alt.X("평균 오차(만원):Q", title=None),
        y=alt.Y("방법:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelColor=INK)),
        color=alt.Color("구분:N", scale=alt.Scale(domain=["AI", "비교"], range=[INK, RANGE_BAND]), legend=None),
        tooltip=["방법", "평균 오차(만원)"])
    labels = bars.mark_text(align="left", dx=4, fontWeight=600).encode(
        text=alt.Text("평균 오차(만원):Q", format=".2f"), color=alt.value(INK))
    show_chart((bars + labels).properties(height=alt.Step(36)))


def importance_chart(imp):
    """imp: 컬럼 [정보, 중요도(%)]"""
    bars = alt.Chart(imp).mark_bar(color=INK, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                   height=14).encode(
        x=alt.X("중요도(%):Q", title=None),
        y=alt.Y("정보:N", sort="-x", title=None, axis=alt.Axis(labelColor=INK)),
        tooltip=["정보", "중요도(%)"])
    labels = bars.mark_text(align="left", dx=4, color=INK).encode(text="중요도(%):Q")
    show_chart((bars + labels).properties(height=alt.Step(28)))


# ---------------------------------------------------------------
# 탭 4. 데이터와 한계
# ---------------------------------------------------------------
def funnel_table(log):
    """정제 단계별 남은 건수 + 첫 단계 대비 막대"""
    top = int(log.values[0][1])
    rows = "".join(f'<tr><td>{a}</td><td class="fr-bar-cell"><div class="fr-bar" style="width:{int(b) / top * 100:.1f}%">'
                   f'</div></td><td class="num">{int(b):,}</td></tr>' for a, b in log.values)
    html(f'<table class="fr-table"><tr><th>단계</th><th class="fr-bar-cell"></th>'
         f'<th class="num">남은 건수</th></tr>{rows}</table>')


def limits_list():
    html('<ul class="fr-list">'
         '<li>관리비·옵션·역까지 거리는 실거래 데이터에 없어 반영되지 않아요.</li>'
         '<li>단독다가구는 데이터에 층과 지번이 없어요.</li>'
         '<li>보증금 6천만 원 이하이면서 월세 30만 원 이하인 계약은 신고 의무가 없어 일부만 들어 있어요.</li>'
         f'<li>최근 1{T}2개월 계약은 신고 지연으로 덜 반영되어 있을 수 있어요.</li>'
         '<li>"보증금을 바꾸면 월세가 얼마?" 계산은 AI 모델이 아니라 한국부동산원 전환율 공식으로 해요.</li>'
         '<li>붙여넣기는 직방 PC 화면 문구 기준이에요. 문구가 바뀌면 일부 값을 못 읽을 수 있어요.</li>'
         '</ul>')
