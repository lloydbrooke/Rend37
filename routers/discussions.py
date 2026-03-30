from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import models 
import auth_utils 
from database import get_db

router = APIRouter()

@router.get("/{event_id}/discussions")
async def get_event_discussions(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_current_user)
):
    # 1. Authorization: Only registered attendees
    reg_stmt = select(models.Registration).where(
        models.Registration.event_id == event_id,
        models.Registration.user_id == current_user.id
    )
    result = await db.execute(reg_stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Must be registered to view discussions.")
    
    # 2. Fetch all messages with authors
    msg_stmt = select(models.Message).where(
        models.Message.event_id == event_id
    ).options(selectinload(models.Message.author))
    all_messages = (await db.execute(msg_stmt)).scalars().all()

    # 3. Build the Thread Tree
    roots = [] 
    msg_map = {msg.id : msg for msg in all_messages}
    for msg in all_messages:
        msg.temp_replies = []

    for msg in all_messages:
        if msg.parent_id is None:
            roots.append(msg)
        else:
            parent = msg_map.get(msg.parent_id)
            if parent:
                parent.temp_replies.append(msg)

    templates = request.app.state.templates 
    return templates.TemplateResponse("partials/discussions.html", {
        "request": request,
        "roots": roots, 
        "event_id": event_id,
        "user": current_user
    })

@router.post("/{event_id}/discussions")
async def post_message(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_current_user),
    content: str = Form(...),
    parent_id: int | None = Form(None)
):
    # Verify registration
    reg_stmt = select(models.Registration).where(
        models.Registration.event_id == event_id,
        models.Registration.user_id == current_user.id
    )
    if not (await db.execute(reg_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="Must be registered to post.")
    
    new_message = models.Message(
        content=content, user_id=current_user.id, event_id=event_id, parent_id=parent_id
    )
    db.add(new_message)
    await db.commit()
    
    # Eager load author for the partial
    await db.execute(select(models.Message).options(selectinload(models.Message.author)).where(models.Message.id == new_message.id))
    await db.refresh(new_message)
    
    templates = request.app.state.templates 
    return templates.TemplateResponse("partials/message.html", {
        "request": request,
        "message": new_message,
        "event_id": event_id,
        "user": current_user,
        "is_new": True
    })

@router.delete("/{event_id}/discussions/{message_id}")
async def delete_message(
    event_id: int,
    message_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth_utils.require_current_user)
):
    # Fix: Correctly select the Message and load its Event to check the Organizer
    stmt = select(models.Message).options(selectinload(models.Message.event)).where(
        models.Message.id == message_id, 
        models.Message.event_id == event_id
    )
    message = (await db.execute(stmt)).scalars().first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")
    
    # RBAC: Author or Event Organizer
    if not (message.user_id == current_user.id or message.event.organizer_id == current_user.id):
        raise HTTPException(status_code=403, detail="Permission denied.")

    # actually delete the message from the db
    await db.delete(message)
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}/discussions", status_code=302)