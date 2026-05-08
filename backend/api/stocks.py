# -*- coding: utf-8 -*-
# 股票与自选股 API 路由

from fastapi import APIRouter, HTTPException, Query

from backend.models.stock import StockDetail, StockList
from backend.services.stock_service import (
    get_all_stocks,
    search_stocks,
    get_stock_detail,
    get_klines,
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
    items = search_stocks(keyword, limit=limit)
    return {"total": len(items), "items": items}


@router.get("/stocks/{code}", response_model=StockDetail)
def stock_detail(code: str):
    detail = get_stock_detail(code)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    return StockDetail(**detail)


# ─── K线行情 ───

@router.get("/stocks/{code}/klines")
def stock_klines(
    code: str,
    start_date: str | None = Query(default=None, description="开始日期 YYYYMMDD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYYMMDD"),
    frequency: str = Query(default="D", description="周期 D/W/M"),
):
    klines = get_klines(code, start_date=start_date, end_date=end_date, frequency=frequency)
    return {"code": code.zfill(6), "frequency": frequency, "count": len(klines), "data": klines}


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
