// API 서버(FastAPI) 부르기. 주소는 같은 서버의 /api (개발 때는 vite.config.js가 8000포트로 넘김)
async function call(path, body) {
  const res = await fetch(`/api${path}`, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : "입력값을 확인해 주세요.";
    throw new Error(msg);
  }
  return data;
}

export const api = {
  meta: () => call("/meta"),
  parse: (text) => call("/parse", { text }),
  diagnose: (input) => call("/diagnose", input),
  convert: (input) => call("/convert", input),
  recommend: (input) => call("/recommend", input),
  score: () => call("/score"),
};
