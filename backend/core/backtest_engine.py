# -*- coding: utf-8 -*-
# 回测引擎：全仓进出 / 收盘价交易 / 忽略手续费

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import date as DateType

from backend.core.signal_engine import (
    generate_signal, calc_macd, calc_rsi, calc_ma,
    detect_golden_cross, detect_death_cross, detect_all_crosses,
)


@dataclass
class TradeRecord:
    date: str
    code: str
    action: str
    price: float
    shares: int = 0
    amount: float = 0.0
    reason: str = ""
    equity_after: float = 0.0


@dataclass
class BacktestResult:
    code: str
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    final_equity: float = 10000.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)
    strategy_name: str = ""


def run_backtest(
    df: pd.DataFrame,
    code: str,
    strategy: str = "macd_daily",
    initial_capital: float = 10000.0,
) -> BacktestResult:
    """
    对单只标的执行回测。

    df: 日线OHLCV数据, 列含 open/high/low/close/volume/date
    strategy:
        "macd_daily"      日线MACD绿柱连续缩短3天买、红柱连续缩短3天卖
        "macd_weekly"     周线MACD金叉买、死叉卖
        "rsi_oversold"    RSI<20买、RSI>70卖，连续3日强化
        "ma_cross"        MA5上穿MA20买、下穿MA20卖

    规则：全仓进出 + 收盘价 + 忽略手续费
    """
    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].values.astype(np.float64)

    signals = _generate_strategy_signals(df, strategy)
    if len(signals) == 0:
        return BacktestResult(code=code, start_date=str(df["date"].iloc[0]),
                              end_date=str(df["date"].iloc[-1]),
                              initial_capital=initial_capital)

    cash = initial_capital
    shares = 0
    equity = initial_capital
    equity_curve = []
    trades = []
    peak = initial_capital
    max_dd = 0.0

    for i in range(len(df)):
        date_str = str(df["date"].iloc[i])
        price = float(close[i])
        sig = signals[i]

        # 交易执行
        if sig == "BUY" and shares == 0 and cash > 0:
            shares = int(cash / price)
            if shares > 0:
                amount = shares * price
                cash -= amount
                equity = cash + shares * price
                trades.append(TradeRecord(
                    date=date_str, code=code, action="BUY",
                    price=price, shares=shares, amount=amount,
                    reason=_trade_reason(strategy, "BUY"),
                    equity_after=round(equity, 2),
                ))

        elif sig == "SELL" and shares > 0:
            amount = shares * price
            cash += amount
            sold = shares
            shares = 0
            equity = cash
            trades.append(TradeRecord(
                date=date_str, code=code, action="SELL",
                price=price, shares=sold, amount=amount,
                reason=_trade_reason(strategy, "SELL"),
                equity_after=round(equity, 2),
            ))

        # 计算当日权益（BUY/SELL已在上面计算过了）
        if sig not in ("BUY", "SELL"):
            equity = cash + shares * price
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

        equity_curve.append({"date": date_str, "equity": round(equity, 2)})

    # 最后如仍持仓，按最后一天收盘价清仓
    if shares > 0:
        last_price = float(close[-1])
        amount = shares * last_price
        cash += amount
        equity = cash
        shares = 0
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        trades.append(TradeRecord(
            date=str(df["date"].iloc[-1]), code=code, action="SELL(回测结束清仓)",
            price=last_price, shares=shares, amount=amount,
            reason="回测结束强制清仓",
            equity_after=round(equity, 2),
        ))
        equity_curve.append({"date": str(df["date"].iloc[-1]), "equity": round(equity, 2)})

    final_equity = equity
    total_return = (final_equity - initial_capital) / initial_capital

    return BacktestResult(
        code=code,
        start_date=str(df["date"].iloc[0]),
        end_date=str(df["date"].iloc[-1]),
        initial_capital=initial_capital,
        final_equity=round(final_equity, 2),
        total_return=round(total_return, 6),
        max_drawdown=round(max_dd, 6),
        total_trades=len([t for t in trades if "回测结束" not in t.action]),
        equity_curve=equity_curve,
        trades=trades,
        strategy_name=strategy,
    )


