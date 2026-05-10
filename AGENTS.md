# AGENTS.md — 量化交易系统开发手册

## 项目概述

个人量化交易辅助系统（v0.1 MVP），支持自选股管理、策略回测、实盘模拟。基于 AI Agent 多窗口协作开发。

## 环境

- **OS**: Windows 11
- **Python**: 3.12+
- **后端**: FastAPI + Uvicorn + Pydantic 2.x + SQLAlchemy 2.0
- **数据库**: SQLite（当前）/ PostgreSQL（规划）
- **数据源**: AKShare（主）/ Tushare（备）
- **前端**: React 18+ / Vite
- **策略引擎**: Backtrader 1.9+
- **Shell**: PowerShell 兼容格式
- **项目根目录**: `c:\Users\晓\Desktop\量化deepseek\`

## 目录结构

```
├── agent.md                 # AI Agent 强制性工作规则（最高约束力）
├── AGENTS.md                # 本文件 — Codex 开发配置
├── prompts/                 # 6个AI Agent角色提示词
│   ├── 01-总设计师.md
│   ├── 02-产品经理.md
│   ├── 03-后端开发.md
│   ├── 04-数据工程师.md
│   ├── 05-前端开发.md
│   └── 06-策略研究员.md
├── docs/specs/              # 产品文档
│   ├── PRD-量化交易系统.md
│   ├── 功能优先级矩阵.md
│   └── 前后端接口约定.md
├── backend/                 # 后端 FastAPI 服务
│   ├── main.py              # ★ 应用入口
│   ├── models/              # ★ 共享数据模型（Pydantic）
│   ├── api/stocks.py        # 股票API路由
│   ├── services/            # 业务逻辑层
│   └── core/                # 策略引擎（待实现）
├── data/                    # 数据工程层
│   ├── pipeline.py          # ★ ETL入口脚本
│   ├── fetcher/             # AKShare数据采集
│   ├── cleaner/             # 数据清洗
│   └── storage/             # SQLite 数据库 + ORM
├── strategy/                # 策略层（骨架，待实现）
│   ├── backtest/
│   ├── factors/
│   └── optimization/
├── frontend/                # 前端（脚手架，待实现）
│   └── src/
└── 外部资料/                # 参考素材
```

## 常用命令

```powershell
# 启动后端
cd c:\Users\晓\Desktop\量化deepseek && uvicorn backend.main:app --reload --port 8000

# 数据管道
python -m data.pipeline init           # 初始化数据库
python -m data.pipeline sync-stocks     # 同步A股列表
python -m data.pipeline sync-klines --days 3000 --codes 600309  # 补最近3000天K线
python -m data.pipeline sync-history --codes 600309             # 从上市以来补K线数据

# 启动前端
cd frontend && npm run dev

# API 文档（启动后端后访问）
# http://localhost:8000/docs
# http://localhost:8000/redoc
```

## 代码规范（摘自 agent.md）

1. **简体中文**回复，代码注释优先中文
2. **先跑通再优化** — 最小可行原则，禁止过度工程化
3. **能用标准库不用第三方库**，新增依赖写入对应 requirements.txt
4. **修改前先读完原文件**，不得擅自重构或变更已有数据结构
5. **所有代码完整可运行**，不得省略 import，不得留 TODO 标记
6. **每个 .py 文件头部必须有** `# -*- coding: utf-8 -*-`
7. **严禁主动执行 `git commit`**（除非用户明确要求；用户说提交、推送、部署、上线、修复线上问题时，视为授权完整提交/推送/部署闭环）

## 自动化交付默认

- 用户明确要求“推送/部署/上线”后，Codex 应自动筛选本次相关文件、运行必要测试和构建、提交、推送到 `origin/main`，并查看 GitHub Actions / Vercel / Render 状态。
- 前端改动至少运行：`cd frontend && npm.cmd run build`
- 后端、数据、策略改动至少运行：`python -m compileall backend data strategy`
- 策略规则改动必须运行或补充 `tests/` 下的测试。
- 回测页面默认直连 AKShare 获取 K 线，SQLite 作为缓存/兜底，不应让线上缓存缺口阻塞用户回测。
- 自动化提交禁止包含工作日志、临时文件、缓存、密钥或与本次任务无关的改动。

## 数据模型

共享数据结构统一定义在 `backend/models/`：
- `stock.py` — StockBase, StockDetail, StockList
- `market.py` — KlineData, RealtimeQuote
- `strategy.py` — StrategyConfig, StrategySignal

数据库三张表（`data/storage/models_orm.py`）：stocks, klines, watchlist

## 跨层调用链路

```
backend/api/ → backend/services/ → data/storage/repository.py → SQLite
```

后端通过 `sys.path.insert(0, PROJECT_ROOT)` 实现跨目录导入 data 包。
