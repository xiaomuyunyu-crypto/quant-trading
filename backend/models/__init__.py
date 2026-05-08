# -*- coding: utf-8 -*-
# 后端共享数据模型（Pydantic）
# 此目录下的模型供所有窗口读取，修改需经总设计师协调

from .stock import StockBase, StockDetail, StockList
from .market import KlineData, RealtimeQuote
from .strategy import StrategyConfig, StrategySignal
from .backtest import BacktestRequest, BacktestResultModel, TradeItem, EquityPoint
from .signals import SignalResultModel, PeriodSignalDetail, SignalWeights, SignalQuery
