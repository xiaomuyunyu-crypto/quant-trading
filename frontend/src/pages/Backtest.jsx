import { useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  BarChart3,
  ChevronRight,
  FlaskConical,
  LineChart,
  Play,
  Search,
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
import { formatCurrency, formatNumber, formatPercent, toneByValue } from "../lib/format";

const ACTIVE_STRATEGY = {
  key: "triple_macd_ma250",
  name: "三周期MACD+250日均线状态机",
  desc: "月线MACD定方向，250日均线定长期开关，周线开窗口，日线执行买卖。",
};

const initialStock = { code: "000001", name: "平安银行", market_label: "深A" };

const ROLLING_STOCKS = [
  { code: "159915", name: "创业板ETF", market_label: "深A", initials: "CYBETF" },
  { code: "510300", name: "沪深300ETF", market_label: "沪A", initials: "HS300ETF" },
  { code: "510050", name: "上证50ETF", market_label: "沪A", initials: "SZ50ETF" },
  { code: "159949", name: "创业板50", market_label: "深A", initials: "CYB50" },
  { code: "512100", name: "中证1000ETF", market_label: "沪A", initials: "ZZ1000" },
  { code: "000001", name: "平安银行", market_label: "深A", initials: "PAYH" },
  { code: "600036", name: "招商银行", market_label: "沪A", initials: "ZSYH" },
  { code: "600519", name: "贵州茅台", market_label: "沪A", initials: "GZMT" },
  { code: "300750", name: "宁德时代", market_label: "深A", initials: "NDSD" },
  { code: "000858", name: "五粮液", market_label: "深A", initials: "WLY" },
  { code: "601318", name: "中国平安", market_label: "沪A", initials: "ZGPA" },
  { code: "600309", name: "万华化学", market_label: "沪A", initials: "WHHX" },
  { code: "002415", name: "海康威视", market_label: "深A", initials: "HKWS" },
  { code: "000333", name: "美的集团", market_label: "深A", initials: "MDJT" },
  { code: "600276", name: "恒瑞医药", market_label: "沪A", initials: "HRYY" },
];

export default function Backtest() {
  const [stockInput, setStockInput] = useState(formatStockLabel(initialStock));
  const [selectedStock, setSelectedStock] = useState(initialStock);
  const [params, setParams] = useState({ code: initialStock.code, days: 1000, capital: 10000 });
  const [mode, setMode] = useState("single");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const selectedStrategy = ACTIVE_STRATEGY.key;
  const currentStrategy = ACTIVE_STRATEGY;

  const updateParam = (key, value) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleStockInputChange = (value) => {
    setStockInput(value);
    setSelectedStock(null);
    const raw = value.trim();
    setParams((prev) => ({ ...prev, code: /^\d{6}$/.test(raw) ? raw : "" }));
  };

  const handleStockSelect = (stock) => {
    setSelectedStock(stock);
    setStockInput(formatStockLabel(stock));
    setParams((prev) => ({ ...prev, code: stock.code }));
    setError("");
  };

  const run = async () => {
    if (!params.code.trim()) {
      setError("请输入6位股票代码，或输入名称后从候选列表选择股票");
      return;
    }

    setMode("single");
    setError("");
    setResult(null);
    setRunning(true);
    try {
      const data = await api.post("/backtest", {
        code: params.code.trim(),
        strategy: selectedStrategy,
        days: Number(params.days),
        initial_capital: Number(params.capital),
      });
      setResult({ type: "single", data });
    } catch (e) {
      setError(e.message || "回测请求失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="backtest-light min-h-full bg-white text-slate-950">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <PageHeader
          title="策略回测工作台"
          description="只保留你的三周期 MACD + 250 日均线交易状态机。先滚动选股，再用固定规则做单标的回测。"
          meta={
            currentStrategy && (
              <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600">
                当前策略 {currentStrategy.name}
              </span>
            )
          }
        />
      </div>

      <div className="grid min-h-[calc(100vh-7.5rem)] gap-5 bg-white p-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-orange-500" strokeWidth={1.8} />
                <h2 className="text-sm font-semibold text-slate-950">滚动选股</h2>
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                输入几个汉字，或 1-2 位数字代码，下方会出现可选择的“代码 + 股票名称”。
              </p>
            </div>

            <div className="space-y-4 p-4">
              <StockSearchInput
                value={stockInput}
                selectedStock={selectedStock}
                onChange={handleStockInputChange}
                onSelect={handleStockSelect}
                onSubmitCode={(code) => updateParam("code", code)}
                placeholder="输入股票名称或代码，例如 万 / 60 / 600309"
                helperText="输入一两个数字或几个字后，从下方候选列表选择股票"
                variant="light"
                limit={10}
                showInitialSuggestions
                resultMode="code-name"
                selectOnFocus
              />

              <div className="rounded border border-orange-200 bg-orange-50/50 px-3 py-2">
                <div className="text-xs text-slate-500">当前标的</div>
                <div className="mt-1 flex items-end justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-lg font-semibold text-slate-950">
                      {selectedStock?.name || "手动代码"}
                    </div>
                    <div className="mt-0.5 font-mono text-sm text-slate-500">
                      {params.code || "未选择"}
                    </div>
                  </div>
                  <span className="shrink-0 bg-blue-600 px-2 py-1 text-xs text-white">
                    {selectedStock?.market_label || selectedStock?.exchange || "A股"}
                  </span>
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-600">快速候选</span>
                  <span className="text-[11px] text-slate-400">可滚动</span>
                </div>
                <div className="overflow-hidden rounded border border-slate-200">
                  <div className="grid grid-cols-[96px_1fr] border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                    <span>代码</span>
                    <span>股票名称</span>
                  </div>
                  <div className="max-h-60 overflow-auto bg-white">
                    {ROLLING_STOCKS.map((stock) => (
                      <button
                        key={stock.code}
                        type="button"
                        onClick={() => handleStockSelect(stock)}
                        className={`grid w-full grid-cols-[96px_1fr] items-center border-b border-slate-100 px-3 py-2.5 text-left text-sm transition-colors hover:bg-orange-50 ${
                          params.code === stock.code ? "bg-orange-50" : "bg-white"
                        }`}
                      >
                        <span className="font-mono text-slate-800">{stock.code}</span>
                        <span className="truncate text-slate-950">{stock.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-slate-950">回测参数</h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                MVP 规则：收盘价、满仓进出、忽略手续费。三周期策略至少需要 260 根日线，默认取 1000 天。
              </p>
            </div>

            {error && <Notice tone="error" className="mb-4">{error}</Notice>}

            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1 block text-xs text-slate-500">回测天数</span>
                  <input
                    type="number"
                    min={30}
                    max={3650}
                    value={params.days}
                    onChange={(e) => updateParam("days", e.target.value)}
                    className="h-10 w-full rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-950 outline-none transition-colors focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs text-slate-500">初始资金</span>
                  <input
                    type="number"
                    min={10000}
                    step={1000}
                    value={params.capital}
                    onChange={(e) => updateParam("capital", e.target.value)}
                    className="h-10 w-full rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-950 outline-none transition-colors focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
                  />
                </label>
              </div>

              <div>
                <label className="mb-2 block text-xs text-slate-500">固定策略</label>
                <div className="rounded border border-blue-200 bg-blue-50 px-3 py-3">
                  <div className="text-sm font-semibold text-slate-950">
                    {ACTIVE_STRATEGY.name}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    {ACTIVE_STRATEGY.desc}
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                    <span className="rounded border border-blue-100 bg-white px-2 py-1">月线 MACD</span>
                    <span className="rounded border border-blue-100 bg-white px-2 py-1">250 日均线</span>
                    <span className="rounded border border-blue-100 bg-white px-2 py-1">周线窗口</span>
                    <span className="rounded border border-blue-100 bg-white px-2 py-1">日线执行</span>
                  </div>
                </div>
              </div>

              <div className="grid gap-2">
                <Button icon={Play} onClick={run} disabled={running}>
                  {running && mode === "single" ? "回测中..." : "开始回测"}
                </Button>
              </div>
            </div>
          </section>
        </aside>

        <main className="min-w-0 space-y-5">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <div className="text-xs text-slate-500">运行模式</div>
                <div className="mt-1 flex items-center gap-2 text-sm font-semibold text-slate-950">
                  单股回测
                  <ChevronRight className="h-4 w-4 text-slate-400" strokeWidth={1.8} />
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">标的</div>
                <div className="mt-1 font-mono text-sm font-semibold text-slate-950">
                  {params.code || "-"} {selectedStock?.name || ""}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">资金 / 周期</div>
                <div className="mt-1 font-mono text-sm font-semibold text-slate-950">
                  {formatCurrency(Number(params.capital))} · {params.days} 天
                </div>
              </div>
            </div>
          </section>

          {running ? (
            <LoadingState label="正在执行回测计算..." />
          ) : !result ? (
            <EmptyState
              title="请选择标的并开始"
              description="左侧输入股票名称或代码选择标的，设置天数和资金后，用固定的 MACD + 250 日均线策略执行回测。"
            />
          ) : (
            <SingleResult result={result.data} initialCapital={Number(params.capital)} />
          )}
        </main>
      </div>
    </div>
  );
}

function SingleResult({ result, initialCapital }) {
  const chartOption = buildEquityOption(result.equity_curve || [], initialCapital);
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="累计收益率"
          value={formatPercent(result.total_return)}
          tone={toneByValue(result.total_return)}
          icon={TrendingIcon}
        />
        <MetricCard
          label="最大回撤"
          value={formatPercent(result.max_drawdown)}
          tone="down"
          icon={LineChart}
        />
        <MetricCard
          label="交易次数"
          value={formatNumber(result.total_trades)}
          unit="笔"
          icon={FlaskConical}
        />
        <MetricCard
          label="最终权益"
          value={formatCurrency(result.final_equity)}
          tone={toneByValue(result.final_equity - result.initial_capital)}
          icon={BarChart3}
        />
      </div>

      <Panel
        title={`${result.code} · ${result.strategy_name}`}
        description={`${result.start_date} ~ ${result.end_date}`}
      >
        <ReactECharts option={chartOption} style={{ height: 380 }} notMerge />
      </Panel>

      <Panel title={`交易明细 · 共 ${(result.trades || []).length} 笔`}>
        {(result.trades || []).length === 0 ? (
          <EmptyState title="该区间没有触发买卖" description="可以更换标的，或扩大回测天数继续观察这套固定策略。" />
        ) : (
          <TableShell minWidth="760px">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="px-3 py-2 font-normal">日期</th>
                <th className="px-3 py-2 text-center font-normal">操作</th>
                <th className="px-3 py-2 text-right font-normal">价格</th>
                <th className="px-3 py-2 text-right font-normal">股数</th>
                <th className="px-3 py-2 text-right font-normal">金额</th>
                <th className="px-3 py-2 font-normal">理由</th>
              </tr>
            </thead>
            <tbody>
              {(result.trades || []).map((trade, index) => (
                <tr
                  key={`${trade.date}-${index}`}
                  className={`border-b border-slate-800/60 ${
                    trade.action === "BUY" ? "bg-red-500/5" : "bg-emerald-500/5"
                  }`}
                >
                  <td className="px-3 py-2.5 font-mono text-slate-400">{trade.date}</td>
                  <td className="px-3 py-2.5 text-center">
                    <SignalBadge type={trade.action}>
                      {trade.action === "BUY" ? "买入" : "卖出"}
                    </SignalBadge>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono">{formatNumber(trade.price, 2)}</td>
                  <td className="px-3 py-2.5 text-right font-mono">{formatNumber(trade.shares)}</td>
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
    </div>
  );
}

function buildEquityOption(equityCurve, initialCapital) {
  const dates = equityCurve.map((point) => point.date);
  const returns = equityCurve.map((point) => (point.equity / initialCapital - 1) * 100);
  const buyPoints = [];
  const sellPoints = [];
  equityCurve.forEach((point, index) => {
    if (point.signal === "BUY") buyPoints.push({ coord: [index, returns[index]], value: "B" });
    if (point.signal === "SELL") sellPoints.push({ coord: [index, returns[index]], value: "S" });
  });

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      formatter: (items) => {
        const item = items?.[0];
        if (!item) return "";
        const point = equityCurve[item.dataIndex];
        return `${point.date}<br/>权益：${formatCurrency(point.equity)}<br/>收益率：${returns[item.dataIndex].toFixed(2)}%`;
      },
    },
    grid: { left: "7%", right: "4%", top: 28, bottom: 36 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: "#64748b", fontSize: 10 },
      axisLine: { lineStyle: { color: "#334155" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#64748b", formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    series: [
      {
        name: "累计收益率",
        type: "line",
        data: returns,
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
              { offset: 0, color: "rgba(56,189,248,0.22)" },
              { offset: 1, color: "rgba(56,189,248,0)" },
            ],
          },
        },
        markPoint: {
          symbol: "triangle",
          symbolSize: 14,
          label: { color: "#fff", fontSize: 10, fontWeight: "bold" },
          data: [
            ...buyPoints.map((point) => ({
              ...point,
              itemStyle: { color: "#ef4444" },
            })),
            ...sellPoints.map((point) => ({
              ...point,
              symbolRotate: 180,
              itemStyle: { color: "#22c55e" },
            })),
          ],
        },
      },
    ],
  };
}

function TrendingIcon(props) {
  return <LineChart {...props} />;
}
