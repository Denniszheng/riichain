# RiiChain 新框架设计方案 v2.0

> 定位：POD（Print on Demand，按需印刷）行业专用全链路系统  
> 设计人：Austin Zheng  
> 日期：2026-06-10  
> 基础：在 pod-platform 现有代码基础上重构升级

---

## 一、核心设计理念

### 1.1 POD 的本质
传统仓储有「库存」，POD 的「库存」是**设计文件 + 空白耗材**。  
订单来了才生产，没有成品库存，所以不需要传统 WMS 的入库/上架/拣货逻辑。

### 1.2 RiiChain 与传统系统的区别

| 传统 WMS/ERP | RiiChain (POD专用) |
|-------------|---------------------|
| 管理实体库存 | 管理设计文件（数字资产） |
| 采购→入库→存储→拣货→出库 | 设计→接单→排版→打印→异形切割→分货→发货 |
| 以 SKU 为中心 | 以 Design + Blank 组合为中心 |
| 库存准确率是关键 | 设计覆盖率 + 爆款识别是关键 |

### 1.3 一块亚克力板 = 一个 Wave
这是你的核心生产逻辑，必须保留并强化：
1. 多个订单按尺寸智能排版到一块大板上
2. 打印完成后，按订单拆分（分货）
3. 每个订单进入后续打包发货流程

---

## 二、六大核心模块（融合现有代码）

### Module 1：Design Hub（设计管理）⭐ 新增重点
**现有基础**：`design.py` 模型已有，但缺少完整的 UI 和管理能力

**需要新增**：
- 设计库列表（缩略图网格视图）
- 设计上传（支持 PSD/AI/PNG，自动提取 DPI/色彩模式）
- Mockup 自动生成（设计图 + 空白产品效果图合成）
- 设计状态流转：`草稿` → `待发布` → `已发布` → `已下线`
- 设计标签管理（风格/主题/适用产品）
- 爆款标记（手动 + 销售数据驱动）

**数据库变更**：
```sql
ALTER TABLE designs ADD COLUMN mockup_urls JSON;      -- 多角度 Mockup
ALTER TABLE designs ADD COLUMN platform_status JSON;   -- {"tiktok":"published","shopify":"draft"}
ALTER TABLE designs ADD COLUMN is_hit BOOLEAN DEFAULT FALSE;  -- 爆款标记
ALTER TABLE designs ADD COLUMN view_count INT DEFAULT 0;
ALTER TABLE designs ADD COLUMN order_count INT DEFAULT 0;
```

---

### Module 2：Listing Engine（一键铺货）⭐ 全新模块
**功能**：一个设计，一键发布到多个跨境电商平台

**支持平台（分阶段）**：
- Phase 1：TikTok Shop、Shopify
- Phase 2：Amazon SP-API、Shopee
- Phase 3：Lazada、Temu

**核心流程**：
```
选择设计 + 选择基底产品（T恤/杯子/手机壳...）
    ↓
系统自动生成 Listing（标题/描述/价格/标签）
    ↓
用户确认/编辑
    ↓
一键推送到选中平台（调用各平台 API）
    ↓
记录各平台发布状态（design.platform_status）
```

**API 对接核心**：
- TikTok Shop：OAuth 2.0 授权，Product Create API
- Shopify：Private App + Admin API（GraphQL 优先）
- Amazon：SP-API，需要 MWS 迁移，难度最高

**数据库新增**：
```sql
CREATE TABLE platform_accounts (
    id STRING PRIMARY KEY,
    tenant_id STRING,
    platform STRING,          -- tiktok, shopify, amazon
    shop_name STRING,
    access_token STRING,
    refresh_token STRING,
    token_expires_at DATETIME,
    shop_id STRING,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE listing_jobs (
    id STRING PRIMARY KEY,
    design_id STRING,
    blank_product_id STRING,
    platform STRING,
    platform_listing_id STRING,
    status STRING,  -- pending, success, failed
    error_msg TEXT,
    created_at DATETIME
);
```

---

### Module 3：Order Router（订单路由）⚠️ 补全接口
**现有基础**：`OrderRouting` 模型已有，四维度评分逻辑已定义，**但 API 接口未实现**

**需要补全**：
- `POST /api/orders/{id}/route` — 执行路由决策
- 路由规则配置界面（各评分维度权重可调）
- 路由结果人工覆盖（自动路由不对，可以手动改）

