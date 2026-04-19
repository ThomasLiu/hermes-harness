"""
Tests for harness-claude-code.py
TDD: Claude Code subprocess interface for invoking gstack skills
"""
import pytest
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from harness_claude_code import (
    run_claude_code, run_gstack_skill, ClaudeCodeRunner,
    call_claude_code, invoke_gstack_skill
)

class TestCallClaudeCode:
    """Claude Code subprocess 调用测试"""

    @patch("harness_claude_code.subprocess.run")
    def test_claude_code_basic_invocation(self, mock_run):
        """基本调用：Claude Code 返回成功"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"success": true, "output": "Done"}',
            stderr=""
        )

        result = run_claude_code(prompt="Fix the login bug", model="sonnet")

        assert result["success"] is True
        assert result["exit_code"] == 0
        mock_run.assert_called_once()

    @patch("harness_claude_code.subprocess.run")
    def test_claude_code_non_zero_return(self, mock_run):
        """Claude Code 返回非零（执行失败）"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: something went wrong"
        )

        result = run_claude_code(prompt="Fix the login bug")

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "something went wrong" in result["error"]

    @patch("harness_claude_code.subprocess.run")
    def test_claude_code_timeout(self, mock_run):
        """超时处理"""
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

        result = run_claude_code(prompt="Do something slow", timeout=120)

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @patch("harness_claude_code.subprocess.run")
    def test_claude_code_not_found(self, mock_run):
        """Claude Code 不存在时的处理"""
        mock_run.side_effect = FileNotFoundError("claude not found")

        result = run_claude_code(prompt="Test")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("harness_claude_code.subprocess.run")
    def test_claude_code_alias_equivalence(self, mock_run):
        """call_claude_code 是 run_claude_code 的别名"""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        r1 = run_claude_code(prompt="test")
        r2 = call_claude_code(prompt="test")
        assert r1["success"] == r2["success"]

class TestInvokeGstackSkill:
    """gstack skill 调用测试"""

    @patch("harness_claude_code.run_claude_code")
    def test_invoke_review_skill(self, mock_call):
        """调用 /review skill"""
        mock_call.return_value = {
            "success": True,
            "exit_code": 0,
            "output": json.dumps({
                "skill": "/review",
                "evidence": {
                    "tsc_output": '{"errors": [], "summary": {"errors": 0}}',
                    "diff_summary": "+50 -10",
                    "findings": []
                },
                "flag": "GREEN"
            }),
            "error": "",
            "duration_ms": 5000,
        }

        result = run_gstack_skill(skill="/review", args="Review auth module")

        assert result["success"] is True
        mock_call.assert_called_once()

    @patch("harness_claude_code.run_claude_code")
    def test_invoke_office_hours_skill(self, mock_call):
        """调用 /office-hours skill"""
        mock_call.return_value = {
            "success": True,
            "exit_code": 0,
            "output": json.dumps({
                "skill": "/office-hours",
                "evidence": {
                    "design_doc": "# Login Feature",
                    "reframed_problem": "Need secure auth",
                    "alternatives": ["方案A", "方案B"]
                },
                "flag": "GREEN"
            }),
            "error": "",
            "duration_ms": 3000,
        }

        result = run_gstack_skill(skill="/office-hours", args="Design login")

        assert result["success"] is True
        assert "design_doc" in result["output"]

    @patch("harness_claude_code.run_claude_code")
    def test_invoke_skill_non_zero_return(self, mock_call):
        """skill 执行失败"""
        mock_call.return_value = {
            "success": False,
            "exit_code": 1,
            "output": "",
            "error": "Skill execution failed",
            "duration_ms": 1000,
        }

        result = run_gstack_skill(skill="/review", args="Review code")
        assert result["success"] is False

    @patch("harness_claude_code.run_claude_code")
    def test_invoke_gstack_skill_alias(self, mock_call):
        """invoke_gstack_skill 是 run_gstack_skill 的别名"""
        mock_call.return_value = {"success": True, "exit_code": 0, "output": "{}", "error": "", "duration_ms": 100}
        r1 = run_gstack_skill(skill="/review", args="x")
        r2 = invoke_gstack_skill(skill="/review", args="x")
        assert r1["success"] == r2["success"]

