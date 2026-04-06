from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from haversine import haversine

from models import Event
from auth_utils import get_current_user
from database import get_db

router = APIRouter(tags=["map"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def map_page(
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event.category).distinct())
    categories = sorted([row[0] for row in result.all()])
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "user": user,
            "categories": categories,
        },
    )


@router.get("/pins")
async def get_map_pins(
    lat: float = Query(53.4084, ge=-90, le=90),
    long: float = Query(-2.9916, ge=-180, le=180),
    radius_km: float = Query(50, gt=0),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Event)
    if category:
        stmt = stmt.where(Event.category == category)
    result = await db.execute(stmt)
    all_events = result.scalars().all()

    pins = []
    for event in all_events:
        distance = haversine(
            (lat, long),
            (event.latitude, event.longitude),
        )
        if distance <= radius_km:
            pins.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "category": event.category,
                    "location_name": event.location_name,
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "date_time": event.date_time.strftime("%b %d, %Y at %H:%M"),
                    "distance_km": round(distance, 2),
                }
            )

    pins.sort(key=lambda p: p["distance_km"])
    return pins
