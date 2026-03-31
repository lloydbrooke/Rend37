from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from models import Event, Registration, User
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated
from schemas import EventCreateForm
from auth_utils import get_current_user, require_current_user
from datetime import datetime
from haversine import haversine



router = APIRouter(prefix = "/events", tags = ["Events"])
templates = Jinja2Templates(directory="templates")

# not complete, templates need to be connected
# Creating events/forms
@router.get("/create")
async def create_event_form(
    request: Request,
    user: User = Depends(require_current_user)
):
    return templates.TemplateResponse("create_event.html", {
        "request": request
    })

@router.post("/create")
async def create_event(
    event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    
    #Validation
    if event.capacity_limit is None:
        raise HTTPException(status_code=400, detail="Must have a capacity limit") 
    if event.capacity_limit <= 0:
        raise HTTPException(status_code=400, detail="Invalid capacity limit") 
    if event.date_time <= datetime.now():               #not sure if this is how we should validate date_time
        raise HTTPException(status_code=400,detail="Date must be in the future")
    if not -90 <= event.latitude <= 90:
        raise HTTPException(status_code=400, detail="Invalid latitude")
    if not -180 <= event.longitude <= 180:
        raise HTTPException(status_code=400, detail="Invalid longitude")

    new_event = Event(
        title = event.title,
        description = event.description,
        category = event.category,
        latitude = event.latitude,
        longitude = event.longitude,
        location_name = event.location_name,  
        date_time = event.date_time,           
        capacity_limit = event.capacity_limit,
        community_id = event.community_id,
        organizer_id = user.id   
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return RedirectResponse(url="/events", status_code=303)


# Returning events
@router.get("/")
async def get_all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events

@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if (not event):
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    return event


# Register and unregister for events 
@router.post("/{event_id}/register")           
async def register_for_event(
    event_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # checks to see whether the event exists
    event = db.query(Event).filter(Event.id == event_id).first()  
    if (not event):
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    #checks to see if the user is already registered, prevent duplicate registers
    check_user_registered = db.query(Registration).filter(
        Registration.event_id == event_id, 
        Registration.user_id == user.id
    ).first()
    if check_user_registered:
        raise HTTPException(status_code= 400, detail = "User already registered!")
    # Checks if Null and  performs capacity check for said event 
    if event.capacity_limit is not None:
        count = db.query(Registration).filter(Registration.event_id == event_id).count()
        if count >= event.capacity_limit:
            raise HTTPException(status_code=400, detail="Event is full")
    
    registration = Registration(event_id = event_id, user_id = user.id)
    db.add(registration)
    db.commit()
    return{"message": "Registration Successful"}

@router.post("/{event_id}/unregister")
async def unregister_event(
    event_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    registration = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_id == user.id
    ).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Not registered")

    db.delete(registration)
    db.commit()

    return {"message": "Unregistered successfully"}


# might want to make a new update schema for partial updates
# Editing events
@router.post("/{event_id}/edit")
async def edit_event(
    event_id: int,
    updated_event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # Get event
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    #Authorisation check
    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised to edit this event")

    #Update fields
    event.title = updated_event.title
    event.description = updated_event.description
    event.category = updated_event.category
    event.latitude = updated_event.latitude
    event.longitude = updated_event.longitude
    event.location_name = updated_event.location_name
    event.date_time = updated_event.date_time
    event.capacity_limit = updated_event.capacity_limit
    event.community_id = updated_event.community_id

    db.commit()
    db.refresh(event)

    return event


@router.get("/{event_id}/edit")
async def edit_event_form(
    event_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")

    return templates.TemplateResponse("edit_event.html", {
        "request": request,
        "event": event
    })


# Deleting events 
@router.delete("/{event_id}")
async def delete_event(
    event_id : int, 
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code= 404, detail= "Event Not found!")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")

    
    db.delete(event)
    db.commit() 
    return {"message" : "Event successfully deleted"}


# List of attendees 
@router.get("/{event_id}/attendees")
async def get_attendees(
    event_id: int,
    db: Session = Depends(get_db)
):
    # Check event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get attendees via join
    attendees = db.query(User).join(Registration).filter(
        Registration.event_id == event_id
    ).all()


    return [{"id": user.id, "username": user.username} for user in attendees]



# Proximity search for events 
@router.get("/nearby")
async def get_nearby_events(
    # Gets data from the URL and automatically verifies
    lat: float = Query(..., ge=-90, le=90),
    long: float = Query(..., ge=-180, le=180),
    #not sure what the default value for radius should be 
    radius_km: float = Query(10, gt=0),
    db: Session = Depends(get_db)
):
    events = db.query(Event).all()

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

    # sorts by distance
    nearby_events.sort(key=lambda x: x["distance_km"])

    return nearby_events


# Still needed funcionality:

# Front end
# Any HTML or HTMX
# Some functions need to return text rather than raw objects 

# Create event form

# when registering for an event partially update button to "Unregister"