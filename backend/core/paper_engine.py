# -*- coding: utf-8 -*-
"""
实盘跟踪核心引擎。

功能：
  1. 读取跟踪标的的K线 → 运行信号引擎 → 生成 BUY/SELL 建议
  2. 用户确认/拒绝信号 → 以当日收盘价记录交易
  3. 实时计算持仓盈亏、总权益、累计收益率
  4. 事后验证信号正确性 → 记录 outcome
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

_FUND_NAME_CACHE: dict[str, str] | None = None


def _normalize_code(code: str) -> str:
    """统一股票代码格式，数字代码补足6位。"""
    value = str(code or "").strip()
    if value.isdigit() and len(value) <= 6:
        return value.zfill(6)
    return value


def _dedupe_codes(codes: list[str]) -> list[str]:
    result = []
    seen = set()
    for code in codes:
        normalized = _normalize_code(code)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _get_stock_name_map(codes: list[str]) -> dict[str, str]:
    """从股票基础表补全名称，避免信号和持仓只显示代码。"""
    normalized_codes = _dedupe_codes(codes)
    if not normalized_codes:
        return {}

    from sqlalchemy import select
    from data.storage.database import get_session
    from data.storage.models_orm import StockModel

    with get_session() as session:
        rows = session.execute(
            select(StockModel.code, StockModel.name).where(StockModel.code.in_(normalized_codes))
        ).all()
        result = {code: name or "" for code, name in rows}

    missing_codes = [code for code in normalized_codes if not result.get(code)]
    if missing_codes:
        fund_names = {
            code: name
            for code, name in _get_fund_name_map(missing_codes).items()
            if name
        }
        if fund_names:
            _save_fund_names_to_stock_table(fund_names)
            result.update(fund_names)
    return result


def _get_fund_name_map(codes: list[str]) -> dict[str, str]:
    """股票基础表缺失时，用基金名称表补 ETF/LOF 名称，并在进程内缓存。"""
    global _FUND_NAME_CACHE
    if _FUND_NAME_CACHE is None:
        try:
            import akshare as ak

            df = ak.fund_name_em()
            code_col = df.columns[0]
            name_col = df.columns[2]
            _FUND_NAME_CACHE = {
                str(row[code_col]).zfill(6): str(row[name_col])
                for _, row in df.iterrows()
            }
        except Exception:
            _FUND_NAME_CACHE = {}

    return {code: _FUND_NAME_CACHE.get(code, "") for code in codes}


def _save_fund_names_to_stock_table(name_map: dict[str, str]) -> None:
    """把已解析的基金/ETF名称写入基础表，下一次启动也能快速命中。"""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from data.storage.database import get_session
    from data.storage.models_orm import StockModel

    with get_session() as session:
        for code, name in name_map.items():
            stmt = sqlite_insert(StockModel).values(
                code=code,
                name=name,
                exchange=_guess_exchange_by_code(code),
                industry="ETF/基金",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "industry": stmt.excluded.industry,
                },
            )
            session.execute(stmt)
        session.commit()


def _guess_exchange_by_code(code: str) -> str:
    if code.startswith(("5", "6")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _get_stock_name(code: str) -> str:
    return _get_stock_name_map([code]).get(_normalize_code(code), "")


def _enrich_stock_names(rows: list[dict]) -> list[dict]:
    name_map = _get_stock_name_map([r.get("code", "") for r in rows])
    for row in rows:
        code = _normalize_code(row.get("code", ""))
        row["code"] = code
        if not row.get("name"):
            row["name"] = name_map.get(code, "")
    return rows


def _resolve_signal_codes(
    codes: list[str] | None,
    account_id: int | None,
    scope: str,
    limit: int,
) -> tuple[list[str], str]:
    """
    解析实盘信号分析范围。

    默认只分析账户持仓（观察股），避免一次性扫全自选股或全市场。
    """
    if codes:
        return _dedupe_codes(codes), "manual"

    normalized_scope = (scope or "holdings").lower()
    if normalized_scope in ("holdings", "positions", "observe", "observed"):
        if not account_id:
            return [], "holdings"
        from data.storage.repository import get_paper_positions

        positions = get_paper_positions(account_id)
        return _dedupe_codes([p["code"] for p in positions]), "holdings"

    if normalized_scope in ("watchlist", "optional"):
        from data.storage.repository import query_watchlist

        watchlist = query_watchlist()
        selected = watchlist[:limit] if limit > 0 else watchlist
        return _dedupe_codes([w["code"] for w in selected]), "watchlist"

    return [], normalized_scope


def generate_daily_signals(codes: list[str] | None = None,
                            account_id: int | None = None,
                            scope: str = "holdings",
                            limit: int = 20) -> list[dict]:
    """
    对给定股票列表生成当日信号。

    codes 有值：分析手动选择股票
    codes 为空：默认只分析账户持仓（观察股）
    scope=watchlist：显式分析自选股，默认限制前20只
    """
    from backend.core.kline_utils import get_klines_df
    from data.storage.repository import save_paper_signal
    from strategy.composite import create_default_strategy

    codes, signal_source = _resolve_signal_codes(codes, account_id, scope, limit)
    if not codes:
        return []

    strategy = create_default_strategy(signal_mode="majority")
    results = []
    name_map = _get_stock_name_map(codes)

    for code in codes:
        try:
            klines = get_klines_df(code, frequency="D")
            if klines is None or klines.empty or len(klines) < 60:
                continue

            result = strategy.analyze(klines)
            close_price = float(klines["close"].iloc[-1])

            saved = save_paper_signal(
                code=code,
                signal_type=result.signal,
                confidence=result.confidence,
                composite_score=result.confidence,
                reason="；".join(result.reasons) if result.reasons else result.signal,
                close_price=close_price,
                account_id=account_id,
            )
            saved["close_price"] = close_price
            saved["name"] = name_map.get(code, "")
            saved["source"] = signal_source
            results.append(saved)
        except Exception:
            continue

    return results


def confirm_signal(signal_id: int, action: str = "confirm") -> dict | None:
    """
    确认或拒绝信号，执行对应的模拟交易。

    action: "confirm" → 执行交易记录; "reject" → 仅标记信号
    """
    from data.storage.repository import (
        get_paper_signals, get_paper_account, get_paper_positions,
        upsert_paper_position, add_paper_trade, update_paper_cash,
    )
    from data.storage.database import get_session
    from data.storage.models_orm import PaperSignalModel

    # 获取信号
    with get_session() as session:
        sig = session.get(PaperSignalModel, signal_id)
        if not sig:
            return None

        new_status = "confirmed" if action == "confirm" else "rejected"
        sig.status = new_status
        session.commit()

        code = sig.code
        signal_type = sig.signal_type
        price = sig.close_price
        account_id = sig.account_id
        reason = sig.reason or ""
        confidence = sig.confidence

    if action != "confirm" or not account_id or signal_type not in ("BUY", "SELL"):
        return {"signal_id": signal_id, "status": new_status, "action": "no_trade"}

    account = get_paper_account(account_id)
    if not account or account["status"] != "active":
        return {"signal_id": signal_id, "status": "account_inactive"}

    cash = account["cash"]
    stock_name = _get_stock_name(code)
    if signal_type == "BUY":
        # 全仓买入
        if cash <= 0 or price <= 0:
            return {"signal_id": signal_id, "status": "insufficient_funds"}
        shares = int(cash / price)
        if shares <= 0:
            return {"signal_id": signal_id, "status": "insufficient_funds"}
        amount = shares * price
        new_cash = cash - amount

        # 更新仓位
        positions = get_paper_positions(account_id)
        existing = {p["code"]: p for p in positions}
        if code in existing:
            old_qty = existing[code]["quantity"]
            old_cost = existing[code]["cost_price"]
            new_qty = old_qty + shares
            new_cost = (old_cost * old_qty + price * shares) / new_qty if new_qty > 0 else price
        else:
            new_qty = shares
            new_cost = price

        position_name = existing.get(code, {}).get("name", "") or stock_name
        upsert_paper_position(account_id, code, name=position_name, quantity=new_qty,
                              cost_price=new_cost, current_price=price)
        update_paper_cash(account_id, new_cash)
        add_paper_trade(account_id, code, "BUY", price, shares, amount,
                        reason=reason, confidence=confidence,
                        confirmed=1)

        return {
            "signal_id": signal_id, "status": "executed",
            "action": "BUY", "price": price, "shares": shares,
            "amount": amount, "cash_after": new_cash,
        }

    elif signal_type == "SELL":
        positions = get_paper_positions(account_id)
        pos = next((p for p in positions if p["code"] == code), None)
        if not pos or pos["quantity"] <= 0:
            return {"signal_id": signal_id, "status": "no_position"}

        shares = pos["quantity"]
        amount = shares * price
        new_cash = cash + amount

        upsert_paper_position(account_id, code, name=pos.get("name", "") or stock_name, quantity=0,
                              cost_price=0, current_price=price)
        update_paper_cash(account_id, new_cash)
        add_paper_trade(account_id, code, "SELL", price, shares, amount,
                        reason=reason, confidence=confidence,
                        confirmed=1)

        return {
            "signal_id": signal_id, "status": "executed",
            "action": "SELL", "price": price, "shares": shares,
            "amount": amount, "cash_after": new_cash,
        }

    return {"signal_id": signal_id, "status": "no_action"}


def get_account_summary(account_id: int) -> dict:
    """获取账户完整摘要：总权益、收益率、持仓盈亏"""
    from data.storage.repository import get_paper_account, get_paper_positions, get_paper_signals

    account = get_paper_account(account_id)
    if not account:
        return {}

    positions = get_paper_positions(account_id)
    _enrich_stock_names(positions)

    # 现价优先用持仓表存储值（由 refresh_position_prices 更新），兜底查K线
    for p in positions:
        if not p.get("current_price") or p["current_price"] <= 0:
            try:
                from backend.core.kline_utils import get_klines_df
                k = get_klines_df(p["code"], frequency="D")
                if k is not None and not k.empty:
                    p["current_price"] = float(k["close"].iloc[-1])
            except Exception:
                p["current_price"] = p["cost_price"]

    cash = account["cash"]
    position_value = sum(p["quantity"] * p["current_price"] for p in positions)
    total_equity = cash + position_value
    total_return = (total_equity - account["initial_capital"]) / account["initial_capital"]

    # 计算各持仓盈亏
    for p in positions:
        p["market_value"] = p["quantity"] * p["current_price"]
        if p["cost_price"] > 0 and p["quantity"] > 0:
            p["unrealized_pnl"] = (p["current_price"] - p["cost_price"]) * p["quantity"]
            p["unrealized_pnl_pct"] = (p["current_price"] - p["cost_price"]) / p["cost_price"]

    # 待处理信号
    pending_signals = get_paper_signals(account_id=account_id, status="pending", limit=20)
    _enrich_stock_names(pending_signals)

    return {
        "account": account,
        "total_equity": round(total_equity, 2),
        "total_return": round(total_return, 6),
        "total_return_pct": round(total_return * 100, 2),
        "positions": positions,
        "pending_signals": pending_signals,
    }


def backfill_signal_outcomes(account_id: int, lookback_days: int = 5):
    """
    事后验证历史信号：
    对已确认的信号，看N天后价格走势是否符合预期。
    BUY信号 → N天后价格更高 = correct
    SELL信号 → N天后价格更低 = correct
    """
    from data.storage.repository import get_paper_signals, update_signal_outcome, query_klines

    signals = get_paper_signals(account_id=account_id, status="confirmed", limit=200)
    for s in signals:
        if s["outcome"] and s["outcome"] != "pending":
            continue
        try:
            trade_date = s["generated_at"]
            if isinstance(trade_date, str):
                trade_date = datetime.fromisoformat(trade_date.replace("Z", "+00:00"))
            end_date = trade_date + timedelta(days=lookback_days)

            k = query_klines(s["code"], frequency="D")
            if k.empty:
                continue
            k["date"] = pd.to_datetime(k["date"])
            after = k[(k["date"] > trade_date) & (k["date"] <= end_date)]
            if after.empty:
                continue

            price_at_signal = s["close_price"]
            price_after = float(after["close"].iloc[-1])

            if s["signal_type"] == "BUY":
                outcome = "correct" if price_after > price_at_signal else "wrong"
            elif s["signal_type"] == "SELL":
                outcome = "correct" if price_after < price_at_signal else "wrong"
            else:
                outcome = "pending"

            update_signal_outcome(s["id"], outcome, lookback_days)
        except Exception:
            continue


# ─── 实时价格刷新 ───

def is_trading_hours() -> tuple[bool, str]:
    """判断当前是否在 A 股交易时段。返回 (是否交易中, 时段描述)"""
    from datetime import time
    now = datetime.now()
    # 周一至周五
    if now.weekday() >= 5:
        return False, "周末休市"
    t = now.time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    if morning_start <= t <= morning_end:
        return True, "早盘交易中"
    elif afternoon_start <= t <= afternoon_end:
        return True, "午盘交易中"
    elif t < morning_start:
        return False, "未开盘"
    elif t < afternoon_start:
        return False, "午间休市"
    else:
        return False, "已收盘"


def refresh_position_prices(account_id: int) -> dict:
    """
    刷新账户所有持仓的现价。

    交易时段：用 AKShare 全市场实时快照（一次调用覆盖全部持仓）
    非交易时段：用最新日线收盘价
    返回：{updated: N, prices: {code: price}}
    """
    from data.storage.repository import get_paper_positions, upsert_paper_position

    positions = get_paper_positions(account_id)
    if not positions:
        return {"updated": 0, "prices": {}, "message": "无持仓"}

    _enrich_stock_names(positions)
    codes = [p["code"] for p in positions]
    trading, phase = is_trading_hours()
    prices = {}

    if trading:
        # 交易时段：拉全市场实时快照
        try:
            from data.fetcher.akshare_fetcher import fetch_realtime_quotes
            quotes = fetch_realtime_quotes()
            if not quotes.empty:
                quote_map = dict(zip(quotes["code"], quotes["current"]))
                for code in codes:
                    if code in quote_map and quote_map[code] > 0:
                        prices[code] = float(quote_map[code])
        except Exception:
            pass

    # 没拿到实时价的 → 用日线收盘价兜底
    for code in codes:
        if code not in prices:
            try:
                from backend.core.kline_utils import get_klines_df
                k = get_klines_df(code, frequency="D")
                if k is not None and not k.empty:
                    prices[code] = float(k["close"].iloc[-1])
            except Exception:
                continue

    # 更新持仓表
    updated = 0
    for p in positions:
        code = p["code"]
        if code in prices:
            upsert_paper_position(
                account_id, code, name=p.get("name", ""),
                quantity=p["quantity"], cost_price=p["cost_price"],
                current_price=prices[code],
            )
            updated += 1

    return {
        "updated": updated,
        "prices": prices,
        "phase": phase,
        "trading": trading,
        "timestamp": datetime.now().isoformat(),
    }


def refresh_all_accounts_prices() -> list[dict]:
    """刷新所有活跃账户的持仓价格"""
    from data.storage.repository import list_paper_accounts
    accounts = list_paper_accounts()
    active = [a for a in accounts if a["status"] == "active"]
    results = []
    for a in active:
        result = refresh_position_prices(a["id"])
        result["account_id"] = a["id"]
        results.append(result)
    return results
