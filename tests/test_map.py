"""
Tests for map routes (routers/map.py).

Covers plan.md section 4: map page, pins JSON, event popups.
"""

import pytest
import json


# ── Map page ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_page_renders(client):
    resp = await client.get("/map")
    assert resp.status_code == 200


# ── Pins endpoint ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_pins_returns_json(client, seed_event):
    resp = await client.get("/map/pins", params={
        "lat": 53.4084,
        "long": -2.9916,
        "radius_km": 50,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_map_pins_contain_required_fields(client, seed_event):
    resp = await client.get("/map/pins", params={
        "lat": 53.4084, "long": -2.9916, "radius_km": 50,
    })
    data = resp.json()
    pin = data[0]
    for field in ("id", "title", "lat", "long"):
        assert field in pin, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_map_pins_filter_by_category(client, seed_event):
    resp = await client.get("/map/pins", params={
        "lat": 53.4084, "long": -2.9916, "radius_km": 50,
        "category": "Social",
    })
    assert resp.status_code == 200
    data = resp.json()
    for pin in data:
        assert pin["category"] == "Social"


@pytest.mark.asyncio
async def test_map_pins_empty_area(client, seed_event):
    """No events near the South Pole."""
    resp = await client.get("/map/pins", params={
        "lat": -89.0, "long": 0.0, "radius_km": 10,
    })
    assert resp.status_code == 200
    assert resp.json() == []


# ── Event popup ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_event_popup(client, seed_event):
    resp = await client.get(f"/map/event-popup/{seed_event.id}")
    assert resp.status_code == 200
    assert "Test Event" in resp.text


@pytest.mark.asyncio
async def test_map_event_popup_not_found(client):
    resp = await client.get("/map/event-popup/9999")
    assert resp.status_code == 404
