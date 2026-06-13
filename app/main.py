from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.config import settings
from app.routers import visits, doctors, departments, products, stats

app = FastAPI(
    title="MR 学术拜访管理系统",
    description="医药代表学术拜访全生命周期管理",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Register API routers
app.include_router(visits.router)
app.include_router(doctors.router)
app.include_router(departments.router)
app.include_router(products.router)
app.include_router(stats.router)


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_list(request: Request):
    return templates.TemplateResponse("visits/list.html", {
        "request": request,
        "page_title": "拜访列表",
        "active_nav": "visits",
        "mr_id": settings.default_mr_id,
    })


@app.get("/visits/new", response_class=HTMLResponse)
async def page_new_visit(request: Request):
    return templates.TemplateResponse("visits/new.html", {
        "request": request,
        "page_title": "新建拜访预约",
        "active_nav": "visits",
        "mr_id": settings.default_mr_id,
    })


@app.get("/visits/{visit_id}", response_class=HTMLResponse)
async def page_visit_detail(request: Request, visit_id: uuid.UUID):
    return templates.TemplateResponse("visits/detail.html", {
        "request": request,
        "page_title": "拜访详情",
        "active_nav": "visits",
        "visit_id": str(visit_id),
        "mr_id": settings.default_mr_id,
    })


@app.get("/compliance", response_class=HTMLResponse)
async def page_compliance(request: Request):
    return templates.TemplateResponse("compliance/overview.html", {
        "request": request,
        "page_title": "合规概览",
        "active_nav": "compliance",
        "mr_id": settings.default_mr_id,
    })


@app.get("/dashboard/products", response_class=HTMLResponse)
async def page_product_dashboard(request: Request):
    return templates.TemplateResponse("dashboard/products.html", {
        "request": request,
        "page_title": "产品拜访看板",
        "active_nav": "dashboard",
        "mr_id": settings.default_mr_id,
        "current_year": datetime.now(timezone.utc).year,
    })
