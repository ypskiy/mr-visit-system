"""
Shared pytest fixtures for the MR Visit Management System test suite.

Test Strategy:
  - Unit tests : pure Python functions, no DB (compliance_service, gps_utils)
  - Integration: in-process FastAPI via httpx.AsyncClient + real async SQLite
                 (SQLite is chosen for portability so tests run without Postgres)
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ── Override DB before importing app ─────────────────────────────────────────
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("DEFAULT_MR_ID", "00000000-0000-0000-0000-000000000001")

from app.main import app
from app.database import get_db
from app.models import Base, MR, Department, Doctor, Product, VisitStatus

# ── In-memory SQLite engine for tests ────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Per-test DB session, rolled back after each test."""
    async with session_factory() as session:
        yield session
        await session.rollback()


# ── Seed helpers ─────────────────────────────────────────────────────────────
FIXED_MR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def mr(db: AsyncSession) -> MR:
    obj = MR(
        id=FIXED_MR_ID,
        name="李明",
        employee_id="MR001",
        phone="13800000001",
        region="华东区",
    )
    obj = await db.merge(obj)
    await db.commit()
    return obj


@pytest_asyncio.fixture
async def department(db: AsyncSession) -> Department:
    obj = Department(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="心内科",
        hospital_name="测试医院",
        hospital_lat=31.2154,
        hospital_lng=121.4619,
    )
    obj = await db.merge(obj)
    await db.commit()
    return obj


@pytest_asyncio.fixture
async def doctor(db: AsyncSession, department: Department) -> Doctor:
    obj = Doctor(
        id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        name="张医生",
        title="主任医师",
        specialty="冠心病",
        department_id=department.id,
    )
    obj = await db.merge(obj)
    await db.commit()
    return obj


@pytest_asyncio.fixture
async def product(db: AsyncSession) -> Product:
    obj = Product(
        id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        name="立普妥",
        generic_name="阿托伐他汀钙片",
        therapeutic_area="心血管",
    )
    obj = await db.merge(obj)
    await db.commit()
    return obj


# ── HTTP client ───────────────────────────────────────────────────────────────
MR_HEADERS = {"X-MR-ID": str(FIXED_MR_ID)}


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    """AsyncClient with DB dependency override."""
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=MR_HEADERS,
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Date helpers ──────────────────────────────────────────────────────────────
def next_monday_noon() -> datetime:
    """Returns next Monday at 12:00 UTC — guaranteed to be in the next week."""
    now = datetime.now(timezone.utc)
    days_ahead = 7 - now.weekday()  # weekday(): 0=Mon
    d = now + timedelta(days=days_ahead)
    return d.replace(hour=12, minute=0, second=0, microsecond=0)
