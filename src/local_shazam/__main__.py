"""CLI entry point for local-shazam."""

import sys

from local_shazam.config import Settings
from local_shazam.logger import setup_root_logger


def main() -> int:
    """Run the application."""
    settings = Settings()
    setup_root_logger(level=settings.log_level)

    # TODO: Implement your CLI logic here
    print("local-shazam v0.1.0")

    return 0


if __name__ == "__main__":
    sys.exit(main())
