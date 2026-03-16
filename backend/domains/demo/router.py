"""Demo data router — seed and clear demo data for demonstrations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from middleware.auth import require_role

from .seed import clear_demo_data, is_demo_seeded, seed_demo_data


def _require_dev_mode() -> None:
    from config import get_settings

    if not get_settings().is_development:
        raise HTTPException(status_code=404, detail="Not available in production")


router = APIRouter(dependencies=[Depends(_require_dev_mode)])


@router.get("/status")
async def demo_status(
    _user: object = Depends(require_role(UserRole.admin)),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, bool]:
    """Check whether demo data is currently seeded."""
    seeded = await is_demo_seeded(db)
    return {"seeded": seeded}


@router.post("/seed")
async def seed_demo(
    _user: object = Depends(require_role(UserRole.admin)),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str | dict[str, int]]:
    """Seed the database with realistic demo data (admin only, idempotent)."""
    counts = await seed_demo_data(db)
    return {"status": "ok", "counts": counts}


@router.delete("/seed")
async def clear_demo(
    _user: object = Depends(require_role(UserRole.admin)),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Remove all demo data (admin only)."""
    await clear_demo_data(db)
    return {"status": "cleared"}
