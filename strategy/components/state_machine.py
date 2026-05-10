# -*- coding: utf-8 -*-
"""
三周期MACD + 250日均线交易状态机。

层级过滤（从高到低）：
  L1 月线MACD → 最高过滤器，死叉禁止一切买入
  L2 MA250   → 长期趋势边界，线下不允许新开仓
  L3 周线MACD → 控制日线交易窗口开闭
  L4 日线MACD → 执行层，产生实际买卖信号
"""

from __future__ import division

from enum import Enum
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from strategy.indicators import (
    compute_macd, compute_macd_bar_trend,
    resample_to_weekly, resample_to_monthly,
)


class MachineState(Enum):
    MONTHLY_DEAD_CROSS = "月线死叉禁止"
    EMPTY_WAITING = "空仓等待"
    WAITING_ABOVE_MA250 = "等待重新上穿MA250"
    WEEKLY_OPEN = "周线规则开启"
    DAILY_OPEN = "日线交易窗口开启"
    FULL_POSITION = "满仓"
    DAILY_SELL_WAITING = "日线卖出等待"
    FORBIDDEN = "禁止操作"


class TradeAction(Enum):
    BUY_FULL = "BUY"
    SELL_FULL = "SELL"
    HOLD = "HOLD"
    WAIT = "WAIT"


@dataclass
class StateSnapshot:
    state: MachineState
    action: TradeAction
    reason: str = ""
    monthly_macd_status: str = ""
    above_ma250: bool = False
    weekly_window_open: bool = False
    daily_macd_status: str = ""
    in_position: bool = False


def prepare_dataframes(df_daily: pd.DataFrame):
    """日线DataFrame → 三周期带全部指标的DataFrame"""
    from strategy.indicators import compute_all_indicators

    daily = df_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").reset_index(drop=True)
    daily = compute_all_indicators(daily)

    weekly = resample_to_weekly(daily)
    weekly = compute_macd(weekly)
    weekly = compute_macd_bar_trend(weekly)

    monthly = resample_to_monthly(daily)
    monthly = compute_macd(monthly)
    monthly = compute_macd_bar_trend(monthly)

    return daily, weekly, monthly


