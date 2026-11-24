"""Container-local login probe honoring host and TLS proxy configuration."""
import os
from urllib.request import Request, urlopen


def main():
    hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost").split(",") if h.strip()]
    host = hosts[0].lstrip(".") if hosts and hosts[0] != "*" else "localhost"
    headers = {"Host": host}
    if os.environ.get("DJANGO_SECURE_SSL", "false").strip().lower() in ("true", "1", "yes", "on"):
        headers["X-Forwarded-Proto"] = "https"
    with urlopen(Request("http://127.0.0.1:8000/accounts/login/", headers=headers), timeout=4) as response:
        if response.status != 200:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
