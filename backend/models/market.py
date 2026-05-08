# -*- coding: utf-8 -*-
# 行情数据模型

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class KlineData(BaseModel):
    """K线数据"""
    code: str = Field(..., description="股票代码")
    date: datetime = Field(..., description="交易日期")
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(default=0, description="成交量")
    amount: float = Field(default=0, description="成交额")
    frequency: str = Field(default="D", description="周期 D/W/M/5m/15m/60m")


class RealtimeQuote(BaseModel):
    """实时行情快照（如数据源支持）"""
    code: str
    name: str
    current: float = Field(..., description="当前价")
    change: float = Field(default=0, description="涨跌额")
    change_pct: float = Field(default=0, description="涨跌幅%")
    volume: float = Field(default=0)
    amount: float = Field(default=0)
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    pre_close: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)
