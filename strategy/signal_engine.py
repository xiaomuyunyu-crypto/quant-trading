# -*- coding: utf-8 -*-
"""
多周期信号引擎 v2。

改为"触发+确认"模式：
  - 触发：MACD 金叉/死叉 或 RSI 极端值 作为主事件
  - 确认：MA排列、量价配合 用来加减置信度
  - 多周期：日/周/月线各判断→取多数意见
  - 防反复：信号翻转需持续性证据

用法：
    engine = SignalEngine()
    signals = engine.run_on_code("000001", "2024-01-01", "2026-05-07")
"""

from __future__ import division

from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from strategy.indicators import (
    compute_ma, compute_macd, compute_rsi, compute_volume_price,
    resample_to_weekly, resample_to_monthly,
)


@dataclass
class TimeframeSignal:
    """单个周期的判断"""
    macd_signal: str = "HOLD"      # BUY / SELL / HOLD
    macd_cross: int = 0            # 1=金叉 -1=死叉 0=无
    rsi_state: str = "neutral"     # oversold / neutral / overbought
    rsi_value: float = 50.0
    ma_bullish: bool = False       # 均线多头排列
    vol_confirm: bool = False      # 量价配合确认
    score: float = 0.0             # 本周期综合得分


@dataclass
class SignalResult:
    """最终信号"""
    code: str
    date: str
    signal: str = "HOLD"
    confidence: float = 0.0
    strength: str = "neutral"
    daily: TimeframeSignal = field(default_factory=TimeframeSignal)
    weekly: TimeframeSignal = field(default_factory=TimeframeSignal)
    monthly: TimeframeSignal = field(default_factory=TimeframeSignal)
    reason: str = ""


