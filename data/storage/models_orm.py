# -*- coding: utf-8 -*-
# SQLAlchemy ORM 模型定义

from datetime import date, datetime
from sqlalchemy import (
    Column, String, Float, Integer, Date, DateTime, Text, Index, JSON,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StockModel(Base):
    """股票基础信息表"""
    __tablename__ = "stocks"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), nullable=False, comment="股票名称")
    exchange = Column(String(4), default="SZ", comment="交易所 SZ/SH/BJ")
    industry = Column(String(100), nullable=True, comment="所属行业")
    list_date = Column(Date, nullable=True, comment="上市日期")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_stock_name", "name"),
    )


class KlineModel(Base):
    """K线行情表"""
    __tablename__ = "klines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    date = Column(DateTime, nullable=False, comment="交易日期")
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0, comment="成交量")
    amount = Column(Float, default=0, comment="成交额")
    frequency = Column(String(10), default="D", comment="周期 D/W/M/5m/15m/60m")

    __table_args__ = (
        Index("idx_kline_code_date", "code", "date", unique=True),
        Index("idx_kline_date", "date"),
    )


class WatchlistModel(Base):
    """自选股表"""
    __tablename__ = "watchlist"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), default="", comment="股票名称")
    tags = Column(JSON, default=list, comment="分组标签")
    notes = Column(Text, nullable=True, comment="用户备注")
    added_at = Column(DateTime, default=datetime.now, comment="添加时间")


class IndustryModel(Base):
    """行业板块表"""
    __tablename__ = "industries"

    code = Column(String(20), primary_key=True, comment="板块代码")
    name = Column(String(100), nullable=False, comment="板块名称")
    stock_count = Column(Integer, default=0, comment="成分股数量")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_industry_name", "name"),
    )


class IndustryStockModel(Base):
    """行业板块-成分股映射表"""
    __tablename__ = "industry_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry_code = Column(String(20), nullable=False, comment="板块代码")
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    stock_name = Column(String(50), default="", comment="股票名称")

    __table_args__ = (
        Index("idx_is_industry", "industry_code"),
        Index("idx_is_stock", "stock_code"),
        Index("idx_is_both", "industry_code", "stock_code", unique=True),
    )


class FundFlowModel(Base):
    """个股资金流向表"""
    __tablename__ = "fund_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    date = Column(DateTime, nullable=False, comment="日期")
    main_net_inflow = Column(Float, default=0, comment="主力净流入")
    super_large_net_inflow = Column(Float, default=0, comment="超大单净流入")
    large_net_inflow = Column(Float, default=0, comment="大单净流入")
    medium_net_inflow = Column(Float, default=0, comment="中单净流入")
    small_net_inflow = Column(Float, default=0, comment="小单净流入")

    __table_args__ = (
        Index("idx_ff_code_date", "code", "date", unique=True),
        Index("idx_ff_date", "date"),
    )


class FinancialModel(Base):
    """财务指标表"""
    __tablename__ = "financials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    report_date = Column(Date, nullable=False, comment="报告期")
    net_profit = Column(Float, nullable=True, comment="净利润")
    revenue = Column(Float, nullable=True, comment="营业总收入")
    eps = Column(Float, nullable=True, comment="每股收益")
    roe = Column(Float, nullable=True, comment="净资产收益率")
    total_assets = Column(Float, nullable=True, comment="总资产")
    total_equity = Column(Float, nullable=True, comment="股东权益")
    gross_margin = Column(Float, nullable=True, comment="毛利率")
    net_margin = Column(Float, nullable=True, comment="净利率")
    extra = Column(JSON, nullable=True, comment="其他指标")

    __table_args__ = (
        Index("idx_fin_code_report", "code", "report_date", unique=True),
    )


# ─── 实盘跟踪 ───

class PaperAccountModel(Base):
    """模拟账户表"""
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), default="模拟账户", comment="账户名称")
    initial_capital = Column(Float, default=10000.0, comment="初始资金")
    cash = Column(Float, default=10000.0, comment="当前现金")
    status = Column(String(20), default="active", comment="active/stopped")
    strategy_key = Column(String(50), nullable=True, comment="使用的策略key")
    created_at = Column(DateTime, default=datetime.now)
    stopped_at = Column(DateTime, nullable=True)


class PaperPositionModel(Base):
    """模拟持仓表"""
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, comment="账户ID")
    code = Column(String(10), nullable=False, comment="股票代码")
    name = Column(String(50), default="", comment="股票名称")
    quantity = Column(Integer, default=0, comment="持仓股数")
    cost_price = Column(Float, default=0.0, comment="成本价")
    current_price = Column(Float, default=0.0, comment="最新价")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_pp_account", "account_id"),
        Index("idx_pp_account_code", "account_id", "code", unique=True),
    )


class PaperTradeModel(Base):
    """模拟交易记录表"""
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, comment="账户ID")
    code = Column(String(10), nullable=False, comment="股票代码")
    action = Column(String(10), nullable=False, comment="BUY/SELL")
    price = Column(Float, nullable=False, comment="成交价")
    quantity = Column(Integer, default=0, comment="股数")
    amount = Column(Float, default=0.0, comment="金额")
    reason = Column(Text, nullable=True, comment="交易理由")
    signal_confidence = Column(Float, default=0.0, comment="信号置信度")
    confirmed = Column(Integer, default=0, comment="0=待确认 1=已确认 2=已拒绝")
    trade_date = Column(DateTime, nullable=False, comment="交易日期")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_pt_account", "account_id"),
        Index("idx_pt_date", "trade_date"),
    )


class PaperSignalModel(Base):
    """信号历史记录表（用于后续修正）"""
    __tablename__ = "paper_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    signal_type = Column(String(10), nullable=False, comment="BUY/SELL/HOLD")
    confidence = Column(Float, default=0.0, comment="置信度")
    composite_score = Column(Float, default=0.0, comment="综合得分")
    reason = Column(Text, nullable=True, comment="信号理由")
    close_price = Column(Float, default=0.0, comment="当日收盘价")
    status = Column(String(20), default="pending", comment="pending/confirmed/rejected/expired")
    account_id = Column(Integer, nullable=True, comment="关联账户ID")
    outcome = Column(String(20), nullable=True, comment="correct/wrong/pending 信号事后验证")
    outcome_days = Column(Integer, nullable=True, comment="事后N天验证")
    generated_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_ps_code_date", "code", "generated_at"),
        Index("idx_ps_account", "account_id"),
    )
