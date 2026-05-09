# -*- coding: utf-8 -*-
# 公共数据查询工具 — 供 signals / backtest / paper 共用

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
from data.storage.database import get_session
from data.storage.models_orm import KlineModel
from sqlalchemy import select


DEFAULT_HISTORY_START = "20150101"
LATEST_TOLERANCE_DAYS = 10


@dataclass
class KlineFetchResult:
    """K线查询结果和补数据过程元信息。"""
    code: str
    frequency: str
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    df: pd.DataFrame | None = None
    data_source: str = "empty"
    cache_rows: int = 0
    fetched_rows: int = 0
    actual_start_date: str | None = None
    actual_end_date: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """供 API 响应直接使用的轻量诊断信息。"""
        count = 0 if self.df is None or self.df.empty else len(self.df)
        return {
            "code": self.code,
            "frequency": self.frequency,
            "requested_start_date": self.requested_start_date,
            "requested_end_date": self.requested_end_date,
            "actual_start_date": self.actual_start_date,
            "actual_end_date": self.actual_end_date,
            "data_points": count,
            "data_source": self.data_source,
            "cache_rows": self.cache_rows,
            "fetched_rows": self.fetched_rows,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def get_klines_df(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> pd.DataFrame | None:
    """查询K线数据，保持旧接口兼容。"""
    return get_klines_with_meta(
        code,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
    ).df


def get_klines_with_meta(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    frequency: str = "D",
) -> KlineFetchResult:
    """查询K线数据，优先本地库；日线缺口按需调用AKShare并写回缓存。"""
    lookup_code = _normalize_lookup_code(code)
    requested_start = _to_akshare_date(start_date)
    requested_end = _to_akshare_date(end_date) or datetime.now().strftime("%Y%m%d")

    result = KlineFetchResult(
        code=lookup_code,
        frequency=frequency,
        requested_start_date=requested_start,
        requested_end_date=requested_end,
    )

    df = _query_klines_from_db(lookup_code, requested_start, requested_end, frequency)
    result.df = df
    result.cache_rows = 0 if df is None or df.empty else len(df)
    _fill_actual_range(result)

    needs_refill = _needs_daily_refill(df, requested_start, requested_end, frequency)
    if frequency != "D":
        result.data_source = "cache" if result.cache_rows > 0 else "empty"
        return result

    if not needs_refill:
        result.data_source = "cache" if result.cache_rows > 0 else "empty"
        return result

    try:
        from data.fetcher.akshare_fetcher import fetch_daily_kline
        from data.cleaner.cleaner import clean_kline
        from data.storage.repository import upsert_klines

        fetch_start = _resolve_fetch_start(df, requested_start)
        if not fetch_start:
            fetch_start = DEFAULT_HISTORY_START

        if pd.to_datetime(fetch_start) > pd.to_datetime(requested_end):
            result.data_source = "cache"
            return result

        fetched = fetch_daily_kline(
            lookup_code,
            start_date=fetch_start,
            end_date=requested_end,
        )
        if fetched is None or fetched.empty:
            result.data_source = "cache_stale" if result.cache_rows > 0 else "empty"
            result.warnings.append("AKShare未返回指定区间K线，已返回本地缓存可用部分")
            return result
        cleaned = clean_kline(fetched)
        if cleaned.empty:
            result.data_source = "cache_stale" if result.cache_rows > 0 else "empty"
            result.warnings.append("AKShare返回K线清洗后为空，已返回本地缓存可用部分")
            return result
        upsert_klines(cleaned)
        result.fetched_rows = len(cleaned)
        result.df = _query_klines_from_db(lookup_code, requested_start, requested_end, frequency)
        result.data_source = "akshare+cache" if result.cache_rows > 0 else "akshare"
        _fill_actual_range(result)
        _append_coverage_warnings(result)
        return result
    except Exception as exc:
        result.data_source = "cache_stale" if result.cache_rows > 0 else "empty"
        result.errors.append(str(exc))
        _append_coverage_warnings(result)
        return result


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


def _resolve_fetch_start(df: pd.DataFrame | None, requested_start: str | None) -> str | None:
    """计算AKShare补数据起点：历史缺口用请求起点，最新缺口只补增量。"""
    if requested_start:
        return requested_start
    if df is None or df.empty or "date" not in df.columns:
        return None

    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return (dates.max().to_pydatetime() + timedelta(days=1)).strftime("%Y%m%d")


def _fill_actual_range(result: KlineFetchResult) -> None:
    df = result.df
    if df is None or df.empty or "date" not in df.columns:
        result.actual_start_date = None
        result.actual_end_date = None
        return
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        result.actual_start_date = None
        result.actual_end_date = None
        return
    result.actual_start_date = dates.min().strftime("%Y-%m-%d")
    result.actual_end_date = dates.max().strftime("%Y-%m-%d")


def _append_coverage_warnings(result: KlineFetchResult) -> None:
    if result.df is None or result.df.empty:
        result.warnings.append("本地缓存和AKShare均未取得K线数据")
        return

    dates = pd.to_datetime(result.df["date"], errors="coerce").dropna()
    if dates.empty:
        result.warnings.append("K线日期无法解析")
        return

    if result.requested_start_date:
        target_start = pd.to_datetime(result.requested_start_date)
        if dates.min() > target_start + pd.Timedelta(days=LATEST_TOLERANCE_DAYS):
            result.warnings.append("返回数据起点晚于请求起点，历史窗口未完全补齐")

    if result.requested_end_date:
        target_end = pd.to_datetime(result.requested_end_date)
        if dates.max() < target_end - pd.Timedelta(days=LATEST_TOLERANCE_DAYS):
            result.warnings.append("返回数据终点早于请求终点，最新行情可能未补齐")


def _needs_daily_refill(
    df: pd.DataFrame | None,
    start_date: str | None,
    end_date: str | None,
    frequency: str,
) -> bool:
    """判断本地日线是否只覆盖了请求区间的一部分。"""
    if frequency != "D":
        return False
    if df is None or df.empty:
        return True

    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return True

    first_date = dates.min()
    last_date = dates.max()
    if start_date:
        target_start = pd.to_datetime(start_date)
        if first_date > target_start + pd.Timedelta(days=10):
            return True
    target_end = pd.to_datetime(end_date or datetime.now().strftime("%Y%m%d"))
    if last_date < target_end - pd.Timedelta(days=LATEST_TOLERANCE_DAYS):
        return True
    return False
