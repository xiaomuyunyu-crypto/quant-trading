import { useState, useEffect, useRef, useCallback } from "react";
import ReactECharts from "echarts-for-react";
import api from "../api/index";

const MOCK_CATEGORIES = [
  {
    name: "单指标",
    strategies: [
      { key: "macd_daily", name: "MACD柱缩短-日线", desc: "绿柱连续缩短3天买入，红柱连续缩短3天卖出", params: {} },
      { key: "macd_weekly", name: "MACD周线趋势", desc: "周线级别MACD趋势跟踪", params: {} },
      { key: "rsi_oversold", name: "RSI超买超卖", desc: "RSI<30买入，>70卖出", params: {} },
      { key: "ma_cross", name: "双均线交叉(5,20)", desc: "5日线上穿20日线买入，下穿卖出", params: {} },
    ],
  },
  {
    name: "组合策略",
    strategies: [
      { key: "composite_majority", name: "四维多数表决", desc: "MACD+RSI+均线+成交量 多数表决", params: { signal_mode: "majority" } },
      { key: "composite_weighted", name: "四维加权评分", desc: "四维度加权评分综合判断", params: { signal_mode: "weighted" } },
      { key: "composite_consensus", name: "四维全票一致", desc: "四维度信号全票通过才开仓", params: { signal_mode: "consensus" } },
      { key: "composite_mtf", name: "四维多周期", desc: "结合多周期信号判断", params: { signal_mode: "majority", multi_timeframe: true } },
    ],
  },
];

const initialParams = { code: "000001", days: 365, capital: 10000 };
const initialStock = { code: "000001", name: "平安银行", market_label: "深A" };

