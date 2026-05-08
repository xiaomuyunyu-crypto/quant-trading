import { useState, useEffect } from "react";
import api from "../api/index";

export default function Settings() {
  const [stats, setStats] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    api
      .get("/dashboard")
      .then((res) => setStats(res))
      .catch(() => setLoadError("后端未连接"))
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-6">系统设置</h1>

      {stats && (
        <section className="mb-8">
          <h2 className="text-base font-semibold text-gray-300 mb-4">数据库统计</h2>
          <div className="grid grid-cols-4 gap-4 max-w-2xl">
            <StatCard label="总股票数" value={stats.totalStocks?.toLocaleString() || "-"} />
            <StatCard label="K线数据量" value={stats.totalKlines?.toLocaleString() || "-"} />
            <StatCard label="自选股" value={stats.watchlistCount || 0} />
            <StatCard label="最新数据" value={stats.latestDataDate || "-"} />
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-300 mb-4">数据源配置</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 max-w-lg">
          <ConfigRow label="当前数据源" value="AKShare" />
          <ConfigRow label="备选数据源" value="Tushare (未配置)" />
          <ConfigRow label="连接状态" value="● 正常" className="text-green-400" />
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-300 mb-4">API 连接</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 max-w-lg">
          <ConfigRow label="后端地址" value="http://localhost:8000" />
          <ConfigRow label="API 文档" value="/docs" href="http://localhost:8000/docs" />
          <ConfigRow label="连接状态" value={loadError ? "✗ 未连接" : "● 正常"} className={loadError ? "text-red-400" : "text-green-400"} />
        </div>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-300 mb-4">关于</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 max-w-lg text-sm text-gray-500 space-y-1">
          <p>量化交易系统 v0.1.0 MVP</p>
          <p>前端：React 18 + Vite + TailwindCSS + ECharts</p>
          <p>后端：FastAPI + SQLAlchemy 2.0 + Pydantic 2.x</p>
          <p>数据源：AKShare（主）/ Tushare（备）</p>
          <p>策略引擎：Backtrader 1.9+ / 自研组件化引擎</p>
        </div>
      </section>
    </div>
  );
}

function ConfigRow({ label, value, href, className = "" }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800/50 last:border-b-0">
      <span className="text-sm text-gray-400">{label}</span>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className={`text-sm hover:underline ${className || "text-blue-400"}`}>
          {value}
        </a>
      ) : (
        <span className={`text-sm ${className || "text-gray-200"}`}>{value}</span>
      )}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-white">{value}</div>
    </div>
  );
}
