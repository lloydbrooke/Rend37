# REND37

REND37 is a map-based web application designed to foster sustained community interaction by linking event participation to structured social contexts.

## 🚀 Getting Started (Local Setup)

### 1. Clone the repository

```bash
#create a folder for your project navigate to it in a terminal an run the following
git clone https://github.com/ItsTachie/COMP208.git
cd COMP208
```

### 2. Python Environment Setup

```bash
# Create the virtual environment
python -m venv venv

# Activate the environment
# On Windows:
venv\Scripts\.\activate
# On macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Frontend & Tailwind CSS Setup

You must have [Node.js](https://nodejs.org/en/download) installed on your machine.

```bash
# Install Node dependencies (Tailwind CLI)
npm install

# Start the Tailwind compiler in a separate terminal
# This watches main.css and generates dist.css
# Do this in a seperate terminal
npx @tailwindcss/cli -i ./static/css/main.css -o ./static/css/dist.css --watch
```

### 4. Database Initialization

We'll use **SQLite** for local development.

- The database file will be automatically generated as `rend37.db`  upon first run.
- Ensure you do **not** commit the `.db` file to GitHub.

#### Seeding the Database

To populate the database with sample data for development, run:

```bash
python seed.py
```

This will **wipe all existing data**, recreate every table, and insert:
- 4 users (`alice`, `bob`, `charlie`, `diana` — all with password `password123`)
- 4 communities
- 6 events (with real Liverpool coordinates)
- 8 event registrations
- 4 threaded discussion messages

Run it whenever you want a clean slate with fresh test data.

### 5. Running the Application

```bash
# Start the FastAPI server in development mode
fastapi dev main.py
```

- The server will be available at: `http://127.0.0.1:8000`
- API Documentation (Swagger UI) is at: `http://127.0.0.1:8000/docs`

---

## Project Structure

To allow concurrent development of vertical features, we use a modular layout:

- **main.py**: The application entry point where all `APIRouters` are registered.
- **routers/**: Contains separate files for `auth.py`, `events.py`, `communities.py`, `discussions.py`, and `map.py`.
- **models.py**: Centralized SQLAlchemy models defining our data schema.
- **templates/**: Jinja2 HTML files. We use **HTMX** for partial page updates to reduce client-side latency.
- **static/**: CSS, JavaScript (Leaflet for maps), and uploaded media.
- **tests/**: Pytest unit tests for each subsystem.

---

## Running Tests

Tests use an **in-memory SQLite database** so they never touch your real `rend37.db`.

```bash
# Run all tests
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_auth.py -v

# Run tests matching a keyword
python -m pytest -k "login" -v
```

---

## Git Workflow (Feature-Branch)

We use a feature-branch workflow for version control.

### 1. Synchronize

Always start your work by pulling the latest changes from the main repository.

```bash
git pull
```

### 2. Create a Branch

Create a new branch for every task or feature. Use descriptive names (e.g., `feature/map-pins` or `bugfix/auth-login`).

```bash
git checkout -b feature/your-feature-name
```

### 3. Develop & Commit

Commit your work frequently. This makes it easier to track changes and roll back if necessary.

```bash
git add .
git commit -m "Add logic for proximity-based event querying"
```

### 4. Rebase from Main

While you're working on your branch, other team members may merge their PRs into `main`. If that happens, your branch will be **behind** `main` and may have conflicts. Rebasing brings your branch up to date by replaying your commits on top of the latest `main`, giving you a clean, linear history.

```bash
# Make sure you've committed or stashed your current work first
git fetch origin
git rebase origin/main
```

If there are **merge conflicts**, Git will pause and ask you to resolve them:

1. Open the conflicting files and fix the conflicts (look for `<<<<<<<`, `=======`, `>>>>>>>` markers).
2. Stage the resolved files: `git add <file>`
3. Continue the rebase: `git rebase --continue`
4. If things go wrong and you want to start over: `git rebase --abort`

**When should you rebase?**

- Before pushing your branch or opening a PR — this ensures your branch merges cleanly.
- When you see that `main` has new commits that affect files you're also working on.
- If your PR shows merge conflicts on GitHub.

### 5. Push & Pull Request (PR)

When your feature is complete and tested:

1. Push your branch: `git push origin feature/your-feature-name`
   - If you've rebased, you may need to force-push: `git push origin feature/your-feature-name --force-with-lease`
2. Go to GitHub and open a **Pull Request**.
3. Tag at least one team member to review your code. **Do not merge your own PR.*

---

### Implementation guide for subsystems

| Subsystem           | Developer Tasks & Requirements                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Authentication**  | Implement `User` registration using FastAPI/Supabase logic. Ensure only authenticated users can access group/event creation.<br><br>       |
| **Communities**     | Build the CRUD for `Community`. Develop views to list communities and their associated events.<br><br>                                     |
| **Events**          | Manage `Event` creation with lat/long indexing for proximity searches. Handle `Registration` logic and capacity checks.<br><br>            |
| **Interactive Map** | Use Leaflet to render `Event` pins based on `latitude` and `longitude`. Implement proximity querying.<br><br>                              |
| **Discussions**     | Create a reddit like disscussion tree with data from `Message` table. **Critical:** Restrict read/write access to registered attendees.<br><br> |
| **UI/UX (HTMX)**    | Manage `Jinja2` templates and `HTMX` partial updates to ensure a "thin-client" experience on lower-end devices.<br><br>                    |
