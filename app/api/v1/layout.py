"""Layout Engine — 一键排版 API（接入 pyckingsolver 排版引擎）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.ai.decision.layout_engine import optimize_layout as run_layout

router = APIRouter()


@router.post("/optimize")
def optimize_layout(data: dict, db: Session = Depends(get_db)):
    """
    执行一键排版：
    输入：订单列表（SKU + 尺寸 + 数量）+ 板材尺寸
    输出：排版方案（坐标 + 利用率）
    """
    orders = data.get("orders", [])
    board_size = data.get("board_size", "480x480")

    if not orders:
        raise HTTPException(400, "订单列表不能为空")

    result = run_layout(orders, board_size, db=db)
    return result


@router.get("/boards")
def list_board_sizes():
    """列出支持的板材尺寸"""
    return {
        "sizes": [
            {"code": "480x480", "name": "480×480mm (标准)", "default": True},
            {"code": "600x600", "name": "600×600mm (大板)", "default": False},
            {"code": "300x400", "name": "300×400mm (小板)", "default": False},
        ]
    }


@router.get("/history")
def list_layout_history(skip: int = 0, limit: int = 20):
    """排版历史记录（暂用 Stub，后续补全持久化存储）"""
    return {"message": "排版历史 — 待持久化存储", "data": [], "total": 0}
