# -*- coding: utf-8 -*-
# 策略回测 API 路由

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from backend.models.backtest import (
    BacktestRequest, BacktestResultModel, TradeItem, EquityPoint,
    StrategyInfo,
)
from backend.core.backtest_engine import run_backtest, generate_strategy_diagnostics
from backend.core.kline_utils import get_klines_df, get_klines_with_meta

router = APIRouter(prefix="/backtest", tags=["策略回测"])

DEFAULT_BACKTEST_DAYS = 3000
MAX_BACKTEST_DAYS = 15000
FULL_HISTORY_START = "19900101"


# ─── 预存策略定义 ───

PRESET_STRATEGIES: list[dict] = [
    {"key": "triple_macd_ma250", "name": "原策略：月线+MA250+周线+日线",
     "desc": "保留当前规则：月线MACD过滤，MA250长期开关，周线窗口，日线MACD执行",
     "category": "MACD逐级松绑", "params": {"level": 0}},
    {"key": "triple_macd_no_monthly", "name": "松绑1：去掉月线MACD控制",
     "desc": "不再用月线MACD限制买卖，保留MA250、周线窗口和日线MACD执行",
     "category": "MACD逐级松绑", "params": {"level": 1}},
    {"key": "triple_macd_no_monthly_no_ma250", "name": "松绑2：再去掉MA250控制",
     "desc": "去掉月线MACD和MA250过滤，保留周线窗口，日线MACD执行",
     "category": "MACD逐级松绑", "params": {"level": 2}},
    {"key": "triple_macd_daily_only", "name": "松绑3：仅日线MACD执行",
     "desc": "去掉月线、MA250、周线控制，只按日线MACD金叉买入、死叉卖出",
     "category": "MACD逐级松绑", "params": {"level": 3}},
    {"key": "weekly_macd_cross", "name": "周线MACD金叉/死叉",
     "desc": "周线MACD出现金叉买入，出现死叉卖出",
     "category": "周线策略", "params": {"level": 4}},
]


@router.post("", response_model=BacktestResultModel)
def execute_backtest(req: BacktestRequest):
    """执行单股回测"""
    # 处理日期：优先显式日期，其次上市以来，最后默认回溯3000天。
    start_date, end_date = _resolve_backtest_range(
        start_date=req.start_date,
        end_date=req.end_date,
        days=req.days,
        full_history=req.full_history,
    )

    kline_result = get_klines_with_meta(req.code, start_date=start_date, end_date=end_date)
    df = kline_result.df
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {req.code} 在指定区间无K线数据")

    result = run_backtest(df, req.code, strategy=req.strategy, initial_capital=req.initial_capital)
    strategy_diagnostics = generate_strategy_diagnostics(df, req.strategy)
    diagnostics = {
        "kline": kline_result.to_dict(),
        "strategy": strategy_diagnostics,
        "requested_days": req.days,
        "full_history": req.full_history,
    }
    warnings = list(kline_result.warnings)
    if result.total_trades == 0:
        warnings.append(strategy_diagnostics.get("primary_reason") or "该区间没有触发买卖信号")

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
        requested_start_date=start_date,
        requested_end_date=end_date,
        data_source=kline_result.data_source,
        data_points=len(df),
        actual_data_start_date=kline_result.actual_start_date,
        actual_data_end_date=kline_result.actual_end_date,
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
        diagnostics=diagnostics,
        warnings=warnings,
    )


@router.get("/compare")
def compare_strategies(
    code: str = Query(..., description="股票代码"),
    days: int = Query(default=DEFAULT_BACKTEST_DAYS, ge=30, le=MAX_BACKTEST_DAYS, description="回测天数"),
    initial_capital: float = Query(default=10000.0),
):
    """一支股票同时跑全部策略 → 排名对比"""
    start_date, end_date = _resolve_backtest_range(days=days)

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
    days: int = Query(default=DEFAULT_BACKTEST_DAYS, ge=30, le=MAX_BACKTEST_DAYS),
    initial_capital: float = Query(default=10000.0),
):
    """网格搜索最优参数"""
    start_date, end_date = _resolve_backtest_range(days=days)

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
    categories_order = ["MACD逐级松绑", "周线策略", "我的策略", "单指标", "组合策略"]
    grouped = {}
    for s in PRESET_STRATEGIES:
        cat = s.get("category", "其他")
        grouped.setdefault(cat, []).append(s)
    return {
        "total": len(PRESET_STRATEGIES),
        "categories": [
            {"name": c, "strategies": grouped[c]}
            for c in categories_order if c in grouped
        ],
    }


def _strategy_display_name(key: str) -> str:
    for strategy in PRESET_STRATEGIES:
        if strategy["key"] == key:
            return strategy["name"]
    return key


def _resolve_backtest_range(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    full_history: bool = False,
) -> tuple[str, str]:
    """统一回测日期解析：支持默认3000天与从上市以来回测。"""
    resolved_end = _to_compact_date(end_date) or datetime.now().strftime("%Y%m%d")
    if full_history:
        return FULL_HISTORY_START, resolved_end
    if start_date:
        return _to_compact_date(start_date), resolved_end

    end_dt = pd.to_datetime(resolved_end).to_pydatetime()
    lookback_days = days or DEFAULT_BACKTEST_DAYS
    start_dt = end_dt - timedelta(days=lookback_days)
    return start_dt.strftime("%Y%m%d"), resolved_end


def _to_compact_date(value: str | None) -> str | None:
    if not value:
        return None
    return pd.to_datetime(value).strftime("%Y%m%d")
