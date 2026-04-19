"""
Tests for harness-analyze.py
TDD: 每日性能分析脚本
"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from harness_analyze import (
    load_logs_since,
    analyze_task_metrics,
    analyze_agent_metrics,
    analyze_flag_triggers,
    detect_optimization_candidates,
    generate_report,
    update_rules_from_candidates,
    BENCHMARK_TASK_SECONDS,
)


class TestAnalyzeTaskMetrics:
    """任务级指标分析测试"""

    def test_empty_logs(self):
        """空日志返回零值"""
        result = analyze_task_metrics([])
        assert result["total_tasks"] == 0
        assert result["success_rate"] == 0

    def test_completed_tasks(self):
        """完成的日志计算正确"""
        logs = [
            {"event_type": "task_end", "status": "completed", "duration_ms": 300000},
            {"event_type": "task_end", "status": "completed", "duration_ms": 600000},
        ]
        result = analyze_task_metrics(logs)
        assert result["completed"] == 2
        assert result["failed"] == 0
        assert result["success_rate"] == 1.0

    def test_failed_tasks(self):
        """失败任务计算正确"""
        logs = [
            {"event_type": "task_end", "status": "completed", "duration_ms": 600000},
            {"event_type": "task_end", "status": "failed", "duration_ms": 100000},
        ]
        result = analyze_task_metrics(logs)
        assert result["completed"] == 1
        assert result["failed"] == 1
        assert abs(result["success_rate"] - 0.5) < 0.01

    def test_efficiency_tier_good(self):
        """<= 基准时长 = GOOD_EXEMPLAR"""
        logs = [
            {"event_type": "task_end", "status": "completed", "duration_ms": BENCHMARK_TASK_SECONDS * 1000},
        ]
        result = analyze_task_metrics(logs)
        assert "GOOD_EXEMPLAR" in result["efficiency_distribution"]
        assert result["efficiency_distribution"]["GOOD_EXEMPLAR"] == 1

    def test_efficiency_tier_slow(self):
        """> 3x 基准时长 = SLOW_BUT_DONE（3x exactly = SLOW_BUT_DONE，> 3x = FAILED）"""
        logs = [
            {"event_type": "task_end", "status": "completed", "duration_ms": int(BENCHMARK_TASK_SECONDS * 3.0 * 1000)},
        ]
        result = analyze_task_metrics(logs)
        assert "SLOW_BUT_DONE" in result["efficiency_distribution"]


class TestAnalyzeAgentMetrics:
    """Agent 级指标分析测试"""

    def test_empty_metrics(self):
        result = analyze_agent_metrics([])
        assert result == {}

    def test_failure_rate(self):
        logs = [
            {"agent": "coder", "event_type": "checkpoint", "status": "FAIL"},
            {"agent": "coder", "event_type": "checkpoint", "status": "PASS"},
            {"agent": "coder", "event_type": "checkpoint", "status": "PASS"},
        ]
        result = analyze_agent_metrics(logs)
        assert result["coder"]["total"] == 3
        assert result["coder"]["failures"] == 1
        assert abs(result["coder"]["failure_rate"] - 1/3) < 0.01

    def test_stuck_and_correction(self):
        logs = [
            {"agent": "reviewer", "event_type": "stuck"},
            {"agent": "reviewer", "event_type": "correction"},
            {"agent": "reviewer", "event_type": "correction"},
        ]
        result = analyze_agent_metrics(logs)
        assert result["reviewer"]["stuck"] == 1
        assert result["reviewer"]["corrections"] == 2

    def test_retry_count(self):
        logs = [
            {"agent": "coder", "retry_count": 3},
            {"agent": "coder", "retry_count": 1},
        ]
        result = analyze_agent_metrics(logs)
        # retries = max(0, retry_count - 1)
        assert result["coder"]["retries"] == 2  # (3-1) + (1-1)


class TestAnalyzeFlagTriggers:
    """三色旗分析测试"""

    def test_empty_flags(self):
        result = analyze_flag_triggers([])
        assert result["yellow_count"] == 0
        assert result["red_count"] == 0
        assert result["ai_reported_vs_actual_ratio"] == 1.0

    def test_yellow_count(self):
        logs = [
            {"event_type": "yellow_trigger", "reason": "需要用户确认"},
            {"event_type": "yellow_trigger", "reason": "权限不足"},
            {"event_type": "red_trigger"},
        ]
        result = analyze_flag_triggers(logs)
        assert result["yellow_count"] == 2
        assert result["red_count"] == 1

    def test_yellow_by_reason(self):
        logs = [
            {"event_type": "yellow_trigger", "reason": "权限不足"},
            {"event_type": "yellow_trigger", "reason": "权限不足"},
            {"event_type": "yellow_trigger", "reason": "其他"},
        ]
        result = analyze_flag_triggers(logs)
        assert result["yellow_by_reason"]["权限不足"] == 2
        assert result["yellow_by_reason"]["其他"] == 1

    def test_ai_reported_vs_actual(self):
        logs = [
            {"event_type": "yellow_trigger", "ai_reported": "true"},
            {"event_type": "yellow_trigger", "ai_reported": "true"},
            {"event_type": "yellow_trigger", "ai_reported": "false"},
        ]
        result = analyze_flag_triggers(logs)
        assert abs(result["ai_reported_vs_actual_ratio"] - 2/3) < 0.01


class TestDetectOptimizationCandidates:
    """优化候选检测测试"""

    def test_no_candidates(self):
        logs = [
            {"event_type": "task_end", "efficiency_tier": "GOOD_EXEMPLAR"},
        ]
        result = detect_optimization_candidates(logs)
        assert result == []

    def test_slow_but_done_candidate(self):
        logs = [
            {"event_type": "task_end", "efficiency_tier": "SLOW_BUT_DONE", "retry_count": 3, "task_id": "T1"},
        ]
        result = detect_optimization_candidates(logs)
        assert len(result) >= 1
        slow = next((c for c in result if c["type"] == "SLOW_BUT_DONE"), None)
        assert slow is not None
        assert "high_retry_count:3" in slow["reasons"]

    def test_frequent_error_candidate(self):
        logs = [
            {"event_type": "checkpoint", "status": "FAIL", "incomplete_reasons": ["missing_tsc"]},
            {"event_type": "checkpoint", "status": "FAIL", "incomplete_reasons": ["missing_tsc"]},
            {"event_type": "checkpoint", "status": "FAIL", "incomplete_reasons": ["missing_tsc"]},
        ]
        result = detect_optimization_candidates(logs)
        freq = next((c for c in result if c["type"] == "FREQUENT_ERROR"), None)
        assert freq is not None
        assert freq["count"] == 3

    def test_yellow_underreporting_candidate(self):
        logs = [
            {"event_type": "correction", "before": "Should be YELLOW"},
            {"event_type": "correction", "before": "Should be YELLOW"},
            {"event_type": "correction", "before": "Should be YELLOW"},
        ]
        result = detect_optimization_candidates(logs)
        under = next((c for c in result if c["type"] == "YELLOW_UNDERRERPORTING"), None)
        assert under is not None
        assert under["count"] == 3


class TestGenerateReport:
    """报告生成测试"""

    def test_report_contains_metrics(self):
        task = {"completed": 5, "failed": 1, "success_rate": 0.833, "avg_duration_minutes": 8.5, "benchmark_minutes": 10, "duration_delta_percent": -15, "total_tasks": 6, "efficiency_distribution": {"GOOD_EXEMPLAR": 4, "SLOW_BUT_DONE": 2}}
        agent = {"coder": {"failure_rate": 0.1, "stuck_rate": 0.05, "correction_rate": 0.02}}
        flag = {"yellow_count": 2, "red_count": 0, "yellow_by_reason": {"权限不足": 2}}
        candidates = []

        report = generate_report("2026-04-19", [], task, agent, flag, candidates)
        assert "2026-04-19" in report
        assert "5" in report  # completed
        assert "83%" in report or "83.3%" in report

    def test_report_empty_data(self):
        task = {"completed": 0, "failed": 0, "success_rate": 0, "avg_duration_minutes": 0, "benchmark_minutes": 10, "duration_delta_percent": 0, "total_tasks": 0, "efficiency_distribution": {}}
        flag = {"yellow_count": 0, "red_count": 0, "yellow_by_reason": {}}
        report = generate_report("2026-04-19", [], task, {}, flag, [])
        assert "0" in report


class TestUpdateRulesFromCandidates:
    """规则更新测试"""

    def test_frequent_error_creates_rule_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        import harness_analyze as ha
        ha.LEARN_DIR = tmp_path / "learn"

        candidates = [{
            "type": "FREQUENT_ERROR",
            "error": "missing_tsc",
            "count": 5,
            "suggestion": "增加 tsc 预检查",
        }]
        update_rules_from_candidates(candidates, [])

        rule_file = tmp_path / "learn" / "reviewer" / "learned_patterns.md"
        assert rule_file.exists()
        assert "missing_tsc" in rule_file.read_text()

    def test_yellow_underreporting_creates_rule(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        import harness_analyze as ha
        ha.LEARN_DIR = tmp_path / "learn"

        candidates = [{
            "type": "YELLOW_UNDERRERPORTING",
            "count": 5,
            "suggestion": "强制人工确认",
        }]
        update_rules_from_candidates(candidates, [])

        rule_file = tmp_path / "learn" / "router" / "high_risk_types.md"
        assert rule_file.exists()


class TestLoadLogsSince:
    """日志加载测试（无外部依赖）"""

    def test_load_logs_no_directory(self, monkeypatch, tmp_path):
        """无日志目录时返回空"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        import harness_analyze as ha
        ha.LOG_DIR = tmp_path / "logs"
        result = ha.load_logs_since(hours=1)
        assert result == []

    def test_load_logs_with_file(self, monkeypatch, tmp_path):
        """有日志文件时正确解析"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        import harness_analyze as ha
        log_dir = tmp_path / "logs" / "critical"
        log_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}.jsonl"
        log_file.write_text(json.dumps({
            "ts": datetime.now().isoformat() + "Z",
            "event_type": "task_start",
            "level": "critical",
        }) + "\n")

        ha.LOG_DIR = tmp_path / "logs"
        result = ha.load_logs_since(hours=24)
        assert len(result) == 1
        assert result[0]["event_type"] == "task_start"
