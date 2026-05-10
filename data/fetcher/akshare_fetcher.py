# -*- coding: utf-8 -*-
# AKShare 数据采集器

from datetime import date, datetime
from typing import Optional
import pandas as pd
import akshare as ak

from ..models import StockBase, KlineData


# ═══ 股票基础信息 ═══

def fetch_stock_list() -> pd.DataFrame:
    """
    获取A股股票列表
    返回: DataFrame [code, name, exchange, industry, list_date]
    """
    try:
        df = ak.stock_info_a_code_name()
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        try:
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={"代码": "code", "名称": "name"})
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame(columns=["code", "name", "exchange"])

    df = df.rename(columns={
        "code": "code",
        "name": "name",
    })

    if "code" not in df.columns or "name" not in df.columns:
        return pd.DataFrame(columns=["code", "name", "exchange"])

    if "exchange" not in df.columns:
        df["exchange"] = df["code"].apply(_guess_exchange)

    df["code"] = df["code"].astype(str).str.zfill(6)

    cols = ["code", "name", "exchange"]
    for c in ["industry", "list_date"]:
        if c in df.columns:
            cols.append(c)
    return df[cols]


# ═══ 实时行情 ═══

def fetch_realtime_quotes() -> pd.DataFrame:
    """
    获取全市场实时行情快照
    返回: DataFrame [code, name, current, change, change_pct, volume, amount,
                     high, low, open, pre_close, turnover, pe, pb]
    """
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns={
        "代码": "code", "名称": "name",
        "最新价": "current", "涨跌额": "change", "涨跌幅": "change_pct",
        "成交量": "volume", "成交额": "amount",
        "最高": "high", "最低": "low", "今开": "open", "昨收": "pre_close",
        "换手率": "turnover", "市盈率-动态": "pe", "市净率": "pb",
    })
    df["code"] = df["code"].astype(str).str.zfill(6)
    cols = ["code", "name", "current", "change", "change_pct",
            "volume", "amount", "high", "low", "open", "pre_close"]
    for c in ["turnover", "pe", "pb"]:
        if c in df.columns:
            cols.append(c)
    return df[cols]


# ═══ K线数据 ═══

