# -*- coding: utf-8 -*-
"""
策略绩效分析模块。

参考 GitHub: yikheichoi5217/multifactor_strategy 的绩效模块，
并融合 quantstats(PyPI: ranaroussi/quantstats) 的设计理念。

功能：
1. 回测指标计算（收益、风险、超额、胜率等）
2. 净值曲线、回撤曲线、月度收益热力图绘制
3. 策略与基准对比分析
"""

from __future__ import division

import os
from typing import Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 尝试设置中文字体
try:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei"]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

# 年化交易天数
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.03


# ═══════════════════════════════════════════
# 数据转换工具
# ═══════════════════════════════════════════

def to_net_value_series(data) -> pd.Series:
    """
    将输入统一转换为净值序列（DatetimeIndex + float）。

    支持：
    - pd.Series（index=日期，values=净值）
    - pd.DataFrame（含 date + net_value 列，或 date + close 列）
    """
    if data is None:
        return pd.Series(dtype=float)

    if isinstance(data, pd.Series):
        s = pd.to_numeric(data, errors="coerce")
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()].sort_index()
        return s.dropna()

    if isinstance(data, pd.DataFrame):
        df = data.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
            if "net_value" in df.columns:
                s = pd.to_numeric(df["net_value"], errors="coerce")
                s.index = df["date"]
                return s.sort_index().dropna()
            if "close" in df.columns:
                close = pd.to_numeric(df["close"], errors="coerce")
                close.index = df["date"]
                close = close.sort_index().dropna()
                if close.empty:
                    return pd.Series(dtype=float)
                return close / close.iloc[0]
        if "net_value" in df.columns:
            s = pd.to_numeric(df["net_value"], errors="coerce")
            if "date" in df.columns:
                s.index = pd.to_datetime(df["date"])
            return s.sort_index().dropna()

    return pd.Series(dtype=float)


# ═══════════════════════════════════════════
# 核心绩效指标计算
# ═══════════════════════════════════════════

def calculate_metrics(net_value, benchmark=None, risk_free_rate=RISK_FREE_RATE) -> Dict[str, float]:
    """
    计算策略绩效指标。

    参数：
        net_value: 策略净值序列 (pd.Series 或含 date/net_value 的 DataFrame)
        benchmark: 基准净值序列（可选）
        risk_free_rate: 无风险利率，默认 0.03

    返回：
        Dict[str, float]: 指标字典，包含：
            - 累计收益率、年化收益率、年化波动率
            - 夏普比率、最大回撤、Calmar比率
            - 盈亏比、胜率（日频）
            - 超额收益、信息比率、月度胜率（需提供 benchmark）
    """
    strat_nv = to_net_value_series(net_value)
    bench_nv = to_net_value_series(benchmark) if benchmark is not None else pd.Series(dtype=float)

    if strat_nv.empty or len(strat_nv) < 2:
        return {}

    # 对齐日期
    if not bench_nv.empty:
        common_idx = strat_nv.index.intersection(bench_nv.index)
        if len(common_idx) > 1:
            strat_nv = strat_nv.reindex(common_idx).dropna()
            bench_nv = bench_nv.reindex(common_idx).dropna()

    ann_factor = TRADING_DAYS_PER_YEAR
    strat_ret = strat_nv.pct_change().dropna()
    if strat_ret.empty:
        return {}

    # ── 绝对收益维度 ──
    cumulative_return = strat_nv.iloc[-1] / strat_nv.iloc[0] - 1.0
    years = float(len(strat_ret)) / float(ann_factor)
    annual_return = (1.0 + cumulative_return) ** (1.0 / years) - 1.0 if years > 0 else np.nan
    annual_vol = strat_ret.std() * np.sqrt(ann_factor)

    sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol and annual_vol > 0 else np.nan

    running_max = strat_nv.cummax()
    drawdown = strat_nv / running_max - 1.0
    max_drawdown = drawdown.min()

    calmar = annual_return / abs(max_drawdown) if max_drawdown and max_drawdown < 0 else np.nan

    # 盈亏比、胜率（日频）
    win_days = (strat_ret > 0).sum()
    lose_days = (strat_ret < 0).sum()
    daily_win_rate = win_days / (win_days + lose_days) if (win_days + lose_days) > 0 else np.nan

    avg_win = strat_ret[strat_ret > 0].mean() if win_days > 0 else 0.0
    avg_loss = abs(strat_ret[strat_ret < 0].mean()) if lose_days > 0 else 0.0
    profit_loss_ratio = avg_win / avg_loss if avg_loss and avg_loss > 0 else np.nan

    # ── 相对基准维度 ──
    excess_cum_return = np.nan
    excess_ann_return = np.nan
    information_ratio = np.nan
    excess_max_drawdown = np.nan
    monthly_win_rate = np.nan

    if not bench_nv.empty and len(bench_nv) >= 2:
        bench_ret = bench_nv.pct_change().dropna()
        common = strat_ret.index.intersection(bench_ret.index)
        if len(common) > 1:
            sr = strat_ret.reindex(common).dropna()
            br = bench_ret.reindex(common).dropna()
            common2 = sr.index.intersection(br.index)
            sr = sr.reindex(common2)
            br = br.reindex(common2)

            if len(common2) > 1:
                excess_r = sr - br
                te = excess_r.std() * np.sqrt(ann_factor)
                if te and te > 0:
                    information_ratio = (excess_r.mean() * ann_factor) / te

                excess_nv = (1.0 + excess_r).cumprod()
                excess_cum_return = excess_nv.iloc[-1] - 1.0
                yrs_ex = float(len(excess_r)) / float(ann_factor)
                if yrs_ex > 0:
                    excess_ann_return = (1.0 + excess_cum_return) ** (1.0 / yrs_ex) - 1.0

                ex_running_max = excess_nv.cummax()
                ex_dd = excess_nv / ex_running_max - 1.0
                excess_max_drawdown = ex_dd.min()

                # 月度胜率
                sm = strat_nv.resample("M").last().pct_change().dropna()
                bm = bench_nv.resample("M").last().pct_change().dropna()
                mi = sm.index.intersection(bm.index)
                if len(mi) > 0:
                    win = (sm.reindex(mi) > bm.reindex(mi)).sum()
                    monthly_win_rate = float(win) / float(len(mi))

    return {
        "累计收益率": float(cumulative_return),
        "年化收益率": float(annual_return) if pd.notna(annual_return) else np.nan,
        "年化波动率": float(annual_vol) if pd.notna(annual_vol) else np.nan,
        "夏普比率": float(sharpe) if pd.notna(sharpe) else np.nan,
        "最大回撤": float(max_drawdown) if pd.notna(max_drawdown) else np.nan,
        "Calmar比率": float(calmar) if pd.notna(calmar) else np.nan,
        "日胜率": float(daily_win_rate) if pd.notna(daily_win_rate) else np.nan,
        "盈亏比": float(profit_loss_ratio) if pd.notna(profit_loss_ratio) else np.nan,
        "超额累计收益": float(excess_cum_return) if pd.notna(excess_cum_return) else np.nan,
        "超额年化收益": float(excess_ann_return) if pd.notna(excess_ann_return) else np.nan,
        "信息比率": float(information_ratio) if pd.notna(information_ratio) else np.nan,
        "超额最大回撤": float(excess_max_drawdown) if pd.notna(excess_max_drawdown) else np.nan,
        "月度胜率": float(monthly_win_rate) if pd.notna(monthly_win_rate) else np.nan,
    }


