"""
领星 WMS API 对接服务
签名算法 + 波次查询 + 订单同步 + 响应转换
"""
import hashlib, hmac, json, time, sqlite3, os
from urllib.request import Request, urlopen
from app.core.config import get_settings

settings = get_settings()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "riichain.db")

WMS_APP_KEY = "60d2da562ee3492e8bdaaea44c611910"
WMS_SECRET = "e7f3e07d4f15438da02308fa1ebf90be"
WMS_BASE_URL = "https://api.xlwms.com"


def make_sign(params: dict, path: str, secret: str) -> str:
    """HMAC-SHA256 签名"""
    sorted_keys = sorted(params.keys())

    def val_to_str(v):
        if isinstance(v, dict):
            return "{" + ",".join(f"{k}={iv}" for k, iv in v.items()) + "}"
        return str(v)

    step2 = "".join(f"{k}{val_to_str(params[k])}" for k in sorted_keys)
    sign_str = secret + path + step2 + secret
    return hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()


def classify_product_type(sku: str, product_name: str = "") -> str:
    """根据 SKU/产品名 推断类型"""
    name_lower = (sku + " " + (product_name or "")).lower()
    acc_keywords = [
        "stand", "base", "rotatable", "display", "holder", "frame",
        "mount", "bracket", "hook", "hanger", "pedestal", "chain",
        "22mm", "connector", "screw", "spacer", "ring", "pin",
    ]
    for kw in acc_keywords:
        if kw in name_lower:
            return "Accessories"
    return "Customization"


def fetch_wave_detail(wave_no: str) -> dict:
    """查询波次明细"""
    ts = str(int(time.time()))
    path = "/openapi/v2/wave/detail"
    params = {"appKey": WMS_APP_KEY, "data": {"waveNo": wave_no}, "timestamp": ts}
    sign = make_sign(params, path, WMS_SECRET)

    body = json.dumps({
        "appKey": WMS_APP_KEY,
        "data": {"waveNo": wave_no},
        "timestamp": ts,
        "sign": sign,
    }).encode("utf-8")

    req = Request(f"{WMS_BASE_URL}{path}", method="POST", data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    resp = urlopen(req, timeout=30)
    wms_data = json.loads(resp.read())

    return _transform_response(wms_data)


def _transform_response(wms_data: dict) -> dict:
    """将 WMS 响应转为 RiiChain 格式"""
    if wms_data.get("code") not in (200, "200"):
        return {"code": wms_data.get("code"), "msg": wms_data.get("message", "error"), "data": None}

    raw = wms_data.get("data", {})
    details = []
    for order in raw.get("orderList", []):
        for product in order.get("productList", []):
            sku = product.get("sku", "")
            details.append({
                "orderNo": order.get("outboundOrderNo", ""),
                "sku": sku,
                "qty": product.get("quantity", 1),
                "productType": classify_product_type(sku, product.get("productName", "")),
                "trackingNo": order.get("logisticsTrackNo", ""),
                "carrier": order.get("logisticsCarrier", ""),
                "productName": product.get("productName", ""),
                "sheetUrl": order.get("sheetUrl", ""),
            })

    return {
        "code": 0,
        "data": {
            "waveNo": raw.get("waveNo", ""),
            "waveStatus": raw.get("waveStatus"),
            "sortingStatus": raw.get("sortingStatus"),
            "reviewStatus": raw.get("reviewStatus"),
            "outboundStatus": raw.get("outboundStatus"),
            "details": details,
        }
    }


# ── Order Sync ──

def init_order_db():
    """Create synced_orders table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS synced_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT, wave_no TEXT, sku TEXT, qty INTEGER DEFAULT 1,
        product_type TEXT, tracking_no TEXT, carrier TEXT,
        product_name TEXT, sheet_url TEXT, order_date TEXT,
        synced_at TEXT, UNIQUE(order_no, sku)
    )""")
    conn.commit(); conn.close()


def sync_waves_to_db(wave_nos: list) -> dict:
    """Sync multiple waves from WMS into local database"""
    init_order_db()
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    synced_waves = 0
    synced_orders = 0
    errors = []

    for wave_no in wave_nos:
        wave_no = wave_no.strip()
        if not wave_no: continue
        try:
            result = fetch_wave_detail(wave_no)
            if result.get("code") != 0:
                errors.append({"waveNo": wave_no, "error": result.get("msg", "unknown")})
                continue
            details = result["data"]["details"]
            conn = sqlite3.connect(DB_PATH)
            for d in details:
                conn.execute("""INSERT OR REPLACE INTO synced_orders
                    (order_no, wave_no, sku, qty, product_type, tracking_no, carrier, product_name, sheet_url, order_date, synced_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (d["orderNo"], wave_no, d["sku"], d["qty"], d["productType"],
                     d.get("trackingNo",""), d.get("carrier",""), d.get("productName",""),
                     d.get("sheetUrl",""), today[:10], today))
                synced_orders += 1
            conn.commit(); conn.close()
            synced_waves += 1
        except Exception as e:
            errors.append({"waveNo": wave_no, "error": str(e)})

    return {"synced_waves": synced_waves, "synced_orders": synced_orders, "errors": errors}


def get_synced_orders(year_month: str = "") -> dict:
    """Get synced orders, optionally filtered by year-month (YYYY-MM)"""
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    if year_month:
        rows = conn.execute(
            "SELECT * FROM synced_orders WHERE order_date LIKE ? ORDER BY order_date DESC, order_no, sku",
            (year_month + "%",)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM synced_orders ORDER BY order_date DESC, order_no, sku").fetchall()
    conn.close()

    orders = [dict(r) for r in rows]

    # Calculate stats
    order_set = set()
    stats = {"total_orders": 0, "total_skus": 0, "total_qty": 0, "status_dist": []}
    for o in orders:
        order_set.add(o["order_no"])
        stats["total_qty"] += o.get("qty", 0)
    stats["total_orders"] = len(order_set)
    stats["total_skus"] = len(set(o["sku"] for o in orders))

    return {"orders": orders, "stats": stats}


def get_available_months() -> list:
    """Get list of months that have synced order data"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT substr(order_date,1,7) as ym FROM synced_orders ORDER BY ym DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]
