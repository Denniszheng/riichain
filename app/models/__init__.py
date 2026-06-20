"""RiiChain 数据模型统一导出"""
from app.models.base import Base, UUIDMixin, TimestampMixin

from app.models.tenant import Tenant
from app.models.design import Design, DesignVariant
from app.models.blank_product import BlankProduct, ProductVariant
from app.models.order import Order, OrderItem, OrderRouting
from app.models.print_job import PrintJob
from app.models.wave import WaveImport, WaveOrder, MaterialInventory, StockTransaction
from app.models.shipping import ShippingLabel
from app.models.facility import Facility, FacilityCapacity
from app.models.platform_account import PlatformAccount
from app.models.listing_job import ListingJob
from app.models.analytics import SalesRecord, HitProduct, DesignAnalytics

__all__ = [
    # Base
    "Base", "UUIDMixin", "TimestampMixin",
    # Design
    "Design", "DesignVariant",
    # Blank Product
    "BlankProduct", "ProductVariant",
    # Order
    "Order", "OrderItem", "OrderRouting",
    # Print Job
    "PrintJob",
    # Wave / Material
    "WaveImport", "WaveOrder", "MaterialInventory", "StockTransaction",
    # Shipping
    "ShippingLabel",
    # Facility
    "Facility", "FacilityCapacity",
    # Platform
    "PlatformAccount",
    # Listing
    "ListingJob",
    # Analytics
    "SalesRecord", "HitProduct", "DesignAnalytics",
]


def init_db():
    """初始化数据库，创建所有表，并写入默认数据"""
    from app.core.database import engine
    Base.metadata.create_all(bind=engine)
    _seed_default_data()


def _seed_default_data():
    """写入默认数据（默认租户、示例基底产品等）"""
    from sqlalchemy.orm import sessionmaker
    from app.core.database import engine
    from datetime import datetime

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        # 创建默认租户（若表存在且有 Tenant 模型）
        try:
            from app.models.tenant import Tenant
            existing = db.query(Tenant).filter_by(slug="default").first()
            if not existing:
                tenant = Tenant(
                    id="default-tenant-id",
                    name="Default Tenant",
                    slug="default",
                )
                db.add(tenant)
                db.commit()
        except Exception:
            pass

        # 创建示例基底产品（T恤）
        from app.models.blank_product import BlankProduct
        existing = db.query(BlankProduct).first()
        if not existing:
            bp = BlankProduct(
                tenant_id="default",
                name="男士经典圆领T恤",
                category="T恤",
                supplier="示例供应商",
                print_area_w=300,
                print_area_h=400,
                design_template_w=3000,
                design_template_h=4000,
                blank_w=600,
                blank_h=800,
                material="纯棉",
                cost_usd=3.5,
                base_price_usd=19.99,
                print_methods=["DTG"],
                is_active=True,
            )
            db.add(bp)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed data warning: {e}")
    finally:
        db.close()
