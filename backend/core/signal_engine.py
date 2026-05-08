# -*- coding: utf-8 -*-
# 信号计算引擎：MACD/RSI/MA/量价多周期分析

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import date as DateType


# ─── 指标计算 ───

def calc_ema(series: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period:
        return result
    # 跳过开头的NaN（如DIF前几个值为NaN）
    start = 0
    while start < len(series) - period and np.isnan(series[start]):
        start += 1
    if start + period > len(series):
        return result
    # 用第一个有效窗口的简单均线作为EMA初始值
    window = series[start:start + period]
    valid = window[~np.isnan(window)]
    if len(valid) == 0:
        return result
    result[start + period - 1] = np.mean(valid)
    multiplier = 2.0 / (period + 1)
    for i in range(start + period, len(series)):
        if np.isnan(series[i]):
            result[i] = result[i - 1]
        else:
            result[i] = (series[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    result = np.full_like(close, np.nan, dtype=np.float64)
    if len(close) < period + 1:
        return result
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


def calc_ma(close: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(close, np.nan, dtype=np.float64)
    if len(close) < period:
        return result
    for i in range(period - 1, len(close)):
        result[i] = np.mean(close[i - period + 1 : i + 1])
    return result


def calc_volume_ma(volume: np.ndarray, period: int = 5) -> np.ndarray:
    return calc_ma(volume, period)


# ─── 交叉检测 ───

def detect_golden_cross(fast: np.ndarray, slow: np.ndarray) -> int:
    """检测最近一次金叉位置，无金叉返回-1"""
    if len(fast) < 2 or len(slow) < 2:
        return -1
    for i in range(len(fast) - 1, 0, -1):
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(fast[i - 1]) or np.isnan(slow[i - 1]):
            continue
        if fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]:
            return i
    return -1


def detect_death_cross(fast: np.ndarray, slow: np.ndarray) -> int:
    """检测最近一次死叉位置，无死叉返回-1"""
    if len(fast) < 2 or len(slow) < 2:
        return -1
    for i in range(len(fast) - 1, 0, -1):
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(fast[i - 1]) or np.isnan(slow[i - 1]):
            continue
        if fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]:
            return i
    return -1


def detect_all_crosses(fast: np.ndarray, slow: np.ndarray) -> list[int]:
    """
    检测所有交叉点，返回与输入等长的信号数组。
    1=金叉日, -1=死叉日, 0=无交叉
    """
    n = len(fast)
    result = [0] * n
    if n < 2:
        return result
    for i in range(1, n):
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(fast[i - 1]) or np.isnan(slow[i - 1]):
            continue
        if fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]:
            result[i] = 1      # 金叉
        elif fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]:
            result[i] = -1     # 死叉
    return result


# ─── 信号评分 ───

@dataclass
class PeriodSignal:
    """单周期信号"""
    frequency: str
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
    details: list[str] = field(default_factory=list)

    @property
    def signal_type(self) -> str:
        if self.score > 0.15:
            return "BUY"
        elif self.score < -0.15:
            return "SELL"
        return "HOLD"


@dataclass
class SignalResult:
    """综合信号结果"""
    code: str
    name: str = ""
    signal_type: str = "HOLD"
    confidence: float = 0.0
    reason: str = ""
    composite_score: float = 0.0
    daily: PeriodSignal | None = None
    weekly: PeriodSignal | None = None
    monthly: PeriodSignal | None = None


