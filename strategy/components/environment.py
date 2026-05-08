# -*- coding: utf-8 -*-
"""
市场环境过滤器 —— 判断当前市场是否适合交易。

参考 Hikyuu 的 Environment 组件设计。
"""

from __future__ import division

import pandas as pd
from strategy.components.base import EnvironmentFilter


class MATrendEnvironment(EnvironmentFilter):
    """
    基于均线判断市场环境：
      - 牛市：价格在MA60上方，MA20向上
      - 熊市：价格在MA60下方，MA20向下
      - 震荡：其他
    """

    def __init__(self, allow_bull=True, allow_bear=False, allow_range=True):
        self.allow_bull = allow_bull
        self.allow_bear = allow_bear
        self.allow_range = allow_range

    @property
    def name(self): return "均线环境过滤"

    def is_tradeable(self, df: pd.DataFrame) -> tuple[bool, str]:
        if df.empty:
            return False, "无数据"

        row = df.iloc[-1]
        close = row.get("close", 0) or 0
        ma20 = row.get("MA20", close) or close
        ma60 = row.get("MA60", close) or close

        if len(df) < 5:
            return True, "数据不足，默认允许"

        # 判断趋势
        ma20_slope = row.get("MA20_slope", 0) or 0

        if close > ma60 and ma20_slope > 0:
            regime = "牛市"
            allowed = self.allow_bull
        elif close < ma60 and ma20_slope < 0:
            regime = "熊市"
            allowed = self.allow_bear
        else:
            regime = "震荡"
            allowed = self.allow_range

        reason = f"当前{regime}(价格={'高于' if close > ma60 else '低于'}MA60, MA20={'上升' if ma20_slope > 0 else '下降'})"
        return allowed, reason


class AlwaysTradeEnvironment(EnvironmentFilter):
    """始终允许交易，不做环境过滤"""

    @property
    def name(self): return "始终交易"

    def is_tradeable(self, df: pd.DataFrame) -> tuple[bool, str]:
        return True, "始终允许"
