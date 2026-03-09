# REND37 Implementation Plan

This document defines every route needed per subsystem. Each route includes its HTTP method, path, purpose, and key implementation details. Use this as a checklist — tick off routes as they are built.

**Already implemented:** Auth registration, login, logout. Basic listing pages for communities and events.

---

## 1. Authentication (`routers/auth.py`)

Already done:

- [x] `GET /auth/register` — Render registration form
- [x] `POST /auth/register` — Handle registration (hash password, create user, set JWT cookie)
- [x] `GET /auth/login` — Render login form
- [x] `POST /auth/login` — Handle login (verify password, set JWT cookie)
- [x] `GET /auth/logout` — Clear JWT cookie, redirect to home

Still needed:

| Method | Path | Purpose | Details |
|--------|------|---------|---------|
| `GET` | `/auth/profile` | View own profile | Show username, email, joined communities, created events, registered events |
| `POST` | `/auth/profile` | Update profile | Change username, email, or profile image |
| `GET` | `/auth/profile/{user_id}` | View another user's public profile | Public info only — username, image, communities |

### Auth dependency (shared utility)

- Create a `get_current_user` dependency that reads the JWT cookie and returns the `User` or `None`. Inject this into any route that needs auth.
- Create a `require_current_user` dependency that raises 401 if not logged in. Use on all protected routes.

---

## 2. Communities (`routers/communities.py`)

Create this router file and register it in `main.py`.

| Method | Path | Purpose | Details |
|--------|------|---------|---------|
| `GET` | `/communities` | List all communities | Already exists in `main.py` — move here. Paginate results. Show search/filter bar. |
| `GET` | `/communities/create` | Render create-community form | **Protected.** Form with name and description fields. |
| `POST` | `/communities/create` | Handle community creation | **Protected.** Validate unique name, set `creator_id` to current user, insert into DB. Redirect to the new community page. |
| `GET` | `/communities/{community_id}` | View a single community | Show community details, list of its events, member count. Include "Create Event" button if user is the creator. |
| `GET` | `/communities/{community_id}/edit` | Render edit form | **Protected.** Only community creator can access. |
| `POST` | `/communities/{community_id}/edit` | Handle edit | **Protected.** Update name/description. Creator only. |
| `DELETE` | `/communities/{community_id}` | Delete community | **Protected.** Creator only. Cascade-delete associated events and registrations. Confirm via modal before executing. |

### Templates needed

- `community_detail.html` — single community view
- `community_form.html` — reusable create/edit form

---

## 3. Events (`routers/events.py`)

Create this router file and register it in `main.py`.

