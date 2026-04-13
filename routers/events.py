from models import Event, Registration, User, Community, CommunityMember
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from models import Event, Registration, User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
import models
import auth_utils
from typing import Annotated
from schemas import EventCreateForm
from auth_utils import get_current_user, require_current_user
from datetime import datetime
from haversine import haversine

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Creating events/forms
# Passed test
@router.get("/create")
async def create_event_form(
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
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
            detail="You must be a member of a community to create an event",
        )

    return templates.TemplateResponse(
        "event_form.html",
        {
            "request": request,
            "communities": communities,
            "user": user,
        },
    )


@router.post("/create")
async def create_event(
    event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify user is actually a member of the submitted community
    result = await db.execute(
        select(CommunityMember).filter(
            CommunityMember.user_id == user.id,
            CommunityMember.community_id == event.community_id,
        )
    )
    # Validation
    if not result.scalars().first():
        raise HTTPException(
            status_code=403, detail="You are not a member of this community"
        )
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
        organizer_id=user.id,
    )

    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)

    return RedirectResponse(url="/events", status_code=303)

@router.get("/", response_class=HTMLResponse)
async def events_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    username = auth_utils.get_current_user_from_cookie(request)
    user = None
    if username:
        result = await db.execute(
            select(models.User).filter(models.User.username == username)
        )
        user = result.scalars().first()

    result = await db.execute(select(models.Event))
    events = result.scalars().all()
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "user": user,
            "events": events,
        },
    )


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).filter(Event.id == event_id))
    event = event_result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event Not found!")

    count_result = await db.execute(
        select(Registration).filter(Registration.event_id == event_id)
    )
    attendee_count = len(count_result.scalars().all())

    if user:
        reg_result = await db.execute(
            select(Registration).filter(
                Registration.event_id == event.id, Registration.user_id == user.id
            )
        )
        is_registered = reg_result.scalars().first() is not None
    else:
        is_registered = False

    return templates.TemplateResponse(
        "event_detail.html",
        {
            "request": request,
            "event": event,
            "user": user,
            "is_registered": is_registered,
            "attendee_count": attendee_count,
        },
    )


# Register and unregister for events
# passes regiter test if already logged in
# But if prompted to log in, after doing so is redirected to /register and gives a 405 error
@router.post("/{event_id}/register")
async def register_for_event(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event Not found!")

    result = await db.execute(
        select(Registration).filter(
            Registration.event_id == event_id, Registration.user_id == user.id
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
            return templates.TemplateResponse(
                "Partials/register_button.html",
                {
                    "request": request,
                    "event": event,
                    "is_registered": False,
                    "error": "This event is full.",
                },
            )

    registration = Registration(event_id=event_id, user_id=user.id)
    db.add(registration)
    await db.commit()

    # Count attendees after registration
    count_result = await db.execute(
        select(Registration).filter(Registration.event_id == event_id)
    )
    attendee_count = len(count_result.scalars().all())

    response = templates.TemplateResponse(
        "Partials/register_button.html",
        {
            "request": request,
            "event": event,
            "is_registered": True,
            "attendee_count": attendee_count,
        },
    )
    response.headers["HX-Trigger"] = "registration-changed"
    return response


@router.post("/{event_id}/unregister")
async def unregister_event(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    result = await db.execute(
        select(Registration).filter(
            Registration.event_id == event_id, Registration.user_id == user.id
        )
    )
    registration = result.scalars().first()

    if not registration:
        raise HTTPException(status_code=404, detail="Not registered")

    await db.delete(registration)
    await db.commit()

    # Count attendees after unregistration
    count_result = await db.execute(
        select(Registration).filter(Registration.event_id == event_id)
    )
    attendee_count = len(count_result.scalars().all())

    response = templates.TemplateResponse(
        "Partials/register_button.html",
        {
            "request": request,
            "event": event,
            "is_registered": False,
            "attendee_count": attendee_count,
        },
    )
    response.headers["HX-Trigger"] = "registration-changed"
    return response


# Editing events
# Passes tests: brings up form, submits changes, redirects to events/{event_id}
@router.post("/{event_id}/edit")
async def edit_event(
    event_id: int,
    updated_event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")

    # Fetch communities the user is a member of
    result = await db.execute(
        select(Community)
        .join(CommunityMember, Community.id == CommunityMember.community_id)
        .filter(CommunityMember.user_id == user.id)
    )
    communities = result.scalars().all()

    return templates.TemplateResponse(
        "event_form.html",
        {
            "request": request,
            "event": event,
            "communities": communities,
            "user": user,
        },
    )


# Deleting events
# Passes tests, delete button on /events/{event_id} appears, works and redirets to /events
@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
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
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).filter(Event.id == event_id))
    event = event_result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    attendees_result = await db.execute(
        select(User).join(Registration).filter(Registration.event_id == event_id)
    )
    attendees = attendees_result.scalars().all()

    return templates.TemplateResponse(
        "Partials/attendee_list.html",
        {"request": request, "event": event, "attendees": attendees, "user": user},
    )


# ====== CHANGED =======
# coppied in /router/discussion.py and /templates/Partials from the feature/event-discussions branch
# Implemnted the discussions into event_detail.html
# Replaced the place holder for map in the event_details section with an interative map
# Added cascading dletes for message replies in models.py
# Moved register_button.html and attendee_list.html into Partials folder and added a nearby_events.html


# ====== ISSUES =========
# when implementing the discussions files i had to change how the template object was fetched, from request.app.state.templates to templates = Jinja2Templates(directory="templates")
# Auto logs out in create form
# When trying to register while logged out it renders the register form in a weird way
# No partial reload for the discussion feature after registering/unregistering for an event
# Lots of red underlined code in event details and event forms to do with the map, works as normal tho
# No cascading delete for user registration and messages, so if a user is deleted nothing will change

# ====== CHANGES (5th April update) =======
# Added some default values for latitude and longitude in the backend for testing purposes, so the nearby events page doesn't come up blank.
# Altered the nearby events endpoint to return the full nearby.html template if it's a normal request, and the nearby_events partial if it's an HTMX request
# Added a new page for nearby events, with a form to submit the latitude, longitude and radius, and a section for results. The form submits to the same endpoint but with HTMX, so the results are rendered as a partial in the same page.
# Added a new template for nearby events (nearby.html)
# updated attendee list partial to include an avatar for each user, using the ui-avatars service to generate them based on their username.
