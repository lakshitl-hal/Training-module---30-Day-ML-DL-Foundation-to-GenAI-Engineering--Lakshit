"""Unit tests: configuration sources and logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest import mock

import pytest

from ticket_pipeline.config import DEFAULT_INPUT_PATH, PipelineConfig
from ticket_pipeline.errors import ConfigurationError
from ticket_pipeline.logging_config import configure_logging, log_duration


class TestPipelineConfig:
    def test_defaults_when_nothing_is_set(self) -> None:
        config = PipelineConfig.from_sources(environ={})
        assert config.input_path == DEFAULT_INPUT_PATH
        assert config.log_level == "INFO"
        assert config.strict is False

    def test_environment_is_used_when_no_argument(self) -> None:
        env = {"TICKET_PIPELINE_INPUT": "x.csv", "TICKET_PIPELINE_LOG_LEVEL": "debug"}
        config = PipelineConfig.from_sources(environ=env)
        assert config.input_path == Path("x.csv")
        assert config.log_level == "DEBUG"
        assert config.numeric_log_level == logging.DEBUG

    def test_explicit_argument_beats_environment(self) -> None:
        env = {"TICKET_PIPELINE_INPUT": "env.csv", "TICKET_PIPELINE_LOG_LEVEL": "ERROR"}
        config = PipelineConfig.from_sources("cli.csv", "warning", environ=env)
        assert config.input_path == Path("cli.csv")
        assert config.log_level == "WARNING"

    @pytest.mark.parametrize("level", ["verbose", "", "TRACE"])
    def test_unknown_log_level_raises_actionable_error(self, level: str) -> None:
        with pytest.raises(ConfigurationError, match="Use one of: DEBUG, INFO"):
            PipelineConfig(log_level=level)


class TestLogDuration:
    def test_logs_stage_outcome_and_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        @log_duration("demo")
        def work() -> int:
            return 42

        # The clock is an external, non-deterministic boundary: mock it.
        with mock.patch("ticket_pipeline.logging_config.time.perf_counter",
                        side_effect=[10.0, 10.25]), caplog.at_level(logging.DEBUG):
            assert work() == 42
        assert "stage=demo outcome=completed duration_ms=250.0" in caplog.text

    def test_failure_is_logged_and_original_exception_re_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        @log_duration("demo")
        def broken() -> None:
            raise KeyError("root cause")

        with caplog.at_level(logging.DEBUG), pytest.raises(KeyError, match="root cause"):
            broken()
        assert "outcome=failed" in caplog.text

    def test_preserves_function_metadata(self) -> None:
        @log_duration("demo")
        def documented() -> None:
            """Docstring."""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "Docstring."


def test_configure_logging_is_idempotent() -> None:
    configure_logging(logging.INFO)
    configure_logging(logging.DEBUG)
    package_logger = logging.getLogger("ticket_pipeline")
    assert len(package_logger.handlers) == 1
    assert package_logger.level == logging.DEBUG
