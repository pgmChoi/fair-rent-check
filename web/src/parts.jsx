// 여러 화면에서 같이 쓰는 작은 부품 (안내 문구, 신호 배지, 범위 막대, 분포, 체크리스트)

export function Notice({ kind = "info", children }) {
  return <div className={`notice ${kind === "warn" ? "warn" : ""}`}>{children}</div>;
}

export function Badge({ signal }) {
  return <span className={`badge ${signal}`}><i />{signal}</span>;
}

export function Field({ label, hint, children }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

// AI 범위(회색 띠) 위에 내 월세(점)
export function RangeBar({ lo, mid, hi, rent, signal }) {
  const min = Math.min(lo, rent) - 8;
  const max = Math.max(hi, rent) + 8;
  const x = (v) => `${((v - min) / (max - min)) * 100}%`;
  const color = signal === "저렴" ? "var(--cheap)" : signal === "비쌈" ? "var(--pricey)" : "var(--ink)";
  return (
    <>
      <div className="rangebar" role="img" aria-label={`AI 적정 범위 ${lo}~${hi}만 원, 입력 월세 ${rent}만 원`}>
        <div className="track" />
        <div className="band" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})` }} />
        <div className="midline" style={{ left: x(mid) }} />
        <div className="dot" style={{ left: x(rent), background: color }} />
        {[lo, hi].map((v) => <div key={v} className="tick" style={{ left: x(v) }}>{v}</div>)}
        <div className="tick" style={{ left: x(rent), top: -4, color, fontWeight: 700 }}>내 월세 {rent}</div>
      </div>
      <div className="legend">
        {[["저렴", `${lo}만 원 미만`, "var(--cheap)", "var(--cheap-bg)"],
          ["적정", `${lo}~${hi}만 원`, "var(--ink)", "var(--surface-strong)"],
          ["비쌈", `${hi}만 원 초과`, "var(--pricey)", "var(--pricey-bg)"]].map(([s, txt, fg, bg]) => (
          <span key={s} className={s === signal ? "on" : ""} style={{ color: fg, background: bg }}>{s} · {txt}</span>
        ))}
      </div>
    </>
  );
}

// 비슷한 실제 계약의 월세 분포 (2만 원 간격 막대)
export function Histogram({ rents, rent, lo, hi, step = 2 }) {
  if (!rents.length) return null;
  const min = Math.floor(Math.min(...rents, rent) / step) * step;
  const max = Math.ceil((Math.max(...rents, rent) + 1) / step) * step;
  const bins = [];
  for (let b = min; b < max; b += step) bins.push({ b, n: rents.filter((r) => r >= b && r < b + step).length });
  const top = Math.max(...bins.map((x) => x.n));
  return (
    <>
      <div className="hist" role="img" aria-label="비슷한 계약 월세 분포">
        {bins.map(({ b, n }) => {
          const me = rent >= b && rent < b + step;
          const inside = b + step > lo && b <= hi;
          return <div key={b} className={me ? "me" : inside ? "in" : ""} style={{ height: `${(n / top) * 100}%` }}
            title={`${b}~${b + step}만 원: ${n}건`} />;
        })}
      </div>
      <div className="hist-axis"><span>{min}만 원</span><span>검은 막대 = 내 월세 구간</span><span>{max}만 원</span></div>
    </>
  );
}

export function Checklist() {
  return (
    <>
      <ol className="list">
        <li><b>방이 지금도 있나요?</b> 등록번호로 중개사무소에 묻고, 직접 볼 수 있는지 확인하세요. 계약이 끝난 방을 계속 올려 두는 경우가 있어요.</li>
        <li><b>전용면적이 맞나요?</b> 건축물대장(정부24에서 열람)의 면적과 광고 면적을 비교하세요.</li>
        <li><b>옵션이 실제로 있나요?</b> 광고에 적힌 에어컨·세탁기 등을 방에서 직접 확인하세요.</li>
        <li><b>관리비는 얼마이고 무엇이 포함되나요?</b> 금액과 포함 항목(수도·인터넷 등)을 물어보세요. 이 진단은 관리비를 반영하지 않아요.</li>
      </ol>
      <p className="sub" style={{ marginTop: 8 }}>
        근거: 국토교통부 청년 밀집 대학가 부동산 광고 모니터링(2025.10) — 적발 321건 중 부당표시 52%, 명시의무 위반 48%
      </p>
    </>
  );
}

export function positionText(pct) {
  if (pct === null || pct === undefined) return "—";
  // Streamlit ui.position_text와 같은 규칙
  if (pct >= 99) return "가장 비싼 편";
  if (pct <= 1) return "가장 싼 편";
  return pct <= 50 ? `하위 ${Math.round(pct)}%` : `상위 ${Math.round(100 - pct)}%`;
}
