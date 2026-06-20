"""Wave / 波次管理 + 耗材库存模型 — POD 生产核心"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class WaveImport(Base, UUIDMixin, TimestampMixin):
    """一次 Excel 导入 = 一个 WaveImport，包含多个 WaveOrder"""
    __tablename__ = "wave_imports"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    filename: Mapped[str] = mapped_column(String(300))
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_skus: Mapped[int] = mapped_column(Integer, default=0)
    total_waves: Mapped[int] = mapped_column(Integer, default=0)

    # 待确认 → 已确认 → 已排版 → 已打印 → 已分货
    status: Mapped[str] = mapped_column(String(30), default="待确认", index=True)

    orders = relationship("WaveOrder", back_populates="import_batch", cascade="all, delete-orphan")


class WaveOrder(Base, UUIDMixin, TimestampMixin):
    """Excel 中的一行 = 一个 WaveOrder（一块亚克力板上的一个 SKU 订单）"""
    __tablename__ = "wave_orders"

    import_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("wave_imports.id"), index=True, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), index=True, nullable=True)

    order_no: Mapped[str] = mapped_column(String(100), index=True)
    wave_no: Mapped[str] = mapped_column(String(100), index=True)   # 一块板 = 一个 wave_no
    tracking_no: Mapped[str | None] = mapped_column(String(200), nullable=True)

    sku_code: Mapped[str] = mapped_column(String(200), index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)

    # Standard/Accessories/Customization
    product_type: Mapped[str] = mapped_column(String(50), default="Standard")

    # 待处理 → 待创波次 → 待打印 → 待分货 → 已分货 → 待包装 → 已发货
    status: Mapped[str] = mapped_column(String(30), default="待处理", index=True)

    order_date: Mapped[str | None] = mapped_column(String(20), nullable=True)  # YYYY-MM-DD
    ship_date: Mapped[str | None] = mapped_column(String(20), nullable=True)    # YYYY-MM-DD

    # 排版坐标（打印时写入）
    layout_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layout_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layout_rotation: Mapped[int] = mapped_column(Integer, default=0)  # 0/90/180/270

    import_batch = relationship("WaveImport", back_populates="orders")


class MaterialInventory(Base, UUIDMixin):
    """亚克力板（耗材）库存，按尺寸分别管理"""
    __tablename__ = "material_inventory"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # "480x480", "600x600", "300x400" 等
    board_size: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    qty_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=20)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockTransaction(Base, UUIDMixin, TimestampMixin):
    """每一次库存变动的审计日志"""
    __tablename__ = "stock_transactions"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # 关联（Material 或 SKU）
    board_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sku_code: Mapped[str | None] = mapped_column(String(200), nullable=True)

    transaction_type: Mapped[str] = mapped_column(String(30), index=True)
    # receipt / allocate / deduct / adjust / layout_consume / restock

    quantity_change: Mapped[int] = mapped_column(Integer)
    quantity_after: Mapped[int] = mapped_column(Integer)

    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 关联单号
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
