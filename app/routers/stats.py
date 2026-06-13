import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func as sqlfunc, extract, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Visit, VisitStatus, Product, ComplianceCheck, Doctor, Department

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _get_mr_id(request: Request) -> uuid.UUID:
    from app.config import settings
    mr_id_str = request.headers.get("X-MR-ID", settings.default_mr_id)
    return uuid.UUID(mr_id_str)


@router.get("/product-visits")
async def product_visit_stats(
    request: Request,
    year: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    if not year:
        year = datetime.now(timezone.utc).year

    # Get all products
    products_result = await db.execute(
        select(Product).where(Product.is_active == True).order_by(Product.name)
    )
    products = products_result.scalars().all()

    data = []
    for product in products:
        # Query monthly visit counts for this product/MR/year
        monthly_q = (
            select(
                extract("month", Visit.planned_date).label("month"),
                sqlfunc.count(Visit.id).label("visit_count"),
                sqlfunc.count(
                    case((Visit.status == VisitStatus.COMPLETED, Visit.id))
                ).label("completed_count"),
            )
            .where(
                Visit.mr_id == mr_id,
                Visit.product_id == product.id,
                extract("year", Visit.planned_date) == year,
            )
            .group_by(extract("month", Visit.planned_date))
            .order_by(extract("month", Visit.planned_date))
        )
        monthly_result = await db.execute(monthly_q)
        monthly_rows = monthly_result.fetchall()

        # Build month dict
        month_map = {int(r.month): {"visit_count": r.visit_count, "completed_count": r.completed_count}
                     for r in monthly_rows}

        # Compliance counts per month
        comp_q = (
            select(
                extract("month", Visit.planned_date).label("month"),
                sqlfunc.count(ComplianceCheck.id).label("compliant_count"),
            )
            .join(ComplianceCheck, ComplianceCheck.visit_id == Visit.id)
            .where(
                Visit.mr_id == mr_id,
                Visit.product_id == product.id,
                extract("year", Visit.planned_date) == year,
                ComplianceCheck.result == "COMPLIANT",
            )
            .group_by(extract("month", Visit.planned_date))
        )
        comp_result = await db.execute(comp_q)
        comp_map = {int(r.month): r.compliant_count for r in comp_result.fetchall()}

        monthly_counts = []
        for m in range(1, 13):
            mc = month_map.get(m, {"visit_count": 0, "completed_count": 0})
            monthly_counts.append({
                "month": m,
                "visit_count": mc["visit_count"],
                "completed_count": mc["completed_count"],
                "compliant_count": comp_map.get(m, 0),
            })

        total_visits = sum(mc["visit_count"] for mc in monthly_counts)
        total_completed = sum(mc["completed_count"] for mc in monthly_counts)
        total_compliant = sum(mc["compliant_count"] for mc in monthly_counts)
        compliance_rate = round(total_compliant / total_completed, 3) if total_completed > 0 else 0.0

        data.append({
            "product_id": product.id,
            "product_name": product.name,
            "therapeutic_area": product.therapeutic_area,
            "monthly_counts": monthly_counts,
            "total_visits": total_visits,
            "total_completed": total_completed,
            "compliance_rate": compliance_rate,
        })

    return {"year": year, "data": data}


@router.get("/compliance")
async def compliance_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    now = datetime.now(timezone.utc)

    # Build 4 recent weeks
    recent_weeks = []
    for i in range(3, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        week_start = week_start.replace(hour=0, minute=0, second=0)

        q = (
            select(
                sqlfunc.count(Visit.id).label("total"),
                sqlfunc.count(
                    case((ComplianceCheck.result == "COMPLIANT", Visit.id))
                ).label("compliant"),
                sqlfunc.count(
                    case((ComplianceCheck.result == "MINOR_VIOLATION", Visit.id))
                ).label("minor"),
                sqlfunc.count(
                    case((ComplianceCheck.result == "MAJOR_VIOLATION", Visit.id))
                ).label("major"),
            )
            .join(ComplianceCheck, ComplianceCheck.visit_id == Visit.id, isouter=True)
            .where(
                Visit.mr_id == mr_id,
                Visit.status == VisitStatus.COMPLETED,
                Visit.planned_date >= week_start,
                Visit.planned_date < week_end,
            )
        )
        row = (await db.execute(q)).fetchone()
        total = row.total or 0
        compliant = row.compliant or 0
        recent_weeks.append({
            "week_label": f"W{week_start.strftime('%m/%d')}",
            "total": total,
            "compliant": compliant,
            "minor": row.minor or 0,
            "major": row.major or 0,
            "compliance_rate": round(compliant / total, 3) if total > 0 else 0.0,
        })

    # Violations list (completed with violations)
    violations_q = (
        select(Visit)
        .join(ComplianceCheck, ComplianceCheck.visit_id == Visit.id)
        .where(
            Visit.mr_id == mr_id,
            Visit.status == VisitStatus.COMPLETED,
            ComplianceCheck.result != "COMPLIANT",
        )
        .options(
            selectinload(Visit.doctor).selectinload(Doctor.department),
            selectinload(Visit.product),
            selectinload(Visit.compliance),
        )
        .order_by(Visit.planned_date.desc())
        .limit(20)
    )
    violations_result = await db.execute(violations_q)
    violations_visits = violations_result.scalars().all()

    # Rule violation counts
    all_comp_q = (
        select(ComplianceCheck.violations)
        .join(Visit, Visit.id == ComplianceCheck.visit_id)
        .where(Visit.mr_id == mr_id)
    )
    all_comp = await db.execute(all_comp_q)
    rule_counts: dict = {}
    for (violations,) in all_comp.fetchall():
        if violations:
            for v in violations:
                rid = v.get("rule_id", "?")
                rname = v.get("rule_name", rid)
                key = f"{rid}: {rname}"
                rule_counts[key] = rule_counts.get(key, 0) + 1

    def visit_to_brief(v):
        doc = v.doctor
        dept = doc.department if doc else None
        prod = v.product
        comp = v.compliance
        return {
            "id": v.id,
            "status": v.status.value,
            "planned_date": v.planned_date,
            "checkin_time": v.checkin_time,
            "checkin_lat": v.checkin_lat,
            "checkin_lng": v.checkin_lng,
            "checkout_time": v.checkout_time,
            "duration_minutes": v.duration_minutes,
            "created_at": v.created_at,
            "updated_at": v.updated_at,
            "doctor": {
                "id": doc.id, "name": doc.name, "title": doc.title,
                "department_name": dept.name if dept else "",
                "hospital_name": dept.hospital_name if dept else "",
            } if doc else None,
            "product": {
                "id": prod.id, "name": prod.name, "generic_name": prod.generic_name,
                "therapeutic_area": prod.therapeutic_area,
            } if prod else None,
            "report": None,
            "compliance": {
                "result": comp.result.value, "score": comp.score,
                "violations": comp.violations or [],
            } if comp else None,
        }

    return {
        "recent_weeks": recent_weeks,
        "rule_violation_counts": rule_counts,
        "violations_list": [visit_to_brief(v) for v in violations_visits],
    }