def fetch_daily_kline(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """
    获取单只股票日K线数据
    adjust: ""不复权, "qfq"前复权, "hfq"后复权
    返回: DataFrame [code, date, open, high, low, close, volume, amount, frequency]
    """
    symbol = _to_akshare_symbol(code)
    start = start_date or "20150101"
    end = end_date or datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust=adjust,
            timeout=30,
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        try:
            df = ak.fund_etf_hist_sina(symbol=_to_sina_symbol(symbol))
            if df is not None and not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df[
                    (df["date"] >= pd.to_datetime(start))
                    & (df["date"] <= pd.to_datetime(end))
                ]
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        return _empty_kline_frame()
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "date" not in df.columns:
        return _empty_kline_frame()
    df["code"] = code
    df["date"] = pd.to_datetime(df["date"])
    df["frequency"] = "D"
    cols = ["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"]
    return df[[c for c in cols if c in df.columns]]


def fetch_hk_daily_kline(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """
    获取港股日K线数据
    """
    df = ak.stock_hk_hist(
        symbol=code,
        period="daily",
        start_date=start_date or "20150101",
        end_date=end_date or datetime.now().strftime("%Y%m%d"),
        adjust=adjust,
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"])
    rename_map = {
        "日期": "date", "开盘": "open", "最高": "high",
        "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "date" not in df.columns:
        return pd.DataFrame(columns=["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"])
    df["code"] = code
    df["date"] = pd.to_datetime(df["date"])
    df["frequency"] = "D"
    cols = ["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"]
    return df[[c for c in cols if c in df.columns]]


def fetch_minute_kline(
    code: str,
    period: str = "5",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """
    获取分钟级K线（近期数据）
    period: "1", "5", "15", "30", "60"
    """
    symbol = _to_akshare_symbol(code)
    df = ak.stock_zh_a_hist_min_em(
        symbol=symbol,
        period=period,
        adjust=adjust,
    )
    df = df.rename(columns={
        "时间": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    })
    df["code"] = code
    df["date"] = pd.to_datetime(df["date"])
    df["frequency"] = f"{period}m"
    cols = ["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"]
    return df[cols]


# ═══ 行业板块 ═══

def fetch_industry_list() -> pd.DataFrame:
    """
    获取行业板块列表
    返回: DataFrame [code, name]
    """
    df = ak.stock_board_industry_name_em()
    df = df.rename(columns={
        "板块代码": "code",
        "板块名称": "name",
    })
    if "stock_count" not in df.columns:
        df["stock_count"] = 0
    else:
        df = df.rename(columns={"stock_count": "stock_count"})
    cols = [c for c in ["code", "name", "stock_count"] if c in df.columns]
    df["code"] = df["code"].astype(str)
    return df[cols]


def fetch_industry_constituents(industry_name: str) -> pd.DataFrame:
    """
    获取行业板块成分股
    返回: DataFrame [stock_code, stock_name]
    """
    df = ak.stock_board_industry_cons_em(symbol=industry_name)
    df = df.rename(columns={
        "代码": "stock_code",
        "名称": "stock_name",
    })
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    return df[["stock_code", "stock_name"]]


# ═══ 资金流向 ═══

def fetch_fund_flow(code: str) -> pd.DataFrame:
    """
    获取个股资金流向（近期数据）
    返回: DataFrame [code, date, main_net_inflow, super_large_net_inflow,
                     large_net_inflow, medium_net_inflow, small_net_inflow]
    """
    market = _guess_market(code)
    df = ak.stock_individual_fund_flow(stock=str(code).zfill(6), market=market)
    df = df.rename(columns={
        "日期": "date",
        "主力净流入-净额": "main_net_inflow",
        "超大单净流入-净额": "super_large_net_inflow",
        "大单净流入-净额": "large_net_inflow",
        "中单净流入-净额": "medium_net_inflow",
        "小单净流入-净额": "small_net_inflow",
    })
    df["code"] = str(code).zfill(6)
    df["date"] = pd.to_datetime(df["date"])
    flow_cols = ["main_net_inflow", "super_large_net_inflow",
                 "large_net_inflow", "medium_net_inflow", "small_net_inflow"]
    for c in flow_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0.0
    return df[["code", "date"] + flow_cols]


# ═══ 财务指标 ═══

def fetch_financial_indicators(code: str) -> pd.DataFrame:
    """
    获取个股财务指标（同花顺接口，按报告期）
    返回: DataFrame [code, report_date, net_profit, revenue, eps, roe,
                     total_assets, total_equity, gross_margin, net_margin]
    """
    symbol = str(code).zfill(6)
    try:
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    rename_map = {
        "报告期": "report_date",
        "净利润": "net_profit",
        "营业总收入": "revenue",
        "基本每股收益": "eps",
        "净资产收益率": "roe",
        "资产总计": "total_assets",
        "归属母公司股东权益合计": "total_equity",
        "销售毛利率": "gross_margin",
        "销售净利率": "net_margin",
    }
    df = df.rename(columns=rename_map)
    df["code"] = symbol

    keep = ["code", "report_date"]
    for col_name in rename_map.values():
        if col_name != "report_date" and col_name in df.columns:
            keep.append(col_name)

    existing = [c for c in keep if c in df.columns]
    result = df[existing].copy()

    if "report_date" in result.columns:
        result["report_date"] = pd.to_datetime(result["report_date"], errors="coerce")

    for col_name in rename_map.values():
        if col_name in result.columns and col_name not in ("report_date",):
            result[col_name] = pd.to_numeric(result[col_name], errors="coerce")

    return result


# ═══ 内部工具 ═══

def _empty_kline_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["code", "date", "open", "high", "low", "close", "volume", "amount", "frequency"]
    )


def _guess_exchange(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith("6"):
        return "SH"
    if c.startswith(("0", "3")):
        return "SZ"
    if c.startswith(("8", "4")):
        return "BJ"
    return "SZ"


def _guess_market(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith("6"):
        return "sh"
    if c.startswith(("0", "3")):
        return "sz"
    if c.startswith(("8", "4")):
        return "bj"
    return "sz"


def _to_akshare_symbol(code: str) -> str:
    return str(code).zfill(6)


def _to_sina_symbol(code: str) -> str:
    symbol = str(code).zfill(6)
    if symbol.startswith(("5", "6")):
        return f"sh{symbol}"
    return f"sz{symbol}"
