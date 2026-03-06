from typing import Annotated

from contextlib import asynccontextmanager
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from fastapi import FastAPI, Form, Request, HTTPException, Response, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import auth_utils
import models

from routers import auth

from database import Base, engine, get_db

'''import route here'''
# from routers import 


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

'''example of how to register a route'''
app.include_router(auth.router, prefix='/auth', tags=['auth'])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    username = auth_utils.get_current_user_from_cookie(request)
    user = None
    
    if username:
        # Correct Async Syntax
        result = await db.execute(select(models.User).filter(models.User.username == username))
        user = result.scalars().first()
    
    # Usually you'd want to render "index.html" here, 
    # but I've kept "base.html" as per your code
    return templates.TemplateResponse("base.html", {"request": request, "user": user})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    username = auth_utils.get_current_user_from_cookie(request)
    if not username:
        return RedirectResponse(url="auth/login?error=Please+login+to+access+your+dashboard")

    result = await db.execute(
        select(models.User)
        .options(
            selectinload(models.User.owned_communities),
            selectinload(models.User.registrations)
        )
        .filter(models.User.username == username)
    )
    user = result.scalars().first()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": user
    })



''' error handling and feedback for user '''
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again."
    )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        status_code=exception.status_code,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Get the URL the user came from
    referer = request.headers.get("Referer")
    
    # Extract the first error message from Pydantic
    # Pydantic errors look like: [{'loc': ('body', 'username'), 'msg': 'field required', ...}]
    errors = exc.errors()
    error_msg = "Invalid input"
    if errors:
        location = errors[0]['loc'][-1]
        raw_msg = errors[0]['msg']
        error_msg = f"Error in {location}: {raw_msg}"

    # If we know where they came from, send them back with the error in the URL
    if referer:
        # Check if there's already a query param
        separator = "&" if "?" in referer else "?"
        return RedirectResponse(
            url=f"{referer}{separator}error={error_msg}", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Fallback to a generic error page if no referer found
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "message": error_msg}, 
        status_code=422
    )