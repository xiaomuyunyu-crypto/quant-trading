# -*- coding: utf-8 -*-
# 数据库引擎与会话管理

import os
from pathlib import Path
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

DB_DIR = Path(__file__).resolve().parent.parent / "db"
DB_PATH = DB_DIR / "quant.db"

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine(db_path: str | None = None) -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    target = db_path or os.getenv("QUANT_DB_PATH") or str(DB_PATH)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{target_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SessionLocal()


def init_db(db_path: str | None = None):
    engine = get_engine(db_path)
    from .models_orm import Base
    Base.metadata.create_all(bind=engine)
