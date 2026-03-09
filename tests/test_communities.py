"""
Tests for community routes (routers/communities.py).

These tests cover the routes defined in plan.md section 2.
Tests are written ahead of implementation — they will fail until the
routes are built. This is intentional (test-driven development).
"""

import pytest
from sqlalchemy import select
import models
from tests.conftest import make_auth_cookie


# ── List communities ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_communities_page(client, seed_community):
    resp = await client.get("/communities")
    assert resp.status_code == 200
    assert "Test Community" in resp.text


@pytest.mark.asyncio
async def test_list_communities_empty(client):
    resp = await client.get("/communities")
    assert resp.status_code == 200


# ── Create community ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_community_form_requires_login(client):
    """GET /communities/create should redirect or 401 if not logged in."""
    resp = await client.get("/communities/create", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


@pytest.mark.asyncio
async def test_create_community_form_renders(auth_client):
    resp = await auth_client.get("/communities/create")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_community_success(auth_client, db):
    resp = await auth_client.post("/communities/create", data={
        "name": "New Community",
        "description": "A brand new community.",
    }, follow_redirects=False)
    # Should redirect to the new community page
    assert resp.status_code in (302, 303)

    result = await db.execute(select(models.Community).filter_by(name="New Community"))
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_create_community_duplicate_name(auth_client, seed_community):
    resp = await auth_client.post("/communities/create", data={
        "name": "Test Community",  # already exists from seed_community
        "description": "duplicate",
    })
    # Should show error, not crash
    assert resp.status_code in (200, 409, 422)


@pytest.mark.asyncio
async def test_create_community_requires_login(client):
    resp = await client.post("/communities/create", data={
        "name": "No Auth", "description": "should fail"
    }, follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


# ── View single community ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_view_community(client, seed_community):
    resp = await client.get(f"/communities/{seed_community.id}")
    assert resp.status_code == 200
    assert "Test Community" in resp.text


@pytest.mark.asyncio
async def test_view_community_not_found(client):
    resp = await client.get("/communities/9999")
    assert resp.status_code == 404


# ── Edit community ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_community_requires_creator(auth_client, db, seed_users):
    """Only the creator should be able to access the edit form."""
    # Create a community owned by bob (seed_users[1])
    community = models.Community(name="Bob's Community", description="owned by bob", creator_id=seed_users[1].id)
    db.add(community)
    await db.commit()
    await db.refresh(community)

    # auth_client is logged in as alice — should be denied
    resp = await auth_client.get(f"/communities/{community.id}/edit", follow_redirects=False)
    assert resp.status_code in (403, 302)


@pytest.mark.asyncio
async def test_edit_community_success(auth_client, seed_community, db):
    resp = await auth_client.post(f"/communities/{seed_community.id}/edit", data={
        "name": "Updated Name",
        "description": "Updated description.",
    }, follow_redirects=False)
    assert resp.status_code in (200, 302, 303)

    await db.refresh(seed_community)
    assert seed_community.name == "Updated Name"


# ── Delete community ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_community_requires_creator(auth_client, db, seed_users):
    community = models.Community(name="Not Mine", description="x", creator_id=seed_users[1].id)
    db.add(community)
    await db.commit()
    await db.refresh(community)

    resp = await auth_client.delete(f"/communities/{community.id}")
    assert resp.status_code in (403, 302)


@pytest.mark.asyncio
async def test_delete_community_success(auth_client, seed_community, db):
    resp = await auth_client.delete(f"/communities/{seed_community.id}", follow_redirects=False)
    assert resp.status_code in (200, 302, 303)

    result = await db.execute(select(models.Community).filter_by(id=seed_community.id))
    assert result.scalars().first() is None
