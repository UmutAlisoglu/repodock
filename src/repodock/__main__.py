"""Allow `python -m repodock`."""

import sys

from .cli import main

sys.exit(main())
