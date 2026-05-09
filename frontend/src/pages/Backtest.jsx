import { useEffect, useMemo, useState } from "react";
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

const DEFAULT_STRATEGIES = [
  {
    key: "triple_macd_ma250",
    name: "原策略：月线+MA250+周线+日线",
    desc: "保留当前规则：月线MACD过滤，MA250长期开关，周线窗口，日线MACD执行",
    params: { level: 0 },
  },
  {
    key: "triple_macd_no_monthly",
    name: "松绑1：去掉月线MACD控制",
    desc: "不再用月线MACD限制买卖，保留MA250、周线窗口和日线MACD执行",
    params: { level: 1 },
  },
  {
    key: "triple_macd_no_monthly_no_ma250",
    name: "松绑2：再去掉MA250控制",
    desc: "去掉月线MACD和MA250过滤，保留周线窗口，日线MACD执行",
    params: { level: 2 },
  },
  {
    key: "triple_macd_daily_only",
    name: "松绑3：仅日线MACD执行",
    desc: "去掉月线、MA250、周线控制，只按日线MACD金叉买入、死叉卖出",
    params: { level: 3 },
  },
  {
    key: "weekly_macd_cross",
    name: "周线MACD金叉/死叉",
    desc: "周线MACD出现金叉买入，出现死叉卖出",
    params: { level: 4 },
  },
];

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
  const [params, setParams] = useState({
    code: initialStock.code,
    days: 3000,
    fullHistory: false,
    capital: 10000,
  });
  const [strategies, setStrategies] = useState(DEFAULT_STRATEGIES);
  const [selectedStrategy, setSelectedStrategy] = useState(DEFAULT_STRATEGIES[0].key);
  const [strategyError, setStrategyError] = useState("");
  const [mode, setMode] = useState("single");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const currentStrategy = useMemo(
    () => strategies.find((strategy) => strategy.key === selectedStrategy) || strategies[0],
    [selectedStrategy, strategies]
  );

  useEffect(() => {
    let alive = true;
    api.get("/backtest/strategies")
      .then((data) => {
        const loaded = (data.categories || []).flatMap((category) => category.strategies || []);
        if (alive && loaded.length > 0) {
          setStrategies(loaded);
          setSelectedStrategy((prev) => loaded.some((strategy) => strategy.key === prev) ? prev : loaded[0].key);
          setStrategyError("");
        }
      })
      .catch((e) => {
        if (alive) setStrategyError(e.message || "策略列表获取失败，已使用本地默认策略");
      });
    return () => {
      alive = false;
    };
  }, []);

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
        days: params.fullHistory ? undefined : Number(params.days),
        full_history: Boolean(params.fullHistory),
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
          variant="light"
          title="策略回测工作台"
          description="保留原 MACD + MA250 状态机，同时提供逐级松绑和周线金叉/死叉策略用于对比。"
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
                输入代码或名称，候选列表会从后端股票 API 获取；下方只是界面演示候选。
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
                MVP 规则：收盘价、满仓进出、忽略手续费。默认取 3000 天，支持从上市以来回测。
              </p>
            </div>

            {error && <Notice tone="error" variant="light" className="mb-4">{error}</Notice>}

            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1 block text-xs text-slate-500">回测天数</span>
                  <input
                    type="number"
                    min={30}
                    max={15000}
                    value={params.days}
                    disabled={params.fullHistory}
                    onChange={(e) => updateParam("days", e.target.value)}
                    className="h-10 w-full rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-950 outline-none transition-colors disabled:bg-slate-100 disabled:text-slate-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
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

              <label className="flex items-center gap-3 rounded border border-slate-200 bg-slate-50 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={params.fullHistory}
                  onChange={(e) => updateParam("fullHistory", e.target.checked)}
                  className="h-4 w-4 accent-orange-500"
                />
                <span className="text-sm font-medium text-slate-700">从上市以来回测</span>
              </label>

              <div>
                <label className="mb-2 block text-xs text-slate-500">策略选择</label>
                {strategyError && (
                  <Notice tone="warn" variant="light" className="mb-3">
                    {strategyError}
                  </Notice>
                )}
                <div className="space-y-2">
                  {strategies.map((strategy, index) => {
                    const active = selectedStrategy === strategy.key;
                    return (
                      <button
                        key={strategy.key}
                        type="button"
                        onClick={() => {
                          setSelectedStrategy(strategy.key);
                          setResult(null);
                        }}
                        className={`w-full rounded border px-3 py-3 text-left transition-colors ${
                          active
                            ? "border-blue-500 bg-blue-50"
                            : "border-slate-200 bg-white hover:border-orange-300 hover:bg-orange-50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-slate-950">
                              {index + 1}. {strategy.name}
                            </div>
                            <p className="mt-1 text-xs leading-5 text-slate-600">
                              {strategy.desc}
                            </p>
                          </div>
                          <span className={`shrink-0 rounded px-2 py-1 text-[11px] ${
                            active ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"
                          }`}>
                            {active ? "已选" : "选择"}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {strategyPills(strategy.key).map((pill) => (
                            <span
                              key={pill}
                              className="rounded border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
                            >
                              {pill}
                            </span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
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
                  {formatCurrency(Number(params.capital))} · {params.fullHistory ? "上市以来" : `${params.days} 天`}
                </div>
              </div>
            </div>
          </section>

          {running ? (
            <LoadingState label="正在执行回测计算..." variant="light" />
          ) : !result ? (
            <EmptyState
              variant="light"
              title="请选择标的并开始"
              description="左侧输入股票名称或代码选择标的，设置策略、周期和资金后执行回测。"
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
  const noTradeReason =
    result.diagnostics?.strategy?.primary_reason ||
    "当前策略在这个区间没有触发完整买卖信号。";
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          variant="light"
          label="累计收益率"
          value={formatPercent(result.total_return)}
          tone={toneByValue(result.total_return)}
          icon={TrendingIcon}
        />
        <MetricCard
          variant="light"
          label="最大回撤"
          value={formatPercent(result.max_drawdown)}
          tone="down"
          icon={LineChart}
        />
        <MetricCard
          variant="light"
          label="交易次数"
          value={formatNumber(result.total_trades)}
          unit="笔"
          icon={FlaskConical}
        />
        <MetricCard
          variant="light"
          label="最终权益"
          value={formatCurrency(result.final_equity)}
          tone={toneByValue(result.final_equity - result.initial_capital)}
          icon={BarChart3}
        />
      </div>

      <Panel
        variant="light"
        title={`${result.code} · ${result.strategy_name}`}
        description={`${result.start_date} ~ ${result.end_date}`}
      >
        <ReactECharts option={chartOption} style={{ height: 380 }} notMerge />
      </Panel>

      <DataDiagnostics result={result} />

      <Panel variant="light" title={`交易明细 · 共 ${(result.trades || []).length} 笔`}>
        {(result.trades || []).length === 0 ? (
          <EmptyState
            variant="light"
            title="该区间没有触发买卖"
            description={noTradeReason}
          />
        ) : (
          <TableShell minWidth="760px">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
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
                  className={`border-b border-slate-100 ${
                    trade.action === "BUY" ? "bg-red-50" : "bg-emerald-50"
                  }`}
                >
                  <td className="px-3 py-2.5 font-mono text-slate-500">{trade.date}</td>
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

function strategyPills(key) {
  const map = {
    triple_macd_ma250: ["月线MACD", "MA250", "周线窗口", "日线MACD"],
    triple_macd_no_monthly: ["MA250", "周线窗口", "日线MACD"],
    triple_macd_no_monthly_no_ma250: ["周线窗口", "日线MACD"],
    triple_macd_daily_only: ["日线MACD"],
    weekly_macd_cross: ["周线MACD"],
  };
  return map[key] || ["MACD"];
}

function DataDiagnostics({ result }) {
  const strategy = result.diagnostics?.strategy || {};
  const warnings = Array.from(new Set([...(result.warnings || []), ...((result.diagnostics?.kline?.warnings) || [])]))
    .filter(Boolean);
  const signalCounts = strategy.signal_counts || {};
  const latestState = strategy.latest_state || {};

  return (
    <Panel
      variant="light"
      title="数据与策略诊断"
      description="用于区分行情 API、数据长度和策略状态机条件。"
    >
      <div className="grid gap-3 md:grid-cols-4">
        <DiagnosticItem label="数据来源" value={result.data_source || "-"} />
        <DiagnosticItem label="实际区间" value={`${result.actual_data_start_date || "-"} ~ ${result.actual_data_end_date || "-"}`} />
        <DiagnosticItem label="K线数量" value={`${formatNumber(result.data_points || 0)} / 至少 ${formatNumber(strategy.min_required_bars || 260)}`} />
        <DiagnosticItem label="信号统计" value={`买 ${signalCounts.BUY || 0} / 卖 ${signalCounts.SELL || 0}`} />
      </div>

      {(strategy.primary_reason || latestState.state) && (
        <div className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
          {latestState.state && <span className="font-medium text-slate-800">{latestState.state}：</span>}
          {strategy.primary_reason || latestState.reason}
        </div>
      )}

      {warnings.length > 0 && (
        <Notice tone="warn" variant="light" className="mt-3">
          {warnings.slice(0, 3).join("；")}
        </Notice>
      )}
    </Panel>
  );
}

function DiagnosticItem({ label, value }) {
  return (
    <div className="border-l border-slate-200 pl-3">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="mt-1 truncate font-mono text-sm font-semibold text-slate-900" title={String(value)}>
        {value}
      </div>
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
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#64748b", formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
      {
        name: "累计收益率",
        type: "line",
        data: returns,
        symbol: "none",
        lineStyle: { color: "#2563eb", width: 1.8 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(37,99,235,0.14)" },
              { offset: 1, color: "rgba(37,99,235,0)" },
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
