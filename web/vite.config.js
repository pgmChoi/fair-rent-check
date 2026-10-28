import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발할 때: /api 요청을 FastAPI(8000포트)로 넘긴다 → React와 API를 따로 켜도 주소가 같아 보임
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
