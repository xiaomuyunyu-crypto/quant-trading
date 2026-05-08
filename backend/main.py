# -*- coding: utf-8 -*-
# FastAPI 应用入口

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse


def _seed_watchlist(project_root: Path):
    """从自选股材料导入数据库（仅首次）"""
    import json, re
    from data.storage.database import get_session
    from data.storage.models_orm import WatchlistModel
    from sqlalchemy import select, func

    json_path = project_root / "外部资料" / "自选股材料" / "自选股图片OCR整理.json"
    if not json_path.exists():
        return

    with get_session() as s:
        count = s.execute(select(func.count()).select_from(WatchlistModel)).scalar() or 0
        if count > 0:
            return  # 已有数据，跳过

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    with get_session() as s:
        for r in records:
            code = r["代码"].strip()
            name = r["名称"].strip()
            # 分类标签
            if re.match(r"^\d{6}$", code):
                tag = "A股" if code.startswith(("0", "3", "6")) else ("ETF" if code.startswith(("1", "5")) else "指数")
            elif re.match(r"^\d{5}$", code):
                tag = "港股"
            elif re.match(r"^[A-Z]{2,5}$", code):
                tag = "美股"
            else:
                tag = "指数" if re.match(r"^(BK|98|H)\d+", code) else "其他"
            s.merge(WatchlistModel(code=code, name=name, tags=[tag]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动初始化数据库并导入种子数据"""
    from data.storage.database import init_db
    init_db()
    _seed_watchlist(PROJECT_ROOT)
    yield


app = FastAPI(
    title="量化交易系统 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

from backend.api.stocks import router as stocks_router
from backend.api.signals import router as signals_router
from backend.api.backtest import router as backtest_router
from backend.api.paper import router as paper_router
from backend.api.dashboard import router as dashboard_router

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(stocks_router, prefix="/api")
app.include_router(signals_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(paper_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}


# ─── 前端静态文件（SPA）───

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.middleware("http")
    async def serve_spa(request: Request, call_next):
        """SPA中间件：API 404 → 前端 index.html"""
        response = await call_next(request)
        # 只处理 GET 请求的非 API 路径的 404
        if (response.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api/")
            and not request.url.path.startswith("/docs")
            and not request.url.path.startswith("/redoc")):
            index_path = FRONTEND_DIST / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
        return response
