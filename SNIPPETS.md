# Some useful snippets to help you

## Protecting routes behind authorization

Import at the top of your router file:
```python
from auth_utils import get_current_user, require_current_user
```

### Protected route (login required)
If the user is not logged in they get redirected to `/auth/login`, then sent back after login.
`user` is a full User model object — no manual DB lookup needed.

```python
@router.get("/protected", response_class=HTMLResponse)
async def protected_page(request: Request, user=Depends(require_current_user)):
    return templates.TemplateResponse("page.html", {
        "request": request,
        "user": user,
    })
```

### Optional auth route (public, but may need user data if they are logged in)
Page is visible to everyone. `user` is the User object if logged in, else `None`.

```python
@router.get("/public", response_class=HTMLResponse)
async def public_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("page.html", {
        "request": request,
        "user": user,   # None if not logged in
    })
```

## When you want a user with all their communities and registrations

```python
#when you extract the user from the db the things in the relationships dont come automatically
#selectinload makes sure you have those
#in the html you can then use dot notation to access shit like user.username, user.registrations or whatever

result = await db.execute(
    select(models.User)
    .options(
        selectinload(models.User.owned_communities),
        selectinload(models.User.registrations)
    )
    .filter(models.User.username == username)
)
user = result.scalars().first()
```
