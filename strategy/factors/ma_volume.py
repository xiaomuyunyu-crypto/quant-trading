# -*- coding: utf-8 -*-
"""
双均线 + 成交量过滤策略。

参考 GitHub: yikheichoi5217/multifactor_strategy 动量因子设计思路。

策略逻辑：
  1. 计算短期均线（fast_ma, 默认 5 日）和长期均线（slow_ma, 默认 20 日）；
  2. 计算成交量均线（vol_ma, 默认 10 日）；
  3. 金叉 + 成交量放大（当前量 > 成交量均线 × vol_ratio）→ 买入信号；
  4. 死叉 + 成交量放大 → 卖出信号；

成交量过滤的金融意义：
  - 放量突破更具可信度，可过滤缩量假突破；
  - 交易量异常放大往往预示趋势的确认或反转。
"""

from __future__ import division

import pandas as pd
import numpy as np
from typing import Optional, Tuple


class MAVolumeStrategy:
    """
    双均线 + 成交量过滤策略。

    参数：
        fast_period: 短期均线周期，默认 5
        slow_period: 长期均线周期，默认 20
        vol_period: 成交量均线周期，默认 10
        vol_ratio: 成交量放大倍数阈值，默认 1.5
        price_col: 价格列名，默认 "close"
        volume_col: 成交量列名，默认 "volume"
    """

    def __init__(self, fast_period=5, slow_period=20, vol_period=10,
                 vol_ratio=1.5, price_col="close", volume_col="volume"):
        if fast_period >= slow_period:
            raise ValueError("fast_period 必须小于 slow_period")

        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.vol_period = int(vol_period)
        self.vol_ratio = float(vol_ratio)
        self.price_col = price_col
        self.volume_col = volume_col

    def generate_signals(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        生成带成交量过滤的交易信号。

        参数：
            klines_df: K线数据 DataFrame，需含 date/close/volume 列。

        返回：
            pd.DataFrame: 含信号和仓位的完整数据。
        """
        df = klines_df.copy()

        for col in ["date", self.price_col, self.volume_col]:
            if col not in df.columns:
                raise ValueError(f"数据中缺少列: {col}")

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", self.price_col, self.volume_col])
        df = df.sort_values("date").reset_index(drop=True)

        # 计算均线
        df["fast_ma"] = df[self.price_col].rolling(
            window=self.fast_period, min_periods=self.fast_period).mean()
        df["slow_ma"] = df[self.price_col].rolling(
            window=self.slow_period, min_periods=self.slow_period).mean()

        # 计算成交量均线
        df["vol_ma"] = df[self.volume_col].rolling(
            window=self.vol_period, min_periods=self.vol_period).mean()

        # 成交量放大条件
        df["volume_surge"] = df[self.volume_col] > (df["vol_ma"] * self.vol_ratio)

        # 交叉判断
        prev_fast = df["fast_ma"].shift(1)
        prev_slow = df["slow_ma"].shift(1)

        golden_cross = (prev_fast <= prev_slow) & (df["fast_ma"] > df["slow_ma"])
        death_cross = (prev_fast >= prev_slow) & (df["fast_ma"] < df["slow_ma"])

        # 信号：金叉+放量 → 买入；死叉+放量 → 卖出
        df["signal"] = 0
        df.loc[golden_cross & df["volume_surge"], "signal"] = 1
        df.loc[death_cross & df["volume_surge"], "signal"] = -1

        # 持仓状态
        df["position"] = 0
        current_pos = 0
        for i in range(len(df)):
            sig = df.loc[i, "signal"]
            if sig == 1:
                current_pos = 1
            elif sig == -1:
                current_pos = 0
            df.loc[i, "position"] = current_pos

        return df

    def get_backtest_returns(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """简单向量化回测（单股票）。"""
        df = self.generate_signals(klines_df)
        df["price_return"] = df[self.price_col].pct_change()
        df["strategy_return"] = df["position"].shift(1) * df["price_return"]
        return df
