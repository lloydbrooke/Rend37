"""
Standalone seed script.
Usage:  python seed.py

Drops all tables, recreates them, and inserts sample data.
All seed users have the password: password123
"""

import asyncio
from datetime import datetime, timedelta, UTC

from database import Base, engine, AsyncSessionLocal
import auth_utils
import models  # noqa: F401 — ensures all models are registered on Base.metadata


async def seed():
    # Drop and recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Tables dropped and recreated.")

    async with AsyncSessionLocal() as session:
        # ── Users ────────────────────────────────────────────────────
        users = [
            models.User(
                username="alice",
                email="alice@example.com",
                hashed_password=auth_utils.hash_password("password123"),
            ),
            models.User(
                username="bob",
                email="bob@example.com",
                hashed_password=auth_utils.hash_password("password123"),
            ),
            models.User(
                username="charlie",
                email="charlie@example.com",
                hashed_password=auth_utils.hash_password("password123"),
            ),
            models.User(
                username="diana",
                email="diana@example.com",
                hashed_password=auth_utils.hash_password("password123"),
            ),
        ]
        session.add_all(users)
        await session.flush()

        # ── Communities ──────────────────────────────────────────────
        communities = [
            models.Community(
                name="Liverpool Tech Meetups",
                description="Weekly talks and workshops for developers in Liverpool.",
                creator_id=users[0].id,
            ),
            models.Community(
                name="Campus Running Club",
                description="Casual runs around Sefton Park and the waterfront. All levels welcome.",
                creator_id=users[1].id,
            ),
            models.Community(
                name="Board Game Nights",
                description="Strategy games, party games, and everything in between.",
                creator_id=users[2].id,
            ),
            models.Community(
                name="Photography Walks",
                description="Explore the city with your camera. Monthly themed photo walks.",
                creator_id=users[3].id,
            ),
        ]
        session.add_all(communities)
        await session.flush()

        # ── Events ───────────────────────────────────────────────────
        now = datetime.now(UTC)
        events = [
            models.Event(
                title="Intro to FastAPI",
                description="Hands-on workshop building a REST API with FastAPI and SQLAlchemy.",
                category="Workshop",
                latitude=53.4084,
                longitude=-2.9916,
                location_name="Liverpool Central Library",
                date_time=now + timedelta(days=7),
                capacity_limit=30,
                community_id=communities[0].id,
                organizer_id=users[0].id,
            ),
            models.Event(
                title="Hack Night: Open Source",
                description="Bring your laptop and contribute to open-source projects together.",
                category="Social",
                latitude=53.4054,
                longitude=-2.9668,
                location_name="Baltic Triangle Co-working",
                date_time=now + timedelta(days=14),
                capacity_limit=20,
                community_id=communities[0].id,
                organizer_id=users[0].id,
            ),
            models.Event(
                title="Sefton Park 5K",
                description="Easy-paced 5K loop around Sefton Park. Meet at the Palm House.",
                category="Sports",
                latitude=53.3838,
                longitude=-2.9456,
                location_name="Sefton Park Palm House",
                date_time=now + timedelta(days=3),
                capacity_limit=50,
                community_id=communities[1].id,
                organizer_id=users[1].id,
            ),
            models.Event(
                title="Waterfront Interval Training",
                description="Sprint intervals along the Mersey waterfront. Intermediate level.",
                category="Sports",
                latitude=53.4001,
                longitude=-2.9946,
                location_name="Albert Dock",
                date_time=now + timedelta(days=10),
                capacity_limit=25,
                community_id=communities[1].id,
                organizer_id=users[1].id,
            ),
            models.Event(
                title="Catan Tournament",
                description="Single-elimination Settlers of Catan bracket. Prizes for top 3.",
                category="Gaming",
                latitude=53.4065,
                longitude=-2.9811,
                location_name="Student Guild Common Room",
                date_time=now + timedelta(days=5),
                capacity_limit=16,
                community_id=communities[2].id,
                organizer_id=users[2].id,
            ),
            models.Event(
                title="Golden Hour at the Docks",
                description="Sunset photography session at the Royal Albert Dock.",
                category="Arts",
                latitude=53.3997,
                longitude=-2.9934,
                location_name="Royal Albert Dock",
                date_time=now + timedelta(days=6),
                capacity_limit=None,
                community_id=communities[3].id,
                organizer_id=users[3].id,
            ),
        ]
        session.add_all(events)
        await session.flush()

        # ── Community Memberships ───────────────────────────────────
        memberships = [
            models.CommunityMember(
                user_id=users[0].id, community_id=communities[1].id
            ),  # alice joins Running Club
            models.CommunityMember(
                user_id=users[0].id, community_id=communities[2].id
            ),  # alice joins Board Games
            models.CommunityMember(
                user_id=users[1].id, community_id=communities[0].id
            ),  # bob joins Tech Meetups
            models.CommunityMember(
                user_id=users[1].id, community_id=communities[3].id
            ),  # bob joins Photography
            models.CommunityMember(
                user_id=users[2].id, community_id=communities[0].id
            ),  # charlie joins Tech Meetups
            models.CommunityMember(
                user_id=users[2].id, community_id=communities[1].id
            ),  # charlie joins Running Club
            models.CommunityMember(
                user_id=users[3].id, community_id=communities[0].id
            ),  # diana joins Tech Meetups
            models.CommunityMember(
                user_id=users[3].id, community_id=communities[2].id
            ),  # diana joins Board Games
        ]
        session.add_all(memberships)
        await session.flush()

        # ── Registrations ────────────────────────────────────────────
        registrations = [
            models.Registration(
                user_id=users[0].id, event_id=events[2].id, status="registered"
            ),
            models.Registration(
                user_id=users[0].id, event_id=events[4].id, status="registered"
            ),
            models.Registration(
                user_id=users[1].id, event_id=events[0].id, status="registered"
            ),
            models.Registration(
                user_id=users[1].id, event_id=events[5].id, status="registered"
            ),
            models.Registration(
                user_id=users[2].id, event_id=events[1].id, status="registered"
            ),
            models.Registration(
                user_id=users[2].id, event_id=events[3].id, status="registered"
            ),
            models.Registration(
                user_id=users[3].id, event_id=events[0].id, status="registered"
            ),
            models.Registration(
                user_id=users[3].id, event_id=events[4].id, status="registered"
            ),
        ]
        session.add_all(registrations)
        await session.flush()

        # ── Discussion messages ──────────────────────────────────────
        msg1 = models.Message(
            content="Should I install Python 3.12 or is 3.11 fine?",
            user_id=users[1].id,
            event_id=events[0].id,
        )
        session.add(msg1)
        await session.flush()

        msg2 = models.Message(
            content="Either works! We'll be using 3.11+ features.",
            user_id=users[0].id,
            event_id=events[0].id,
            parent_id=msg1.id,
        )

        msg3 = models.Message(
            content="Are expansions included or just the base game?",
            user_id=users[3].id,
            event_id=events[4].id,
        )
        session.add_all([msg2, msg3])
        await session.flush()

        msg4 = models.Message(
            content="Base game only for the tournament. We might do a Cities & Knights casual game after.",
            user_id=users[2].id,
            event_id=events[4].id,
            parent_id=msg3.id,
        )
        session.add(msg4)

        await session.commit()
        print("Database seeded successfully.")
        print(
            "  4 users  |  4 communities  |  8 memberships  |  6 events  |  8 registrations  |  4 messages"
        )
        print("  All users have password: password123")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
