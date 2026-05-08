# -*- coding: utf-8 -*-
"""
组件化策略组装器 —— CompositeStrategy。

借鉴 Hikyuu 的可插拔 System 设计：
  System = Σ SignalComponents + EnvironmentFilter + MoneyManager + RiskManager

用法：
    strategy = CompositeStrategy(
        signals=[MACDCrossSignal(), RSISignal(), MATrendSignal(), VolumePriceSignal()],
        environment=MATrendEnvironment(allow_bull=True, allow_bear=True),
        money=AllInManager(),
        risk=StopLossRisk(),
        signal_mode="majority",   # majority / consensus / weighted
    )
    signals_df = strategy.run_on_code("000001", "2024-01-01", "2026-05-07")
"""

from __future__ import division

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from strategy.components.base import (
    SignalComponent, EnvironmentFilter, MoneyManager, RiskManager,
    SignalOutput,
)
from strategy.indicators import (
    compute_ma, compute_macd, compute_rsi, compute_volume_price,
    resample_to_weekly, resample_to_monthly,
)


@dataclass
class CompositeResult:
    """组装策略的最终输出"""
    date: str
    code: str
    signal: str = "HOLD"           # BUY / SELL / HOLD
    confidence: float = 0.0
    position_pct: float = 0.0       # 目标仓位比例
    environment_ok: bool = True
    env_reason: str = ""
    risk_triggered: bool = False
    risk_reason: str = ""
    signal_votes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class CompositeStrategy:
    """
    组件化策略 —— 组装多个组件为一个完整策略。

    参数：
        signals: 信号组件列表
        environment: 环境过滤器
        money: 仓位管理器
        risk: 风控管理器
        signal_mode: 信号投票模式
            - "majority": 多数表决（BUY vs SELL票数）
            - "consensus": 全票一致才出信号（否则HOLD）
            - "weighted": 按置信度加权求和
        multi_timeframe: 是否在日/周/月线上分别分析
        tf_weights: 多周期权重 {"daily": 0.5, "weekly": 0.3, "monthly": 0.2}
    """

    def __init__(
        self,
        signals: list[SignalComponent],
        environment: Optional[EnvironmentFilter] = None,
        money: Optional[MoneyManager] = None,
        risk: Optional[RiskManager] = None,
        signal_mode: str = "majority",
        multi_timeframe: bool = False,
        tf_weights: dict | None = None,
    ):
        self.signals = signals
        self.environment = environment or AlwaysTradeEnv()
        self.money = money or AllInMoney()
        self.risk = risk or NoRisk()
        self.signal_mode = signal_mode
        self.multi_timeframe = multi_timeframe
        self.tf_weights = tf_weights or {"daily": 0.5, "weekly": 0.3, "monthly": 0.2}

    # ─── 数据准备 ───

    def _prepare_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = compute_ma(df)
        df = compute_macd(df)
        df = compute_rsi(df)
        df = compute_volume_price(df)
        return df

    def _prepare_multi_timeframe(self, df_daily: pd.DataFrame) -> dict:
        daily = self._prepare_indicators(df_daily)
        weekly = resample_to_weekly(daily)
        weekly = self._prepare_indicators(weekly)
        monthly = resample_to_monthly(daily)
        monthly = self._prepare_indicators(monthly)
        return {"daily": daily, "weekly": weekly, "monthly": monthly}

    # ─── 信号汇总 ───

    def _aggregate_signals(self, outputs: list[SignalOutput]) -> tuple[str, float, list[str]]:
        """汇总多个信号组件的输出"""
        buy_count = sum(1 for o in outputs if o.signal == "BUY")
        sell_count = sum(1 for o in outputs if o.signal == "SELL")
        hold_count = sum(1 for o in outputs if o.signal == "HOLD")

        reasons = [f"[{o.reason}]" for o in outputs if o.signal != "HOLD"]

        if self.signal_mode == "consensus":
            if buy_count == len(outputs):
                return "BUY", 0.9, reasons
            elif sell_count == len(outputs):
                return "SELL", 0.9, reasons
            else:
                return "HOLD", 0.0, reasons

        elif self.signal_mode == "weighted":
            total_conf = 0.0
            for o in outputs:
                if o.signal == "BUY":
                    total_conf += o.confidence
                elif o.signal == "SELL":
                    total_conf -= o.confidence
            if total_conf > 0.3:
                return "BUY", min(1.0, abs(total_conf)), reasons
            elif total_conf < -0.3:
                return "SELL", min(1.0, abs(total_conf)), reasons
            else:
                return "HOLD", 0.0, reasons

        else:  # majority
            if buy_count > sell_count:
                conf = buy_count / len(outputs)
                return "BUY", conf, reasons
            elif sell_count > buy_count:
                conf = sell_count / len(outputs)
                return "SELL", conf, reasons
            else:
                return "HOLD", 0.0, reasons

    # ─── 单周期分析 ───

    def _analyze_single(self, df: pd.DataFrame, code: str) -> CompositeResult:
        if df.empty or len(df) < 2:
            return CompositeResult(date="", code=code)

        latest_date = str(df["date"].iloc[-1])[:10]

        # 1) 环境检查
        env_ok, env_reason = self.environment.is_tradeable(df)

        # 2) 各信号组件
        outputs = [sig.analyze(df) for sig in self.signals]
        agg_signal, agg_conf, reasons = self._aggregate_signals(outputs)

        # 3) 环境否决
        if not env_ok and agg_signal == "BUY":
            agg_signal = "HOLD"
            agg_conf = 0.0
            reasons.append(f"[环境否决: {env_reason}]")

        # 4) 仓位
        pos_pct = self.money.get_position_pct(agg_signal, agg_conf, df)
        if pos_pct < 0:
            pos_pct = -1.0   # 不改变

        return CompositeResult(
            date=latest_date, code=code,
            signal=agg_signal, confidence=agg_conf, position_pct=pos_pct,
            environment_ok=env_ok, env_reason=env_reason,
            signal_votes=[o.signal for o in outputs], reasons=reasons,
        )

    # ─── 多周期分析 ───

    def analyze(self, df_daily: pd.DataFrame, code: str = "") -> CompositeResult:
        """
        核心方法：输入日线DataFrame（包含K线列），输出当前信号。
        """
        if not self.multi_timeframe:
            df = self._prepare_indicators(df_daily)
            return self._analyze_single(df, code)

        # 多周期模式
        tf_data = self._prepare_multi_timeframe(df_daily)
        tf_results = {}
        for tf_name, df in tf_data.items():
            tf_results[tf_name] = self._analyze_single(df, code)

        # 汇总多周期
        buy_weight = 0.0
        sell_weight = 0.0
        all_reasons = []
        for tf_name, result in tf_results.items():
            w = self.tf_weights.get(tf_name, 0.33)
            if result.signal == "BUY":
                buy_weight += w * result.confidence
            elif result.signal == "SELL":
                sell_weight += w * result.confidence
            all_reasons.extend([f"[{tf_name}]{r}" for r in result.reasons])

        if buy_weight > sell_weight and buy_weight > 0.2:
            signal = "BUY"
            conf = buy_weight
        elif sell_weight > buy_weight and sell_weight > 0.2:
            signal = "SELL"
            conf = sell_weight
        else:
            signal = "HOLD"
            conf = 0.0

        pos_pct = self.money.get_position_pct(signal, conf, tf_data["daily"])
        if pos_pct < 0:
            pos_pct = -1.0

        daily_res = tf_results.get("daily", CompositeResult(date="", code=code))
        return CompositeResult(
            date=daily_res.date, code=code,
            signal=signal, confidence=min(1.0, conf), position_pct=pos_pct,
            environment_ok=daily_res.environment_ok,
            env_reason=daily_res.env_reason,
            signal_votes=[f"{tf}:{r.signal}" for tf, r in tf_results.items()],
            reasons=all_reasons,
        )

    # ─── 批量运行 ───

    def run_on_code(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """对单个标的逐日生成信号历史"""
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

        # 重置风控状态
        for sig in self.signals:
            if hasattr(sig, 'reset'):
                sig.reset()
        if hasattr(self.risk, 'reset'):
            self.risk.reset()

        results = []
        entry_price = 0.0
        holding_days = 0
        max_dd = 0.0

        for i in range(min_bars, len(klines) + 1):
            window = klines.iloc[:i].copy()
            try:
                result = self.analyze(window, code=code)
                current_price = window["close"].iloc[-1]

                # 风控检查
                if entry_price > 0 and result.signal != "SELL":
                    triggered, risk_reason = self.risk.check(
                        entry_price, current_price, holding_days, max_dd
                    )
                    if triggered:
                        result.signal = "SELL"
                        result.confidence = 1.0
                        result.risk_triggered = True
                        result.risk_reason = risk_reason
                        result.reasons.append(f"[风控]{risk_reason}")

                # 跟踪持仓状态
                if result.signal == "BUY" and entry_price == 0:
                    entry_price = current_price
                    holding_days = 0
                    max_dd = 0.0
                elif result.signal == "SELL":
                    entry_price = 0.0
                    holding_days = 0
                    max_dd = 0.0
                elif entry_price > 0:
                    holding_days += 1
                    dd = (current_price - entry_price) / entry_price
                    max_dd = min(max_dd, dd)

                results.append({
                    "date": result.date,
                    "signal": result.signal,
                    "confidence": result.confidence,
                    "position_pct": result.position_pct,
                    "env_ok": result.environment_ok,
                    "risk_triggered": result.risk_triggered,
                    "signal_votes": "|".join(result.signal_votes) if result.signal_votes else "",
                    "reason": "；".join(result.reasons) if result.reasons else "",
                })
            except Exception:
                continue

        return pd.DataFrame(results)


# ─── 便捷内置策略 ───

class AlwaysTradeEnv(EnvironmentFilter):
    @property
    def name(self): return "始终交易"
    def is_tradeable(self, df): return True, "始终允许"


class AllInMoney(MoneyManager):
    @property
    def name(self): return "全仓"
    def get_position_pct(self, signal, confidence, df):
        if signal == "BUY": return 1.0
        elif signal == "SELL": return 0.0
        return -1.0


class NoRisk(RiskManager):
    @property
    def name(self): return "无风控"
    def check(self, entry_price, current_price, holding_days, max_dd):
        return False, ""


def create_default_strategy(
    signal_mode="majority",
    multi_timeframe=False,
) -> CompositeStrategy:
    """创建默认的组件化策略"""
    from strategy.components.signals import (
        MACDCrossSignal, RSISignal, MATrendSignal, VolumePriceSignal,
    )
    from strategy.components.environment import AlwaysTradeEnvironment
    from strategy.components.money_manager import AllInManager
    from strategy.components.risk_manager import NoRiskManager

    return CompositeStrategy(
        signals=[
            MACDCrossSignal(),
            RSISignal(),
            MATrendSignal(),
            VolumePriceSignal(),
        ],
        environment=AlwaysTradeEnvironment(),
        money=AllInManager(),
        risk=NoRiskManager(),
        signal_mode=signal_mode,
        multi_timeframe=multi_timeframe,
    )
