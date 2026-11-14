"""Run on the prepared host; writes ignored Compose config from SSM, never prints secrets."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--token-parameter", default="/fieldshift/production/internal-token")
    parser.add_argument("--database-parameter", default="/fieldshift/production/database-password")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", args.domain):
        parser.error("Provide a valid lowercase public domain")
    if not re.fullmatch(r"[^\s@$]+@[^\s@$]+\.[^\s@$]+", args.email):
        parser.error("Provide a valid contact email without spaces or dollar signs")
    output = Path(__file__).resolve().parents[2] / ".env.production"
    if output.exists():
        parser.error(".env.production already exists; review it before replacing deployment secrets")

    def parameter(name):
        try:
            completed = subprocess.run([
                "aws", "ssm", "get-parameter", "--name", name, "--with-decryption",
                "--region", args.region, "--output", "json",
            ], capture_output=True, text=True, check=True, timeout=30)
            result = json.loads(completed.stdout)["Parameter"]
            if result["Type"] != "SecureString":
                raise ValueError("Expected SecureString")
            return result["Value"]
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            raise SystemExit("Unable to load a SecureString parameter; check region, name and host permissions") from None

    token = parameter(args.token_parameter)
    password = parameter(args.database_parameter)
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,}", token):
        parser.error("The internal token must have at least 32 URL-safe characters")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,}", password):
        parser.error("The database password must have at least 24 URL-safe characters")
    data = {
        "DOMAIN": args.domain, "ACME_EMAIL": args.email,
        "POSTGRES_USER": "fieldshift", "POSTGRES_DB": "fieldshift",
        "POSTGRES_PASSWORD": password, "INTERNAL_API_TOKEN": token,
        "ENGINE_MODE": "demo", "ENABLE_NASA_POWER": "false", "CACHE_ENABLED": "true",
    }
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write("\n".join(f"{key}={value}" for key, value in data.items()) + "\n")
    print("Created ignored .env.production with owner-only permissions. No secret values printed.")


if __name__ == "__main__":
    main()
