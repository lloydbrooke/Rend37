from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request, Response, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import auth_utils
import models
from database import get_db
from schemas import CommunityCreateForm, CommunityUpdateForm

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/")
async def create_community(
    request: Request,
    form_data: Annotated[CommunityCreateForm, Depends(CommunityCreateForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user),
):
    """Create a new community (requires authentication)"""
    try:
        # Check if community name already exists
        existing = await db.execute(
            select(models.Community).filter(models.Community.name == form_data.name)
        )
        if existing.scalars().first():
            return RedirectResponse(
                url="/communities?error=Community+name+already+exists",
                status_code=status.HTTP_302_FOUND,
            )
        # Create new community
        new_community = models.Community(
            name=form_data.name.capitalize(), description=form_data.description, creator_id=user.id
        )
        db.add(new_community)
        await db.flush()

        # Auto-register creator as a member
        new_membership = models.CommunityMember(
            user_id=user.id, community_id=new_community.id
        )
        db.add(new_membership)
        await db.commit()
        await db.refresh(new_community)

        return RedirectResponse(
            url=f"/communities/{new_community.id}?msg=Community+created+successfully",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        await db.rollback()
        return RedirectResponse(
            url="/communities?error=Failed+to+create+community",
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/{community_id}")
async def get_community(
    community_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user=Depends(auth_utils.get_current_user),
):
    """Get a specific community with its events and members"""
    result = await db.execute(
        select(models.Community)
        .options(
            selectinload(models.Community.creator),
            selectinload(models.Community.events)
            .selectinload(models.Event.attendees)
            .selectinload(models.Registration.user),
            selectinload(models.Community.members).selectinload(
                models.CommunityMember.user
            ),
        )
        .filter(models.Community.id == community_id)
    )
    community = result.scalars().first()

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Check if current user is a member
    is_member = False
    if current_user:
        member_result = await db.execute(
            select(models.CommunityMember).filter(
                models.CommunityMember.user_id == current_user.id,
                models.CommunityMember.community_id == community_id,
            )
        )
        is_member = member_result.scalars().first() is not None

    is_creator = current_user and current_user.id == community.creator_id

    return templates.TemplateResponse(
        "community_detail.html",
        {
            "request": request,
            "community": community,
            "user": current_user,
            "is_member": is_member,
            "is_creator": is_creator,
        },
    )


@router.post("/{community_id}")
async def update_community(
    community_id: int,
    request: Request,
    form_data: Annotated[CommunityUpdateForm, Depends(CommunityUpdateForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user),
):
    """Update a community (only creator can update)"""
    result = await db.execute(
        select(models.Community).filter(models.Community.id == community_id)
    )
    community = result.scalars().first()

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    if community.creator_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the community creator can update this community",
        )

    try:
        if form_data.name:
            # Check if new name already exists
            existing = await db.execute(
                select(models.Community).filter(
                    models.Community.name == form_data.name,
                    models.Community.id != community_id,
                )
            )
            if existing.scalars().first():
                return RedirectResponse(
                    url=f"/communities/{community_id}?error=Community+name+already+exists",
                    status_code=status.HTTP_302_FOUND,
                )
            community.name = form_data.name

        if form_data.description:
            community.description = form_data.description

        await db.commit()
        return RedirectResponse(
            url=f"/communities/{community_id}?msg=Community+updated+successfully",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/communities/{community_id}?error=Failed+to+update+community",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/{community_id}/delete")
async def delete_community(
    community_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user),
):
    """Delete a community (only creator can delete)"""
    result = await db.execute(
        select(models.Community).filter(models.Community.id == community_id)
    )
    community = result.scalars().first()

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    if community.creator_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the community creator can delete this community",
        )

    try:
        await db.delete(community)
        await db.commit()
        return RedirectResponse(
            url="/communities?msg=Community+deleted+successfully",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete community")


@router.post("/{community_id}/join")
async def join_community(
    community_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user),
):
    """Join a community"""
    result = await db.execute(
        select(models.Community).filter(models.Community.id == community_id)
    )
    community = result.scalars().first()

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Check if already a member
    existing_member = await db.execute(
        select(models.CommunityMember).filter(
            models.CommunityMember.user_id == user.id,
            models.CommunityMember.community_id == community_id,
        )
    )
    if existing_member.scalars().first():
        return RedirectResponse(
            url=f"/communities/{community_id}?msg=Already+a+member",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        new_membership = models.CommunityMember(
            user_id=user.id, community_id=community_id
        )
        db.add(new_membership)
        await db.commit()
        return RedirectResponse(
            url=f"/communities/{community_id}?msg=Joined+community+successfully",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to join community")


@router.post("/{community_id}/leave")
async def leave_community(
    community_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user),
):
    """Leave a community"""
    result = await db.execute(
        select(models.CommunityMember).filter(
            models.CommunityMember.user_id == user.id,
            models.CommunityMember.community_id == community_id,
        )
    )
    membership = result.scalars().first()

    if not membership:
        raise HTTPException(status_code=404, detail="Not a member of this community")

    try:
        await db.delete(membership)
        await db.commit()
        return RedirectResponse(
            url=f"/communities/{community_id}?msg=Left+community+successfully",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to leave community")
