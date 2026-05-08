# -*- coding: utf-8 -*-
# 数据层内部模型（dataclass，与 backend/models/ 对齐）

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class StockBase:
    """股票基础信息"""
    code: str
    name: str
    exchange: str = "SZ"
    industry: str | None = None
    list_date: date | None = None


@dataclass
class KlineData:
    """K线数据"""
    code: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0
    frequency: str = "D"


@dataclass
class WatchlistItem:
    """自选股条目"""
    code: str
    name: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    added_at: datetime = field(default_factory=datetime.now)
