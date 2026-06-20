"""Design 模型 — 设计管理核心"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, JSON, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class Design(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "designs"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 设计文件
    file_path: Mapped[str] = mapped_column(String(500))           # 原始设计文件服务器路径
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 缩略图
    mockup_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)            # Mockup 多角度图 URL 列表

    # 设计属性
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["复古","搞笑","文字"]
    dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)  # RGB/CMYK

    # 状态流转：草稿 → 待发布 → 已发布 → 已下线
    status: Mapped[str] = mapped_column(String(30), default="草稿", index=True)

    # 平台发布状态：{"tiktok": "published", "shopify": "draft", "amazon": "none"}
    platform_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 数据分析
    is_hit: Mapped[bool] = mapped_column(Boolean, default=False)   # 爆款标记
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关联
    variants: Mapped[list["DesignVariant"]] = relationship(
        "DesignVariant", back_populates="design", cascade="all, delete-orphan"
    )
    listing_jobs: Mapped[list["ListingJob"]] = relationship(
        "ListingJob", back_populates="design", cascade="all, delete-orphan"
    )


class DesignVariant(Base, UUIDMixin, TimestampMixin):
    """设计 + 基底产品 = 一个可售 SKU"""
    __tablename__ = "design_variants"

    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("designs.id"), index=True)
    blank_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("blank_products.id"), index=True)

    sku_code: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    mockup_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 该组合的效果图

    # 定价
    base_price: Mapped[float] = mapped_column(default=0.0)       # 建议零售价
    cost_price: Mapped[float] = mapped_column(default=0.0)        # 生产成本（印刷+耗材）

    status: Mapped[str] = mapped_column(String(30), default="active")  # active/inactive

    design: Mapped["Design"] = relationship("Design", back_populates="variants")
    blank_product: Mapped["BlankProduct"] = relationship("BlankProduct", back_populates="design_variants")