class TripleMACDStateMachine:
    """三周期MACD+MA250交易状态机，可按策略配置逐级关闭过滤器。"""

    def __init__(
        self,
        daily: pd.DataFrame,
        weekly: pd.DataFrame,
        monthly: pd.DataFrame,
        use_monthly_filter: bool = True,
        use_ma250_filter: bool = True,
        use_weekly_filter: bool = True,
    ):
        self.daily = daily.reset_index(drop=True)
        self.weekly = weekly.reset_index(drop=True)
        self.monthly = monthly.reset_index(drop=True)
        self.state = MachineState.MONTHLY_DEAD_CROSS
        self.in_position = False
        self._weekly_window_open = False
        self._n = len(self.daily)
        self.use_monthly_filter = use_monthly_filter
        self.use_ma250_filter = use_ma250_filter
        self.use_weekly_filter = use_weekly_filter

    def run(self) -> tuple[list[str], list[dict]]:
        """逐日运行，返回 (信号列表, 状态历史)"""
        signals = ["HOLD"] * self._n
        history = []

        for i in range(self._n):
            d_row = self.daily.iloc[i]
            date_str = str(d_row.get("date", ""))[:10]
            w_row = self._find_tf_row(self.weekly, d_row)
            m_row = self._find_tf_row(self.monthly, d_row)
            snap = self._step(d_row, w_row, m_row)
            history.append({
                "date": date_str,
                "state": snap.state.value,
                "signal": snap.action.value,
                "reason": snap.reason,
                "monthly_macd": snap.monthly_macd_status,
                "above_ma250": snap.above_ma250,
                "weekly_window": snap.weekly_window_open,
                "daily_macd": snap.daily_macd_status,
                "in_position": snap.in_position,
            })
            signals[i] = snap.action.value
        return signals, history

    def _step(self, d, w, m) -> StateSnapshot:
        # ── L1: 月线 ──
        if self.use_monthly_filter:
            m_status = "多头" if self._macd_bullish(m) else "空头"
            m_cross = self._safe_int(m.get("MACD_cross", 0))

            if m_cross == -1 or m_status == "空头":
                if self.in_position:
                    self.in_position = False
                    self.state = MachineState.MONTHLY_DEAD_CROSS
                    return StateSnapshot(self.state, TradeAction.SELL_FULL,
                        reason="月线MACD死叉/空头，强制平仓",
                        monthly_macd_status="死叉" if m_cross == -1 else "空头",
                        above_ma250=self._above_ma250(d))
                self.state = MachineState.MONTHLY_DEAD_CROSS
                return StateSnapshot(self.state, TradeAction.HOLD,
                    reason="月线MACD空头，禁止一切买入",
                    monthly_macd_status="死叉" if m_cross == -1 else "空头",
                    above_ma250=self._above_ma250(d))

            m_label = "金叉" if m_status == "多头" else "维持金叉"
        else:
            m_label = "月线未启用"

        # ── L2: MA250 ──
        above = True
        if self.use_ma250_filter:
            above = self._above_ma250(d)
            if not above:
                if self.in_position:
                    self.in_position = False
                    self.state = MachineState.WAITING_ABOVE_MA250
                    return StateSnapshot(self.state, TradeAction.SELL_FULL,
                        reason="价格跌破MA250，平仓等待",
                        monthly_macd_status=m_label, above_ma250=False)
                self.state = MachineState.WAITING_ABOVE_MA250
                return StateSnapshot(self.state, TradeAction.HOLD,
                    reason="价格在MA250下方，等待重新上穿",
                    monthly_macd_status=m_label, above_ma250=False)

        # ── L3: 周线窗口 ──
        if self.use_weekly_filter:
            self._weekly_window_open = self._eval_weekly(w)
            if not self._weekly_window_open:
                self.state = MachineState.EMPTY_WAITING
                return StateSnapshot(self.state, TradeAction.HOLD,
                    reason="等待周线交易窗口开启",
                    monthly_macd_status=m_label, above_ma250=above,
                    weekly_window_open=False, in_position=self.in_position)
        else:
            self._weekly_window_open = True

        # ── L4: 日线执行 ──
        d_status = "多头" if self._macd_bullish(d) else "空头"
        buy_signal = self._daily_buy_signal(d)
        sell_signal = self._daily_sell_signal(d)
        buy_context = self._buy_context(m_label)

        if not self.in_position:
            if buy_signal:
                self.in_position = True
                self.state = MachineState.FULL_POSITION
                return StateSnapshot(self.state, TradeAction.BUY_FULL,
                    reason=f"{buy_signal}（{buy_context}），全仓买入",
                    monthly_macd_status=m_label, above_ma250=above,
                    weekly_window_open=True, daily_macd_status=buy_signal, in_position=True)
            self.state = MachineState.DAILY_OPEN
            return StateSnapshot(self.state, TradeAction.HOLD,
                reason="日线交易窗口开启，等待日线MACD买入信号",
                monthly_macd_status=m_label, above_ma250=above,
                weekly_window_open=True, daily_macd_status=d_status)
        else:
            if sell_signal:
                self.in_position = False
                self.state = MachineState.DAILY_SELL_WAITING
                return StateSnapshot(self.state, TradeAction.SELL_FULL,
                    reason=f"{sell_signal}，卖出",
                    monthly_macd_status=m_label, above_ma250=above,
                    weekly_window_open=True, daily_macd_status=sell_signal, in_position=False)
            self.state = MachineState.FULL_POSITION
            return StateSnapshot(self.state, TradeAction.HOLD,
                reason="持仓中，等待卖出信号",
                monthly_macd_status=m_label, above_ma250=above,
                weekly_window_open=True, daily_macd_status=d_status, in_position=True)

    # ── 辅助 ──

    def _macd_bullish(self, row) -> bool:
        dif = row.get("DIF") or 0
        dea = row.get("DEA") or 0
        if pd.isna(dif) or pd.isna(dea):
            return False
        return float(dif) > float(dea)

    def _above_ma250(self, d) -> bool:
        c = d.get("close") or 0
        m = d.get("MA250") or 0
        if pd.isna(m) or m <= 0:
            return False
        return float(c) > float(m)

    def _find_tf_row(self, tf_df: pd.DataFrame, daily_row) -> pd.Series:
        dd = pd.to_datetime(daily_row.get("date"))
        df = tf_df.copy()
        if "date" not in df.columns:
            return daily_row
        df["_dt"] = pd.to_datetime(df["date"])
        mask = df["_dt"] <= dd
        if not mask.any():
            return df.iloc[0]
        return df[mask].iloc[-1]

    def _eval_weekly(self, w) -> bool:
        """周线窗口：绿柱缩短1次→开 / 红柱增长≥2次→开 / 红柱缩短1次→关 / 死叉→关"""
        cross = self._safe_int(w.get("MACD_cross", 0))
        if cross == -1:
            return False
        if bool(w.get("MACD_red_shrink", False)):
            return False
        if bool(w.get("MACD_green_shrink", False)):
            return True
        grow = self._safe_int(w.get("MACD_red_grow_consecutive", 0))
        if grow >= 2:
            return True
        return self._weekly_window_open

    def _daily_buy_signal(self, d) -> str:
        """日线买入：金叉 / 绿柱连续缩短3次 / 当前绿柱段累计缩短4次。"""
        cross = self._safe_int(d.get("MACD_cross", 0))
        if cross == 1:
            return "日线MACD金叉"
        green_consecutive = self._safe_int(d.get("MACD_green_shrink_consecutive", 0))
        if green_consecutive >= 3:
            return "日线MACD绿柱连续缩短3次"
        green_total = self._safe_int(d.get("MACD_green_shrink_segment_total", 0))
        if green_total >= 4:
            return "日线MACD绿柱累计缩短4次"
        return ""

    def _daily_sell_signal(self, d) -> str:
        """日线卖出：死叉 / 红柱连续缩短2次 / 当前红柱段累计缩短3次。"""
        cross = self._safe_int(d.get("MACD_cross", 0))
        if cross == -1:
            return "日线MACD死叉"
        red_consecutive = self._safe_int(d.get("MACD_red_shrink_consecutive", 0))
        if red_consecutive >= 2:
            return "日线MACD红柱连续缩短2次"
        red_total = self._safe_int(d.get("MACD_red_shrink_segment_total", 0))
        if red_total >= 3:
            return "日线MACD红柱累计缩短3次"
        return ""

    def _buy_context(self, monthly_label: str) -> str:
        parts = []
        if self.use_monthly_filter:
            parts.append(monthly_label)
        if self.use_ma250_filter:
            parts.append("MA250上方")
        if self.use_weekly_filter:
            parts.append("周线窗口开启")
        return "+".join(parts) if parts else "无上层过滤"

    def _safe_int(self, value) -> int:
        if pd.isna(value):
            return 0
        return int(value or 0)
