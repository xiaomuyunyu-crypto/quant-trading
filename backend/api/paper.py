# -*- coding: utf-8 -*-
# 实盘跟踪 API 路由

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from backend.models.paper import (
    CreateAccountRequest, AccountResponse, PositionResponse,
    SignalResponse, ConfirmSignalRequest, TradeResponse,
    AccountDetailResponse, EquityPoint,
)
from backend.core.paper_engine import (
    generate_daily_signals, confirm_signal, get_account_summary,
    backfill_signal_outcomes,
)
from data.storage.repository import (
    create_paper_account, get_paper_account, list_paper_accounts,
    stop_paper_account, get_paper_trades, get_paper_signals,
)

router = APIRouter(prefix="/paper", tags=["实盘跟踪"])


# ─── 账户管理 ───

@router.post("/account", response_model=AccountResponse)
def api_create_account(req: CreateAccountRequest):
    """创建模拟账户"""
    acct = create_paper_account(
        name=req.name,
        initial_capital=req.initial_capital,
        strategy_key=req.strategy_key,
    )
    return AccountResponse(**acct)


@router.get("/account/{account_id}")
def api_get_account(account_id: int):
    """获取账户详情（含持仓、待处理信号、权益）"""
    summary = get_account_summary(account_id)
    if not summary:
        raise HTTPException(status_code=404, detail="账户不存在")

    from backend.models.paper import PositionResponse as PR, SignalResponse as SR

    return {
        "account": AccountResponse(**summary["account"]),
        "total_equity": summary["total_equity"],
        "total_return": summary["total_return"],
        "total_return_pct": summary["total_return_pct"],
        "positions": [
            PR(
                id=p["id"], account_id=p["account_id"],
                code=p["code"], name=p["name"],
                quantity=p["quantity"], cost_price=p["cost_price"],
                current_price=p["current_price"],
                market_value=p.get("market_value", 0),
                unrealized_pnl=p.get("unrealized_pnl", 0),
                unrealized_pnl_pct=p.get("unrealized_pnl_pct", 0),
            )
            for p in summary["positions"]
        ],
        "pending_signals": [
            SR(
                id=s["id"], code=s["code"], name=s.get("name", ""),
                signal_type=s["signal_type"],
                confidence=s["confidence"], composite_score=s["composite_score"],
                reason=s["reason"] or "", close_price=s["close_price"],
                status=s["status"], generated_at=s["generated_at"],
                source=s.get("source"),
            )
            for s in summary["pending_signals"]
        ],
    }


@router.get("/accounts")
def api_list_accounts():
    """列出所有模拟账户"""
    accts = list_paper_accounts()
    return {"total": len(accts), "items": [AccountResponse(**a) for a in accts]}


@router.post("/account/{account_id}/stop")
def api_stop_account(account_id: int):
    """停止模拟（结算）"""
    from backend.core.paper_engine import get_account_summary

    # 先做结算快照
    summary = get_account_summary(account_id)
    acct = stop_paper_account(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="账户不存在")

    return {
        "account": AccountResponse(**acct),
        "final_equity": summary.get("total_equity", acct["initial_capital"]),
        "total_return_pct": summary.get("total_return_pct", 0),
        "settled_at": acct.get("stopped_at"),
    }


# ─── 信号生成 ───

