# -*- coding: utf-8 -*-
# 实盘跟踪数据模型

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateAccountRequest(BaseModel):
    """创建模拟账户"""
    name: str = Field(default="模拟账户", description="账户名称")
    initial_capital: float = Field(default=10000.0, ge=1000, description="初始资金")
    strategy_key: Optional[str] = Field(default="composite_majority", description="策略key")


class AccountResponse(BaseModel):
    """账户信息"""
    id: int
    name: str
    initial_capital: float
    cash: float
    status: str
    strategy_key: Optional[str] = None
    created_at: datetime
    stopped_at: Optional[datetime] = None


class PositionResponse(BaseModel):
    """持仓信息"""
    id: int
    account_id: int
    code: str
    name: str
    quantity: int
    cost_price: float
    current_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


class SignalResponse(BaseModel):
    """信号输出"""
    id: int
    code: str
    name: str = ""
    signal_type: str
    confidence: float
    composite_score: float
    reason: str
    close_price: float
    status: str
    generated_at: datetime
    source: Optional[str] = None


class ConfirmSignalRequest(BaseModel):
    """确认/拒绝信号"""
    signal_id: int
    action: str = Field(..., description="confirm 或 reject")


class TradeResponse(BaseModel):
    """交易记录"""
    id: int
    account_id: int
    code: str
    action: str
    price: float
    quantity: int
    amount: float
    reason: str
    signal_confidence: float
    confirmed: int
    trade_date: datetime


class EquityPoint(BaseModel):
    """权益曲线点"""
    date: str
    equity: float


class AccountDetailResponse(BaseModel):
    """账户详情（含持仓+总权益+收益率）"""
    account: AccountResponse
    total_equity: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    positions: list[PositionResponse] = []
    pending_signals: list[SignalResponse] = []
