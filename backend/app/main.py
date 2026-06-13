"""应用入口：创建表、播种、注册路由、配置 CORS。

启动：uvicorn app.main:app --reload
文档：http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from . import models  # noqa: F401  确保模型被注册
from .seed import seed
from .routers import auth, users, classifications, indicators, suggestions, comments, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # 开发期建表；生产建议改用 Alembic 迁移
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="健康指标标准修订协作平台 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
for r in (auth, users, classifications, indicators, suggestions, comments, export):
    app.include_router(r.router, prefix=API)


@app.get("/health", tags=["健康检查"])
def health():
    return {"status": "ok"}
