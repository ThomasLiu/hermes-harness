#!/usr/bin/env python3
"""
harness-claude-code — 调用 Claude Code 执行 gstack skills
作为 Hermes 的 subprocess 层，MiniMax 通过这个模块派发任务
"""
import subprocess
import json
import sys
import argparse
import os
import time
from pathlib import Path
from typing import Optional, List

HARNESS_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = HARNESS_DIR / "config.yaml"

def load_config() -> dict:
    """加载配置"""
    import yaml
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return {
        "claude_code": {"path": "claude"},
        "gstack": {"dir": "~/.claude/skills/gstack"},
    }

def run_claude_code(
    prompt: str,
    model: Optional[str] = None,
    context_files: Optional[List[Path]] = None,
    timeout: int = 300,
) -> dict:
    """
    运行 Claude Code 命令

    Args:
        prompt: 要执行的 prompt
        model: 可选，指定模型
        context_files: 可选，附加的上下文文件
        timeout: 超时秒数

    Returns:
        {
            "success": bool,
            "output": str,
            "exit_code": int,
            "duration_ms": int,
        }
    """
    config = load_config()
    claude_path = config.get("claude_code", {}).get("path", "claude")

    cmd = [claude_path]

    if model:
        cmd.extend(["--model", model])

    cmd.extend([
        "-p",                        # non-interactive print mode
        "--output-format", "json",    # JSON 输出
        "--no-session-persistence",  # 不保存会话
    ])

    if context_files:
        for f in context_files:
            cmd.extend(["--add-dir", str(f)])

    system_prompt = f"""你正在被 Hermes Harness 调用。
Harness 的核心理念：
- MiniMax 做裁判，Claude Code 做执行
- 所有修改必须携带 evidence
- 如果需要用户确认，输出 YELLOW 报告
- 重要：不要在未确认的情况下做不可逆的修改

当前任务：
{prompt}
"""

    cmd.extend([
        "--system-prompt", system_prompt,
    ])

    try:
        start = time.time()
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        duration_ms = int((time.time() - start) * 1000)

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Timeout after {timeout}s",
            "exit_code": -1,
            "duration_ms": timeout * 1000,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": f"Claude Code not found at: {claude_path}",
            "exit_code": -2,
            "duration_ms": 0,
        }

def run_gstack_skill(
    skill: str,
    args: str = "",
    project_dir: Optional[Path] = None,
    timeout: int = 600,
) -> dict:
    """运行 gstack skill"""
    config = load_config()
    gstack_dir = Path(config.get("gstack", {}).get("dir", "~/.claude/skills/gstack")).expanduser()

    prompt = f"""运行 gstack skill: {skill}
项目目录: {project_dir or '当前目录'}
参数: {args}

请执行该 skill 并返回结构化的 evidence 输出。"""

    result = run_claude_code(
        prompt=prompt,
        timeout=timeout,
        context_files=[gstack_dir / "SKILL.md"] if (gstack_dir / "SKILL.md").exists() else None,
    )

    # 记录到日志
    try:
        from harness_log import write_log
        write_log(
            level="normal",
            event_type="skill_execution",
            skill=skill,
            success=str(result["success"]),
            duration_ms=str(result.get("duration_ms", 0)),
        )
    except Exception:
        pass  # 日志失败不影响主流程

    return result

# Aliases for test compatibility
call_claude_code = run_claude_code
invoke_gstack_skill = run_gstack_skill

class ClaudeCodeRunner:
    """
    Orchestrates Claude Code execution with Router decisions.
    MiniMax Router decides skill, this runner executes it.
    """

    def __init__(self, project_path: Path, minimax_router=None):
        self.project_path = Path(project_path)
        self.router = minimax_router or (lambda task: {"skill": "/review", "flag": "GREEN"})
        self.last_result = None

    def run_task(self, task: str) -> dict:
        """Execute a task: route it, then run the appropriate gstack skill."""
        route = self.router(task)
        skill = route.get("skill", "/review")
        flag = route.get("flag", "GREEN")

        result = run_gstack_skill(
            skill=skill,
            args=task,
            project_dir=self.project_path,
            timeout=600,
        )

        parsed = {"skill": skill, "flag": flag, "success": result["success"]}
        try:
            output = result.get("output", "")
            if output:
                data = json.loads(output)
                parsed.update(data)
                parsed["parsed"] = True
            else:
                parsed["parsed"] = False
                parsed["error"] = result.get("error", "no output")
        except json.JSONDecodeError:
            parsed["parsed"] = False
            parsed["raw_output"] = result.get("output", "")[:500]
            parsed["error"] = result.get("error", "")

        self.last_result = parsed
        return parsed

    def checkpoint_verify(self) -> dict:
        """Run checkpoint verification on the last result."""
        from harness_checkpoint import check_evidence
        if not self.last_result:
            return {"status": "ERROR", "reason": "no result to verify"}
        evidence = self.last_result.get("evidence", {})
        skill = self.last_result.get("skill", "/review")
        return check_evidence(skill, evidence, project_dir=self.project_path)

def main():
    parser = argparse.ArgumentParser(description="Hermes Harness — Claude Code 接口")
    parser.add_argument("--skill", required=True, help="gstack skill 名称")
    parser.add_argument("--args", default="", help="skill 参数")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--timeout", type=int, default=600, help="超时秒数")
    parser.add_argument("--output", default="json", choices=["json", "text"])

    args = parser.parse_args()

    result = run_gstack_skill(
        skill=args.skill,
        args=args.args,
        project_dir=Path(args.project_dir) if args.project_dir else None,
        timeout=args.timeout,
    )

    if args.output == "json":
        print(json.dumps({
            "skill": args.skill,
            "success": result["success"],
            "duration_ms": result.get("duration_ms"),
            "output": result.get("output", "")[:2000],
            "error": result.get("error", "")[:500],
        }, ensure_ascii=False, indent=2))
    else:
        if result["success"]:
            print(result["output"])
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
