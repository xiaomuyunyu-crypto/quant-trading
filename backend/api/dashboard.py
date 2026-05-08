# -*- coding: utf-8 -*-
# 仪表盘 API 路由

from fastapi import APIRouter
from sqlalchemy import select, func, text

from data.storage.database import get_session
from data.storage.repository import list_paper_accounts

router = APIRouter(tags=["仪表盘"])


@router.post("/seed-watchlist")
def seed_watchlist():
    """手动触发自选股种子数据导入"""
    from backend.main import _seed_watchlist
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    _seed_watchlist(project_root)

    from data.storage.database import get_session
    from data.storage.models_orm import WatchlistModel
    from sqlalchemy import select, func
    with get_session() as s:
        count = s.execute(select(func.count()).select_from(WatchlistModel)).scalar() or 0
    return {"status": "done", "watchlist_count": count}


@router.get("/dashboard")
def dashboard_summary():
    """仪表盘首页摘要数据"""
    try:
        with get_session() as session:
            # 检查表是否存在
            tables = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).scalars().all()

            watchlist_count = 0
            total_stocks = 0
            total_klines = 0
            active_accounts = 0
            latest_kline = None

            if "watchlist" in tables:
                watchlist_count = session.execute(
                    select(func.count()).select_from(text("watchlist"))
                ).scalar() or 0

            if "stocks" in tables:
                total_stocks = session.execute(
                    select(func.count()).select_from(text("stocks"))
                ).scalar() or 0

            if "klines" in tables:
                total_klines = session.execute(
                    select(func.count()).select_from(text("klines"))
                ).scalar() or 0

                latest = session.execute(text(
                    "SELECT date FROM klines ORDER BY date DESC LIMIT 1"
                )).scalar_one_or_none()
                if latest:
                    latest_kline = str(latest)[:10]

            if "paper_accounts" in tables:
                active_accounts = session.execute(text(
                    "SELECT COUNT(*) FROM paper_accounts WHERE status = 'active'"
                )).scalar() or 0

        # 计算活跃账户总权益
        active_eq = 0.0
        active_pnl = 0.0
        try:
            from backend.core.paper_engine import get_account_summary
            accounts = list_paper_accounts()
            for acct in accounts:
                if acct.get("status") == "active":
                    summary = get_account_summary(acct["id"])
                    active_eq += summary.get("total_equity", acct.get("cash", 0))
                    active_pnl += summary.get("total_equity", 0) - acct.get("initial_capital", 0)
        except Exception:
            pass

        return {
            "watchlistCount": watchlist_count,
            "totalStocks": total_stocks,
            "totalKlines": total_klines,
            "todayPnL": round(active_pnl, 2),
            "todayPnLPct": round(active_pnl / active_eq * 100, 2) if active_eq > 0 else 0,
            "totalEquity": round(active_eq, 2),
            "activeStrategies": active_accounts,
            "latestDataDate": latest_kline,
        }
    except Exception:
        return {
            "watchlistCount": 0,
            "totalStocks": 0,
            "totalKlines": 0,
            "todayPnL": 0,
            "todayPnLPct": 0,
            "totalEquity": 0,
            "activeStrategies": 0,
            "latestDataDate": None,
        }
