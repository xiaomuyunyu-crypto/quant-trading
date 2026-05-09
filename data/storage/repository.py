# -*- coding: utf-8 -*-
# 数据存储与查询接口

import pandas as pd
from datetime import date, datetime
from sqlalchemy import select, delete, and_, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import get_session
from .models_orm import (
    StockModel, KlineModel, WatchlistModel,
    IndustryModel, IndustryStockModel, FundFlowModel, FinancialModel,
)


# ─── 股票基础信息 ───

def upsert_stocks(df: pd.DataFrame) -> int:
    """批量写入/更新股票列表，返回写入行数"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            code = str(r.get("code", "")).zfill(6)
            stmt = sqlite_insert(StockModel).values(
                code=code,
                name=str(r.get("name", "")),
                exchange=str(r.get("exchange", "SZ")),
                industry=str(r.get("industry", "")) or None,
                list_date=_parse_date(r.get("list_date")),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "industry": stmt.excluded.industry,
                    "list_date": stmt.excluded.list_date,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def query_stocks(exchange: str | None = None) -> pd.DataFrame:
    """查询股票列表"""
    with get_session() as session:
        stmt = select(StockModel)
        if exchange:
            stmt = stmt.where(StockModel.exchange == exchange)
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "code": r.code,
                "name": r.name,
                "exchange": r.exchange,
                "industry": r.industry,
                "list_date": r.list_date,
            }
            for r in rows
        ]
        return pd.DataFrame(data)


# ─── K线数据 ───

def upsert_klines(df: pd.DataFrame) -> int:
    """批量写入/更新K线，返回写入行数"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            code = str(r["code"]).zfill(6)
            stmt = sqlite_insert(KlineModel).values(
                code=code,
                date=pd.to_datetime(r["date"]).to_pydatetime(),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume", 0)),
                amount=float(r.get("amount", 0)),
                frequency=str(r.get("frequency", "D")),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "date"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "amount": stmt.excluded.amount,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def query_klines(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> pd.DataFrame:
    """查询K线数据"""
    with get_session() as session:
        stmt = select(KlineModel).where(KlineModel.code == code.zfill(6))
        if frequency:
            stmt = stmt.where(KlineModel.frequency == frequency)
        if start_date:
            stmt = stmt.where(KlineModel.date >= pd.to_datetime(start_date))
        if end_date:
            stmt = stmt.where(KlineModel.date <= pd.to_datetime(end_date))
        stmt = stmt.order_by(KlineModel.date.asc())
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "code": r.code,
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "amount": r.amount,
                "frequency": r.frequency,
            }
            for r in rows
        ]
        return pd.DataFrame(data)


def get_latest_trade_date(code: str) -> datetime | None:
    """获取某股票最新K线日期"""
    with get_session() as session:
        stmt = (
            select(KlineModel.date)
            .where(KlineModel.code == code.zfill(6))
            .order_by(KlineModel.date.desc())
            .limit(1)
        )
        result = session.execute(stmt).scalar_one_or_none()
        return result


def get_kline_date_range(code: str, frequency: str = "D") -> tuple[datetime | None, datetime | None]:
    """获取某股票本地K线覆盖区间。"""
    with get_session() as session:
        stmt = select(func.min(KlineModel.date), func.max(KlineModel.date)).where(
            KlineModel.code == code.zfill(6)
        )
        if frequency:
            stmt = stmt.where(KlineModel.frequency == frequency)
        first_date, last_date = session.execute(stmt).one()
        return first_date, last_date


# ─── 自选股 ───

def add_watchlist(code: str, name: str = "", tags: list[str] | None = None, notes: str | None = None):
    with get_session() as session:
        item = WatchlistModel(
            code=code.zfill(6),
            name=name,
            tags=tags or [],
            notes=notes,
        )
        session.merge(item)
        session.commit()


def remove_watchlist(code: str):
    with get_session() as session:
        stmt = delete(WatchlistModel).where(WatchlistModel.code == code.zfill(6))
        session.execute(stmt)
        session.commit()


def query_watchlist() -> list[dict]:
    with get_session() as session:
        stmt = select(WatchlistModel).order_by(WatchlistModel.added_at.desc())
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "code": r.code,
                "name": r.name,
                "tags": r.tags,
                "notes": r.notes,
                "added_at": r.added_at,
            }
            for r in rows
        ]


