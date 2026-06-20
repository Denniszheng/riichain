"""Facilities — 印刷厂/生产中心管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.core.database import get_db
from app.models.facility import Facility, FacilityCapacity
from app.models.blank_product import BlankProduct

router = APIRouter()


def _fac_to_dict(f: Facility) -> dict:
    return {
        "id": f.id,
        "tenant_id": f.tenant_id,
        "name": f.name,
        "address": f.address,
        "lat": f.lat,
        "lng": f.lng,
        "contact_name": f.contact_name,
        "contact_phone": f.contact_phone,
        "contact_email": f.contact_email,
        "print_methods": f.print_methods,
        "supported_categories": f.supported_categories,
        "is_active": f.is_active,
        "capacity_utilization": f.capacity_utilization,
        "cost_factor": f.cost_factor,
        "capacity_count": len(f.capacities) if f.capacities else 0,
        "created_at": str(f.created_at) if f.created_at else None,
        "updated_at": str(f.updated_at) if f.updated_at else None,
    }


# ── GET /api/v1/facilities/ — 列出印刷厂 ──
@router.get("/")
def list_facilities(
    skip: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Facility)
    if is_active is not None:
        q = q.filter(Facility.is_active == is_active)
    total = q.count()
    facilities = q.order_by(desc(Facility.updated_at)).offset(skip).limit(limit).all()
    return {"data": [_fac_to_dict(f) for f in facilities], "total": total}


# ── POST /api/v1/facilities/ — 添加印刷厂 ──
@router.post("/")
def create_facility(data: dict, db: Session = Depends(get_db)):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name 为必填")

    facility = Facility(
        tenant_id=data.get("tenant_id", "default"),
        name=name,
        address=data.get("address"),
        lat=data.get("lat"),
        lng=data.get("lng"),
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
        contact_email=data.get("contact_email"),
        print_methods=data.get("print_methods", []),
        supported_categories=data.get("supported_categories", []),
        cost_factor=float(data.get("cost_factor", 1.0)),
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return {"data": _fac_to_dict(facility)}


# ── GET /api/v1/facilities/{facility_id} ──
@router.get("/{facility_id}")
def get_facility(facility_id: str, db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")
    return {"data": _fac_to_dict(facility)}


# ── PUT /api/v1/facilities/{facility_id} ──
@router.put("/{facility_id}")
def update_facility(facility_id: str, data: dict, db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")
    updatable = [
        "name", "address", "lat", "lng", "contact_name", "contact_phone",
        "contact_email", "print_methods", "supported_categories",
        "is_active", "cost_factor",
    ]
    for k in updatable:
        if k in data:
            setattr(facility, k, data[k])
    db.commit()
    return {"data": _fac_to_dict(facility)}


# ── DELETE /api/v1/facilities/{facility_id} ──
@router.delete("/{facility_id}")
def delete_facility(facility_id: str, db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")
    facility.is_active = False
    db.commit()
    return {"data": {"id": facility_id, "deleted": True}}


# ── Capacity Management ─────────────────────────────────────────

@router.get("/{facility_id}/capacity")
def get_facility_capacity(facility_id: str, db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")

    capacities = (
        db.query(FacilityCapacity, BlankProduct.name)
        .join(BlankProduct, FacilityCapacity.blank_product_id == BlankProduct.id)
        .filter(FacilityCapacity.facility_id == facility_id)
        .all()
    )

    return {
        "data": [
            {
                "id": cap.FacilityCapacity.id,
                "blank_product_id": cap.FacilityCapacity.blank_product_id,
                "product_name": name,
                "daily_capacity": cap.FacilityCapacity.daily_capacity,
                "allocated_qty": cap.FacilityCapacity.allocated_qty,
                "available": cap.FacilityCapacity.daily_capacity - cap.FacilityCapacity.allocated_qty,
            }
            for cap, name in capacities
        ]
    }


@router.put("/{facility_id}/capacity")
def update_facility_capacity(facility_id: str, data: dict, db: Session = Depends(get_db)):
    """更新/创建产能配置。data: {blank_product_id, daily_capacity}"""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")

    blank_product_id = data.get("blank_product_id")
    daily_capacity = data.get("daily_capacity", 100)
    if not blank_product_id:
        raise HTTPException(400, "blank_product_id 为必填")

    existing = (
        db.query(FacilityCapacity)
        .filter(
            FacilityCapacity.facility_id == facility_id,
            FacilityCapacity.blank_product_id == blank_product_id,
        )
        .first()
    )

    if existing:
        existing.daily_capacity = daily_capacity
    else:
        existing = FacilityCapacity(
            facility_id=facility_id,
            blank_product_id=blank_product_id,
            daily_capacity=daily_capacity,
        )
        db.add(existing)

    db.commit()
    return {
        "data": {
            "facility_id": facility_id,
            "blank_product_id": blank_product_id,
            "daily_capacity": daily_capacity,
        }
    }


@router.post("/{facility_id}/update_utilization")
def update_capacity_utilization(facility_id: str, db: Session = Depends(get_db)):
    """重新计算产能利用率 = 已分配 / 总日产能"""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(404, "印刷厂不存在")

    caps = (
        db.query(FacilityCapacity)
        .filter(FacilityCapacity.facility_id == facility_id)
        .all()
    )

    total_capacity = sum(c.daily_capacity for c in caps)
    total_allocated = sum(c.allocated_qty for c in caps)

    if total_capacity > 0:
        facility.capacity_utilization = round(total_allocated / total_capacity, 2)
    else:
        facility.capacity_utilization = 0.0

    db.commit()
    return {
        "data": {
            "facility_id": facility_id,
            "capacity_utilization": facility.capacity_utilization,
            "total_daily_capacity": total_capacity,
            "total_allocated": total_allocated,
        }
    }
