# -*- coding: utf-8 -*-
# 股票与自选股业务服务

from __future__ import annotations

from datetime import datetime, timedelta

from data.storage.database import get_session
from data.storage.repository import (
    query_stocks,
    add_watchlist,
    remove_watchlist,
    query_watchlist,
)
from data.storage.models_orm import StockModel, WatchlistModel, KlineModel
from sqlalchemy import select

_stock_bootstrap_status = {
    "source": "cache",
    "error": None,
}

_FALLBACK_SEARCH_STOCKS = [
    {"code": "600055", "name": "万东医疗", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "600246", "name": "万通发展", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "600309", "name": "万华化学", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "600371", "name": "万向德农", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "600847", "name": "万里股份", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "603010", "name": "万盛股份", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "000001", "name": "平安银行", "exchange": "SZ", "industry": None, "list_date": None},
    {"code": "600036", "name": "招商银行", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "600519", "name": "贵州茅台", "exchange": "SH", "industry": None, "list_date": None},
    {"code": "300750", "name": "宁德时代", "exchange": "SZ", "industry": None, "list_date": None},
    {"code": "159915", "name": "创业板ETF", "exchange": "SZ", "industry": "ETF/基金", "list_date": None},
    {"code": "510300", "name": "沪深300ETF", "exchange": "SH", "industry": "ETF/基金", "list_date": None},
]


def get_all_stocks(exchange: str | None = None) -> list[dict]:
    _ensure_stocks_populated()
    df = query_stocks(exchange=exchange)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def _ensure_stocks_populated() -> int:
    """确保stocks表有数据；为空时从AKShare拉取全量A股列表并写入。返回stocks数量。"""
    global _stock_bootstrap_status
    with get_session() as session:
        count = session.query(StockModel).count()
        if count > 0:
            _stock_bootstrap_status = {"source": "cache", "error": None}
            return count

    try:
        from data.fetcher.akshare_fetcher import fetch_stock_list
        from data.cleaner.cleaner import clean_stock_list
        from data.storage.repository import upsert_stocks

        raw = fetch_stock_list()
        df = clean_stock_list(raw) if raw is not None and not raw.empty else raw
        if df is not None and not df.empty:
            upsert_stocks(df)
            with get_session() as session:
                _stock_bootstrap_status = {"source": "akshare", "error": None}
                return session.query(StockModel).count()
        _stock_bootstrap_status = {"source": "empty", "error": "AKShare股票列表为空"}
    except Exception as exc:
        _stock_bootstrap_status = {"source": "empty", "error": str(exc)}

    with get_session() as session:
        return session.query(StockModel).count()


def search_stocks(keyword: str, limit: int = 10) -> list[dict]:
    """按代码或中文名称搜索股票，优先从stocks表查，为空则查自选股。"""
    return search_stocks_with_meta(keyword, limit=limit)["items"]


def search_stocks_with_meta(keyword: str, limit: int = 10) -> dict:
    """搜索股票并返回数据来源诊断。"""
    query = keyword.strip()
    if not query:
        return {"total": 0, "items": [], "data_source": "empty", "warnings": []}

    limit = max(1, min(limit, 50))

    # stocks表为空时自动从AKShare拉取全量A股列表
    _ensure_stocks_populated()

    with get_session() as session:
        stocks = session.execute(select(StockModel)).scalars().all()
        watch_rows = session.execute(select(WatchlistModel)).scalars().all()
        watch_codes = {r.code for r in watch_rows}

    # 同时从stocks表和自选股搜索（自选股可能包含港股/美股不在stocks表）
    candidates = list(stocks)
    seen_codes = {s.code for s in stocks}
    for w in watch_rows:
        if w.code not in seen_codes:
            candidates.append(type('StockProxy', (), {
                'code': w.code, 'name': w.name or '', 'exchange': '',
                'industry': None, 'list_date': None,
            }))

    matches = []
    for stock in candidates:
        code = stock.code
        name = getattr(stock, 'name', '') or ''
        exchange = getattr(stock, 'exchange', '') or ''
        exchange_val = exchange if hasattr(stock, 'exchange') else ''
        score = _stock_match_score(query, code, name)
        if score is None:
            continue
        # 给港股/美股标记合适的市场
        if not exchange_val:
            if len(code) == 5 and code.isdigit():
                exchange_val = 'HK'
            elif not code.isdigit():
                exchange_val = 'US'

        matches.append((
            score,
            code,
            {
                "code": code,
                "name": name,
                "exchange": exchange_val,
                "market_label": _market_label(exchange_val),
                "industry": getattr(stock, 'industry', None) or None,
                "list_date": None,
                "is_watchlist": code in watch_codes,
            },
        ))

    matches.sort(key=lambda item: (item[0], item[1]))
    items = [item[2] for item in matches[:limit]]
    data_source = _stock_bootstrap_status.get("source") or "cache"
    warnings = []
    if not items and _stock_bootstrap_status.get("error"):
        fallback_items = _search_fallback_stocks(query, limit, watch_codes)
        if fallback_items:
            items = fallback_items
            data_source = "fallback"
            warnings.append("AKShare股票基础列表暂不可用，已使用内置应急候选；输入6位代码仍可直接回测")
        else:
            warnings.append(f"AKShare股票基础列表暂不可用：{_stock_bootstrap_status.get('error')}")

    return {
        "total": len(items),
        "items": items,
        "data_source": data_source,
        "warnings": warnings,
    }


