#!/usr/bin/env python3
"""
harness-claude-code — 调用 Claude Code 执行 gstack skills
作为 Hermes 的 subprocess 层，MiniMax 通过这个模块派发任务
"""
import subprocess
import json
import sys
import argparse
from pathlib import Path
from typing import Optional, List

HARNESS_DIR = Path(__file__).resolve().parent.parent.parent
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

    # 构建命令
    cmd = [claude_path]

    if model:
        cmd.extend(["--model", model])

    cmd.extend([
        "--print",
        "--no-input",
        "--verbose",
    ])

    if context_files:
        for f in context_files:
            cmd.extend(["--add-context", str(f)])

    # 添加 system prompt（限制 Claude Code 的行为）
    system_prompt = f"""你正在被 Hermes Harness 调用。
Harness 的核心理念：
- MiniMax 做裁判，Claude Code 做执行
- 所有修改必须携带 evidence
- 如果需要用户确认，输出 YELLOW 报告
- 重要：不要在未确认的情况下做不可逆的修改

当前任务：
{prompt}
"""

    import os
    env = os.environ.copy()
    env["CLAUDE_CODE_SYSTEM_PROMPT"] = system_prompt

    try:
        import time
        start = time.time()

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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
    """
    运行 gstack skill

    Args:
        skill: gstack skill 名称 (e.g. "/review", "/qa")
        args: skill 参数
        project_dir: 项目目录
        timeout: 超时秒数

    Returns:
        skill 执行结果
    """
    config = load_config()
    gstack_dir = Path(config.get("gstack", {}).get("dir", "~/.claude/skills/gstack")).expanduser()

    # 构建 prompt
    prompt = f"""运行 gstack skill: {skill}
项目目录: {project_dir or '当前目录'}
参数: {args}

请执行该 skill 并返回结构化的 evidence 输出。
"""

    # 调用 Claude Code
    result = run_claude_code(
        prompt=prompt,
        timeout=timeout,
        context_files=[gstack_dir / "SKILL.md"] if (gstack_dir / "SKILL.md").exists() else None,
    )

    # 记录到日志
    from harness_log import write_log
    write_log(
        level="normal",
        event_type="skill_execution",
        skill=skill,
        success=str(result["success"]),
        duration_ms=str(result.get("duration_ms", 0)),
        output_hash=str(hash(result.get("output", ""))[:16]),
    )

    return result

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
