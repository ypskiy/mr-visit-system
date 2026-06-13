import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import VisitCreate, VisitUpdate, CheckinRequest, ReportRequest, VisitOut, PaginatedVisits
from app.services import visit_service
from app.models import VisitStatus

router = APIRouter(prefix="/api/v1/visits", tags=["visits"])


def _get_mr_id(request: Request) -> uuid.UUID:
    """Extract MR ID from header (demo mode: falls back to default)."""
    from app.config import settings
    mr_id_str = request.headers.get("X-MR-ID", settings.default_mr_id)
    try:
        return uuid.UUID(mr_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 MR ID")


def _visit_or_404(visit):
    if visit is None:
        raise HTTPException(status_code=404, detail={"code": "VISIT_NOT_FOUND", "message": "拜访记录不存在"})
    return visit


def _state_error(msg: str):
    raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": msg})


def _visit_to_out(visit) -> dict:
    """Convert ORM visit to response dict."""
    doc = visit.doctor
    dept = doc.department if doc else None
    prod = visit.product
    rep = visit.report
    comp = visit.compliance

    return {
        "id": visit.id,
        "status": visit.status.value,
        "planned_date": visit.planned_date,
        "checkin_time": visit.checkin_time,
        "checkin_lat": visit.checkin_lat,
        "checkin_lng": visit.checkin_lng,
        "checkout_time": visit.checkout_time,
        "duration_minutes": visit.duration_minutes,
        "created_at": visit.created_at,
        "updated_at": visit.updated_at,
        "doctor": {
            "id": doc.id,
            "name": doc.name,
            "title": doc.title,
            "department_name": dept.name if dept else "",
            "hospital_name": dept.hospital_name if dept else "",
        } if doc else None,
        "product": {
            "id": prod.id,
            "name": prod.name,
            "generic_name": prod.generic_name,
            "therapeutic_area": prod.therapeutic_area,
        } if prod else None,
        "report": {
            "talking_points": rep.talking_points,
            "doctor_feedback": rep.doctor_feedback,
            "materials_distributed": rep.materials_distributed,
            "material_type": rep.material_type,
            "submitted_at": rep.submitted_at,
        } if rep else None,
        "compliance": {
            "result": comp.result.value,
            "score": comp.score,
            "violations": comp.violations or [],
        } if comp else None,
    }


# ── List & Create ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedVisits)
async def list_visits(
    request: Request,
    status: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    total, visits = await visit_service.list_visits(db, mr_id, status, from_date, to_date, page, limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [_visit_to_out(v) for v in visits],
    }


@router.post("", status_code=201)
async def create_visit(
    request: Request,
    data: VisitCreate,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    try:
        visit = await visit_service.create_visit(db, mr_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(e)})
    return _visit_to_out(visit)


# ── Single visit ──────────────────────────────────────────────────────────────

@router.get("/{visit_id}")
async def get_visit(visit_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    return _visit_to_out(visit)


@router.put("/{visit_id}")
async def update_visit(
    visit_id: uuid.UUID,
    data: VisitUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    try:
        visit = await visit_service.update_visit(db, visit, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": str(e)})
    return _visit_to_out(visit)


@router.delete("/{visit_id}", status_code=204)
async def delete_visit(visit_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    try:
        await visit_service.delete_visit(db, visit)
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": str(e)})


# ── State transitions ─────────────────────────────────────────────────────────

@router.post("/{visit_id}/checkin")
async def checkin(
    visit_id: uuid.UUID,
    req: CheckinRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    try:
        visit = await visit_service.checkin_visit(db, visit, req)
    except ValueError as e:
        _state_error(str(e))
    return _visit_to_out(visit)


@router.post("/{visit_id}/checkout")
async def checkout(
    visit_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    try:
        visit = await visit_service.checkout_visit(db, visit)
    except ValueError as e:
        _state_error(str(e))
    return _visit_to_out(visit)


@router.post("/{visit_id}/report")
async def submit_report(
    visit_id: uuid.UUID,
    req: ReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    try:
        visit = await visit_service.submit_report(db, visit, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(e)})
    return _visit_to_out(visit)


@router.get("/{visit_id}/compliance")
async def get_compliance(visit_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    mr_id = _get_mr_id(request)
    visit = _visit_or_404(await visit_service.get_visit(db, visit_id, mr_id))
    if visit.status.value != "COMPLETED":
        raise HTTPException(status_code=409, detail={"code": "NOT_COMPLETED", "message": "拜访尚未完成"})
    if not visit.compliance:
        raise HTTPException(status_code=404, detail={"code": "COMPLIANCE_NOT_FOUND", "message": "合规校验记录不存在"})
    c = visit.compliance
    return {
        "result": c.result.value,
        "score": c.score,
        "violations": c.violations or [],
        "rule_details": c.rule_details or [],
        "checked_at": c.checked_at,
    }