# ─── 行业板块 ───

def upsert_industries(df: pd.DataFrame) -> int:
    """批量写入/更新行业板块"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            stmt = sqlite_insert(IndustryModel).values(
                code=str(r.get("code", "")),
                name=str(r.get("name", "")),
                stock_count=int(r.get("stock_count", 0)),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": stmt.excluded.name,
                    "stock_count": stmt.excluded.stock_count,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def upsert_industry_stocks(industry_code: str, df: pd.DataFrame) -> int:
    """批量写入/更新某行业板块的成分股"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            stmt = sqlite_insert(IndustryStockModel).values(
                industry_code=str(industry_code),
                stock_code=str(r.get("stock_code", "")).zfill(6),
                stock_name=str(r.get("stock_name", "")),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["industry_code", "stock_code"],
                set_={"stock_name": stmt.excluded.stock_name},
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def query_industries() -> pd.DataFrame:
    with get_session() as session:
        rows = session.execute(select(IndustryModel)).scalars().all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {"code": r.code, "name": r.name, "stock_count": r.stock_count}
            for r in rows
        ])


def query_industry_stocks(industry_code: str) -> pd.DataFrame:
    with get_session() as session:
        stmt = select(IndustryStockModel).where(
            IndustryStockModel.industry_code == str(industry_code)
        )
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {"stock_code": r.stock_code, "stock_name": r.stock_name}
            for r in rows
        ])


# ─── 资金流向 ───

