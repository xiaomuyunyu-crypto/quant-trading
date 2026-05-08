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
    # 静态资源
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    # SPA 路由：根路径和所有非 API 路径返回 index.html
    @app.get("/")
    @app.get("/{path:path}")
    async def serve_spa(path: str = ""):
        if path.startswith("api/") or path == "docs" or path == "redoc":
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index_file = FRONTEND_DIST / "index.html"
        return FileResponse(index_file)
