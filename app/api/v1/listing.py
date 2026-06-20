"""Listing Engine — 一键铺货 API"""
import uuid
import json
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import desc
from app.core.database import SessionLocal
from app.models.listing_job import ListingJob
from app.models.design import Design
from app.models.platform_account import PlatformAccount
from app.models.blank_product import BlankProduct

router = APIRouter()


def _job_to_dict(job: ListingJob) -> dict:
    design_title = None
    platform_name = None
    platform_shop = None
    if job.design:
        design_title = job.design.title
    if job.platform_account:
        platform_name = job.platform_account.platform
        platform_shop = job.platform_account.shop_name
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "design_id": job.design_id,
        "design_title": design_title,
        "design_variant_id": job.design_variant_id,
        "blank_product_id": job.blank_product_id,
        "platform_account_id": job.platform_account_id,
        "platform": platform_name,
        "platform_shop_name": platform_shop,
        "platform_listing_id": job.platform_listing_id,
        "platform_product_url": job.platform_product_url,
        "status": job.status,
        "error_msg": job.error_msg,
        "title_used": job.title_used,
        "description_used": job.description_used,
        "price_used": job.price_used,
        "created_at": str(job.created_at) if job.created_at else None,
        "updated_at": str(job.updated_at) if job.updated_at else None,
    }


# ── GET /api/v1/listing/ — 列出 ListingJob（分页，支持 status 过滤） ──
@router.get("/")
def list_listing_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
):
    db = SessionLocal()
    try:
        q = db.query(ListingJob)
        if status:
            q = q.filter(ListingJob.status == status)
        total = q.count()
        jobs = q.order_by(desc(ListingJob.created_at)).offset(skip).limit(limit).all()
        return {"data": [_job_to_dict(j) for j in jobs], "total": total}
    finally:
        db.close()


# ── POST /api/v1/listing/ — 创建铺货任务 ──
@router.post("/")
def create_listing_job(data: dict):
    design_id = data.get("design_id")
    platform_account_id = data.get("platform_account_id")
    title = data.get("title", "")
    price = data.get("price")
    description = data.get("description", "")
    blank_product_id = data.get("blank_product_id")
    design_variant_id = data.get("design_variant_id")

    if not design_id:
        raise HTTPException(status_code=400, detail="design_id 为必填")
    if not platform_account_id:
        raise HTTPException(status_code=400, detail="platform_account_id 为必填")

    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")

        platform = db.query(PlatformAccount).filter(
            PlatformAccount.id == platform_account_id
        ).first()
        if not platform:
            raise HTTPException(status_code=404, detail="平台账号不存在")

        # 自动获取基底产品 ID（未提供时取第一个可用基底产品）
        if not blank_product_id:
            # 先尝试从 design_variants 获取
            from app.models.design import DesignVariant
            variant = db.query(DesignVariant).filter(
                DesignVariant.design_id == design_id
            ).first()
            if variant:
                blank_product_id = variant.blank_product_id
            else:
                first_product = db.query(BlankProduct).filter(
                    BlankProduct.is_active == True
                ).first()
                if first_product:
                    blank_product_id = first_product.id
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="无可用基底产品，请先添加基底产品或提供 blank_product_id",
                    )

        job = ListingJob(
            tenant_id="default",
            design_id=design_id,
            design_variant_id=design_variant_id,
            blank_product_id=blank_product_id,
            platform_account_id=platform_account_id,
            title_used=title,
            description_used=description,
            price_used=float(price) if price else None,
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"data": _job_to_dict(job)}
    finally:
        db.close()


# ── GET /api/v1/listing/{job_id} — 任务详情 ──
@router.get("/{job_id}")
def get_listing_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(ListingJob).filter(ListingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="铺货任务不存在")
        return {"data": _job_to_dict(job)}
    finally:
        db.close()


# ── PUT /api/v1/listing/{job_id}/cancel — 取消任务 ──
@router.put("/{job_id}/cancel")
def cancel_listing_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(ListingJob).filter(ListingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="铺货任务不存在")
        if job.status not in ("pending", "processing"):
            raise HTTPException(
                status_code=400,
                detail=f"当前状态 {job.status} 不可取消，仅 pending/processing 状态可取消",
            )
        job.status = "cancelled"
        job.error_msg = "用户手动取消"
        db.commit()
        return {"data": {"id": job_id, "status": "cancelled"}}
    finally:
        db.close()


# ── POST /api/v1/listing/batch — 批量铺货 ──
@router.post("/batch")
def batch_listing(data: dict):
    design_id = data.get("design_id")
    platform_account_ids = data.get("platform_account_ids", [])
    title = data.get("title", "")
    price = data.get("price")
    description = data.get("description", "")
    blank_product_id = data.get("blank_product_id")
    design_variant_id = data.get("design_variant_id")

    if not design_id:
        raise HTTPException(status_code=400, detail="design_id 为必填")
    if not platform_account_ids or not isinstance(platform_account_ids, list):
        raise HTTPException(status_code=400, detail="platform_account_ids 为必填数组")

    db = SessionLocal()
    try:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            raise HTTPException(status_code=404, detail="设计不存在")

        # 验证所有平台账号
        platforms = db.query(PlatformAccount).filter(
            PlatformAccount.id.in_(platform_account_ids)
        ).all()
        found_ids = {p.id for p in platforms}
        missing = [pid for pid in platform_account_ids if pid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"平台账号不存在: {', '.join(missing[:3])}",
            )

        # 自动获取基底产品
        if not blank_product_id:
            from app.models.design import DesignVariant
            variant = db.query(DesignVariant).filter(
                DesignVariant.design_id == design_id
            ).first()
            if variant:
                blank_product_id = variant.blank_product_id
            else:
                first_product = db.query(BlankProduct).filter(
                    BlankProduct.is_active == True
                ).first()
                if first_product:
                    blank_product_id = first_product.id
                else:
                    raise HTTPException(
                        status_code=400, detail="无可用基底产品"
                    )

        jobs_created = []
        for pid in platform_account_ids:
            job = ListingJob(
                tenant_id="default",
                design_id=design_id,
                design_variant_id=design_variant_id,
                blank_product_id=blank_product_id,
                platform_account_id=pid,
                title_used=title,
                description_used=description,
                price_used=float(price) if price else None,
                status="pending",
            )
            db.add(job)
            db.flush()
            jobs_created.append(_job_to_dict(job))

        db.commit()
        return {"data": jobs_created, "total": len(jobs_created)}
    finally:
        db.close()
