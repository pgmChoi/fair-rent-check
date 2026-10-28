// 탭 4. 예측 성적표 + 데이터와 한계
import { useEffect, useState } from "react";
import { api } from "./api.js";

const OURS = "LightGBM (건축년도 앎)";

export default function Score() {
  const [s, setS] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.score().then(setS).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="loading">{err}</div>;
  if (!s) return <div className="loading">성적표를 불러오는 중...</div>;

  const ours = s.rows.find((r) => r.방법 === OURS);
  const base = s.rows.find((r) => r.방법.includes("기준선"));
  const cut = Math.round(((base["평균 오차(만원)"] - ours["평균 오차(만원)"]) / base["평균 오차(만원)"]) * 100);
  const cols = ["평균 오차(만원)", "±5만원 이내(%)", "범위 적중(%)"];
  const top = Math.max(...s.importance.map((i) => i.중요도));
  const funnelTop = s.funnel[0][1];

  return (
    <>
      <div className="section" style={{ marginTop: 24 }}>
        <div className="h1">예측이 실제 계약과 얼마나 맞았나</div>
        <p className="sub">{s.period} · 과거 거래로만 학습하고 이후 계약으로 시험했어요. 시험 기간은 데이터가 갱신될 때마다 가장 최근 6개월로 바뀌어요.</p>
        <div className="kpis">
          <div className="kpi"><div className="lbl">평균 오차</div><b>{ours["평균 오차(만원)"].toFixed(2)}<small>만 원</small></b><span>기준선({base["평균 오차(만원)"].toFixed(2)}만 원)보다 {cut}% 작아요</span></div>
          <div className="kpi"><div className="lbl">±5만 원 이내</div><b>{ours["±5만원 이내(%)"]}<small>%</small></b><span>실제와 5만 원 안쪽으로 맞은 비율</span></div>
          <div className="kpi"><div className="lbl">범위 적중</div><b>{ours["범위 적중(%)"]}<small>%</small></b><span>목표 약 50% (실제 계약 절반이 들어오는 범위)</span></div>
          <div className="kpi"><div className="lbl">시험 계약</div><b>{ours.시험건수.toLocaleString()}<small>건</small></b><span>학습에 쓰지 않은 최근 계약</span></div>
        </div>
        <Table rows={s.rows} cols={cols} isOurs={(r) => r.방법.startsWith("LightGBM")} />
      </div>

      <div className="section">
        <div className="h1">건축물대장 정보를 더하면 (연립다세대)</div>
        <p className="sub">지번으로 건물을 찾으면 층수·승강기·세대수 등을 함께 넣어 예측해요. 같은 시험 계약끼리 비교했어요.</p>
        <Table rows={s.building_rows} cols={cols} isOurs={(r) => r.방법.includes("건물")} />
      </div>

      <div className="section">
        <div className="h1">AI가 많이 참고한 정보</div>
        <p className="sub">중요도 (%)</p>
        {s.importance.map((i) => (
          <div key={i.정보} className="hbar"><span>{i.정보}</span><div className="bar" style={{ width: `${(i.중요도 / top) * 100}%` }} /><span className="num">{i.중요도}</span></div>
        ))}
      </div>

      <div className="section">
        <div className="h1">데이터 정제 과정</div>
        <p className="sub">국토교통부 전월세 실거래(인천 미추홀구 3년)에서 원룸 월세 계약만 남기기까지</p>
        {s.funnel.map(([step, n]) => (
          <div key={step} className="hbar" style={{ gridTemplateColumns: "130px 1fr 64px" }}>
            <span>{step}</span><div className="bar" style={{ width: `${(n / funnelTop) * 100}%` }} /><span className="num">{n.toLocaleString()}</span>
          </div>
        ))}
      </div>

      <div className="section">
        <div className="h1">알고 쓰세요</div>
        <ul className="list">
          <li>관리비·옵션·역까지 거리는 실거래 데이터에 없어 반영되지 않아요.</li>
          <li>단독다가구는 데이터에 층과 지번이 없어요.</li>
          <li>보증금 6천만 원 이하이면서 월세 30만 원 이하인 계약은 신고 의무가 없어 일부만 들어 있어요.</li>
          <li>최근 1~2개월 계약은 신고 지연으로 덜 반영되어 있을 수 있어요.</li>
          <li>보증금 조정 계산은 AI 모델이 아니라 한국부동산원 전환율 공식으로 해요.</li>
          <li>붙여넣기는 직방 PC 화면 문구 기준이에요. 문구가 바뀌면 일부 값을 못 읽을 수 있어요.</li>
        </ul>
      </div>
    </>
  );
}

function Table({ rows, cols, isOurs }) {
  return (
    <div className="table-wrap">
      <table className="t">
        <thead><tr><th>방법</th><th className="num">시험 건수</th><th className="num">평균 오차 (만 원)</th><th className="num">±5만 원 이내 (%)</th><th className="num">범위 적중 (%)</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.방법} className={isOurs(r) ? "ours" : ""}>
              <td>{r.방법}</td><td className="num">{r.시험건수.toLocaleString()}</td>
              {cols.map((c) => <td key={c} className="num">{r[c]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
