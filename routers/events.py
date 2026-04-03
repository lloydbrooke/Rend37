from models import Event, Registration, User, Community, CommunityMember
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from models import Event, Registration, User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from typing import Annotated
from schemas import EventCreateForm
from auth_utils import get_current_user, require_current_user
from datetime import datetime
from haversine import haversine





router = APIRouter(prefix="/events", tags=["Events"])
templates = Jinja2Templates(directory="templates")


# Creating events/forms
# Passed test 
@router.get("/create")
async def create_event_form(
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch communities the user is a member of
    result = await db.execute(
        select(Community)
        .join(CommunityMember, Community.id == CommunityMember.community_id)
        .filter(CommunityMember.user_id == user.id)
    )
    communities = result.scalars().all()

    if not communities:
        raise HTTPException(
            status_code=403,
            detail="You must be a member of a community to create an event"
        )

    return templates.TemplateResponse("create_event.html", {
        "request": request,
        "communities": communities
    })


@router.post("/create")
async def create_event(
    event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user is actually a member of the submitted community
    result = await db.execute(
        select(CommunityMember).filter(
            CommunityMember.user_id == user.id,
            CommunityMember.community_id == event.community_id
        )
    )
    # Validation
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="You are not a member of this community")
    if event.capacity_limit is None:
        raise HTTPException(status_code=400, detail="Must have a capacity limit")
    if event.capacity_limit <= 0:
        raise HTTPException(status_code=400, detail="Invalid capacity limit")
    if event.date_time <= datetime.now():
        raise HTTPException(status_code=400, detail="Date must be in the future")
    if not -90 <= event.latitude <= 90:
        raise HTTPException(status_code=400, detail="Invalid latitude")
    if not -180 <= event.longitude <= 180:
        raise HTTPException(status_code=400, detail="Invalid longitude")

    new_event = Event(
        title=event.title,
        description=event.description,
        category=event.category,
        latitude=event.latitude,
        longitude=event.longitude,
        location_name=event.location_name,
        date_time=event.date_time,
        capacity_limit=event.capacity_limit,
        community_id=event.community_id,
        organizer_id=user.id
    )

    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)

    return RedirectResponse(url="/events", status_code=303)


# Proximity search
# Passed Tests
@router.get("/nearby")
async def get_nearby_events(
    lat: float = Query(..., ge=-90, le=90),
    long: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event))
    events = result.scalars().all()

    nearby_events = []

    for event in events:
        distance = haversine(
            (lat, long),
            (event.latitude, event.longitude)
        )

        if distance <= radius_km:
            nearby_events.append({
                "id": event.id,
                "title": event.title,
                "distance_km": round(distance, 2)
            })

    nearby_events.sort(key=lambda x: x["distance_km"])

    return nearby_events





# Returning events
# Passed Tests
# when clicking on an event in /event it redirects to /event/{event_id}
@router.get("/")
async def get_all_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event))
    events = result.scalars().all()
    return events


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    request: Request,
    user: User = Depends(get_current_user),  # allow None
    db: AsyncSession = Depends(get_db)
):
    # Get event
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event Not found!")

    #check if user is registered
    if user:
        result = await db.execute(
            select(Registration).filter(
                Registration.event_id == event.id,
                Registration.user_id == user.id
            )
        )
        is_registered = result.scalars().first() is not None
    else:
        is_registered = False

    #Return TEMPLATE 
    return templates.TemplateResponse("event_detail.html", {
        "request": request,
        "event": event,
        "user": user,
        "is_registered": is_registered
})

# Register and unregister for events
# passes regiter test if already logged in 
# But if prompted to log in, after doing so is redirected to /register and gives a 405 error
@router.post("/{event_id}/register")
async def register_for_event(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event Not found!")

    result = await db.execute(
        select(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_id == user.id
        )
    )
    check_user_registered = result.scalars().first()

    if check_user_registered:
        raise HTTPException(status_code=400, detail="User already registered!")

    if event.capacity_limit is not None:
        result = await db.execute(
            select(Registration).filter(Registration.event_id == event_id)
        )
        count = len(result.scalars().all())

        if count >= event.capacity_limit:
            raise HTTPException(status_code=400, detail="Event is full")

    registration = Registration(event_id=event_id, user_id=user.id)
    db.add(registration)
    await db.commit()

    return templates.TemplateResponse("register_event.html", {
        "request": request,
        "event": event,
        "is_registered": True
})


@router.post("/{event_id}/unregister")
async def unregister_event(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    result = await db.execute(
        select(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_id == user.id
        )
    )
    registration = result.scalars().first()

    if not registration:
        raise HTTPException(status_code=404, detail="Not registered")

    await db.delete(registration)
    await db.commit()

    return templates.TemplateResponse("register_event.html", {
        "request": request,
        "event": event,
        "is_registered": False
    })


# Editing events
# Passes tests: brings up form, submits changes, redirects to events/{event_id}
@router.post("/{event_id}/edit")
async def edit_event(
    event_id: int,
    updated_event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised to edit this event")

    event.title = updated_event.title
    event.description = updated_event.description
    event.category = updated_event.category
    event.latitude = updated_event.latitude
    event.longitude = updated_event.longitude
    event.location_name = updated_event.location_name
    event.date_time = updated_event.date_time
    event.capacity_limit = updated_event.capacity_limit
    event.community_id = updated_event.community_id

    await db.commit()
    await db.refresh(event)

    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.get("/{event_id}/edit")
async def edit_event_form(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")

    return templates.TemplateResponse("edit_event.html", {
        "request": request,
        "event": event
    })


# Deleting events
# Passes tests, delete button on /events/{event_id} appears, works and redirets to /events
@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event Not found!")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")

    await db.delete(event)
    await db.commit()

    return RedirectResponse(url="/events", status_code=303)


# List of attendees
# passes tests: displays registered useres and changes if a new user is registered/unregistered 
@router.get("/{event_id}/attendees")
async def get_attendees(
    event_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db.execute(
        select(User).join(Registration).filter(Registration.event_id == event_id)
    )
    attendees = result.scalars().all()

    return [{"id": user.id, "username": user.username} for user in attendees]






# When registering the button doesnt change unregister until you refresh the code 
# add a create events button 



# Changed event_details to include a map place holder that redirects, include a view atendees button 
# improved the visuals of create event, delete event and register/unregister buttons 

# Auto logs out in create form 
# When trying to register while logged out it renders the register form in a weird way 

