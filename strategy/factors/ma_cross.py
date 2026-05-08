# -*- coding: utf-8 -*-
"""
均线交叉策略 —— 第一个 Demo 策略。

参考 GitHub: 0xRobWatson/Quant-Trading-Strategy-Backtesting-Framework
           yikheichoi5217/multifactor_strategy

策略逻辑：
  1. 计算短期均线（fast_ma, 默认 5 日）和长期均线（slow_ma, 默认 20 日）；
  2. 金叉（短线上穿长线）→ 买入信号；
  3. 死叉（短线下穿长线）→ 卖出信号；
  4. 支持通过本项目的 data/storage/repository.py 查询 K 线数据。

适用场景：
  - 趋势明显的单边行情效果较好；
  - 震荡市可能频繁产生假信号，需结合其他过滤条件。

风险与局限：
  - 滞后性：均线是滞后指标，在快速反转行情中反应慢；
  - 假信号：震荡行情中可能频繁交叉，导致交易成本过高；
  - 单股票操作：当前为单标的策略，不涉及组合管理。
"""

from __future__ import division

import pandas as pd
import numpy as np
from typing import Optional, Tuple


class MACrossStrategy:
    """
    均线交叉策略。

    参数：
        fast_period: 短期均线周期，默认 5
        slow_period: 长期均线周期，默认 20
        price_col: 价格列名，默认 "close"

    用法：
        strategy = MACrossStrategy(fast_period=5, slow_period=20)
        signals = strategy.generate_signals(klines_df)

    signals 返回 DataFrame，包含：
        - date: 交易日期
        - close: 收盘价
        - fast_ma: 短期均线
        - slow_ma: 长期均线
        - signal: 1=买入, -1=卖出, 0=无信号
        - position: 当前仓位（1=持有, 0=空仓）
    """

    def __init__(self, fast_period=5, slow_period=20, price_col="close"):
        if fast_period >= slow_period:
            raise ValueError("fast_period 必须小于 slow_period")
        if fast_period < 2:
            raise ValueError("fast_period 至少为 2")

        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.price_col = price_col

    def compute_ma(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算双均线。

        参数：
            klines_df: K线数据，必须含 date 列和 price_col 列。

        返回：
            pd.DataFrame: 包含 fast_ma, slow_ma 的数据框。
        """
        df = klines_df.copy()
        if self.price_col not in df.columns:
            raise ValueError(f"数据中缺少列: {self.price_col}")

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", self.price_col])
        df = df.sort_values("date").reset_index(drop=True)

        df["fast_ma"] = df[self.price_col].rolling(window=self.fast_period, min_periods=self.fast_period).mean()
        df["slow_ma"] = df[self.price_col].rolling(window=self.slow_period, min_periods=self.slow_period).mean()

        return df

    def generate_signals(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号。

        参数：
            klines_df: K线数据 DataFrame。

        返回：
            pd.DataFrame: 含信号和仓位的完整数据。
        """
        df = self.compute_ma(klines_df)

        # 交叉判断：前一刻短均线 <= 长均线 且 当前短均线 > 长均线 → 金叉
        prev_fast = df["fast_ma"].shift(1)
        prev_slow = df["slow_ma"].shift(1)

        golden_cross = (prev_fast <= prev_slow) & (df["fast_ma"] > df["slow_ma"])
        death_cross = (prev_fast >= prev_slow) & (df["fast_ma"] < df["slow_ma"])

        df["signal"] = 0
        df.loc[golden_cross, "signal"] = 1
        df.loc[death_cross, "signal"] = -1

        # 持仓状态：信号出现后次日开盘持有，直到出现反向信号
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

    def get_holdings_for_backtest(self, klines_df: pd.DataFrame) -> dict:
        """
        生成回测引擎所需的持仓字典。

        返回：
            Dict[pd.Timestamp, List[str]]: {日期: [持仓股票代码列表]}。
            注意：此方法需要 klines_df 包含 "code" 列。
        """
        df = self.generate_signals(klines_df)
        code_col = "code" if "code" in df.columns else "stock_code"

        holdings = {}
        for _, row in df.iterrows():
            date = row["date"]
            code = str(row.get(code_col, "000001"))
            if pd.notna(date):
                holdings[pd.Timestamp(date)] = [code] if row["position"] == 1 else []

        return holdings

    def get_backtest_returns(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        简单向量化回测（单股票，不考虑交易成本），快速验证策略效果。

        返回：
            pd.DataFrame: 含 strategy_return 列的数据框。
        """
        df = self.generate_signals(klines_df)
        df["price_return"] = df[self.price_col].pct_change()
        df["strategy_return"] = df["position"].shift(1) * df["price_return"]
        return df


def from_repository(code: str, start_date: str, end_date: str,
                    fast_period=5, slow_period=20) -> pd.DataFrame:
    """
    从项目数据仓库加载 K 线并运行策略的便捷函数。

    用法：
        from strategy.factors.ma_cross import from_repository
        result = from_repository("000001", "2023-01-01", "2024-01-01")
    """
    import sys
    sys.path.insert(0, ".")
    from data.storage.repository import query_klines

    klines = query_klines(code, start_date=start_date, end_date=end_date)
    if klines.empty:
        print(f"[警告] 未获取到 {code} 的K线数据。")
        return pd.DataFrame()

    strategy = MACrossStrategy(fast_period=fast_period, slow_period=slow_period)
    return strategy.generate_signals(klines)
