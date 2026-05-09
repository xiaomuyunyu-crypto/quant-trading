import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { Activity, BarChart3, CalendarDays, LineChart } from "lucide-react";
import api from "../api/index";
import {
  Button,
  LoadingState,
  MetricCard,
  Notice,
  PageHeader,
  Panel,
} from "../components/WorkbenchUI";
import { compactDate, formatNumber, formatPercent, toneByValue } from "../lib/format";

const FREQUENCIES = [
  { key: "D", label: "日线" },
  { key: "W", label: "周线" },
  { key: "M", label: "月线" },
];

function genMockKline() {
  const data = [];
  const start = new Date(2024, 0, 2);
  let close = 20 + Math.random() * 80;
  for (let i = 0; i < 180; i += 1) {
    const date = new Date(start);
    date.setDate(date.getDate() + i);
    if (date.getDay() === 0 || date.getDay() === 6) continue;
    const open = close;
    const change = (Math.random() - 0.48) * close * 0.04;
    close += change;
    const high = Math.max(open, close) + Math.random() * Math.abs(change || 1);
    const low = Math.min(open, close) - Math.random() * Math.abs(change || 1);
    data.push({
      date: date.toISOString().slice(0, 10),
      open: +open.toFixed(2),
      close: +close.toFixed(2),
      low: +low.toFixed(2),
      high: +high.toFixed(2),
      volume: Math.round(800000 + Math.random() * 2600000),
    });
  }
  return data;
}

