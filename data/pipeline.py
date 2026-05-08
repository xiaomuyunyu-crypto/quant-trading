# -*- coding: utf-8 -*-
# ETL Pipeline 入口脚本
# 用法:
#   python -m data.pipeline init                  # 初始化数据库
#   python -m data.pipeline sync-stocks           # 全量同步股票列表
#   python -m data.pipeline sync-klines           # 增量同步日K线
#   python -m data.pipeline sync-industries       # 行业板块+成分股
#   python -m data.pipeline sync-fund-flows       # 资金流向
#   python -m data.pipeline sync-financials       # 财务指标
#   python -m data.pipeline sync-all              # 全量同步

import sys
import argparse
import traceback
import pandas as pd
from datetime import datetime, timedelta

from .storage.database import init_db
from .storage.repository import (
    upsert_stocks, upsert_klines,
    query_stocks, get_latest_trade_date,
    upsert_industries, upsert_industry_stocks,
    upsert_fund_flows, upsert_financials,
)
from .fetcher.akshare_fetcher import (
    fetch_stock_list, fetch_daily_kline,
    fetch_industry_list, fetch_industry_constituents,
    fetch_fund_flow, fetch_financial_indicators,
)
from .cleaner.cleaner import (
    clean_stock_list, clean_kline,
    clean_industry_list, clean_fund_flow, clean_financials,
)


def run_init():
    """初始化数据库"""
    print("初始化数据库...")
    init_db()
    print("数据库初始化完成")


def run_sync_stocks():
    """全量同步A股股票列表"""
    print("获取A股股票列表...")
    raw = fetch_stock_list()
    print(f"  获取到 {len(raw)} 条原始数据")
    clean = clean_stock_list(raw)
    print(f"  清洗后 {len(clean)} 条有效数据")
    n = upsert_stocks(clean)
    print(f"  写入数据库 {n} 条记录")


def run_sync_klines(days_back: int = 365, codes: list[str] | None = None):
    """
    增量同步日K线
    days_back: 向前补多少天数据
    codes: 指定股票代码列表，不指定则拉取已入库的全部股票
    """
    if codes is None:
        existing = query_stocks()
        if existing.empty:
            print("请先同步股票列表: python -m data.pipeline sync-stocks")
            return
        codes = existing["code"].tolist()
        print(f"全量模式，共 {len(codes)} 只股票")

    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    total = 0
    errors = 0

    for i, code in enumerate(codes):
        code = str(code).zfill(6)
        last_date = get_latest_trade_date(code)
        if last_date:
            actual_start = max(
                datetime.strptime(start_date, "%Y%m%d"),
                last_date + timedelta(days=1),
            )
        else:
            actual_start = datetime.strptime(start_date, "%Y%m%d")

        end_dt = datetime.strptime(end_date, "%Y%m%d")
        if actual_start >= end_dt:
            continue

        try:
            raw = fetch_daily_kline(code, start_date=actual_start.strftime("%Y%m%d"), end_date=end_date)
            if raw.empty:
                continue
            clean = clean_kline(raw)
            n = upsert_klines(clean)
            total += n
            if (i + 1) % 100 == 0:
                print(f"  进度: {i + 1}/{len(codes)}, 累计 {total} 条K线")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  {code} 失败: {e}")
                traceback.print_exc()

    print(f"同步完成: {len(codes)} 只股票, {total} 条K线, {errors} 个错误")


def run_sync_industries(fetch_constituents: bool = False):
    """同步行业板块列表，可选拉取成分股"""
    print("获取行业板块列表...")
    raw = fetch_industry_list()
    clean = clean_industry_list(raw)
    n = upsert_industries(clean)
    print(f"  行业板块: {n} 个")

    if fetch_constituents:
        industry_names = clean["name"].tolist()
        print(f"  拉取成分股（共 {len(industry_names)} 个板块）...")
        total_cs = 0
        for i, name in enumerate(industry_names):
            try:
                cs = fetch_industry_constituents(name)
                upsert_industry_stocks(name, cs)
                total_cs += len(cs)
                if (i + 1) % 20 == 0:
                    print(f"    进度: {i + 1}/{len(industry_names)}")
            except Exception as e:
                pass
        print(f"  成分股总计: {total_cs} 条映射")


def run_sync_fund_flows(codes: list[str] | None = None):
    """同步个股资金流向"""
    if codes is None:
        existing = query_stocks()
        if existing.empty:
            print("请先同步股票列表")
            return
        codes = existing["code"].head(50).tolist()
        print(f"测试模式：拉取前 {len(codes)} 只")

    total = 0
    errors = 0
    for code in codes:
        code = str(code).zfill(6)
        try:
            raw = fetch_fund_flow(code)
            if raw.empty:
                continue
            clean = clean_fund_flow(raw)
            n = upsert_fund_flows(clean)
            total += n
        except Exception as e:
            errors += 1
    print(f"资金流向: {total} 条记录, {errors} 个错误")


def run_sync_financials(codes: list[str] | None = None):
    """同步财务指标"""
    if codes is None:
        existing = query_stocks()
        if existing.empty:
            print("请先同步股票列表")
            return
        codes = existing["code"].head(20).tolist()
        print(f"测试模式：拉取前 {len(codes)} 只")

    total = 0
    errors = 0
    for i, code in enumerate(codes):
        code = str(code).zfill(6)
        try:
            raw = fetch_financial_indicators(code)
            if raw.empty:
                continue
            clean = clean_financials(raw)
            n = upsert_financials(clean)
            total += n
        except Exception as e:
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"  进度: {i + 1}/{len(codes)}")
    print(f"财务指标: {total} 条记录, {errors} 个错误")


def run_sync_all(days_back: int = 60):
    """一键全量同步"""
    print("=" * 50)
    print("全量数据同步开始")
    print("=" * 50)

    print("\n[1/5] 股票列表")
    run_sync_stocks()

    print("\n[2/5] 行业板块")
    run_sync_industries(fetch_constituents=False)

    print("\n[3/5] 日K线 (前50只热门股)")
    existing = query_stocks()
    codes = existing["code"].head(50).tolist() if not existing.empty else []
    run_sync_klines(days_back=days_back, codes=codes)

    print("\n[4/5] 资金流向 (前50只)")
    run_sync_fund_flows(codes=codes)

    print("\n[5/5] 财务指标 (前20只)")
    run_sync_financials(codes=codes[:20])

    print("\n" + "=" * 50)
    print("全量同步完成")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="数据管道")
    parser.add_argument(
        "command",
        choices=[
            "init", "sync-stocks", "sync-klines",
            "sync-industries", "sync-fund-flows", "sync-financials",
            "sync-all",
        ],
    )
    parser.add_argument("--days", type=int, default=365, help="K线回溯天数")
    parser.add_argument("--codes", nargs="*", default=None, help="指定股票代码")
    parser.add_argument("--constituents", action="store_true", help="是否拉取成分股")
    args = parser.parse_args()

    if args.command == "init":
        run_init()
    elif args.command == "sync-stocks":
        run_sync_stocks()
    elif args.command == "sync-klines":
        run_sync_klines(days_back=args.days, codes=args.codes)
    elif args.command == "sync-industries":
        run_sync_industries(fetch_constituents=args.constituents)
    elif args.command == "sync-fund-flows":
        run_sync_fund_flows(codes=args.codes)
    elif args.command == "sync-financials":
        run_sync_financials(codes=args.codes)
    elif args.command == "sync-all":
        run_sync_all(days_back=args.days)


if __name__ == "__main__":
    main()
