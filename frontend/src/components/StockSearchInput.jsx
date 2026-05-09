import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import api from "../api/index";

const FALLBACK_STOCKS = [
  { code: "600055", name: "万东医疗", exchange: "SH", market_label: "沪A", initials: "WDYL" },
  { code: "600246", name: "万通发展", exchange: "SH", market_label: "沪A", initials: "WTFZ" },
  { code: "600309", name: "万华化学", exchange: "SH", market_label: "沪A", initials: "WHHX" },
  { code: "600371", name: "万向德农", exchange: "SH", market_label: "沪A", initials: "WXDN" },
  { code: "600847", name: "万里股份", exchange: "SH", market_label: "沪A", initials: "WLGF" },
  { code: "603010", name: "万盛股份", exchange: "SH", market_label: "沪A", initials: "WSGF" },
  { code: "000001", name: "平安银行", exchange: "SZ", market_label: "深A", initials: "PAYH" },
  { code: "000002", name: "万科A", exchange: "SZ", market_label: "深A", initials: "WKA" },
  { code: "600036", name: "招商银行", exchange: "SH", market_label: "沪A", initials: "ZSYH" },
  { code: "300750", name: "宁德时代", exchange: "SZ", market_label: "深A", initials: "NDSD" },
  { code: "159915", name: "创业板ETF", exchange: "SZ", market_label: "深A", initials: "CYBETF" },
  { code: "510300", name: "沪深300ETF", exchange: "SH", market_label: "沪A", initials: "HS300ETF" },
];

export function formatStockLabel(stock) {
  if (!stock) return "";
  return `${stock.code} ${stock.name || ""}`.trim();
}

function searchFallbackStocks(keyword, limit) {
  const q = keyword.trim().toUpperCase();
  const source = q ? FALLBACK_STOCKS : FALLBACK_STOCKS.slice(0, limit);
  const rows = source
    .map((stock) => {
      const code = stock.code.toUpperCase();
      const name = stock.name.toUpperCase();
      const initials = (stock.initials || "").toUpperCase();
      if (!q) return { score: 0, stock };
      if (code === q) return { score: 0, stock };
      if (code.startsWith(q)) return { score: 10 + code.length - q.length, stock };
      if (name.startsWith(q)) return { score: 20 + name.length - q.length, stock };
      if (initials.startsWith(q)) return { score: 30 + initials.length - q.length, stock };
      if (code.includes(q)) return { score: 40 + code.indexOf(q), stock };
      if (name.includes(q)) return { score: 50 + name.indexOf(q), stock };
      if (initials.includes(q)) return { score: 60 + initials.indexOf(q), stock };
      return null;
    })
    .filter(Boolean)
    .sort((a, b) => a.score - b.score || a.stock.code.localeCompare(b.stock.code));
  return rows.slice(0, limit).map((item) => item.stock);
}

const themeClass = {
  dark: {
    icon: "text-slate-600",
    input:
      "border-slate-700 bg-slate-900 text-slate-100 placeholder:text-slate-600 focus:border-blue-500",
    clear: "text-slate-600 hover:bg-slate-800 hover:text-slate-300",
    helper: "text-slate-600",
    panel: "border-slate-700 bg-slate-950 shadow-2xl",
    header: "border-slate-800 bg-slate-900 text-slate-500",
    row: "border-slate-900 text-slate-300 hover:bg-slate-800",
    rowName: "text-slate-100",
    message: "text-slate-500",
    code: "text-slate-300",
  },
  light: {
    icon: "text-slate-400",
    input:
      "border-slate-300 bg-white text-slate-950 placeholder:text-slate-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10",
    clear: "text-slate-400 hover:bg-slate-100 hover:text-slate-700",
    helper: "text-slate-500",
    panel: "border-slate-200 bg-white shadow-[0_18px_45px_rgba(15,23,42,0.14)]",
    header: "border-slate-100 bg-slate-50 text-slate-500",
    row: "border-slate-100 text-slate-700 hover:bg-orange-50/70",
    rowName: "text-slate-950",
    message: "text-slate-500",
    code: "text-slate-800",
  },
};

