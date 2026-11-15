# CropPilot on your VPS

For the configured shared VPS at `crop-pilot.nemes.engineer`, use the
[GitHub Actions and existing-NGINX guide](deploy/README.md). Its checkout is
`/home/ubuntu/crop-pilot`, and production migrations are manual.

The instructions below describe the alternative standalone Caddy installation.

Use a Linux VPS with Docker Engine and the Docker Compose plugin. No AWS account,
CloudFormation, IAM or SSM configuration is required. For Ubuntu installation, follow
[Docker's official instructions](https://docs.docker.com/engine/install/ubuntu/).

## Configuration

Clone the repository on the VPS and run commands from its root. Copy `.env.example`
to `.env` for a new deployment; do not overwrite an existing configured file.
Set owner-only permissions with `chmod 600 .env`.

Fill in the root `.env`:

- `POSTGRES_PASSWORD`: a unique URL-safe password (letters, digits, underscores, hyphens).
- `INTERNAL_API_TOKEN`: a unique random token of at least 32 characters, shared automatically by web and engine.
- `DOMAIN`: the public hostname, without `https://` or a path.
- `ACME_EMAIL`: your certificate contact email.
- `OPENAI_API_KEY`: optional, for English-written summaries only.
- `OPENAI_SUMMARY_MODEL=gpt-6-luna`: default summary model; can be changed without editing code.

Keep `ENGINE_MODE=computed`, `ENABLE_NASA_POWER=true`, and
`NEXT_PUBLIC_USE_MOCK_API=false` for real recommendations. The public-data cache is
optional; it does not store farmer forms or their recommendations.
Use dedicated VPS credentials instead of copying this checkout's local credentials.

Point the domain's DNS record to the VPS. Allow inbound TCP 80/443 and preserve your
administrative access. UDP 443 is optional for HTTP/3. The production profile removes
the database, engine, web and gateway host ports; only Caddy is public.

## Start

```sh
docker compose -f compose.yaml -f infra/compose.production.yaml config --quiet
docker compose -f compose.yaml -f infra/compose.production.yaml up -d --build --wait --wait-timeout 180
```

Caddy obtains and renews the TLS certificate when DNS and ports are ready. Open your
HTTPS domain, choose a real field inside Romania, fill in its known history and
conditions, and press Calculate. Do not expect an AI summary until the API key has
been added. The detailed calculated plans are available independently of that key.

The connection is already implemented:

```text
Browser → Caddy HTTPS → NGINX → Next.js /api/recommendations
                                      → Python engine /recommendations
                                      → NASA weather + soil data + crop rules
                                      → three alternative plans → browser
```

The engine stays on the private container network. Its token is sent only by the web
server, never by the browser. No public engine URL or browser-side API key is needed.

## Inspect and update

```sh
docker compose -f compose.yaml -f infra/compose.production.yaml ps
python3 infra/check-local.py --url https://YOUR_DOMAIN
docker compose -f compose.yaml -f infra/compose.production.yaml logs --tail=100 web engine gateway https
```

The connectivity script checks health and engine reachability only. Successful real
field calculations must be checked through the UI; no scientific validation is implied.
Use `config --quiet` when checking configuration so secrets are not printed.

For updates, pull the reviewed source version and repeat the build/start command.
Compose applies the cache migration through its one-off migration service. Back up
the private root `.env`, and keep the PostgreSQL and Caddy volumes when replacing
containers. Avoid `down -v` unless you intend to discard the database and certificate
state. If changing a password on an already initialized database, update that database
role's password too; editing `.env` alone does not change an existing PostgreSQL role.

This is a single-server setup. Container restarts and health checks are configured;
server backups, monitoring, and DNS are managed on your VPS. Nothing has been deployed
by these source changes.