def upsert_fund_flows(df: pd.DataFrame) -> int:
    """批量写入/更新资金流向"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            stmt = sqlite_insert(FundFlowModel).values(
                code=str(r["code"]).zfill(6),
                date=pd.to_datetime(r["date"]).to_pydatetime(),
                main_net_inflow=float(r.get("main_net_inflow", 0)),
                super_large_net_inflow=float(r.get("super_large_net_inflow", 0)),
                large_net_inflow=float(r.get("large_net_inflow", 0)),
                medium_net_inflow=float(r.get("medium_net_inflow", 0)),
                small_net_inflow=float(r.get("small_net_inflow", 0)),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "date"],
                set_={
                    "main_net_inflow": stmt.excluded.main_net_inflow,
                    "super_large_net_inflow": stmt.excluded.super_large_net_inflow,
                    "large_net_inflow": stmt.excluded.large_net_inflow,
                    "medium_net_inflow": stmt.excluded.medium_net_inflow,
                    "small_net_inflow": stmt.excluded.small_net_inflow,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def query_fund_flows(code: str, start_date: str | None = None) -> pd.DataFrame:
    with get_session() as session:
        stmt = select(FundFlowModel).where(FundFlowModel.code == code.zfill(6))
        if start_date:
            stmt = stmt.where(FundFlowModel.date >= pd.to_datetime(start_date))
        stmt = stmt.order_by(FundFlowModel.date.asc())
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "code": r.code, "date": r.date,
                "main_net_inflow": r.main_net_inflow,
                "super_large_net_inflow": r.super_large_net_inflow,
                "large_net_inflow": r.large_net_inflow,
                "medium_net_inflow": r.medium_net_inflow,
                "small_net_inflow": r.small_net_inflow,
            }
            for r in rows
        ])


# ─── 财务指标 ───

def upsert_financials(df: pd.DataFrame) -> int:
    """批量写入/更新财务指标"""
    records = df.to_dict(orient="records")
    with get_session() as session:
        for r in records:
            extra_cols = {}
            all_known = {
                "code", "report_date", "net_profit", "revenue", "eps", "roe",
                "total_assets", "total_equity", "gross_margin", "net_margin",
            }
            for k, v in r.items():
                if k not in all_known:
                    extra_cols[k] = v

            stmt = sqlite_insert(FinancialModel).values(
                code=str(r["code"]).zfill(6),
                report_date=pd.to_datetime(r["report_date"]).date(),
                net_profit=float(r.get("net_profit")) if _has_value(r.get("net_profit")) else None,
                revenue=float(r.get("revenue")) if _has_value(r.get("revenue")) else None,
                eps=float(r.get("eps")) if _has_value(r.get("eps")) else None,
                roe=float(r.get("roe")) if _has_value(r.get("roe")) else None,
                total_assets=float(r.get("total_assets")) if _has_value(r.get("total_assets")) else None,
                total_equity=float(r.get("total_equity")) if _has_value(r.get("total_equity")) else None,
                gross_margin=float(r.get("gross_margin")) if _has_value(r.get("gross_margin")) else None,
                net_margin=float(r.get("net_margin")) if _has_value(r.get("net_margin")) else None,
                extra=extra_cols if extra_cols else None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "report_date"],
                set_={
                    "net_profit": stmt.excluded.net_profit,
                    "revenue": stmt.excluded.revenue,
                    "eps": stmt.excluded.eps,
                    "roe": stmt.excluded.roe,
                    "total_assets": stmt.excluded.total_assets,
                    "total_equity": stmt.excluded.total_equity,
                    "gross_margin": stmt.excluded.gross_margin,
                    "net_margin": stmt.excluded.net_margin,
                    "extra": stmt.excluded.extra,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(records)


def query_financials(code: str) -> pd.DataFrame:
    with get_session() as session:
        stmt = (
            select(FinancialModel)
            .where(FinancialModel.code == code.zfill(6))
            .order_by(FinancialModel.report_date.asc())
        )
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "code": r.code, "report_date": r.report_date,
                "net_profit": r.net_profit, "revenue": r.revenue,
                "eps": r.eps, "roe": r.roe,
                "total_assets": r.total_assets, "total_equity": r.total_equity,
                "gross_margin": r.gross_margin, "net_margin": r.net_margin,
            }
            for r in rows
        ])


# ─── 工具函数 ───

def _parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _has_value(val) -> bool:
    if val is None:
        return False
    try:
        return not pd.isna(float(val))
    except (ValueError, TypeError):
        return False


# ─── 实盘跟踪 ───

def create_paper_account(name: str = "模拟账户", initial_capital: float = 10000.0,
                         strategy_key: str | None = None) -> dict:
    """创建模拟账户，返回账户信息"""
    from .models_orm import PaperAccountModel
    with get_session() as session:
        acct = PaperAccountModel(
            name=name, initial_capital=initial_capital,
            cash=initial_capital, strategy_key=strategy_key,
        )
        session.add(acct)
        session.commit()
        return _paper_account_to_dict(acct)


def get_paper_account(account_id: int) -> dict | None:
    from .models_orm import PaperAccountModel
    with get_session() as session:
        acct = session.get(PaperAccountModel, account_id)
        return _paper_account_to_dict(acct) if acct else None


def list_paper_accounts() -> list[dict]:
    from .models_orm import PaperAccountModel
    from sqlalchemy import select
    with get_session() as session:
        rows = session.execute(
            select(PaperAccountModel).order_by(PaperAccountModel.created_at.desc())
        ).scalars().all()
        return [_paper_account_to_dict(r) for r in rows]


def stop_paper_account(account_id: int) -> dict | None:
    from .models_orm import PaperAccountModel
    from datetime import datetime
    with get_session() as session:
        acct = session.get(PaperAccountModel, account_id)
        if not acct:
            return None
        acct.status = "stopped"
        acct.stopped_at = datetime.now()
        session.commit()
        return _paper_account_to_dict(acct)


def upsert_paper_position(account_id: int, code: str, name: str = "",
                          quantity: int = 0, cost_price: float = 0.0,
                          current_price: float = 0.0):
    from .models_orm import PaperPositionModel
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    with get_session() as session:
        stmt = sqlite_insert(PaperPositionModel).values(
            account_id=account_id, code=code.zfill(6), name=name,
            quantity=quantity, cost_price=cost_price, current_price=current_price,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["account_id", "code"],
            set_={
                "name": stmt.excluded.name,
                "quantity": stmt.excluded.quantity,
                "cost_price": stmt.excluded.cost_price,
                "current_price": stmt.excluded.current_price,
                "updated_at": datetime.now(),
            },
        )
        session.execute(stmt)
        session.commit()


def get_paper_positions(account_id: int) -> list[dict]:
    from .models_orm import PaperPositionModel
    from sqlalchemy import select
    with get_session() as session:
        stmt = select(PaperPositionModel).where(
            PaperPositionModel.account_id == account_id,
            PaperPositionModel.quantity > 0,
        )
        rows = session.execute(stmt).scalars().all()
        return [_paper_position_to_dict(r) for r in rows]


def add_paper_trade(account_id: int, code: str, action: str, price: float,
                    quantity: int, amount: float, reason: str = "",
                    confidence: float = 0.0, confirmed: int = 1,
                    trade_date=None) -> dict:
    from .models_orm import PaperTradeModel
    with get_session() as session:
        t = PaperTradeModel(
            account_id=account_id, code=code.zfill(6), action=action,
            price=price, quantity=quantity, amount=amount,
            reason=reason, signal_confidence=confidence, confirmed=confirmed,
            trade_date=trade_date or datetime.now(),
        )
        session.add(t)
        session.commit()
        return _paper_trade_to_dict(t)


def get_paper_trades(account_id: int, limit: int = 100) -> list[dict]:
    from .models_orm import PaperTradeModel
    from sqlalchemy import select
    with get_session() as session:
        stmt = select(PaperTradeModel).where(
            PaperTradeModel.account_id == account_id
        ).order_by(PaperTradeModel.trade_date.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [_paper_trade_to_dict(r) for r in rows]


def save_paper_signal(code: str, signal_type: str, confidence: float,
                      composite_score: float, reason: str, close_price: float,
                      account_id: int | None = None) -> dict:
    from .models_orm import PaperSignalModel
    with get_session() as session:
        s = PaperSignalModel(
            code=code.zfill(6), signal_type=signal_type,
            confidence=confidence, composite_score=composite_score,
            reason=reason, close_price=close_price,
            account_id=account_id,
        )
        session.add(s)
        session.commit()
        return _paper_signal_to_dict(s)


def get_paper_signals(account_id: int | None = None, code: str | None = None,
                      status: str | None = None, limit: int = 50) -> list[dict]:
    from .models_orm import PaperSignalModel
    from sqlalchemy import select
    with get_session() as session:
        stmt = select(PaperSignalModel).order_by(PaperSignalModel.generated_at.desc())
        if account_id:
            stmt = stmt.where(PaperSignalModel.account_id == account_id)
        if code:
            stmt = stmt.where(PaperSignalModel.code == code.zfill(6))
        if status:
            stmt = stmt.where(PaperSignalModel.status == status)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [_paper_signal_to_dict(r) for r in rows]


def update_signal_outcome(signal_id: int, outcome: str, outcome_days: int = 5):
    from .models_orm import PaperSignalModel
    with get_session() as session:
        s = session.get(PaperSignalModel, signal_id)
        if s:
            s.outcome = outcome
            s.outcome_days = outcome_days
            session.commit()


def update_paper_cash(account_id: int, cash: float):
    from .models_orm import PaperAccountModel
    with get_session() as session:
        acct = session.get(PaperAccountModel, account_id)
        if acct:
            acct.cash = cash
            session.commit()


# ─── 内部序列化 ───

def _paper_account_to_dict(a) -> dict:
    return {
        "id": a.id, "name": a.name,
        "initial_capital": a.initial_capital, "cash": a.cash,
        "status": a.status, "strategy_key": a.strategy_key,
        "created_at": a.created_at, "stopped_at": a.stopped_at,
    }


def _paper_position_to_dict(p) -> dict:
    return {
        "id": p.id, "account_id": p.account_id,
        "code": p.code, "name": p.name,
        "quantity": p.quantity, "cost_price": p.cost_price,
        "current_price": p.current_price,
    }


def _paper_trade_to_dict(t) -> dict:
    return {
        "id": t.id, "account_id": t.account_id, "code": t.code,
        "action": t.action, "price": t.price,
        "quantity": t.quantity, "amount": t.amount,
        "reason": t.reason, "signal_confidence": t.signal_confidence,
        "confirmed": t.confirmed, "trade_date": t.trade_date,
    }


def _paper_signal_to_dict(s) -> dict:
    return {
        "id": s.id, "code": s.code, "signal_type": s.signal_type,
        "confidence": s.confidence, "composite_score": s.composite_score,
        "reason": s.reason, "close_price": s.close_price,
        "status": s.status, "account_id": s.account_id,
        "outcome": s.outcome, "outcome_days": s.outcome_days,
        "generated_at": s.generated_at,
    }
