"""PrintJob 模型 — 打印任务生命周期管理"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class PrintJob(Base, UUIDMixin, TimestampMixin):
    """
    PrintJob 生命周期：
    queued → printing → printed → qc → packed → shipped
    """
    __tablename__ = "print_jobs"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("order_items.id"), index=True)

    # 关联的排版波次
    wave_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # 分配到的印刷厂
    facility_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # 打印文件
    print_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    layout_preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 状态机
    status: Mapped[str] = mapped_column(
        String(30), default="queued", index=True
    )  # queued/printing/printed/qc/packed/shipped

    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qc_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qc_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 耗材使用记录
    material_board_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_qty_used: Mapped[int] = mapped_column(Integer, default=1)

    # 关联
    order: Mapped["Order"] = relationship("Order", back_populates="print_jobs")
