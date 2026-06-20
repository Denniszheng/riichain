"""BlankProduct 模型 — 基底产品（T恤/杯子/手机壳等）"""
import uuid
from sqlalchemy import String, Float, Integer, Boolean, Text, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, UUIDMixin, TimestampMixin


class BlankProduct(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "blank_products"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))               # "男士经典圆领T恤"
    category: Mapped[str] = mapped_column(String(50), index=True)  # T恤/杯子/手机壳/帽子/袋子
    supplier: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 打印区域尺寸（mm）
    print_area_w: Mapped[int] = mapped_column(Integer, default=300)
    print_area_h: Mapped[int] = mapped_column(Integer, default=400)

    # 产品设计尺寸（设计师需要以此为准出图）
    design_template_w: Mapped[int] = mapped_column(Integer, default=3000)  # DPI=300 时的像素宽
    design_template_h: Mapped[int] = mapped_column(Integer, default=4000)

    # 基底实物尺寸（mm）— 用于排版引擎计算
    blank_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blank_h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    material: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 纯棉/涤纶/陶瓷
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    base_price_usd: Mapped[float] = mapped_column(default=19.99)

    # 支持的印刷方式
    print_methods: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ["DTG","DTF","Sublimation"]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    thumbnail: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 关联
    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="blank_product", cascade="all, delete-orphan"
    )
    design_variants: Mapped[list["DesignVariant"]] = relationship(
        "DesignVariant", back_populates="blank_product", cascade="all, delete-orphan"
    )


class ProductVariant(Base, UUIDMixin, TimestampMixin):
    """基底产品的尺寸/颜色变体"""
    __tablename__ = "product_variants"

    blank_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("blank_products.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    size: Mapped[str | None] = mapped_column(String(30), nullable=True)   # S/M/L/XL
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 白色/黑色
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    price_usd: Mapped[float] = mapped_column(default=0.0)
    inventory: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    blank_product: Mapped["BlankProduct"] = relationship(
        "BlankProduct", back_populates="variants"
    )
