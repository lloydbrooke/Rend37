from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
import auth_utils
from database import get_db

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def list_communities(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await auth_utils.get_current_user(request, db)
    result = await db.execute(select(models.Community))
    communities = result.scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse("communities.html", {
        "request": request,
        "user": user,
        "communities": communities,
    })


@router.get("/create", response_class=HTMLResponse)
async def create_community_form(
    request: Request,
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    templates = request.app.state.templates
    return templates.TemplateResponse("community_create.html", {
        "request": request,
        "user": current_user,
    })


@router.post("/create")
async def create_community(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
    name: str = Form(...),
    description: str = Form(...),
):
    # check if a community with that name already exists
    existing = await db.execute(select(models.Community).where(models.Community.name == name))
    if existing.scalars().first():
        templates = request.app.state.templates
        return templates.TemplateResponse("community_create.html", {
            "request": request,
            "user": current_user,
            "error": "A community with that name already exists.",
        }, status_code=409)

    community = models.Community(name=name, description=description, creator_id=current_user.id)
    db.add(community)
    await db.commit()
    await db.refresh(community)
    return RedirectResponse(url=f"/communities/{community.id}", status_code=303)


@router.get("/{community_id}", response_class=HTMLResponse)
async def view_community(
    community_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await auth_utils.get_current_user(request, db)
    result = await db.execute(
        select(models.Community)
        .options(selectinload(models.Community.creator), selectinload(models.Community.events))
        .where(models.Community.id == community_id)
    )
    community = result.scalars().first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    templates = request.app.state.templates
    return templates.TemplateResponse("community_detail.html", {
        "request": request,
        "user": user,
        "community": community,
    })


@router.get("/{community_id}/edit", response_class=HTMLResponse)
async def edit_community_form(
    community_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(select(models.Community).where(models.Community.id == community_id))
    community = result.scalars().first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    # only the person who made it can edit
    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can edit this community.")
    templates = request.app.state.templates
    return templates.TemplateResponse("community_edit.html", {
        "request": request,
        "user": current_user,
        "community": community,
    })


@router.post("/{community_id}/edit")
async def edit_community(
    community_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
    name: str = Form(...),
    description: str = Form(...),
):
    result = await db.execute(select(models.Community).where(models.Community.id == community_id))
    community = result.scalars().first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can edit this community.")
    community.name = name
    community.description = description
    await db.commit()
    return RedirectResponse(url=f"/communities/{community_id}", status_code=303)


@router.delete("/{community_id}")
async def delete_community(
    community_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: models.User = Depends(auth_utils.require_current_user),
):
    result = await db.execute(select(models.Community).where(models.Community.id == community_id))
    community = result.scalars().first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this community.")
    await db.delete(community)
    await db.commit()
    return RedirectResponse(url="/communities", status_code=303)
