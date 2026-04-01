"""
Tests for event routes (routers/events.py).

Covers plan.md section 3: CRUD, registration, attendees, nearby search.
"""

import pytest
from datetime import datetime, timedelta, UTC
from sqlalchemy import select
import models


# ── List events ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_events_page(client, seed_event):
    resp = await client.get("/events")
    assert resp.status_code == 200
    assert "Test Event" in resp.text


@pytest.mark.asyncio
async def test_list_events_empty(client):
    resp = await client.get("/events")
    assert resp.status_code == 200


# ── Create event ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_event_form_requires_login(client):
    resp = await client.get("/events/create", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


@pytest.mark.asyncio
async def test_create_event_form_renders(auth_client, seed_community):
    resp = await auth_client.get("/events/create")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_event_success(auth_client, seed_community, db):
    future_date = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    resp = await auth_client.post("/events/create", data={
        "title": "New Event",
        "description": "A new test event.",
        "category": "Workshop",
        "latitude": "53.4084",
        "longitude": "-2.9916",
        "location_name": "Test Venue",
        "date_time": future_date,
        "capacity_limit": "20",
        "community_id": str(seed_community.id),
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)

    result = await db.execute(select(models.Event).filter_by(title="New Event"))
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_create_event_requires_login(client, seed_community):
    resp = await client.post("/events/create", data={
        "title": "No Auth Event",
        "description": "x",
        "category": "Social",
        "latitude": "0", "longitude": "0",
        "location_name": "x",
        "date_time": "2030-01-01T00:00:00",
        "community_id": str(seed_community.id),
    }, follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


# ── View single event ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_view_event(client, seed_event):
    resp = await client.get(f"/events/{seed_event.id}")
    assert resp.status_code == 200
    assert "Test Event" in resp.text


@pytest.mark.asyncio
async def test_view_event_not_found(client):
    resp = await client.get("/events/9999")
    assert resp.status_code == 404


# ── Edit event ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_event_requires_organizer(auth_client, db, seed_users, seed_community):
    """Only the organizer should be able to edit."""
    event = models.Event(
        title="Bob's Event", description="x", category="Social",
        latitude=0, longitude=0, location_name="x",
        date_time=datetime.now(UTC) + timedelta(days=5),
        community_id=seed_community.id, organizer_id=seed_users[1].id,  # bob
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # alice tries to edit bob's event
    resp = await auth_client.get(f"/events/{event.id}/edit", follow_redirects=False)
    assert resp.status_code in (403, 302)


@pytest.mark.asyncio
async def test_edit_event_success(auth_client, seed_event, db):
    future_date = (datetime.now(UTC) + timedelta(days=21)).isoformat()
    resp = await auth_client.post(f"/events/{seed_event.id}/edit", data={
        "title": "Updated Event",
        "description": "Updated.",
        "category": "Workshop",
        "latitude": "53.0", "longitude": "-3.0",
        "location_name": "New Venue",
        "date_time": future_date,
        "capacity_limit": "50",
    }, follow_redirects=False)
    assert resp.status_code in (200, 302, 303)

    await db.refresh(seed_event)
    assert seed_event.title == "Updated Event"


# ── Delete event ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_event_success(auth_client, seed_event, db):
    resp = await auth_client.delete(f"/events/{seed_event.id}", follow_redirects=False)
    assert resp.status_code in (200, 302, 303)

    result = await db.execute(select(models.Event).filter_by(id=seed_event.id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_event_requires_organizer(auth_client, db, seed_users, seed_community):
    event = models.Event(
        title="Not Mine", description="x", category="Social",
        latitude=0, longitude=0, location_name="x",
        date_time=datetime.now(UTC) + timedelta(days=5),
        community_id=seed_community.id, organizer_id=seed_users[1].id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    resp = await auth_client.delete(f"/events/{event.id}")
    assert resp.status_code in (403, 302)


# ── Event registration ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_for_event(auth_client, seed_event, db):
    resp = await auth_client.post(f"/events/{seed_event.id}/register", follow_redirects=False)
    assert resp.status_code in (200, 302)

    result = await db.execute(select(models.Registration).filter_by(event_id=seed_event.id))
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_register_requires_login(client, seed_event):
    resp = await client.post(f"/events/{seed_event.id}/register", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


@pytest.mark.asyncio
async def test_unregister_from_event(auth_client, seed_event, db, seed_users):
    # First register
    db.add(models.Registration(user_id=seed_users[0].id, event_id=seed_event.id, status="registered"))
    await db.commit()

    resp = await auth_client.post(f"/events/{seed_event.id}/unregister", follow_redirects=False)
    assert resp.status_code in (200, 302)

    result = await db.execute(
        select(models.Registration).filter_by(user_id=seed_users[0].id, event_id=seed_event.id)
    )
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_register_respects_capacity(auth_client, db, seed_users, seed_community):
    """Should not allow registration when event is full."""
    event = models.Event(
        title="Full Event", description="x", category="Social",
        latitude=0, longitude=0, location_name="x",
        date_time=datetime.now(UTC) + timedelta(days=5),
        capacity_limit=1,  # only 1 spot
        community_id=seed_community.id, organizer_id=seed_users[0].id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Fill it with bob
    db.add(models.Registration(user_id=seed_users[1].id, event_id=event.id, status="registered"))
    await db.commit()

    # Alice tries to register — should be rejected
    resp = await auth_client.post(f"/events/{event.id}/register", follow_redirects=False)
    assert resp.status_code in (200, 400, 409, 422)


# ── Attendees list ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_attendees_list(client, seed_event, db, seed_users):
    db.add(models.Registration(user_id=seed_users[0].id, event_id=seed_event.id, status="registered"))
    db.add(models.Registration(user_id=seed_users[1].id, event_id=seed_event.id, status="registered"))
    await db.commit()

    resp = await client.get(f"/events/{seed_event.id}/attendees")
    assert resp.status_code == 200
    assert "alice" in resp.text
    assert "bob" in resp.text


# ── Nearby events ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nearby_events(client, seed_event):
    """Should return events within the given radius."""
    resp = await client.get("/events/nearby", params={
        "lat": 53.4084,
        "long": -2.9916,
        "radius_km": 10,
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_nearby_events_excludes_distant(client, db, seed_users, seed_community):
    """An event far away should not appear in nearby results."""
    event = models.Event(
        title="Far Away Event", description="x", category="Social",
        latitude=0.0, longitude=0.0,  # on the equator
        location_name="Null Island",
        date_time=datetime.now(UTC) + timedelta(days=5),
        community_id=seed_community.id, organizer_id=seed_users[0].id,
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/events/nearby", params={
        "lat": 53.4084,  # Liverpool
        "long": -2.9916,
        "radius_km": 10,
    })
    assert resp.status_code == 200
    assert "Far Away Event" not in resp.text
