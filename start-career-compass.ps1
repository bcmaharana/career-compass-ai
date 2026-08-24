Write-Host "Starting Career Compass AI..." -ForegroundColor Green

$root = $PSScriptRoot

# -----------------------------
# Start Docker Compose services
# -----------------------------
Write-Host "Starting Docker services..."

Set-Location "$root\infra"

docker compose up -d

# -----------------------------
# Wait for PostgreSQL
# -----------------------------
Write-Host "Waiting for PostgreSQL..."

do {
    $status = docker inspect --format='{{.State.Health.Status}}' compass-postgres 2>$null
    Start-Sleep -Seconds 2
}
while ($status -ne "healthy")

Write-Host "PostgreSQL is ready."

# -----------------------------
# Run migrations
# -----------------------------
Write-Host "Running database migrations..."

Set-Location "$root\backend"

.\.venv\Scripts\activate

alembic upgrade head

# -----------------------------
# Start backend
# -----------------------------
Write-Host "Starting backend..."

Start-Process powershell `
    -ArgumentList "-NoExit", `
    "-Command", `
    "cd '$root\backend'; .\.venv\Scripts\activate; uvicorn app.main:app --reload" `
    -WindowStyle Minimized

# -----------------------------
# Start frontend
# -----------------------------
Write-Host "Starting frontend..."

Start-Process powershell `
    -ArgumentList "-NoExit", `
    "-Command", `
    "cd '$root\frontend'; npm run dev" `
    -WindowStyle Minimized

Write-Host "Career Compass AI started successfully." -ForegroundColor Green