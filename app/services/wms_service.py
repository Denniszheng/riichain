"""
领星 WMS API 对接服务
签名算法 + 波次查询 + 订单同步（写入 wave_orders） + 响应转换
"""
import hashlib, hmac, json, time, sqlite3, os, uuid
from urllib.request import Request, urlopen
from app.core.config import get_settings

settings = get_settings()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "riichain.db")

# 从 settings 读取 WMS 密钥（pydantic-settings 会自动从 .env 文件加载）
WMS_APP_KEY = settings.WMS_APP_KEY
WMS_SECRET = settings.WMS_SECRET
WMS_BASE_URL = settings.WMS_BASE_URL


def make_sign(params: dict, path: str, secret: str) -> str:
    """HMAC-SHA256 签名（领星WMS规范）

    签名规则（来自领星官方文档）：
    第一步：按字典序排列参数名（data内的参数无需排序）
    第二步：将参数名和值拼接成字符串（格式：key1value1key2value2...）
    第三步：appSecret + path + 第二步生成的字符串 + appSecret
    第四步：HMAC-SHA256加密生成sign

    示例：
      params = {appKey: "xxx", data: {outboundNo: "OBS0212606200S0"}, timestamp: "1781975557"}
      step2 = "appKey60d2da...data{outboundNo=OBS0212606200S0}timestamp1781975557"
      sign_str = "secret/openapi/v2/delivery/detail" + step2 + "secret"
    """
    sorted_keys = sorted(params.keys())

    def val_to_str(v):
        """将值转为字符串（领星WMS格式）
        - dict 类型使用 {key=value, key2=value2} 格式（注意逗号后有空格）
        - 其他类型直接 str()
        """
        if isinstance(v, dict):
            # data 内的参数无需排序，使用 {key=value, key2=value2} 格式，逗号后有空格
            return "{" + ", ".join(f"{k}={iv}" for k, iv in v.items()) + "}"
        return str(v)

    # 第二步：按 key 字典序拼接 key+value
    step2 = "".join(f"{k}{val_to_str(params[k])}" for k in sorted_keys)

    # 第三步：secret + path + step2 + secret
    sign_str = secret + path + step2 + secret

    # 第四步：HMAC-SHA256
    return hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()


