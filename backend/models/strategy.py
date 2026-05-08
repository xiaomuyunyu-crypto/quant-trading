# -*- coding: utf-8 -*-
# 策略相关数据模型

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class StrategyConfig(BaseModel):
    """策略配置"""
    id: Optional[str] = Field(default=None, description="策略唯一ID")
    name: str = Field(..., description="策略名称")
    description: str = Field(default="", description="策略描述")
    params: dict[str, Any] = Field(default_factory=dict, description="策略参数")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class StrategySignal(BaseModel):
    """策略交易信号"""
    strategy_id: str = Field(..., description="策略ID")
    code: str = Field(..., description="股票代码")
    signal_type: str = Field(..., description="信号类型 BUY/SELL/HOLD")
    price: float = Field(default=0, description="建议价格")
    reason: str = Field(default="", description="信号理由")
    confidence: float = Field(default=1.0, ge=0, le=1, description="置信度 0-1")
    timestamp: datetime = Field(default_factory=datetime.now)
