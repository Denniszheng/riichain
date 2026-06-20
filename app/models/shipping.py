"""ShippingLabel 模型 — 面单管理"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDMixin, TimestampMixin


class ShippingLabel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shipping_labels"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    order_no: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)

    file_path: Mapped[str] = mapped_column(String(500))  # PDF 文件路径
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)  # USPS/JOFO/DHL
    tracking_no: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    # 面单状态：pending / printed / shipped
    status: Mapped[str] = mapped_column(String(30), default="pending")

    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