class SignalEngine:
    """
    多周期信号引擎 v2 —— 触发+确认模式。

    参数：
        rsi_oversold/rsi_overbought: 保留兼容参数；当前RSI采用极端值+连续天数规则
        confirm_required: 需要几个周期确认才触发信号（1-3，默认2）
        anti_flicker_window: 防反复窗口
    """

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        confirm_required: int = 1,
        anti_flicker_window: int = 3,
    ):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.confirm_required = confirm_required
        self.anti_flicker_window = anti_flicker_window
        self._signal_history: list[dict] = []

    # ─── 数据准备 ───

    def prepare_data(self, df_daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
        df = df_daily.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = compute_ma(df)
        df = compute_macd(df)
        df = compute_rsi(df)
        df = compute_volume_price(df)

        w = resample_to_weekly(df)
        w = compute_ma(w); w = compute_macd(w); w = compute_rsi(w); w = compute_volume_price(w)

        m = resample_to_monthly(df)
        m = compute_ma(m); m = compute_macd(m); m = compute_rsi(m); m = compute_volume_price(m)

        return {"daily": df, "weekly": w, "monthly": m}

    # ─── 单周期分析 ───

    def _analyze_timeframe(self, df: pd.DataFrame) -> TimeframeSignal:
        """分析单个周期的最后一根K线"""
        if df.empty:
            return TimeframeSignal()
        row = df.iloc[-1]

        ts = TimeframeSignal()

        # 1) MACD 交叉
        cross = int(row.get("MACD_cross", 0) or 0)
        ts.macd_cross = cross
        dif = row.get("DIF", 0) or 0
        dea = row.get("DEA", 0) or 0
        if cross == 1:
            ts.macd_signal = "BUY"
        elif cross == -1:
            ts.macd_signal = "SELL"
        elif dif > dea:
            ts.macd_signal = "BUY"       # DIF在DEA上方=偏多
        else:
            ts.macd_signal = "SELL"

        # 2) RSI
        rsi = row.get("RSI", 50) or 50
        ts.rsi_value = float(rsi)
        oversold_days = int(row.get("RSI_oversold_days", 0) or 0)
        deep_oversold_days = int(row.get("RSI_deep_oversold_days", 0) or 0)
        overbought_days = int(row.get("RSI_overbought_days", 0) or 0)
        extreme_overbought = bool(row.get("RSI_extreme_overbought", False))
        rsi_buy_signal = oversold_days >= 3 or deep_oversold_days >= 2
        rsi_sell_signal = extreme_overbought or overbought_days >= 2
        if rsi_buy_signal:
            ts.rsi_state = "oversold"
        elif rsi_sell_signal:
            ts.rsi_state = "overbought"
        else:
            ts.rsi_state = "neutral"

        # 3) 均线排列
        ma5 = row.get("MA5", 0) or 0
        ma10 = row.get("MA10", 0) or 0
        ma20 = row.get("MA20", 0) or 0
        ma60 = row.get("MA60", 0) or 0
        close = row.get("close", 0) or 0
        ts.ma_bullish = (ma5 > ma10 > ma20 > ma60 and close > ma5)

        # 4) 量价确认
        vp_score = row.get("vol_price_score", 0) or 0
        vol_ratio = row.get("vol_ratio", 1.0) or 1.0
        ts.vol_confirm = (vp_score > 0 or vol_ratio > 1.5)

        # 5) 综合得分
        score = 0.0
        if cross == 1:
            score = 0.6
        elif cross == -1:
            score = -0.6
        elif dif > dea:
            score = 0.15
        else:
            score = -0.15

        if rsi_buy_signal:
            score += 0.25
        elif rsi_sell_signal:
            score -= 0.25

        if ts.ma_bullish:
            score += 0.1
        elif ma5 < ma20 and close < ma20:
            score -= 0.1

        if ts.vol_confirm:
            score += 0.05

        ts.score = round(max(-1.0, min(1.0, score)), 4)
        return ts

    # ─── 汇总三周期 → 最终信号 ───

    def _decide(self, daily: TimeframeSignal, weekly: TimeframeSignal, monthly: TimeframeSignal) -> SignalResult:
        """三个周期的判断汇总为一个最终信号"""

        # 收集各周期的投票
        votes = []
        for ts, label in [(daily, "日线"), (weekly, "周线"), (monthly, "月线")]:
            if ts.macd_cross == 1:
                votes.append(("BUY", 2.0, f"{label}MACD金叉"))
            elif ts.macd_cross == -1:
                votes.append(("SELL", 2.0, f"{label}MACD死叉"))
            elif ts.macd_signal == "BUY" and ts.rsi_state == "oversold":
                votes.append(("BUY", 1.5, f"{label}MACD偏多+RSI超卖"))
            elif ts.macd_signal == "SELL" and ts.rsi_state == "overbought":
                votes.append(("SELL", 1.5, f"{label}MACD偏空+RSI超买"))
            elif ts.rsi_state == "oversold":
                votes.append(("BUY", 1.0, f"{label}RSI超卖({ts.rsi_value:.0f})"))
            elif ts.rsi_state == "overbought":
                votes.append(("SELL", 1.0, f"{label}RSI超买({ts.rsi_value:.0f})"))

        if not votes:
            return SignalResult(
                code="", date="", signal="HOLD", confidence=0.0, strength="neutral",
                daily=daily, weekly=weekly, monthly=monthly,
                reason="三周期均无明确信号",
            )

        buy_votes = [(d, w) for d, w, r in votes if d == "BUY"]
        sell_votes = [(d, w) for d, w, r in votes if d == "SELL"]

        buy_weight = sum(w for _, w in buy_votes)
        sell_weight = sum(w for _, w in sell_votes)
        reasons = [r for _, _, r in votes]

        # 信号方向和强度
        if buy_weight > sell_weight and len(buy_votes) >= self.confirm_required:
            signal = "BUY"
            net_weight = buy_weight - sell_weight
        elif sell_weight > buy_weight and len(sell_votes) >= self.confirm_required:
            signal = "SELL"
            net_weight = sell_weight - buy_weight
        else:
            signal = "HOLD"
            net_weight = abs(buy_weight - sell_weight)

        signal = self._anti_flicker(signal, buy_weight - sell_weight)

        confidence = min(1.0, net_weight / 4.0)
        if net_weight >= 3.0:
            strength = "strong"
        elif net_weight >= 1.5:
            strength = "weak"
        else:
            strength = "neutral"

        # 更新历史
        self._signal_history.append({"signal": signal, "net": buy_weight - sell_weight})
        if len(self._signal_history) > 50:
            self._signal_history = self._signal_history[-50:]

        return SignalResult(
            code="", date="", signal=signal,
            confidence=round(confidence, 4), strength=strength,
            daily=daily, weekly=weekly, monthly=monthly,
            reason="；".join(reasons) if reasons else "无信号",
        )

    def _anti_flicker(self, current_signal: str, net_weight: float) -> str:
        """防止信号反复横跳"""
        if len(self._signal_history) < self.anti_flicker_window:
            return current_signal
        recent = self._signal_history[-self.anti_flicker_window:]
        recent_signals = [s["signal"] for s in recent]
        if current_signal == "HOLD":
            return current_signal
        if all(s == recent_signals[0] for s in recent_signals) and current_signal != recent_signals[0]:
            if abs(net_weight) < 2.0:
                return recent_signals[0]
        return current_signal

    # ─── 主入口 ───

    def analyze(self, data: dict[str, pd.DataFrame], code: str = "") -> SignalResult:
        daily = self._analyze_timeframe(data.get("daily", pd.DataFrame()))
        weekly = self._analyze_timeframe(data.get("weekly", pd.DataFrame()))
        monthly = self._analyze_timeframe(data.get("monthly", pd.DataFrame()))

        result = self._decide(daily, weekly, monthly)
        result.code = code
        result.daily = daily
        result.weekly = weekly
        result.monthly = monthly

        daily_df = data.get("daily", pd.DataFrame())
        if not daily_df.empty:
            result.date = str(daily_df["date"].iloc[-1])[:10]

        return result

    def run_on_code(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        对单个标的逐日滚动生成信号历史。
        返回 DataFrame，列=[date, signal, confidence, strength, reason, ...]
        """
        import sys
        sys.path.insert(0, ".")
        from data.storage.repository import query_klines

        klines = query_klines(code, start_date=start_date, end_date=end_date)
        if klines.empty:
            return pd.DataFrame()

        klines["date"] = pd.to_datetime(klines["date"])
        klines = klines.sort_values("date").reset_index(drop=True)

        min_bars = 60
        if len(klines) < min_bars:
            return pd.DataFrame()

        self._signal_history = []
        results = []
        for i in range(min_bars, len(klines) + 1):
            window = klines.iloc[:i].copy()
            try:
                data = self.prepare_data(window)
                result = self.analyze(data, code=code)
                results.append({
                    "date": result.date,
                    "signal": result.signal,
                    "confidence": result.confidence,
                    "strength": result.strength,
                    "daily_macd": result.daily.macd_signal,
                    "daily_rsi": result.daily.rsi_state,
                    "daily_ma_bullish": result.daily.ma_bullish,
                    "weekly_macd": result.weekly.macd_signal,
                    "monthly_macd": result.monthly.macd_signal,
                    "reason": result.reason,
                })
            except Exception:
                continue

        return pd.DataFrame(results)
