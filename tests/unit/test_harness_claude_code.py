"""
Tests for harness-claude-code.py
TDD: Claude Code 子进程接口
"""
import pytest
import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

from harness_claude_code import (
    run_claude_code,
    run_gstack_skill,
    load_config,
    ClaudeCodeRunner,
    call_claude_code,
    invoke_gstack_skill,
)


class TestLoadConfig:
    """配置加载测试"""

    def test_load_config_default(self, monkeypatch, tmp_path):
        """无 config.yaml 时返回默认配置"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        import importlib
        import harness_claude_code as hcc
        hcc.CONFIG_FILE = tmp_path / "nonexistent.yaml"
        config = load_config()
        assert "claude_code" in config
        assert config["claude_code"]["path"] == "claude"


class TestRunClaudeCode:
    """Claude Code 执行测试"""

    @patch("subprocess.run")
    def test_success_returns_output(self, mock_run, monkeypatch, tmp_path):
        """成功执行返回 output"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "ok"}',
            stderr="",
        )

        result = run_claude_code("test prompt", timeout=60)

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "duration_ms" in result
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_nonzero_exit_code_is_failure(self, mock_run, monkeypatch, tmp_path):
        """非零退出码表示失败"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="some error",
        )

        result = run_claude_code("test prompt")

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "some error" in result["error"]

    @patch("subprocess.run")
    def test_timeout_returns_failure(self, mock_run, monkeypatch, tmp_path):
        """超时返回失败"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

        result = run_claude_code("long running prompt", timeout=60)

        assert result["success"] is False
        assert result["exit_code"] == -1
        assert "Timeout" in result["error"]

    @patch("subprocess.run")
    def test_claude_code_not_found(self, mock_run, monkeypatch, tmp_path):
        """Claude Code 不存在返回失败"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.side_effect = FileNotFoundError()

        result = run_claude_code("test prompt")

        assert result["success"] is False
        assert result["exit_code"] == -2
        assert "not found" in result["error"]

    @patch("subprocess.run")
    def test_model_option_passed(self, mock_run, monkeypatch, tmp_path):
        """model 参数传递给 claude 命令"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_claude_code("prompt", model="claude-opus-4")

        cmd = mock_run.call_args.args[0]
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "claude-opus-4"

    @patch("subprocess.run")
    def test_call_alias_equals_run(self, mock_run, monkeypatch, tmp_path):
        """call_claude_code 是 run_claude_code 的别名"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = call_claude_code("test")
        assert result["success"] is True


class TestRunGstackSkill:
    """gstack skill 执行测试"""

    @patch("subprocess.run")
    def test_runs_claude_code_with_skill_prompt(self, mock_run, monkeypatch, tmp_path):
        """run_gstack_skill 调用 run_claude_code"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="{}",
            stderr="",
        )

        result = run_gstack_skill("/review", args="check code", project_dir=tmp_path)

        assert result["success"] is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_invoke_alias_works(self, mock_run, monkeypatch, tmp_path):
        """invoke_gstack_skill 是 run_gstack_skill 的别名"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        result = invoke_gstack_skill("/cso")
        assert "success" in result

    @patch("subprocess.run")
    def test_gstack_skill_logs_event(self, mock_run, monkeypatch, tmp_path):
        """run_gstack_skill 记录日志（即使失败也不崩溃）"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")

        # 不应该抛异常
        result = run_gstack_skill("/office-hours", project_dir=tmp_path)
        assert result["success"] is True


class TestClaudeCodeRunner:
    """ClaudeCodeRunner 编排测试"""

    def test_init_with_default_router(self, monkeypatch, tmp_path):
        """默认 router 返回 /review + GREEN"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        runner = ClaudeCodeRunner(project_path=tmp_path)
        assert runner.project_path == tmp_path
        assert callable(runner.router)

    @patch("harness_claude_code.run_gstack_skill")
    def test_run_task_uses_router_decision(self, mock_run_skill, monkeypatch, tmp_path):
        """run_task 根据 router 决策选择 skill"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run_skill.return_value = {
            "success": True,
            "output": "{}",
            "error": "",
            "duration_ms": 100,
        }

        def mock_router(task):
            return {"skill": "/review", "flag": "YELLOW"}

        runner = ClaudeCodeRunner(project_path=tmp_path, minimax_router=mock_router)
        result = runner.run_task("review my code")

        assert result["skill"] == "/review"
        assert result["flag"] == "YELLOW"

    @patch("harness_claude_code.run_gstack_skill")
    def test_run_task_parses_json_output(self, mock_run_skill, monkeypatch, tmp_path):
        """run_task 解析 JSON 输出"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        output_data = {"evidence": {"tsc_output": "{}", "diff_summary": "+5"}, "findings": []}
        mock_run_skill.return_value = {
            "success": True,
            "output": json.dumps(output_data),
            "error": "",
            "duration_ms": 100,
        }

        runner = ClaudeCodeRunner(project_path=tmp_path, minimax_router=lambda t: {"skill": "/review", "flag": "GREEN"})
        result = runner.run_task("review")

        assert result["parsed"] is True

    @patch("harness_claude_code.run_gstack_skill")
    def test_run_task_non_json_output(self, mock_run_skill, monkeypatch, tmp_path):
        """run_task 处理非 JSON 输出"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        mock_run_skill.return_value = {
            "success": True,
            "output": "some plain text output",
            "error": "",
            "duration_ms": 50,
        }

        runner = ClaudeCodeRunner(project_path=tmp_path, minimax_router=lambda t: {"skill": "/review", "flag": "GREEN"})
        result = runner.run_task("review")

        assert result["parsed"] is False

    def test_checkpoint_verify_no_result(self, monkeypatch, tmp_path):
        """checkpoint_verify 无结果时返回 ERROR"""
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        runner = ClaudeCodeRunner(project_path=tmp_path)
        result = runner.checkpoint_verify()
        assert result["status"] == "ERROR"
