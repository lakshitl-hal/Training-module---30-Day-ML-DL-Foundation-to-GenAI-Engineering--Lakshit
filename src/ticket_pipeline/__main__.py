"""Allow ``python -m ticket_pipeline``."""

import sys

from ticket_pipeline.cli import main

sys.exit(main())
