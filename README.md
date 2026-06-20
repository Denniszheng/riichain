# RiiChain v2.0 — POD 专用全链路系统

欢迎使用 RiiChain！

## 快速开始

```bash
pip install -r requirements.txt
python -m app.main
```

访问：
- 前端：http://localhost:8000/
- API 文档：http://localhost:8000/api/docs

## 项目结构

```
riichain/
├── app/
│   ├── main.py               # FastAPI 入口
│   ├── config.py             # 配置
│   ├── database.py           # 数据库
│   ├── models/              # 数据模型（13个模型）
│   ├── api/v1/              # API 路由（按模块）
│   ├── services/            # 业务逻辑层
│   ├── templates/           # Jinja2 模板
│   └── static/              # 静态资源
├── requirements.txt
└── .env
```

## 核心模块

| 模块 | 说明 |
|------|------|
| Design Hub | 设计管理、Mockup 生成 |
| Listing Engine | 一键铺货到 TikTok/Shopify |
| Order Router | 订单路由（四维度评分） |
| Layout Engine | 一键排版（pyckingsolver） |
| Wave & Fulfillment | 波次履约（一板=一Wave） |
| Analytics | 销售分析、爆款识别 |

## 配置

复制 `.env.example` 为 `.env`，按需修改配置。

```bash
cp .env.example .env
```

## 数据库

首次启动自动创建 SQLite 数据库和表。

```
riichain.db   # 开发环境数据库
```
