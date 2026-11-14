# AWS — prepared configuration, no automatic deployment

The prototype uses a single EC2 host: Caddy for HTTPS, NGINX for request limits,
Next.js, Python, and PostgreSQL for caching. This is not a highly available setup.
The cache can be rebuilt and contains no farmer data.

`host.yaml` creates an Amazon Linux 2023 host in an existing public VPC/subnet, a role
for SSM administration and reading two secrets, an encrypted disk, and ingress on
ports 80/443 only. It does not create a domain, certificate, SSM parameters, RDS, or
the application. Creating AWS resources incurs costs; it was not performed in this task.

## Preparing a future deployment

Choose the region, VPC, public subnet, and domain when deploying. Create SecureString
SSM parameters with the default AWS SSM key:
`/fieldshift/production/internal-token` (at least 32 random URL-safe characters) and
`/fieldshift/production/database-password` (at least 24). Do not reuse local values.
The AI summary is optional. To enable it, also create a SecureString such as
`/fieldshift/production/anthropic-api-key`, pass its name as the template parameter
`AiSummaryKeyParameterName` (the host role can then read it), and run the configure
script with `--ai-summary-key-parameter <name>`. Without it the summary stays off and
the page says it is not set up; the calculated results are unaffected.
If using a custom KMS key, grant decryption permission only for that key.

Validate and apply `host.yaml` through CloudFormation with `CAPABILITY_IAM` after
reviewing parameters and costs. Administration uses SSM, not SSH. The host installs
Docker and Compose 2.39.4, checking the published SHA-256 checksum. Wait for bootstrap
to finish before running Docker. Copy a reviewed source version to `/opt/fieldshift`,
excluding `.env*`, dependencies, and local artifacts. For a private repository, use
separate Git access; never put credentials in UserData. Source transfer is not automated.

From the source root on the host, with write permissions and Docker access, configure:

```sh
python3 infra/aws/configure.py --region <region> --domain <domain> --email <email>
```

The script reads secrets using the host role and creates `.env.production` with 0600
permissions. It refuses to overwrite an existing file and does not print secrets.
Both services receive the same token from this configuration. Do not run
`docker compose config` without `--quiet`: it may print environment values.

After the domain's DNS A record points to the host IP and ports 80/443 are accessible:

```sh
docker compose -p fieldshift-production --env-file .env.production -f compose.yaml -f infra/compose.production.yaml config --quiet
docker compose -p fieldshift-production --env-file .env.production -f compose.yaml -f infra/compose.production.yaml up -d --build --wait
```

Caddy obtains and renews the certificate. This profile publishes no ports for web,
engine, gateway, or PostgreSQL. NGINX blocks `/api/internal/*`; Python reaches those
routes directly through the Compose network. Limits are per IP: 5 calculations/minute,
60 searches/minute, and 30 engine checks/minute, with bursts documented in
`infra/nginx.conf`. Do not expose the gateway separately or place a CDN/proxy before
Caddy without explicitly configuring trusted IP sources.

Check `/api/health`, `/api/engine/status`, and a demo request. `computed` remains a
separate integration step when P2/P3/P4 are ready and verified. Changing the mode
does not validate the models. The public IP may change after stop/start; update DNS
or allocate an Elastic IP separately if needed.

## Operational limits

Application logs contain an ID, operation, status, error code, and duration. They
contain no forms, coordinates, queries, or tokens. Proxy HTTP access logs are disabled.
Docker logs rotate. Cache cleanup runs at maintenance-service startup and hourly in
bounded batches. This is not persistent analysis storage. Losing the host may lose
the cache; no recovery or high-availability guarantee is made.

CloudFormation and local syntax can be validated without creating resources. AWS
configuration and certificate issuance require separate verification at deployment.

Primary references: [EC2 CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-instance.html),
[SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html),
[Compose merge](https://docs.docker.com/reference/compose-file/merge/),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[NGINX limit_req](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).
