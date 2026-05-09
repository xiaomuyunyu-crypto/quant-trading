import { useCallback, useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  BriefcaseBusiness,
  Check,
  CircleDollarSign,
  PauseCircle,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import api from "../api/index";
import StockSearchInput, { formatStockLabel } from "../components/StockSearchInput";
import {
  Button,
  EmptyState,
  LoadingState,
  MetricCard,
  Notice,
  PageHeader,
  Panel,
  SignalBadge,
  TableShell,
} from "../components/WorkbenchUI";
import { compactDate, formatCurrency, formatNumber, formatPercent, toneByValue } from "../lib/format";

export default function Paper() {
  const [accounts, setAccounts] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [signals, setSignals] = useState(null);
  const [trades, setTrades] = useState([]);
  const [equityCurve, setEquityCurve] = useState([]);
  const [extraStocks, setExtraStocks] = useState([]);
  const [stockInput, setStockInput] = useState("");
  const [selectedStock, setSelectedStock] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("我的模拟账户");
  const [newCapital, setNewCapital] = useState(10000);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState("");

  const loadSummary = useCallback(async (id) => {
    if (!id) return;
    setError("");
    try {
      const [detail, tradeRes, equityRes] = await Promise.all([
        api.get(`/paper/account/${id}`),
        api.get(`/paper/account/${id}/trades?limit=50`),
        api.get(`/paper/account/${id}/equity`),
      ]);
      setSummary(detail);
      setTrades(tradeRes.trades || []);
      setEquityCurve(equityRes.equity_curve || []);
      if (!signals && (detail.pending_signals || []).length > 0) {
        const pending = detail.pending_signals || [];
        setSignals({
          scope: "pending",
          total: pending.length,
          all: pending,
        });
      }
    } catch (e) {
      setError(e.message || "账户加载失败");
    }
  }, [signals]);

  const loadAccounts = useCallback(async () => {
    setPageLoading(true);
    setError("");
    try {
      const res = await api.get("/paper/accounts");
      const items = res.items || [];
      setAccounts(items);
      if (!activeId && items.length > 0) {
        const first = items.find((item) => item.status === "active") || items[0];
        setActiveId(first.id);
        await loadSummary(first.id);
      }
    } catch (e) {
      setAccounts([]);
      setError(e.message || "后端未连接，无法读取模拟账户");
    } finally {
      setPageLoading(false);
    }
  }, [activeId, loadSummary]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const createAccount = async () => {
    setLoading(true);
    setError("");
    try {
      const account = await api.post("/paper/account", {
        name: newName,
        initial_capital: Number(newCapital),
        strategy_key: "composite_majority",
      });
      setShowCreate(false);
      setActiveId(account.id);
      setSignals(null);
      await loadAccounts();
      await loadSummary(account.id);
    } catch (e) {
      setError(e.message || "创建账户失败");
    } finally {
      setLoading(false);
    }
  };

  const switchAccount = async (id) => {
    setActiveId(id);
    setSummary(null);
    setSignals(null);
    setTrades([]);
    setEquityCurve([]);
    setExtraStocks([]);
    await loadSummary(id);
  };

  const generateSignals = async (scope = "holdings") => {
    if (!activeId) {
      setError("请先选择或创建模拟账户");
      return;
    }
    if (scope === "manual" && extraStocks.length === 0) {
      setError("请先手动选择要查看的股票");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        account_id: String(activeId),
        scope,
      });
      if (scope === "manual") {
        params.set("codes", extraStocks.map((stock) => stock.code).join(","));
      }
      const res = await api.post(`/paper/signals/generate?${params.toString()}`);
      setSignals(res);
      await loadSummary(activeId);
    } catch (e) {
      setError(e.message || "信号生成失败");
    } finally {
      setLoading(false);
    }
  };

  const confirmSignal = async (signalId, action) => {
    setLoading(true);
    setError("");
    try {
      await api.post("/paper/signals/confirm", { signal_id: signalId, action });
      await loadSummary(activeId);
      setSignals((prev) => {
        if (!prev) return prev;
        const all = (prev.all || []).map((item) =>
          item.id === signalId
            ? { ...item, status: action === "confirm" ? "confirmed" : "rejected" }
            : item
        );
        return { ...prev, all, total: all.filter((item) => item.status === "pending").length };
      });
    } catch (e) {
      setError(e.message || "处理信号失败");
    } finally {
      setLoading(false);
    }
  };

  const refreshPrices = async () => {
    if (!activeId) return;
    setLoading(true);
    setError("");
    try {
      await api.post(`/paper/account/${activeId}/refresh-prices`);
      await loadSummary(activeId);
    } catch (e) {
      setError(e.message || "刷新价格失败");
    } finally {
      setLoading(false);
    }
  };

  const stopAccount = async () => {
    if (!activeId || !confirm("确定停止该账户？将按当前价格结算。")) return;
    setLoading(true);
    try {
      await api.post(`/paper/account/${activeId}/stop`);
      await loadAccounts();
      await loadSummary(activeId);
    } catch (e) {
      setError(e.message || "停止账户失败");
    } finally {
      setLoading(false);
    }
  };

  const addExtraStock = (stock) => {
    setExtraStocks((prev) =>
      prev.some((item) => item.code === stock.code) ? prev : [...prev, stock]
    );
    setStockInput("");
    setSelectedStock(null);
  };

  const pendingSignals = useMemo(
    () => (signals?.all || []).filter((item) => item.status !== "confirmed" && item.status !== "rejected"),
    [signals]
  );

  if (pageLoading) {
    return <LoadingState label="正在加载模拟账户..." />;
  }

  return (
    <div className="flex min-h-full">
      <aside className="w-72 shrink-0 border-r border-slate-800 bg-slate-950/50 p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-base font-semibold text-slate-100">模拟账户</div>
            <div className="mt-1 text-xs text-slate-600">手动确认，不自动下单</div>
          </div>
          <Button size="sm" icon={Plus} onClick={() => setShowCreate((value) => !value)}>
            新建
          </Button>
        </div>

        {showCreate && (
          <div className="mb-4 space-y-2 rounded border border-slate-800 bg-slate-900/70 p-3">
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              className="h-9 w-full rounded border border-slate-700 bg-slate-950 px-3 text-sm outline-none focus:border-blue-500"
              placeholder="账户名称"
            />
            <input
              type="number"
              value={newCapital}
              onChange={(event) => setNewCapital(event.target.value)}
              className="h-9 w-full rounded border border-slate-700 bg-slate-950 px-3 font-mono text-sm outline-none focus:border-blue-500"
              placeholder="初始资金"
            />
            <Button variant="success" size="sm" className="w-full" onClick={createAccount} disabled={loading}>
              创建账户
            </Button>
          </div>
        )}

        <div className="space-y-2">
          {accounts.length === 0 ? (
            <EmptyState title="暂无账户" description="创建模拟账户后再生成交易信号。" />
          ) : (
            accounts.map((account) => (
              <button
                key={account.id}
                onClick={() => switchAccount(account.id)}
                className={`w-full rounded border px-3 py-3 text-left transition-colors ${
                  activeId === account.id
                    ? "border-blue-500/60 bg-blue-500/10"
                    : "border-slate-800 bg-slate-900/50 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-slate-100">{account.name}</span>
                  <span className={account.status === "active" ? "text-xs text-emerald-300" : "text-xs text-slate-500"}>
                    {account.status === "active" ? "运行中" : "已停止"}
                  </span>
                </div>
                <div className="mt-1 font-mono text-xs text-slate-500">
                  {formatCurrency(account.initial_capital)}
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-5">
        <PageHeader
          title="实盘模拟跟踪"
          description="把策略信号变成可记录的手动操作：生成信号、确认/拒绝、按收盘价记录、复盘表现。"
        >
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={RefreshCw} onClick={refreshPrices} disabled={!activeId || loading}>
              刷新现价
            </Button>
            {summary?.account?.status === "active" && (
              <Button variant="danger" icon={PauseCircle} onClick={stopAccount} disabled={loading}>
                停止结算
              </Button>
            )}
          </div>
        </PageHeader>

        {error && <Notice tone="error" className="mb-4">{error}</Notice>}

        {!activeId ? (
          <EmptyState title="请先创建模拟账户" description="账户用于承载持仓、信号、交易记录和权益曲线。" />
        ) : !summary ? (
          <LoadingState label="正在读取账户详情..." />
        ) : (
          <div className="space-y-5">
            <AccountOverview summary={summary} equityCurve={equityCurve} />

            <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
              <PositionsPanel positions={summary.positions || []} />
              <SignalsPanel
                loading={loading}
                extraStocks={extraStocks}
                setExtraStocks={setExtraStocks}
                stockInput={stockInput}
                selectedStock={selectedStock}
                setStockInput={setStockInput}
                setSelectedStock={setSelectedStock}
                addExtraStock={addExtraStock}
                generateSignals={generateSignals}
                pendingSignals={pendingSignals}
                confirmSignal={confirmSignal}
              />
            </div>

            <TradesPanel trades={trades} />
          </div>
        )}
      </main>
    </div>
  );
}

function AccountOverview({ summary, equityCurve }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1.1fr]">
      <Panel
        title={summary.account.name}
        description={`${summary.account.status === "active" ? "运行中" : "已停止"} · 策略 ${summary.account.strategy_key || "默认"}`}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <MetricCard label="总权益" value={formatCurrency(summary.total_equity)} tone={toneByValue(summary.total_return)} icon={BriefcaseBusiness} />
          <MetricCard label="收益率" value={formatPercent(summary.total_return_pct, 2, true)} tone={toneByValue(summary.total_return_pct)} icon={CircleDollarSign} />
          <MetricCard label="现金" value={formatCurrency(summary.account.cash)} />
          <MetricCard label="持仓数量" value={formatNumber(summary.positions?.length || 0)} unit="只" />
        </div>
      </Panel>

      <Panel title="权益曲线" description="当前版本基于交易记录和当前权益重建。">
        {equityCurve.length <= 1 ? (
          <EmptyState title="权益点不足" description="确认交易后会逐步形成权益曲线。" />
        ) : (
          <ReactECharts option={equityOption(equityCurve)} style={{ height: 260 }} notMerge />
        )}
      </Panel>
    </div>
  );
}

function PositionsPanel({ positions }) {
  return (
    <Panel title="持仓明细" description="观察股默认来自当前账户持仓。">
      {positions.length === 0 ? (
        <EmptyState title="暂无持仓" description="确认买入信号后，持仓会出现在这里。" />
      ) : (
        <TableShell minWidth="720px">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-500">
              <th className="px-3 py-2 font-normal">标的</th>
              <th className="px-3 py-2 text-right font-normal">持仓</th>
              <th className="px-3 py-2 text-right font-normal">成本价</th>
              <th className="px-3 py-2 text-right font-normal">现价</th>
              <th className="px-3 py-2 text-right font-normal">市值</th>
              <th className="px-3 py-2 text-right font-normal">浮盈</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr key={position.code} className="border-b border-slate-800/60 hover:bg-slate-900">
                <td className="px-3 py-2.5">
                  <div className="text-sm text-slate-100">{position.name || "未命名"}</div>
                  <div className="font-mono text-xs text-slate-500">{position.code}</div>
                </td>
                <td className="px-3 py-2.5 text-right font-mono">{formatNumber(position.quantity)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatNumber(position.cost_price, 2)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatNumber(position.current_price, 2)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatCurrency(position.market_value)}</td>
                <td className={`px-3 py-2.5 text-right font-mono ${(position.unrealized_pnl || 0) >= 0 ? "text-up" : "text-down"}`}>
                  {formatCurrency(position.unrealized_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      )}
    </Panel>
  );
}

function SignalsPanel({
  loading,
  extraStocks,
  setExtraStocks,
  stockInput,
  selectedStock,
  setStockInput,
  setSelectedStock,
  addExtraStock,
  generateSignals,
  pendingSignals,
  confirmSignal,
}) {
  return (
    <Panel
      title="交易信号"
      description="默认分析观察股；自选股扫描需要显式触发；手动标的用于临时查看。"
      actions={
        <>
          <Button size="sm" icon={RefreshCw} onClick={() => generateSignals("holdings")} disabled={loading}>
            分析观察股
          </Button>
          <Button size="sm" variant="secondary" icon={StarIcon} onClick={() => generateSignals("watchlist")} disabled={loading}>
            自选股
          </Button>
          <Button size="sm" variant="secondary" icon={Search} onClick={() => generateSignals("manual")} disabled={loading || extraStocks.length === 0}>
            手动查看
          </Button>
        </>
      }
    >
      <div className="mb-4 rounded border border-slate-800 bg-slate-950/50 p-3">
        <StockSearchInput
          value={stockInput}
          selectedStock={selectedStock}
          onChange={(value) => {
            setStockInput(value);
            setSelectedStock(null);
          }}
          onSelect={(stock) => {
            setSelectedStock(stock);
            setStockInput(formatStockLabel(stock));
            addExtraStock(stock);
          }}
          placeholder="添加临时观察标的，例如 万化 / 600309"
          helperText="选择后可点击“手动查看”生成信号"
        />
        {extraStocks.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {extraStocks.map((stock) => (
              <button
                key={stock.code}
                onClick={() => setExtraStocks((prev) => prev.filter((item) => item.code !== stock.code))}
                className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300 hover:border-red-600 hover:text-red-300"
              >
                <span className="font-mono">{stock.code}</span>
                <span>{stock.name}</span>
                <X className="h-3 w-3" strokeWidth={1.8} />
              </button>
            ))}
          </div>
        )}
      </div>

      {pendingSignals.length === 0 ? (
        <EmptyState title="暂无待处理信号" description="点击上方按钮生成当前范围的交易建议。" />
      ) : (
        <div className="space-y-2">
          {pendingSignals.map((signal) => (
            <div
              key={signal.id}
              className="rounded border border-slate-800 bg-slate-950/50 p-3"
            >
              <div className="flex items-start gap-3">
                <SignalBadge type={signal.signal_type} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-slate-100">
                    {signal.name || "未命名"}{" "}
                    <span className="font-mono text-xs text-slate-500">{signal.code}</span>
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {signal.reason || "暂无理由"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-xs text-slate-400">
                    @{formatNumber(signal.close_price, 2)}
                  </div>
                  <div className="mt-1 text-xs text-slate-600">
                    {Math.round((signal.confidence || 0) * 100)}%
                  </div>
                </div>
              </div>
              <div className="mt-3 flex justify-end gap-2">
                <Button size="sm" variant="success" icon={Check} onClick={() => confirmSignal(signal.id, "confirm")}>
                  确认
                </Button>
                <Button size="sm" variant="secondary" icon={X} onClick={() => confirmSignal(signal.id, "reject")}>
                  拒绝
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function TradesPanel({ trades }) {
  return (
    <Panel title={`交易记录 · ${trades.length} 笔`} description="按确认后的模拟交易倒序展示。">
      {trades.length === 0 ? (
        <EmptyState title="暂无交易记录" description="确认买入或卖出信号后，这里会记录操作。" />
      ) : (
        <TableShell minWidth="760px">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-500">
              <th className="px-3 py-2 font-normal">日期</th>
              <th className="px-3 py-2 text-center font-normal">操作</th>
              <th className="px-3 py-2 font-normal">代码</th>
              <th className="px-3 py-2 text-right font-normal">价格</th>
              <th className="px-3 py-2 text-right font-normal">股数</th>
              <th className="px-3 py-2 text-right font-normal">金额</th>
              <th className="px-3 py-2 font-normal">理由</th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 30).map((trade) => (
              <tr key={trade.id} className={`border-b border-slate-800/60 ${trade.action === "BUY" ? "bg-red-500/5" : "bg-emerald-500/5"}`}>
                <td className="px-3 py-2.5 text-slate-400">{compactDate(trade.trade_date)}</td>
                <td className="px-3 py-2.5 text-center">
                  <SignalBadge type={trade.action}>{trade.action === "BUY" ? "买" : "卖"}</SignalBadge>
                </td>
                <td className="px-3 py-2.5 font-mono text-slate-300">{trade.code}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatNumber(trade.price, 2)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatNumber(trade.quantity)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{formatCurrency(trade.amount)}</td>
                <td className="max-w-xs truncate px-3 py-2.5 text-slate-500" title={trade.reason}>
                  {trade.reason || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      )}
    </Panel>
  );
}

function equityOption(points) {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: "8%", right: "5%", top: 18, bottom: 28 },
    xAxis: {
      type: "category",
      data: points.map((point) => compactDate(point.date)),
      axisLabel: { color: "#64748b", fontSize: 10 },
      axisLine: { lineStyle: { color: "#334155" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#64748b", formatter: "¥{value}" },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    series: [
      {
        type: "line",
        data: points.map((point) => point.equity),
        symbol: "none",
        lineStyle: { color: "#38bdf8", width: 1.8 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(56,189,248,0.2)" },
              { offset: 1, color: "rgba(56,189,248,0)" },
            ],
          },
        },
      },
    ],
  };
}

function StarIcon(props) {
  return <BriefcaseBusiness {...props} />;
}
