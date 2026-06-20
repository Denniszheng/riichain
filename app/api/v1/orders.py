"""Order Management — 订单管理 API（Order Router 模块）"""
import uuid
import random
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.order import Order, OrderItem, OrderRouting
from app.models.facility import Facility

router = APIRouter()

VALID_STATUSES = [
    "pending", "paid", "processing", "printed",
    "packed", "shipped", "completed", "cancelled",
]

def gen_uuid():
    return str(uuid.uuid4())


# ── GET /orders/stats — 统计各状态数量（必须在 /{order_id} 之前）──

@router.get("/stats")
def order_stats():
    db = SessionLocal()
    try:
        rows = (
            db.query(Order.status, func.count(Order.id))
            .group_by(Order.status)
            .all()
        )
        status_map = {s: c for s, c in rows}
        total = sum(status_map.values())

        return {
            "total": total,
            "pending": status_map.get("pending", 0),
            "paid": status_map.get("paid", 0),
            "processing": status_map.get("processing", 0),
            "printed": status_map.get("printed", 0),
            "packed": status_map.get("packed", 0),
            "shipped": status_map.get("shipped", 0),
            "completed": status_map.get("completed", 0),
            "cancelled": status_map.get("cancelled", 0),
            "by_status": status_map,
        }
    finally:
        db.close()


# ── GET /orders/ — 订单列表（分页 + 过滤） ───────────────────────

