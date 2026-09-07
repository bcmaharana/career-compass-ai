# Runbook: Migrating Prod from this Laptop to Oracle Cloud (Always Free)

Moves `career.scaledbrain.com` from this laptop's Docker Compose stack
+ Cloudflare Tunnel to a permanent, free Oracle Cloud VM
(`VM.Standard.A1.Flex`, 2 OCPUs / 12 GB RAM — Oracle's Always Free
allocation), with zero hosting cost and no dependency on this laptop
being powered on. Does not touch dev, and does not touch the sibling
Platform Identity service (`scaledbrain.com`), which stays on this
laptop for now — see "Scope" below.

## Scope

- **In scope**: `career-compass-ai`'s production stack (Postgres, Redis,
  MinIO, backend, frontend/nginx) and its own Cloudflare Tunnel
  ingress for `career.scaledbrain.com`.
- **Out of scope**: the `enterprise/platform` repo's own prod stack
  (`scaledbrain.com`) — it keeps running on this laptop, reached via
  the laptop's existing tunnel. `PLATFORM_IDENTITY_BASE_URL` in
  `backend/.env.production` already points at the public
  `https://scaledbrain.com` URL, not a local address, so this app
  reaching it works identically regardless of which machine either
  service runs on.
- **Not yet decided**: whether the Platform Identity service moves off
  this laptop too, later. Independent decision, not part of this
  migration.

## Prerequisites

- An Oracle Cloud Always Free account with a running `VM.Standard.A1.Flex`
  instance (2 OCPU / 12 GB), Ubuntu 24.04, Docker installed, reachable
  via SSH — see the provisioning walkthrough (chat history / this
  file's companion conversation) for the OCI Console steps.
- This repo cloned (or otherwise copied) onto that VM at
  `~/career-compass-ai`.
- `infra/docker-compose.oracle.yml` present (resource-limit overlay,
  already in this repo).

## Step 1 — Verify ARM64 image compatibility (on the VM)

```bash
docker manifest inspect pgvector/pgvector:pg16 | grep -A2 arm64
```

If no `arm64` entry appears, stop here and swap `infra/docker-compose.prod.yml`'s
`postgres` image to `postgres:16` + install the `pgvector` extension via
apt/build before continuing — everything else in this runbook assumes
`pgvector/pgvector:pg16` works as-is.

## Step 2 — Export real data (on this laptop, prod stays running)

```powershell
cd C:\Users\bcmah\workspace\enterprise\career-compass-ai
.\migration\export-prod-data.ps1
```

Produces `migration-export\<timestamp>\` (gitignored) containing a full
Postgres dump, a MinIO object-data tarball, the Firebase service-account
key, and both production env files. Read-only against the running prod
containers — does not stop or affect the live site.

Transfer the bundle to the VM (path/IP from your own provisioning):

```powershell
scp -i <path-to-private-key> -r "migration-export\<timestamp>" ubuntu@<oracle-vm-ip>:~/migration-import
```

## Step 3 — Import real data (on the Oracle VM)

```bash
cd ~/career-compass-ai
chmod +x infra/*.sh migration/*.sh   # scp doesn't reliably preserve the executable bit from Windows
./migration/import-prod-data.sh ~/migration-import
```

Restores Postgres (schema + real data + `alembic_version` — the dump
already reflects whatever migration state prod was at, so this doubles
as the migration step) and MinIO's real object data, and places the
real secrets/env files (`backend/.env.production`, `infra/.env`,
`backend/secrets/firebase-service-account.json`) — no values need
retyping, they're carried over from the export bundle exactly as they
are in prod today, including `AI_DEFAULT_MODEL=openai/gpt-oss-120b`
(Groq, cloud-hosted) staying the default with no change needed.

## Step 4 — Bring up the full stack (on the Oracle VM)

```bash
./infra/oracle-start.sh
```

Builds and starts all five containers under the resource-limited
overlay, applies migrations (no-op — the restored dump is already
current), reseeds platform defaults (idempotent — also applies the
`qwen2.5:7b`/`qwen2.5:3b` production sunset from
`scripts/seed_platform_defaults.py`'s `RETIRED_MODELS_IN_PRODUCTION`),
and waits for the frontend to accept connections on `127.0.0.1:8080`.

Sanity check before touching DNS:

```bash
curl -I http://127.0.0.1:8080
```

## Step 5 — Set up the Oracle VM's own Cloudflare Tunnel

```bash
./infra/setup-cloudflared-oracle.sh
```

Creates a **new, separate** tunnel (`career-compass-oracle`) dedicated
to `career.scaledbrain.com` — not a second replica of the laptop's
existing tunnel, which also serves `scaledbrain.com` and shouldn't be
touched. Installs cloudflared as a systemd service (`enable`d, survives
reboot on its own — no Windows lid-close/scheduled-task workaround
needed here). Stops short of the actual DNS cutover, printing the exact
command for Step 6.

## Step 6 — Cut over DNS (real traffic moves the moment this runs)

```bash
cloudflared tunnel route dns career-compass-oracle career.scaledbrain.com
```

This overwrites the `career.scaledbrain.com` DNS record to point at the
Oracle VM's tunnel instead of the laptop's. Verify from an outside
network (phone on cellular, not this laptop's own wifi) that
`https://career.scaledbrain.com` now serves real, correct data from the
new VM before moving on.

## Step 7 — Decide Ollama's fate on the VM

`qwen2.5:7b`/`qwen2.5:3b` are already sunset in prod as of Step 4's
reseed — hidden from Settings > AI Model, any existing user preference
for either silently falls back to the platform default (Groq). No
Ollama installation is required on the Oracle VM for the app to work
correctly. If you want them selectable again later anyway, install
Ollama directly on the VM (not containerized, same
`OLLAMA_BASE_URL=http://host.docker.internal:11434` pattern as today)
and flip their `model_versions.status` back to `active` — understand
it'll be slow on 2 shared ARM cores with no GPU.

## Step 8 — Cleanup

- Delete the migration bundle on both machines:
  ```bash
  rm -rf ~/migration-import   # on the VM
  ```
  ```powershell
  Remove-Item -Recurse -Force "migration-export\<timestamp>"   # on the laptop
  ```
- Keep the laptop's prod stack running (untouched, real data frozen at
  export time) as a cold rollback for a few days — if `career.scaledbrain.com`
  needs to move back, re-point DNS at the laptop's original tunnel.
- Once confident, on the laptop: remove `career.scaledbrain.com` from
  `~/.cloudflared/config.yml`'s ingress rules (leave `scaledbrain.com`
  intact), stop the prod stack (`.\stop-prod.ps1`), and retire the
  `CareerCompassProdStart` scheduled task — `CareerCompassDevStart` and
  `CloudflaredTunnel` (still needed for `scaledbrain.com`) stay.

## Rollback

At any point before Step 6, rolling back is free — nothing on the
laptop was ever stopped or modified. After Step 6, rolling back means
re-running `cloudflared tunnel route dns <laptop's-tunnel-name>
career.scaledbrain.com` to point DNS back, since the laptop's stack was
never taken down.