| Method | Path | Purpose | Details |
|--------|------|---------|---------|
| `GET` | `/events` | List all events | Already exists in `main.py` — move here. Support query params: `?category=`, `?community_id=`, `?search=`. Paginate. |
| `GET` | `/events/create` | Render create-event form | **Protected.** Include fields: title, description, category, location_name, lat, long (auto-fill from map picker), date_time, capacity_limit, community_id (dropdown of user's communities). |
| `POST` | `/events/create` | Handle event creation | **Protected.** Validate capacity > 0, date in future, lat/long valid. Set `organizer_id` to current user. |
| `GET` | `/events/{event_id}` | View a single event | Show full event details, map pin preview, attendee count vs capacity, registration button, discussion thread. |
| `GET` | `/events/{event_id}/edit` | Render edit form | **Protected.** Organizer only. |
| `POST` | `/events/{event_id}/edit` | Handle edit | **Protected.** Organizer only. |
| `DELETE` | `/events/{event_id}` | Delete event | **Protected.** Organizer only. Cascade-delete registrations and messages. |
| `POST` | `/events/{event_id}/register` | Register current user for event | **Protected.** Check capacity not exceeded. Create `Registration` row with status `confirmed`. Return HTMX partial updating the button to "Unregister". |
| `POST` | `/events/{event_id}/unregister` | Unregister current user | **Protected.** Delete `Registration` row. Return HTMX partial updating button back to "Register". |
| `GET` | `/events/{event_id}/attendees` | List attendees | HTMX partial. Show usernames/avatars of registered users. |
| `GET` | `/events/nearby` | Proximity search | Query params: `?lat=&long=&radius_km=`. Return events within radius using Haversine formula or bounding-box query. Return JSON for the map or an HTMX partial. |

### Templates needed

- `event_detail.html` — single event view with map preview, registration, and discussion
- `event_form.html` — create/edit form with map picker for lat/long
- `partials/event_card.html` — reusable card for event lists
- `partials/attendee_list.html` — HTMX partial for attendee list
- `partials/register_button.html` — HTMX partial for register/unregister toggle

---

## 4. Interactive Map (`routers/map.py`)

Create this router file and register it in `main.py`.

| Method | Path | Purpose | Details |
|--------|------|---------|---------|
| `GET` | `/map` | Render full-page map | Replace current placeholder. Load Leaflet.js, center on user's location (browser geolocation API) or default coords. On load, fetch pins via `/map/pins`. |
| `GET` | `/map/pins` | Return event pins as JSON | Query params: `?lat=&long=&radius_km=&category=`. Return JSON array: `[{id, title, category, lat, long, date_time, attendee_count}]`. Used by Leaflet to place markers. |
| `GET` | `/map/event-popup/{event_id}` | Return HTMX partial for map popup | When a user clicks a pin, load a small card with event title, date, attendee count, and a "View Event" link. Keeps the map page lightweight. |

### Frontend work (static/js/map.js)

- Initialize Leaflet map with tile layer (OpenStreetMap)
- On map load and on pan/zoom, call `/map/pins` with the current viewport bounds
- Place markers with click handlers that fetch `/map/event-popup/{id}` into a Leaflet popup
- Add category filter controls that re-fetch pins
- Add a "pick location" mode for event creation (emit lat/long back to event form)

### Templates needed

- Update `map.html` — full Leaflet map with filter controls
- `partials/map_popup.html` — small event card for pin popups

---

## 5. Discussions (`routers/discussions.py`)

Create this router file and register it in `main.py`.

| Method | Path | Purpose | Details |
|--------|------|---------|---------|
| `GET` | `/events/{event_id}/discussions` | Load discussion thread | **Protected — registered attendees only.** Return HTMX partial with all messages for this event, rendered as a threaded tree. Load into `event_detail.html`. |
| `POST` | `/events/{event_id}/discussions` | Post a new message | **Protected — registered attendees only.** Create `Message` row. Return HTMX partial appending the new message to the thread. |
| `DELETE` | `/events/{event_id}/discussions/{message_id}` | Delete a message | **Protected.** Only the message author or event organizer can delete. Return HTMX partial removing the message. |

### Access control

Create a dependency `require_event_attendee(event_id)` that checks:

1. User is logged in
2. A `Registration` row exists for this user + event with status `confirmed`

### Templates needed

- `partials/discussion_thread.html` — recursive template rendering message tree
- `partials/discussion_message.html` — single message with reply button
- `partials/discussion_form.html` — new message / reply form

---

## 6. HTMX Integration Notes

These are not separate routes but patterns to apply across all subsystems.

| Pattern | Where to use | How |
|---------|-------------|-----|
| Partial page swap | All list pages (communities, events) | Use `hx-get` with `hx-target="#content"` to swap only the main content area, not the full page. |
| Infinite scroll | Event list, community list | Add `hx-get="/events?page=2"` with `hx-trigger="revealed"` on a sentinel element at the bottom. |
| Inline forms | Registration button, discussion reply | Use `hx-post` + `hx-swap="outerHTML"` to replace the button/form with the result partial. |
| Search-as-you-type | Community/event search bars | Use `hx-get` with `hx-trigger="keyup changed delay:300ms"` to filter results live. |
| Confirm dialogs | Delete actions | Use `hx-confirm="Are you sure?"` attribute before destructive actions. |
| Loading indicators | All HTMX requests | Add `hx-indicator` pointing to a spinner element. |

---

## 7. Suggested Build Order

Build in this order to unblock teammates and get a working app incrementally:

1. **Auth dependency** — `get_current_user` / `require_current_user`. Everything depends on this.
2. **Communities CRUD** — Create, read, update, delete. This is the simplest full CRUD and sets the pattern.
3. **Events CRUD** — Build on communities. Include registration/unregistration.
4. **Interactive Map** — Depends on events existing with lat/long data. Wire up Leaflet + `/map/pins`.
5. **Discussions** — Depends on event registration (access control). Add `parent_id` to Message model, build threaded view.
6. **HTMX polish** — Convert full-page loads to partial swaps, add search-as-you-type, infinite scroll.
7. **Profile pages** — Lower priority, build last.

---

## 8. Summary: All New Routes at a Glance

```
AUTH
  GET    /auth/profile
  POST   /auth/profile
  GET    /auth/profile/{user_id}

COMMUNITIES
  GET    /communities                    (move from main.py)
  GET    /communities/create
  POST   /communities/create
  GET    /communities/{community_id}
  GET    /communities/{community_id}/edit
  POST   /communities/{community_id}/edit
  DELETE /communities/{community_id}

EVENTS
  GET    /events                         (move from main.py)
  GET    /events/create
  POST   /events/create
  GET    /events/{event_id}
  GET    /events/{event_id}/edit
  POST   /events/{event_id}/edit
  DELETE /events/{event_id}
  POST   /events/{event_id}/register
  POST   /events/{event_id}/unregister
  GET    /events/{event_id}/attendees
  GET    /events/nearby

MAP
  GET    /map                            (replace placeholder)
  GET    /map/pins
  GET    /map/event-popup/{event_id}

DISCUSSIONS
  GET    /events/{event_id}/discussions
  POST   /events/{event_id}/discussions
  DELETE /events/{event_id}/discussions/{message_id}
```
