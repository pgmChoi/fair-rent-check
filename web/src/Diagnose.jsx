// 탭 1. 진단하기 — ① 직방 붙여넣기 → ② 입력값 확인·수정 → ③ 결과 + 북마크 저장
import { useState } from "react";
import { api } from "./api.js";
import { Badge, Checklist, Field, Histogram, Notice, RangeBar, positionText } from "./parts.jsx";

const LABEL = { 동: "동", 유형: "주택 유형", 면적: "전용면적", 보증금: "보증금", 월세: "월세", 층: "층", 건축년도: "건축년도", 지번: "지번" };
const UNIT = { 면적: "㎡", 보증금: "만 원", 월세: "만 원", 층: "층", 건축년도: "년" };
const EMPTY = { dong: "용현동", kind: "단독다가구", area: "", deposit: "", rent: "", floor: "", build_year: "", jibun: "" };

export default function Diagnose({ meta, bookmarks, form, setForm, onSaved }) {
  const [paste, setPaste] = useState("");
  const [parsed, setParsed] = useState(null);
  const [result, setResult] = useState(null);     // { input, extra, r }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function readPaste() {
    setError("");
    try {
      const p = await api.parse(paste);
      const v = p.values;
      setParsed(p);
      setForm({
        ...EMPTY, dong: form.dong,
        ...(meta.dongs.includes(v.동) && { dong: v.동 }),
        ...(v.유형 && { kind: v.유형 }),
        ...(v.면적 !== undefined && { area: String(v.면적) }),
        ...(v.보증금 !== undefined && { deposit: String(v.보증금) }),
        ...(v.월세 !== undefined && { rent: String(v.월세) }),
        ...(v.층 !== undefined && { floor: String(v.층) }),
        ...(v.건축년도 !== undefined && { build_year: String(v.건축년도) }),
        ...(v.지번 && v.유형 === "연립다세대" && { jibun: v.지번 }),   // 지번은 연립다세대 진단에만 씀
        extra: p.extra,
      });
    } catch (e) {
      setError(e.message);
    }
  }

  async function run(e) {
    e.preventDefault();
    setError("");
    const num = (s) => (s === "" || s === undefined ? null : Number(s));
    const input = {
      dong: form.dong, kind: form.kind, area: num(form.area), deposit: num(form.deposit), rent: num(form.rent),
      floor: num(form.floor), build_year: num(form.build_year),
      jibun: form.kind === "연립다세대" && form.jibun ? form.jibun : null,
    };
    if (input.area === null || input.deposit === null || input.rent === null) {
      setError("전용면적, 보증금, 월세는 꼭 넣어 주세요.");
      return;
    }
    if (input.area < 8 || input.area > 33) {
      setError("전용면적은 원룸 범위(8~33㎡)만 진단할 수 있어요.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.diagnose(input);
      setResult({ input, extra: form.extra || {}, r });
      setTimeout(() => document.getElementById("result")?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function save() {
    const { input, extra, r } = result;
    bookmarks.add({ input, extra, r: { signal: r.signal, lo: r.lo, mid: r.mid, hi: r.hi, bait: r.bait, n: r.n, pct: r.pct } });
    onSaved();
  }

  return (
    <>
      {/* ① 붙여넣기 */}
      <section className="panel">
        <div className="panel-title">직방 매물 정보 붙여넣기</div>
        <ol className="paste-steps">
          <li>직방(PC)에서 매물을 열고, 위쪽 <b>월세 300/45 · 관리비</b> 부분을 드래그해서 복사</li>
          <li><b>더보기</b>를 눌러 매물 정보 창 전체를 드래그해서 복사</li>
          <li>아래 칸에 둘 다 이어서 붙여 넣고 <b>읽기</b> — 하나만 붙여도 읽을 수 있는 값은 채워져요</li>
        </ol>
        <textarea value={paste} onChange={(e) => setPaste(e.target.value)} aria-label="직방 매물 정보 붙여넣기"
          placeholder={"월세 300/45\n인천시 미추홀구 용현동 · 관리비 5만원\n전용 23.14m²\n단일동 3층/4층\n다가구주택\n20020605 준공\n미추홀구 용현동 83-13"} />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn" onClick={readPaste} disabled={!paste.trim()}>읽기</button>
          <button className="btn ghost" onClick={() => { setPaste(""); setParsed(null); setForm({ ...EMPTY }); setResult(null); }}>
            지우기
          </button>
        </div>
        {parsed && <ParseResult p={parsed} />}
      </section>

      {/* ② 입력값 (읽은 값이 채워지고, 직접 고칠 수 있음) */}
      <form className="panel" onSubmit={run}>
        <div className="panel-title">매물 정보</div>
        <p className="sub">붙여넣기로 채워진 값을 확인하고, 비어 있는 칸은 직접 넣어 주세요.</p>
        <div className="grid4">
          <Field label="동">
            <select value={form.dong} onChange={set("dong")}>
              {meta.dongs.map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="주택 유형">
            <select value={form.kind} onChange={set("kind")}>
              {meta.kinds.map((k) => <option key={k}>{k}</option>)}
            </select>
          </Field>
          <Field label="전용면적 (㎡)"><input type="number" inputMode="decimal" step="0.01" value={form.area} onChange={set("area")} placeholder="예: 23.14" /></Field>
          <Field label="층 (선택)" hint={form.kind === "단독다가구" ? "단독다가구는 층이 반영되지 않아요" : ""}>
            <input type="number" inputMode="numeric" value={form.floor} onChange={set("floor")} placeholder="모르면 비워 두기" />
          </Field>
          <Field label="보증금 (만 원)"><input type="number" inputMode="numeric" value={form.deposit} onChange={set("deposit")} placeholder="예: 300" /></Field>
          <Field label="월세 (만 원, 관리비 제외)"><input type="number" inputMode="numeric" value={form.rent} onChange={set("rent")} placeholder="예: 45" /></Field>
          <Field label="준공년도 (선택)" hint="넣으면 더 정확해요">
            <input type="number" inputMode="numeric" value={form.build_year} onChange={set("build_year")} placeholder="예: 2002" />
          </Field>
          <Field label="지번 (연립다세대만)" hint="건축물대장 반영">
            <input value={form.jibun} onChange={set("jibun")} placeholder="예: 222-23" disabled={form.kind !== "연립다세대"} />
          </Field>
        </div>
        <button className="btn block" disabled={busy}>{busy ? "진단하는 중..." : "진단하기"}</button>
        {error && <Notice kind="warn">{error}</Notice>}
      </form>

      {result && <Result {...result} meta={meta} saved={bookmarks.has(result)} onSave={save} />}
    </>
  );
}

function ParseResult({ p }) {
  const found = Object.entries(p.values);
  const ref = Object.entries(p.extra).filter(([k]) => ["관리비", "엘리베이터", "주차", "위반건축물", "등록번호"].includes(k));
  return (
    <>
      {found.length > 0 && (
        <Notice>
          <b>읽은 값</b>
          <div className="kv">{found.map(([k, v]) => <span key={k}>{LABEL[k]} {v}{UNIT[k] || ""}</span>)}</div>
          {ref.length > 0 && <div className="kv">{ref.map(([k, v]) => <span key={k} style={{ color: "var(--muted)" }}>{k} {v}{k === "관리비" ? "만 원" : ""}</span>)}</div>}
        </Notice>
      )}
      {p.missing.length > 0 && <Notice kind="warn"><b>못 읽은 값</b>: {p.missing.map((k) => LABEL[k]).join(", ")} — 아래 칸에 직접 넣어 주세요.</Notice>}
      {p.warnings.map((w) => <Notice key={w} kind="warn">{w}</Notice>)}
    </>
  );
}

function Result({ input, extra, r, meta, saved, onSave }) {
  const { lo, mid, hi, signal } = r;
  const rent = input.rent;
  const verdict = signal === "저렴" ? <>AI 적정 범위의 아래쪽 끝보다 <b>{lo - rent}만 원 낮아요</b>.</>
    : signal === "비쌈" ? <>AI 적정 범위의 위쪽 끝보다 <b>{rent - hi}만 원 높아요</b>.</>
    : <>AI 적정 범위 <b>안에 있어요</b>.</>;
  const extraLine = [input.build_year && `${input.build_year}년 준공`, input.floor && `${input.floor}층`,
    extra.관리비 !== undefined && `관리비 ${extra.관리비}만 원`].filter(Boolean).join(" · ");
  return (
    <div id="result" className="section">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="h1">{input.dong} · {input.kind} · {input.area}㎡</div>
          <p className="sub" style={{ margin: 0 }}>보증금 {input.deposit.toLocaleString()}만 원 · 월세 {rent}만 원{extraLine && ` · ${extraLine}`}</p>
        </div>
        <button className="btn ghost small" onClick={onSave}>{saved ? "북마크 업데이트" : "☆ 북마크에 담기"}</button>
      </div>
      <div className="result">
        <div>
          <div className="h2">내 월세는 범위의 어디쯤일까?</div>
          <p className="sub">회색 띠가 AI 적정 범위(흰 선은 예상 중앙값), 점이 입력하신 월세예요.</p>
          <RangeBar lo={lo} mid={mid} hi={hi} rent={rent} signal={signal} />
          {r.same_rents.length > 0 ? (
            <div style={{ marginTop: 32 }}>
              <div className="h2">비슷한 실제 계약의 월세</div>
              <p className="sub">조건: {r.level} · {r.n.toLocaleString()}건</p>
              <Histogram rents={r.same_rents} rent={rent} lo={lo} hi={hi} />
              <details>
                <summary>근거 거래 목록 보기 (최근 {r.comparables.length}건)</summary>
                <div className="table-wrap">
                  <table className="t">
                    <thead><tr><th>계약일</th><th>동</th><th>유형</th><th className="num">면적</th><th className="num">층</th>
                      <th className="num">건축</th><th className="num">보증금</th><th className="num">월세</th></tr></thead>
                    <tbody>
                      {r.comparables.map((c, i) => (
                        <tr key={i} className={c.월세 === rent ? "me" : ""}>
                          <td>{c.계약일}</td><td>{c.동}</td><td>{c.유형}</td><td className="num">{c.면적}</td>
                          <td className="num">{c.층 ?? "—"}</td><td className="num">{c.건축년도 ?? "—"}</td>
                          <td className="num">{c.보증금?.toLocaleString()}</td><td className="num">{c.월세}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          ) : <Notice kind="warn">비슷한 조건의 실제 계약을 찾지 못했어요. AI 범위만 참고하세요.</Notice>}
        </div>

        <div className="side">
          <div className="card sticky">
            <Badge signal={signal} />
            <div className="label">AI 적정 범위</div>
            <div className="big">{lo}~{hi}<small>만 원</small></div>
            <p className="sentence">입력하신 월세 <b>{rent}만 원</b>은 {verdict}</p>
            <div className="stats">
              <div><b>{mid}만 원</b><span>AI 예상 중앙값</span></div>
              <div><b>{positionText(r.pct)}</b><span>비슷한 계약 중</span></div>
              <div><b>{r.n.toLocaleString()}건</b><span>근거 거래</span></div>
            </div>
            <div className="fee">관리비 별도 · 신호는 AI 범위로만 정해요{r.used_building && " · 건축물대장 반영"}</div>
          </div>
          {r.bait && (
            <Notice kind="warn">
              <b>시세보다 크게 싸요.</b> AI 예상 중앙값 {mid}만 원의 {Math.round(meta.bait_ratio * 100)}%인 {r.bait_cut}만 원 이하예요.
              실제 거래에서 이만큼 싼 계약은 약 2%뿐이에요. 허위·미끼매물일 수 있으니 아래 4가지를 꼭 확인하세요.
            </Notice>
          )}
          {extra.위반건축물 === "있음" && <Notice kind="warn">위반건축물로 표시된 매물이에요. 대출·보증보험이 거절될 수 있어요.</Notice>}
          {r.notices.map((n) => <Notice key={n.text} kind={n.kind}>{n.text}</Notice>)}
        </div>
      </div>

      <Convert key={JSON.stringify(input)} input={input} />
      <details open={r.bait}>
        <summary>계약 전 꼭 확인할 것 4가지</summary>
        <Checklist />
      </details>
      <p className="sub" style={{ marginTop: 32 }}>
        관리비는 실거래 데이터에 없어서 반영되지 않았어요. 이 결과는 참고용이며 실제 계약 전 현장 확인이 필요합니다.
      </p>
    </div>
  );
}

function Convert({ input }) {
  const [newDep, setNewDep] = useState(input.deposit + 1000);
  const [c, setC] = useState(null);
  const [err, setErr] = useState("");
  async function calc(e) {
    e.preventDefault();
    setErr("");
    try {
      setC(await api.convert({ kind: input.kind, rent: input.rent, deposit: input.deposit, new_deposit: Number(newDep) }));
    } catch (e2) {
      setErr(e2.message);
    }
  }
  const diff = Number(newDep) - input.deposit;
  return (
    <div className="section">
      <div className="h1">보증금을 바꾸면 월세는?</div>
      <p className="sub">집주인과 보증금·월세 조합을 조정할 때 참고하세요. 위 AI 진단과는 별개의 공식 계산이에요.</p>
      <form className="row" onSubmit={calc}>
        <div className="field" style={{ width: 220 }}>
          <label>바꿀 보증금 (만 원)</label>
          <input type="number" inputMode="numeric" value={newDep} onChange={(e) => { setNewDep(e.target.value); setC(null); }} />
        </div>
        <button className="btn" style={{ marginTop: 26 }} disabled={diff === 0}>계산</button>
      </form>
      {err && <Notice kind="warn">{err}</Notice>}
      {c && (
        <>
          <div className="table-wrap" style={{ marginTop: 16 }}>
            <table className="t">
              <thead><tr><th>기준</th><th className="num">전환율</th><th className="num">바뀐 월세</th><th className="num">차이</th></tr></thead>
              <tbody>
                <tr className="ours"><td>시장 전환율 (한국부동산원)</td><td className="num">{c.market_rate.toFixed(1)}%</td>
                  <td className="num">{c.market_rent.toFixed(1)}만 원</td><td className="num">{(c.market_rent - input.rent).toFixed(1)}</td></tr>
                <tr><td>법정 상한 (참고)</td><td className="num">{c.legal_rate.toFixed(1)}%</td>
                  <td className="num">{c.legal_rent.toFixed(1)}만 원</td><td className="num">{(c.legal_rent - input.rent).toFixed(1)}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="sub" style={{ marginTop: 8 }}>
            보증금을 {Math.abs(diff).toLocaleString()}만 원 {diff > 0 ? "올리면" : "내리면"} · 월세 = 지금 월세 − 보증금 차이 × 전환율 ÷ 12 ·
            시장 전환율: {c.source} ({c.base_month}) · 법정 상한: 연 10%와 기준금리({c.base_rate.toFixed(2)}%)+2%p 중 낮은 값 —
            계약 기간 중 전환에 적용되는 상한이라 새 계약 시세와는 달라요.
          </p>
          {c.small_diff && <Notice>보증금 차이가 1,000만 원보다 작으면, 실제 거래에서는 월세가 거의 안 바뀌는 경우가 많았어요(같은 건물 거래 비교).</Notice>}
          {diff > 0 && <Notice>보증금을 올리면 월세는 줄지만, 돌려받아야 할 돈도 커져요. 등기부등본의 근저당 등을 꼭 확인하세요.</Notice>}
        </>
      )}
    </div>
  );
}

export { EMPTY };
