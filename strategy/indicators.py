# -*- coding: utf-8 -*-
# 技术指标计算模块
# 支持日线/周线/月线三个周期，实现 MACD / RSI / MA / 量价分析

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class IndicatorResult:
    """单个标的的多周期指标计算结果"""
    code: str
    daily: pd.DataFrame    # 日线指标（在原K线基础上追加指标列）
    weekly: pd.DataFrame   # 周线指标
    monthly: pd.DataFrame  # 月线指标


# ─── 周期转换 ───

def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线（前向复权，以周五为周收盘）"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    weekly = df.resample("W").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
    })
    weekly = weekly.dropna().reset_index()
    weekly["code"] = df["code"].iloc[0] if "code" in df.columns else ""
    weekly["frequency"] = "W"
    return weekly


def resample_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """日线 → 月线"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    monthly = df.resample("ME").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
    })
    monthly = monthly.dropna().reset_index()
    monthly["code"] = df["code"].iloc[0] if "code" in df.columns else ""
    monthly["frequency"] = "M"
    return monthly


# ─── 均线 MA ───

def compute_ma(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """计算多周期均线，追加 MA{N} 列"""
    if periods is None:
        periods = [5, 10, 20, 60]
    df = df.copy()
    for p in periods:
        df[f"MA{p}"] = df["close"].rolling(window=p).mean()
    df["MA5_slope"] = df["MA5"].diff(3)          # 3日斜率
    df["MA20_slope"] = df["MA20"].diff(5)
    return df


# ─── MACD ───

def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算 MACD，追加 DIF / DEA / MACD_hist 列"""
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["DIF"] = ema_fast - ema_slow
    df["DEA"] = df["DIF"].ewm(span=signal, adjust=False).mean()
    df["MACD_hist"] = 2 * (df["DIF"] - df["DEA"])

    # 金叉/死叉标记
    df["MACD_cross"] = 0
    cross_up = (df["DIF"] > df["DEA"]) & (df["DIF"].shift(1) <= df["DEA"].shift(1))
    cross_down = (df["DIF"] < df["DEA"]) & (df["DIF"].shift(1) >= df["DEA"].shift(1))
    df.loc[cross_up, "MACD_cross"] = 1       # 金叉
    df.loc[cross_down, "MACD_cross"] = -1    # 死叉

    # DIF 方向（连续N天朝哪个方向走）
    df["DIF_direction"] = np.sign(df["DIF"].diff(3)).fillna(0)
    return df


# ─── RSI ───

def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算 RSI，追加 RSI 列"""
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100.0 - (100.0 / (1.0 + rs))

    # RSI 连续超卖/超买天数
    df["RSI_oversold_days"] = (df["RSI"] < 30).astype(int).rolling(window=5, min_periods=1).sum()
    df["RSI_overbought_days"] = (df["RSI"] > 70).astype(int).rolling(window=5, min_periods=1).sum()
    return df


# ─── 量价分析 ───

def compute_volume_price(df: pd.DataFrame) -> pd.DataFrame:
    """量价配合分析，追加 vol_* 列"""
    df = df.copy()

    # 成交量均线
    df["vol_MA5"] = df["volume"].rolling(5).mean()
    df["vol_MA20"] = df["volume"].rolling(20).mean()

    # 放量倍数
    df["vol_ratio"] = df["volume"] / df["vol_MA20"].replace(0, np.nan)

    # 量价配合：上涨放量 = +1，上涨缩量 = -1，下跌放量 = -1，下跌缩量 = +1
    price_up = df["close"] > df["close"].shift(1)
    vol_up = df["volume"] > df["vol_MA20"]
    df["vol_price_score"] = 0
    df.loc[price_up & vol_up, "vol_price_score"] = 1       # 价涨量增 → 健康
    df.loc[price_up & ~vol_up, "vol_price_score"] = -1     # 价涨量缩 → 背离
    df.loc[~price_up & vol_up, "vol_price_score"] = -1     # 价跌量增 → 危险
    df.loc[~price_up & ~vol_up, "vol_price_score"] = 1     # 价跌量缩 → 企稳

    # 量价趋势一致性（滚动窗口）
    df["price_trend"] = df["close"].pct_change(5)
    df["vol_trend"] = df["volume"].pct_change(5)
    df["vol_price_diverge"] = 0
    df.loc[(df["price_trend"] > 0) & (df["vol_trend"] < 0), "vol_price_diverge"] = -1
    df.loc[(df["price_trend"] < 0) & (df["vol_trend"] > 0), "vol_price_diverge"] = -1
    df.loc[(df["price_trend"] > 0) & (df["vol_trend"] > 0), "vol_price_diverge"] = 1

    return df


# ─── 批量计算 ───

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """对单周期 DataFrame 计算全部四个指标，返回追加了所有指标列的 DataFrame"""
    df = compute_ma(df)
    df = compute_macd(df)
    df = compute_rsi(df)
    df = compute_volume_price(df)
    return df


def compute_multi_timeframe(df_daily: pd.DataFrame) -> IndicatorResult:
    """输入日线DataFrame，输出三个周期各自的计算结果"""
    code = df_daily["code"].iloc[0] if "code" in df_daily.columns else ""
    df_daily = compute_all_indicators(df_daily)

    df_weekly = resample_to_weekly(df_daily)
    df_weekly = compute_all_indicators(df_weekly)

    df_monthly = resample_to_monthly(df_daily)
    df_monthly = compute_all_indicators(df_monthly)

    return IndicatorResult(code=code, daily=df_daily, weekly=df_weekly, monthly=df_monthly)
