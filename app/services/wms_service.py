"""
领星 WMS API 对接服务
签名算法 + 波次查询 + 响应转换
"""
import hashlib, hmac, json, time
from urllib.request import Request, urlopen
from app.core.config import get_settings

settings = get_settings()

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
