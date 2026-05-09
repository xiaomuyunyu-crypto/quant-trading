# -*- coding: utf-8 -*-
# 策略回测 API 路由

from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from backend.models.backtest import (
    BacktestRequest, BacktestResultModel, TradeItem, EquityPoint,
    StrategyInfo,
)
from backend.core.backtest_engine import run_backtest
from backend.core.kline_utils import get_klines_df

router = APIRouter(prefix="/backtest", tags=["策略回测"])


# ─── 预存策略定义 ───

PRESET_STRATEGIES: list[dict] = [
    # 单指标策略
    {"key": "macd_daily", "name": "MACD金叉死叉-日线", "desc": "日线MACD金叉买入，死叉卖出",
     "category": "单指标", "params": {}},
    {"key": "macd_hist", "name": "MACD柱趋势", "desc": "绿柱从最低点回升3天买入，红柱连续2天缩短卖出",
     "category": "单指标", "params": {}},
    {"key": "macd_weekly", "name": "MACD周线趋势", "desc": "周线MACD金叉买入，死叉卖出",
     "category": "单指标", "params": {}},
    {"key": "rsi_oversold", "name": "RSI极值反转", "desc": "连续3日<20或连续2日<16买入；单日>92或连续2日>85卖出",
     "category": "单指标", "params": {}},
    {"key": "ma_cross", "name": "双均线交叉(5,20)", "desc": "MA5上穿MA20买入，下穿MA20卖出",
     "category": "单指标", "params": {}},
    # 组件化组合策略
    {"key": "composite_majority", "name": "四维多数表决", "desc": "MACD+RSI+均线+量价，多数表决决定买卖",
     "category": "组合策略", "params": {"signal_mode": "majority"}},
    {"key": "composite_weighted", "name": "四维加权评分", "desc": "四指标按置信度加权，综合判定买卖信号",
     "category": "组合策略", "params": {"signal_mode": "weighted"}},
    {"key": "composite_consensus", "name": "四维全票一致", "desc": "四个指标全部同意才出信号，追求高胜率",
     "category": "组合策略", "params": {"signal_mode": "consensus"}},
    {"key": "composite_mtf", "name": "四维多周期", "desc": "日/周/月三周期分别分析，加权汇总",
     "category": "组合策略", "params": {"signal_mode": "majority", "multi_timeframe": True}},
    {"key": "triple_macd_ma250", "name": "三周期MACD+MA250状态机",
     "desc": "月线MACD过滤→MA250趋势边界→周线窗口→日线执行，八状态状态机",
     "category": "高级策略", "params": {}},
]


