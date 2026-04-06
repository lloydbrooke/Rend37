from urllib.parse import quote
from datetime import datetime, timedelta, UTC
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db


class LoginRequiredException(HTTPException):
    """Raised when a user must log in. Carries the redirect URL."""

    def __init__(self, redirect_url: str):
        super().__init__(status_code=401, detail="Not logged in")
        self.redirect_url = redirect_url


SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if len(password) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    # Ensure this uses UTC
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user_from_cookie(request: Request):
    """Checks the 'access_token' cookie for a valid JWT"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        # Remove "Bearer " prefix if present
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")  # Returns the username
    except JWTError:
        return None


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """FastAPI dependency: returns the full User model object or None."""
    import models

    username = get_current_user_from_cookie(request)
    if not username:
        return None
    result = await db.execute(
        select(models.User).filter(models.User.username == username)
    )
    return result.scalars().first()


async def require_current_user(request: Request, user=Depends(get_current_user)):
    """FastAPI dependency: redirects to login if not authenticated.
    After login the user is sent back to the page they originally requested."""
    if not user:
        # For POST/DELETE/etc, redirect back to the page the user was on (Referer),
        # not the action URL which would 405 on GET
        if request.method == "GET":
            next_url = str(request.url.path)
            if request.url.query:
                next_url += f"?{request.url.query}"
        else:
            referer = request.headers.get("referer", "")
            # Extract just the path from the referer URL
            if referer:
                from urllib.parse import urlparse

                next_url = urlparse(referer).path
            else:
                next_url = "/"
        raise LoginRequiredException(
            redirect_url=f"/auth/login?error=Please+login+first&next={quote(next_url, safe='')}"
        )
    return user
