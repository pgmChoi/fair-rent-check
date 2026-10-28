// 적정월세 React 화면 — 탭 4개: 진단하기 / 북마크 비교 / 예산으로 찾기 / 예측 성적표
import { useEffect, useState } from "react";
import { api } from "./api.js";
import { useBookmarks } from "./bookmarks.js";
import Diagnose, { EMPTY } from "./Diagnose.jsx";
import Compare from "./Compare.jsx";
import Budget from "./Budget.jsx";
import Score from "./Score.jsx";

const TABS = [["dx", "진단하기"], ["cmp", "북마크 비교"], ["rec", "예산으로 찾기"], ["score", "예측 성적표"]];

export default function App() {
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState(() => (location.hash.slice(1) in Object.fromEntries(TABS) ? location.hash.slice(1) : "dx"));
  const [form, setForm] = useState(EMPTY);          // 탭을 옮겨도 입력값 유지
  const bookmarks = useBookmarks();

  useEffect(() => { api.meta().then(setMeta).catch(() => setErr("서버에 연결하지 못했어요. 잠시 후 새로고침해 주세요.")); }, []);
  const go = (t) => { setTab(t); history.replaceState(null, "", `#${t}`); window.scrollTo(0, 0); };

  return (
    <div className="wrap">
      <header className="nav">
        <div className="wordmark"><span className="mark">적</span>적정월세</div>
        {meta && <span className="chip">인천 미추홀구 · 실거래 {meta.n.toLocaleString()}건 · {meta.date_from}~{meta.date_to}</span>}
      </header>
      <div className="hero">
        <h1>이 원룸 월세, 적당한 걸까?</h1>
        <p>국토교통부 실거래 데이터로 학습한 AI가 계약 전에 적정 월세 범위를 알려 드려요.</p>
      </div>
      <nav className="tabs" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" className="tab" aria-selected={tab === k} onClick={() => go(k)}>
            {label}{k === "cmp" && bookmarks.items.length > 0 && <span className="count">{bookmarks.items.length}</span>}
          </button>
        ))}
      </nav>

      {err && <div className="loading">{err}</div>}
      {!err && !meta && <div className="loading">데이터를 불러오는 중...</div>}
      {meta && (
        <main>
          {tab === "dx" && <Diagnose meta={meta} bookmarks={bookmarks} form={form} setForm={setForm} onSaved={() => {}} />}
          {tab === "cmp" && <Compare bookmarks={bookmarks} onOpen={(b) => {
            const s = (v) => (v === null || v === undefined ? "" : String(v));
            setForm({ dong: b.input.dong, kind: b.input.kind, area: s(b.input.area), deposit: s(b.input.deposit), rent: s(b.input.rent),
              floor: s(b.input.floor), build_year: s(b.input.build_year), jibun: s(b.input.jibun), extra: b.extra });
            go("dx");
          }} />}
          {tab === "rec" && <Budget meta={meta} />}
          {tab === "score" && <Score />}
        </main>
      )}

      <footer className="footer">
        <span>데이터: 국토교통부 전월세 실거래가 · 한국부동산원 전월세전환율 · 건축HUB 건축물대장</span>
        <span>AI캡스톤디자인 · 호갱방지위원회</span>
      </footer>
    </div>
  );
}
