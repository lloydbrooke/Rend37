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