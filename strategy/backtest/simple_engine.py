# -*- coding: utf-8 -*-
"""
简单单股回测引擎。

按用户设计构想：
  - 初始资金：10000 元
  - 买入 = 满仓（全部资金买成股票）
  - 卖出 = 清仓（全部股票卖成现金）
  - 以收盘价成交
  - 忽略手续费
  - 输出：总资金曲线、累计收益率、买卖操作明细

后续可扩展为 3-5 只标的组合，按比例分配仓位（33%/25%/20%）。
"""

from __future__ import division

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class Trade:
    """单笔交易记录"""
    date: str
    action: str           # BUY / SELL
    price: float
    shares: int
    amount: float
    cash_after: float
    equity_after: float
    return_pct: float     # 累计收益率（%）
    reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_return: float           # 累计收益率（小数）
    total_return_pct: float       # 累计收益率（%）
    max_drawdown: float           # 最大回撤（小数）
    total_trades: int
    win_trades: int
    equity_curve: pd.DataFrame    # 每日权益
    trades: list[Trade]


class SimpleBacktestEngine:
    """
    简单单股回测引擎 —— 每次信号全仓进出。

    用法：
        engine = SimpleBacktestEngine(initial_capital=10000)
        result = engine.run(klines_df, signals_df)
    """

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.shares = 0
        self.trades: list[Trade] = []
        self.daily_records: list[dict] = []

    def reset(self):
        self.cash = float(self.initial_capital)
        self.shares = 0
        self.trades = []
        self.daily_records = []

    def run(
        self,
        klines: pd.DataFrame,
        signals: pd.DataFrame,
        code: str = "",
    ) -> BacktestResult:
        """
        执行回测。

        参数：
            klines: K线数据，需含 date / close 列
            signals: 信号数据，需含 date / signal 列
                     signal="BUY" → 满仓买入
                     signal="SELL" → 清仓卖出
                     signal="HOLD" → 不操作
            code: 股票代码（用于结果展示）

        返回：
            BacktestResult
        """
        self.reset()

        df = klines.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        sig = signals.copy()
        sig["date"] = pd.to_datetime(sig["date"])
        sig = sig.sort_values("date").reset_index(drop=True)

        # 按日期对齐，取每个信号日对应的收盘价
        price_map = dict(zip(df["date"], df["close"]))

        for _, srow in sig.iterrows():
            trade_date = srow["date"]
            signal = str(srow.get("signal", "HOLD")).upper()
            reason = str(srow.get("reason", ""))
            confidence = float(srow.get("confidence", 0))

            close_price = self._get_price(trade_date, price_map, df)
            if close_price is None or close_price <= 0:
                self._record_day(trade_date, close_price or 0)
                continue

            # ── 执行信号 ──
            if signal == "BUY" and self.shares == 0:
                # 满仓买入
                self.shares = int(self.cash / close_price)
                if self.shares > 0:
                    cost = self.shares * close_price
                    self.cash -= cost
                    self.trades.append(Trade(
                        date=str(trade_date)[:10],
                        action="BUY",
                        price=close_price,
                        shares=self.shares,
                        amount=cost,
                        cash_after=self.cash,
                        equity_after=self.cash + self.shares * close_price,
                        return_pct=self._return_pct(close_price),
                        reason=reason,
                    ))

            elif signal == "SELL" and self.shares > 0:
                # 清仓卖出
                proceeds = self.shares * close_price
                self.cash += proceeds
                sold_shares = self.shares
                self.shares = 0
                self.trades.append(Trade(
                    date=str(trade_date)[:10],
                    action="SELL",
                    price=close_price,
                    shares=sold_shares,
                    amount=proceeds,
                    cash_after=self.cash,
                    equity_after=self.cash,
                    return_pct=self._return_pct(close_price),
                    reason=reason,
                ))

            self._record_day(trade_date, close_price)

        # 如果最后还持有，按最后价格估值
        if self.shares > 0 and not df.empty:
            final_price = float(df["close"].iloc[-1])
            self._record_day(df["date"].iloc[-1], final_price)

        return self._build_result(code, df)

    def _get_price(self, target_date, price_map: dict, df: pd.DataFrame) -> Optional[float]:
        """获取某个日期的收盘价，找不到则用最近的前一个交易日价格"""
        if target_date in price_map:
            px = price_map[target_date]
            if pd.notna(px) and px > 0:
                return float(px)
        # 找之前最近的交易日
        earlier = [d for d in price_map if d < target_date]
        if earlier:
            px = price_map[max(earlier)]
            if pd.notna(px) and px > 0:
                return float(px)
        return None

    def _return_pct(self, current_price: float) -> float:
        """计算累计收益率（%）"""
        equity = self.cash + self.shares * current_price
        return (equity / self.initial_capital - 1.0) * 100.0

    def _record_day(self, trade_date, close_price: float):
        equity = self.cash + self.shares * close_price if close_price > 0 else self.cash
        self.daily_records.append({
            "date": trade_date,
            "cash": self.cash,
            "shares": self.shares,
            "close": close_price,
            "equity": equity,
            "net_value": equity / self.initial_capital,
        })

    def _build_result(self, code: str, klines: pd.DataFrame) -> BacktestResult:
        records = pd.DataFrame(self.daily_records)
        if records.empty:
            return BacktestResult(
                code=code,
                start_date="", end_date="",
                initial_capital=self.initial_capital,
                final_equity=self.initial_capital,
                total_return=0.0, total_return_pct=0.0,
                max_drawdown=0.0, total_trades=0, win_trades=0,
                equity_curve=records, trades=self.trades,
            )

        final_equity = float(records["equity"].iloc[-1])
        total_return = (final_equity / self.initial_capital) - 1.0

        # 最大回撤
        running_max = records["equity"].cummax()
        drawdown = (records["equity"] - running_max) / running_max
        max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

        # 胜负统计
        win_trades = 0
        for i in range(1, len(self.trades), 2):
            if i < len(self.trades):
                sell = self.trades[i]
                buy = self.trades[i - 1]
                if buy.action == "BUY" and sell.action == "SELL":
                    if sell.amount > buy.amount:
                        win_trades += 1

        return BacktestResult(
            code=code,
            start_date=str(records["date"].iloc[0])[:10],
            end_date=str(records["date"].iloc[-1])[:10],
            initial_capital=self.initial_capital,
            final_equity=round(final_equity, 2),
            total_return=round(total_return, 6),
            total_return_pct=round(total_return * 100, 2),
            max_drawdown=round(max_dd, 6),
            total_trades=len(self.trades),
            win_trades=win_trades,
            equity_curve=records,
            trades=self.trades,
        )

    def print_report(self, result: BacktestResult):
        """打印回测报告"""
        print("\n" + "=" * 55)
        print(f"  回测报告 — {result.code}")
        print("=" * 55)
        print(f"  回测区间：{result.start_date} ~ {result.end_date}")
        print(f"  初始资金：{result.initial_capital:,.2f} 元")
        print(f"  最终权益：{result.final_equity:,.2f} 元")
        print(f"  累计收益率：{result.total_return_pct:+.2f}%")
        print(f"  最大回撤：{result.max_drawdown:.2%}")
        print(f"  交易次数：{result.total_trades} 笔")
        print(f"  盈利次数：{result.win_trades} 笔")
        print("-" * 55)
        print(f"  {'日期':<12} {'操作':<6} {'价格':>8} {'股数':>8} {'金额':>12} {'累计收益%':>10}")
        print("  " + "-" * 53)
        for t in result.trades:
            print(f"  {t.date:<12} {t.action:<6} {t.price:>8.2f} {t.shares:>8} {t.amount:>12.2f} {t.return_pct:>+9.2f}%")
        print("=" * 55)


def run_simple_backtest(
    code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
    signal_weights: dict | None = None,
) -> BacktestResult:
    """
    一站式回测：从数据库读取K线 → 信号引擎分析 → 简单回测执行。

    用法：
        from strategy.backtest.simple_engine import run_simple_backtest
        result = run_simple_backtest("000001", "2023-01-01", "2024-12-31")
    """
    import sys
    sys.path.insert(0, ".")

    from data.storage.repository import query_klines
    from strategy.signal_engine import SignalEngine

    klines = query_klines(code, start_date=start_date, end_date=end_date)
    if klines.empty:
        raise ValueError(f"未获取到 {code} 的K线数据，请先同步: python -m data.pipeline sync-klines")

    engine = SignalEngine(weights=signal_weights) if signal_weights else SignalEngine()
    signals_df = engine.run_on_code(code, start_date, end_date)

    if signals_df.empty:
        raise ValueError(f"未能生成 {code} 的交易信号（数据不足或指标计算失败）")

    backtest = SimpleBacktestEngine(initial_capital=initial_capital)
    result = backtest.run(klines, signals_df, code=code)
    return result
