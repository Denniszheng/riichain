"""Facility 模型 — 印刷厂/生产中心管理"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class Facility(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "facilities"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 支持的印刷方式
    print_methods: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ["DTG","DTF"]
    # 支持的品类
    supported_categories: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ["T恤","杯子"]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 当前产能利用率 0.0-1.0
    capacity_utilization: Mapped[float] = mapped_column(default=0.0)

    # 成本系数（对比基准成本，1.0=基准）
    cost_factor: Mapped[float] = mapped_column(default=1.0)

    capacities: Mapped[list["FacilityCapacity"]] = relationship(
        "FacilityCapacity", back_populates="facility", cascade="all, delete-orphan"
    )


class FacilityCapacity(Base, UUIDMixin, TimestampMixin):
    """印刷厂各基底产品的日产能"""
    __tablename__ = "facility_capacities"

    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    blank_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blank_products.id"), index=True
    )

    # 日产能（件/天）
    daily_capacity: Mapped[int] = mapped_column(Integer, default=100)
    # 当前已分配未完成的量
    allocated_qty: Mapped[int] = mapped_column(Integer, default=0)

    facility: Mapped["Facility"] = relationship("Facility", back_populates="capacities")
