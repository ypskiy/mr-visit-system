"""
Visit service: business logic for CRUD and state transitions.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Visit, VisitStatus, Doctor, Department, Product, VisitReport, ComplianceCheck, ComplianceResult
from app.schemas import VisitCreate, VisitUpdate, CheckinRequest, ReportRequest
from app.services.compliance_service import run_compliance_check


# ── Date validation helpers ───────────────────────────────────────────────────

def _get_next_week_range() -> tuple[datetime, datetime]:
    """Return (monday_start, sunday_end) for next calendar week (local UTC)."""
    now = datetime.now(timezone.utc)
    today = now.date()
    # Current week Monday
    current_monday = today - timedelta(days=today.weekday())
    next_monday = current_monday + timedelta(weeks=1)
    next_sunday = next_monday + timedelta(days=6)
    start = datetime(next_monday.year, next_monday.month, next_monday.day,
                     0, 0, 0, tzinfo=timezone.utc)
    end = datetime(next_sunday.year, next_sunday.month, next_sunday.day,
                   23, 59, 59, tzinfo=timezone.utc)
    return start, end


def validate_planned_date(planned_date: datetime) -> None:
    start, end = _get_next_week_range()
    # Make aware if naive
    if planned_date.tzinfo is None:
        planned_date = planned_date.replace(tzinfo=timezone.utc)
    if not (start <= planned_date <= end):
        raise ValueError(
            f"预约日期必须在下一自然周范围内（{start.date()} ~ {end.date()}）"
        )


# ── Query helpers ─────────────────────────────────────────────────────────────

def _visit_query(mr_id: uuid.UUID):
    return (
        select(Visit)
        .where(Visit.mr_id == mr_id)
        .options(
            selectinload(Visit.doctor).selectinload(Doctor.department),
            selectinload(Visit.product),
            selectinload(Visit.report),
            selectinload(Visit.compliance),
        )
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_visits(
    db: AsyncSession,
    mr_id: uuid.UUID,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[int, list[Visit]]:
    q = _visit_query(mr_id)
    if status:
        try:
            status_enum = VisitStatus(status)
            q = q.where(Visit.status == status_enum)
        except ValueError:
            return 0, []
    if from_date:
        q = q.where(Visit.planned_date >= from_date)
    if to_date:
        q = q.where(Visit.planned_date <= to_date)

    # Count
    count_q = select(sqlfunc.count()).select_from(Visit).where(Visit.mr_id == mr_id)
    if status:
        try:
            count_q = count_q.where(Visit.status == VisitStatus(status))
        except ValueError:
            pass
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Visit.planned_date.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    return total, list(result.scalars().all())


async def get_visit(db: AsyncSession, visit_id: uuid.UUID, mr_id: uuid.UUID) -> Optional[Visit]:
    q = _visit_query(mr_id).where(Visit.id == visit_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def create_visit(db: AsyncSession, mr_id: uuid.UUID, data: VisitCreate) -> Visit:
    validate_planned_date(data.planned_date)

    # Verify doctor and product exist
    doctor = await db.get(Doctor, data.doctor_id)
    if not doctor:
        raise ValueError("医生不存在")
    product = await db.get(Product, data.product_id)
    if not product:
        raise ValueError("产品不存在")

    visit = Visit(
        mr_id=mr_id,
        doctor_id=data.doctor_id,
        product_id=data.product_id,
        planned_date=data.planned_date,
        status=VisitStatus.PLANNED,
    )
    db.add(visit)
    await db.commit()
    # Expire to force reload with relationships
    db.expunge(visit)
    return await get_visit(db, visit.id, mr_id)


async def update_visit(db: AsyncSession, visit: Visit, data: VisitUpdate) -> Visit:
    if visit.status != VisitStatus.PLANNED:
        raise ValueError("只有「计划中」状态的拜访可以修改")
    if data.planned_date:
        validate_planned_date(data.planned_date)
        visit.planned_date = data.planned_date
    if data.doctor_id:
        doctor = await db.get(Doctor, data.doctor_id)
        if not doctor:
            raise ValueError("医生不存在")
        visit.doctor_id = data.doctor_id
    if data.product_id:
        product = await db.get(Product, data.product_id)
        if not product:
            raise ValueError("产品不存在")
        visit.product_id = data.product_id
    await db.commit()
    db.expunge(visit)
    return await get_visit(db, visit.id, visit.mr_id)


async def delete_visit(db: AsyncSession, visit: Visit) -> None:
    if visit.status != VisitStatus.PLANNED:
        raise ValueError("只有「计划中」状态的拜访可以删除")
    await db.delete(visit)
    await db.commit()


# ── State transitions ─────────────────────────────────────────────────────────

async def checkin_visit(db: AsyncSession, visit: Visit, req: CheckinRequest) -> Visit:
    if visit.status != VisitStatus.PLANNED:
        raise ValueError(f"当前状态「{visit.status.value}」无法执行签到（需为 PLANNED）")
    visit.status = VisitStatus.CHECKED_IN
    visit.checkin_time = datetime.now(timezone.utc)
    visit.checkin_lat = req.latitude
    visit.checkin_lng = req.longitude
    await db.commit()
    db.expunge(visit)
    return await get_visit(db, visit.id, visit.mr_id)


async def checkout_visit(db: AsyncSession, visit: Visit) -> Visit:
    if visit.status != VisitStatus.CHECKED_IN:
        raise ValueError(f"当前状态「{visit.status.value}」无法执行签退（需为 CHECKED_IN）")
    now = datetime.now(timezone.utc)
    visit.checkout_time = now
    checkin = visit.checkin_time
    if checkin.tzinfo is None:
        checkin = checkin.replace(tzinfo=timezone.utc)
    delta = now - checkin
    visit.duration_minutes = max(0, int(delta.total_seconds() / 60))
    visit.status = VisitStatus.CHECKED_OUT
    await db.commit()
    db.expunge(visit)
    return await get_visit(db, visit.id, visit.mr_id)


async def submit_report(db: AsyncSession, visit: Visit, req: ReportRequest) -> Visit:
    if visit.status != VisitStatus.CHECKED_OUT:
        raise ValueError(f"当前状态「{visit.status.value}」无法提交报告（需为 CHECKED_OUT）")

    # Create report
    report = VisitReport(
        visit_id=visit.id,
        talking_points=req.talking_points,
        doctor_feedback=req.doctor_feedback,
        materials_distributed=req.materials_distributed,
        material_type=req.material_type,
    )
    db.add(report)
    visit.report = report

    # Mark completed
    visit.status = VisitStatus.COMPLETED
    await db.flush()

    # Run compliance check
    dept = visit.doctor.department
    checkin_time = visit.checkin_time
    if checkin_time.tzinfo is None:
        checkin_time = checkin_time.replace(tzinfo=timezone.utc)

    compliance_data = run_compliance_check(
        checkin_time=checkin_time,
        checkin_lat=float(visit.checkin_lat),
        checkin_lng=float(visit.checkin_lng),
        checkout_time=visit.checkout_time,
        duration_minutes=visit.duration_minutes,
        hospital_lat=float(dept.hospital_lat),
        hospital_lng=float(dept.hospital_lng),
        talking_points=req.talking_points,
        doctor_feedback=req.doctor_feedback,
        materials_distributed=req.materials_distributed,
        material_type=req.material_type,
    )

    check = ComplianceCheck(
        visit_id=visit.id,
        result=ComplianceResult(compliance_data["result"]),
        score=compliance_data["score"],
        violations=compliance_data["violations"],
        rule_details=compliance_data["rule_details"],
    )
    db.add(check)
    visit.compliance = check
    await db.commit()
    db.expunge(visit)
    return await get_visit(db, visit.id, visit.mr_id)
