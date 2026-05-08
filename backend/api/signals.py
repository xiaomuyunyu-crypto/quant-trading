# -*- coding: utf-8 -*-
# 信号系统 API 路由

from fastapi import APIRouter, HTTPException, Query

from backend.models.signals import SignalResultModel, SignalWeights
from backend.core.signal_engine import generate_signal

router = APIRouter(prefix="/signals", tags=["信号系统"])

_default_weights = SignalWeights()


# ─── 权重配置（需要放在 /{code} 之前避免路由冲突）───

@router.get("/weights", response_model=SignalWeights)
def get_weights():
    return _default_weights


@router.put("/weights", response_model=SignalWeights)
def update_weights(weights: SignalWeights):
    global _default_weights
    total = weights.daily_weight + weights.weekly_weight + weights.monthly_weight
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="权重之和必须等于1")
    _default_weights = weights
    return _default_weights


# ─── 信号查询 ───

@router.get("")
def list_signals(
    code: str | None = Query(default=None, description="股票代码"),
    signal_type: str | None = Query(default=None, description="信号类型 BUY/SELL/HOLD"),
):
    """获取自选股信号列表"""
    items = []
    codes = _get_watchlist_codes()

    if code:
        codes = [code] if code in codes else [code]

    if not codes:
        codes = ["000001"]

    for c in codes[:20]:
        try:
            df = get_klines_df(c)
            if df is None or df.empty:
                continue
            result = generate_signal(df, c)
            if signal_type and result.signal_type != signal_type:
                continue
            items.append(result)
        except Exception:
            continue

    return {"total": len(items), "items": items}


@router.get("/{code}", response_model=SignalResultModel)
def get_signal_detail(
    code: str,
    daily_weight: float = Query(default=0.5, description="日线权重"),
    weekly_weight: float = Query(default=0.3, description="周线权重"),
    monthly_weight: float = Query(default=0.2, description="月线权重"),
):
    """查询某只股票的综合信号"""
    df = get_klines_df(code)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {code} 无K线数据")

    result = generate_signal(
        df, code,
        daily_weight=daily_weight,
        weekly_weight=weekly_weight,
        monthly_weight=monthly_weight,
    )
    return result


# ─── 工具函数 ───

def _get_watchlist_codes() -> list[str]:
    from data.storage.database import get_session
    from data.storage.models_orm import WatchlistModel
    from sqlalchemy import select
    with get_session() as session:
        rows = session.execute(select(WatchlistModel)).scalars().all()
        return [r.code for r in rows]


def get_klines_df(code: str):
    """获取某股票的日线DataFrame（委托公共工具）"""
    from backend.core.kline_utils import get_klines_df as _get
    return _get(code)
