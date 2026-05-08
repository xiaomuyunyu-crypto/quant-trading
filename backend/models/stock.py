# -*- coding: utf-8 -*-
# 股票相关数据模型

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class StockBase(BaseModel):
    """股票基础信息"""
    code: str = Field(..., description="股票代码，如 000001")
    name: str = Field(..., description="股票名称")
    exchange: str = Field(default="SZ", description="交易所 SZ/SH/BJ")
    industry: Optional[str] = Field(default=None, description="所属行业")
    list_date: Optional[date] = Field(default=None, description="上市日期")


class StockDetail(StockBase):
    """股票详细信息（含自选股标记）"""
    is_watchlist: bool = Field(default=False, description="是否在自选股中")
    tags: list[str] = Field(default_factory=list, description="自选股分组标签")
    notes: Optional[str] = Field(default=None, description="用户备注")


class StockList(BaseModel):
    """股票列表响应"""
    total: int
    items: list[StockDetail]
