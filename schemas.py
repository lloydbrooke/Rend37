from typing import Type, Annotated
import inspect
from pydantic import BaseModel, EmailStr
from fastapi import Form, Depends

def as_form(cls: Type[BaseModel]):
    new_params = [
        inspect.Parameter(
            field_name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Form(...),
            annotation=field.annotation,
        )
        for field_name, field in cls.model_fields.items()
    ]

    def _as_form(**data):
        return cls(**data)

    _as_form.__signature__ = inspect.Signature(new_params)
    setattr(cls, "as_form", _as_form)
    return cls

@as_form
class UserRegisterForm(BaseModel):
    username: str
    email: EmailStr  # Automatically validates email format!
    password: str

@as_form
class LoginForm(BaseModel):
    username: str
    password: str