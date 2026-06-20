"""ListingJob 模型 — 一键铺货任务记录"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class ListingJob(Base, UUIDMixin, TimestampMixin):
    """
    一次「一键铺货」操作产生一条 ListingJob 记录。
    包含：哪个设计、哪个基底产品、推到哪个平台、结果如何。
    """
    __tablename__ = "listing_jobs"

    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)

    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id"), index=True
    )
    design_variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("design_variants.id"), nullable=True
    )
    blank_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blank_products.id"), index=True
    )

    platform_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platform_accounts.id"), index=True
    )

    # 平台返回的信息
    platform_listing_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    platform_product_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # 铺货状态：pending / success / failed / syncing
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    # 失败原因 / 平台返回的错误信息
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 本次铺货使用的标题/描述快照（平台可能修改）
    title_used: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_used: Mapped[float | None] = mapped_column(default=None)

    # 关联
    design: Mapped["Design"] = relationship("Design", back_populates="listing_jobs")
    platform_account: Mapped["PlatformAccount"] = relationship(
        "PlatformAccount", back_populates="listing_jobs"
    )
