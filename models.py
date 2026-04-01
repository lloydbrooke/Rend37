from __future__ import annotations
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) 
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False) 
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False) 
    image_url: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    owned_communities: Mapped[List[Community]] = relationship(back_populates='creator', cascade="all, delete-orphan")
    created_events: Mapped[List[Event]] = relationship(back_populates='organizer', cascade="all, delete-orphan")
    community_memberships: Mapped[List[CommunityMember]] = relationship(back_populates='user', cascade="all, delete-orphan")
    registrations: Mapped[List[Registration]] = relationship(back_populates='user')
    messages: Mapped[List[Message]] = relationship(back_populates='author')

class Community(Base):
    __tablename__ = 'communities'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False) 
    description: Mapped[str] = mapped_column(Text, nullable=False) 
    creator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    # Relationships
    creator: Mapped[User] = relationship(back_populates='owned_communities')
    events: Mapped[List[Event]] = relationship(back_populates='community', cascade="all, delete-orphan")
    members: Mapped[List[CommunityMember]] = relationship(back_populates='community', cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False) 
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True) 
    
    # Proximity/Location Data
    latitude: Mapped[float] = mapped_column(Float, nullable=False) 
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)

    date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False) 
    capacity_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    community_id: Mapped[int] = mapped_column(ForeignKey('communities.id'), nullable=False)
    organizer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

    # Relationships
    community: Mapped[Community] = relationship(back_populates='events')
    organizer: Mapped[User] = relationship(back_populates='created_events')
    attendees: Mapped[List[Registration]] = relationship(back_populates='event', cascade="all, delete-orphan") 
    discussion_posts: Mapped[List[Message]] = relationship(back_populates='event', cascade="all, delete-orphan") 

class CommunityMember(Base):
    """Association table linking Users to Communities they have joined"""
    __tablename__ = 'community_members'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey('communities.id'), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    user: Mapped[User] = relationship(back_populates='community_memberships')
    community: Mapped[Community] = relationship(back_populates='members')

class Registration(Base):
    """Association table linking Users to Events with status tracking"""
    __tablename__ = 'registrations'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="registered") # e.g., registered, attended 
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    user: Mapped[User] = relationship(back_populates='registrations')
    event: Mapped[Event] = relationship(back_populates='attendees')

class Message(Base):
    """Live discussion threads for events"""
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey('messages.id'), nullable=True)

    # Relationships
    author: Mapped[User] = relationship(back_populates='messages')
    event: Mapped[Event] = relationship(back_populates='discussion_posts')
    replies: Mapped[List["Message"]] = relationship("Message", back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped[Optional["Message"]] = relationship("Message", back_populates="replies", remote_side=[id])