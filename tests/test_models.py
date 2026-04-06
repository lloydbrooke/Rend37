"""
Tests for SQLAlchemy models — relationships, constraints, and defaults.
"""

import pytest
from datetime import datetime, timedelta, UTC
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import models


# ── User model ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user(db):
    user = models.User(
        username="testuser", email="test@test.com", hashed_password="fakehash"
    )
    db.add(user)
    await db.commit()

    result = await db.execute(select(models.User).filter_by(username="testuser"))
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.email == "test@test.com"
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_username_unique_constraint(db):
    db.add(
        models.User(username="duplicate", email="a@test.com", hashed_password="hash1")
    )
    await db.commit()
    db.add(
        models.User(username="duplicate", email="b@test.com", hashed_password="hash2")
    )
    with pytest.raises(IntegrityError):
        await db.commit()


@pytest.mark.asyncio
async def test_email_unique_constraint(db):
    db.add(
        models.User(username="user1", email="same@test.com", hashed_password="hash1")
    )
    await db.commit()
    db.add(
        models.User(username="user2", email="same@test.com", hashed_password="hash2")
    )
    with pytest.raises(IntegrityError):
        await db.commit()


# ── Community model ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_community(db, seed_users):
    community = models.Community(
        name="My Community", description="desc", creator_id=seed_users[0].id
    )
    db.add(community)
    await db.commit()

    result = await db.execute(select(models.Community).filter_by(name="My Community"))
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.creator_id == seed_users[0].id


@pytest.mark.asyncio
async def test_community_name_unique(db, seed_users):
    db.add(
        models.Community(name="Unique", description="a", creator_id=seed_users[0].id)
    )
    await db.commit()
    db.add(
        models.Community(name="Unique", description="b", creator_id=seed_users[0].id)
    )
    with pytest.raises(IntegrityError):
        await db.commit()


# ── Event model ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_event(db, seed_event):
    result = await db.execute(select(models.Event).filter_by(title="Test Event"))
    event = result.scalars().first()
    assert event is not None
    assert event.category == "Social"
    assert event.capacity_limit == 10
    assert event.latitude == pytest.approx(53.4084)
    assert event.longitude == pytest.approx(-2.9916)


# ── Registration model ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_registration(db, seed_users, seed_event):
    reg = models.Registration(
        user_id=seed_users[1].id, event_id=seed_event.id, status="registered"
    )
    db.add(reg)
    await db.commit()

    result = await db.execute(
        select(models.Registration).filter_by(
            user_id=seed_users[1].id, event_id=seed_event.id
        )
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.status == "registered"


@pytest.mark.asyncio
async def test_duplicate_registration_fails(db, seed_users, seed_event):
    db.add(models.Registration(user_id=seed_users[0].id, event_id=seed_event.id))
    await db.commit()
    db.add(models.Registration(user_id=seed_users[0].id, event_id=seed_event.id))
    with pytest.raises(IntegrityError):
        await db.commit()


# ── Message model ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_message(db, seed_users, seed_event):
    msg = models.Message(
        content="Hello world", user_id=seed_users[0].id, event_id=seed_event.id
    )
    db.add(msg)
    await db.commit()

    result = await db.execute(select(models.Message).filter_by(event_id=seed_event.id))
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.content == "Hello world"
    assert fetched.timestamp is not None


@pytest.mark.asyncio
async def test_threaded_message(db, seed_users, seed_event):
    parent = models.Message(
        content="Parent", user_id=seed_users[0].id, event_id=seed_event.id
    )
    db.add(parent)
    await db.flush()

    reply = models.Message(
        content="Reply",
        user_id=seed_users[1].id,
        event_id=seed_event.id,
        parent_id=parent.id,
    )
    db.add(reply)
    await db.commit()

    result = await db.execute(select(models.Message).filter_by(parent_id=parent.id))
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.content == "Reply"


# ── Cascade deletes ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deleting_user_cascades_communities(db, seed_users, seed_community):
    await db.delete(seed_users[0])
    await db.commit()

    result = await db.execute(select(models.Community).filter_by(id=seed_community.id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_deleting_community_cascades_events(db, seed_community, seed_event):
    await db.delete(seed_community)
    await db.commit()

    result = await db.execute(select(models.Event).filter_by(id=seed_event.id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_deleting_event_cascades_registrations(db, seed_users, seed_event):
    db.add(models.Registration(user_id=seed_users[1].id, event_id=seed_event.id))
    await db.commit()

    await db.delete(seed_event)
    await db.commit()

    result = await db.execute(
        select(models.Registration).filter_by(event_id=seed_event.id)
    )
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_deleting_event_cascades_messages(db, seed_users, seed_event):
    db.add(
        models.Message(
            content="will be deleted", user_id=seed_users[0].id, event_id=seed_event.id
        )
    )
    await db.commit()

    await db.delete(seed_event)
    await db.commit()

    result = await db.execute(select(models.Message).filter_by(event_id=seed_event.id))
    assert result.scalars().first() is None
