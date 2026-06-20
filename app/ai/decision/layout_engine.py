"""
RiiChain Layout Engine — 2D 嵌套排版算法 for POD 亚克力板。
- 优先使用 pyckingsolver（专业级 CNC 嵌套）
- 降级使用贪心 Shelf 算法
- 排版前检查耗材库存（MaterialInventory）
"""
import math
import time
from typing import List, Optional
from collections import defaultdict

BOARD_SIZES = {
    "480x480": (480, 480),
    "600x600": (600, 600),
    "300x400": (300, 400),
}


def optimize_layout(orders: list, board_size: str = "480x480", db=None) -> dict:
    """优化 SKU 在亚克力板上的放置方案。

    Args:
        orders: [{"order_no":"OBS001","skus":[{"sku":"A","qty":3,"w":50,"h":80},...]},...]
        board_size: "480x480" | "600x600" | "300x400"
        db: SQLAlchemy Session（可选，用于检查耗材库存）

    Returns:
        {board_size, total_boards, boards:[{placements:[]}], overall_utilization, engine, ...}
    """
    bw, bh = BOARD_SIZES.get(board_size, (480, 480))

    # Flatten orders → rectangles
    rects = []
    for order in orders:
        for sku in order.get("skus", []):
            w = float(sku.get("w", 80))
            h = float(sku.get("h", 60))
            qty = int(sku.get("qty", 1))
            for _ in range(qty):
                rects.append({
                    "sku": sku.get("sku", "?"),
                    "order_no": order.get("order_no", "?"),
                    "w": w, "h": h,
                })

    if not rects:
        return {"error": "No items to place", "boards": [], "total_boards": 0}

    # Check material stock
    if db:
        try:
            from app.models.wave import MaterialInventory
            mat = db.query(MaterialInventory).filter(
                MaterialInventory.board_size == board_size
            ).first()
            if mat and mat.qty_on_hand < 1:
                return {
                    "error": f"板材 {board_size} 库存不足，请补充耗材",
                    "board_size": board_size,
                    "stock_available": mat.qty_on_hand,
                    "boards": [],
                    "total_boards": 0,
                    "overall_utilization": 0,
                    "engine": "blocked_no_stock",
                }
        except Exception:
            pass  # Table doesn't exist yet, allow layout anyway

    # Try pyckingsolver first, fall back to greedy
    try:
        result = _nest_with_pyckingsolver(rects, bw, bh, board_size)
        if result["total_boards"] == 0:
            raise ValueError("pyckingsolver returned 0 boards")
        return result
    except Exception as e:
        print(f"[LayoutEngine] pyckingsolver unavailable ({e}), falling back to greedy")
        return _nest_with_greedy(rects, bw, bh, board_size)


def _nest_with_pyckingsolver(rects: list, bw: float, bh: float, board_size: str) -> dict:
    """pyckingsolver 专业嵌套算法"""
    from pyckingsolver import nest, Objective
    from shapely.geometry import box

    shapes = [box(0, 0, r["w"], r["h"]) for r in rects]

    start = time.time()
    time_limit = max(5, min(60, 5 + len(shapes) * 0.5))
    sol = nest(
        shapes,
        bins=(int(bw), int(bh)),
        objective=Objective.BIN_PACKING,
        spacing=1.5,
        allowed_rotations=[(0, 0), (90, 90)],
        time_limit=time_limit,
    )
    elapsed = time.time() - start

    total_bins = sol.total_bins_used()
    total_area = total_bins * bw * bh
    used_area = 0
    boards = []
    order_board_map = defaultdict(set)

    for bi, b in enumerate(sol.bins):
        placements = []
        bin_used = 0
        for it in b.items:
            bounds = it.shapes[0].bounds
            iw = bounds[2] - bounds[0]
            ih = bounds[3] - bounds[1]
            ix = it.x
            iy = it.y

            shape_idx = it.item_type_id - 1
            if 0 <= shape_idx < len(rects):
                r = rects[shape_idx]
            else:
                r = rects[0]

            bin_used += iw * ih
            order_board_map[r["order_no"]].add(bi)
            placements.append({
                "sku": r["sku"],
                "order_no": r["order_no"],
                "x": round(ix, 1), "y": round(iy, 1),
                "w": round(iw, 1), "h": round(ih, 1),
                "rotated": abs(it.angle - 90) < 1,
            })

        used_area += bin_used
        boards.append({
            "name": f"Board {bi + 1}",
            "width": bw, "height": bh,
            "fill_rate": round(bin_used / (bw * bh), 3),
            "sku_count": len(set(p["sku"] for p in placements)),
            "order_count": len(set(p["order_no"] for p in placements)),
            "placements": placements,
        })

    utilization = used_area / total_area if total_area > 0 else 0
    split_orders = [on for on, bs in order_board_map.items() if len(bs) > 1]

    return {
        "board_size": board_size,
        "total_boards": total_bins,
        "boards": boards,
        "overall_utilization": round(utilization, 3),
        "waste_area_sqmm": round(total_area - used_area, 1),
        "split_orders": split_orders,
        "split_count": len(split_orders),
        "total_skus_placed": len(rects),
        "engine": "pyckingsolver",
        "solve_time_s": round(elapsed, 2),
    }


