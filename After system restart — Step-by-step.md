After system restart — Step-by-step
# Step 1 — Start Docker Desktop

Open:

## Docker Desktop

Wait until Docker Desktop shows it is running.

Verify:
### docker ps

At this point, you may see no Career Compass containers yet.

# Step 2 — Start Career Compass infrastructure

Open PowerShell: 
# cd C:\Users\bcmah\workspace\career-compass-ai\infra

Start containers:
## docker compose up -d

Verify:
## docker ps

Expected:

compass-postgres   Up (healthy)
compass-redis      Up (healthy)
compass-minio      Up (healthy)

If you want to confirm PostgreSQL:

### docker exec compass-postgres pg_isready -U compass -d career_compass

Expected:

accepting connections

# Step 3 — Start backend

Open another PowerShell window:

## cd C:\Users\bcmah\workspace\career-compass-ai\backend

Activate virtual environment:

## .venv\Scripts\activate

Run migrations:

## alembic upgrade head

Seed defaults:

## python scripts\seed_platform_defaults.py

Start API:

## uvicorn app.main:app --reload

You should get something like:

Uvicorn running on http://127.0.0.1:8000

# Step 4 — Start frontend

Open another PowerShell window:

## cd C:\Users\bcmah\workspace\career-compass-ai\frontend

Start:

## npm run dev
Things you no longer need to do every restart

Do not run:

pip install -e ".[dev]"

unless dependencies changed.

Do not run:

npm install

unless package.json changed.

Do not run:

copy .env.example .env.local

unless you are creating the environment file for the first time.

Optional improvement later

Once you confirm this works after a reboot, we can create a simple start-career-compass.ps1 script that:

Starts Docker Compose
Waits for PostgreSQL health
Runs Alembic migration
Starts backend
Opens frontend

Then your daily startup becomes one command instead of several.

For now, after reboot, follow the four steps above. The critical change from before is:

Start Docker stack first → then run Alembic.