# FieldShift infrastructure

- `compose.yaml`: local PostgreSQL, migration, web, engine, NGINX gateway, and cache maintenance.
- `nginx.conf`: request/body limits and protection of the internal API from public access.
- `cache-maintenance.py`: authenticated periodic cleanup of expired public data.
- `Caddyfile` + `compose.production.yaml`: HTTPS profile without direct service ports.
- `aws/host.yaml`, `aws/configure.py`, `aws/README.md`: prepared EC2 infrastructure and
  secret loading; no AWS resources have been created.
- `.github/workflows/checks.yml`: checks prepared for pushes/PRs.
  `ci/checks.yml.example` is the reference copy; the workflow has not yet run on GitHub.

## Local verification

With Node available in the shell and dependencies installed, start the local configuration:

```sh
docker compose up -d --build --wait
pnpm test:cache
services/engine/.venv/bin/python infra/check-local.py
```

The integration script uses localhost only. It checks the demo engine, live geocoding,
cache, and gateway limits; it temporarily stops only this project's PostgreSQL and
recreates the engine in `computed` mode, then restores the database and `demo` mode.
Do not run it against a shared deployment. It does not delete volumes or active data.
Migration runs automatically as a separate Compose service. Local configuration is ignored by Git.

The application with public-request limits is at `http://localhost:8080`; the direct
development port is 3000. The database and engine bind only to loopback in the local
profile. For production, use the [AWS guide](aws/README.md), which removes these ports.

The cache stores public data only. Farmer forms, entered history, and recommendations
are not persisted. No SMS/WhatsApp messages are sent.

Primary configuration references: [NGINX](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html),
[Compose](https://docs.docker.com/reference/compose-file/merge/),
[node-postgres](https://node-postgres.com/apis/client),
[Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
