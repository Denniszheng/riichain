"""Analytics — 销售分析 API"""
import random
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, desc
from app.core.database import SessionLocal
from app.models.analytics import SalesRecord, HitProduct
from app.models.design import Design

router = APIRouter()

PLATFORMS = ["tiktok", "shopify", "amazon"]


# ── GET /api/v1/analytics/overview — 概览 ──
@router.get("/overview")
def get_overview():
    db = SessionLocal()
    try:
        total_revenue = db.query(func.coalesce(func.sum(SalesRecord.revenue), 0)).scalar()
        total_orders = db.query(func.coalesce(func.sum(SalesRecord.orders), 0)).scalar()
        avg_order_value = round(total_revenue / total_orders, 2) if total_orders else 0
        hit_count = db.query(func.count(HitProduct.id)).filter(
            HitProduct.hit_score >= 70
        ).scalar()
        return {
            "data": {
                "total_revenue": round(float(total_revenue), 2),
                "total_orders": int(total_orders),
                "avg_order_value": float(avg_order_value),
                "hit_products": hit_count,
            }
        }
    finally:
        db.close()


# ── GET /api/v1/analytics/designs — 按设计分组 ──
@router.get("/designs")
def list_design_analytics():
    db = SessionLocal()
    try:
        rows = (
            db.query(
                SalesRecord.design_id,
                Design.title,
                func.sum(SalesRecord.orders).label("total_orders"),
                func.sum(SalesRecord.revenue).label("total_revenue"),
                func.sum(SalesRecord.ad_spend).label("total_ad_spend"),
            )
            .join(Design, SalesRecord.design_id == Design.id)
            .group_by(SalesRecord.design_id, Design.title)
            .order_by(desc(func.sum(SalesRecord.revenue)))
            .all()
        )

        hit_set = {
            h.design_id
            for h in db.query(HitProduct.design_id).filter(
                HitProduct.hit_score >= 70
            ).all()
        }

        data = []
        for idx, r in enumerate(rows):
            profit = r.total_revenue - (r.total_ad_spend or 0)
            margin = (
                round(profit / r.total_revenue * 100, 1) if r.total_revenue else 0
            )
            data.append({
                "rank": idx + 1,
                "design_id": r.design_id,
                "design_title": r.title,
                "total_orders": int(r.total_orders),
                "total_revenue": round(float(r.total_revenue), 2),
                "total_ad_spend": round(float(r.total_ad_spend or 0), 2),
                "profit": round(float(profit), 2),
                "margin": float(margin),
                "is_hit": r.design_id in hit_set,
            })
        return {"data": data, "total": len(data)}
    finally:
        db.close()


# ── GET /api/v1/analytics/platforms — 按平台分组 ──
@router.get("/platforms")
def list_platform_analytics():
    db = SessionLocal()
    try:
        total_revenue = db.query(
            func.coalesce(func.sum(SalesRecord.revenue), 0)
        ).scalar() or 0

        rows = (
            db.query(
                SalesRecord.platform,
                func.sum(SalesRecord.orders).label("total_orders"),
                func.sum(SalesRecord.revenue).label("total_revenue"),
            )
            .group_by(SalesRecord.platform)
            .order_by(desc(func.sum(SalesRecord.revenue)))
            .all()
        )

        data = []
        for r in rows:
            share = round(r.total_revenue / total_revenue * 100, 1) if total_revenue else 0
            data.append({
                "platform": r.platform,
                "total_orders": int(r.total_orders),
                "total_revenue": round(float(r.total_revenue), 2),
                "share": float(share),
            })
        return {"data": data, "total": len(data)}
    finally:
        db.close()


# ── GET /api/v1/analytics/trends — 最近 30 天每日销售额 ──
@router.get("/trends")
def get_trends():
    db = SessionLocal()
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=29)

        rows = (
            db.query(
                SalesRecord.record_date,
                func.sum(SalesRecord.revenue).label("revenue"),
                func.sum(SalesRecord.orders).label("orders"),
            )
            .filter(SalesRecord.record_date >= start_date)
            .filter(SalesRecord.record_date <= end_date)
            .group_by(SalesRecord.record_date)
            .order_by(SalesRecord.record_date)
            .all()
        )

        # 填充缺失日期
        row_map = {r.record_date: (float(r.revenue or 0), int(r.orders or 0)) for r in rows}
        data = []
        d = start_date
        while d <= end_date:
            rev, ord_count = row_map.get(d, (0, 0))
            data.append({
                "date": d.isoformat(),
                "revenue": rev,
                "orders": ord_count,
            })
            d += timedelta(days=1)
        return {"data": data, "total": len(data)}
    finally:
        db.close()