def analyze_period(df: pd.DataFrame, frequency: str) -> PeriodSignal | None:
    """对单个周期的K线数据做指标分析和评分"""
    if df.empty or len(df) < 30:
        return None

    close = df["close"].values.astype(np.float64)
    volume = df["volume"].values.astype(np.float64)

    sig = PeriodSignal(frequency=frequency)
    details = []

    # MACD
    dif, dea, hist = calc_macd(close)
    sig.macd_dif = float(dif[-1]) if not np.isnan(dif[-1]) else 0.0
    sig.macd_dea = float(dea[-1]) if not np.isnan(dea[-1]) else 0.0

    gc_idx = detect_golden_cross(dif, dea)
    dc_idx = detect_death_cross(dif, dea)

    if gc_idx >= 0 and dc_idx >= 0:
        if gc_idx > dc_idx:
            sig.macd_status = "金叉"
            days_since = len(dif) - 1 - gc_idx
            details.append(f"MACD{days_since}日前金叉")
            sig.score += 0.25
        else:
            sig.macd_status = "死叉"
            days_since = len(dif) - 1 - dc_idx
            details.append(f"MACD{days_since}日前死叉")
            sig.score -= 0.25
    elif gc_idx >= 0:
        sig.macd_status = "金叉"
        days_since = len(dif) - 1 - gc_idx
        details.append(f"MACD{days_since}日前金叉")
        sig.score += 0.25
    elif dc_idx >= 0:
        sig.macd_status = "死叉"
        days_since = len(dif) - 1 - dc_idx
        details.append(f"MACD{days_since}日前死叉")
        sig.score -= 0.25
    else:
        if not np.isnan(dif[-1]) and not np.isnan(dea[-1]):
            if dif[-1] > dea[-1]:
                sig.macd_status = "多头"
            else:
                sig.macd_status = "空头"

    # RSI
    rsi_values = calc_rsi(close, 14)
    sig.rsi_value = float(rsi_values[-1]) if not np.isnan(rsi_values[-1]) else 50.0

    if sig.rsi_value < 20:
        sig.rsi_status = "超卖"
        consecutive = 0
        for i in range(len(rsi_values) - 1, -1, -1):
            if not np.isnan(rsi_values[i]) and rsi_values[i] < 20:
                consecutive += 1
            else:
                break
        details.append(f"RSI超卖{sig.rsi_value:.0f}")
        boost = min(0.2, 0.05 * consecutive)
        sig.score += 0.15 + boost
        if consecutive >= 3:
            details.append(f"RSI连续{consecutive}日超卖，信号增强")
    elif sig.rsi_value > 70:
        sig.rsi_status = "超买"
        consecutive = 0
        for i in range(len(rsi_values) - 1, -1, -1):
            if not np.isnan(rsi_values[i]) and rsi_values[i] > 70:
                consecutive += 1
            else:
                break
        details.append(f"RSI超买{sig.rsi_value:.0f}")
        boost = min(0.2, 0.05 * consecutive)
        sig.score -= 0.15 + boost
    elif sig.rsi_value > 50:
        sig.rsi_status = "偏强"
    elif sig.rsi_value < 50:
        sig.rsi_status = "偏弱"
    else:
        sig.rsi_status = "中性"

    # 均线
    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)

    sig.ma5 = float(ma5[-1]) if not np.isnan(ma5[-1]) else 0.0
    sig.ma10 = float(ma10[-1]) if not np.isnan(ma10[-1]) else 0.0
    sig.ma20 = float(ma20[-1]) if not np.isnan(ma20[-1]) else 0.0
    sig.ma60 = float(ma60[-1]) if not np.isnan(ma60[-1]) else 0.0

    ma_gc_5_20 = detect_golden_cross(ma5, ma20)
    ma_dc_5_20 = detect_death_cross(ma5, ma20)

    if ma_gc_5_20 >= 0 and ma_dc_5_20 >= 0:
        if ma_gc_5_20 > ma_dc_5_20:
            sig.ma_status = "金叉(MA5↑MA20)"
            sig.score += 0.15
            details.append("MA5上穿MA20")
        else:
            sig.ma_status = "死叉(MA5↓MA20)"
            sig.score -= 0.15
            details.append("MA5下穿MA20")
    elif ma_gc_5_20 >= 0:
        sig.ma_status = "金叉(MA5↑MA20)"
        sig.score += 0.15
        details.append("MA5上穿MA20")
    elif ma_dc_5_20 >= 0:
        sig.ma_status = "死叉(MA5↓MA20)"
        sig.score -= 0.15
        details.append("MA5下穿MA20")
    else:
        if not np.isnan(ma5[-1]) and not np.isnan(ma20[-1]):
            if ma5[-1] > ma20[-1]:
                sig.ma_status = "MA5>MA20 多头排列"
            else:
                sig.ma_status = "MA5<MA20 空头排列"

    if not np.isnan(ma10[-1]) and not np.isnan(ma20[-1]):
        if ma10[-1] > ma20[-1] and ma5[-1] > ma10[-1]:
            sig.ma_status = "多头排列"
            sig.score += 0.05

    # 量价
    vol_ma5 = calc_volume_ma(volume, 5)
    avg_vol = np.mean(volume[-5:]) if len(volume) >= 5 else volume[-1]
    if not np.isnan(vol_ma5[-1]) and vol_ma5[-1] > 0:
        ratio = volume[-1] / vol_ma5[-1]
        if ratio > 1.5 and close[-1] > close[-2] if len(close) >= 2 else False:
            sig.volume_status = "放量上涨"
            sig.score += 0.1
            details.append("放量上涨")
        elif ratio > 1.5:
            sig.volume_status = "放量下跌"
            sig.score -= 0.1
        elif ratio < 0.5:
            sig.volume_status = "缩量"
        else:
            sig.volume_status = "量价正常"

    sig.score = max(-1.0, min(1.0, sig.score))
    sig.details = details
    return sig


