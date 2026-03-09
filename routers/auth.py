from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import auth_utils
import models
from database import get_db
from schemas import LoginForm, UserRegisterForm

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None, next: str = None):
    return templates.TemplateResponse("register.html", {"request": request, "error": error, "next": next})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, msg: str = None, error: str = None, next: str = None):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "success_msg": msg,
        "error": error,
        "next": next,
    })

@router.post("/register")
async def register_user(
    request: Request,
    form_data: Annotated[UserRegisterForm, Depends(UserRegisterForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    next: Annotated[str | None, Form()] = None,
):
    # check if username already exists
    user_stmt = select(models.User).filter(models.User.username == form_data.username)
    user_result = await db.execute(user_stmt)
    if user_result.scalars().first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"The username '{form_data.username}' is already taken.",
            "next": next,
        })

    # check if email already exists
    email_stmt = select(models.User).filter(models.User.email == form_data.email)
    email_result = await db.execute(email_stmt)
    if email_result.scalars().first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"the email '{form_data.email}' is already associated with an account.",
            "next": next,
        })

    # create user if both are clear
    try:
        new_user = models.User(
            username=form_data.username,
            email=form_data.email,
            hashed_password=auth_utils.hash_password(form_data.password)
        )
        db.add(new_user)
        await db.commit()
        login_url = "/auth/login?msg=Account+created+successfully"
        if next:
            login_url += f"&next={next}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        await db.rollback()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "An unexpected error occurred. Please try again.",
            "next": next,
        })

@router.post("/login")
async def login_user(
    response: Response,
    request: Request,
    form_data: Annotated[LoginForm, Depends(LoginForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    next: Annotated[str | None, Form()] = None,
):
    # Use Async-style query (select)
    result = await db.execute(select(models.User).filter(models.User.username == form_data.username))
    user = result.scalars().first()

    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "next": next})

    token = auth_utils.create_access_token(data={"sub": user.username})

    redirect_url = next if next and next.startswith("/") else "/communities"
    redirect = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, samesite="lax")
    return redirect

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/communities", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


''' user profile routes '''
@router.get("/profile")
async def get_user_profile(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user=Depends(auth_utils.require_current_user)
):
    result = await db.execute(
    select(models.User)
    .options(
        selectinload(models.User.owned_communities),
        selectinload(models.User.created_events),
        selectinload(models.User.community_memberships).selectinload(models.CommunityMember.community),
        selectinload(models.User.registrations).selectinload(models.Registration.event)
    )
    .filter(models.User.username == user.username)
    )   
    user_data = result.scalars().first()

    return templates.TemplateResponse("profile.html", {"request": request, "user": user_data})

