from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import auth_utils
import models
from database import get_db
from schemas import LoginForm, UserRegisterForm

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    return templates.TemplateResponse("register.html", {"request": request, "error": error})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, msg: str = None, error: str = None):
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "success_msg": msg,
        "error": error # Now handles the dashboard-kick-back error
    })

# --- LOGIC (POST REQUESTS) ---
@router.post("/register")
async def register_user(
    request: Request,
    form_data: Annotated[UserRegisterForm, Depends(UserRegisterForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None 
):
    # 1. Check if Username exists
    user_stmt = select(models.User).filter(models.User.username == form_data.username)
    user_result = await db.execute(user_stmt)
    if user_result.scalars().first():
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": f"The username '{form_data.username}' is already taken."
        })

    # 2. Check if Email exists
    email_stmt = select(models.User).filter(models.User.email == form_data.email)
    email_result = await db.execute(email_stmt)
    if email_result.scalars().first():
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": f"the email '{form_data.email}' is already associated with an account."
        })

    # 3. Create user if both are clear
    try:
        new_user = models.User(
            username=form_data.username,
            email=form_data.email,
            hashed_password=auth_utils.hash_password(form_data.password)
        )
        db.add(new_user)
        await db.commit()
        return RedirectResponse(url="/auth/login?msg=Account+created+successfully", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        await db.rollback()
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "An unexpected error occurred. Please try again."
        })

@router.post("/login")
async def login_user(
    response: Response,
    request: Request,
    form_data: Annotated[LoginForm, Depends(LoginForm.as_form)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    # Use Async-style query (select)
    result = await db.execute(select(models.User).filter(models.User.username == form_data.username))
    user = result.scalars().first()
    
    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    token = auth_utils.create_access_token(data={"sub": user.username})
    
    redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, samesite="lax")
    return redirect

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response