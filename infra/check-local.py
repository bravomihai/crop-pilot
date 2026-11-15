"""Read-only app connectivity check. Real field calculations are tested through the UI."""
import argparse
import json
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("Web health check failed")
        with urllib.request.urlopen(base + "/api/engine/status", timeout=15) as response:
            status = json.load(response)
        if status.get("status") != "reachable":
            raise RuntimeError("The web server cannot reach the recommendation engine")
        if status.get("mode") != "computed":
            raise RuntimeError("The engine is not configured for real computed recommendations")
    except (urllib.error.URLError, ValueError, RuntimeError) as error:
        raise SystemExit("Connectivity check failed: " + str(error)) from error
    print("Web and computed engine are reachable. Select a real field and calculate in the UI.")


if __name__ == "__main__":
    main()