export default function StockSearchInput({
  value,
  selectedStock,
  onChange,
  onSelect,
  onSubmitCode,
  placeholder = "输入股票代码或中文名称，例如 600309 / 万化",
  helperText = "可输入股票名称或6位代码，选择候选项后继续",
  className = "",
  inputClassName = "",
  variant = "dark",
  limit = 8,
  showInitialSuggestions = false,
  enableFallback = true,
}) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const boxRef = useRef(null);
  const classes = themeClass[variant] || themeClass.dark;
  const selectedLabel = selectedStock ? formatStockLabel(selectedStock) : "";
  const keyword = value.trim();

  const fallbackItems = useMemo(
    () => (enableFallback ? searchFallbackStocks(keyword, limit) : []),
    [enableFallback, keyword, limit]
  );

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
    if (!open || keyword === selectedLabel || (!keyword && !showInitialSuggestions)) {
      setItems(keyword === selectedLabel ? [] : fallbackItems);
      setMessage("");
      setLoading(false);
      return;
    }

    if (!keyword) {
      setItems(fallbackItems);
      setMessage(fallbackItems.length === 0 ? "暂无候选股票" : "");
      setLoading(false);
      return;
    }

    let canceled = false;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setMessage("");
      try {
        const res = await api.get("/stocks/search", {
          params: { keyword, limit },
        });
        if (canceled) return;
        const apiItems = res.items || [];
        const nextItems = apiItems.length > 0 ? apiItems : fallbackItems;
        setItems(nextItems);
        setMessage(nextItems.length === 0 ? "没有匹配的股票" : "");
      } catch (e) {
        if (canceled) return;
        setItems(fallbackItems);
        setMessage(fallbackItems.length === 0 ? e.message || "搜索失败" : "");
      } finally {
        if (!canceled) setLoading(false);
      }
    }, 180);

    return () => {
      canceled = true;
      window.clearTimeout(timer);
    };
  }, [fallbackItems, keyword, limit, open, selectedLabel, showInitialSuggestions]);

  const showPanel = open && (loading || message || items.length > 0);

  return (
    <div ref={boxRef} className={`relative ${className}`}>
      <div className="relative">
        <Search className={`pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 ${classes.icon}`} strokeWidth={1.8} />
        <input
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            const code = value.trim();
            if (e.key === "Enter" && /^\d{6}$/.test(code) && onSubmitCode) {
              onSubmitCode(code);
              setOpen(false);
            }
          }}
          placeholder={placeholder}
          className={`h-10 w-full rounded border pl-9 pr-9 text-sm outline-none transition-colors ${classes.input} ${inputClassName}`}
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              onChange("");
              setOpen(false);
            }}
            className={`absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded ${classes.clear}`}
            aria-label="清空搜索"
          >
            <X className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
        )}
      </div>

      <div className={`mt-1 min-h-4 text-[11px] ${classes.helper}`}>
        {selectedStock ? (
          <span>
            已选 {selectedStock.market_label || selectedStock.exchange || "-"} ·{" "}
            <span className="font-mono">{selectedStock.code}</span> · {selectedStock.name}
          </span>
        ) : /^\d{6}$/.test(value.trim()) ? (
          <span>按回车使用代码 {value.trim()}</span>
        ) : (
          <span>{helperText}</span>
        )}
      </div>

      {showPanel && (
        <div className={`absolute left-0 right-0 top-[68px] z-30 overflow-hidden rounded border ${classes.panel}`}>
          <div className={`grid grid-cols-[54px_78px_1fr_86px] border-b px-3 py-2 text-xs ${classes.header}`}>
            <span>市场</span>
            <span>代码</span>
            <span>名称</span>
            <span>首字母</span>
          </div>

          {loading ? (
            <div className={`px-3 py-3 text-xs ${classes.message}`}>搜索中...</div>
          ) : message ? (
            <div className={`px-3 py-3 text-xs ${classes.message}`}>{message}</div>
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
                  className={`grid w-full grid-cols-[54px_78px_1fr_86px] items-center border-b px-3 py-2.5 text-left text-sm ${classes.row}`}
                >
                  <span className="w-10 bg-blue-600 px-1.5 py-0.5 text-center text-xs text-white">
                    {item.market_label || item.exchange || "-"}
                  </span>
                  <span className={`font-mono ${classes.code}`}>{item.code}</span>
                  <span className={`truncate ${classes.rowName}`}>{item.name}</span>
                  <span className="truncate font-mono text-xs text-slate-500">
                    {item.initials || item.py || "-"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
