"""Blank Products — 基底产品 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import get_db
from app.models.blank_product import BlankProduct, ProductVariant

router = APIRouter()


def _bp_to_dict(p: BlankProduct) -> dict:
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "name": p.name,
        "category": p.category,
        "supplier": p.supplier,
        "print_area_w": p.print_area_w,
        "print_area_h": p.print_area_h,
        "design_template_w": p.design_template_w,
        "design_template_h": p.design_template_h,
        "blank_w": p.blank_w,
        "blank_h": p.blank_h,
        "material": p.material,
        "cost_usd": p.cost_usd,
        "base_price_usd": p.base_price_usd,
        "print_methods": p.print_methods,
        "is_active": p.is_active,
        "thumbnail": p.thumbnail,
        "variant_count": len(p.variants) if p.variants else 0,
        "created_at": str(p.created_at) if p.created_at else None,
        "updated_at": str(p.updated_at) if p.updated_at else None,
    }


# ── GET /api/v1/products/ — 列出基底产品 ──
@router.get("/")
def list_products(
    skip: int = 0,
    limit: int = 50,
    category: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(BlankProduct)
    if category:
        q = q.filter(BlankProduct.category == category)
    if is_active is not None:
        q = q.filter(BlankProduct.is_active == is_active)
    total = q.count()
    products = q.order_by(desc(BlankProduct.updated_at)).offset(skip).limit(limit).all()
    return {"data": [_bp_to_dict(p) for p in products], "total": total}


# ── POST /api/v1/products/ — 创建基底产品 ──
@router.post("/")
def create_product(data: dict, db: Session = Depends(get_db)):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name 为必填")

    product = BlankProduct(
        tenant_id=data.get("tenant_id", "default"),
        name=name,
        category=data.get("category", "其他"),
        supplier=data.get("supplier"),
        print_area_w=data.get("print_area_w", 300),
        print_area_h=data.get("print_area_h", 400),
        design_template_w=data.get("design_template_w", 3000),
        design_template_h=data.get("design_template_h", 4000),
        blank_w=data.get("blank_w"),
        blank_h=data.get("blank_h"),
        material=data.get("material"),
        cost_usd=float(data.get("cost_usd", 0)),
        base_price_usd=float(data.get("base_price_usd", 19.99)),
        print_methods=data.get("print_methods", []),
        thumbnail=data.get("thumbnail"),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"data": _bp_to_dict(product)}


# ── GET /api/v1/products/{product_id} ──
@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(BlankProduct).filter(BlankProduct.id == product_id).first()
    if not product:
        raise HTTPException(404, "基底产品不存在")
    return {"data": _bp_to_dict(product)}


# ── PUT /api/v1/products/{product_id} ──
@router.put("/{product_id}")
def update_product(product_id: str, data: dict, db: Session = Depends(get_db)):
    product = db.query(BlankProduct).filter(BlankProduct.id == product_id).first()
    if not product:
        raise HTTPException(404, "基底产品不存在")
    updatable = [
        "name", "category", "supplier", "print_area_w", "print_area_h",
        "design_template_w", "design_template_h", "blank_w", "blank_h",
        "material", "cost_usd", "base_price_usd", "print_methods",
        "is_active", "thumbnail",
    ]
    for k in updatable:
        if k in data:
            setattr(product, k, data[k])
    db.commit()
    return {"data": _bp_to_dict(product)}


# ── DELETE /api/v1/products/{product_id} ──
@router.delete("/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(BlankProduct).filter(BlankProduct.id == product_id).first()
    if not product:
        raise HTTPException(404, "基底产品不存在")
    product.is_active = False
    db.commit()
    return {"data": {"id": product_id, "deleted": True}}


# ── Variants ────────────────────────────────────────────────────

@router.get("/{product_id}/variants")
def list_variants(product_id: str, db: Session = Depends(get_db)):
    variants = (
        db.query(ProductVariant)
        .filter(ProductVariant.blank_product_id == product_id)
        .all()
    )
    return {
        "data": [
            {
                "id": v.id,
                "sku": v.sku,
                "size": v.size,
                "color": v.color,
                "cost_usd": v.cost_usd,
                "price_usd": v.price_usd,
                "inventory": v.inventory,
                "is_active": v.is_active,
            }
            for v in variants
        ]
    }


@router.post("/{product_id}/variants")
def create_variant(product_id: str, data: dict, db: Session = Depends(get_db)):
    product = db.query(BlankProduct).filter(BlankProduct.id == product_id).first()
    if not product:
        raise HTTPException(404, "基底产品不存在")
    variant = ProductVariant(
        blank_product_id=product_id,
        tenant_id=data.get("tenant_id", "default"),
        sku=data.get("sku", f"{product_id[:8]}-{data.get('size','')}-{data.get('color','')}"),
        size=data.get("size"),
        color=data.get("color"),
        cost_usd=float(data.get("cost_usd", 0)),
        price_usd=float(data.get("price_usd", 0)),
        inventory=int(data.get("inventory", 0)),
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return {"data": {"id": variant.id, "sku": variant.sku, "size": variant.size, "color": variant.color}}
