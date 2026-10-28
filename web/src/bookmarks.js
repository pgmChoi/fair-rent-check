// 북마크: 로그인 없이 이 브라우저에만 저장 (localStorage). 기기를 바꾸면 보이지 않는다.
import { useEffect, useState } from "react";

const KEY = "fair-rent-bookmarks-v1";

function load() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];          // 시크릿 창 등 저장소를 못 쓰는 경우
  }
}

export function useBookmarks() {
  const [items, setItems] = useState(load);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch {
      /* 저장 못 해도 화면은 계속 동작 */
    }
  }, [items]);

  // 같은 매물(등록번호, 없으면 입력값이 같으면)은 새로 추가하지 않고 덮어쓴다
  const keyOf = (b) => b.extra?.등록번호 || JSON.stringify(b.input);
  const add = (b) =>
    setItems((xs) => [{ ...b, id: keyOf(b), savedAt: new Date().toISOString() },
      ...xs.filter((x) => x.id !== keyOf(b))].slice(0, 30));
  const remove = (id) => setItems((xs) => xs.filter((x) => x.id !== id));
  const rename = (id, memo) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, memo } : x)));
  const has = (b) => items.some((x) => x.id === keyOf(b));
  return { items, add, remove, rename, has };
}
