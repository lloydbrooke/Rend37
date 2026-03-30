from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException

from auth_utils import LoginRequiredException

from routers import auth, communities, events, discussions, map as map_router

from database import Base, engine

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

# register all the routers
app.include_router(auth.router, prefix='/auth', tags=['auth'])
app.include_router(communities.router, prefix='/communities', tags=['communities'])
app.include_router(events.router, prefix='/events', tags=['events'])
app.include_router(discussions.router, prefix='/events', tags=['discussions'])
app.include_router(map_router.router, prefix='/map', tags=['map'])


# homepage just redirects to communities for now
@app.get("/")
async def homepage():
    return RedirectResponse(url="/communities", status_code=302)


@app.exception_handler(LoginRequiredException)
async def login_required_handler(request: Request, exc: LoginRequiredException):
    return RedirectResponse(url=exc.redirect_url, status_code=status.HTTP_302_FOUND)

''' error handling and feedback for user '''
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again."
    )

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        status_code=exception.status_code,
    )