def classify_product_type(sku: str, product_name: str = "") -> str:
    """根据 SKU/产品名 推断类型"""
    name_lower = (sku + " " + (product_name or "")).lower()
    acc_keywords = [
        "stand", "base", "rotatable", "display", "holder",
        "frame", "mount", "bracket", "hook", "hanger",
        "pedestal", "chain", "22mm", "connector",
        "screw", "spacer", "ring", "pin",
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


# ── Order Sync (写入 wave_orders) ──

def sync_waves_to_db(wave_nos: list) -> dict:
    """从 WMS 同步波次数据到 wave_orders 表"""
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    synced_waves = 0
    synced_orders = 0
    errors = []

    for wave_no in wave_nos:
        wave_no = wave_no.strip()
        if not wave_no:
            continue
        try:
            result = fetch_wave_detail(wave_no)
            if result.get("code") != 0:
                errors.append({"waveNo": wave_no, "error": result.get("msg", "unknown")})
                continue
            details = result["data"]["details"]
            conn = sqlite3.connect(DB_PATH)
            for d in details:
                order_no = d["orderNo"]
                # 检查是否已存在
                existing = conn.execute(
                    "SELECT id FROM wave_orders WHERE order_no = ?", (order_no,)
                ).fetchone()
                
                if existing:
                    # 更新已有记录
                    conn.execute("""UPDATE wave_orders SET
                        wave_no = ?, sku_code = ?, qty = ?, product_type = ?,
                        tracking_no = ?, carrier = ?, sheet_url = ?, synced_at = ?
                        WHERE order_no = ?""",
                        (wave_no, d["sku"], d["qty"], d["productType"],
                         d.get("trackingNo", ""), d.get("carrier", ""),
                         d.get("sheetUrl", ""), today, order_no))
                else:
                    # 插入新记录
                    new_id = str(uuid.uuid4())
                    conn.execute("""INSERT INTO wave_orders
                        (id, order_no, wave_no, sku_code, qty, product_type,
                         tracking_no, carrier, sheet_url, synced_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (new_id, order_no, wave_no, d["sku"], d["qty"], d["productType"],
                         d.get("trackingNo", ""), d.get("carrier", ""),
                         d.get("sheetUrl", ""), today, "待处理"))
                synced_orders += 1
            conn.commit()
            conn.close()
            synced_waves += 1
        except Exception as e:
            errors.append({"waveNo": wave_no, "error": str(e)})

    return {"synced_waves": synced_waves, "synced_orders": synced_orders, "errors": errors}


def get_synced_orders(year_month: str = "") -> dict:
    """从 wave_orders 读取已同步的订单"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if year_month:
        rows = conn.execute(
            "SELECT * FROM wave_orders WHERE order_date LIKE ? ORDER BY order_date DESC, order_no",
            (year_month + "%",)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM wave_orders ORDER BY created_at DESC, order_no"
        ).fetchall()
    conn.close()

    orders = [dict(r) for r in rows]

    # 统计
    order_set = set()
    stats = {"total_orders": 0, "total_skus": 0, "total_qty": 0}
    for o in orders:
        order_set.add(o["order_no"])
        stats["total_qty"] += o.get("qty", 0)
    stats["total_orders"] = len(order_set)
    stats["total_skus"] = len(set(o.get("sku_code", "") for o in orders))

    return {"orders": orders, "stats": stats}


def get_available_months() -> list:
    """获取有订单数据的月份列表"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT substr(synced_at, 1, 7) as ym FROM wave_orders WHERE synced_at != '' ORDER BY ym DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


# ── 按日期自动同步 ──

def fetch_wave_list(date_str: str = "") -> dict:
    """
    按日期查询波次列表（领星WMS API）
    date_str: YYYY-MM-DD 格式，默认为今天
    """
    if not date_str:
        date_str = time.strftime("%Y-%m-%d")
    
    ts = str(int(time.time()))
    path = "/openapi/v2/wave/list"
    
    # 构造请求数据（按领星WMS API规范）
    data = {
        "startTime": date_str + " 00:00:00",
        "endTime": date_str + " 23:59:59",
        "pageSize": 100,
        "pageNo": 1,
    }
    
    params = {"appKey": WMS_APP_KEY, "data": data, "timestamp": ts}
    sign = make_sign(params, path, WMS_SECRET)
    
    body = json.dumps({
        "appKey": WMS_APP_KEY,
        "data": data,
        "timestamp": ts,
        "sign": sign,
    }).encode("utf-8")
    
    req = Request(f"{WMS_BASE_URL}{path}", method="POST", data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    resp = urlopen(req, timeout=30)
    wms_data = json.loads(resp.read())
    
    if wms_data.get("code") not in (200, "200"):
        return {"code": wms_data.get("code"), "msg": wms_data.get("message", "error"), "data": None}
    
    # 提取波次号列表
    wave_list = wms_data.get("data", {}).get("list", [])
    wave_nos = [w.get("waveNo", "") for w in wave_list if w.get("waveNo")]
    
    return {
        "code": 0,
        "data": {
            "date": date_str,
            "total": len(wave_nos),
            "wave_nos": wave_nos,
            "raw": wave_list,
        }
    }


def sync_orders_by_date(date_str: str = "", overwrite: bool = False) -> dict:
    """
    按日期从WMS同步订单到RiiChain
    date_str: YYYY-MM-DD 格式，默认为今天
    overwrite: 是否覆盖已存在的订单
    """
    if not date_str:
        date_str = time.strftime("%Y-%m-%d")
    
    # 1. 获取当天的波次列表
    result = fetch_wave_list(date_str)
    if result.get("code") != 0:
        return {
            "code": result.get("code"),
            "msg": f"获取波次列表失败: {result.get('msg')}",
            "data": None
        }
    
    wave_nos = result["data"]["wave_nos"]
    if not wave_nos:
        return {
            "code": 0,
            "msg": f"{date_str} 没有找到波次",
            "data": {"synced_waves": 0, "synced_orders": 0, "errors": []}
        }
    
    # 2. 同步这些波次到数据库
    sync_result = sync_waves_to_db(wave_nos)
    
    return {
        "code": 0,
        "msg": f"同步完成：{sync_result['synced_waves']}个波次，{sync_result['synced_orders']}个订单",
        "data": sync_result
    }


def sync_yesterday_orders() -> dict:
    """同步昨天的订单（用于每日定时任务）"""
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    return sync_orders_by_date(yesterday)


def sync_today_orders() -> dict:
    """同步今天的订单"""
    return sync_orders_by_date(time.strftime("%Y-%m-%d"))


# ── 订单同步（出库单 /openapi/v2/delivery/page）──

def fetch_delivery_page(date_str: str = "", page_no: int = 1, page_size: int = 50, wh_code: str = "TXMISSOURI") -> dict:
    """
    分页查询出库单（领星WMS API）
    /openapi/v2/delivery/page
    date_str: YYYY-MM-DD 格式，默认为今天
    wh_code: 仓库代码，默认为 TXMISSOURI
    """
    if not date_str:
        date_str = time.strftime("%Y-%m-%d")
    
    ts = str(int(time.time()))
    path = "/openapi/v2/delivery/page"
    
    # 领星WMS API 请求格式（根据官方示例）
    # 注意：键顺序必须为 size, status, whCode, startTime, endTime, current
    # 签名算法中 data 内部参数不排序，直接按插入顺序拼接
    data = {
        "size": page_size,
        "status": "1,2,3,4,5,6",
        "whCode": wh_code,
        "startTime": date_str + " 00:00:00",
        "endTime": date_str + " 23:59:59",
        "current": page_no,
    }
    
    params = {"appKey": WMS_APP_KEY, "data": data, "timestamp": ts}
    sign = make_sign(params, path, WMS_SECRET)
    
    body = json.dumps({
        "appKey": WMS_APP_KEY,
        "data": data,
        "timestamp": ts,
        "sign": sign,
    }).encode("utf-8")
    
    req = Request(f"{WMS_BASE_URL}{path}", method="POST", data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    
    try:
        resp = urlopen(req, timeout=30)
        wms_data = json.loads(resp.read())
    except Exception as e:
        return {
            "code": -1,
            "msg": f"API调用失败: {str(e)}",
            "data": None
        }
    
    if wms_data.get("code") not in (200, "200"):
        return {
            "code": wms_data.get("code"),
            "msg": wms_data.get("msg", "error"),
            "data": None
        }
    
    # 领星WMS返回格式：records 数组
    response_data = wms_data.get("data", {})
    
    return {
        "code": 0,
        "data": {
            "list": response_data.get("records", []),  # 统一字段名
            "total": response_data.get("total", 0),
            "page": response_data.get("page", 1),
            "pageSize": response_data.get("pageSize", page_size),
            "pages": response_data.get("pages", 1),
        }
    }


def sync_delivery_orders_by_date(date_str: str = "", overwrite: bool = False, wh_code: str = "", fetch_details: bool = False) -> dict:
    """
    按日期从WMS同步出库单到 wave_orders 表
    
    ⚠️ 注意：/openapi/v2/delivery/page 列表API只返回基本信息
    不包含产品详情（SKU、数量）、物流信息（trackingNo）等
    
    参数：
    - date_str: YYYY-MM-DD 格式，默认为今天
    - overwrite: 是否覆盖已存在的订单
    - wh_code: 仓库代码，默认为 TXMISSOURI
    - fetch_details: 是否自动获取订单详情（SKU列表、物流信息）
                    设为 True 会自动调用 /delivery/detail 接口
                    注意：每个订单都会发起一次API调用，可能较慢
    
    数据流向：
    1. 先调 /delivery/page 同步订单列表（outboundNo、status等基本信息）
    2. 如果 fetch_details=True，再调 /delivery/detail 获取产品详情和物流信息
    3. 所有信息写入 wave_orders 表
    """
    if not date_str:
        date_str = time.strftime("%Y-%m-%d")
    
    if not wh_code:
        wh_code = settings.WMS_WH_CODE or "TXMISSOURI"
    
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    synced_orders = 0
    skipped_orders = 0
    errors = []
    synced_outbound_nos = []  # 收集已同步的订单号，用于后续获取详情
    
    # 领星WMS状态码映射（数字 → 可读状态）
    # 1=待处理, 2=已打印, 3=已拣货, 4=已复核, 5=已出库, 6=已取消
    status_map = {
        1: "pending",
        2: "printed",
        3: "picked",
        4: "reviewed",
        5: "shipped",
        6: "cancelled",
    }
    
    page_no = 1
    page_size = 50
    total_pages = 1
    
    while page_no <= total_pages:
        try:
            result = fetch_delivery_page(date_str, page_no, page_size, wh_code)
            if result.get("code") != 0:
                errors.append({"page": page_no, "error": result.get("msg", "unknown")})
                break
            
            response_data = result["data"]
            orders = response_data.get("list", [])   # 领星返回 records，fetch_delivery_page 已统一为 list
            total_pages = max(1, response_data.get("pages", 1))
            
            if not orders:
                break
            
            conn = sqlite3.connect(DB_PATH)
            
            for order in orders:
                try:
                    # ------ 领星WMS /delivery/page 实际返回字段（根据官方示例）------
                    # outboundNo, referOrderNo, platformOrderNo, status, customerCode
                    order_no   = order.get("outboundNo", "")
                    if not order_no:
                        continue
                    
                    # 状态码：领星返回数字 1-6
                    wms_status   = order.get("status", 1)
                    custom_status = status_map.get(int(wms_status), "pending")
                    
                    # 查询是否已存在
                    existing = conn.execute(
                        "SELECT id FROM wave_orders WHERE order_no = ?", (order_no,)
                    ).fetchone()
                    
                    if existing and not overwrite:
                        skipped_orders += 1
                        continue
                    
                    # ------ 列表API不包含产品详情，只存基本信息 ------
                    # 产品详情（SKU、数量）需要通过 /delivery/detail 接口获取
                    if existing:
                        conn.execute(
                            "UPDATE wave_orders SET custom_status = ?, synced_at = ? WHERE order_no = ?",
                            (custom_status, today, order_no)
                        )
                    else:
                        new_id = str(uuid.uuid4())
                        conn.execute(
                            """INSERT INTO wave_orders
                               (id, order_no, custom_status, synced_at, status)
                               VALUES (?, ?, ?, ?, ?)""",
                            (new_id, order_no, custom_status, today, "待处理")
                        )
                    
                    synced_orders += 1
                    synced_outbound_nos.append(order_no)  # 收集订单号
                    
                except Exception as e:
                    errors.append({"orderNo": order.get("outboundNo", ""), "error": str(e)})
            
            conn.commit()
            conn.close()
            page_no += 1
            
        except Exception as e:
            errors.append({"page": page_no, "error": str(e)})
            break
    
    # ------ 如果需要获取订单详情 ------
    detail_result = None
    if fetch_details and synced_outbound_nos:
        try:
            detail_result = sync_order_details(synced_outbound_nos)
        except Exception as e:
            errors.append({"stage": "fetch_details", "error": str(e)})
    
    # ------ 返回结果 ------
    result = {
        "synced_orders": synced_orders,
        "skipped_orders": skipped_orders,
        "total_pages": total_pages,
        "errors": errors
    }
    
    if detail_result:
        result["detail_result"] = detail_result
    
    return result


# ── 工具函数：根据 outboundNo 获取订单产品详情 ──

def fetch_order_detail(outbound_no: str) -> dict:
    """
    获取单个出库单的详情（含产品列表）
    /openapi/v2/delivery/detail
    
    返回格式（根据官方示例）：
    {
      "code": 200,
      "data": {
        "total": 1,
        "deliveryDetailList": [
          {
            "outboundNo": "OBS0212606200S0",
            "referOrderNo": "OBS0222606200S0",
            "platformOrderNo": "PO-211-07017416269430253",
            "customerCode": "QS3X021",
            "logisticsTrackNo": "873311453247",
            "labelUrl": "https://...",
            "packageList": [...],
            "skuList": [
              {
                "sku": "ZGBC12V100AH100BT",
                "barcode": "",
                "productName": "12.8V100AH-蓝牙",
                "quantity": 1,
                "cellPreList": [...]
              }
            ]
          }
        ]
      },
      "msg": "操作成功"
    }
    """
    ts = str(int(time.time()))
    path = "/openapi/v2/delivery/detail"
    
    # 请求格式（根据官方示例）
    data = {
        "outboundNo": outbound_no
    }
    
    params = {"appKey": WMS_APP_KEY, "data": data, "timestamp": ts}
    sign = make_sign(params, path, WMS_SECRET)
    
    body = json.dumps({
        "appKey": WMS_APP_KEY,
        "data": data,
        "timestamp": ts,
        "sign": sign,
    }).encode("utf-8")
    
    req = Request(f"{WMS_BASE_URL}{path}", method="POST", data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    
    try:
        resp = urlopen(req, timeout=30)
        wms_data = json.loads(resp.read())
    except Exception as e:
        return {
            "code": -1,
            "msg": f"API调用失败: {str(e)}",
            "data": None
        }
    
    if wms_data.get("code") not in (200, "200"):
        return {
            "code": wms_data.get("code"),
            "msg": wms_data.get("msg", "error"),
            "data": None
        }
    
    # 提取订单详情
    response_data = wms_data.get("data", {})
    detail_list = response_data.get("deliveryDetailList", [])
    
    if not detail_list:
        return {
            "code": 404,
            "msg": "未找到订单详情",
            "data": None
        }
    
    # 返回第一个匹配的订单详情
    order_detail = detail_list[0]
    
    return {
        "code": 0,
        "msg": wms_data.get("msg", "操作成功"),
        "data": {
            "outboundNo": order_detail.get("outboundNo", ""),
            "referOrderNo": order_detail.get("referOrderNo", ""),
            "platformOrderNo": order_detail.get("platformOrderNo", ""),
            "customerCode": order_detail.get("customerCode", ""),
            "logisticsTrackNo": order_detail.get("logisticsTrackNo", ""),
            "labelUrl": order_detail.get("labelUrl", ""),
            "packageList": order_detail.get("packageList", []),
            "skuList": order_detail.get("skuList", []),
        }
    }


def sync_order_details(outbound_nos: list) -> dict:
    """
    根据出库单号列表，从WMS获取订单详情（含SKU列表），并更新到 wave_orders 表
    
    数据流向：
    1. 先调 /delivery/page 同步订单列表（基本信息）
    2. 再调此函数，根据 outboundNo 获取订单详情（SKU、物流信息）
    3. 将详情写入 wave_orders 表（每个SKU一行）
    
    注意：
    - 一个订单可能有多个SKU，会在 wave_orders 表中生成多行
    - 如果订单已存在SKU记录，则更新；否则插入
    """
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    synced_orders = 0
    synced_skus  = 0
    errors = []
    
    for outbound_no in outbound_nos:
        outbound_no = outbound_no.strip()
        if not outbound_no:
            continue
        
        try:
            # 1. 获取订单详情
            result = fetch_order_detail(outbound_no)
            if result.get("code") != 0:
                errors.append({"outboundNo": outbound_no, "error": result.get("msg", "unknown")})
                continue
            
            order_detail = result["data"]
            sku_list = order_detail.get("skuList", [])
            
            if not sku_list:
                errors.append({"outboundNo": outbound_no, "error": "订单无SKU信息"})
                continue
            
            # 2. 连接数据库
            conn = sqlite3.connect(DB_PATH)
            
            # 3. 先更新订单基本信息（物流单号、面单URL、参考订单号等）
            # 更新所有该订单的行（包括有SKU和没有SKU的）
            conn.execute(
                """UPDATE wave_orders SET 
                    tracking_no = ?, 
                    label_url = ?,
                    refer_order_no = ?,
                    platform_order_no = ?,
                    customer_code = ?,
                    synced_at = ?
                   WHERE order_no = ?""",
                (order_detail.get("logisticsTrackNo", ""),
                 order_detail.get("labelUrl", ""),
                 order_detail.get("referOrderNo", ""),
                 order_detail.get("platformOrderNo", ""),
                 order_detail.get("customerCode", ""),
                 today,
                 outbound_no)
            )
            
            # 4. 处理每个SKU
            for sku_item in sku_list:
                sku_code = sku_item.get("sku", "")
                if not sku_code:
                    continue
                
                qty = sku_item.get("quantity", 1)
                product_name = sku_item.get("productName", "")
                product_type = classify_product_type(sku_code, product_name)
                
                # 查询是否已存在该订单+SKU的组合
                existing = conn.execute(
                    "SELECT id FROM wave_orders WHERE order_no = ? AND sku_code = ?",
                    (outbound_no, sku_code)
                ).fetchone()
                
                if existing:
                    # 更新已有记录
                    conn.execute(
                        """UPDATE wave_orders SET 
                            qty = ?, 
                            product_type = ?,
                            product_name = ?,
                            synced_at = ?
                           WHERE id = ?""",
                        (qty, product_type, product_name, today, existing[0])
                    )
                else:
                    # 插入新记录
                    new_id = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO wave_orders
                           (id, order_no, sku_code, qty, product_type,
                            product_name, tracking_no, label_url, 
                            refer_order_no, platform_order_no, customer_code,
                            synced_at, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (new_id, outbound_no, sku_code, qty, product_type,
                         product_name,
                         order_detail.get("logisticsTrackNo", ""),
                         order_detail.get("labelUrl", ""),
                         order_detail.get("referOrderNo", ""),
                         order_detail.get("platformOrderNo", ""),
                         order_detail.get("customerCode", ""),
                         today, "待处理")
                    )
                
                synced_skus += 1
            
            conn.commit()
            conn.close()
            synced_orders += 1
            
        except Exception as e:
            errors.append({"outboundNo": outbound_no, "error": str(e)})
    
    return {
        "synced_orders": synced_orders,
        "synced_skus": synced_skus,
        "errors": errors
    }


def sync_wave_details_for_orders(wave_nos: list) -> dict:
    """
    根据波次号列表，从WMS获取波次详情（含产品列表），并更新到 wave_orders 表
    适用场景：WMS中已创建波次后，同步产品详情到RiiChain
    """
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    synced_waves = 0
    synced_skus  = 0
    errors = []

    for wave_no in wave_nos:
        wave_no = wave_no.strip()
        if not wave_no:
            continue
        try:
            result = fetch_wave_detail(wave_no)
            if result.get("code") != 0:
                errors.append({"waveNo": wave_no, "error": result.get("msg", "unknown")})
                continue

            details = result["data"]["details"]
            conn = sqlite3.connect(DB_PATH)

            for d in details:
                order_no = d["orderNo"]
                # 检查该订单是否已存在
                existing = conn.execute(
                    "SELECT id FROM wave_orders WHERE order_no = ? AND sku_code = ?",
                    (order_no, d.get("sku", ""))
                ).fetchone()

                if existing:
                    conn.execute("""UPDATE wave_orders SET
                        wave_no = ?, sku_code = ?, qty = ?, product_type = ?,
                        tracking_no = ?, carrier = ?, sheet_url = ?, synced_at = ?
                        WHERE id = ?""",
                        (wave_no, d["sku"], d["qty"], d["productType"],
                         d.get("trackingNo", ""), d.get("carrier", ""),
                         d.get("sheetUrl", ""), today, existing[0]))
                else:
                    new_id = str(uuid.uuid4())
                    conn.execute("""INSERT INTO wave_orders
                        (id, order_no, wave_no, sku_code, qty,
                         product_type, tracking_no, carrier,
                         sheet_url, synced_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (new_id, order_no, wave_no, d["sku"], d["qty"],
                         d["productType"], d.get("trackingNo", ""),
                         d.get("carrier", ""), d.get("sheetUrl", ""),
                         today, "待处理"))
                synced_skus += 1

            conn.commit()
            conn.close()
            synced_waves += 1

        except Exception as e:
            errors.append({"waveNo": wave_no, "error": str(e)})

    return {"synced_waves": synced_waves, "synced_skus": synced_skus, "errors": errors}


def sync_today_delivery_orders() -> dict:
    """同步今天的出库单"""
    return sync_delivery_orders_by_date(time.strftime("%Y-%m-%d"))


def sync_yesterday_delivery_orders() -> dict:
    """同步昨天的出库单（用于每日定时任务）"""
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    return sync_delivery_orders_by_date(yesterday)