export default function Backtest() {
  const [categories, setCategories] = useState([]);
  const [params, setParams] = useState(initialParams);
  const [stockInput, setStockInput] = useState(formatStockLabel(initialStock));
  const [selectedStock, setSelectedStock] = useState(initialStock);
  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const chartRef = useRef(null);

  useEffect(() => {
    api
      .get("/backtest/strategies")
      .then((res) => {
        const list = Array.isArray(res) ? res : res.categories || [];
        if (Array.isArray(list) && list.length > 0 && !list[0].strategies) {
          setCategories([{ name: "全部策略", strategies: list }]);
        } else {
          setCategories(list);
        }
      })
      .catch(() => {
        setLoadError("后端未连接，展示Mock策略列表");
        setCategories(MOCK_CATEGORIES);
      });
  }, []);

  const runBacktest = useCallback(async () => {
    if (!params.code.trim()) { setError("请输入6位股票代码，或输入名称后从候选列表选择股票"); return; }
    if (!selectedStrategy) { setError("请选择一个策略"); return; }
    setError(null);
    setResult(null);
    setRunning(true);
    try {
      const data = await api.post("/backtest", {
        code: params.code.trim(),
        strategy: selectedStrategy,
        days: Number(params.days),
        initial_capital: Number(params.capital),
      });
      setResult(data);
    } catch (e) {
      setError(e.message || "回测请求失败");
    } finally {
      setRunning(false);
    }
  }, [params, selectedStrategy]);

  const updateParam = (key, value) =>
    setParams((p) => ({ ...p, [key]: value }));

  const handleStockInputChange = (value) => {
    setStockInput(value);
    setSelectedStock(null);
    const raw = value.trim();
    setParams((p) => ({ ...p, code: /^\d{6}$/.test(raw) ? raw : "" }));
  };

  const handleStockSelect = (stock) => {
    setSelectedStock(stock);
    setStockInput(formatStockLabel(stock));
    setParams((p) => ({ ...p, code: stock.code }));
    setError(null);
  };

  return (
    <div className="flex flex-1 min-h-0">
      {/* ===== 左侧参数面板 ===== */}
      <aside className="w-72 shrink-0 border-r border-gray-800 bg-gray-900/50 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-800">
          <h1 className="text-base font-bold">回测系统</h1>
        </div>
        <div className="flex-1 overflow-auto p-5 space-y-5">
          {loadError && (
            <div className="px-3 py-2 bg-yellow-900/30 border border-yellow-700 rounded text-yellow-400 text-xs">
              {loadError}
            </div>
          )}

          {/* 回测标的 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">回测标的</label>
            <StockSelector
              value={stockInput}
              selectedStock={selectedStock}
              onChange={handleStockInputChange}
              onSelect={handleStockSelect}
            />
          </div>

          {/* 回测天数 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">回测天数</label>
            <input
              type="number"
              min={30}
              max={3650}
              value={params.days}
              onChange={(e) => updateParam("days", e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* 初始资金 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">初始资金（元）</label>
            <input
              type="number"
              min={10000}
              step={1000}
              value={params.capital}
              onChange={(e) => updateParam("capital", e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* 策略选择 */}
          <div>
            <label className="block text-xs text-gray-500 mb-2">策略选择</label>
            <div className="space-y-3 max-h-64 overflow-auto">
              {categories.map((cat) => (
                <div key={cat.name}>
                  <div className="text-xs text-gray-600 font-medium mb-1.5">{cat.name}</div>
                  {cat.strategies.map((s) => (
                    <label
                      key={s.key}
                      className={`flex items-start gap-2 px-2 py-2 rounded cursor-pointer text-sm mb-1 transition-colors ${
                        selectedStrategy === s.key
                          ? "bg-blue-600/20 border border-blue-600/50"
                          : "hover:bg-gray-800 border border-transparent"
                      }`}
                    >
                      <input
                        type="radio"
                        name="strategy"
                        value={s.key}
                        checked={selectedStrategy === s.key}
                        onChange={() => setSelectedStrategy(s.key)}
                        className="mt-0.5 accent-blue-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-gray-200 text-xs">{s.name}</div>
                        <div className="text-gray-600 text-xs mt-0.5 truncate">{s.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* 开始回测 */}
          <button
            onClick={runBacktest}
            disabled={running}
            className={`w-full py-2.5 rounded text-sm font-medium transition-colors ${
              running
                ? "bg-gray-700 text-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 text-white"
            }`}
          >
            {running ? "回测中..." : "开始回测"}
          </button>

          {error && (
            <div className="px-3 py-2 bg-red-900/30 border border-red-700 rounded text-red-400 text-xs">
              {error}
            </div>
          )}
        </div>
      </aside>

      {/* ===== 右侧结果展示区 ===== */}
      <main className="flex-1 overflow-auto p-6">
        {running ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <div className="text-gray-500 text-sm">正在执行回测...</div>
            </div>
          </div>
        ) : result ? (
          <ResultView result={result} initialCapital={params.capital} chartRef={chartRef} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            请在左侧设置参数并选择策略，点击"开始回测"查看结果
          </div>
        )}
      </main>
    </div>
  );
}

function StockSelector({ value, selectedStock, onChange, onSelect }) {
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
    const selectedLabel = selectedStock ? formatStockLabel(selectedStock) : "";

    if (!open || !keyword || keyword === selectedLabel) {
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
  }, [open, selectedStock, value]);

  const showPanel = open && (loading || message || items.length > 0);

  return (
    <div ref={boxRef} className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="输入代码或中文名称，例如 600309 / 万化"
        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm focus:outline-none focus:border-orange-500"
      />

      <div className="mt-1 min-h-4 text-[11px] text-gray-600">
        {selectedStock ? (
          <span>
            已选 {selectedStock.market_label || selectedStock.exchange || "-"} ·{" "}
            <span className="font-mono">{selectedStock.code}</span> · {selectedStock.name}
          </span>
        ) : /^\d{6}$/.test(value.trim()) ? (
          <span>将按代码 {value.trim()} 回测</span>
        ) : (
          <span>可输入股票名称或6位代码，选择候选项后开始回测</span>
        )}
      </div>

      {showPanel && (
        <div className="absolute left-0 right-0 top-[68px] z-30 overflow-hidden rounded border border-gray-700 bg-gray-950 shadow-2xl">
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
                    onSelect(item);
                    setOpen(false);
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

function formatStockLabel(stock) {
  if (!stock) return "";
  return `${stock.code} ${stock.name || ""}`.trim();
}

function ResultView({ result, initialCapital, chartRef }) {
  const { equity_curve, trades, total_return, max_drawdown, total_trades, final_equity, strategy_name, code, start_date, end_date } = result;

  const dates = equity_curve.map((p) => p.date);
  const equityValues = equity_curve.map(
    (p) => (p.equity / initialCapital - 1) * 100
  );

  const buyPoints = [];
  const sellPoints = [];
  equity_curve.forEach((p, i) => {
    if (p.signal === "BUY") buyPoints.push({ coord: [i, equityValues[i]] });
    if (p.signal === "SELL") sellPoints.push({ coord: [i, equityValues[i]] });
  });

  const chartOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const p = params[0];
        if (!p) return "";
        const idx = p.dataIndex;
        const ec = equity_curve[idx];
        return `<div class="text-sm">
          <div class="text-gray-400">${ec.date}</div>
          <div class="font-mono">权益: ¥${ec.equity.toFixed(2)}</div>
          <div class="font-mono">收益率: ${equityValues[idx].toFixed(2)}%</div>
          ${ec.signal ? `<div class="text-blue-400">信号: ${ec.signal}</div>` : ""}
        </div>`;
      },
    },
    grid: { left: "8%", right: "6%", top: 40, bottom: 40 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: "#6b7280", fontSize: 10 },
      axisLine: { lineStyle: { color: "#374151" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#6b7280", formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#1f2937" } },
    },
    series: [
      {
        type: "line",
        data: equityValues,
        smooth: false,
        symbol: "none",
        lineStyle: { color: "#3b82f6", width: 1.5 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59,130,246,0.15)" },
              { offset: 1, color: "rgba(59,130,246,0)" },
            ],
          },
        },
        markPoint: {
          symbol: "triangle",
          symbolSize: 12,
          label: { fontSize: 10, fontWeight: "bold", color: "#fff" },
          data: [
            ...buyPoints.map((p) => ({
              ...p,
              value: "B",
              symbolRotate: 0,
              itemStyle: { color: "#22c55e" },
            })),
            ...sellPoints.map((p) => ({
              ...p,
              value: "S",
              symbolRotate: 180,
              itemStyle: { color: "#ef4444" },
            })),
          ],
        },
      },
    ],
  };

  return (
    <div className="space-y-6">
      {/* 标题行 */}
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold">
          <span className="font-mono text-blue-400">{code}</span> · {strategy_name}
        </h1>
        <span className="text-xs text-gray-600">
          {start_date} ~ {end_date}
        </span>
      </div>

      {/* 绩效指标卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="累计收益率"
          value={(total_return * 100).toFixed(2)}
          unit="%"
          positive={total_return >= 0}
        />
        <MetricCard
          label="最大回撤"
          value={(max_drawdown * 100).toFixed(2)}
          unit="%"
          positive={false}
        />
        <MetricCard label="交易次数" value={total_trades} unit="笔" />
        <MetricCard
          label="最终权益"
          value={final_equity.toFixed(2)}
          unit="元"
        />
      </div>

      {/* 权益曲线图 */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-3">累计收益曲线</h2>
        <ReactECharts
          ref={chartRef}
          option={chartOption}
          style={{ height: 380 }}
          notMerge
        />
      </div>

      {/* 交易明细表 */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-3">
          交易明细 · 共 {trades.length} 笔
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="py-2 px-3 font-normal">日期</th>
                <th className="py-2 px-3 font-normal text-center">操作</th>
                <th className="py-2 px-3 font-normal text-right">价格</th>
                <th className="py-2 px-3 font-normal text-right">股数</th>
                <th className="py-2 px-3 font-normal text-right">金额</th>
                <th className="py-2 px-3 font-normal">理由</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr
                  key={i}
                  className={`border-b border-gray-800/40 ${
                    t.action === "BUY"
                      ? "bg-green-900/10"
                      : "bg-red-900/10"
                  }`}
                >
                  <td className="py-2.5 px-3 text-gray-400 font-mono">{t.date}</td>
                  <td className="py-2.5 px-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        t.action === "BUY"
                          ? "bg-green-900/50 text-green-400"
                          : "bg-red-900/50 text-red-400"
                      }`}
                    >
                      {t.action === "BUY" ? "买入" : "卖出"}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono">{t.price?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono">{t.shares}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-gray-300">
                    {t.amount?.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-gray-500 max-w-48 truncate" title={t.reason}>
                    {t.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, unit, positive }) {
  let colorClass = "text-white";
  if (positive === true) colorClass = "text-up";
  else if (positive === false) colorClass = "text-down";
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-2">{label}</div>
      <div className={`text-xl font-bold ${colorClass}`}>
        {value}
        <span className="text-xs font-normal text-gray-500 ml-1">{unit}</span>
      </div>
    </div>
  );
}
