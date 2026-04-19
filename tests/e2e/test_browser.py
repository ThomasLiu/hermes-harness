"""
Playwright 浏览器端到端测试
测试 hermes-harness 的 GitHub 页面渲染和基本 UI 验收
"""
import pytest
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

REPO_URL = "https://github.com/ThomasLiu/hermes-harness"

@pytest.fixture(scope="module")
def browser_context():
    """启动浏览器"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN"
        )
        yield context
        context.close()
        browser.close()

class TestGitHubRepoPage:
    """GitHub 仓库页面验收测试"""

    def test_repo_loads(self, browser_context):
        """仓库页面能正常加载"""
        page = browser_context.new_page()
        response = page.goto(REPO_URL, wait_until="domcontentloaded")
        assert response.ok, f"Page failed to load: {response.status}"

    def test_repo_title(self, browser_context):
        """仓库标题正确"""
        page = browser_context.new_page()
        page.goto(REPO_URL, wait_until="domcontentloaded")
        title = page.title()
        assert "hermes-harness" in title.lower()

    def test_readme_renders(self, browser_context):
        """README 渲染正常"""
        page = browser_context.new_page()
        page.goto(f"{REPO_URL}/blob/main/README.md", wait_until="domcontentloaded")
        content = page.locator(".markdown-body").inner_text()
        assert "Hermes Harness" in content

    def test_file_list_visible(self, browser_context):
        """文件列表可见"""
        page = browser_context.new_page()
        page.goto(f"{REPO_URL}", wait_until="domcontentloaded")
        items = page.locator("svg.octicon-file, svg.octicon-file-directory")
        count = items.count()
        assert count > 0

    def test_skill_md_exists(self, browser_context):
        """SKILL.md 文件存在且可访问"""
        page = browser_context.new_page()
        response = page.goto(f"{REPO_URL}/blob/main/SKILL.md", wait_until="domcontentloaded")
        assert response.ok
        page.wait_for_selector(".markdown-body", timeout=10000)
        content = page.locator(".markdown-body").inner_text()
        assert "Hermes Harness" in content
        assert "hg" in content

    def test_pyproject_exists(self, browser_context):
        """pyproject.toml 存在"""
        page = browser_context.new_page()
        # Use raw URL to avoid blob page rendering issues
        response = page.goto(f"{REPO_URL}/raw/main/pyproject.toml", wait_until="domcontentloaded")
        assert response.ok
        content = page.content()
        assert "pytest" in content or "hermes-harness" in content

class TestHgCLIIntegration:
    """hg CLI 端到端测试（使用真实环境）"""

    def test_hg_help_command(self):
        """hg help 输出正确"""
        project_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "init" in result.stdout
        assert "new" in result.stdout

    def test_hg_init_creates_all_dirs(self, tmp_path, monkeypatch):
        """hg init 创建所有必要目录"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "init"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert (tmp_path / "logs" / "critical").exists()
        assert (tmp_path / "logs" / "normal").exists()
        assert (tmp_path / "tmp").exists()
        assert (tmp_path / "requirements").exists()
        assert (tmp_path / "config.yaml").exists()

    def test_hg_new_creates_requirement(self, tmp_path, monkeypatch):
        """hg new 创建完整的需求文档"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "new", "实现一个登录功能"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        req_dirs = list((tmp_path / "requirements").iterdir())
        assert len(req_dirs) == 1
        assert (req_dirs[0] / "requirement.txt").exists()
        assert (req_dirs[0] / "alignment.yaml").exists()

    def test_hg_status_empty_state(self, tmp_path, monkeypatch):
        """hg status 无任务时显示空状态"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "status"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "没有运行中的任务" in result.stdout

    def test_hg_verify_no_task_error(self, tmp_path, monkeypatch):
        """hg verify 无任务时报错"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "verify"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode != 0 or "没有运行中的任务" in result.stdout

    def test_hg_rollback_no_history(self, tmp_path, monkeypatch):
        """hg rollback 无历史时显示提示"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "rollback"],
            capture_output=True, text=True, timeout=10, input="n\n"
        )
        assert result.returncode == 0
        assert "暂无部署历史" in result.stdout or "Rollback" in result.stdout

    def test_hg_deploy_no_pr(self, tmp_path, monkeypatch):
        """hg deploy 无 PR 时提示先完成 STAGE 2"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "new", "Test task"],
            capture_output=True, timeout=10
        )
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "deploy"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0 or result.returncode == 1
        # 应该提示尚未生成 PR
        assert "尚未生成 PR" in result.stdout or "STAGE 2" in result.stdout

    def test_hg_align_shows_stage0(self, tmp_path, monkeypatch):
        """hg align 显示 STAGE 0"""
        project_root = Path(__file__).parent.parent.parent
        monkeypatch.setenv("HARNESS_DIR", str(tmp_path))
        subprocess.run(["bash", str(project_root / "bin" / "hg"), "init"],
                      capture_output=True, timeout=10)
        subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "new", "实现搜索"],
            capture_output=True, timeout=10
        )
        result = subprocess.run(
            ["bash", str(project_root / "bin" / "hg"), "align"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "STAGE 0" in result.stdout
