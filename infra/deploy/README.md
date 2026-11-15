# CropPilot CI/CD on the shared NGINX VPS

The production checkout is `/home/ubuntu/crop-pilot`, on `main`. It follows the
same in-place Git + Docker Compose deployment model as Universident. There are
no release directories, privileged receiver, automatic backups, or automatic
rollback scripts. Recovery is a reviewed Git revert followed by a successful
main deployment. A Git revert does not undo database migrations or changed data.

## Account and configuration

The dedicated `croppilot-deploy` account can traverse `/home/ubuntu`, update this
checkout and `.git`, read its ignored `.env`, and run Docker through membership
in the `docker` group. File ACLs grant access to this project, following the
existing Universident pattern. `ubuntu` remains the administrative account.
Docker group membership grants broad host privileges; separate accounts provide
operational organization, not strong isolation between mutually untrusted apps.

The CI key is dedicated to this project. Its authorized key has `restrict` to
disable forwarding and PTY allocation while allowing the deployment shell.
Application credentials remain in `/home/ubuntu/crop-pilot/.env`; never put them
in GitHub or Git. The checkout uses the public HTTPS repository URL for fetches,
so there is no additional GitHub private key on the VPS.

GitHub's `production` environment allows only the branch `main`, not tags.
Environment secrets: `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS` (verified server host key).
Environment variables: `VPS_HOST`, `VPS_USER=croppilot-deploy`, `VPS_PORT=22`,
`VPS_PATH=/home/ubuntu/crop-pilot`.

Set the repository variable `VPS_DEPLOY_ENABLED=true` only after initial server
provisioning and verification. `false` disables automatic deployments without
disabling CI. A manual workflow on `main` offers `verify` (default) or `deploy`.
Both automatic and manual deployment require `github.actor` and
`github.triggering_actor` to equal `bravomihai`. Reruns by others cannot deploy.
The existing main rules require PRs and restrict merges to the repository admin.

## What Actions does

1. Run existing contract, web, Python, database, ingress and Docker build checks.
2. Connect only after CI succeeds, using the production environment and strict
   SSH host verification. PR jobs receive no deployment credentials.
3. Acquire `.git/croppilot-deploy.lock`; require a clean main checkout and ignored
   server `.env`. Fetch main and require its tip to equal the exact tested SHA.
4. Fast-forward the checkout, retaining server settings. Build migration, engine
   and web images. Run only `prisma migrate status` against production.
5. Stop if migrations are pending/failed. Otherwise update engine, web, gateway
   and cache maintenance, leaving PostgreSQL in place. Check running images,
   container health, computed-engine connectivity, and the SHA over public HTTPS.

The host's NGINX handles HTTPS for `crop-pilot.nemes.engineer` and forwards to the
container gateway on `127.0.0.1:18080`. PostgreSQL, engine and web ports are not
published. Use `compose.yaml` + `infra/compose.vps.yaml`; do not add the standalone
Caddy override `infra/compose.production.yaml` on this server. Certbot's existing
renewal timer manages the hostname's certificate.

## Initial provisioning and migrations (administrator only)

Provision the checkout, ignored `.env`, account permissions, host NGINX and
certificate once before enabling automatic deployments. First bring PostgreSQL
up, build the application images, review/apply the initial cache migration, then
start the other services. Normal Actions deployments refuse to bootstrap a new
database and never apply production migrations.

For a reviewed future migration, confirm the exact checkout and database first,
take/verify an appropriate backup, and acquire the same deployment lock:

```sh
cd /home/ubuntu/crop-pilot
export DEPLOYMENT_SHA="$(git rev-parse HEAD)"
(
  flock --exclusive --wait 60 9 || exit 1
  docker compose --project-name croppilot --env-file .env \
    -f compose.yaml -f infra/compose.vps.yaml run --rm --no-deps migrate \
    pnpm db:deploy
) 9> .git/croppilot-deploy.lock
```

Run this as the Docker-enabled deployment account or through the administrator's
sudo access. Review old/new application compatibility before applying schema
changes. Never run `db push`, reset the database, or delete production volumes.

## Inspect and recover

```sh
cd /home/ubuntu/crop-pilot
git rev-parse HEAD
docker compose --project-name croppilot --env-file .env \
  -f compose.yaml -f infra/compose.vps.yaml ps
curl --fail https://crop-pilot.nemes.engineer/api/health
curl --fail https://crop-pilot.nemes.engineer/api/engine/status
```

If a build or migration check fails, existing services remain, while the checkout
and local image tags may have advanced. A service-update failure can leave some
services replaced; inspect the failed stage rather than rerunning blindly. Revert
the faulty application change through a PR, merge as `bravomihai`, and let CI/CD
build/deploy the correction. Database and server configuration recovery is manual.

This is a single-server replacement with possible brief interruptions. Maintain
off-server backups and monitor disk space. Cleanup is a separate administrative
task; the workflow performs no global Docker pruning or volume deletion.

An OpenAI key is optional. Add it only to the server `.env` to enable real AI
summaries; calculations remain available without it. Runtime-only configuration
changes require recreating affected services with the same Compose arguments.