# ── POST /api/v1/analytics/sync — 手动同步（生成模拟数据用于演示） ──
@router.post("/sync")
def sync_analytics_data():
    db = SessionLocal()
    try:
        designs = db.query(Design).filter(Design.status.in_(["已发布", "待发布"])).all()
        if not designs:
            # 拉取全部设计
            designs = db.query(Design).all()
        if not designs:
            return {"data": {"records_created": 0, "message": "无可用设计，请先创建设计"}}

        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        records_created = 0

        for d in range(31):
            record_date = start_date + timedelta(days=d)
            for design in designs:
                for platform in PLATFORMS:
                    # 检查是否已存在
                    exists = (
                        db.query(SalesRecord.id)
                        .filter(
                            SalesRecord.design_id == design.id,
                            SalesRecord.platform == platform,
                            SalesRecord.record_date == record_date,
                        )
                        .first()
                    )
                    if exists:
                        continue

                    # 生成模拟数据
                    base_views = random.randint(80, 500)
                    clicks = int(base_views * random.uniform(0.02, 0.12))
                    orders = max(0, int(clicks * random.uniform(0.03, 0.15)))
                    revenue = round(orders * random.uniform(15.0, 49.99), 2)
                    ad_spend = round(revenue * random.uniform(0.1, 0.4), 2)

                    ctr = round(clicks / base_views, 4) if base_views else 0
                    cvr = round(orders / clicks, 4) if clicks else 0
                    cpa = round(ad_spend / orders, 2) if orders else 0
                    roi = (
                        round((revenue - ad_spend) / ad_spend, 2) if ad_spend else 0
                    )

                    record = SalesRecord(
                        tenant_id="default",
                        design_id=design.id,
                        platform=platform,
                        record_date=record_date,
                        views=base_views,
                        clicks=clicks,
                        orders=orders,
                        revenue=revenue,
                        ad_spend=ad_spend,
                        ctr=ctr,
                        cvr=cvr,
                        cpa=cpa,
                        roi=roi,
                    )
                    db.add(record)
                    records_created += 1

        db.commit()

        # 自动标记爆款（综合 orders + revenue + roi）
        _auto_mark_hit_products(db)

        return {"data": {"records_created": records_created}}
    finally:
        db.close()


def _auto_mark_hit_products(db):
    """自动识别爆款：近 30 天订单 >= 10 且 ROI >= 1.5"""
    thirty_days_ago = date.today() - timedelta(days=30)

    rows = (
        db.query(
            SalesRecord.design_id,
            func.sum(SalesRecord.orders).label("total_orders"),
            func.sum(SalesRecord.revenue).label("total_revenue"),
            func.sum(SalesRecord.ad_spend).label("total_ad_spend"),
        )
        .filter(SalesRecord.record_date >= thirty_days_ago)
        .group_by(SalesRecord.design_id)
        .all()
    )

    for r in rows:
        roi = (
            round((r.total_revenue - r.total_ad_spend) / r.total_ad_spend, 2)
            if r.total_ad_spend
            else 0
        )
        if r.total_orders >= 10 and roi >= 1.5:
            # 计算 hit_score（0-100）
            order_score = min(r.total_orders / 50 * 40, 40)
            roi_score = min(roi / 3.0 * 40, 40)
            revenue_score = min(r.total_revenue / 1000 * 20, 20)
            hit_score = round(order_score + roi_score + revenue_score, 1)
            hit_score = min(hit_score, 100)

            existing = (
                db.query(HitProduct)
                .filter(HitProduct.design_id == r.design_id)
                .first()
            )
            if existing:
                existing.hit_score = hit_score
                existing.trigger_tags = [
                    f"近30天订单{r.total_orders}",
                    f"ROI {roi}",
                ]
            else:
                hp = HitProduct(
                    tenant_id="default",
                    design_id=r.design_id,
                    hit_score=hit_score,
                    trigger_tags=[
                        f"近30天订单{r.total_orders}",
                        f"ROI {roi}",
                    ],
                )
                db.add(hp)
            # 同步更新 Design 的 is_hit 和统计数据
            design = db.query(Design).filter(Design.id == r.design_id).first()
            if design:
                design.is_hit = True
                design.order_count = int(r.total_orders or 0)
    db.commit()