export default function StockDetail() {
  const { code } = useParams();
  const [frequency, setFrequency] = useState("D");
  const [kline, setKline] = useState([]);
  const [stockInfo, setStockInfo] = useState(null);
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    let canceled = false;
    async function load() {
      setLoading(true);
      setError("");
      setDemoMode(false);
      setSignal(null);
      try {
        const [detailRes, klineRes, signalRes] = await Promise.allSettled([
          api.get(`/stocks/${code}`),
          api.get(`/stocks/${code}/klines`, { params: { frequency } }),
          api.get(`/signals/${code}`),
        ]);
        if (canceled) return;

        if (detailRes.status === "fulfilled") setStockInfo(detailRes.value);
        else setStockInfo(null);

        if (signalRes.status === "fulfilled") setSignal(signalRes.value);

        if (klineRes.status !== "fulfilled") throw klineRes.reason;
        const raw = klineRes.value.data || [];
        if (raw.length === 0) {
          setError("当前标的暂无K线数据");
          setKline([]);
        } else {
          setKline(
            raw.map((item) => ({
              date: String(item.date).slice(0, 10),
              open: Number(item.open),
              high: Number(item.high),
              low: Number(item.low),
              close: Number(item.close),
              volume: Number(item.volume || 0),
            }))
          );
        }
      } catch {
        if (canceled) return;
        setDemoMode(true);
        setError("后端未连接，展示演示K线数据");
        setKline(genMockKline());
        setStockInfo(null);
      } finally {
        if (!canceled) setLoading(false);
      }
    }
    load();
    return () => {
      canceled = true;
    };
  }, [code, frequency]);

  const indicators = useMemo(() => buildIndicators(kline), [kline]);
  const latest = kline[kline.length - 1];
  const prev = kline[kline.length - 2];
  const changePct = latest && prev ? (latest.close / prev.close - 1) * 100 : 0;

  const chartOption = useMemo(
    () => buildChartOption(kline, indicators),
    [kline, indicators]
  );

  if (loading) {
    return <LoadingState label="正在加载标的图表..." />;
  }

  return (
    <div className="p-5">
      <PageHeader
        title={`${stockInfo?.name || "标的分析"} · ${code}`}
        description="日、周、月三周期配合 MA、MACD、RSI 和成交量观察，不把单日波动当成交易结论。"
        meta={
          <span className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-500">
            {FREQUENCIES.find((item) => item.key === frequency)?.label || frequency}
          </span>
        }
      >
        <div className="flex gap-2">
          {FREQUENCIES.map((item) => (
            <Button
              key={item.key}
              variant={frequency === item.key ? "primary" : "secondary"}
              size="sm"
              onClick={() => setFrequency(item.key)}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </PageHeader>

      {error && <Notice tone={demoMode ? "warn" : "error"} className="mb-4">{error}</Notice>}

      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="最新收盘" value={formatNumber(latest?.close, 2)} icon={LineChart} />
        <MetricCard
          label="区间涨跌"
          value={formatPercent(changePct, 2, true)}
          tone={toneByValue(changePct)}
          icon={Activity}
        />
        <MetricCard label="最新成交量" value={formatNumber(latest?.volume)} icon={BarChart3} />
        <MetricCard label="最新日期" value={compactDate(latest?.date)} icon={CalendarDays} />
      </div>

      {signal && (
        <Panel title="综合信号" description="后端多周期信号引擎返回的当前结论。" className="mb-5">
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="信号" value={signal.signal_type || signal.signal || "-"} tone={signal.signal_type === "BUY" ? "up" : signal.signal_type === "SELL" ? "down" : "neutral"} />
            <MetricCard label="置信度" value={formatPercent(signal.confidence || 0)} tone="info" />
            <MetricCard label="综合分" value={formatNumber(signal.score || signal.composite_score, 2)} />
            <MetricCard label="建议" value={signal.action || "手动确认"} />
          </div>
        </Panel>
      )}

      <Panel
        title="价格与指标"
        description="主图为K线+MA5/MA20/MA60，下方依次是成交量、MACD、RSI。"
      >
        {kline.length === 0 ? (
          <div className="py-16 text-center text-sm text-slate-500">暂无K线数据</div>
        ) : (
          <ReactECharts option={chartOption} style={{ height: 720 }} notMerge />
        )}
      </Panel>
    </div>
  );
}

function buildIndicators(rows) {
  const closes = rows.map((item) => item.close);
  const ma5 = movingAverage(closes, 5);
  const ma20 = movingAverage(closes, 20);
  const ma60 = movingAverage(closes, 60);
  const { dif, dea, hist } = macd(closes);
  const rsi = calcRsi(closes, 14);
  return { ma5, ma20, ma60, dif, dea, hist, rsi };
}

function movingAverage(values, period) {
  return values.map((_, index) => {
    if (index + 1 < period) return null;
    const slice = values.slice(index + 1 - period, index + 1);
    const sum = slice.reduce((total, item) => total + item, 0);
    return +(sum / period).toFixed(3);
  });
}

function ema(values, period) {
  const alpha = 2 / (period + 1);
  const result = [];
  values.forEach((value, index) => {
    if (index === 0) result.push(value);
    else result.push(value * alpha + result[index - 1] * (1 - alpha));
  });
  return result;
}

function macd(values) {
  if (values.length === 0) return { dif: [], dea: [], hist: [] };
  const ema12 = ema(values, 12);
  const ema26 = ema(values, 26);
  const dif = values.map((_, index) => ema12[index] - ema26[index]);
  const dea = ema(dif, 9);
  const hist = dif.map((value, index) => (value - dea[index]) * 2);
  return {
    dif: dif.map((value) => +value.toFixed(4)),
    dea: dea.map((value) => +value.toFixed(4)),
    hist: hist.map((value) => +value.toFixed(4)),
  };
}

function calcRsi(values, period) {
  const result = values.map(() => null);
  if (values.length <= period) return result;
  for (let index = period; index < values.length; index += 1) {
    let gain = 0;
    let loss = 0;
    for (let cursor = index - period + 1; cursor <= index; cursor += 1) {
      const diff = values[cursor] - values[cursor - 1];
      if (diff >= 0) gain += diff;
      else loss -= diff;
    }
    if (loss === 0) result[index] = 100;
    else {
      const rs = gain / loss;
      result[index] = +(100 - 100 / (1 + rs)).toFixed(2);
    }
  }
  return result;
}

function buildChartOption(rows, indicators) {
  const dates = rows.map((item) => item.date);
  const volumes = rows.map((item) => item.volume);
  const candles = rows.map((item) => [item.open, item.close, item.low, item.high]);
  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    axisPointer: { link: [{ xAxisIndex: [0, 1, 2, 3] }] },
    legend: {
      top: 0,
      right: 10,
      textStyle: { color: "#94a3b8" },
      data: ["K线", "MA5", "MA20", "MA60", "DIF", "DEA", "RSI"],
    },
    grid: [
      { left: "7%", right: "4%", top: 36, height: "42%" },
      { left: "7%", right: "4%", top: "53%", height: "12%" },
      { left: "7%", right: "4%", top: "69%", height: "12%" },
      { left: "7%", right: "4%", top: "85%", height: "9%" },
    ],
    xAxis: [0, 1, 2, 3].map((index) => ({
      type: "category",
      data: dates,
      gridIndex: index,
      axisLabel: { color: "#64748b", fontSize: index === 3 ? 10 : 0 },
      axisLine: { lineStyle: { color: "#334155" } },
      axisTick: { show: index === 3 },
    })),
    yAxis: [
      { scale: true, gridIndex: 0, axisLabel: { color: "#64748b" }, splitLine: { lineStyle: { color: "#1e293b" } } },
      { scale: true, gridIndex: 1, axisLabel: { color: "#64748b" }, splitLine: { show: false } },
      { scale: true, gridIndex: 2, axisLabel: { color: "#64748b" }, splitLine: { lineStyle: { color: "#1e293b" } } },
      { min: 0, max: 100, gridIndex: 3, axisLabel: { color: "#64748b" }, splitLine: { lineStyle: { color: "#1e293b" } } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1, 2, 3], start: 45, end: 100 },
      { type: "slider", xAxisIndex: [0, 1, 2, 3], bottom: 0, height: 18, textStyle: { color: "#64748b" } },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: candles,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: "#ef4444",
          color0: "#22c55e",
          borderColor: "#ef4444",
          borderColor0: "#22c55e",
        },
      },
      lineSeries("MA5", indicators.ma5, "#f59e0b", 0),
      lineSeries("MA20", indicators.ma20, "#38bdf8", 0),
      lineSeries("MA60", indicators.ma60, "#a78bfa", 0),
      {
        name: "成交量",
        type: "bar",
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: "#334155" },
      },
      {
        name: "MACD柱",
        type: "bar",
        data: indicators.hist,
        xAxisIndex: 2,
        yAxisIndex: 2,
        itemStyle: {
          color: (params) => (params.value >= 0 ? "#ef4444" : "#22c55e"),
        },
      },
      lineSeries("DIF", indicators.dif, "#f97316", 2),
      lineSeries("DEA", indicators.dea, "#60a5fa", 2),
      lineSeries("RSI", indicators.rsi, "#eab308", 3),
      {
        name: "RSI参考",
        type: "line",
        data: rows.map(() => 70),
        xAxisIndex: 3,
        yAxisIndex: 3,
        symbol: "none",
        lineStyle: { color: "#475569", width: 1, type: "dashed" },
      },
      {
        name: "RSI低位",
        type: "line",
        data: rows.map(() => 20),
        xAxisIndex: 3,
        yAxisIndex: 3,
        symbol: "none",
        lineStyle: { color: "#475569", width: 1, type: "dashed" },
      },
    ],
  };
}

function lineSeries(name, data, color, axisIndex) {
  return {
    name,
    type: "line",
    data,
    xAxisIndex: axisIndex,
    yAxisIndex: axisIndex,
    symbol: "none",
    connectNulls: true,
    lineStyle: { color, width: 1.4 },
  };
}
