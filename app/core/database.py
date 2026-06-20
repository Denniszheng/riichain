"""RiiChain - POD专用全链路系统 数据库配置"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import get_settings

settings = get_settings()

# SQLite 开发环境：启用外键约束 + 单连接（支持 FastAPI 热重载）
connect_args = {"check_same_thread": False}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    from app.models.base import Base
    Base.metadata.create_all(bind=engine)
