# -*- coding: utf-8 -*-
# 股票与自选股业务服务

from __future__ import annotations

from data.storage.database import init_db, get_session
from data.storage.repository import (
    query_stocks,
    query_klines,
    add_watchlist,
    remove_watchlist,
    query_watchlist,
)
from data.storage.models_orm import StockModel, WatchlistModel, KlineModel
from sqlalchemy import select


def get_all_stocks(exchange: str | None = None) -> list[dict]:
    df = query_stocks(exchange=exchange)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def search_stocks(keyword: str, limit: int = 10) -> list[dict]:
    """按代码或中文名称搜索股票，优先从stocks表查，为空则查自选股。"""
    query = keyword.strip()
    if not query:
        return []

    limit = max(1, min(limit, 50))
    with get_session() as session:
        stocks = session.execute(select(StockModel)).scalars().all()
        watch_rows = session.execute(select(WatchlistModel)).scalars().all()
        watch_codes = {r.code for r in watch_rows}

    # 如果stocks表为空，从自选股中搜索
    if not stocks:
        candidates = []
        for w in watch_rows:
            candidates.append(type('StockProxy', (), {
                'code': w.code, 'name': w.name or '', 'exchange': '',
                'industry': None, 'list_date': None,
            }))
    else:
        candidates = list(stocks)

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
    return [item[2] for item in matches[:limit]]


def get_stock_detail(code: str) -> dict | None:
    with get_session() as session:
        stock = session.get(StockModel, code.zfill(6))
        if stock is None:
            return None
        watch = session.get(WatchlistModel, code.zfill(6))
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
    df = query_klines(code, start_date=start_date, end_date=end_date, frequency=frequency)
    if df.empty:
        return []
    for col in ("date",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


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
