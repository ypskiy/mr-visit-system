from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("")
async def list_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product).where(Product.is_active == True).order_by(Product.name)
    )
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "generic_name": p.generic_name,
            "therapeutic_area": p.therapeutic_area,
        }
        for p in products
    ]
