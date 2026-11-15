# CropPilot infrastructure

The app runs on a Linux VPS with Docker Compose. AWS provisioning and secret-loading
scripts have been removed.

- `compose.yaml`: PostgreSQL cache, migration, engine, web, request gateway, cache cleanup.
- `nginx.conf`: public request limits; blocks public access to the internal cache API.
- `Caddyfile` + `compose.production.yaml`: standalone-server HTTPS.
- `compose.vps.yaml` + `nginx.vps.conf`: shared VPS with an existing host NGINX.
- `deploy/README.md`: GitHub Actions, account permissions, and manual migration/recovery.
- `vps.md`: domain, root configuration, startup, updates, and recovery.
- `.github/workflows/checks.yml`: contract, configuration, web, Python, database, and container checks.
- `ci/checks.yml.example`: reference copy of the workflow.

## One configuration file

Use `.env` at the repository root, alongside `compose.yaml`. Docker Compose reads it
for interpolation. Native web, engine, and Prisma commands load the same file.
Do not create environment files inside `apps/web` or `services/engine`.
The root `.env` is ignored by Git and excluded from container builds.

For a new checkout, copy `.env.example` to `.env` and replace the password and token.
The internal token must contain at least 32 characters. This checkout already has
generated local credentials. Use separate credentials on a public VPS.

## Local startup

Stop any native development server using port 3000 before starting the full Docker
stack. Do not run the native and container web servers on that port together.

```sh
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
```

Open http://localhost:8080. The gateway forwards to the website, which forwards
Calculate requests to `http://engine:8000` inside Docker using the shared token.
`ENGINE_MODE=computed` and `ENABLE_NASA_POWER=true` use real public data;
`NEXT_PUBLIC_USE_MOCK_API=false` keeps frontend fixtures disabled.
The migration service creates the cache table before the web service starts.

Check connectivity without submitting a field or changing services:

```sh
python3 infra/check-local.py
docker compose ps
```

Then select a real Romanian field in the UI and press Calculate. The first request
can take longer while public weather and soil data are fetched. A health check alone
does not verify a successful calculation or agronomic accuracy.

## Optional English summary

Add `OPENAI_API_KEY` to the root `.env`. The default model is `gpt-6-luna`, configurable
through `OPENAI_SUMMARY_MODEL`. `AI_SUMMARY_ENABLED=true` enables the feature when a key
is present. Missing keys and provider failures leave the calculated plans usable.
The summary uses OpenAI Responses with structured output, response storage disabled,
and no tools. It rewrites the calculated results; it does not generate the rotation.
After changing the key or model, run `docker compose up -d web` to recreate the web
service with the new values. Native development servers need a restart.

The cache stores public data only, not farmer forms, histories or recommendations.
For public hosting, follow [the VPS guide](vps.md).

References: [Compose environment files](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/),
[Compose merge rules](https://docs.docker.com/reference/compose-file/merge/),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
