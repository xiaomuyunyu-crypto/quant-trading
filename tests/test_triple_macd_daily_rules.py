# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

import pandas as pd

from backend.core.backtest_engine import run_backtest
from strategy.components.state_machine import TripleMACDStateMachine
from strategy.indicators import compute_macd_bar_trend


def _daily_frame(hist_values, crosses=None, dif=1.0, dea=0.0):
    rows = len(hist_values)
    crosses = crosses or [0] * rows
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=rows, freq="D"),
        "code": ["TEST"] * rows,
        "open": [10.0] * rows,
        "high": [10.5] * rows,
        "low": [9.5] * rows,
        "close": [10.0 + i * 0.1 for i in range(rows)],
        "volume": [1000.0] * rows,
        "amount": [10000.0] * rows,
        "DIF": [dif] * rows,
        "DEA": [dea] * rows,
        "MACD_cross": crosses,
        "MACD_hist": hist_values,
        "MA250": [1.0] * rows,
    })
    return compute_macd_bar_trend(df)


def _plain_ohlcv(rows=60):
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=rows, freq="D"),
        "code": ["TEST"] * rows,
        "open": [10.0] * rows,
        "high": [10.5] * rows,
        "low": [9.5] * rows,
        "close": [10.0 + i * 0.1 for i in range(rows)],
        "volume": [1000.0] * rows,
        "amount": [10000.0] * rows,
    })


def _run_daily_only(hist_values, crosses=None):
    daily = _daily_frame(hist_values, crosses=crosses)
    sm = TripleMACDStateMachine(
        daily,
        daily,
        daily,
        use_monthly_filter=False,
        use_ma250_filter=False,
        use_weekly_filter=False,
    )
    return sm.run()


class TripleMACDDailyRuleTest(unittest.TestCase):
    def test_green_consecutive_shrink_buys(self):
        signals, history = _run_daily_only([-1.0, -0.8, -0.6, -0.4])

        self.assertEqual(signals[3], "BUY")
        self.assertIn("绿柱连续缩短3次", history[3]["reason"])

    def test_green_segment_total_shrink_buys(self):
        signals, history = _run_daily_only([
            -1.0, -0.8, -0.9, -0.7, -0.75, -0.6, -0.65, -0.5,
        ])

        self.assertNotIn("BUY", signals[:7])
        self.assertEqual(signals[7], "BUY")
        self.assertIn("绿柱累计缩短4次", history[7]["reason"])

    def test_red_consecutive_shrink_sells(self):
        signals, history = _run_daily_only([0.9, 0.8, 0.7], crosses=[1, 0, 0])

        self.assertEqual(signals[0], "BUY")
        self.assertEqual(signals[2], "SELL")
        self.assertIn("红柱连续缩短2次", history[2]["reason"])

    def test_red_segment_total_shrink_sells(self):
        signals, history = _run_daily_only(
            [0.9, 0.8, 0.85, 0.75, 0.8, 0.7],
            crosses=[1, 0, 0, 0, 0, 0],
        )

        self.assertNotIn("SELL", signals[:5])
        self.assertEqual(signals[5], "SELL")
        self.assertIn("红柱累计缩短3次", history[5]["reason"])

    def test_segment_total_resets_after_color_change(self):
        daily = _daily_frame([-1.0, -0.8, -0.9, 0.2, 0.1, -0.7, -0.6])

        self.assertEqual(int(daily.loc[1, "MACD_green_shrink_segment_total"]), 1)
        self.assertEqual(int(daily.loc[2, "MACD_green_shrink_segment_total"]), 1)
        self.assertEqual(int(daily.loc[3, "MACD_green_shrink_segment_total"]), 0)
        self.assertEqual(int(daily.loc[6, "MACD_green_shrink_segment_total"]), 1)

    def test_daily_only_backtest_uses_new_reason(self):
        hist = [0.0] * 55 + [0.2, 0.9, 0.8, 0.7, 0.6]
        crosses = [0] * 55 + [1, 0, 0, 0, 0]
        prepared = _daily_frame(hist, crosses=crosses)

        with patch("strategy.components.state_machine.prepare_dataframes", return_value=(prepared, prepared, prepared)):
            result = run_backtest(
                _plain_ohlcv(len(hist)),
                "TEST",
                strategy="triple_macd_daily_only",
                initial_capital=10000,
            )

        self.assertEqual([trade.action for trade in result.trades[:2]], ["BUY", "SELL"])
        self.assertIn("日线MACD金叉", result.trades[0].reason)
        self.assertIn("红柱连续缩短2次", result.trades[1].reason)

    def test_original_strategy_keeps_monthly_filter(self):
        hist = [0.0] * 59 + [0.2]
        crosses = [0] * 59 + [1]
        daily = _daily_frame(hist, crosses=crosses, dif=1.0, dea=0.0)
        weekly = daily.copy()
        monthly = _daily_frame(hist, crosses=[0] * 60, dif=-1.0, dea=0.0)

        with patch("strategy.components.state_machine.prepare_dataframes", return_value=(daily, weekly, monthly)):
            result = run_backtest(
                _plain_ohlcv(len(hist)),
                "TEST",
                strategy="triple_macd_ma250",
                initial_capital=10000,
            )

        self.assertEqual(result.total_trades, 0)
        self.assertEqual(result.signals.count("BUY"), 0)


if __name__ == "__main__":
    unittest.main()
