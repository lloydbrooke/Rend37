import math
from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
import auth_utils
from database import get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_events(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await auth_utils.get_current_user(request, db)
    result = await db.execute(select(models.Event))
    events = result.scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse("events.html", {
        "request": request,
        "user": user,
        "events": events,
    })


@router.get("/create", response_class=HTMLResponse)
async def create_event_form(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    # grab communities for the dropdown
    result = await db.execute(select(models.Community))
    communities = result.scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse("event_create.html", {
        "request": request,
        "user": current_user,
        "communities": communities,
    })


@router.post("/create")
async def create_event(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(...),
    date_time: str = Form(...),
    community_id: int = Form(...),
    capacity_limit: int | None = Form(None),
):
    from datetime import datetime
    # parse the date string from the form
    dt = datetime.fromisoformat(date_time)

    event = models.Event(
        title=title, description=description, category=category,
        latitude=latitude, longitude=longitude, location_name=location_name,
        date_time=dt, capacity_limit=capacity_limit,
        community_id=community_id, organizer_id=current_user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


# nearby search — needs to come before /{event_id} so it doesn't get caught by the path param
@router.get("/nearby")
async def nearby_events(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: float = Query(...),
    long: float = Query(...),
    radius_km: float = Query(10),
):
    result = await db.execute(select(models.Event))
    all_events = result.scalars().all()

    # filter by haversine distance
    nearby = []
    for event in all_events:
        dist = _haversine(lat, long, event.latitude, event.longitude)
        if dist <= radius_km:
            nearby.append(event)

    templates = request.app.state.templates
    return templates.TemplateResponse("events.html", {
        "request": request,
        "user": None,
        "events": nearby,
    })


@router.get("/{event_id}", response_class=HTMLResponse)
async def view_event(
    event_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await auth_utils.get_current_user(request, db)
    result = await db.execute(
        select(models.Event)
        .options(selectinload(models.Event.organizer))
        .where(models.Event.id == event_id)
    )
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    templates = request.app.state.templates
    return templates.TemplateResponse("event_detail.html", {
        "request": request,
        "user": user,
        "event": event,
    })


@router.get("/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(
    event_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can edit this event.")
    templates = request.app.state.templates
    return templates.TemplateResponse("event_edit.html", {
        "request": request,
        "user": current_user,
        "event": event,
    })


@router.post("/{event_id}/edit")
async def edit_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(...),
    date_time: str = Form(...),
    capacity_limit: int | None = Form(None),
):
    from datetime import datetime
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can edit this event.")

    event.title = title
    event.description = description
    event.category = category
    event.latitude = latitude
    event.longitude = longitude
    event.location_name = location_name
    event.date_time = datetime.fromisoformat(date_time)
    event.capacity_limit = capacity_limit
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can delete this event.")
    await db.delete(event)
    await db.commit()
    return RedirectResponse(url="/events", status_code=303)


''' registration routes '''

@router.post("/{event_id}/register")
async def register_for_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # check if already registered
    existing = await db.execute(
        select(models.Registration).where(
            models.Registration.user_id == current_user.id,
            models.Registration.event_id == event_id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Already registered for this event.")

    # check capacity if there's a limit
    if event.capacity_limit:
        count_result = await db.execute(
            select(func.count()).select_from(models.Registration).where(
                models.Registration.event_id == event_id
            )
        )
        count = count_result.scalar()
        if count >= event.capacity_limit:
            raise HTTPException(status_code=409, detail="Event is full.")

    reg = models.Registration(user_id=current_user.id, event_id=event_id, status="registered")
    db.add(reg)
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=302)


@router.post("/{event_id}/unregister")
async def unregister_from_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(
        select(models.Registration).where(
            models.Registration.user_id == current_user.id,
            models.Registration.event_id == event_id,
        )
    )
    reg = result.scalars().first()
    if not reg:
        raise HTTPException(status_code=404, detail="Not registered for this event.")
    await db.delete(reg)
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}", status_code=302)


@router.get("/{event_id}/attendees", response_class=HTMLResponse)
async def attendees_list(
    event_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.Registration)
        .options(selectinload(models.Registration.user))
        .where(models.Registration.event_id == event_id)
    )
    registrations = result.scalars().all()
    attendees = [r.user for r in registrations]
    templates = request.app.state.templates
    return templates.TemplateResponse("attendees.html", {
        "request": request,
        "attendees": attendees,
        "event_id": event_id,
    })


def _haversine(lat1, lon1, lat2, lon2):
    """quick haversine calc to get distance in km between two points"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
