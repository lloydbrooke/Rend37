import math

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import auth_utils
from database import get_db

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def map_page(request: Request, user=Depends(auth_utils.get_current_user)):
    templates = request.app.state.templates
    return templates.TemplateResponse("map.html", {"request": request, "user": user})


@router.get("/pins")
async def map_pins(
    db: AsyncSession = Depends(get_db),
    lat: float = Query(...),
    long: float = Query(...),
    radius_km: float = Query(50),
    category: str | None = Query(None),
):
    """return event pins as json for the map frontend"""
    result = await db.execute(select(models.Event))
    all_events = result.scalars().all()

    pins = []
    for event in all_events:
        dist = _haversine(lat, long, event.latitude, event.longitude)
        if dist > radius_km:
            continue
        if category and event.category != category:
            continue
        pins.append({
            "id": event.id,
            "title": event.title,
            "lat": event.latitude,
            "long": event.longitude,
            "category": event.category,
            "location_name": event.location_name,
        })

    return JSONResponse(content=pins)


@router.get("/event-popup/{event_id}", response_class=HTMLResponse)
async def event_popup(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    templates = request.app.state.templates
    return templates.TemplateResponse("event_popup.html", {
        "request": request,
        "event": event,
    })


def _haversine(lat1, lon1, lat2, lon2):
    """quick haversine calc for distance in km"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
