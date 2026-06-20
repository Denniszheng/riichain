"""Order 模型 — 订单管理 + 路由决策"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, Text, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class Order(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "orders"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # 平台来源
    platform: Mapped[str] = mapped_column(String(30), index=True)  # tiktok/shopify/amazon/manual
    platform_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # 客户信息
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 金额
    total_amount: Mapped[float] = mapped_column(default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # 状态流转：pending → paid → processing → printed → packed → shipped → completed
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    # 物流
    tracking_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 标记
    is_rush: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 关联
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    routing: Mapped["OrderRouting | None"] = relationship(
        "OrderRouting", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    print_jobs: Mapped[list["PrintJob"]] = relationship(
        "PrintJob", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    design_variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("design_variants.id"), nullable=True
    )
    sku: Mapped[str] = mapped_column(String(200), index=True)
    product_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(default=0.0)

    # 生产状态：pending → queued → printing → printed → qc → packed
    production_status: Mapped[str] = mapped_column(String(30), default="pending")

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    design_variant: Mapped["DesignVariant | None"] = relationship("DesignVariant")


class OrderRouting(Base, UUIDMixin, TimestampMixin):
    """订单路由决策 — 四维度评分，选择最优印刷厂"""
    __tablename__ = "order_routings"

    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # 四维度评分（0-100）
    proximity_score: Mapped[float] = mapped_column(default=0.0)   # 印刷厂到客户距离
    stock_score: Mapped[float] = mapped_column(default=0.0)        # 空白耗材库存充足度
    capacity_score: Mapped[float] = mapped_column(default=0.0)     # 印刷厂当前产能余量
    cost_score: Mapped[float] = mapped_column(default=0.0)         # 综合成本（越低分越高）

    # 权重配置（可调整，总和=1.0）
    w_proximity: Mapped[float] = mapped_column(default=0.25)
    w_stock: Mapped[float] = mapped_column(default=0.25)
    w_capacity: Mapped[float] = mapped_column(default=0.25)
    w_cost: Mapped[float] = mapped_column(default=0.25)

    total_score: Mapped[float] = mapped_column(default=0.0)
    selected_facility_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 路由执行状态
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending/confirmed/overridden
    overridden_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="routing")
