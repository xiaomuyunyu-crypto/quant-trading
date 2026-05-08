# -*- coding: utf-8 -*-
"""
策略组件抽象基类。

借鉴 Hikyuu 的可插拔组件设计：
  System = Signal + Environment + MoneyManager + RiskManager

每个组件独立可测试、可替换。组合起来就是一个完整策略。
"""

from __future__ import division

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import pandas as pd


# ─── 信号输出 ───

@dataclass
class SignalOutput:
    """单个信号组件的输出"""
    signal: str = "HOLD"       # BUY / SELL / HOLD
    confidence: float = 0.0    # 0~1
    reason: str = ""


# ─── 抽象基类 ───

class SignalComponent(ABC):
    """买卖信号生成器"""

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> SignalOutput:
        """输入含有K线+指标的DataFrame（最后一行是当前），返回信号"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class EnvironmentFilter(ABC):
    """市场环境过滤器 —— 判断当前是否适合交易"""

    @abstractmethod
    def is_tradeable(self, df: pd.DataFrame) -> tuple[bool, str]:
        """返回（是否可交易, 理由）"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class MoneyManager(ABC):
    """仓位管理 —— 决定每次交易的资金量"""

    @abstractmethod
    def get_position_pct(self, signal: str, confidence: float, df: pd.DataFrame) -> float:
        """
        返回 0.0~1.0 的目标仓位比例。
        1.0 = 全仓，0.5 = 半仓，0.0 = 不操作
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class RiskManager(ABC):
    """风控 —— 判断是否需要强制平仓"""

    @abstractmethod
    def check(self, entry_price: float, current_price: float, holding_days: int,
              max_drawdown_pct: float) -> tuple[bool, str]:
        """
        返回（是否触发风控, 理由）。
        触发 → 强制卖出
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
