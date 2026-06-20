"""Platform Accounts — 平台账号管理 API"""
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import desc
from app.core.database import SessionLocal
from app.models.platform_account import PlatformAccount

router = APIRouter()


def _account_to_dict(acc: PlatformAccount) -> dict:
    return {
        "id": acc.id,
        "tenant_id": acc.tenant_id,
        "platform": acc.platform,
        "shop_name": acc.shop_name,
        "shop_id": acc.shop_id,
        "is_active": acc.is_active,
        "token_expires_at": str(acc.token_expires_at) if acc.token_expires_at else None,
        "is_token_expired": acc.is_token_expired(),
        "created_at": str(acc.created_at) if acc.created_at else None,
        "updated_at": str(acc.updated_at) if acc.updated_at else None,
    }


# ── GET /api/v1/platforms/ — 列出平台账号 ──
@router.get("/")
def list_platform_accounts(platform: str | None = Query(None)):
    db = SessionLocal()
    try:
        q = db.query(PlatformAccount)
        if platform:
            q = q.filter(PlatformAccount.platform == platform)
        accounts = q.order_by(desc(PlatformAccount.updated_at)).all()
        return {"data": [_account_to_dict(a) for a in accounts], "total": len(accounts)}
    finally:
        db.close()


# ── POST /api/v1/platforms/ — 添加平台账号 ──
@router.post("/")
def create_platform_account(data: dict):
    platform = data.get("platform", "").strip().lower()
    shop_name = data.get("shop_name", "").strip()
    shop_id = data.get("shop_id")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    valid_platforms = ["tiktok", "shopify", "amazon", "shopee", "lazada", "etsy"]
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"无效平台类型，支持: {', '.join(valid_platforms)}",
        )
    if not shop_name:
        raise HTTPException(status_code=400, detail="shop_name 为必填")

    db = SessionLocal()
    try:
        account = PlatformAccount(
            tenant_id="default",
            platform=platform,
            shop_name=shop_name,
            shop_id=shop_id,
            access_token=access_token,
            refresh_token=refresh_token,
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return {"data": _account_to_dict(account)}
    finally:
        db.close()


# ── PUT /api/v1/platforms/{account_id}/toggle — 启用/禁用 ──
@router.put("/{account_id}/toggle")
def toggle_platform_account(account_id: str):
    db = SessionLocal()
    try:
        account = db.query(PlatformAccount).filter(
            PlatformAccount.id == account_id
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="平台账号不存在")
        account.is_active = not account.is_active
        db.commit()
        return {
            "data": {
                "id": account_id,
                "is_active": account.is_active,
            }
        }
    finally:
        db.close()


# ── DELETE /api/v1/platforms/{account_id} — 删除 ──
@router.delete("/{account_id}")
def delete_platform_account(account_id: str):
    db = SessionLocal()
    try:
        account = db.query(PlatformAccount).filter(
            PlatformAccount.id == account_id
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="平台账号不存在")
        db.delete(account)
        db.commit()
        return {"data": {"id": account_id, "deleted": True}}
    finally:
        db.close()
