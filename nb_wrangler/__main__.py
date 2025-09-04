"""Entry point for running nb-wrangler as a module."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
