from typing import Annotated

from contextlib import asynccontextmanager
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)

from fastapi import FastAPI, Request, HTTPException, Response, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from starlette.exceptions import HTTPException as StarletteHTTPException

import auth_utils
from auth_utils import require_current_user, get_current_user, LoginRequiredException
import models

from routers import auth, communities, discussions, events, map as map_router

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
app.state.templates = templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# register routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(communities.router, prefix="/communities", tags=["communities"])
app.include_router(discussions.router, prefix="/events", tags=["discussions"])
app.include_router(map_router.router, prefix="/map", tags=["map"])


@app.get("/", response_class=HTMLResponse)
@app.get("/communities", response_class=HTMLResponse)
async def communities_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(models.Community).options(
            selectinload(models.Community.creator),
            selectinload(models.Community.events),
            selectinload(models.Community.members).selectinload(
                models.CommunityMember.user
            ),
        )
    )
    communities = result.scalars().all()

    return templates.TemplateResponse(
        "communities.html",
        {
            "request": request,
            "user": user,
            "communities": communities,
        },
    )


@app.exception_handler(LoginRequiredException)
async def login_required_handler(request: Request, exc: LoginRequiredException):
    # For HTMX requests, use HX-Redirect so the browser does a full-page navigate
    # instead of rendering the login page inside a partial div
    if request.headers.get("hx-request"):
        response = Response(status_code=200)
        response.headers["HX-Redirect"] = exc.redirect_url
        return response
    return RedirectResponse(url=exc.redirect_url, status_code=status.HTTP_303_SEE_OTHER)


""" error handling and feedback for user """


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request, exception: StarletteHTTPException
):
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
