"""Design Hub — 设计管理 API"""
import uuid
import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from sqlalchemy import desc
from app.core.database import SessionLocal
from app.models.design import Design, DesignVariant

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent / "static" / "uploads" / "designs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

VALID_STATUSES = ["草稿", "待发布", "已发布", "已下线"]


# ── GET /api/v1/designs/ ─────────────────────────────────────────
@router.get("/")
def list_designs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    type: str | None = Query(None),
    is_hit: bool | None = Query(None),
):
    """分页列出设计，支持 status / type（保留参数）/ is_hit 过滤"""
    db = SessionLocal()
    try:
        q = db.query(Design)
        if status:
            q = q.filter(Design.status == status)
        if is_hit is not None:
            q = q.filter(Design.is_hit == is_hit)
        total = q.count()
        designs = q.order_by(desc(Design.updated_at)).offset(skip).limit(limit).all()
        return {
            "data": [_design_to_dict(d) for d in designs],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    finally:
        db.close()


# ── GET /api/v1/designs/{design_id} ─────────────────────────────
@router.get("/{design_id}")
def get_design(design_id: str):
    """获取设计详情（含 Variants）"""
    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")
        return {"data": _design_to_dict(design, include_variants=True)}
    finally:
        db.close()


# ── POST /api/v1/designs/upload ──────────────────────────────────
@router.post("/upload")
async def upload_design(
    title: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    file: UploadFile = File(None),
):
    """上传图片文件 + 创建设计记录"""
    file_path = None
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
        allowed_exts = {"png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "ai", "psd"}
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式：{ext}")
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        save_path = UPLOAD_DIR / stored_name
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        file_path = f"/static/uploads/designs/{stored_name}"

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    db = SessionLocal()
    try:
        design = Design(
            tenant_id="default",
            title=title,
            description=description,
            file_path=file_path or "",
            thumbnail_path=file_path,  # 图片直接用作缩略图
            tags=tag_list,
            status="草稿",
            platform_status={},
        )
        db.add(design)
        db.commit()
        db.refresh(design)
        return {"data": _design_to_dict(design)}
    finally:
        db.close()


# ── PUT /api/v1/designs/{design_id}/status ───────────────────────
@router.put("/{design_id}/status")
async def update_design_status(design_id: str, payload: dict):
    """更新设计状态：草稿 / 待发布 / 已发布 / 已下线"""
    new_status = payload.get("status")
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效状态，允许值：{VALID_STATUSES}",
        )
    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")
        design.status = new_status
        db.commit()
        return {"data": {"id": design_id, "status": new_status}}
    finally:
        db.close()


# ── DELETE /api/v1/designs/{design_id} ───────────────────────────
@router.delete("/{design_id}")
def delete_design(design_id: str):
    """软删除设计（状态设为已下线）"""
    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")
        design.status = "已下线"
        db.commit()
        return {"data": {"id": design_id, "deleted": True, "status": "已下线"}}
    finally:
        db.close()


# ── PUT /api/v1/designs/{design_id} ─────────────────────────────
@router.put("/{design_id}")
async def update_design(design_id: str, data: dict):
    """更新设计元数据（标题/描述/标签等）"""
    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")
        updatable = ["title", "description", "tags", "dpi", "color_mode", "is_hit"]
        for k in updatable:
            if k in data:
                setattr(design, k, data[k])
        db.commit()
        return {"data": {"id": design_id, "updated": True}}
    finally:
        db.close()


# ── POST /api/v1/designs/{design_id}/variants ────────────────────
@router.post("/{design_id}/variants")
async def create_design_variant(design_id: str, data: dict):
    """创建设计 + 基底产品组合（DesignVariant）"""
    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")
        variant = DesignVariant(
            design_id=design_id,
            blank_product_id=data["blank_product_id"],
            sku_code=data.get(
                "sku_code",
                f"DESIGN-{design_id[:8]}-{data['blank_product_id'][:8]}",
            ),
            base_price=data.get("base_price", 0.0),
            cost_price=data.get("cost_price", 0.0),
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)
        return {"data": {"id": variant.id, "sku_code": variant.sku_code}}
    finally:
        db.close()


# ── Helper ───────────────────────────────────────────────────────
def _design_to_dict(design: Design, include_variants: bool = False) -> dict:
    result = {
        "id": design.id,
        "tenant_id": design.tenant_id,
        "title": design.title,
        "description": design.description,
        "file_path": design.file_path,
        "thumbnail_path": design.thumbnail_path,
        "mockup_urls": design.mockup_urls,
        "tags": design.tags or [],
        "dpi": design.dpi,
        "color_mode": design.color_mode,
        "status": design.status,
        "platform_status": design.platform_status or {},
        "is_hit": design.is_hit,
        "view_count": design.view_count,
        "order_count": design.order_count,
        "created_at": str(design.created_at) if design.created_at else None,
        "updated_at": str(design.updated_at) if design.updated_at else None,
    }
    if include_variants and design.variants:
        result["variants"] = [
            {
                "id": v.id,
                "blank_product_id": v.blank_product_id,
                "sku_code": v.sku_code,
                "base_price": v.base_price,
                "cost_price": v.cost_price,
                "mockup_path": v.mockup_path,
                "status": v.status,
            }
            for v in design.variants
        ]
    return result
