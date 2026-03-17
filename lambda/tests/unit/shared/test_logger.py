"""Tests for portable structured logger."""

import json

from src.shared.logger import get_logger


class TestGetLogger:
    def test_returns_logger_with_name(self):
        log = get_logger("test_module")
        assert log is not None

    def test_logger_outputs_json(self, capsys):
        log = get_logger("test_json")
        log.info("hello", extra_field="value")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip().split("\n")[-1])
        assert parsed["event"] == "hello"
        assert parsed["extra_field"] == "value"

    def test_logger_includes_module_name(self, capsys):
        log = get_logger("my_module")
        log.info("test")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip().split("\n")[-1])
        assert parsed["logger"] == "my_module"
