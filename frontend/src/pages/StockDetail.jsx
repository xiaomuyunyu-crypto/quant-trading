import { useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import ReactECharts from "echarts-for-react";
import api from "../api/index";

function genMockKline(code) {
  const data = [];
  const start = new Date(2024, 0, 2);
  let close = 20 + Math.random() * 80;
  for (let i = 0; i < 120; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    if (d.getDay() === 0 || d.getDay() === 6) continue;
    const open = close;
    const change = (Math.random() - 0.48) * close * 0.04;
    close = close + change;
    const high = Math.max(open, close) + Math.random() * Math.abs(change);
    const low = Math.min(open, close) - Math.random() * Math.abs(change);
    data.push([
      d.toISOString().slice(0, 10),
      +open.toFixed(2),
      +close.toFixed(2),
      +low.toFixed(2),
      +high.toFixed(2),
    ]);
  }
  return data;
}

export default function StockDetail() {
  const { code } = useParams();
  const [kline, setKline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get(`/stocks/${code}/klines`)
      .then((res) => {
        const raw = res.data || [];
        if (raw.length === 0) {
          setError("当前标的暂无K线数据");
          setKline([]);
          return;
        }
        setKline(
          raw.map((k) => [k.date.slice(0, 10), k.open, k.close, k.low, k.high])
        );
      })
      .catch(() => {
        setError("后端未连接，展示Mock K线数据");
        setKline(genMockKline(code));
      })
      .finally(() => setLoading(false));
  }, [code]);

  const option = {
    backgroundColor: "transparent",
    grid: { left: "8%", right: "4%", top: 20, bottom: 40 },
    xAxis: { type: "category", data: kline.map((k) => k[0]), axisLabel: { color: "#6b7280", fontSize: 11 } },
    yAxis: { type: "value", scale: true, axisLabel: { color: "#6b7280" }, splitLine: { lineStyle: { color: "#1f2937" } } },
    series: [
      {
        type: "candlestick",
        data: kline.map((k) => [k[1], k[4], k[3], k[2]]),
        itemStyle: {
          color: "#ef4444",
          color0: "#22c55e",
          borderColor: "#ef4444",
          borderColor0: "#22c55e",
        },
      },
    ],
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
  };

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-6">
        个股详情 · <span className="font-mono text-blue-400">{code}</span>
      </h1>
      {error && (
        <div className="mb-4 px-4 py-2 bg-yellow-900/30 border border-yellow-700 rounded text-yellow-400 text-sm">
          {error}
        </div>
      )}
      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          加载中...
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <ReactECharts option={option} style={{ height: 450 }} />
        </div>
      )}
    </div>
  );
}
