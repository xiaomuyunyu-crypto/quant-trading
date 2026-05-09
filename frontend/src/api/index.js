import axios from "axios";

function normalizeApiBaseUrl(value) {
  const raw = (value || "").trim().replace(/\/+$/, "");
  if (!raw) return "/api";
  return raw.endsWith("/api") ? raw : `${raw}/api`;
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
export const API_MODE = API_BASE_URL === "/api" ? "local-proxy" : "remote";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

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

export default client;
