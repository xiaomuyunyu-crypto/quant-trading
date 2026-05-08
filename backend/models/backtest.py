# -*- coding: utf-8 -*-
# 回测相关数据模型

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BacktestRequest(BaseModel):
    """回测执行请求"""
    code: str = Field(..., description="股票代码")
    strategy: str = Field(default="macd_daily", description="策略类型")
    start_date: Optional[str] = Field(default=None, description="起始日期 YYYYMMDD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYYMMDD")
    days: Optional[int] = Field(default=None, ge=30, le=3650, description="回测天数（与start_date/end_date二选一）")
    initial_capital: float = Field(default=10000.0, ge=10000, description="初始资金")


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
    initial_capital: float
    final_equity: float
    total_return: float
    max_drawdown: float
    total_trades: int
    strategy_name: str
    equity_curve: list[EquityPoint]
    trades: list[TradeItem]
    generated_at: datetime = Field(default_factory=datetime.now)


class StrategyInfo(BaseModel):
    """策略信息"""
    key: str
    name: str
    desc: str
    category: str = ""
    params: dict = Field(default_factory=dict)
