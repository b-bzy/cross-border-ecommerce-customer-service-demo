from __future__ import annotations

import argparse
import json
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a running synthetic commerce-support Demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    for endpoint in ("/healthz", "/readyz"):
        with urlopen(f"{args.base_url}{endpoint}", timeout=5) as response:  # noqa: S310 -- user chooses local URL
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") not in {"ok", "ready"}:
                raise SystemExit(f"Unexpected response from {endpoint}: {payload}")
    print(
        "Health and readiness checks passed. Use the documented API examples "
        "for confirmation-flow testing."
    )


if __name__ == "__main__":
    main()
