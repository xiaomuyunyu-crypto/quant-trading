# -*- coding: utf-8 -*-
# 仪表盘 API 路由

from fastapi import APIRouter
from sqlalchemy import select, func

from data.storage.database import get_session
from data.storage.models_orm import (
    StockModel, WatchlistModel, KlineModel, PaperAccountModel,
)
from data.storage.repository import list_paper_accounts

router = APIRouter(tags=["仪表盘"])


@router.get("/dashboard")
def dashboard_summary():
    """仪表盘首页摘要数据"""
    with get_session() as session:
        # 自选股数量
        watchlist_count = session.execute(
            select(func.count()).select_from(WatchlistModel)
        ).scalar() or 0

        # 总股票数
        total_stocks = session.execute(
            select(func.count()).select_from(StockModel)
        ).scalar() or 0

        # 总K线数据量
        total_klines = session.execute(
            select(func.count()).select_from(KlineModel)
        ).scalar() or 0

        # 活跃模拟账户
        active_accounts = session.execute(
            select(func.count()).select_from(PaperAccountModel).where(
                PaperAccountModel.status == "active"
            )
        ).scalar() or 0

        # 计算活跃账户总权益
        from backend.core.paper_engine import get_account_summary
        accounts = list_paper_accounts()
        active_eq = 0.0
        active_pnl = 0.0
        active_pnl_pct = 0.0
        for acct in accounts:
            if acct.get("status") == "active":
                summary = get_account_summary(acct["id"])
                active_eq += summary.get("total_equity", acct.get("cash", 0))
                active_pnl += summary.get("total_equity", 0) - acct.get("initial_capital", 0)

        # 最近更新日期
        latest_kline = session.execute(
            select(KlineModel.date).order_by(KlineModel.date.desc()).limit(1)
        ).scalar_one_or_none()

    return {
        "watchlistCount": watchlist_count,
        "totalStocks": total_stocks,
        "totalKlines": total_klines,
        "todayPnL": round(active_pnl, 2),
        "todayPnLPct": round(active_pnl / active_eq * 100, 2) if active_eq > 0 else 0,
        "totalEquity": round(active_eq, 2),
        "activeStrategies": active_accounts,
        "latestDataDate": str(latest_kline)[:10] if latest_kline else None,
    }
