# Some useful snippets to help you

## Protecting routes behing authorization

```python
#add this at the top of any route that you want to protect behind authorization
#replace the last bit with whatever route you want to return to after logging in 

username = auth_utils.get_current_user_from_cookie(request)
if not username:
    return RedirectResponse(url="/auth/login?error=Please+login+first&next=/<route to go to after logging in>")
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