**路由逻辑（已有模型，需实现）**：
```
proximity_score: 印刷厂到客户的距离（近=高分）
stock_score:    空白耗材库存是否充足（有货=高分）
capacity_score: 印刷厂当前产能余量（有余量=高分）
cost_score:     综合成本（低=高分）
total_score:    加权平均，最高分胜出
```

---

### Module 4：Layout Engine（一键排版）✅ 已完成
**现有基础**：`layout_engine.py` 使用专业级 `pyckingsolver` 嵌套算法

**现状评估**：代码质量高，算法专业，无需大改  
**需要补全**：
- 排版结果可视化预览（HTML5 Canvas 展示排版图）
- 排版历史记录（同一批订单多次排版可对比）
- 耗材自动扣减（排版成功后自动减少 `material_inventory`）

**数据库已有**：
```sql
-- material_inventory 表已存在，记录各尺寸亚克力板库存
-- layout 相关 API 已实现：/api/layout/optimize
```

---

### Module 5：Wave & Fulfillment（波次与履约）✅ 已完成
**现有基础**：`pod.py` 中的 `WaveImport`/`WaveOrder` 模型 + `wave.py` API

**核心流程（你的原始设计，非常合理）**：
1. Excel 导入订单（已实现）
2. 系统自动排版，生成 Wave 方案
3. 打印完成后，按 WaveOrder 分货（一个亚克力板 = 一个 Wave）
4. 分货完成后，打包、贴面单、发货

**需要补全**：
- 分货界面（扫描订单号，系统提示放在哪个托盘/袋子）
- 面单打印集成（对接快递公司 API 或本地打印）
- 发货确认（批量标记 `shipped`，回传追踪号到平台）

---

### Module 6：Analytics（销售分析）⭐ 全新模块
**功能**：数据驱动选品，决定赚不赚钱

**核心报表**：
1. **设计维度**：哪个设计卖得最好（销量/销售额/利润率排名）
2. **平台维度**：哪个平台 ROI 最高（考虑平台佣金/流量成本）
3. **产品维度**：哪个基底产品最赚钱（T恤 vs 杯子 vs 手机壳）
4. **时间维度**：日/周/月销售趋势，识别季节性
5. **爆款预测**：基于点击率/加购率/转化率的早期信号

**数据库新增**：
```sql
CREATE TABLE sales_analytics (
    id STRING PRIMARY KEY,
    design_id STRING,
    platform STRING,
    date DATE,
    views INT DEFAULT 0,
    clicks INT DEFAULT 0,
    orders INT DEFAULT 0,
    revenue FLOAT DEFAULT 0,
    ad_spend FLOAT DEFAULT 0,
    roi FLOAT
);
```

---

## 三、技术架构

### 3.1 技术栈（沿用现有，保持一致性）

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 后端框架 | **FastAPI** | 现有 pod-platform 已用，继续使用 |
| ORM | **SQLAlchemy 2.0** | 现有已用，继续使用 |
| 数据库 | **SQLite（开发）/ PostgreSQL（生产）** | 现有已用 |
| 排版算法 | **pyckingsolver** | 现有已用，专业级嵌套算法 |
| 前端框架 | **Vanilla JS + 未来可升级 Vue/React** | 现有用 Jinja2 + JS，保持简单 |
| 多平台对接 | **httpx（异步 HTTP）** | 用于调用 TikTok/Shopify 等 API |

### 3.2 项目目录结构（重构后）

