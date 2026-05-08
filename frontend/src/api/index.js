import axios from "axios";

const client = axios.create({
  baseURL: "/api",
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