def get_stock_detail(code: str) -> dict | None:
    lookup_code = _normalize_stock_code(code)
    with get_session() as session:
        stock = session.get(StockModel, lookup_code)
        watch = session.get(WatchlistModel, lookup_code)

    if stock is None:
        _ensure_stocks_populated()
        with get_session() as session:
            stock = session.get(StockModel, lookup_code)
            watch = session.get(WatchlistModel, lookup_code)

    if stock is None and watch is None:
        return None

    if stock is None:
        return {
            "code": lookup_code,
            "name": watch.name or "",
            "exchange": "",
            "industry": None,
            "list_date": None,
            "is_watchlist": watch is not None,
            "tags": watch.tags,
            "notes": watch.notes,
        }

    return {
        "code": stock.code,
        "name": stock.name,
        "exchange": stock.exchange,
        "industry": stock.industry,
        "list_date": stock.list_date.isoformat() if stock.list_date else None,
        "is_watchlist": watch is not None,
        "tags": watch.tags if watch else [],
        "notes": watch.notes if watch else None,
    }


def get_klines(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> list[dict]:
    from backend.core.kline_utils import get_klines_df

    df = get_klines_df(code, start_date=start_date, end_date=end_date, frequency=frequency)
    if df is None or df.empty:
        return []
    for col in ("date",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def get_klines_with_diagnostics(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> dict:
    from backend.core.kline_utils import get_klines_with_meta

    result = get_klines_with_meta(
        code,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
    )
    df = result.df
    data = []
    if df is not None and not df.empty:
        if "date" in df.columns:
            df = df.copy()
            df["date"] = df["date"].astype(str)
        data = df.to_dict(orient="records")

    meta = result.to_dict()
    meta["data"] = data
    meta["count"] = len(data)
    return meta


def get_realtime_quote(code: str) -> dict:
    """获取单只股票实时行情；失败时退回最新日线收盘价。"""
    lookup_code = _normalize_stock_code(code)
    now = datetime.now()
    errors = []

    try:
        from data.fetcher.akshare_fetcher import fetch_realtime_quotes

        quotes = fetch_realtime_quotes()
        if quotes is not None and not quotes.empty:
            row = quotes[quotes["code"].astype(str).str.zfill(6) == lookup_code]
            if not row.empty:
                item = row.iloc[0].to_dict()
                return {
                    "code": lookup_code,
                    "name": str(item.get("name", "")),
                    "current": _safe_float(item.get("current")),
                    "change": _safe_float(item.get("change")),
                    "change_pct": _safe_float(item.get("change_pct")),
                    "volume": _safe_float(item.get("volume")),
                    "amount": _safe_float(item.get("amount")),
                    "high": _safe_optional_float(item.get("high")),
                    "low": _safe_optional_float(item.get("low")),
                    "open": _safe_optional_float(item.get("open")),
                    "pre_close": _safe_optional_float(item.get("pre_close")),
                    "timestamp": now.isoformat(),
                    "data_source": "akshare_realtime",
                    "is_realtime": True,
                    "warnings": [],
                    "errors": [],
                }
    except Exception as exc:
        errors.append(str(exc))

    start_date = (now - timedelta(days=60)).strftime("%Y%m%d")
    kline_meta = get_klines_with_diagnostics(lookup_code, start_date=start_date, frequency="D")
    data = kline_meta.get("data") or []
    if data:
        latest = data[-1]
        prev = data[-2] if len(data) > 1 else None
        current = _safe_float(latest.get("close"))
        prev_close = _safe_float(prev.get("close")) if prev else current
        change = current - prev_close if prev else 0.0
        change_pct = change / prev_close * 100 if prev_close else 0.0
        return {
            "code": lookup_code,
            "name": get_stock_detail(lookup_code).get("name", "") if get_stock_detail(lookup_code) else "",
            "current": current,
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
            "volume": _safe_float(latest.get("volume")),
            "amount": _safe_float(latest.get("amount")),
            "high": _safe_optional_float(latest.get("high")),
            "low": _safe_optional_float(latest.get("low")),
            "open": _safe_optional_float(latest.get("open")),
            "pre_close": prev_close,
            "trade_date": str(latest.get("date", ""))[:10],
            "timestamp": now.isoformat(),
            "data_source": "latest_daily_kline",
            "is_realtime": False,
            "warnings": ["实时行情暂不可用，已退回最新日线收盘价"] + kline_meta.get("warnings", []),
            "errors": errors + kline_meta.get("errors", []),
        }

    return {
        "code": lookup_code,
        "name": "",
        "current": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "volume": 0.0,
        "amount": 0.0,
        "timestamp": now.isoformat(),
        "data_source": "empty",
        "is_realtime": False,
        "warnings": ["实时行情和日线兜底均未取得数据"],
        "errors": errors + kline_meta.get("errors", []),
    }


def add_to_watchlist(code: str, name: str = "", tags: list[str] | None = None, notes: str | None = None) -> dict:
    add_watchlist(code, name=name, tags=tags, notes=notes)
    return {"code": code.zfill(6), "status": "added"}


def remove_from_watchlist(code: str) -> dict:
    remove_watchlist(code)
    return {"code": code.zfill(6), "status": "removed"}


def get_watchlist_all() -> list[dict]:
    items = query_watchlist()
    # 补全股票基础信息与最近行情，避免 OCR 导入名称覆盖标准股票名称。
    with get_session() as session:
        for item in items:
            stock = session.get(StockModel, item["code"])
            if stock:
                item["name"] = stock.name
                item["exchange"] = stock.exchange
                item["industry"] = stock.industry
            else:
                item["exchange"] = ""
                item["industry"] = None

            latest = session.execute(
                select(KlineModel)
                .where(KlineModel.code == item["code"], KlineModel.frequency == "D")
                .order_by(KlineModel.date.desc())
                .limit(2)
            ).scalars().all()
            if latest:
                current = float(latest[0].close)
                item["current"] = current
                item["latest_date"] = latest[0].date.isoformat() if hasattr(latest[0].date, "isoformat") else str(latest[0].date)
                if len(latest) > 1 and latest[1].close:
                    prev_close = float(latest[1].close)
                    item["change"] = round(current - prev_close, 4)
                    item["change_pct"] = round((current - prev_close) / prev_close * 100, 4)
                else:
                    item["change"] = 0.0
                    item["change_pct"] = 0.0
            else:
                item["current"] = None
                item["change"] = None
                item["change_pct"] = None
                item["latest_date"] = None

            if "added_at" in item and item["added_at"]:
                item["added_at"] = item["added_at"].isoformat() if hasattr(item["added_at"], "isoformat") else str(item["added_at"])
    return items


def _stock_match_score(keyword: str, code: str, name: str) -> int | None:
    q = keyword.strip().upper()
    stock_code = str(code).zfill(6)
    stock_name = name or ""
    stock_name_upper = stock_name.upper()

    if q == stock_code:
        return 0
    if q.isdigit() and stock_code.startswith(q):
        return 10 + len(stock_code) - len(q)
    if q in stock_code:
        return 30 + stock_code.index(q)

    if q == stock_name_upper:
        return 40
    if stock_name_upper.startswith(q):
        return 50 + len(stock_name_upper) - len(q)
    if q in stock_name_upper:
        return 60 + stock_name_upper.index(q)

    if _is_ordered_subsequence(q, stock_name_upper):
        return 80 + len(stock_name_upper) - len(q)
    if all(ch in stock_name_upper for ch in q):
        return 120 + len(stock_name_upper) - len(q)

    return None


def _is_ordered_subsequence(query: str, text: str) -> bool:
    pos = 0
    for ch in query:
        found = text.find(ch, pos)
        if found < 0:
            return False
        pos = found + 1
    return True


def _market_label(exchange: str | None) -> str:
    mapping = {
        "SH": "沪A", "SZ": "深A", "BJ": "北交",
        "HK": "港股", "US": "美股",
    }
    return mapping.get(exchange or "", exchange or "-")


def _search_fallback_stocks(query: str, limit: int, watch_codes: set[str]) -> list[dict]:
    matches = []
    for stock in _FALLBACK_SEARCH_STOCKS:
        score = _stock_match_score(query, stock["code"], stock["name"])
        if score is None:
            continue
        exchange = stock.get("exchange", "")
        item = {
            "code": stock["code"],
            "name": stock["name"],
            "exchange": exchange,
            "market_label": _market_label(exchange),
            "industry": stock.get("industry"),
            "list_date": stock.get("list_date"),
            "is_watchlist": stock["code"] in watch_codes,
        }
        matches.append((score, stock["code"], item))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in matches[:limit]]


def _safe_float(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_stock_code(code: str) -> str:
    value = str(code or "").strip()
    if value.isdigit() and len(value) <= 6:
        return value.zfill(6)
    return value
