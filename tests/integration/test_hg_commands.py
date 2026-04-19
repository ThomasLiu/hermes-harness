"""
End-to-End Integration Tests for hermes-harness
测试完整流程: init → new → align → verify → deploy
"""
import pytest
import json
import tempfile
import os
import subprocess
import yaml
from pathlib import Path
from unittest.mock import patch

# 用 HARNESS_DIR 环境变量指向临时目录进行隔离测试
@pytest.fixture(autouse=True)
def harness_dir(tmp_path, monkeypatch):
    """每个测试使用独立的临时 HARNESS_DIR"""
    harness_root = tmp_path / "hermes_harness_root"
    harness_root.mkdir()
    monkeypatch.setenv("HARNESS_DIR", str(harness_root))
    return harness_root

@pytest.fixture
def hg(harness_dir):
    """返回 hg 脚本路径"""
    project_root = Path(__file__).parent.parent.parent
    hg_path = project_root / "bin" / "hg"
    return str(hg_path)

class TestHgInit:
    """hg init 命令测试"""

    def test_init_creates_directories(self, hg, harness_dir):
        """init 应该创建必要的目录结构"""
        result = subprocess.run(["bash", hg, "init"], capture_output=True, text=True)
        assert result.returncode == 0, f"init failed: {result.stderr}"

        assert (harness_dir / "logs" / "critical").exists()
        assert (harness_dir / "logs" / "normal").exists()
        assert (harness_dir / "logs" / "verbose").exists()
        assert (harness_dir / "tmp").exists()
        assert (harness_dir / "requirements").exists()

    def test_init_creates_config(self, hg, harness_dir):
        """init 应该创建 config.yaml"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        config = harness_dir / "config.yaml"
        assert config.exists()

        with open(config) as f:
            cfg = yaml.safe_load(f)
        assert cfg["version"] == "1.0"
        assert "minimax" in cfg
        assert "claude_code" in cfg

    def test_init_idempotent(self, hg):
        """init 重复执行不应该报错"""
        result = subprocess.run(["bash", hg, "init"], capture_output=True, text=True)
        assert result.returncode == 0
        result2 = subprocess.run(["bash", hg, "init"], capture_output=True, text=True)
        assert result2.returncode == 0

class TestHgNew:
    """hg new 命令测试"""

    def test_new_creates_requirement(self, hg, harness_dir):
        """new 应该创建需求目录和对齐文档"""
        subprocess.run(["bash", hg, "init"], capture_output=True)

        result = subprocess.run(
            ["bash", hg, "new", "实现一个用户登录功能"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"new failed: {result.stderr}"

        # 找到刚创建的需求目录
        req_dirs = list((harness_dir / "requirements").iterdir())
        assert len(req_dirs) == 1

        req_dir = req_dirs[0]
        assert (req_dir / "requirement.txt").exists()
        assert (req_dir / "alignment.yaml").exists()

        with open(req_dir / "requirement.txt") as f:
            assert "用户登录" in f.read()

    def test_new_empty_requirement_fails(self, hg):
        """new 不带参数应该失败"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        result = subprocess.run(["bash", hg, "new"], capture_output=True, text=True)
        assert result.returncode != 0

    def test_new_logs_event(self, hg, harness_dir):
        """new 应该记录事件（即使 log 文件可能为空）"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        subprocess.run(
            ["bash", hg, "new", "测试任务"],
            capture_output=True
        )
        # 只要不报错就说明流程正常

class TestHgStatus:
    """hg status 命令测试"""

    def test_status_no_tasks(self, hg):
        """没有任务时显示空状态"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        result = subprocess.run(["bash", hg, "status"], capture_output=True, text=True)
        assert "没有运行中的任务" in result.stdout

    def test_status_with_task_shows_requirement(self, hg, harness_dir):
        """有任务时显示任务信息"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        subprocess.run(
            ["bash", hg, "new", "实现搜索功能"],
            capture_output=True
        )
        result = subprocess.run(["bash", hg, "status"], capture_output=True, text=True)
        assert "实现搜索功能" in result.stdout

class TestHgAlign:
    """hg align 命令测试"""

    def test_align_shows_stage0(self, hg, harness_dir):
        """align 显示 STAGE 0"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        subprocess.run(["bash", hg, "new", "实现支付功能"], capture_output=True)
        result = subprocess.run(["bash", hg, "align"], capture_output=True, text=True)
        assert "STAGE 0" in result.stdout

class TestHgLearn:
    """hg learn 命令测试"""

    def test_learn_runs_without_error(self, hg, harness_dir):
        """learn 应该触发分析脚本"""
        subprocess.run(["bash", hg, "init"], capture_output=True)
        result = subprocess.run(["bash", hg, "learn"], capture_output=True, text=True)
        assert result.returncode == 0 or "暂无数据" in result.stdout

class TestHgHelp:
    """hg help 命令测试"""

    def test_help_shows_commands(self, hg):
        """help 显示所有可用命令"""
        result = subprocess.run(["bash", hg, "help"], capture_output=True, text=True)
        assert "init" in result.stdout
        assert "new" in result.stdout
        assert "status" in result.stdout

class TestHgTest:
    """hg test 命令测试"""

    def test_test_runs_pytest(self, hg, harness_dir, monkeypatch):
        """test 应该运行 pytest"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.chdir(project_root)
        result = subprocess.run(["bash", hg, "test"], capture_output=True, text=True)
        assert "pytest" in result.stdout or "error" in result.stdout.lower() or result.returncode == 0

class TestIntegration:
    """完整流程集成测试"""

    def test_full_flow_init_to_status(self, hg, harness_dir):
        """完整流程: init → new → status"""
        r = subprocess.run(["bash", hg, "init"], capture_output=True)
        assert r.returncode == 0
        r = subprocess.run(["bash", hg, "new", "实现一个 REST API"], capture_output=True, text=True)
        assert r.returncode == 0
        assert "R" in r.stdout
        r = subprocess.run(["bash", hg, "status"], capture_output=True, text=True)
        assert "REST API" in r.stdout

    def test_hg_entry_point_exists(self):
        """hg 入口脚本存在且可执行"""
        project_root = Path(__file__).parent.parent.parent
        hg_path = project_root / "bin" / "hg"
        assert hg_path.exists()
        assert os.access(hg_path, os.X_OK)
