# export-prod-data.ps1
#
# Run on THIS laptop, against the currently-running prod containers
# (compass-postgres-prod, compass-minio-prod), to produce a self-contained
# bundle for transfer to the Oracle VM: a full Postgres dump, a tarball
# of MinIO's real object data (both buckets), the Firebase service-account
# key, and the two production env files (backend/.env.production,
# infra/.env) - so the Oracle VM starts with the exact same real secrets
# rather than needing them hand-retyped.
#
# Does NOT stop or modify the running prod stack on this laptop - purely
# read-only against it. Safe to run while career.scaledbrain.com is still
# being served from here.
#
# Output goes to migration-export/<timestamp>/ (gitignored - never
# committed). This bundle contains real user data and real secrets -
# after a verified successful import on the Oracle VM (see
# migration/import-prod-data.sh), delete the local copy and the copy
# transferred to the VM's home directory; don't leave either lying
# around longer than the migration itself takes.
#
# Usage:
#   cd C:\Users\bcmah\workspace\enterprise\career-compass-ai
#   .\migration\export-prod-data.ps1

$ErrorActionPreference = "Stop"
$root = "$PSScriptRoot\.."
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = "$root\migration-export\$timestamp"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Step "Checking prod containers are running"
$pgStatus = docker inspect -f '{{.State.Status}}' compass-postgres-prod 2>$null
$minioStatus = docker inspect -f '{{.State.Status}}' compass-minio-prod 2>$null
if ($pgStatus -ne "running" -or $minioStatus -ne "running") {
    Write-Host "compass-postgres-prod / compass-minio-prod are not both running - start prod first (.\start-prod.ps1)" -ForegroundColor Red
    exit 1
}

Write-Step "Dumping Postgres (custom format, includes schema + data + alembic_version)"
docker exec compass-postgres-prod pg_dump -U compass -Fc -d career_compass -f /tmp/career_compass.dump
if ($LASTEXITCODE -ne 0) { Write-Host "pg_dump failed" -ForegroundColor Red; exit 1 }
docker cp compass-postgres-prod:/tmp/career_compass.dump "$outDir\career_compass.dump"
docker exec compass-postgres-prod rm /tmp/career_compass.dump
Write-Host "Wrote $outDir\career_compass.dump"

Write-Step "Archiving MinIO object data (both buckets, via a throwaway container against the real volume)"
docker run --rm `
    -v career-compass-prod_compass_minio_prod_data:/data:ro `
    -v "${outDir}:/backup" `
    alpine sh -c "tar czf /backup/minio-data.tar.gz -C /data ."
if ($LASTEXITCODE -ne 0) { Write-Host "MinIO archive failed" -ForegroundColor Red; exit 1 }
Write-Host "Wrote $outDir\minio-data.tar.gz"

Write-Step "Copying secrets and env files"
Copy-Item "$root\backend\secrets\firebase-service-account.json" "$outDir\firebase-service-account.json"
Copy-Item "$root\backend\.env.production" "$outDir\backend.env.production"
Copy-Item "$root\infra\.env" "$outDir\infra.env"
Write-Host "Copied firebase-service-account.json, backend.env.production, infra.env"

Write-Step "Done"
$sizeMb = [math]::Round(((Get-ChildItem $outDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
Write-Host "Bundle ready at $outDir ($sizeMb MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Next: transfer it to the Oracle VM, e.g.:" -ForegroundColor Yellow
Write-Host "  scp -i <path-to-your-private-key> -r `"$outDir`" ubuntu@<oracle-vm-public-ip>:~/migration-import"
Write-Host ""
Write-Host "Then on the VM, inside the repo checkout: ./migration/import-prod-data.sh ~/migration-import"
Write-Host ""
Write-Host "This bundle contains real user data and real secrets (DB password, JWT secret, API keys)." -ForegroundColor Yellow
Write-Host "Delete $outDir and its copy on the VM once the import is verified working." -ForegroundColor Yellow
