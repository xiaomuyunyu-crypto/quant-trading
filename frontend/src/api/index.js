import axios from "axios";

const DEFAULT_REMOTE_API_BASE_URL = "https://quant-trading-pyyo.onrender.com/api";

function normalizeApiBaseUrl(value) {
  const raw = (value || "").trim().replace(/\/+$/, "");
  if (!raw) return "";
  return raw.endsWith("/api") ? raw : `${raw}/api`;
}

function resolveApiBaseUrl() {
  const configured = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
  if (configured) return configured;
  return import.meta.env.PROD ? DEFAULT_REMOTE_API_BASE_URL : "/api";
}

export const API_BASE_URL = resolveApiBaseUrl();
export const API_MODE = API_BASE_URL === "/api" ? "local-proxy" : "remote";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

// ── Render 冷启动预热 + 自动重试 ──

let _warmedUp = false;

async function warmUpRender() {
  if (_warmedUp || API_MODE !== "remote") return;
  try {
    await axios.get(`${API_BASE_URL}/health`, { timeout: 30000 });
    _warmedUp = true;
  } catch {
    // 预热失败不阻塞，后续请求走重试逻辑
  }
}

async function withRetry(fn, retries = 1) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const isNetworkError =
        err.code === "ERR_NETWORK" ||
        err.message === "Network Error" ||
        (err.message || "").includes("Network Error") ||
        (err.message || "").includes("timeout");

      if (isNetworkError && attempt < retries) {
        // Render 可能正在冷启动，等它唤醒后重试
        await new Promise((r) => setTimeout(r, 5000));
        continue;
      }
      throw err;
    }
  }
}

// 响应拦截器 — 解包 data
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

// ── 封装后的 API 方法 ──

const api = {
  get(url, config) {
    const fn = () => client.get(url, config);
    // GET 请求先预热，再发送
    if (API_MODE === "remote") {
      return warmUpRender().then(() => withRetry(fn));
    }
    return fn();
  },

  post(url, data, config) {
    const fn = () => client.post(url, data, config);
    if (API_MODE === "remote") {
      return warmUpRender().then(() => withRetry(fn));
    }
    return fn();
  },

  put(url, data, config) {
    const fn = () => client.put(url, data, config);
    if (API_MODE === "remote") {
      return warmUpRender().then(() => withRetry(fn));
    }
    return fn();
  },

  delete(url, config) {
    const fn = () => client.delete(url, config);
    if (API_MODE === "remote") {
      return warmUpRender().then(() => withRetry(fn));
    }
    return fn();
  },
};

export default api;
