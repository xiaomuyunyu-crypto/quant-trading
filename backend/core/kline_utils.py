# -*- coding: utf-8 -*-
# 公共数据查询工具 — 供 signals / backtest / paper 共用

import pandas as pd
from data.storage.database import get_session
from data.storage.models_orm import KlineModel
from sqlalchemy import select


def get_klines_df(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> pd.DataFrame | None:
    """查询K线数据，优先本地库；日线缺失时用AKShare快速兜底并写回缓存。"""
    lookup_code = _normalize_lookup_code(code)
    df = _query_klines_from_db(lookup_code, start_date, end_date, frequency)
    if df is not None and not df.empty:
        return df

    if frequency != "D":
        return None

    try:
        from data.fetcher.akshare_fetcher import fetch_daily_kline
        from data.storage.repository import upsert_klines

        fetched = fetch_daily_kline(
            lookup_code,
            start_date=_to_akshare_date(start_date),
            end_date=_to_akshare_date(end_date),
        )
        if fetched is None or fetched.empty:
            return None
        upsert_klines(fetched)
        return _query_klines_from_db(lookup_code, start_date, end_date, frequency)
    except Exception:
        return None


def _query_klines_from_db(
    lookup_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> pd.DataFrame | None:
    """从数据库查询K线数据，返回DataFrame。未查到数据返回None。"""
    with get_session() as session:
        stmt = select(KlineModel).where(
            KlineModel.code == lookup_code,
            KlineModel.frequency == frequency,
        ).order_by(KlineModel.date.asc())

        if start_date:
            stmt = stmt.where(KlineModel.date >= pd.to_datetime(start_date))
        if end_date:
            stmt = stmt.where(KlineModel.date <= pd.to_datetime(end_date))

        rows = session.execute(stmt).scalars().all()
        if not rows:
            return None

        data = [{
            "code": r.code, "date": r.date, "open": r.open,
            "high": r.high, "low": r.low, "close": r.close,
            "volume": r.volume, "amount": r.amount, "frequency": r.frequency,
        } for r in rows]
        return pd.DataFrame(data)


def _normalize_lookup_code(code: str) -> str:
    """A股/ETF数字代码补零到6位，港股5位和美股字母保持原样。"""
    value = str(code or "").strip()
    if value.isdigit() and len(value) < 5:
        return value.zfill(6)
    return value


def _to_akshare_date(value: str | None) -> str | None:
    if not value:
        return None
    return pd.to_datetime(value).strftime("%Y%m%d")
