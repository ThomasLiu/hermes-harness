"""
Tests for harness-log.py
TDD: 先写测试，明确期望行为
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

# 设置测试环境（在 conftest.py 中已设置 HARNESS_DIR）
from harness_log import write_log, query_logs, LOG_LEVELS

class TestHarnessLog:
    """harness-log 核心测试"""

    def setup_method(self):
        """每个测试前清理"""
        for level_dir in LOG_LEVELS.values():
            if level_dir.exists():
                for f in level_dir.glob("*.jsonl"):
                    f.unlink()

    def test_write_log_creates_file(self):
        """写入日志后文件应该存在"""
        entry = write_log("critical", "task_start", task_id="R001", intent="FEATURE")
        assert entry is not None
        assert entry["event_type"] == "task_start"
        assert entry["task_id"] == "R001"
        assert "ts" in entry
        assert "level" in entry

        # 验证文件存在
        log_file = Path(LOG_LEVELS["critical"]) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        assert log_file.exists()

    def test_write_log_critical_level(self):
        """critical 级别日志应该写入 critical 目录"""
        entry = write_log("critical", "yellow_trigger", reason="scope_ambiguous", ai_reported="true")
        assert entry["level"] == "critical"
        assert entry["reason"] == "scope_ambiguous"

    def test_write_log_normal_level(self):
        """normal 级别日志应该写入 normal 目录"""
        entry = write_log("normal", "skill_execution", skill="/review", success="true")
        assert entry["level"] == "normal"

    def test_write_log_verbose_level(self):
        """verbose 级别日志应该写入 verbose 目录"""
        entry = write_log("verbose", "tool_call", tool="read_file", params="...")
        assert entry["level"] == "verbose"

    def test_query_logs_by_event_type(self):
        """应该能按 event_type 查询"""
        write_log("critical", "task_start", task_id="R001")
        write_log("critical", "task_end", task_id="R002")
        write_log("critical", "task_start", task_id="R003")

        logs = query_logs(levels=["critical"], event_types=["task_start"])
        assert len(logs) >= 2  # 至少有 R001 和 R003

    def test_query_logs_limit(self):
        """应该能限制返回数量"""
        for i in range(10):
            write_log("critical", "task_start", task_id=f"R{i:03d}")

        logs = query_logs(levels=["critical"], limit=5)
        assert len(logs) == 5

    def test_query_logs_empty(self):
        """无日志时应该返回空列表"""
        logs = query_logs(levels=["critical"])
        assert isinstance(logs, list)

    def test_log_contains_timestamp(self):
        """日志必须包含 ISO 格式时间戳"""
        entry = write_log("critical", "test_event", key="value")
        assert entry["ts"].endswith("Z")
        # 验证是有效 ISO 格式
        datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))

    def test_log_jsonl_format(self):
        """日志文件应该是有效的 JSONL 格式"""
        write_log("critical", "task_start", task_id="R001")
        write_log("critical", "task_end", task_id="R001")

        log_file = Path(LOG_LEVELS["critical"]) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        lines = log_file.read_text().strip().split("\n")

        for line in lines:
            entry = json.loads(line)
            assert "ts" in entry
            assert "level" in entry
            assert "event_type" in entry
