// 탭 2. 북마크 비교 — 저장한 매물을 'AI 예상 중앙값보다 얼마나 싼가' 기준으로 나란히 비교
import { useState } from "react";
import { Badge, Notice, positionText } from "./parts.jsx";

const SORTS = {
  gap: { label: "시세 대비 싼 순", key: (b) => b.input.rent - b.r.mid },
  total: { label: "월 부담(월세+관리비) 낮은 순", key: (b) => b.input.rent + (b.extra.관리비 ?? 0) },
  deposit: { label: "보증금 낮은 순", key: (b) => b.input.deposit },
  recent: { label: "최근 담은 순", key: (b) => -new Date(b.savedAt).getTime() },
};

export default function Compare({ bookmarks, onOpen }) {
  const [sort, setSort] = useState("gap");
  const items = [...bookmarks.items].sort((a, b) => SORTS[sort].key(a) - SORTS[sort].key(b));
  if (!items.length) {
    return (
      <div className="empty">
        <b>아직 담은 매물이 없어요.</b><br />
        진단하기에서 결과를 본 뒤 <b>☆ 북마크에 담기</b>를 누르면 여기서 나란히 비교할 수 있어요.
      </div>
    );
  }
  // 미끼매물 의심은 '가장 좋은 조건'에서 뺀다
  const candidates = items.filter((b) => !b.r.bait);
  const best = candidates.length > 1
    ? candidates.reduce((a, b) => (b.input.rent - b.r.mid < a.input.rent - a.r.mid ? b : a)).id : null;
  // 모든 매물을 같은 눈금으로 그리기 위한 범위
  const lo = Math.min(...items.map((b) => Math.min(b.r.lo, b.input.rent))) - 5;
  const hi = Math.max(...items.map((b) => Math.max(b.r.hi, b.input.rent))) + 5;
  const x = (v) => `${((v - lo) / (hi - lo)) * 100}%`;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 24 }}>
        <div>
          <div className="h1">담은 매물 {items.length}개 비교</div>
          <p className="sub" style={{ margin: 0 }}>매물마다 조건(동·면적·건축년도)이 달라서, 월세 금액보다 <b>AI 예상 중앙값과의 차이</b>로 비교하는 게 공정해요.</p>
        </div>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬"
          style={{ minHeight: 40, border: "1px solid var(--hairline)", borderRadius: 8, padding: "0 10px" }}>
          {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>

      <div className="compare">
        {items.map((b) => {
          const gap = b.input.rent - b.r.mid;
          const fee = b.extra.관리비;
          const info = [b.input.build_year && `${b.input.build_year}년`, b.input.floor && `${b.input.floor}층`,
            b.extra.엘리베이터 && `엘리베이터 ${b.extra.엘리베이터}`, b.extra.주차 && `주차 ${b.extra.주차}`,
            b.extra.입주가능일 && `입주 ${b.extra.입주가능일}`].filter(Boolean).join(" · ");
          return (
            <div key={b.id} className={`cmp ${b.id === best ? "best" : ""}`}>
              <div>
                <Badge signal={b.r.signal} />{b.id === best && <span className="pill">시세 대비 가장 좋음</span>}
                <h3>{b.input.dong} · {b.input.kind} · {b.input.area}㎡</h3>
                <div className="meta">{info || "추가 정보 없음"}{b.extra.등록번호 && ` · 등록번호 ${b.extra.등록번호}`}</div>
                <input className="memo" value={b.memo || ""} placeholder="메모 (예: 역 가까움, 채광 좋음)"
                  onChange={(e) => bookmarks.rename(b.id, e.target.value)} aria-label="메모" />
              </div>
              <div>
                <div className="row" style={{ gap: 16, alignItems: "baseline" }}>
                  <span className="money">{b.input.deposit.toLocaleString()}/{b.input.rent}</span>
                  <span className="meta">관리비 {fee === undefined ? "모름" : `${fee}만 원`}{fee !== undefined && ` · 월 부담 ${b.input.rent + fee}만 원`}</span>
                </div>
                <div className="rangebar" style={{ height: 34, margin: "8px 4px 0" }}>
                  <div className="track" style={{ top: 12 }} />
                  <div className="band" style={{ top: 6, height: 14, left: x(b.r.lo), width: `calc(${x(b.r.hi)} - ${x(b.r.lo)})` }} />
                  <div className="dot" style={{ top: 3, width: 18, height: 18, marginLeft: -9, left: x(b.input.rent),
                    background: b.r.signal === "저렴" ? "var(--cheap)" : b.r.signal === "비쌈" ? "var(--pricey)" : "var(--ink)" }} />
                </div>
                <div className="meta">
                  AI 범위 {b.r.lo}~{b.r.hi}만 원 · 중앙값보다 <b style={{ color: "var(--ink)" }}>{gap === 0 ? "같음" : `${Math.abs(gap)}만 원 ${gap < 0 ? "쌈" : "비쌈"}`}</b>
                  {" "}· 비슷한 계약 중 {positionText(b.r.pct)}
                </div>
                {b.r.bait && <Notice kind="warn">미끼매물 의심 — 방이 실제로 있는지 먼저 확인하세요.</Notice>}
              </div>
              <div className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
                <button className="btn ghost small" onClick={() => onOpen(b)}>다시 진단</button>
                <button className="btn ghost small" onClick={() => bookmarks.remove(b.id)}>빼기</button>
              </div>
            </div>
          );
        })}
      </div>
      <p className="sub" style={{ marginTop: 16 }}>
        북마크는 이 브라우저에만 저장돼요(로그인 없음). 다른 기기나 시크릿 창에서는 보이지 않아요. 최대 30개.
      </p>
    </>
  );
}
