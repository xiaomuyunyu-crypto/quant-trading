import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Filter, Plus, RefreshCw, Star, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
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
  TableShell,
} from "../components/WorkbenchUI";
import { formatNumber, formatPercent } from "../lib/format";

const MOCK = [
  { code: "000001", name: "平安银行", exchange: "SZ", industry: "银行", current: 10.52, change_pct: 1.15, tags: ["A股"] },
  { code: "000002", name: "万科A", exchange: "SZ", industry: "房地产", current: 15.3, change_pct: -0.85, tags: ["A股"] },
  { code: "600036", name: "招商银行", exchange: "SH", industry: "银行", current: 38.2, change_pct: 0.5, tags: ["A股"] },
  { code: "159915", name: "创业板ETF", exchange: "SZ", industry: "ETF", current: 1.88, change_pct: 0.34, tags: ["ETF"] },
];

export default function Watchlist() {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [demoMode, setDemoMode] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [tag, setTag] = useState("all");
  const [sort, setSort] = useState("code");
  const [stockInput, setStockInput] = useState("");
  const [selectedStock, setSelectedStock] = useState(null);
  const [newTags, setNewTags] = useState("观察");
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/watchlist");
      setStocks(res.items || []);
      setDemoMode(false);
    } catch {
      setStocks(MOCK);
      setDemoMode(true);
      setError("后端未连接，展示演示自选股");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const tags = useMemo(() => {
    const result = new Set();
    stocks.forEach((stock) => (stock.tags || []).forEach((item) => result.add(item)));
    return Array.from(result).sort((a, b) => a.localeCompare(b, "zh-CN"));
  }, [stocks]);

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    const rows = stocks.filter((stock) => {
      const tagMatched = tag === "all" || (stock.tags || []).includes(tag);
      const keywordMatched =
        !kw ||
        stock.code?.toLowerCase().includes(kw) ||
        stock.name?.toLowerCase().includes(kw) ||
        stock.industry?.toLowerCase().includes(kw);
      return tagMatched && keywordMatched;
    });

    return [...rows].sort((a, b) => {
      if (sort === "name") return (a.name || "").localeCompare(b.name || "", "zh-CN");
      if (sort === "change_pct") return (b.change_pct || 0) - (a.change_pct || 0);
      return String(a.code).localeCompare(String(b.code));
    });
  }, [stocks, keyword, tag, sort]);

  const addToWatchlist = async () => {
    if (!selectedStock) {
      setError("请先从候选列表选择要添加的股票");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.post(`/watchlist/${selectedStock.code}`, null, {
        params: {
          name: selectedStock.name || "",
          tags: newTags,
        },
      });
      setStockInput("");
      setSelectedStock(null);
      await fetchList();
    } catch (e) {
      setError(e.message || "添加失败");
    } finally {
      setSaving(false);
    }
  };

  const removeStock = async (stock) => {
    setError("");
    try {
      await api.delete(`/watchlist/${stock.code}`);
      setStocks((prev) => prev.filter((item) => item.code !== stock.code));
    } catch (e) {
      setError(e.message || "移除失败");
    }
  };

  if (loading) {
    return <LoadingState label="正在读取自选股..." />;
  }

  return (
    <div className="p-5">
      <PageHeader
        title="自选池管理"
        description="自选池是回测、信号生成和实盘模拟的起点。先管好标的，再谈策略表现。"
      >
        <Button variant="secondary" icon={RefreshCw} onClick={fetchList}>
          刷新列表
        </Button>
      </PageHeader>

      {error && <Notice tone={demoMode ? "warn" : "error"} className="mb-4">{error}</Notice>}

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <MetricCard label="当前自选股" value={formatNumber(stocks.length)} unit="只" icon={Star} />
        <MetricCard label="筛选结果" value={formatNumber(filtered.length)} unit="只" icon={Filter} />
        <MetricCard label="分组数量" value={formatNumber(tags.length)} unit="个" icon={Star} />
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="添加自选股" description="输入中文名称或代码，从候选列表选择后添加。">
          <div className="grid gap-3 md:grid-cols-[1fr_160px_auto] md:items-start">
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
              }}
              placeholder="输入股票名称或代码，例如 恒生 / 159920"
              helperText="不使用拼音首字母，支持代码和中文模糊匹配"
            />
            <label>
              <span className="mb-1 block text-xs text-slate-500">分组标签</span>
              <input
                value={newTags}
                onChange={(event) => setNewTags(event.target.value)}
                placeholder="观察,ETF"
                className="h-10 w-full rounded border border-slate-700 bg-slate-900 px-3 text-sm outline-none focus:border-blue-500"
              />
            </label>
            <Button icon={Plus} onClick={addToWatchlist} disabled={saving || demoMode} className="md:mt-5">
              {saving ? "添加中" : "添加"}
            </Button>
          </div>
        </Panel>

        <Panel title="筛选与排序" description="先按分组缩小范围，再按涨跌幅或代码观察。">
          <div className="grid gap-3 md:grid-cols-3">
            <label>
              <span className="mb-1 block text-xs text-slate-500">关键字</span>
              <input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="代码 / 名称 / 行业"
                className="h-10 w-full rounded border border-slate-700 bg-slate-900 px-3 text-sm outline-none focus:border-blue-500"
              />
            </label>
            <label>
              <span className="mb-1 block text-xs text-slate-500">分组</span>
              <select
                value={tag}
                onChange={(event) => setTag(event.target.value)}
                className="h-10 w-full rounded border border-slate-700 bg-slate-900 px-3 text-sm outline-none focus:border-blue-500"
              >
                <option value="all">全部分组</option>
                {tags.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-xs text-slate-500">排序</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value)}
                className="h-10 w-full rounded border border-slate-700 bg-slate-900 px-3 text-sm outline-none focus:border-blue-500"
              >
                <option value="code">代码</option>
                <option value="name">名称</option>
                <option value="change_pct">涨跌幅</option>
              </select>
            </label>
          </div>
        </Panel>
      </div>

      <Panel title="自选股列表" description="点击名称进入日/周/月与指标分析。">
        {filtered.length === 0 ? (
          <EmptyState title="没有匹配结果" description="换一个关键字或分组再试。" />
        ) : (
          <TableShell minWidth="880px">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="px-3 py-2 font-normal">代码</th>
                <th className="px-3 py-2 font-normal">名称</th>
                <th className="px-3 py-2 font-normal">交易所</th>
                <th className="px-3 py-2 font-normal">行业</th>
                <th className="px-3 py-2 font-normal">分组</th>
                <th className="px-3 py-2 text-right font-normal">最新价</th>
                <th className="px-3 py-2 text-right font-normal">涨跌幅</th>
                <th className="px-3 py-2 text-right font-normal">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((stock) => (
                <tr key={stock.code} className="border-b border-slate-800/60 hover:bg-slate-900">
                  <td className="px-3 py-2.5 font-mono text-slate-400">{stock.code}</td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={() => navigate(`/stock/${stock.code}`)}
                      className="font-medium text-slate-100 hover:text-blue-300"
                    >
                      {stock.name}
                    </button>
                  </td>
                  <td className="px-3 py-2.5 text-slate-500">{stock.exchange || "-"}</td>
                  <td className="px-3 py-2.5 text-slate-500">{stock.industry || "-"}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {(stock.tags || []).length === 0 ? (
                        <span className="text-slate-600">-</span>
                      ) : (
                        stock.tags.map((item) => (
                          <span key={item} className="rounded border border-slate-700 px-1.5 py-0.5 text-[11px] text-slate-400">
                            {item}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-300">
                    {stock.current == null ? "-" : formatNumber(stock.current, 2)}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-mono ${(stock.change_pct || 0) >= 0 ? "text-up" : "text-down"}`}>
                    {formatPercent(stock.change_pct || 0, 2, true)}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" icon={Eye} onClick={() => navigate(`/stock/${stock.code}`)}>
                        查看
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={Trash2}
                        onClick={() => removeStock(stock)}
                        disabled={demoMode}
                      >
                        移除
                      </Button>
                    </div>
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
