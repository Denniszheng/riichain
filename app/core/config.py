"""RiiChain - POD专用全链路系统 配置文件"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用基础
    APP_NAME: str = "RiiChain"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/riichain.db"

    # 上传文件
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # 排版引擎
    LAYOUT_ENGINE: str = "pyckingsolver"  # pyckingsolver / guillotine
    LAYOUT_OUTPUT_DIR: str = "app/static/outputs/layouts"

    # AI / LLM
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    LLM_MODEL: str = "gpt-4o"

    # 平台对接
    TIKTOK_APP_KEY: str | None = None
    TIKTOK_APP_SECRET: str | None = None
    TIKTOK_REDIRECT_URI: str | None = None

    SHOPIFY_CLIENT_ID: str | None = None
    SHOPIFY_CLIENT_SECRET: str | None = None
    SHOPIFY_REDIRECT_URI: str | None = None

    # 领星 WMS 对接
    WMS_APP_KEY: str = "60d2da562ee3492e8bdaaea44c611910"
    WMS_SECRET: str = "e7f3e07d4f15438da02308fa1ebf90be"
    WMS_BASE_URL: str = "https://api.xlwms.com"
    WMS_WH_CODE: str = "TXMISSOURI"  # 仓库代码

    # 安全
    SECRET_KEY: str = "riichain-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
