import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  BarChart3,
  ChevronRight,
  FlaskConical,
  LineChart,
  Play,
  Search,
  SlidersHorizontal,
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

const MOCK_CATEGORIES = [
  {
    name: "我的策略",
    strategies: [
      { key: "triple_macd_ma250", name: "三周期MACD+MA250状态机", desc: "月线MACD→MA250→周线→日线，八状态", params: {} },
    ],
  },
];

const initialStock = { code: "000001", name: "平安银行", market_label: "深A" };

const ROLLING_STOCKS = [
  { code: "600055", name: "万东医疗", market_label: "沪A", initials: "WDYL" },
  { code: "600246", name: "万通发展", market_label: "沪A", initials: "WTFZ" },
  { code: "600309", name: "万华化学", market_label: "沪A", initials: "WHHX" },
  { code: "600371", name: "万向德农", market_label: "沪A", initials: "WXDN" },
  { code: "600847", name: "万里股份", market_label: "沪A", initials: "WLGF" },
  { code: "603010", name: "万盛股份", market_label: "沪A", initials: "WSGF" },
  { code: "000001", name: "平安银行", market_label: "深A", initials: "PAYH" },
  { code: "600036", name: "招商银行", market_label: "沪A", initials: "ZSYH" },
  { code: "300750", name: "宁德时代", market_label: "深A", initials: "NDSD" },
];