class TestClaudeCodeRunner:
    """ClaudeCodeRunner 集成测试"""

    @patch("harness_claude_code.run_gstack_skill")
    def test_runner_routes_to_office_hours(self, mock_gstack):
        """Router 决策为 /office-hours 时的路由"""
        mock_gstack.return_value = {
            "success": True,
            "exit_code": 0,
            "output": json.dumps({
                "skill": "/office-hours",
                "flag": "GREEN",
                "evidence": {
                    "design_doc": "...",
                    "reframed_problem": "...",
                    "alternatives": ["A", "B"]
                }
            }),
            "error": "",
            "duration_ms": 3000,
        }

        runner = ClaudeCodeRunner(
            project_path=Path("/tmp/myapp"),
            minimax_router=lambda t: {"skill": "/office-hours", "flag": "GREEN"}
        )

        result = runner.run_task("Design a login feature")

        assert result["skill"] == "/office-hours"
        assert result["flag"] == "GREEN"
        assert result["success"] is True

    @patch("harness_claude_code.run_gstack_skill")
    def test_runner_routes_to_review(self, mock_gstack):
        """Router 决策为 /review 时的路由"""
        mock_gstack.return_value = {
            "success": True,
            "exit_code": 0,
            "output": json.dumps({
                "skill": "/review",
                "flag": "YELLOW",
                "evidence": {
                    "tsc_output": '{"errors": [], "summary": {"errors": 0}}',
                    "diff_summary": "+20 -5",
                    "findings": ["风格问题: 缺少注释"]
                }
            }),
            "error": "",
            "duration_ms": 5000,
        }

        runner = ClaudeCodeRunner(
            project_path=Path("/tmp/myapp"),
            minimax_router=lambda t: {"skill": "/review", "flag": "YELLOW"}
        )

        result = runner.run_task("Improve the API")

        assert result["skill"] == "/review"
        assert result["flag"] == "YELLOW"

    @patch("harness_claude_code.run_gstack_skill")
    def test_runner_checkpoint_verify(self, mock_gstack):
        """runner.checkpoint_verify() 调用"""
        mock_gstack.return_value = {
            "success": True,
            "exit_code": 0,
            "output": json.dumps({
                "skill": "/review",
                "flag": "GREEN",
                "evidence": {
                    "tsc_output": '{"errors": [], "summary": {"errors": 0}}',
                    "diff_summary": "+10 -2",
                    "findings": []
                }
            }),
            "error": "",
            "duration_ms": 3000,
        }

        runner = ClaudeCodeRunner(project_path=Path("/tmp/myapp"))
        runner.run_task("Test task")

        verify_result = runner.checkpoint_verify()
        assert "status" in verify_result

    @patch("harness_claude_code.run_gstack_skill")
    def test_runner_malformed_json_output(self, mock_gstack):
        """Claude Code 返回非 JSON 时的降级处理"""
        mock_gstack.return_value = {
            "success": True,
            "exit_code": 0,
            "output": "Oops, not JSON at all",
            "error": "",
            "duration_ms": 1000,
        }

        runner = ClaudeCodeRunner(project_path=Path("/tmp/myapp"))
        result = runner.run_task("Test")

        assert result["parsed"] is False
        assert "raw_output" in result

    def test_runner_checkpoint_verify_no_result(self):
        """无 result 时 checkpoint_verify 返回错误"""
        runner = ClaudeCodeRunner(project_path=Path("/tmp/myapp"))
        result = runner.checkpoint_verify()
        assert result["status"] == "ERROR"

    def test_runner_default_router(self):
        """无 router 时使用默认路由"""
        runner = ClaudeCodeRunner(project_path=Path("/tmp/myapp"))
        assert callable(runner.router)
        result = runner.router("test task")
        assert "skill" in result
        assert "flag" in result
