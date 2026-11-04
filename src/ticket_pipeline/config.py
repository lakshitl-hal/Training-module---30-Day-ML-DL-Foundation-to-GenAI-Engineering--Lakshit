"""
Pipeline configuration.

All tunable settings live in one immutable object. Values come from, in
order of precedence: explicit arguments (the CLI), environment variables,
then defaults. Nothing else in the package reads the environment, which
keeps the other modules deterministic and easy to test.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ticket_pipeline.errors import ConfigurationError

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH: Path = PROJECT_ROOT / "data" / "tickets.csv"
DEFAULT_LOG_LEVEL: str = "INFO"
VALID_LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")

ENV_INPUT_PATH = "TICKET_PIPELINE_INPUT"
ENV_LOG_LEVEL = "TICKET_PIPELINE_LOG_LEVEL"


@dataclass(frozen=True)
class PipelineConfig:
    """Validated, immutable settings for one pipeline run."""

    input_path: Path = DEFAULT_INPUT_PATH
    log_level: str = DEFAULT_LOG_LEVEL
    strict: bool = False  # True: any rejected row makes the run fail

    def __post_init__(self) -> None:
        level = self.log_level.upper()
        if level not in VALID_LOG_LEVELS:
            raise ConfigurationError(
                f"Unknown log level '{self.log_level}'. "
                f"Use one of: {', '.join(VALID_LOG_LEVELS)}."
            )
        # frozen=True blocks normal assignment; normalise once, here.
        object.__setattr__(self, "log_level", level)
        object.__setattr__(self, "input_path", Path(self.input_path))

    @property
    def numeric_log_level(self) -> int:
        """The ``logging`` module constant for ``log_level`` (e.g. 20 for INFO)."""
        return logging.getLevelNamesMapping()[self.log_level]

    @classmethod
    def from_sources(
        cls,
        input_path: str | Path | None = None,
        log_level: str | None = None,
        strict: bool = False,
        environ: Mapping[str, str] | None = None,
    ) -> PipelineConfig:
        """Build a config from explicit values, then environment, then defaults.

        ``environ`` is injectable so tests never depend on the real
        environment of the machine running them.
        """
        env = os.environ if environ is None else environ
        return cls(
            input_path=Path(input_path or env.get(ENV_INPUT_PATH) or DEFAULT_INPUT_PATH),
            log_level=log_level or env.get(ENV_LOG_LEVEL) or DEFAULT_LOG_LEVEL,
            strict=strict,
        )
