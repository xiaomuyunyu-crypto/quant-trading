import { useState, useEffect } from "react";
import api from "../api/index";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/dashboard")
      .then((res) => {
        setSummary(res);
      })
      .catch(() => {
        setError("后端未连接，展示Mock数据");
        setSummary({
          watchlistCount: 12,
          todayPnL: 1560.5,
          todayPnLPct: 1.52,
          totalEquity: 102300.0,
          activeStrategies: 2,
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        加载中...
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-6">仪表盘</h1>
      {error && (
        <div className="mb-4 px-4 py-2 bg-yellow-900/30 border border-yellow-700 rounded text-yellow-400 text-sm">
          {error}
        </div>
      )}
      <div className="grid grid-cols-4 gap-4">
        <Card label="自选股数量" value={summary.watchlistCount} unit="只" />
        <Card
          label="今日盈亏"
          value={summary.todayPnL.toFixed(2)}
          unit="元"
          up={summary.todayPnL >= 0}
        />
        <Card
          label="今日收益率"
          value={summary.todayPnLPct.toFixed(2)}
          unit="%"
          up={summary.todayPnLPct >= 0}
        />
        <Card label="总权益" value={summary.totalEquity.toFixed(2)} unit="元" />
        <Card
          label="活跃策略"
          value={summary.activeStrategies}
          unit="个"
        />
      </div>
    </div>
  );
}

function Card({ label, value, unit, up }) {
  const colorClass =
    up === true ? "text-up" : up === false ? "text-down" : "text-white";
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <div className="text-sm text-gray-500 mb-2">{label}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>
        {value}
        <span className="text-sm font-normal text-gray-500 ml-1">{unit}</span>
      </div>
    </div>
  );
}
