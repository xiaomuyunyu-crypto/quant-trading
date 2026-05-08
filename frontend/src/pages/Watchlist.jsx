import { useState, useEffect, useCallback } from "react";
import api from "../api/index";

const MOCK = {
  total: 5,
  items: [
    { code: "000001", name: "平安银行", exchange: "SZ", industry: "银行", current: 10.52, change_pct: 1.15 },
    { code: "000002", name: "万科A", exchange: "SZ", industry: "房地产", current: 15.30, change_pct: -0.85 },
    { code: "600036", name: "招商银行", exchange: "SH", industry: "银行", current: 38.20, change_pct: 0.50 },
    { code: "000858", name: "五粮液", exchange: "SZ", industry: "白酒", current: 168.50, change_pct: 2.10 },
    { code: "300750", name: "宁德时代", exchange: "SZ", industry: "新能源", current: 205.30, change_pct: -1.20 },
  ],
};

export default function Watchlist() {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);

  const fetchList = useCallback(() => {
    setLoading(true);
    api
      .get("/watchlist")
      .then((res) => setStocks(res.items || []))
      .catch(() => {
        setError("后端未连接，展示Mock数据");
        setStocks(MOCK.items);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const filtered = stocks.filter(
    (s) =>
      s.code.includes(search) || s.name.includes(search.toUpperCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">自选股管理</h1>
        <button
          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm transition-colors"
          onClick={() => alert("搜索添加功能将在后端就绪后启用")}
        >
          + 添加自选股
        </button>
      </div>
      {error && (
        <div className="mb-4 px-4 py-2 bg-yellow-900/30 border border-yellow-700 rounded text-yellow-400 text-sm">
          {error}
        </div>
      )}
      {/* 搜索栏 */}
      <input
        type="text"
        placeholder="搜索股票代码或名称..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md mb-4 px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
      />
      {/* 表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="py-3 px-4 font-normal">代码</th>
              <th className="py-3 px-4 font-normal">名称</th>
              <th className="py-3 px-4 font-normal">交易所</th>
              <th className="py-3 px-4 font-normal">行业</th>
              <th className="py-3 px-4 font-normal text-right">最新价</th>
              <th className="py-3 px-4 font-normal text-right">涨跌幅</th>
              <th className="py-3 px-4 font-normal">操作</th>
            </tr>
          </thead>
          {loading ? (
            <tbody>
              <tr>
                <td colSpan={7} className="py-12 text-center text-gray-600">
                  加载中...
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody>
              {filtered.map((s) => (
                <tr
                  key={s.code}
                  className="border-b border-gray-800/50 hover:bg-gray-900/50 transition-colors"
                >
                  <td className="py-3 px-4 text-gray-400 font-mono">{s.code}</td>
                  <td className="py-3 px-4">{s.name}</td>
                  <td className="py-3 px-4 text-gray-500">{s.exchange}</td>
                  <td className="py-3 px-4 text-gray-500">{s.industry || "-"}</td>
                  <td className="py-3 px-4 text-right font-mono">
                    {s.current?.toFixed(2) || "-"}
                  </td>
                  <td
                    className={`py-3 px-4 text-right font-mono ${
                      (s.change_pct || 0) >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {(s.change_pct || 0) >= 0 ? "+" : ""}
                    {s.change_pct?.toFixed(2) || "0.00"}%
                  </td>
                  <td className="py-3 px-4">
                    <button className="text-red-500 hover:text-red-400 text-xs transition-colors">
                      移除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-gray-600">
                    无匹配结果
                  </td>
                </tr>
              )}
            </tbody>
          )}
        </table>
      </div>
    </div>
  );
}