@router.post("/signals/generate")
def api_generate_signals(
    account_id: int | None = Query(default=None, description="关联账户ID"),
    codes: str | None = Query(default=None, description="股票代码列表，逗号分隔；传入则按手动股票分析"),
    scope: str = Query(default="holdings", description="holdings=观察股/持仓，watchlist=自选股"),
    limit: int = Query(default=20, ge=1, le=100, description="自选股分析上限"),
):
    """为持仓观察股、自选股或手动股票生成当日信号"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    signals = generate_daily_signals(code_list, account_id=account_id, scope=scope, limit=limit)
    return {
        "scope": "manual" if code_list else scope,
        "total": len(signals),
        "buy_signals": [s for s in signals if s["signal_type"] == "BUY"],
        "sell_signals": [s for s in signals if s["signal_type"] == "SELL"],
        "all": signals,
    }


# ─── 信号确认 ───

@router.post("/signals/confirm")
def api_confirm_signal(req: ConfirmSignalRequest):
    """确认或拒绝信号 → 执行模拟交易"""
    result = confirm_signal(req.signal_id, action=req.action)
    if result is None:
        raise HTTPException(status_code=404, detail="信号不存在")
    return result


# ─── 交易记录 ───

@router.get("/account/{account_id}/trades")
def api_get_trades(account_id: int, limit: int = Query(default=50)):
    """获取账户交易记录"""
    trades = get_paper_trades(account_id, limit=limit)
    return {
        "total": len(trades),
        "trades": [
            TradeResponse(
                id=t["id"], account_id=t["account_id"],
                code=t["code"], action=t["action"],
                price=t["price"], quantity=t["quantity"],
                amount=t["amount"], reason=t.get("reason", ""),
                signal_confidence=t.get("signal_confidence", 0),
                confirmed=t.get("confirmed", 0),
                trade_date=t["trade_date"],
            )
            for t in trades
        ],
    }


# ─── 权益曲线 ───

@router.get("/account/{account_id}/equity")
def api_get_equity_curve(account_id: int):
    """获取权益曲线（基于交易记录重建）"""
    trades = get_paper_trades(account_id, limit=10000)
    acct = get_paper_account(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 从交易记录和当前持仓重建权益曲线
    initial = acct["initial_capital"]
    equity_points = [{"date": str(acct["created_at"])[:10], "equity": initial}]

    cash = initial
    positions = {}
    for t in reversed(trades):
        if t["action"] == "BUY":
            cash -= t["amount"]
            positions[t["code"]] = positions.get(t["code"], 0) + t["quantity"]
        elif t["action"] == "SELL":
            cash += t["amount"]
            positions[t["code"]] = positions.get(t["code"], 0) - t["quantity"]

        # 简化：当天权益 = 现金（不含持仓浮盈，因为没有每日收盘价快照）
        equity_points.append({
            "date": str(t["trade_date"])[:10],
            "equity": round(cash, 2),
        })

    # 补充当前权益
    summary = get_account_summary(account_id)
    if summary:
        equity_points.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "equity": summary["total_equity"],
        })

    return {"account_id": account_id, "equity_curve": equity_points}


# ─── 信号回顾 ───

@router.get("/signals/review")
def api_review_signals(
    account_id: int | None = Query(default=None),
    status: str | None = Query(default=None, description="pending/confirmed/rejected"),
):
    """查看历史信号及其验证结果"""
    signals = get_paper_signals(account_id=account_id, status=status, limit=100)
    correct = sum(1 for s in signals if s.get("outcome") == "correct")
    wrong = sum(1 for s in signals if s.get("outcome") == "wrong")
    return {
        "total": len(signals),
        "correct": correct,
        "wrong": wrong,
        "accuracy": round(correct / (correct + wrong), 4) if (correct + wrong) > 0 else 0,
        "signals": signals,
    }


@router.get("/market-hours")
def api_market_hours():
    """查询当前交易时段状态"""
    from backend.core.paper_engine import is_trading_hours
    trading, phase = is_trading_hours()
    return {"trading": trading, "phase": phase, "timestamp": datetime.now().isoformat()}


@router.post("/account/{account_id}/refresh-prices")
def api_refresh_prices(account_id: int):
    """刷新账户持仓现价（交易时段=实时快照，非交易时段=日线收盘价）"""
    from backend.core.paper_engine import refresh_position_prices
    result = refresh_position_prices(account_id)
    return result


@router.post("/refresh-all-prices")
def api_refresh_all_prices():
    """刷新所有活跃账户持仓现价"""
    from backend.core.paper_engine import refresh_all_accounts_prices
    results = refresh_all_accounts_prices()
    return {"accounts": len(results), "results": results}


@router.post("/signals/backfill")
def api_backfill_outcomes(
    account_id: int = Query(...),
    lookback_days: int = Query(default=5, description="事后验证天数"),
):
    """事后验证：回溯历史信号是否正确"""
    backfill_signal_outcomes(account_id, lookback_days=lookback_days)
    return {"status": "done", "account_id": account_id, "lookback_days": lookback_days}