```
riichain/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   │
│   ├── models/                 # 数据模型
│   │   ├── base.py             # TimestampMixin, UUIDMixin
│   │   ├── design.py           # Design, DesignVariant
│   │   ├── blank_product.py    # BlankProduct, ProductVariant
│   │   ├── order.py            # Order, OrderItem, OrderRouting
│   │   ├── print_job.py        # PrintJob
│   │   ├── pod.py              # WaveImport, WaveOrder, MaterialInventory...
│   │   ├── platform_account.py # 新增：平台账号
│   │   ├── listing_job.py      # 新增：铺货任务
│   │   └── analytics.py       # 新增：销售分析
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── designs.py      # 设计管理 API（补全）
│   │       ├── products.py     # 基底产品 API
│   │       ├── orders.py       # 订单 API（补全路由）
│   │       ├── wave.py         # Wave 管理 API
│   │       ├── layout.py       # 排版 API
│   │       ├── listing.py      # 新增：一键铺货 API
│   │       ├── analytics.py    # 新增：销售分析 API
│   │       └── platforms/      # 新增：各平台对接
│   │           ├── tiktok.py
│   │           ├── shopify.py
│   │           └── base.py     # 平台对接抽象基类
│   │
│   ├── ai/                    # AI 功能（现有）
│   │   ├── decision/
│   │   │   └── layout_engine.py  # 排版引擎（保留）
│   │   ├── llm/
│   │   └── nlp/
│   │
│   ├── services/              # 新增：业务服务层
│   │   ├── design_service.py
│   │   ├── listing_service.py  # 一键铺货核心逻辑
│   │   ├── order_service.py
│   │   ├── analytics_service.py
│   │   └── platform_adapters/  # 平台适配器
│   │       ├── base_adapter.py
│   │       ├── tiktok_adapter.py
│   │       └── shopify_adapter.py
│   │
│   ├── templates/             # Jinja2 模板
│   │   ├── base.html
│   │   ├── designs.html        # 新增：设计库页面
│   │   ├── listing.html        # 新增：一键铺货页面
│   │   ├── analytics.html      # 新增：销售分析页面
│   │   ├── orders.html
│   │   ├── wave.html
│   │   └── layout.html
│   │
│   └── static/                # 静态资源
│       ├── css/
│       ├── js/
│       ├── uploads/designs/   # 设计文件上传目录
│       └── outputs/layouts/  # 排版结果输出目录
│
├── scripts/                   # 工具脚本
├── tests/                     # 单元测试
├── requirements.txt
└── README.md
```

### 3.3 数据库 E-R 关系图

```
Design (设计)
  ├── 1:N → DesignVariant（设计+基底组合）
  └── 1:N → ListingJob（铺货记录）

BlankProduct (基底产品)
  ├── 1:N → ProductVariant（尺寸/颜色变体）
  └── 1:N → DesignVariant

Order (订单)
  ├── 1:N → OrderItem
  └── 1:N → OrderRouting

PrintJob (打印任务)
  └── 1:1 → OrderItem

WaveImport → 1:N → WaveOrder（波次订单）

PlatformAccount（平台账号）  ← 新增
ListingJob（铺货任务）        ← 新增
Analytics（销售分析）          ← 新增
```

---

## 四、实施路线图

### Phase 1：基础重构（1-2周）
- [ ] 创建 riichain 新项目目录
- [ ] 迁移现有模型（design/blank_product/order/print_job/pod）
- [ ] 补全缺失的 API 接口（订单路由）
- [ ] 数据库迁移脚本

### Phase 2：Design Hub（1周）⭐
- [ ] 设计库 UI（缩略图网格 + 列表切换）
- [ ] 设计上传（拖拽上传 + 自动提取元数据）
- [ ] Mockup 自动生成（Pillow 合成）
- [ ] 设计状态流转

### Phase 3：Listing Engine（2周）⭐⭐
- [ ] 平台账号 OAuth 授权管理
- [ ] TikTok Shop API 对接（产品创建/更新/删除）
- [ ] Shopify Admin API 对接（GraphQL）
- [ ] 一键铺货 UI（选择设计+产品+平台，批量发布）

### Phase 4：Analytics（1周）⭐
- [ ] 销售数据聚合 API
- [ ] 爆款识别算法
- [ ] 报表页面（图表用 Chart.js）

### Phase 5：生产流程完善
- [ ] 分货界面（扫描枪兼容）
- [ ] 面单打印集成
- [ ] 发货确认 + 平台回传

---

## 五、关键决策记录

### 5.1 为什么不用现有 pod-platform 直接改？
- 现有代码模型混在一起（POD 模型和传统 WMS 模型都在 `pod.py`）
- 需要清晰的模块边界，方便后续维护和扩展
- 新框架命名为 **RiiChain**，标识清晰

### 5.2 为什么先对接 TikTok Shop 和 Shopify？
- TikTok Shop API 相对友好，中文文档齐全
- Shopify 是跨境电商最成熟的平台，API 最稳定
- 两个平台覆盖了「兴趣电商」和「独立站」两个核心场景

### 5.3 排版引擎为什么用 pyckingsolver？
- 专业级嵌套算法，比简单贪心算法利用率高 15-25%
- 你的现有代码已经用得很好，直接保留

---

## 六、下一步行动

1. **确认方案**：你看完这个文档，告诉我哪些地方要调整
2. **搭建骨架**：我帮你把 riichain 新项目目录 + 数据库模型建好
3. **逐个模块实现**：按 Phase 1→2→3→4 的顺序推进

---

*本方案由 WorkBuddy AI 协助整理，基于 Austin Zheng 的 pod-platform 现有代码和 RiiChain 业务需求设计。*
