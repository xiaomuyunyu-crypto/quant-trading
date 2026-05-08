# -*- coding: utf-8 -*-
"""
回测引擎模块。

参考 GitHub: yikheichoi5217/multifactor_strategy 的回测引擎架构，
适配本项目数据接口（data/storage/repository.py）。

功能：
1. 按日推进回测，支持日频/周频/月频调仓；
2. 等权/市值加权配置；
3. 双边交易成本（买入+卖出佣金）；
4. 停牌处理（无当日价格沿用上一可用价格估值）；
5. 完整记录每日净值、现金、持仓与交易日志。
"""

from __future__ import division

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class BacktestEngine:
    """
    通用回测引擎，支持单策略/多策略运行。
    """

    def __init__(self, initial_cash=1000000.0, commission_rate=0.001):
        """
        参数：
            initial_cash: 初始资金
            commission_rate: 单边交易费率（买入和卖出均收取）
        """
        self.initial_cash = float(initial_cash)
        self.commission_rate = float(commission_rate)
        self.reset()

    def reset(self):
        """重置引擎状态，用于多次回测。"""
        self.cash = float(self.initial_cash)
        self.positions = {}
        self.last_prices = {}
        self.records = []
        self.trade_logs = []

    # ─── 价格矩阵构建 ───

    @staticmethod
    def build_price_table(price_df, code_col="code", date_col="date", price_col="close"):
        """
        将长表行情转换为宽表价格矩阵（date x stock）。

        参数：
            price_df: 价格数据 DataFrame，至少包含 date/code/close 列。
        返回：
            pd.DataFrame: index=日期，columns=股票代码，values=收盘价。
        """
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        required = [date_col, code_col, price_col]
        for col in required:
            if col not in price_df.columns:
                return pd.DataFrame()

        df = price_df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df[code_col] = df[code_col].astype(str)
        df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
        df = df.dropna(subset=required)

        if df.empty:
            return pd.DataFrame()

        price_table = df.pivot_table(
            index=date_col,
            columns=code_col,
            values=price_col,
            aggfunc="last"
        ).sort_index()
        return price_table

    # ─── 持仓字典标准化 ───

    @staticmethod
    def normalize_holdings(holdings_dict):
        """
        标准化调仓字典的日期索引。

        参数：
            holdings_dict: {date_str: [stock_codes]} 或 {Timestamp: [...]}
        返回：
            Dict[pd.Timestamp, List[str]]
        """
        result = {}
        if holdings_dict is None:
            return result
        for k, v in holdings_dict.items():
            dt = pd.to_datetime(k, errors="coerce")
            if pd.isna(dt):
                continue
            stocks = [str(x) for x in v] if v is not None else []
            result[dt] = stocks
        return result

    # ─── 估值价格获取 ───

    def _get_valuation_price(self, code, current_date, price_table):
        """
        获取某股票在当前日期的估值价格。
        - 若有当日价格，使用当日价格并更新 last_prices；
        - 若无（停牌），使用上次可用价格；
        - 若从未有过价格，返回 None。
        """
        px = None
        if code in price_table.columns and current_date in price_table.index:
            px = price_table.at[current_date, code]
            if pd.notna(px):
                px = float(px)
                self.last_prices[code] = px
                return px
        if code in self.last_prices:
            return float(self.last_prices[code])
        return None

    # ─── 交易记录 ───

    def _record_trade(self, trade_date, code, side, shares, price, amount, commission):
        self.trade_logs.append({
            "date": trade_date,
            "code": code,
            "side": side,
            "shares": float(shares),
            "price": float(price),
            "amount": float(amount),
            "commission": float(commission)
        })

    # ─── 调仓执行 ───

    def _rebalance(self, current_date, target_stocks, price_table, weight_mode="equal"):
        """
        在调仓日执行组合调仓。

        参数：
            current_date: 当前交易日
            target_stocks: 目标持仓股票列表
            price_table: 收盘价宽表
            weight_mode: "equal" 等权 / "market_cap" 市值加权(暂用等权)
        """
        target_set = set(str(s) for s in (target_stocks or []))
        current_set = set(self.positions.keys())

        # 1) 卖出不再持有的股票
        to_sell = list(current_set - target_set)
        for code in to_sell:
            shares = float(self.positions.get(code, 0.0))
            if shares <= 0:
                continue
            px = self._get_valuation_price(code, current_date, price_table)
            has_price = (
                code in price_table.columns
                and current_date in price_table.index
                and pd.notna(price_table.at[current_date, code])
            )
            if not has_price or px is None or px <= 0:
                continue
            amount = shares * px
            commission = amount * self.commission_rate
            self.cash += (amount - commission)
            self.positions.pop(code, None)
            self._record_trade(current_date, code, "SELL", shares, px, amount, commission)

        # 2) 计算当前总资产
        portfolio_value = 0.0
        for code, shares in self.positions.items():
            px = self._get_valuation_price(code, current_date, price_table)
            if px is not None and px > 0:
                portfolio_value += float(shares) * px
        total_asset = self.cash + portfolio_value

        if len(target_set) == 0:
            return

        target_each_value = total_asset / float(len(target_set))

        # 3) 对目标股票逐只调整仓位
        for code in target_set:
            px = self._get_valuation_price(code, current_date, price_table)
            has_price = (
                code in price_table.columns
                and current_date in price_table.index
                and pd.notna(price_table.at[current_date, code])
            )
            if px is None or px <= 0 or not has_price:
                continue

            current_shares = float(self.positions.get(code, 0.0))
            current_value = current_shares * px
            diff_value = target_each_value - current_value

            if diff_value > 0:
                max_buy_amount = self.cash / (1.0 + self.commission_rate)
                buy_amount = min(diff_value, max_buy_amount)
                if buy_amount <= 0:
                    continue
                buy_shares = buy_amount / px
                commission = buy_amount * self.commission_rate
                self.cash -= (buy_amount + commission)
                self.positions[code] = current_shares + buy_shares
                self._record_trade(current_date, code, "BUY", buy_shares, px, buy_amount, commission)

            elif diff_value < 0:
                sell_amount_target = -diff_value
                max_sell_amount = current_shares * px
                sell_amount = min(sell_amount_target, max_sell_amount)
                if sell_amount <= 0:
                    continue
                sell_shares = sell_amount / px
                commission = sell_amount * self.commission_rate
                self.cash += (sell_amount - commission)
                new_shares = current_shares - sell_shares
                if new_shares <= 1e-12:
                    self.positions.pop(code, None)
                else:
                    self.positions[code] = new_shares
                self._record_trade(current_date, code, "SELL", sell_shares, px, sell_amount, commission)

    # ─── 盯市估值 ───

    def _mark_to_market(self, current_date, price_table):
        portfolio_value = 0.0
        for code, shares in self.positions.items():
            px = self._get_valuation_price(code, current_date, price_table)
            if px is not None and px > 0:
                portfolio_value += float(shares) * px
        total_asset = self.cash + portfolio_value
        return portfolio_value, total_asset

    # ─── 主运行流程 ───

    def run(self, price_data, holdings_dict, benchmark_df=None,
            price_col="close", code_col="code", date_col="date"):
        """
        运行回测主流程。

        参数：
            price_data: 价格数据长表 DataFrame
            holdings_dict: 调仓日目标持仓字典 {date: [codes]}
            benchmark_df: 基准数据（对齐日期范围用，可选）
            price_col: 价格列名
            code_col: 代码列名
            date_col: 日期列名

        返回：无，结果通过 get_results() 获取。
        """
        price_table = self.build_price_table(
            price_data, code_col=code_col, date_col=date_col, price_col=price_col
        )
        if price_table.empty:
            raise ValueError("无法构建有效价格矩阵，请检查数据列。")

        holdings_norm = self.normalize_holdings(holdings_dict)
        rebalance_dates = set(holdings_norm.keys())

        trading_dates = price_table.index

        # 可选：与基准日期对齐
        if benchmark_df is not None and isinstance(benchmark_df, pd.DataFrame) and not benchmark_df.empty:
            if "date" in benchmark_df.columns:
                bench_dates = pd.to_datetime(benchmark_df["date"], errors="coerce").dropna().unique()
                bench_dates = pd.DatetimeIndex(bench_dates)
                common_dates = trading_dates.intersection(bench_dates)
                if len(common_dates) > 0:
                    trading_dates = common_dates

        for dt in trading_dates:
            if dt in rebalance_dates:
                target = holdings_norm.get(dt, [])
                self._rebalance(dt, target, price_table)

            portfolio_value, total_asset = self._mark_to_market(dt, price_table)
            net_value = total_asset / self.initial_cash if self.initial_cash > 0 else np.nan

            self.records.append({
                "date": dt,
                "cash": float(self.cash),
                "portfolio_value": float(portfolio_value),
                "total_asset": float(total_asset),
                "net_value": float(net_value),
                "positions_count": int(len(self.positions))
            })

    def get_results(self):
        """
        获取回测结果。

        返回：
            dict: {
                "daily_records": 每日记录 DataFrame,
                "net_value": 净值 DataFrame(date, net_value),
                "trade_logs": 交易日志 DataFrame
            }
        """
        daily_records = pd.DataFrame(self.records)
        if not daily_records.empty and "date" in daily_records.columns:
            daily_records = daily_records.sort_values("date").reset_index(drop=True)

        net_value_df = (
            daily_records[["date", "net_value"]].copy()
            if not daily_records.empty
            else pd.DataFrame(columns=["date", "net_value"])
        )

        trade_logs_df = pd.DataFrame(self.trade_logs)
        if not trade_logs_df.empty and "date" in trade_logs_df.columns:
            trade_logs_df = trade_logs_df.sort_values("date").reset_index(drop=True)

        return {
            "daily_records": daily_records,
            "net_value": net_value_df,
            "trade_logs": trade_logs_df
        }