def _generate_strategy_signals(df: pd.DataFrame, strategy: str) -> list[str]:
    """根据策略类型生成逐日信号列表"""
    close = df["close"].values.astype(np.float64)
    n = len(close)

    # ── 组件化组合策略 ──
    if strategy.startswith("composite_"):
        return _generate_composite_signals(df, strategy)

    if strategy == "macd_hist":
        # MACD柱趋势策略：红柱连续2天缩短→卖出，绿柱从最低点回升3次→买入
        dif, dea, hist = calc_macd(close)
        signals = ["HOLD"] * n
        in_position = False
        green_low_count = 0   # 绿柱从低点回升计数
        prev_hist = 0

        for i in range(n):
            h = float(hist[i]) if not np.isnan(hist[i]) else 0
            if i < 2:
                prev_hist = h
                continue

            prev_h = float(hist[i-1]) if not np.isnan(hist[i-1]) else 0
            prev2_h = float(hist[i-2]) if not np.isnan(hist[i-2]) else 0

            if in_position:
                # 持仓中：红柱连续2天缩短 → 卖出
                if h > 0 and prev_h > 0 and prev2_h > 0:
                    if h < prev_h < prev2_h:
                        signals[i] = "SELL"
                        in_position = False
                        green_low_count = 0
            else:
                # 空仓中：绿柱从最低点回升 → 买入
                if h < 0 and prev_h < 0 and prev2_h < 0:
                    # 检测绿柱回升（数值在变大，即负得少）
                    if prev2_h < prev_h < h:
                        green_low_count += 1
                        if green_low_count >= 3:
                            signals[i] = "BUY"
                            in_position = True
                            green_low_count = 0
                else:
                    green_low_count = 0
                    # 红柱区域直接买入(金叉已经发生在上方)
                    if h > 0 and prev_h <= 0:
                        signals[i] = "BUY"
                        in_position = True
                        green_low_count = 0

            prev_hist = h

        return signals

    if strategy == "macd_daily":
        dif, dea, _ = calc_macd(close)
        hist = (dif - dea) * 2
        signals = []
        for i in range(n):
            if _macd_hist_shrinking(hist, i, color="green", days=3):
                signals.append("BUY")
            elif _macd_hist_shrinking(hist, i, color="red", days=3):
                signals.append("SELL")
            else:
                signals.append("HOLD")
        return signals

    elif strategy == "macd_weekly":
        # 用日线重采样到周线 OHLC
        df_w = _resample_to_weekly(df)
        close_w = df_w["close"].values.astype(np.float64)
        dif, dea, _ = calc_macd(close_w)
        crosses_w = detect_all_crosses(dif, dea)
        # 将周线交叉映射回日线（交叉发生在该周最后一个交易日）
        signals = ["HOLD"] * n
        for w in range(len(crosses_w)):
            if crosses_w[w] != 0:
                day_idx = min((w + 1) * 5 - 1, n - 1)
                if crosses_w[w] == 1:
                    signals[day_idx] = "BUY"
                else:
                    signals[day_idx] = "SELL"
        return signals

    elif strategy == "rsi_oversold":
        rsi = calc_rsi(close, 14)
        under_20_count = 0
        over_70_count = 0
        signals = []
        in_position = False
        for i in range(n):
            if np.isnan(rsi[i]):
                signals.append("HOLD")
                continue
            if rsi[i] < 20:
                under_20_count += 1
                over_70_count = 0
                if under_20_count >= 3 and not in_position:
                    signals.append("BUY")
                    in_position = True
                else:
                    signals.append("HOLD")
            elif rsi[i] > 70:
                over_70_count += 1
                under_20_count = 0
                if over_70_count >= 3 and in_position:
                    signals.append("SELL")
                    in_position = False
                else:
                    signals.append("HOLD")
            else:
                under_20_count = 0
                over_70_count = 0
                signals.append("HOLD")
        return signals

    elif strategy == "ma_cross":
        ma5 = calc_ma(close, 5)
        ma20 = calc_ma(close, 20)
        crosses = detect_all_crosses(ma5, ma20)
        signals = []
        for i in range(n):
            if crosses[i] == 1:
                signals.append("BUY")
            elif crosses[i] == -1:
                signals.append("SELL")
            else:
                signals.append("HOLD")
        return signals

    else:
        return ["HOLD"] * n


