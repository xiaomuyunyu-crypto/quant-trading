import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import api from "../api/index";

export function formatStockLabel(stock) {
  if (!stock) return "";
  return `${stock.code} ${stock.name || ""}`.trim();
}

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
}) {
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
    <div ref={boxRef} className={`relative ${className}`}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" strokeWidth={1.8} />
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
          className={`h-10 w-full rounded border border-slate-700 bg-slate-900 pl-9 pr-9 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-600 focus:border-blue-500 ${inputClassName}`}
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              onChange("");
              setOpen(false);
            }}
            className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-slate-600 hover:bg-slate-800 hover:text-slate-300"
            aria-label="清空搜索"
          >
            <X className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
        )}
      </div>

      <div className="mt-1 min-h-4 text-[11px] text-slate-600">
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
        <div className="absolute left-0 right-0 top-[68px] z-30 overflow-hidden rounded border border-slate-700 bg-slate-950 shadow-2xl">
          <div className="grid grid-cols-[54px_78px_1fr] border-b border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-500">
            <span>市场</span>
            <span>代码</span>
            <span>名称</span>
          </div>

          {loading ? (
            <div className="px-3 py-3 text-xs text-slate-500">搜索中...</div>
          ) : message ? (
            <div className="px-3 py-3 text-xs text-slate-500">{message}</div>
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
                  className="grid w-full grid-cols-[54px_78px_1fr] items-center border-b border-slate-900 px-3 py-2.5 text-left text-sm hover:bg-slate-800"
                >
                  <span className="w-10 bg-blue-600 px-1.5 py-0.5 text-center text-xs text-white">
                    {item.market_label || item.exchange || "-"}
                  </span>
                  <span className="font-mono text-slate-300">{item.code}</span>
                  <span className="truncate text-slate-100">{item.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
