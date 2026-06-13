import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Doctor, Department

router = APIRouter(prefix="/api/v1/doctors", tags=["doctors"])


@router.get("")
async def list_doctors(
    department_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Doctor).options(selectinload(Doctor.department))
    if department_id:
        q = q.where(Doctor.department_id == department_id)
    q = q.order_by(Doctor.name)
    result = await db.execute(q)
    doctors = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "title": d.title,
            "specialty": d.specialty,
            "department_id": d.department_id,
            "department_name": d.department.name if d.department else None,
            "hospital_name": d.department.hospital_name if d.department else None,
        }
        for d in doctors
    ]
