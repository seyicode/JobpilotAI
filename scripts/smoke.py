"""Run against an already running local stack; Python standard library only."""
import json
import os
from urllib.request import urlopen


def main():
    api = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
    web = os.environ.get("WEB_URL", "http://localhost:3000").rstrip("/")
    for route in ("/health", "/ready"):
        with urlopen(api + route, timeout=10) as response:
            if response.status != 200 or json.load(response) != {"status": "ok"}:
                raise RuntimeError("API check failed: " + route)
        print("PASS " + route)
    with urlopen(web, timeout=30) as response:
        html = response.read().decode()
        if response.status != 200 or "Your dashboard" not in html or "apply manually" not in html:
            raise RuntimeError("Dashboard check failed")
    print("PASS dashboard")


if __name__ == "__main__":
    main()
