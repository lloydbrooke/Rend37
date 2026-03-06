from typing import Annotated

from contextlib import asynccontextmanager
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from fastapi import FastAPI, Request, HTTPException, Response, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from starlette.exceptions import HTTPException as StarletteHTTPException

import auth_utils
import models

from routers import auth

from database import Base, engine, get_db

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
        result = await db.execute(select(models.User).filter(models.User.username == username))
        user = result.scalars().first()
    
    return templates.TemplateResponse("communities.html", {"request": request, "user": user})


@app.get("/communities", response_class=HTMLResponse)
async def communities_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    username = auth_utils.get_current_user_from_cookie(request)
    user = None
    if username:
        result = await db.execute(select(models.User).filter(models.User.username == username))
        user = result.scalars().first()

    result = await db.execute(select(models.Community))
    communities = result.scalars().all()
    return templates.TemplateResponse("communities.html", {
        "request": request,
        "user": user,
        "communities": communities,
    })

@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    username = auth_utils.get_current_user_from_cookie(request)
    user = None
    if username:
        result = await db.execute(select(models.User).filter(models.User.username == username))
        user = result.scalars().first()

    result = await db.execute(select(models.Event))
    events = result.scalars().all()
    return templates.TemplateResponse("events.html", {
        "request": request,
        "user": user,
        "events": events,
    })

@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    username = auth_utils.get_current_user_from_cookie(request)
    user = None
    if username:
        result = await db.execute(select(models.User).filter(models.User.username == username))
        user = result.scalars().first()

    return templates.TemplateResponse("map.html", {"request": request, "user": user})


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