@router.post("", response_model=BacktestResultModel)
def execute_backtest(req: BacktestRequest):
    """执行单股回测"""
    # 处理日期：优先用 start_date/end_date，否则根据 days 回溯
    start_date = req.start_date
    end_date = req.end_date
    if req.days and not start_date:
        from datetime import datetime, timedelta
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=req.days)
        end_date = end_dt.strftime("%Y%m%d")
        start_date = start_dt.strftime("%Y%m%d")

    df = get_klines_df(req.code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {req.code} 在指定区间无K线数据")

    result = run_backtest(df, req.code, strategy=req.strategy, initial_capital=req.initial_capital)

    # 权益曲线加入信号标记（前端直接用来标注买卖点）
    trade_dates = {t.date[:10]: t.action for t in result.trades}
    equity_with_signals = []
    for p in result.equity_curve:
        d = p["date"][:10] if len(p["date"]) > 10 else p["date"]
        signal_marker = trade_dates.get(d, "")
        equity_with_signals.append(
            EquityPoint(date=d, equity=p["equity"], signal=signal_marker)
        )

    return BacktestResultModel(
        code=result.code,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        total_return=result.total_return,
        max_drawdown=result.max_drawdown,
        total_trades=result.total_trades,
        strategy_name=_strategy_display_name(result.strategy_name),
        equity_curve=equity_with_signals,
        trades=[TradeItem(
            date=t.date, code=t.code, action=t.action,
            price=t.price, shares=t.shares, amount=t.amount,
            reason=t.reason,
        ) for t in result.trades],
    )


@router.get("/compare")
def compare_strategies(
    code: str = Query(..., description="股票代码"),
    days: int = Query(default=365, ge=30, description="回测天数"),
    initial_capital: float = Query(default=10000.0),
):
    """一支股票同时跑全部策略 → 排名对比"""
    from datetime import datetime, timedelta
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start_date = start_dt.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")

    df = get_klines_df(code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {code} 无K线数据")

    results = []
    for s in PRESET_STRATEGIES:
        try:
            r = run_backtest(df, code, strategy=s["key"], initial_capital=initial_capital)
            results.append({
                "key": s["key"],
                "name": s["name"],
                "category": s["category"],
                "total_return": r.total_return,
                "total_return_pct": round(r.total_return * 100, 2),
                "max_drawdown": r.max_drawdown,
                "max_drawdown_pct": round(r.max_drawdown * 100, 2),
                "total_trades": r.total_trades,
                "final_equity": r.final_equity,
                "equity_curve": r.equity_curve,
                "calmar": round(r.total_return / abs(r.max_drawdown), 2) if r.max_drawdown != 0 else 0,
            })
        except Exception:
            continue

    # 排除零交易策略，按收益率排名
    traded = [r for r in results if r["total_trades"] > 0]
    no_trades = [r for r in results if r["total_trades"] == 0]
    traded.sort(key=lambda x: x["total_return"], reverse=True)

    all_ranked = traded + no_trades
    for i, r in enumerate(all_ranked):
        r["rank"] = i + 1

    return {
        "code": code,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "total_strategies": len(all_ranked),
        "has_trades": len(traded),
        "best": traded[0] if traded else None,
        "results": all_ranked,
    }


@router.get("/optimize")
def optimize_parameters(
    code: str = Query(..., description="股票代码"),
    strategy: str = Query(default="ma_cross", description="优化策略key"),
    days: int = Query(default=365, ge=30),
    initial_capital: float = Query(default=10000.0),
):
    """网格搜索最优参数"""
    from datetime import datetime, timedelta
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start_date = start_dt.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")

    df = get_klines_df(code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {code} 无K线数据")

    results = []

    if strategy == "ma_cross":
        for fast in [3, 5, 7, 10, 13]:
            for slow in [15, 20, 25, 30, 40]:
                if fast >= slow:
                    continue
                try:
                    from backend.core.backtest_engine import (
                        _generate_strategy_signals_by_params,
                        run_backtest_with_signals,
                    )
                    signals = _generate_strategy_signals_by_params(df, "ma_cross",
                                                                   fast=fast, slow=slow)
                    r = run_backtest_with_signals(df, code, signals, "ma_cross",
                                                  initial_capital=initial_capital)
                    results.append({
                        "params": f"MA{fast}/MA{slow}",
                        "fast": fast, "slow": slow,
                        "total_return_pct": round(r.total_return * 100, 2),
                        "max_drawdown_pct": round(r.max_drawdown * 100, 2),
                        "total_trades": r.total_trades,
                    })
                except Exception:
                    continue

    elif strategy == "macd_daily":
        for fast in [8, 10, 12, 14]:
            for slow in [20, 24, 26, 28, 30]:
                for sig in [7, 9, 11]:
                    try:
                        from backend.core.backtest_engine import (
                            _generate_strategy_signals_by_params,
                            run_backtest_with_signals,
                        )
                        signals = _generate_strategy_signals_by_params(
                            df, "macd_daily", fast=fast, slow=slow, signal=sig)
                        r = run_backtest_with_signals(df, code, signals, "macd_daily",
                                                      initial_capital=initial_capital)
                        results.append({
                            "params": f"MACD({fast},{slow},{sig})",
                            "fast": fast, "slow": slow, "signal": sig,
                            "total_return_pct": round(r.total_return * 100, 2),
                            "max_drawdown_pct": round(r.max_drawdown * 100, 2),
                            "total_trades": r.total_trades,
                        })
                    except Exception:
                        continue

    results.sort(key=lambda x: x["total_return_pct"], reverse=True)

    return {
        "code": code, "strategy": strategy,
        "total_combinations": len(results),
        "top5": results[:5],
        "all": results,
    }


@router.get("/strategies")
def list_strategies():
    """获取可用策略列表（含分组）"""
    return {
        "total": len(PRESET_STRATEGIES),
        "categories": [
            {"name": "单指标", "strategies": [s for s in PRESET_STRATEGIES if s["category"] == "单指标"]},
            {"name": "组合策略", "strategies": [s for s in PRESET_STRATEGIES if s["category"] == "组合策略"]},
            {"name": "高级策略", "strategies": [s for s in PRESET_STRATEGIES if s["category"] == "高级策略"]},
        ],
    }


def _strategy_display_name(key: str) -> str:
    for strategy in PRESET_STRATEGIES:
        if strategy["key"] == key:
            return strategy["name"]
    return key
