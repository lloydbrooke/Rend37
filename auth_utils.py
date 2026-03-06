from datetime import datetime, timedelta, UTC
from typing import Optional
from fastapi import Request, HTTPException, status
from jose import JWTError
from jose import jwt
from passlib.context import CryptContext


# Configuration
SECRET_KEY = "your_secret_key_here" # Keep this safe!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    # Ensure the password isn't massive, though 72 is plenty for users
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
        return payload.get("sub") # Returns the username
    except JWTError:
        return None