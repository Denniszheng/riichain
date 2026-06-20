"""Tenant 模型 — 多租户支持（初始版预留）"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDMixin, TimestampMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # 可选：API Key 用于平台对接签名
    api_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    is_active: Mapped[bool] = mapped_column(default=True)

    def __repr__(self):
        return f"<Tenant {self.slug}>"