def _resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """日线DataFrame → 周线 OHLC（前向填充，周五收盘）"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    weekly = df.resample("W-FRI").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum", "amount": "sum",
    })
    weekly["code"] = df["code"].iloc[0] if "code" in df.columns else ""
    return weekly.dropna().reset_index()


def _generate_strategy_signals_by_params(df: pd.DataFrame, strategy: str, **params) -> list[str]:
    """参数化信号生成——用于网格搜索优化"""
    close = df["close"].values.astype(np.float64)
    n = len(close)

    if strategy == "ma_cross":
        fast = params.get("fast", 5)
        slow = params.get("slow", 20)
        ma_fast = calc_ma(close, fast)
        ma_slow = calc_ma(close, slow)
        crosses = detect_all_crosses(ma_fast, ma_slow)
        return ["BUY" if c == 1 else ("SELL" if c == -1 else "HOLD") for c in crosses]

    elif strategy == "macd_daily":
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        dif, dea, _ = calc_macd(close, fast=fast, slow=slow, signal=signal)
        hist = (dif - dea) * 2
        signals = []
        for i in range(n):
            if _macd_hist_shrinking(hist, i, color="green", days=3):
                signals.append("BUY")
            elif _macd_hist_shrinking(hist, i, color="red", days=3):
                signals.append("SELL")
            else:
                signals.append("HOLD")
        return signals

    return _generate_strategy_signals(df, strategy)


def _macd_hist_shrinking(hist: np.ndarray, idx: int, color: str, days: int = 3) -> bool:
    """判断最近days根MACD柱是否同色且逐日缩短。"""
    start = idx - days + 1
    if start < 0:
        return False

    values = hist[start:idx + 1]
    if len(values) < days or np.isnan(values).any():
        return False

    if color == "green":
        same_color = np.all(values < 0)
    elif color == "red":
        same_color = np.all(values > 0)
    else:
        return False

    if not same_color:
        return False

    heights = np.abs(values)
    return all(heights[i] < heights[i - 1] for i in range(1, len(heights)))


def _trade_reason(strategy: str, action: str) -> str:
    if strategy == "macd_daily":
        if action == "BUY":
            return "MACD绿柱连续缩短3天"
        if action == "SELL":
            return "MACD红柱连续缩短3天"
    return f"{strategy}{'买入' if action == 'BUY' else '卖出'}信号"


def run_backtest_with_signals(df: pd.DataFrame, code: str, signals: list[str],
                               strategy_name: str = "",
                               initial_capital: float = 10000.0) -> BacktestResult:
    """用已有信号列表跑回测（跳过信号生成步骤）"""
    from backend.core.backtest_engine import BacktestResult, TradeRecord

    close = df["close"].values.astype(np.float64)
    n = min(len(close), len(signals))

    cash = initial_capital
    shares = 0
    equity = initial_capital
    equity_curve = []
    trades = []
    peak = initial_capital
    max_dd = 0.0

    for i in range(n):
        date_str = str(df["date"].iloc[i])
        price = float(close[i])
        sig = signals[i]

        if sig == "BUY" and shares == 0 and cash > 0:
            shares = int(cash / price)
            if shares > 0:
                amount = shares * price
                cash -= amount
                equity = cash + shares * price
                trades.append(TradeRecord(date=date_str, code=code, action="BUY",
                                          price=price, shares=shares, amount=amount,
                                          reason=f"{strategy_name}买入", equity_after=round(equity, 2)))

        elif sig == "SELL" and shares > 0:
            amount = shares * price
            cash += amount
            shares = 0
            equity = cash
            trades.append(TradeRecord(date=date_str, code=code, action="SELL",
                                      price=price, shares=shares, amount=amount,
                                      reason=f"{strategy_name}卖出", equity_after=round(equity, 2)))

        if sig not in ("BUY", "SELL"):
            equity = cash + shares * price

        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        equity_curve.append({"date": date_str, "equity": round(equity, 2)})

    if shares > 0:
        last_price = float(close[-1])
        cash += shares * last_price
        equity = cash
        shares = 0
        equity_curve.append({"date": str(df["date"].iloc[-1]), "equity": round(equity, 2)})

    final_equity = equity
    total_return = (final_equity - initial_capital) / initial_capital

    return BacktestResult(
        code=code, start_date=str(df["date"].iloc[0]), end_date=str(df["date"].iloc[-1]),
        initial_capital=initial_capital, final_equity=round(final_equity, 2),
        total_return=round(total_return, 6), max_drawdown=round(max_dd, 6),
        total_trades=len([t for t in trades if "回测结束" not in t.action]),
        equity_curve=equity_curve, trades=trades, strategy_name=strategy_name,
    )


def _generate_composite_signals(df: pd.DataFrame, strategy: str) -> list[str]:
    """使用组件化策略生成信号"""
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from strategy.composite import create_default_strategy

    # 解析策略参数
    mode_map = {
        "composite_majority": "majority",
        "composite_weighted": "weighted",
        "composite_consensus": "consensus",
        "composite_mtf": "majority",
    }
    mode = mode_map.get(strategy, "majority")
    mtf = strategy == "composite_mtf"

    strat = create_default_strategy(signal_mode=mode, multi_timeframe=mtf)

    min_bars = 60
    if len(df) < min_bars:
        return ["HOLD"] * len(df)

    signals = ["HOLD"] * len(df)
    for i in range(min_bars, len(df) + 1):
        window = df.iloc[:i].copy()
        try:
            result = strat.analyze(window)
            signals[i - 1] = result.signal
        except Exception:
            pass

    return signals
