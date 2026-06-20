"""Analytics 模型 — 销售数据分析 + 爆款识别"""
import uuid
from datetime import date, datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Date, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDMixin


class SalesRecord(Base, UUIDMixin):
    """
    每日销售聚合数据（按 design + platform + date 维度）。
    用于趋势分析、爆款识别、ROI 计算。
    """
    __tablename__ = "sales_records"

    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)

    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(30), index=True)
    record_date: Mapped[date] = mapped_column(Date, index=True)

    # 销售指标
    views: Mapped[int] = mapped_column(default=0)           # 曝光/浏览量
    clicks: Mapped[int] = mapped_column(default=0)           # 点击量
    orders: Mapped[int] = mapped_column(default=0)           # 订单数
    revenue: Mapped[float] = mapped_column(default=0.0)    # 销售额（平台货币）
    ad_spend: Mapped[float] = mapped_column(default=0.0)   # 广告花费

    # 衍生指标（可计算，也存一份加速查询）
    ctr: Mapped[float] = mapped_column(default=0.0)          # 点击率 = clicks / views
    cvr: Mapped[float] = mapped_column(default=0.0)         # 转化率 = orders / clicks
    cpa: Mapped[float] = mapped_column(default=0.0)         # 获客成本 = ad_spend / orders
    roi: Mapped[float] = mapped_column(default=0.0)         # 投资回报 = (revenue - ad_spend) / ad_spend

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    design: Mapped["Design"] = relationship("Design")


class HitProduct(Base, UUIDMixin):
    """
    爆款标记表（人工 + 算法自动识别）。
    当设计的综合评分超过阈值时自动标记，也可人工覆盖。
    """
    __tablename__ = "hit_products"

    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)

    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id"), unique=True, index=True
    )

    # 爆款分数（0-100，综合 views/orders/revenue/roi）
    hit_score: Mapped[float] = mapped_column(default=0.0)

    # 触发爆款的原因标签
    trigger_tags: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    # 例：["连续3天订单>10","ROI>3.0","自然流量暴涨"]

    is_confirmed: Mapped[bool] = mapped_column(default=False)  # 人工确认？
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    design: Mapped["Design"] = relationship("Design")


class DesignAnalytics(Base, UUIDMixin):
    """
    设计维度聚合指标（加速查询，避免每次都扫 sales_records）。
    每天凌晨定时任务从 sales_records 聚合写入。
    """
    __tablename__ = "design_analytics"

    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id"), unique=True, index=True
    )

    total_views: Mapped[int] = mapped_column(default=0)
    total_orders: Mapped[int] = mapped_column(default=0)
    total_revenue: Mapped[float] = mapped_column(default=0.0)
    total_ad_spend: Mapped[float] = mapped_column(default=0.0)

    avg_ctr: Mapped[float] = mapped_column(default=0.0)
    avg_cvr: Mapped[float] = mapped_column(default=0.0)
    overall_roi: Mapped[float] = mapped_column(default=0.0)

    last_7d_orders: Mapped[int] = mapped_column(default=0)   # 近7天订单数
    last_7d_revenue: Mapped[float] = mapped_column(default=0.0)

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    design: Mapped["Design"] = relationship("Design")
