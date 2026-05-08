# -*- coding: utf-8 -*-
"""
仓位管理组件。
"""

from __future__ import division

import pandas as pd
from strategy.components.base import MoneyManager


class AllInManager(MoneyManager):
    """全仓进出 —— 每次交易使用100%资金"""

    @property
    def name(self): return "全仓进出"

    def get_position_pct(self, signal: str, confidence: float, df: pd.DataFrame) -> float:
        if signal == "BUY":
            return 1.0
        elif signal == "SELL":
            return 0.0
        return -1.0   # -1 表示不改变当前仓位


class FixedRatioManager(MoneyManager):
    """
    固定比例仓位。

    buy_pct: 买入时使用的资金比例（如0.5=半仓）
    """

    def __init__(self, buy_pct=0.5):
        self.buy_pct = buy_pct

    @property
    def name(self): return f"固定{buy_pct*100:.0f}%仓位"

    def get_position_pct(self, signal: str, confidence: float, df: pd.DataFrame) -> float:
        if signal == "BUY":
            return self.buy_pct
        elif signal == "SELL":
            return 0.0
        return -1.0


class ConfidenceBasedManager(MoneyManager):
    """
    根据信号置信度动态调整仓位。

    strong_conf: 强信号时使用 strong_pct 仓位
    weak_conf: 弱信号时使用 weak_pct 仓位
    """

    def __init__(self, strong_pct=1.0, weak_pct=0.3, strong_threshold=0.7):
        self.strong_pct = strong_pct
        self.weak_pct = weak_pct
        self.strong_threshold = strong_threshold

    @property
    def name(self): return "置信度仓位"

    def get_position_pct(self, signal: str, confidence: float, df: pd.DataFrame) -> float:
        if signal == "BUY":
            if confidence >= self.strong_threshold:
                return self.strong_pct
            return self.weak_pct
        elif signal == "SELL":
            return 0.0
        return -1.0