export default function Backtest() {
  const [categories, setCategories] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState("triple_macd_ma250");
  const [stockInput, setStockInput] = useState(formatStockLabel(initialStock));
  const [selectedStock, setSelectedStock] = useState(initialStock);
  const [params, setParams] = useState({ code: initialStock.code, days: 365, capital: 10000 });
  const [mode, setMode] = useState("single");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    api
      .get("/backtest/strategies")
      .then((res) => {
        const list = Array.isArray(res) ? res : res.categories || [];
        setCategories(list.length > 0 ? list : MOCK_CATEGORIES);
      })
      .catch(() => {
        setLoadError("后端未连接，展示演示策略列表");
        setCategories(MOCK_CATEGORIES);
      });
  }, []);

  const flatStrategies = useMemo(
    () => categories.flatMap((cat) => cat.strategies || []),
    [categories]
  );
  const currentStrategy = flatStrategies.find((item) => item.key === selectedStrategy);

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

  const run = async (nextMode = mode) => {
    if (!params.code.trim()) {
      setError("请输入6位股票代码，或输入名称后从候选列表选择股票");
      return;
    }
    if ((nextMode === "single" || nextMode === "optimize") && !selectedStrategy) {
      setError("请选择一个策略");
      return;
    }
    if (nextMode === "optimize" && !["triple_macd_ma250"].includes(selectedStrategy)) {
      setError("当前后端参数优化只支持 ma_cross 和 macd_daily，请先选择对应策略");
      return;
    }

    setMode(nextMode);
    setError("");
    setResult(null);
    setRunning(true);
    try {
      if (nextMode === "single") {
        const data = await api.post("/backtest", {
          code: params.code.trim(),
          strategy: selectedStrategy,
          days: Number(params.days),
          initial_capital: Number(params.capital),
        });
        setResult({ type: "single", data });
      } else if (nextMode === "compare") {
        const data = await api.get("/backtest/compare", {
          params: {
            code: params.code.trim(),
            days: Number(params.days),
            initial_capital: Number(params.capital),
          },
        });
        setResult({ type: "compare", data });
      } else {
        const data = await api.get("/backtest/optimize", {
          params: {
            code: params.code.trim(),
            strategy: selectedStrategy,
            days: Number(params.days),
            initial_capital: Number(params.capital),
          },
        });
        setResult({ type: "optimize", data });
      }
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
          description="先选标的，再选择策略与资金区间。单次回测看可行性，策略对比看稳定性，参数优化只作为继续观察的起点。"
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
                支持代码、中文和首字母。接口不可用时会保留本地候选，避免预览页空掉。
              </p>
            </div>

            <div className="space-y-4 p-4">
              <StockSearchInput
                value={stockInput}
                selectedStock={selectedStock}
                onChange={handleStockInputChange}
                onSelect={handleStockSelect}
                onSubmitCode={(code) => updateParam("code", code)}
                placeholder="输入 万 / 600309 / WHHX"
                helperText="点击输入框后可滚动选择候选标的"
                variant="light"
                limit={10}
                showInitialSuggestions
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
                  <div className="grid grid-cols-[54px_78px_1fr_76px] border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                    <span>市场</span>
                    <span>代码</span>
                    <span>名称</span>
                    <span>首字母</span>
                  </div>
                  <div className="max-h-60 overflow-auto bg-white">
                    {ROLLING_STOCKS.map((stock) => (
                      <button
                        key={stock.code}
                        type="button"
                        onClick={() => handleStockSelect(stock)}
                        className={`grid w-full grid-cols-[54px_78px_1fr_76px] items-center border-b border-slate-100 px-3 py-2.5 text-left text-sm transition-colors hover:bg-orange-50 ${
                          params.code === stock.code ? "bg-orange-50" : "bg-white"
                        }`}
                      >
                        <span className="w-10 bg-blue-600 px-1.5 py-0.5 text-center text-xs text-white">
                          {stock.market_label}
                        </span>
                        <span className="font-mono text-slate-800">{stock.code}</span>
                        <span className="truncate text-slate-950">{stock.name}</span>
                        <span className="truncate font-mono text-xs text-slate-500">
                          {stock.initials}
                        </span>
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
                MVP 规则：收盘价、满仓进出、忽略手续费。
              </p>
            </div>

            {loadError && <Notice tone="warn" className="mb-4">{loadError}</Notice>}
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
                <label className="mb-2 block text-xs text-slate-500">策略选择</label>
                <div className="max-h-[300px] space-y-4 overflow-auto pr-1">
                  {categories.map((cat) => (
                    <div key={cat.name}>
                      <div className="mb-2 text-xs font-medium text-slate-500">{cat.name}</div>
                      <div className="space-y-1.5">
                        {(cat.strategies || []).map((strategy) => (
                          <label
                            key={strategy.key}
                            className={`flex cursor-pointer items-start gap-2 rounded border px-3 py-2 transition-colors ${
                              selectedStrategy === strategy.key
                                ? "border-blue-500/60 bg-blue-50"
                                : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                            }`}
                          >
                            <input
                              type="radio"
                              name="strategy"
                              value={strategy.key}
                              checked={selectedStrategy === strategy.key}
                              onChange={() => setSelectedStrategy(strategy.key)}
                              className="mt-1 accent-blue-600"
                            />
                            <span className="min-w-0">
                              <span className="block text-xs font-medium text-slate-950">
                                {strategy.name}
                              </span>
                              <span className="mt-0.5 block truncate text-xs text-slate-500">
                                {strategy.desc}
                              </span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-2">
                <Button icon={Play} onClick={() => run("single")} disabled={running}>
                  {running && mode === "single" ? "回测中..." : "开始回测"}
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    icon={BarChart3}
                    onClick={() => run("compare")}
                    disabled={running}
                  >
                    策略对比
                  </Button>
                  <Button
                    variant="secondary"
                    icon={SlidersHorizontal}
                    onClick={() => run("optimize")}
                    disabled={running}
                  >
                    参数优化
                  </Button>
                </div>
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
                  {mode === "single" ? "单股回测" : mode === "compare" ? "策略对比" : "参数优化"}
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
              title="请选择模式并开始"
              description="左侧设置标的、天数、资金和策略后，可执行单股回测、全部策略对比或参数优化。"
            />
          ) : result.type === "single" ? (
            <SingleResult result={result.data} initialCapital={Number(params.capital)} />
          ) : result.type === "compare" ? (
            <CompareResult result={result.data} />
          ) : (
            <OptimizeResult result={result.data} />
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
          <EmptyState title="该区间没有触发买卖" description="可以更换标的、扩大回测天数或尝试策略对比。" />
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

function CompareResult({ result }) {
  const best = result.best;
  const rows = result.results || [];
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="策略数量" value={formatNumber(result.total_strategies)} unit="个" icon={FlaskConical} />
        <MetricCard label="有交易策略" value={formatNumber(result.has_trades)} unit="个" icon={BarChart3} />
        <MetricCard
          label="最佳策略"
          value={best?.name || "-"}
          subValue={best ? formatPercent(best.total_return) : "暂无交易"}
          tone={toneByValue(best?.total_return)}
          icon={LineChart}
        />
        <MetricCard label="回测标的" value={result.code} icon={SlidersHorizontal} />
      </div>

      <Panel title="策略排名" description="优先看收益率，再看最大回撤和交易次数，避免只追最高收益。">
        <TableShell minWidth="820px">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-500">
              <th className="px-3 py-2 font-normal">排名</th>
              <th className="px-3 py-2 font-normal">策略</th>
              <th className="px-3 py-2 font-normal">类别</th>
              <th className="px-3 py-2 text-right font-normal">收益率</th>
              <th className="px-3 py-2 text-right font-normal">最大回撤</th>
              <th className="px-3 py-2 text-right font-normal">交易</th>
              <th className="px-3 py-2 text-right font-normal">Calmar</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b border-slate-800/60 hover:bg-slate-900">
                <td className="px-3 py-2.5 font-mono text-slate-500">{row.rank}</td>
                <td className="px-3 py-2.5 text-slate-100">{row.name}</td>
                <td className="px-3 py-2.5 text-slate-500">{row.category}</td>
                <td className={`px-3 py-2.5 text-right font-mono ${(row.total_return || 0) >= 0 ? "text-up" : "text-down"}`}>
                  {formatPercent(row.total_return)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-down">{formatPercent(row.max_drawdown)}</td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-400">{formatNumber(row.total_trades)}</td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-400">{formatNumber(row.calmar, 2)}</td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </div>
  );
}

function OptimizeResult({ result }) {
  const rows = result.all || result.top5 || [];
  const best = rows[0];
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="参数组合" value={formatNumber(result.total_combinations)} unit="组" icon={SlidersHorizontal} />
        <MetricCard label="当前策略" value={result.strategy} icon={FlaskConical} />
        <MetricCard
          label="最佳组合"
          value={best?.params || "-"}
          subValue={best ? `${best.total_return_pct?.toFixed(2)}% / 回撤 ${best.max_drawdown_pct?.toFixed(2)}%` : "暂无结果"}
          tone={toneByValue(best?.total_return_pct)}
          icon={BarChart3}
        />
      </div>

      <Panel title="参数优化结果" description="仅作为观察起点，不能直接替代样本外验证。">
        {rows.length === 0 ? (
          <EmptyState title="暂无参数结果" description="当前策略可能暂不支持优化，先选择 ma_cross 或 macd_daily。" />
        ) : (
          <TableShell minWidth="680px">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="px-3 py-2 font-normal">参数</th>
                <th className="px-3 py-2 text-right font-normal">收益率</th>
                <th className="px-3 py-2 text-right font-normal">最大回撤</th>
                <th className="px-3 py-2 text-right font-normal">交易次数</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.params}-${index}`} className="border-b border-slate-800/60 hover:bg-slate-900">
                  <td className="px-3 py-2.5 font-mono text-slate-100">{row.params}</td>
                  <td className={`px-3 py-2.5 text-right font-mono ${row.total_return_pct >= 0 ? "text-up" : "text-down"}`}>
                    {row.total_return_pct?.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-down">{row.max_drawdown_pct?.toFixed(2)}%</td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-400">{formatNumber(row.total_trades)}</td>
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
