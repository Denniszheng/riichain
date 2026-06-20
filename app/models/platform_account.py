"""PlatformAccount 模型 — 电商平台账号管理（OAuth 凭证存储）"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class PlatformAccount(Base, UUIDMixin, TimestampMixin):
    """
    存储各电商平台的 OAuth 凭证。
    TikTok/Shopify 等通过 OAuth 2.0 授权后，token 存这里。
    """
    __tablename__ = "platform_accounts"

    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)

    # 平台类型：tiktok / shopify / amazon / shopee
    platform: Mapped[str] = mapped_column(String(30), index=True)

    # 店铺标识
    shop_name: Mapped[str] = mapped_column(String(200))
    shop_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # OAuth 凭证（加密存储，生产环境务必加密！）
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 平台额外配置（各平台不同，用 JSON 存）
    platform_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 关联
    listing_jobs: Mapped[list["ListingJob"]] = relationship(
        "ListingJob", back_populates="platform_account"
    )

    def is_token_expired(self) -> bool:
        """判断 access_token 是否过期"""
        if not self.token_expires_at:
            return True
        # 提前 5 分钟视为过期，留刷新余量
        return datetime.now(timezone.utc) >= (self.token_expires_at - timedelta(minutes=5))

    def __repr__(self):
        return f"<PlatformAccount {self.platform}/{self.shop_name}>"
