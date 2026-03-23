'''
Create basic functionality for creating an event, deleting an event and looking up the event
'''
from fastapi import APIRouter, Depends, HTTPException
from models import Event, Registration, User
from sqlalchemy.orm import Session
from database import get_db



router = APIRouter(prefix = "/events", tags = ["Events"])
@router.post("/")
async def create_event(event: Event, db: Session = Depends(get_db)):
    new_event = Event(
        event_id = event.id,            # Might not need this ID attribute since I think the DB generates a unique ID itself 
        event_title = event.title,
        event_description = event.description,
        event_category = event.category,
        event_capacity = event.capacity_limit,
        event_latitude = event.latitude,
        event_longitude = event.longitude
        )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    return new_event


@router.get("/")
async def get_all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events

@router.get("/{event_id}")
async def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if (not event):
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    return event
@router.post("/{event_id}/{register}")            # path should be "/{event_id}/register"
async def register_for_event(event_id: int, user_id: int, db: Session = Depends(get_db)):
    # checks to see whether the event exists
    event = db.query(Event).filter_by(Event.id == event_id, id).first()        # should be event = db.query(Event).filter(Event.id == event_id).first() 
    if (not event):
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    #checks to see if the user is already registered, prevent duplicate registers
    check_user_registered = db.query(Registration).filter(
        Registration.event_id == event_id, 
        Registration.user_id == user_id).first()
    if check_user_registered:
        raise HTTPException(status_code= 400, detail = "User already registered!")
    #perform capacity check for said event 
    person_count = db.query(Registration).filter(Registration.event_id == event_id).count()
    if person_count >= event.capacity:
        raise HTTPException(status_code= 400, detail = "Event is full")
    registration = Registration(event_id = event_id, user_id = user_id)
    db.add(registration)
    db.commit()
    return{"message": "Registration Successful"}


@router.delete("/{event_id}")
async def delete_event(event_id : int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    db.delete(event)
    db.commit() 
    return {"message" : "Event successfully deleted"}


@router.put("/{event_id}")
async def edit_event(event_id: int, updated_event : Event, db : Session = Depends(det_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code= 404, detail= "Event Not found!")
    
    event.title = updated_event.title,
    event.description = updated_event.description,
    event.category = updated_event.category,
    event.capacity = updated_event.capacity_limit,
    event.latitude = updated_event.latitude,
    event.longitude = updated_event.longitude
        
    db.commit()
    db.refresh(event)
    return event
        
        
    


'''
further functionality such a
'''