def resample_to_frequency(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """将日线OHLCV重采样为周线或月线"""
    if df.empty or freq == "D":
        return df.copy()

    freq_map = {"W": "W-FRI", "M": "ME"}
    rule = freq_map.get(freq, freq)
    if "date" not in df.columns:
        return df.copy()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    resampled = df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    resampled["amount"] = 0.0
    resampled["code"] = df["code"].iloc[0] if "code" in df.columns else ""
    resampled["frequency"] = freq
    resampled = resampled.reset_index()
    resampled["date"] = resampled["date"].astype(str)
    return resampled


def generate_signal(df: pd.DataFrame, code: str, name: str = "",
                    daily_weight: float = 0.5, weekly_weight: float = 0.3,
                    monthly_weight: float = 0.2) -> SignalResult:
    """
    主入口：对某个标的的日线数据生成综合信号
    df 列需含: open, high, low, close, volume
    """
    result = SignalResult(code=code, name=name)

    daily_df = df.copy()
    if "date" in daily_df.columns:
        daily_df = daily_df.sort_values("date")

    result.daily = analyze_period(daily_df, "D")
    if result.daily:
        result.daily.weight = daily_weight

    weekly_df = resample_to_frequency(daily_df, "W")
    result.weekly = analyze_period(weekly_df.reset_index(drop=True), "W") if weekly_df is not None else None
    if result.weekly:
        result.weekly.weight = weekly_weight

    monthly_df = resample_to_frequency(daily_df, "M")
    result.monthly = analyze_period(monthly_df.reset_index(drop=True), "M") if monthly_df is not None else None
    if result.monthly:
        result.monthly.weight = monthly_weight

    composite = 0.0
    reason_parts = []
    active_periods = [s for s in [result.daily, result.weekly, result.monthly] if s is not None]

    for s in active_periods:
        composite += s.score * s.weight
        if s.details:
            reason_parts.append(f"{s.frequency}线: {'; '.join(s.details)}")

    result.composite_score = round(composite, 4)

    if result.composite_score > 0.15:
        result.signal_type = "BUY"
    elif result.composite_score < -0.15:
        result.signal_type = "SELL"
    else:
        result.signal_type = "HOLD"

    # 趋势连续性约束：有周线信号时不过度依赖单日波动
    if result.weekly and result.weekly.signal_type == "BUY" and result.signal_type == "SELL":
        result.signal_type = "HOLD"
        reason_parts.insert(0, "周线看多，暂不卖出")
    elif result.weekly and result.weekly.signal_type == "SELL" and result.signal_type == "BUY":
        result.signal_type = "HOLD"
        reason_parts.insert(0, "周线看空，暂不买入")

    result.confidence = abs(result.composite_score) if result.signal_type != "HOLD" else 1.0 - abs(result.composite_score)
    result.confidence = round(min(1.0, max(0.0, result.confidence)), 2)
    result.reason = " | ".join(reason_parts) if reason_parts else "无显著信号"

    return result
