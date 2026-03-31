from fastapi import APIRouter, Depends, HTTPException
from models import Event, Registration, User
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated
from schemas import EventCreateForm
from auth_utils import get_current_user, require_current_user
from datetime import datetime


router = APIRouter(prefix = "/events", tags = ["Events"])

# not complete, templates need to be connected
# Creating events/forms
@router.get("/create")
async def create_event_form():
    return {"message": "Render create event form here"}

@router.post("/create")
async def create_event(
    event: Annotated[EventCreateForm, Depends(EventCreateForm.as_form)],
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    
    #Validation
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

    return new_event

# Returning events
@router.get("/", response_model=None)
async def get_all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events

@router.get("/{event_id}")
async def get_event(event_id: int, db: Session = Depends(get_db)):
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


# might want to make a new update schema for partial updates
# Editing events
@router.put("/{event_id}")
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



# Still needed funcionality:
# Unregister from event 
# Output antendees list 
# Implement the authoraisation checking 
# Output nerby events 
# In github main/test/test_events.py the paths used are different from ours 
# Create event form
# Front end
# Cascade a delete event with delete registrations and messages 
# when registerign for an event partially update button to "Unregister"