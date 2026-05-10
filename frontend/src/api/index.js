import axios from "axios";

function normalizeApiBaseUrl(value) {
  const raw = (value || "").trim().replace(/\/+$/, "");
  if (!raw) return "";
  return raw.endsWith("/api") ? raw : `${raw}/api`;
}

function resolveApiBaseUrl() {
  const configured = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
  if (configured) return configured;
  // 默认走 Vercel 代理 → Render（vercel.json rewrites）
  return "/api";
}

export const API_BASE_URL = resolveApiBaseUrl();
export const API_MODE = API_BASE_URL === "/api" ? "local-proxy" : "remote";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

// ── 响应拦截器 — 解包 data ──

client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const detail = err.response?.data?.detail;
    const validationMsg = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join("；")
      : null;
    const msg =
      err.response?.data?.message ||
      (typeof detail === "string" ? detail : null) ||
      validationMsg ||
      err.message ||
      "网络异常";
    return Promise.reject(new Error(msg));
  }
);

// ── API 方法 ──

const api = {
  get: (url, config) => client.get(url, config),
  post: (url, data, config) => client.post(url, data, config),
  put: (url, data, config) => client.put(url, data, config),
  delete: (url, config) => client.delete(url, config),
};

export default api;