@router.get("/")
def list_orders(
    platform: str | None = Query(None),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = SessionLocal()
    try:
        q = db.query(Order)

        if platform:
            q = q.filter(Order.platform == platform)
        if status:
            q = q.filter(Order.status == status)
        # channel 兼容旧参数，映射到 platform
        if channel and not platform:
            q = q.filter(Order.platform == channel)

        total = q.count()
        orders = (
            q.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "data": [
                {
                    "id": o.id,
                    "platform": o.platform,
                    "platform_order_id": o.platform_order_id,
                    "customer_name": o.customer_name,
                    "status": o.status,
                    "total_amount": o.total_amount,
                    "currency": o.currency,
                    "is_rush": o.is_rush,
                    "created_at": str(o.created_at)[:19] if o.created_at else "",
                    "tracking_no": o.tracking_no,
                    "item_count": len(o.items) if o.items else 0,
                }
                for o in orders
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }
    finally:
        db.close()


# ── POST /orders/ — 手动创建订单 ─────────────────────────────────

@router.post("/")
def create_order(data: dict):
    db = SessionLocal()
    try:
        order = Order(
            id=gen_uuid(),
            tenant_id=data.get("tenant_id", "default"),
            platform=data.get("platform", "manual"),
            platform_order_id=data.get("platform_order_id") or data.get("order_no"),
            customer_name=data.get("customer_name"),
            customer_email=data.get("customer_email"),
            shipping_address=data.get("shipping_address"),
            phone=data.get("phone"),
            total_amount=float(data.get("total_amount", 0)),
            currency=data.get("currency", "USD"),
            status=data.get("status", "pending"),
            is_rush=data.get("is_rush", False),
            notes=data.get("notes"),
        )
        db.add(order)

        items_data = data.get("items", [])
        for item in items_data:
            db.add(OrderItem(
                id=gen_uuid(),
                order_id=order.id,
                tenant_id=order.tenant_id,
                sku=item.get("sku", ""),
                product_name=item.get("product_name"),
                qty=int(item.get("qty", 1)),
                unit_price=float(item.get("unit_price", 0)),
                production_status=item.get("production_status", "pending"),
            ))

        db.commit()
        db.refresh(order)
        return {
            "id": order.id,
            "platform": order.platform,
            "status": order.status,
            "total_amount": order.total_amount,
            "created_at": str(order.created_at)[:19] if order.created_at else "",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(400, str(e))
    finally:
        db.close()


# ── GET /orders/{order_id} — 订单详情（含 items + routing）───────

@router.get("/{order_id}")
def get_order(order_id: str):
    db = SessionLocal()
    try:
        order = (
            db.query(Order)
            .options(joinedload(Order.items), joinedload(Order.routing))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            raise HTTPException(404, "Order not found")

        items = [
            {
                "id": i.id,
                "sku": i.sku,
                "product_name": i.product_name,
                "qty": i.qty,
                "unit_price": i.unit_price,
                "production_status": i.production_status,
            }
            for i in (order.items or [])
        ]

        routing = None
        if order.routing:
            r = order.routing
            routing = {
                "id": r.id,
                "proximity_score": r.proximity_score,
                "stock_score": r.stock_score,
                "capacity_score": r.capacity_score,
                "cost_score": r.cost_score,
                "total_score": r.total_score,
                "selected_facility_id": r.selected_facility_id,
                "status": r.status,
            }

        return {
            "id": order.id,
            "tenant_id": order.tenant_id,
            "platform": order.platform,
            "platform_order_id": order.platform_order_id,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "shipping_address": order.shipping_address,
            "phone": order.phone,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "status": order.status,
            "tracking_no": order.tracking_no,
            "carrier": order.carrier,
            "shipped_at": str(order.shipped_at)[:19] if order.shipped_at else "",
            "is_rush": order.is_rush,
            "notes": order.notes,
            "created_at": str(order.created_at)[:19] if order.created_at else "",
            "items": items,
            "routing": routing,
        }
    finally:
        db.close()


# ── PUT /orders/{order_id}/status — 更新状态 ─────────────────────

@router.put("/{order_id}/status")
def update_status(order_id: str, data: dict):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(404, "Order not found")

        new_status = data.get("status")
        if not new_status:
            raise HTTPException(400, "status is required")
        if new_status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status. Must be one of: {VALID_STATUSES}")

        order.status = new_status
        db.commit()
        return {"id": order.id, "status": order.status}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, str(e))
    finally:
        db.close()


# ── POST /orders/{order_id}/route — 四维度评分路由 ───────────────

@router.post("/{order_id}/route")
def route_order(order_id: str, data: dict | None = None):
    """四维度评分：proximity / stock / capacity / cost，选最优印刷厂"""
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(404, "Order not found")

        weights = (data or {}).get("weights", {})
        w_prox = weights.get("proximity", 0.25)
        w_stock = weights.get("stock", 0.25)
        w_cap = weights.get("capacity", 0.25)
        w_cost = weights.get("cost", 0.25)

        facilities = db.query(Facility).filter(Facility.is_active == True).all()
        if not facilities:
            raise HTTPException(400, "No active facilities available")

        results = []
        for f in facilities:
            # 1. proximity — 距离评分（基于经纬度归一化 0-100）
            if f.lat is not None and f.lng is not None:
                prox = max(0, min(100, (f.lat + 90) / 1.8 * 50 + (f.lng + 180) / 3.6 * 50))
            else:
                prox = round(random.uniform(40, 90), 1)

            # 2. stock — 库存充足度（产能利用率越低越充足）
            stock = round((1.0 - f.capacity_utilization) * 100, 1)

            # 3. capacity — 产能余量（利用率越低余量越大）
            cap = round((1.0 - f.capacity_utilization) * 100, 1)

            # 4. cost — 综合成本（cost_factor 越低评分越高）
            cost_factor = max(f.cost_factor, 0.01)
            cost = round(min(100, (1.0 / cost_factor) * 50), 1)

            total = round(
                w_prox * prox + w_stock * stock + w_cap * cap + w_cost * cost, 1
            )

            results.append({
                "facility_id": f.id,
                "facility_name": f.name,
                "proximity_score": prox,
                "stock_score": stock,
                "capacity_score": cap,
                "cost_score": cost,
                "total_score": total,
            })

        results.sort(key=lambda x: x["total_score"], reverse=True)
        best = results[0]

        # 写入/更新 OrderRouting
        existing = db.query(OrderRouting).filter(OrderRouting.order_id == order_id).first()
        if existing:
            existing.proximity_score = best["proximity_score"]
            existing.stock_score = best["stock_score"]
            existing.capacity_score = best["capacity_score"]
            existing.cost_score = best["cost_score"]
            existing.w_proximity = w_prox
            existing.w_stock = w_stock
            existing.w_capacity = w_cap
            existing.w_cost = w_cost
            existing.total_score = best["total_score"]
            existing.selected_facility_id = best["facility_id"]
            existing.status = "confirmed"
        else:
            routing = OrderRouting(
                id=gen_uuid(),
                order_id=order_id,
                tenant_id=order.tenant_id,
                proximity_score=best["proximity_score"],
                stock_score=best["stock_score"],
                capacity_score=best["capacity_score"],
                cost_score=best["cost_score"],
                w_proximity=w_prox,
                w_stock=w_stock,
                w_capacity=w_cap,
                w_cost=w_cost,
                total_score=best["total_score"],
                selected_facility_id=best["facility_id"],
                status="confirmed",
            )
            db.add(routing)

        if order.status == "pending":
            order.status = "processing"

        db.commit()

        return {
            "order_id": order_id,
            "selected_facility": best,
            "all_scores": results,
            "weights": {"proximity": w_prox, "stock": w_stock, "capacity": w_cap, "cost": w_cost},
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, str(e))
    finally:
        db.close()


# ── WMS Integration: 领星波次查询 ──
from pydantic import BaseModel

class WMSWaveRequest(BaseModel):
    waveNo: str

@router.post("/wms/wave-detail")
def wms_wave_detail(req: WMSWaveRequest):
    """从领星 WMS 拉取波次订单数据"""
    from app.services.wms_service import fetch_wave_detail
    try:
        result = fetch_wave_detail(req.waveNo)
        return result
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": None}
