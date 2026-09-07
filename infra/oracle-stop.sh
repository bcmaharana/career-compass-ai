#!/usr/bin/env bash
# oracle-stop.sh
#
# Linux counterpart to stop-prod.ps1, for the Oracle Cloud VM — stops
# the production stack via docker-compose.prod.yml + docker-compose.oracle.yml.
# This takes the live app offline for any real user reaching it through
# the Cloudflare Tunnel.
#
# Removes containers but named volumes (compass_postgres_prod_data,
# compass_minio_prod_data) are preserved - real data survives; the next
# oracle-start.sh run recreates the same database and object storage
# contents, just via fresh containers.
#
# Requires typed confirmation before doing anything, since this affects
# real users, not just a local dev environment. Pass --force to skip
# the prompt for scripted/non-interactive use.
#
# Usage:
#   cd ~/career-compass-ai
#   ./infra/oracle-stop.sh
#   ./infra/oracle-stop.sh --force

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_args=(-f "$root/infra/docker-compose.prod.yml" -f "$root/infra/docker-compose.oracle.yml")
force=false
if [ "${1:-}" = "--force" ]; then
    force=true
fi

echo "WARNING: this stops the PRODUCTION stack - the live app will go offline for real users until oracle-start.sh is run again." >&2

if [ "$force" != true ]; then
    read -r -p "Type 'yes' to continue: " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted - nothing was stopped."
        exit 0
    fi
fi

echo ""
echo "==> Stopping prod Docker services"
docker compose "${compose_args[@]}" down

echo ""
echo "==> Done"
echo "Prod stack stopped. Data volumes were preserved. Run ./infra/oracle-start.sh when ready to bring it back up."
