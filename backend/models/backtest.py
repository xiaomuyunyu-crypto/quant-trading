# -*- coding: utf-8 -*-
# 回测相关数据模型

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class BacktestRequest(BaseModel):
    """回测执行请求"""
    code: str = Field(..., description="股票代码")
    strategy: str = Field(default="macd_daily", description="策略类型")
    start_date: Optional[str] = Field(default=None, description="起始日期 YYYYMMDD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYYMMDD")
    days: Optional[int] = Field(default=None, ge=30, le=15000, description="回测天数（与start_date/end_date二选一）")
    full_history: bool = Field(default=False, description="是否从数据源可获取的最早上市日期开始回测")
    initial_capital: float = Field(default=10000.0, ge=10000, description="初始资金")
    bypass_cache: bool = Field(default=True, description="是否跳过本地数据库缓存，直连AKShare获取K线")


class TradeItem(BaseModel):
    """单笔交易记录"""
    date: str
    code: str
    action: str
    price: float
    shares: int = 0
    amount: float = 0.0
    reason: str = ""


class EquityPoint(BaseModel):
    """权益曲线点"""
    date: str
    equity: float
    signal: str = ""   # BUY / SELL / "" — 前端用来标记买卖点


class BacktestResultModel(BaseModel):
    """回测结果"""
    code: str
    start_date: str
    end_date: str
    requested_start_date: Optional[str] = None
    requested_end_date: Optional[str] = None
    data_source: str = ""
    data_points: int = 0
    actual_data_start_date: Optional[str] = None
    actual_data_end_date: Optional[str] = None
    initial_capital: float
    final_equity: float
    total_return: float
    max_drawdown: float
    total_trades: int
    strategy_name: str
    equity_curve: list[EquityPoint]
    trades: list[TradeItem]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class StrategyInfo(BaseModel):
    """策略信息"""
    key: str
    name: str
    desc: str
    category: str = ""
    params: dict = Field(default_factory=dict)
