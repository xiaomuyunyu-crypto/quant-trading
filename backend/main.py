# -*- coding: utf-8 -*-
# FastAPI 应用入口

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.api.stocks import router as stocks_router
from backend.api.signals import router as signals_router
from backend.api.backtest import router as backtest_router
from backend.api.paper import router as paper_router
from backend.api.dashboard import router as dashboard_router

app = FastAPI(
    title="量化交易系统 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
