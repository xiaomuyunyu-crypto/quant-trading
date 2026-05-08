import { useState, useEffect, useCallback, useRef } from "react";
import ReactECharts from "echarts-for-react";
import api from "../api/index";

export default function Paper() {
  const [accounts, setAccounts] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [signals, setSignals] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [equityCurve, setEquityCurve] = useState([]);
  const [newName, setNewName] = useState("我的模拟账户");
  const [newCapital, setNewCapital] = useState(10000);
  const [extraStocks, setExtraStocks] = useState([]);

  // 加载账户列表
  const loadAccounts = useCallback(async () => {
    try {
      const res = await api.get("/paper/accounts");
      setAccounts(res.items || []);
    } catch { setAccounts([]); }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  // 创建账户
  const createAccount = async () => {
    setError("");
    try {
      const acct = await api.post("/paper/account", {
        name: newName, initial_capital: Number(newCapital),
        strategy_key: "composite_majority",
      });
      setShowCreate(false);
      await loadAccounts();
      setActiveId(acct.id);
      loadSummary(acct.id);
    } catch (e) { setError(e.message); }
  };

  // 加载账户摘要
  const loadSummary = async (id) => {
    setError("");
    try {
      const [s, t, e] = await Promise.all([
        api.get(`/paper/account/${id}`),
        api.get(`/paper/account/${id}/trades?limit=50`),
        api.get(`/paper/account/${id}/equity`),
      ]);
      setSummary(s);
      setTrades(t.trades || []);
      setEquityCurve(e.equity_curve || []);
      setSignals(prev => {
        if (prev) return prev;
        const pending = s.pending_signals || [];
        if (pending.length === 0) return prev;
        return {
          scope: "pending",
          total: pending.length,
          buy_signals: pending.filter(item => item.signal_type === "BUY"),
          sell_signals: pending.filter(item => item.signal_type === "SELL"),
          all: pending,
        };
      });
    } catch (e) { setError(e.message); }
  };

  // 切换账户
  const switchAccount = (id) => {
    setActiveId(id);
    setSignals(null);
    setSummary(null);
    setTrades([]);
    setExtraStocks([]);
    loadSummary(id);
  };

  // 生成信号
  const generateSignals = async (scope = "holdings") => {
    setError(""); setLoading(true);
    try {
      const params = new URLSearchParams({
        account_id: String(activeId),
        scope,
      });
      if (scope === "manual") {
        if (extraStocks.length === 0) {
          setError("请先手动选择要查看的股票");
          return;
        }
        params.set("codes", extraStocks.map(stock => stock.code).join(","));
      }
      const res = await api.post(`/paper/signals/generate?${params.toString()}`);
      setSignals(res);
      await loadSummary(activeId);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const addExtraStock = (stock) => {
    setExtraStocks(prev => (
      prev.some(item => item.code === stock.code) ? prev : [...prev, stock]
    ));
  };

  const removeExtraStock = (code) => {
    setExtraStocks(prev => prev.filter(stock => stock.code !== code));
  };

  // 确认/拒绝信号
  const confirmSignal = async (signalId, action) => {
    setError("");
    try {
      await api.post("/paper/signals/confirm", { signal_id: signalId, action });
      // 交易后刷新全部数据
      await loadSummary(activeId);
      // 更新信号列表状态
      setSignals(prev => {
        if (!prev) return prev;
        const all = prev.all.map(s => s.id === signalId ? { ...s, status: action === "confirm" ? "confirmed" : "rejected" } : s);
        return { ...prev, all,
          buy_signals: all.filter(s => s.signal_type === "BUY" && s.status === "pending"),
          sell_signals: all.filter(s => s.signal_type === "SELL" && s.status === "pending"),
        };
      });
    } catch (e) { setError(e.message); }
  };

  // 刷新价格
  const refreshPrices = async () => {
    setError("");
    try {
      await api.post(`/paper/account/${activeId}/refresh-prices`);
      loadSummary(activeId);
    } catch (e) { setError(e.message); }
  };

  // 停止账户
  const stopAccount = async () => {
    if (!confirm("确定停止该账户？将按当前价格结算。")) return;
    try {
      await api.post(`/paper/account/${activeId}/stop`);
      loadAccounts();
      loadSummary(activeId);
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="flex flex-1 min-h-0">
      {/* ===== 左侧：账户管理 ===== */}
      <aside className="w-64 shrink-0 border-r border-gray-800 bg-gray-900/50 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <span className="text-sm font-bold">实盘模拟</span>
          <button onClick={() => setShowCreate(!showCreate)}
            className="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded">+ 新建</button>
        </div>

        {/* 新建账户 */}
        {showCreate && (
          <div className="p-3 border-b border-gray-800 space-y-2">
            <input value={newName} onChange={e => setNewName(e.target.value)}
              className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs" placeholder="账户名称" />
            <input type="number" value={newCapital} onChange={e => setNewCapital(e.target.value)}
              className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs" placeholder="初始资金" />
            <button onClick={createAccount}
              className="w-full py-1.5 bg-green-600 hover:bg-green-700 rounded text-xs font-medium">创建</button>
          </div>
        )}

        {/* 账户列表 */}
        <div className="flex-1 overflow-auto">
          {accounts.map(a => (
            <button key={a.id} onClick={() => switchAccount(a.id)}
              className={`w-full text-left px-4 py-3 border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors ${
                activeId === a.id ? "bg-blue-600/20 border-l-2 border-l-blue-500" : ""
              }`}>
              <div className="text-sm font-medium">{a.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {a.status === "active" ? "● 运行中" : "○ 已停止"} · ¥{a.initial_capital.toLocaleString()}
              </div>
            </button>
          ))}
          {accounts.length === 0 && (
            <div className="p-4 text-xs text-gray-600 text-center">暂无账户，点击"+ 新建"创建</div>
          )}
        </div>
      </aside>

      {/* ===== 右侧：详情 ===== */}
      <main className="flex-1 overflow-auto p-5">
        {error && (
          <div className="mb-4 px-4 py-2 bg-red-900/30 border border-red-700 rounded text-red-400 text-xs">{error}</div>
        )}

        {!activeId ? (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            请先创建一个模拟账户
          </div>
        ) : summary ? (
          <div className="space-y-5">
            {/* 权益概览 */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold">{summary.account.name}</h2>
                <span className="text-xs text-gray-600">
                  {summary.account.status === "active" ? "运行中" : "已停止"} · 策略: {summary.account.strategy_key || "默认"}
                </span>
              </div>
              <div className="flex gap-2">
                <button onClick={refreshPrices} className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded">刷新现价</button>
                {summary.account.status === "active" && (
                  <button onClick={stopAccount} className="px-3 py-1.5 text-xs bg-red-900/50 hover:bg-red-800 rounded text-red-400">停止结算</button>
                )}
              </div>
            </div>

            {/* 指标卡片 */}
            <div className="grid grid-cols-4 gap-4">
              <Card label="总权益" value={`¥${summary.total_equity.toFixed(2)}`} />
              <Card label="收益率" value={`${summary.total_return_pct >= 0 ? "+" : ""}${summary.total_return_pct.toFixed(2)}%`}
                color={summary.total_return_pct >= 0 ? "text-green-400" : "text-red-400"} />
              <Card label="现金" value={`¥${summary.account.cash.toFixed(2)}`} />
              <Card label="持仓数" value={`${summary.positions.length}只`} />
            </div>

            {/* 权益曲线图 */}
            {equityCurve.length > 1 && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">权益曲线</h3>
                <ReactECharts
                  option={{
                    backgroundColor: "transparent",
                    tooltip: { trigger: "axis" },
                    grid: { left: "8%", right: "5%", top: 20, bottom: 30 },
                    xAxis: {
                      type: "category",
                      data: equityCurve.map(p => p.date?.slice(0,10)),
                      axisLabel: { color: "#6b7280", fontSize: 10 },
                    },
                    yAxis: {
                      type: "value",
                      axisLabel: { color: "#6b7280", formatter: "¥{value}" },
                      splitLine: { lineStyle: { color: "#1f2937" } },
                    },
                    series: [{
                      type: "line",
                      data: equityCurve.map(p => p.equity),
                      smooth: false,
                      symbol: "none",
                      lineStyle: { color: "#22c55e", width: 1.5 },
                      areaStyle: {
                        color: {
                          type: "linear", x: 0, y: 0, x2: 0, y2: 1,
                          colorStops: [
                            { offset: 0, color: "rgba(34,197,94,0.15)" },
                            { offset: 1, color: "rgba(34,197,94,0)" },
                          ],
                        },
                      },
                    }],
                  }}
                  style={{ height: 280 }}
                  notMerge
                />
              </div>
            )}

            {/* 持仓明细 */}
            {summary.positions.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">持仓明细</h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-800">
                      <th className="py-2 text-left font-normal">标的</th>
                      <th className="py-2 text-right font-normal">持仓</th>
                      <th className="py-2 text-right font-normal">成本价</th>
                      <th className="py-2 text-right font-normal">现价</th>
                      <th className="py-2 text-right font-normal">市值</th>
                      <th className="py-2 text-right font-normal">浮盈</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.positions.map(p => (
                      <tr key={p.code} className="border-b border-gray-800/30">
                        <td className="py-2.5">
                          <div className="text-sm text-gray-100">{p.name || "未命名"}</div>
                          <div className="font-mono text-xs text-gray-500">{p.code}</div>
                        </td>
                        <td className="py-2.5 text-right font-mono">{p.quantity}股</td>
                        <td className="py-2.5 text-right font-mono">{p.cost_price.toFixed(2)}</td>
                        <td className="py-2.5 text-right font-mono">{p.current_price.toFixed(2)}</td>
                        <td className="py-2.5 text-right font-mono">¥{p.market_value?.toFixed(2) || "0.00"}</td>
                        <td className={`py-2.5 text-right font-mono ${(p.unrealized_pnl || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {(p.unrealized_pnl || 0) >= 0 ? "+" : ""}{(p.unrealized_pnl || 0).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* 信号区 */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-medium text-gray-400">交易信号</h3>
                  <div className="mt-1 text-xs text-gray-600">
                    默认分析观察股，手动添加可单独查看额外标的
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => generateSignals("holdings")} disabled={loading}
                    className={`px-3 py-1.5 text-xs rounded font-medium ${
                      loading ? "bg-gray-700 text-gray-500" : "bg-blue-600 hover:bg-blue-700 text-white"
                    }`}>
                    {loading ? "分析中..." : "分析观察股"}
                  </button>
                  <button onClick={() => generateSignals("watchlist")} disabled={loading}
                    className={`px-3 py-1.5 text-xs rounded font-medium ${
                      loading ? "bg-gray-700 text-gray-500" : "bg-gray-700 hover:bg-gray-600 text-gray-200"
                    }`}>
                    自选股
                  </button>
                  <button onClick={() => generateSignals("manual")} disabled={loading || extraStocks.length === 0}
                    className={`px-3 py-1.5 text-xs rounded font-medium ${
                      loading || extraStocks.length === 0
                        ? "bg-gray-800 text-gray-600"
                        : "bg-green-600 hover:bg-green-700 text-white"
                    }`}>
                    手动查看
                  </button>
                </div>
              </div>

              <div className="mb-4 rounded border border-gray-800 bg-gray-950/40 p-3">
                <ManualStockPicker onAdd={addExtraStock} />
                {extraStocks.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {extraStocks.map(stock => (
                      <button
                        key={stock.code}
                        type="button"
                        onClick={() => removeExtraStock(stock.code)}
                        className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-300 hover:border-red-700 hover:text-red-300"
                      >
                        <span className="font-mono">{stock.code}</span> · {stock.name} ×
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {!signals ? (
                <div className="text-xs text-gray-600 py-6 text-center">点击"分析观察股"获取当前持仓的买入/卖出建议</div>
              ) : signals.total === 0 ? (
                <div className="text-xs text-gray-600 py-6 text-center">当前无可交易信号</div>
              ) : (
                <div className="space-y-2">
                  {signals.all.filter(s => s.status === "pending").map(s => (
                    <div key={s.id} className={`flex items-center gap-3 px-3 py-2.5 rounded border ${
                      s.signal_type === "BUY" ? "bg-green-900/10 border-green-800/50" :
                      s.signal_type === "SELL" ? "bg-red-900/10 border-red-800/50" :
                      "bg-gray-800/50 border-gray-700/50"
                    }`}>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        s.signal_type === "BUY" ? "bg-green-900/50 text-green-400" :
                        s.signal_type === "SELL" ? "bg-red-900/50 text-red-400" :
                        "bg-gray-700 text-gray-400"
                      }`}>{s.signal_type}</span>
                      <span className="min-w-0 flex-1">
                        <span className="mr-2 text-sm text-gray-100">{s.name || "未命名"}</span>
                        <span className="font-mono text-xs text-gray-500">{s.code}</span>
                      </span>
                      <span className="text-xs text-gray-500">@{s.close_price.toFixed(2)}</span>
                      <span className="text-xs text-gray-600">置信度: {(s.confidence*100).toFixed(0)}%</span>
                      <button onClick={() => confirmSignal(s.id, "confirm")}
                        className="px-3 py-1 text-xs bg-green-600 hover:bg-green-700 rounded font-medium">确认</button>
                      <button onClick={() => confirmSignal(s.id, "reject")}
                        className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded">拒绝</button>
                    </div>
                  ))}
                  {signals.all.filter(s => s.status === "pending").length === 0 && (
                    <div className="text-xs text-gray-600 py-6 text-center">所有信号已处理</div>
                  )}
                </div>
              )}
            </div>

            {/* 交易记录 */}
            {trades.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">交易记录 · {trades.length}笔</h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-800">
                      <th className="py-2 text-left font-normal">日期</th>
                      <th className="py-2 text-center font-normal">操作</th>
                      <th className="py-2 text-left font-normal">代码</th>
                      <th className="py-2 text-right font-normal">价格</th>
                      <th className="py-2 text-right font-normal">股数</th>
                      <th className="py-2 text-right font-normal">金额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.slice(0, 20).map(t => (
                      <tr key={t.id} className={`border-b border-gray-800/30 ${t.action === "BUY" ? "bg-green-900/5" : "bg-red-900/5"}`}>
                        <td className="py-2 text-gray-400">{t.trade_date?.slice(0, 10)}</td>
                        <td className="py-2 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${t.action === "BUY" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>
                            {t.action === "BUY" ? "买" : "卖"}
                          </span>
                        </td>
                        <td className="py-2 font-mono">{t.code}</td>
                        <td className="py-2 text-right font-mono">{t.price.toFixed(2)}</td>
                        <td className="py-2 text-right font-mono">{t.quantity}</td>
                        <td className="py-2 text-right font-mono">¥{t.amount.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </main>
    </div>
  );
}

function Card({ label, value, color = "text-white" }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function ManualStockPicker({ onAdd }) {
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const boxRef = useRef(null);

  useEffect(() => {
    const handleMouseDown = (event) => {
      if (boxRef.current && !boxRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  useEffect(() => {
    const keyword = value.trim();
    if (!open || !keyword) {
      setItems([]);
      setMessage("");
      setLoading(false);
      return;
    }

    let canceled = false;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setMessage("");
      try {
        const res = await api.get("/stocks/search", {
          params: { keyword, limit: 8 },
        });
        if (canceled) return;
        const nextItems = res.items || [];
        setItems(nextItems);
        setMessage(nextItems.length === 0 ? "没有匹配的股票" : "");
      } catch (e) {
        if (canceled) return;
        setItems([]);
        setMessage(e.message || "搜索失败");
      } finally {
        if (!canceled) setLoading(false);
      }
    }, 180);

    return () => {
      canceled = true;
      window.clearTimeout(timer);
    };
  }, [open, value]);

  const showPanel = open && (loading || message || items.length > 0);

  const selectStock = (stock) => {
    onAdd(stock);
    setValue("");
    setOpen(false);
  };

  return (
    <div ref={boxRef} className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="输入股票名称或代码，例如 万化 / 600309"
        className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm focus:outline-none focus:border-orange-500"
      />

      {showPanel && (
        <div className="absolute left-0 right-0 top-10 z-30 overflow-hidden rounded border border-gray-700 bg-gray-950 shadow-2xl">
          <div className="grid grid-cols-[54px_78px_1fr] border-b border-gray-800 bg-gray-900 px-3 py-2 text-xs text-gray-500">
            <span>市场</span>
            <span>代码</span>
            <span>名称</span>
          </div>

          {loading ? (
            <div className="px-3 py-3 text-xs text-gray-500">搜索中...</div>
          ) : message ? (
            <div className="px-3 py-3 text-xs text-gray-500">{message}</div>
          ) : (
            <div className="max-h-72 overflow-auto">
              {items.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    selectStock(item);
                  }}
                  className="grid w-full grid-cols-[54px_78px_1fr] items-center border-b border-gray-900 px-3 py-2.5 text-left text-sm hover:bg-gray-800"
                >
                  <span className="w-10 bg-blue-600 px-1.5 py-0.5 text-center text-xs text-white">
                    {item.market_label || item.exchange || "-"}
                  </span>
                  <span className="font-mono text-gray-300">{item.code}</span>
                  <span className="truncate text-gray-100">{item.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
