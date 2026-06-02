"""Backward-compatible entrypoint for the automation toolkit."""

from apps.api.automation_server import *  # noqa: F401,F403
from apps.api.automation_server import main


if __name__ == "__main__":
    raise SystemExit(main())
