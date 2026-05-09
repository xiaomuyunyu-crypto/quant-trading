# -*- coding: utf-8 -*-
# ETL Pipeline 入口脚本
# 用法:
#   python -m data.pipeline init                  # 初始化数据库
#   python -m data.pipeline sync-stocks           # 全量同步股票列表
#   python -m data.pipeline sync-klines --days 3000 --codes 600309  # 补最近3000天日K线
#   python -m data.pipeline sync-history --codes 600309             # 从上市以来补日K线
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
    query_stocks, get_kline_date_range,
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

FULL_HISTORY_START = "19900101"
DEFAULT_KLINE_DAYS = 3000


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


def run_sync_klines(
    days_back: int | None = DEFAULT_KLINE_DAYS,
    codes: list[str] | None = None,
    full_history: bool = False,
):
    """
    同步日K线，自动补齐历史缺口和最新缺口。
    days_back: 向前补多少天数据；full_history=True 时从可获取最早日期开始。
    codes: 指定股票代码列表，不指定则拉取已入库的全部股票
    """
    if codes is None:
        existing = query_stocks()
        if existing.empty:
            print("请先同步股票列表: python -m data.pipeline sync-stocks")
            return
        codes = existing["code"].tolist()
        print(f"全量模式，共 {len(codes)} 只股票")

    end_dt = datetime.now()
    if full_history:
        target_start = datetime.strptime(FULL_HISTORY_START, "%Y%m%d")
    else:
        target_start = end_dt - timedelta(days=days_back or DEFAULT_KLINE_DAYS)

    start_date = target_start.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")
    mode_name = "上市以来" if full_history else f"最近{days_back or DEFAULT_KLINE_DAYS}天"
    print(f"K线同步范围: {mode_name} ({start_date} ~ {end_date})")

    total = 0
    errors = 0

    for i, code in enumerate(codes):
        code = str(code).zfill(6)
        first_date, last_date = get_kline_date_range(code)
        windows = _build_kline_fetch_windows(target_start, end_dt, first_date, last_date)
        if not windows:
            continue

        try:
            for win_start, win_end in windows:
                raw = fetch_daily_kline(
                    code,
                    start_date=win_start.strftime("%Y%m%d"),
                    end_date=win_end.strftime("%Y%m%d"),
                )
                if raw.empty:
                    continue
                clean = clean_kline(raw)
                total += upsert_klines(clean)
            if (i + 1) % 50 == 0:
                print(f"  进度: {i + 1}/{len(codes)}, 累计 {total} 条K线")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  {code} 失败: {e}")
                traceback.print_exc()

    print(f"同步完成: {len(codes)} 只股票, {total} 条K线, {errors} 个错误")


def _build_kline_fetch_windows(
    target_start: datetime,
    target_end: datetime,
    first_date,
    last_date,
) -> list[tuple[datetime, datetime]]:
    """根据本地覆盖区间计算需要抓取的历史和最新窗口。"""
    if first_date is None or last_date is None:
        return [(target_start, target_end)]

    first_dt = pd.to_datetime(first_date).to_pydatetime()
    last_dt = pd.to_datetime(last_date).to_pydatetime()
    windows: list[tuple[datetime, datetime]] = []

    if first_dt > target_start + timedelta(days=1):
        windows.append((target_start, first_dt - timedelta(days=1)))
    if last_dt < target_end - timedelta(days=1):
        windows.append((last_dt + timedelta(days=1), target_end))

    return [(start, end) for start, end in windows if start < end]


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
            "sync-all", "sync-history",
        ],
    )
    parser.add_argument("--days", type=int, default=DEFAULT_KLINE_DAYS, help="K线回溯天数")
    parser.add_argument("--codes", nargs="*", default=None, help="指定股票代码")
    parser.add_argument("--full-history", action="store_true", help="从可获取最早日期同步日K线")
    parser.add_argument("--constituents", action="store_true", help="是否拉取成分股")
    args = parser.parse_args()

    if args.command == "init":
        run_init()
    elif args.command == "sync-stocks":
        run_sync_stocks()
    elif args.command == "sync-klines":
        run_sync_klines(days_back=args.days, codes=args.codes, full_history=args.full_history)
    elif args.command == "sync-history":
        run_sync_klines(days_back=None, codes=args.codes, full_history=True)
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
