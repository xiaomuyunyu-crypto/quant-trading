# -*- coding: utf-8 -*-
"""
风控组件 —— 止损、回撤控制等。
"""

from __future__ import division

from strategy.components.base import RiskManager


class NoRiskManager(RiskManager):
    """无风控 —— 不设止损止盈"""

    @property
    def name(self): return "无风控"

    def check(self, entry_price: float, current_price: float, holding_days: int,
              max_drawdown_pct: float) -> tuple[bool, str]:
        return False, ""


class StopLossRisk(RiskManager):
    """
    固定止损 + 最大回撤止损。

    参数：
        stop_loss_pct: 单笔亏损超过此比例 → 止损（如 -0.08 = -8%）
        max_drawdown_pct: 持仓期间最大回撤 → 止损
        min_holding_days: 最短持仓天数（避免开盘就被止损）
    """

    def __init__(self, stop_loss_pct=-0.08, max_drawdown_pct=-0.15, min_holding_days=1):
        self.stop_loss_pct = stop_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.min_holding_days = min_holding_days

    @property
    def name(self): return f"止损({self.stop_loss_pct:.0%})"

    def check(self, entry_price: float, current_price: float, holding_days: int,
              max_drawdown_pct: float) -> tuple[bool, str]:
        if holding_days < self.min_holding_days:
            return False, ""

        current_pnl = (current_price - entry_price) / entry_price

        if current_pnl <= self.stop_loss_pct:
            return True, f"触发止损: 亏损{current_pnl:.2%} >= {self.stop_loss_pct:.2%}"

        if max_drawdown_pct <= self.max_drawdown_pct:
            return True, f"触发回撤止损: 最大回撤{max_drawdown_pct:.2%}"

        return False, ""


class TrailingStopRisk(RiskManager):
    """
    移动止损 —— 从最高点回撤超过一定比例就卖出。

    参数：
        trail_pct: 从持仓期间最高点回撤超过此比例 → 止损（如 -0.05 = -5%）
    """

    def __init__(self, trail_pct=0.05):
        self.trail_pct = trail_pct
        self._highest_price = 0.0

    @property
    def name(self): return f"移动止损({self.trail_pct:.0%})"

    def check(self, entry_price: float, current_price: float, holding_days: int,
              max_drawdown_pct: float) -> tuple[bool, str]:
        self._highest_price = max(self._highest_price, current_price)

        if self._highest_price <= 0:
            return False, ""

        drawdown_from_high = (current_price - self._highest_price) / self._highest_price
        if drawdown_from_high <= -self.trail_pct:
            self._highest_price = 0.0  # 重置
            return True, f"触发移动止损: 从高点{self._highest_price:.2f}回撤{drawdown_from_high:.2%}"

        return False, ""

    def reset(self):
        self._highest_price = 0.0
