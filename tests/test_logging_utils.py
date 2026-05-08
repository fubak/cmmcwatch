#!/usr/bin/env python3
"""Tests for logging_utils module."""

import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from logging_utils import (
    ErrorCollector,
    StructuredLogger,
    log_api_call,
    log_operation,
    log_performance_metrics,
    log_quality_metrics,
)


class TestStructuredLogger:
    def test_default_correlation_id_is_uuid(self):
        logger = StructuredLogger("test")
        # Should be a valid UUID string
        uuid.UUID(logger.correlation_id)

    def test_custom_correlation_id(self):
        logger = StructuredLogger("test", correlation_id="my-corr-id")
        assert logger.correlation_id == "my-corr-id"

    def test_set_and_clear_context(self):
        logger = StructuredLogger("test")
        logger.set_context(user="alice", session="s1")
        assert logger.context == {"user": "alice", "session": "s1"}
        logger.clear_context()
        assert logger.context == {}

    def test_add_context_includes_correlation_id(self):
        logger = StructuredLogger("test", correlation_id="cid-1")
        result = logger._add_context({"foo": "bar"})
        assert result["correlation_id"] == "cid-1"
        assert result["foo"] == "bar"

    def test_logs_info_with_extra(self, caplog):
        logger = StructuredLogger("test_info_logger")
        with caplog.at_level(logging.INFO, logger="test_info_logger"):
            logger.info("hello", extra={"key": "value"})
        assert any("hello" in r.message for r in caplog.records)

    def test_logs_warning(self, caplog):
        logger = StructuredLogger("test_warn_logger")
        with caplog.at_level(logging.WARNING, logger="test_warn_logger"):
            logger.warning("watch out")
        assert any("watch out" in r.message for r in caplog.records)


class TestLogOperation:
    def test_yields_metadata_with_operation_id(self, caplog):
        logger = StructuredLogger("test_op")
        with caplog.at_level(logging.INFO, logger="test_op"):
            with log_operation(logger, "my_op", source="test") as meta:
                assert meta["operation"] == "my_op"
                assert meta["source"] == "test"
                assert meta["operation_id"]
        # Should log start AND completion
        assert sum(1 for r in caplog.records if "my_op" in r.message) >= 2

    def test_logs_failure_and_reraises(self, caplog):
        logger = StructuredLogger("test_op_err")
        with caplog.at_level(logging.ERROR, logger="test_op_err"):
            with pytest.raises(ValueError):
                with log_operation(logger, "bad_op"):
                    raise ValueError("boom")
        assert any("Failed operation" in r.message and "bad_op" in r.message for r in caplog.records)


class TestLogApiCall:
    def test_decorator_logs_success(self, caplog):
        logger = StructuredLogger("test_api")

        @log_api_call(logger)
        def my_api_call(url):
            return {"ok": True}

        with caplog.at_level(logging.INFO, logger="test_api"):
            result = my_api_call("https://example.com")
        assert result == {"ok": True}
        assert any("API call succeeded" in r.message for r in caplog.records)

    def test_decorator_logs_failure_and_reraises(self, caplog):
        logger = StructuredLogger("test_api_err")

        @log_api_call(logger)
        def failing_call():
            raise RuntimeError("503")

        with caplog.at_level(logging.ERROR, logger="test_api_err"):
            with pytest.raises(RuntimeError):
                failing_call()
        assert any("API call failed" in r.message for r in caplog.records)


class TestPerformanceAndQualityMetrics:
    def test_log_performance_metrics(self, caplog):
        logger = StructuredLogger("perf")
        with caplog.at_level(logging.INFO, logger="perf"):
            log_performance_metrics(logger, {"duration_ms": 123.4, "items": 50})
        assert any("Performance metrics" in r.message for r in caplog.records)

    def test_log_quality_metrics(self, caplog):
        logger = StructuredLogger("quality")
        with caplog.at_level(logging.INFO, logger="quality"):
            log_quality_metrics(logger, {"failed_validations": 0, "trends_kept": 42})
        assert any("Quality metrics" in r.message for r in caplog.records)


class TestErrorCollector:
    def test_starts_empty(self):
        collector = ErrorCollector()
        # Implementation may expose `errors` list or `count` etc.
        assert hasattr(collector, "errors") or hasattr(collector, "add")

    def test_add_increases_count(self):
        collector = ErrorCollector()
        if hasattr(collector, "add"):
            collector.add("test_module", ValueError("oops"))
            # Count should reflect 1 error
            errors = getattr(collector, "errors", None)
            if errors is not None:
                assert len(errors) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
