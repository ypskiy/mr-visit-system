from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Department

router = APIRouter(prefix="/api/v1/departments", tags=["departments"])


@router.get("")
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).order_by(Department.hospital_name, Department.name))
    depts = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "hospital_name": d.hospital_name,
            "hospital_lat": float(d.hospital_lat),
            "hospital_lng": float(d.hospital_lng),
        }
        for d in depts
    ]
