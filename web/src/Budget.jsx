// 탭 3. 예산으로 찾기 — 최근 1년 실제 계약에서 내 예산으로 구하기 쉬웠던 동·유형·면적
import { useState } from "react";
import { api } from "./api.js";
import { Field, Notice } from "./parts.jsx";

export default function Budget({ meta }) {
  const [f, setF] = useState({ max_deposit: 300, max_rent: 35, min_area: 0, kinds: meta.kinds });
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const toggle = (k) => setF({ ...f, kinds: f.kinds.includes(k) ? f.kinds.filter((x) => x !== k) : [...f.kinds, k] });

  async function run(e) {
    e.preventDefault();
    setErr("");
    if (!f.kinds.length) return setErr("주택 유형을 하나 이상 골라 주세요.");
    try {
      setRes({ ...(await api.recommend({ ...f, max_deposit: +f.max_deposit, max_rent: +f.max_rent, min_area: +f.min_area })), f: { ...f } });
    } catch (e2) {
      setErr(e2.message);
    }
  }

  return (
    <>
      <form className="panel" onSubmit={run}>
        <div className="panel-title">내 예산</div>
        <p className="sub">보증금과 월세 상한을 넣으면, 최근 1년 실제 계약에서 그 예산으로 구하기 쉬웠던 동·유형·면적을 찾아드려요.</p>
        <div className="grid4">
          <Field label="보증금 최대 (만 원)"><input type="number" inputMode="numeric" value={f.max_deposit} onChange={set("max_deposit")} /></Field>
          <Field label="월세 최대 (만 원)"><input type="number" inputMode="numeric" value={f.max_rent} onChange={set("max_rent")} /></Field>
          <Field label="최소 면적 (㎡, 상관없으면 0)"><input type="number" inputMode="decimal" value={f.min_area} onChange={set("min_area")} /></Field>
          <Field label="주택 유형">
            <div className="row">
              {meta.kinds.map((k) => (
                <label key={k} className="check" style={{ marginTop: 0, minHeight: 0 }}>
                  <input type="checkbox" checked={f.kinds.includes(k)} onChange={() => toggle(k)} />{k}
                </label>
              ))}
            </div>
          </Field>
        </div>
        <button className="btn block">찾기</button>
        {err && <Notice kind="warn">{err}</Notice>}
      </form>

      {res && (
        <div className="section">
          <div className="h1">보증금 {(+res.f.max_deposit).toLocaleString()}만 원 · 월세 {res.f.max_rent}만 원으로 구하기 쉬운 곳</div>
          <p className="sub">최근 1년({res.period}) 실제 계약 중 보증금이 예산 이하인 {res.n_pool.toLocaleString()}건 기준</p>
          {res.rows.length ? (
            <>
              <div className="table-wrap">
                <table className="t">
                  <thead><tr><th>순위</th><th>동</th><th>유형</th><th>면적</th><th style={{ width: "24%" }}></th>
                    <th className="num">예산 안 비율</th><th className="num">예산 안/전체</th><th className="num">월세 중앙값</th><th className="num">건축(중앙)</th></tr></thead>
                  <tbody>
                    {res.rows.map((r, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td><td>{r.동}</td><td>{r.유형}</td><td>{r.면적}</td>
                        <td><div className="bar" style={{ width: `${r["예산 안 비율"]}%` }} /></td>
                        <td className="num"><b>{Math.round(r["예산 안 비율"])}%</b></td>
                        <td className="num">{r["예산 안 계약"]}/{r.계약수}건</td>
                        <td className="num">{Math.round(r["월세 중앙값"])}</td>
                        <td className="num">{r["건축년도 중앙값"] ? Math.round(r["건축년도 중앙값"]) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="sub" style={{ marginTop: 8 }}>예산 안 비율 = 그 조합의 최근 1년 계약 중 월세 {res.f.max_rent}만 원 이하였던 비율 · 계약 10건 이상인 조합만</p>
              <Notice>
                <b>실제 매물이 아니라 시세 기준 추천이에요.</b> 과거 데이터로 확인해 보니 다음 6개월에는 평균 약 15%p 낮게 나왔어요(월세가 계속 오르는 중).
                그래도 추천 조합은 같은 예산의 전체 평균보다 예산 안에 드는 계약이 많았어요(64% vs 45%).
              </Notice>
            </>
          ) : <Notice kind="warn">이 예산으로 최근 1년에 계약된 조합이 없어요. 월세나 보증금 상한을 조금 올려 보세요.</Notice>}
        </div>
      )}
    </>
  );
}
