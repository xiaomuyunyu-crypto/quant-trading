# -*- coding: utf-8 -*-
# 数据清洗模块

import pandas as pd
import numpy as np
from datetime import datetime


def clean_stock_list(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗股票列表
    - 去重、code标准化
    - 剔除ST/*ST/退市股票
    """
    df = df.copy()
    df["code"] = df["code"].astype(str).str.strip().str.zfill(6)
    df = df.drop_duplicates(subset=["code"], keep="last")
    df = df[~df["name"].str.contains(r"^\*?ST", na=False)]
    df = df.dropna(subset=["code", "name"])
    return df.reset_index(drop=True)


def clean_kline(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗K线数据
    - 去重、填缺、剔异常、排序
    """
    df = df.copy()
    if df.empty:
        return df

    df["code"] = df["code"].astype(str).str.strip().str.zfill(6)
    df = df.drop_duplicates(subset=["code", "date"], keep="last")

    price_cols = ["open", "high", "low", "close"]
    for c in price_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    mask = (df[price_cols] > 0).all(axis=1) & (df["volume"] >= 0)
    df = df[mask]

    df[price_cols] = df.groupby("code")[price_cols].ffill()
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    return df


def clean_fund_flow(df: pd.DataFrame) -> pd.DataFrame:
    """清洗资金流向数据"""
    df = df.copy()
    if df.empty:
        return df
    df["code"] = df["code"].astype(str).str.zfill(6)
    df = df.drop_duplicates(subset=["code", "date"], keep="last")
    flow_cols = ["main_net_inflow", "super_large_net_inflow",
                 "large_net_inflow", "medium_net_inflow", "small_net_inflow"]
    for c in flow_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df = df.dropna(subset=["code", "date"])
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    return df


def clean_financials(df: pd.DataFrame) -> pd.DataFrame:
    """清洗财务指标数据"""
    df = df.copy()
    if df.empty:
        return df
    df["code"] = df["code"].astype(str).str.zfill(6)
    df = df.drop_duplicates(subset=["code", "report_date"], keep="last")
    df = df.dropna(subset=["code", "report_date"])
    df = df.sort_values(["code", "report_date"]).reset_index(drop=True)
    return df


def clean_industry_list(df: pd.DataFrame) -> pd.DataFrame:
    """清洗行业板块列表"""
    df = df.copy()
    if df.empty:
        return df
    df["code"] = df["code"].astype(str)
    df = df.drop_duplicates(subset=["code"], keep="last")
    df = df.dropna(subset=["code", "name"])
    return df.reset_index(drop=True)


def fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """填充缺失值：数值列填0，字符串列填空字符串"""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna("")
    return df
