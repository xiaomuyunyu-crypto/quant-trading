# -*- coding: utf-8 -*-
"""
信号组件 —— 可插拔的买卖信号生成器。

每个组件分析一个技术维度，输出 BUY/SELL/HOLD + 置信度。
多个信号组件可以通过 CompositeStrategy 组合使用。
"""

from __future__ import division

import pandas as pd
import numpy as np
from strategy.components.base import SignalComponent, SignalOutput


class MACDCrossSignal(SignalComponent):
    """
    MACD 金叉/死叉信号。

    参数：
        fast/slow/signal: MACD 标准参数
        require_hist_confirm: 金叉时是否需要柱状图>0确认
    """

    def __init__(self, fast=12, slow=26, signal=9, require_hist_confirm=False):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.require_hist_confirm = require_hist_confirm

    @property
    def name(self): return "MACD交叉"

    def analyze(self, df: pd.DataFrame) -> SignalOutput:
        if df.empty or len(df) < 2:
            return SignalOutput()
        row = df.iloc[-1]
        cross = int(row.get("MACD_cross", 0) or 0)
        hist = row.get("MACD_hist", 0) or 0
        dif = row.get("DIF", 0) or 0
        dea = row.get("DEA", 0) or 0

        if cross == 1:
            if self.require_hist_confirm and hist <= 0:
                return SignalOutput(signal="BUY", confidence=0.5,
                                    reason=f"MACD金叉(柱状图未确认) DIF={dif:.4f}")
            return SignalOutput(signal="BUY", confidence=0.8,
                                reason=f"MACD金叉 DIF={dif:.4f} DEA={dea:.4f}")
        elif cross == -1:
            return SignalOutput(signal="SELL", confidence=0.8,
                                reason=f"MACD死叉 DIF={dif:.4f} DEA={dea:.4f}")

        # 无交叉，看方向
        if dif > dea:
            return SignalOutput(signal="BUY", confidence=0.2,
                                reason=f"MACD偏多 DIF={dif:.4f}>DEA={dea:.4f}")
        else:
            return SignalOutput(signal="SELL", confidence=0.2,
                                reason=f"MACD偏空 DIF={dif:.4f}<DEA={dea:.4f}")


class RSISignal(SignalComponent):
    """
    RSI 超买超卖信号。

    规则：
      - 买入：连续3天 RSI<20，或连续2天 RSI<16
      - 卖出：单日 RSI>92，或连续2天 RSI>85
    """

    def __init__(self, oversold=20, overbought=85, consecutive_days=2):
        self.oversold = oversold
        self.overbought = overbought
        self.consecutive_days = consecutive_days

    @property
    def name(self): return "RSI"

    def analyze(self, df: pd.DataFrame) -> SignalOutput:
        if df.empty:
            return SignalOutput()
        row = df.iloc[-1]
        rsi = row.get("RSI", 50) or 50
        oversold_days = int(row.get("RSI_oversold_days", 0) or 0)
        deep_oversold_days = int(row.get("RSI_deep_oversold_days", 0) or 0)
        overbought_days = int(row.get("RSI_overbought_days", 0) or 0)
        extreme_overbought = bool(row.get("RSI_extreme_overbought", False))

        if oversold_days >= 3:
            return SignalOutput(signal="BUY", confidence=0.9,
                                reason=f"RSI连续{oversold_days}天低于20(RSI={rsi:.0f})，观察反转买入")
        elif deep_oversold_days >= 2:
            return SignalOutput(signal="BUY", confidence=0.9,
                                reason=f"RSI连续{deep_oversold_days}天低于16(RSI={rsi:.0f})，深度超卖买入")
        elif extreme_overbought:
            return SignalOutput(signal="SELL", confidence=0.9,
                                reason=f"RSI单日大于92(RSI={rsi:.0f})，极端超买卖出")
        elif overbought_days >= 2:
            return SignalOutput(signal="SELL", confidence=0.9,
                                reason=f"RSI连续{overbought_days}天大于85(RSI={rsi:.0f})，超买卖出")

        return SignalOutput(reason=f"RSI中性({rsi:.0f})")


class MATrendSignal(SignalComponent):
    """
    均线趋势信号。

    检测：
      - 多头排列（MA5>MA10>MA20>MA60，价格在MA5上方）
      - 空头排列（反向）
      - 价格与均线的关系
    """

    def __init__(self):
        pass

    @property
    def name(self): return "均线趋势"

    def analyze(self, df: pd.DataFrame) -> SignalOutput:
        if df.empty:
            return SignalOutput()
        row = df.iloc[-1]
        close = row.get("close", 0) or 0
        ma5 = row.get("MA5", close) or close
        ma10 = row.get("MA10", close) or close
        ma20 = row.get("MA20", close) or close
        ma60 = row.get("MA60", close) or close

        if close == 0:
            return SignalOutput(reason="无价格数据")

        # 多头排列
        if ma5 > ma10 > ma20 > ma60 and close > ma5:
            return SignalOutput(signal="BUY", confidence=0.7,
                                reason="均线多头排列，价格在MA5上方")
        elif ma5 > ma20 and close > ma20:
            return SignalOutput(signal="BUY", confidence=0.4,
                                reason="短期均线在长期上方，价格高于MA20")

        # 空头排列
        if ma5 < ma10 < ma20 < ma60 and close < ma5:
            return SignalOutput(signal="SELL", confidence=0.7,
                                reason="均线空头排列，价格在MA5下方")
        elif ma5 < ma20 and close < ma20:
            return SignalOutput(signal="SELL", confidence=0.4,
                                reason="短期均线在长期下方，价格低于MA20")

        return SignalOutput(reason="均线交织，趋势不明")


class VolumePriceSignal(SignalComponent):
    """
    量价配合信号。

    放量上涨 → 看多；放量下跌 → 看空；缩量→信号弱。
    """

    def __init__(self, vol_ratio_threshold=1.5):
        self.vol_ratio_threshold = vol_ratio_threshold

    @property
    def name(self): return "量价配合"

    def analyze(self, df: pd.DataFrame) -> SignalOutput:
        if df.empty:
            return SignalOutput()
        row = df.iloc[-1]
        vp_score = row.get("vol_price_score", 0) or 0
        vol_ratio = row.get("vol_ratio", 1.0) or 1.0
        diverge = row.get("vol_price_diverge", 0) or 0
        price_up = (row.get("close", 0) or 0) > (row.get("close", 0) or 0)

        if len(df) >= 2:
            price_up = df["close"].iloc[-1] > df["close"].iloc[-2]

        if vp_score > 0 and vol_ratio > self.vol_ratio_threshold:
            return SignalOutput(signal="BUY", confidence=0.5,
                                reason=f"放量上涨(量比{vol_ratio:.1f})，量价配合良好")
        elif vp_score < 0 and vol_ratio > self.vol_ratio_threshold:
            return SignalOutput(signal="SELL", confidence=0.5,
                                reason=f"放量下跌(量比{vol_ratio:.1f})，量价背离")
        elif diverge < 0:
            return SignalOutput(signal="SELL", confidence=0.3,
                                reason="量价趋势背离")

        return SignalOutput(reason="量价正常")
