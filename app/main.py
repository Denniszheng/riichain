"""RiiChain v2.0 — POD 专用全链路系统 FastAPI 入口"""
import os
import importlib
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="POD (Print on Demand) full-chain system",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
jinja_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))

def render_template(name: str, request: Request, **kwargs):
    """Render a Jinja2 template with request in context."""
    template = jinja_env.get_template(name)
    return HTMLResponse(template.render(request=request, **kwargs))

UPLOAD_DIR = BASE_DIR / "static" / "uploads"
OUTPUT_DIR = BASE_DIR / "static" / "outputs" / "layouts"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ── API Routers ─────────────────────────────────────────────────
router_registry = [
    ("app.api.v1.designs",    "/api/v1/designs",    "Design Hub"),
    ("app.api.v1.products",   "/api/v1/products",   "Blank Products"),
    ("app.api.v1.orders",     "/api/v1/orders",     "Orders"),
    ("app.api.v1.listing",    "/api/v1/listing",    "Listing Engine"),
    ("app.api.v1.layout",     "/api/v1/layout",     "Layout Engine"),
    ("app.api.v1.wave",       "/api/v1/wave",       "Wave & Fulfillment"),
    ("app.api.v1.analytics",  "/api/v1/analytics",  "Analytics"),
    ("app.api.v1.platforms",  "/api/v1/platforms",  "Platform Accounts"),
]

for module_path, prefix, label in router_registry:
    try:
        mod = importlib.import_module(module_path)
        router = getattr(mod, "router", None)
        if router:
            app.include_router(router, prefix=prefix, tags=[label])
    except ModuleNotFoundError:
        print(f"   [WARN] Route module not found: {module_path}")
    except Exception as e:
        print(f"   [WARN] Route registration failed {module_path}: {e}")


# ── Page Routes ─────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    return render_template("index.html", request)

@app.get("/designs", response_class=HTMLResponse)
async def page_designs(request: Request):
    return render_template("designs.html", request)

@app.get("/products", response_class=HTMLResponse)
async def page_products(request: Request):
    return render_template("products.html", request)

@app.get("/listing", response_class=HTMLResponse)
async def page_listing(request: Request):
    return render_template("listing.html", request)

@app.get("/orders", response_class=HTMLResponse)
async def page_orders(request: Request):
    return render_template("orders.html", request)

@app.get("/layout", response_class=HTMLResponse)
async def page_layout(request: Request):
    return render_template("layout.html", request)

@app.get("/wave", response_class=HTMLResponse)
async def page_wave(request: Request):
    return render_template("wave.html", request)

@app.get("/analytics", response_class=HTMLResponse)
async def page_analytics(request: Request):
    return render_template("analytics.html", request)


# ── Health Check ─────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


print(f"\n{'='*50}")
print(f"  RiiChain v{settings.APP_VERSION}")
print(f"  http://localhost:8000")
print(f"  API docs: http://localhost:8000/api/docs")
print(f"{'='*50}\n")
