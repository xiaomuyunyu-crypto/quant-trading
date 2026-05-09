# -*- coding: utf-8 -*-
# 股票与自选股 API 路由

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from backend.models.stock import StockDetail, StockList
from backend.services.stock_service import (
    get_all_stocks,
    search_stocks,
    search_stocks_with_meta,
    get_stock_detail,
    get_klines,
    get_klines_with_diagnostics,
    get_realtime_quote,
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist_all,
)

router = APIRouter(tags=["stocks"])


# ─── 股票查询 ───

@router.get("/stocks", response_model=StockList)
def list_stocks(exchange: str | None = Query(default=None, description="交易所 SZ/SH/BJ")):
    items = get_all_stocks(exchange=exchange)
    result = []
    for s in items:
        result.append(StockDetail(
            code=s.get("code", ""),
            name=s.get("name", ""),
            exchange=s.get("exchange", "SZ"),
            industry=s.get("industry"),
            list_date=s.get("list_date"),
            is_watchlist=False,
        ))
    return StockList(total=len(result), items=result)


@router.get("/stocks/search")
def stock_search(
    keyword: str = Query(..., min_length=1, description="股票代码或中文名称关键字"),
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
):
    return search_stocks_with_meta(keyword, limit=limit)


@router.get("/stocks/{code}/quote")
def stock_quote(code: str):
    """获取单只股票实时行情；实时源不可用时退回最新日线收盘价。"""
    quote = get_realtime_quote(code)
    if quote.get("data_source") == "empty":
        raise HTTPException(status_code=404, detail=f"股票 {code} 暂无实时或日线行情")
    return quote


# ─── K线行情 ───

@router.get("/stocks/{code}/klines")
def stock_klines(
    code: str,
    start_date: str | None = Query(default=None, description="开始日期 YYYYMMDD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYYMMDD"),
    days: int | None = Query(default=None, ge=1, le=15000, description="最近N个自然日；未传start_date时生效"),
    frequency: str = Query(default="D", description="周期 D/W/M"),
):
    resolved_start = start_date
    resolved_end = end_date or datetime.now().strftime("%Y%m%d")
    if days and not resolved_start:
        resolved_start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    result = get_klines_with_diagnostics(
        code,
        start_date=resolved_start,
        end_date=resolved_end,
        frequency=frequency,
    )
    return result


@router.get("/stocks/{code}", response_model=StockDetail)
def stock_detail(code: str):
    detail = get_stock_detail(code)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    return StockDetail(**detail)


# ─── 自选股管理 ───

@router.get("/watchlist")
def watchlist_list():
    items = get_watchlist_all()
    return {"total": len(items), "items": items}


@router.post("/watchlist/{code}")
def watchlist_add(
    code: str,
    name: str = Query(default="", description="股票名称"),
    tags: str = Query(default="", description="标签，逗号分隔"),
    notes: str | None = Query(default=None, description="备注"),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return add_to_watchlist(code, name=name, tags=tag_list, notes=notes)


@router.delete("/watchlist/{code}")
def watchlist_remove(code: str):
    return remove_from_watchlist(code)