def print_metrics(metrics: Dict[str, float]):
    """格式化打印绩效指标。"""
    print("\n" + "=" * 50)
    print("  策略绩效指标")
    print("=" * 50)
    for k, v in metrics.items():
        if isinstance(v, float) and not np.isnan(v):
            if "率" in k or "收益" in k or "回撤" in k:
                print(f"  {k}: {v:.4%}")
            else:
                print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: N/A")
    print("=" * 50)


# ═══════════════════════════════════════════
# 可视化
# ═══════════════════════════════════════════

def plot_net_value(net_value, benchmark=None, title="策略净值曲线", save_path=None):
    """绘制策略净值与基准对比图。"""
    strat_nv = to_net_value_series(net_value)
    if strat_nv.empty:
        print("[警告] 净值数据为空，无法绘图。")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(strat_nv.index, strat_nv.values, label="策略净值", linewidth=1.8, color="#1f77b4")

    if benchmark is not None:
        bench_nv = to_net_value_series(benchmark)
        if not bench_nv.empty:
            idx = strat_nv.index.intersection(bench_nv.index)
            if len(idx) > 0:
                ax.plot(idx, bench_nv.reindex(idx).values, label="基准净值",
                        linewidth=1.5, color="#ff7f0e", alpha=0.8)

    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("净值")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_drawdown(net_value, title="回撤曲线", save_path=None):
    """绘制策略回撤曲线。"""
    strat_nv = to_net_value_series(net_value)
    if strat_nv.empty:
        return

    running_max = strat_nv.cummax()
    drawdown = (strat_nv / running_max - 1.0) * 100

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="tomato", alpha=0.6)
    ax.plot(drawdown.index, drawdown.values, color="red", linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("回撤 (%)")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_yearly_returns(net_value, title="年度收益", save_path=None):
    """绘制年度收益率柱状图。"""
    strat_nv = to_net_value_series(net_value)
    if strat_nv.empty:
        return

    yearly = strat_nv.resample("Y").last().pct_change().dropna()
    if yearly.empty:
        return

    years = [d.year for d in yearly.index]
    vals = [v * 100 for v in yearly.values]
    colors = ["#2ca02c" if v > 0 else "#d62728" for v in yearly.values]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(range(len(years)), vals, color=colors, edgecolor="white")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + (0.5 if val >= 0 else -1.5),
                f"{val:.1f}%", ha="center", va="bottom" if val >= 0 else "top", fontsize=10)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    ax.axhline(y=0, color="black", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("收益率 (%)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_monthly_heatmap(net_value, title="月度收益热力图", save_path=None):
    """绘制月度收益热力图（行=年份，列=月份）。"""
    strat_nv = to_net_value_series(net_value)
    if strat_nv.empty:
        return

    monthly_ret = strat_nv.resample("M").last().pct_change().dropna()
    if monthly_ret.empty:
        return

    hm_df = pd.DataFrame({
        "year": monthly_ret.index.year,
        "month": monthly_ret.index.month,
        "ret": monthly_ret.values
    })
    pivot = hm_df.pivot(index="year", columns="month", values="ret")

    try:
        import seaborn as sns
    except ImportError:
        print("[警告] seaborn 未安装，无法绘制热力图。")
        return

    fig, ax = plt.subplots(figsize=(12, 4 + max(1, len(pivot) * 0.3)))
    sns.heatmap(pivot, annot=True, fmt=".1%", cmap="RdYlGn", center=0,
                cbar_kws={"label": "月度收益率"}, ax=ax)
    ax.set_title(title)
    ax.set_xlabel("月份")
    ax.set_ylabel("年份")
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150)
    plt.close(fig)