def _nest_with_greedy(rects: list, bw: float, bh: float, board_size: str) -> dict:
    """贪心 Shelf 算法 — pyckingsolver 不可用时的降级方案"""
    sorted_rects = sorted(enumerate(rects), key=lambda x: x[1]["w"] * x[1]["h"], reverse=True)

    boards = [[]]
    for idx, r in sorted_rects:
        placed = False
        placed_r = None
        best_y = float("inf")

        for bi, br_list in enumerate(boards):
            for rotated in [False, True]:
                rw = r["h"] if rotated else r["w"]
                rh = r["w"] if rotated else r["h"]
                if rw > bw or rh > bh:
                    continue

                for x in range(0, int(bw - rw) + 1, max(1, int(min(rw, rh) // 2))):
                    for y in range(0, int(bh - rh) + 1, max(1, int(min(rw, rh) // 2))):
                        overlap = False
                        for pr in br_list:
                            if not (
                                x + rw <= pr["x"] or x >= pr["x"] + pr["w"]
                                or y + rh <= pr["y"] or y >= pr["y"] + pr["h"]
                            ):
                                overlap = True
                                break
                        if not overlap and y < best_y:
                            best_y = y
                            placed_r = {
                                "idx": idx, "sku": r["sku"], "order_no": r["order_no"],
                                "x": x, "y": y, "w": int(rw), "h": int(rh), "rotated": rotated,
                            }
                            placed = True

            if placed:
                br_list.append(placed_r)
                break

        if not placed:
            for rotated in [False, True]:
                rw = r["h"] if rotated else r["w"]
                rh = r["w"] if rotated else r["h"]
                if rw <= bw and rh <= bh:
                    boards.append([{
                        "idx": idx, "sku": r["sku"], "order_no": r["order_no"],
                        "x": 0, "y": 0, "w": int(rw), "h": int(rh), "rotated": rotated,
                    }])
                    break

    total_boards = len(boards)
    total_area = total_boards * bw * bh
    used_area = sum(pr["w"] * pr["h"] for br in boards for pr in br)
    utilization = used_area / total_area if total_area > 0 else 0

    order_board_map = defaultdict(set)
    for bi, br in enumerate(boards):
        for pr in br:
            order_board_map[pr["order_no"]].add(bi)
    split_orders = [on for on, bs in order_board_map.items() if len(bs) > 1]

    return {
        "board_size": board_size,
        "total_boards": total_boards,
        "boards": [{
            "name": f"Board {i+1}", "width": bw, "height": bh,
            "fill_rate": round(sum(p["w"]*p["h"] for p in br) / (bw*bh), 3),
            "sku_count": len(set(p["sku"] for p in br)),
            "order_count": len(set(p["order_no"] for p in br)),
            "placements": [{"sku":p["sku"],"order_no":p["order_no"],"x":p["x"],"y":p["y"],"w":p["w"],"h":p["h"],"rotated":p["rotated"]} for p in br],
        } for i, br in enumerate(boards)],
        "overall_utilization": round(utilization, 3),
        "waste_area_sqmm": round(total_area - used_area, 1),
        "split_orders": split_orders,
        "split_count": len(split_orders),
        "total_skus_placed": sum(len(br) for br in boards),
        "engine": "greedy",
        "solve_time_s": 0,
    }
