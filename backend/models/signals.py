# -*- coding: utf-8 -*-
# 信号系统数据模型

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PeriodSignalDetail(BaseModel):
    """单周期信号详情"""
    frequency: str = "D"
    score: float = 0.0
    weight: float = 0.5
    macd_status: str = ""
    macd_dif: float = 0.0
    macd_dea: float = 0.0
    rsi_value: float = 50.0
    rsi_status: str = ""
    ma_status: str = ""
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    volume_status: str = ""
    details: list[str] = []


class SignalResultModel(BaseModel):
    """综合信号结果"""
    code: str
    name: str = ""
    signal_type: str = "HOLD"
    confidence: float = 0.0
    reason: str = ""
    composite_score: float = 0.0
    daily: Optional[PeriodSignalDetail] = None
    weekly: Optional[PeriodSignalDetail] = None
    monthly: Optional[PeriodSignalDetail] = None
    generated_at: datetime = Field(default_factory=datetime.now)


class SignalWeights(BaseModel):
    """信号权重配置"""
    daily_weight: float = Field(default=0.5, ge=0, le=1, description="日线权重")
    weekly_weight: float = Field(default=0.3, ge=0, le=1, description="周线权重")
    monthly_weight: float = Field(default=0.2, ge=0, le=1, description="月线权重")


class SignalQuery(BaseModel):
    """信号查询参数"""
    code: Optional[str] = Field(default=None, description="股票代码")
    signal_type: Optional[str] = Field(default=None, description="BUY/SELL/HOLD")
