#!/usr/bin/env python3
"""
harness-router — Router 实现
MiniMax/Claude Code 作为 Router，直接通过 prompt 做意图分类和任务路由
不依赖外部 API，直接通过 Claude Code subprocess 执行路由
"""
import json
import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

HARNESS_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = HARNESS_DIR / "logs" / "router.jsonl"

# 从 config.yaml 读取 claude_code 路径
def get_claude_path() -> str:
    import yaml
    config_file = HARNESS_DIR / "config.yaml"
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.safe_load(f)
            return config.get("claude_code", {}).get(
                "path",
                "/Users/thomas/Library/pnpm/global/5/.pnpm/@anthropic-ai+claude-code@2.1.68/node_modules/@anthropic-ai/claude-code/node_modules/.bin/claude"
            )
    return "/Users/thomas/Library/pnpm/global/5/.pnpm/@anthropic-ai+claude-code@2.1.68/node_modules/@anthropic-ai/claude-code/node_modules/.bin/claude"


def get_gstack_dir() -> Path:
    import yaml
    config_file = HARNESS_DIR / "config.yaml"
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.safe_load(f)
            return Path(config.get("gstack", {}).get("dir", "~/.claude/skills/gstack")).expanduser()
    return Path("~/.claude/skills/gstack").expanduser()


def build_router_prompt(task_input: str, context: Optional[dict] = None) -> str:
    """构建 Router prompt"""
    system_prompt_path = HARNESS_DIR / "agents" / "router" / "SYSTEM_PROMPT.md"
    if system_prompt_path.exists():
        system = system_prompt_path.read_text()
    else:
        system = _default_router_system()

    context_str = ""
    if context:
        context_str = "\n\n## Context\n" + json.dumps(context, ensure_ascii=False, indent=2)

    return f"""{system}

## Task
{task_input}
{context_str}

## Output Format
Return ONLY a JSON object:
{{"intent": "...", "skill": "...", "flag": "GREEN|YELLOW|RED", "reason": "...", "confidence": 0.0-1.0}}
"""


def _default_router_system() -> str:
    return """You are a Router for an AI coding harness. Your job is to classify user intent and route to the correct skill.

## Intent Classification
- EXPLORE: New task, find a working path
- OPTIMIZE: Known task, improve existing solution
- REVIEW: Code review, security audit
- LEARN: Knowledge acquisition from codebase
- UNKNOWN: Cannot classify

## Three-Color Flag
- GREEN: AI can handle autonomously
- YELLOW: AI can handle but needs human confirmation
- RED: Human must intervene immediately

## Routing Rules
- EXPLORE → /office-hours (plan) → /cso (assess) → /review (implement) → /ship
- OPTIMIZE → /review (verify) → /ship
- REVIEW → /review
- LEARN → /read-file + /grep
- UNKNOWN → /office-hours

## Checkpoint Verification
After each skill, verify evidence completeness before proceeding."""


def call_router_llm(prompt: str) -> str:
    """通过 Claude Code 执行路由决策（subprocess 调用）"""
    import subprocess
    import os
    import time

    claude_path = get_claude_path()

    system_msg = """You are the Router for Hermes Harness. You classify user intent and route to the correct gstack skill.
Respond ONLY with a JSON object. No markdown, no explanation."""
    full_prompt = f"{system_msg}\n\n## Task\n{prompt}"

    try:
        start = time.time()
        result = subprocess.run(
            [claude_path, "--print", "--no-input", "--verbose"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "CLAUDE_CODE_SYSTEM_PROMPT": system_msg},
        )
        duration_ms = int((time.time() - start) * 1000)

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            raise RuntimeError(f"Claude Code error: {result.stderr[:200]}")
    except FileNotFoundError:
        raise RuntimeError(f"Claude Code not found at: {claude_path}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Router timeout after 60s")


def route_task(task_input: str, context: Optional[dict] = None) -> dict:
    """主路由函数：输入任务，输出路由决策"""
    prompt = build_router_prompt(task_input, context)

    try:
        response = call_router_llm(prompt)
    except Exception as e:
        # Claude Code 失败时降级为 UNKNOWN + YELLOW
        return {
            "intent": "UNKNOWN",
            "skill": "/office-hours",
            "flag": "YELLOW",
            "reason": f"Router failed: {e}. Defaulting to manual routing.",
            "confidence": 0.0,
            "error": str(e),
        }

    # 解析 JSON 响应
    try:
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            result = json.loads(response[start:end].strip())
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            result = json.loads(response[start:end].strip())
        else:
            result = json.loads(response.strip())

        for field in ["intent", "skill", "flag", "reason"]:
            if field not in result:
                result[field] = ""

        if result.get("flag") not in ("GREEN", "YELLOW", "RED"):
            result["flag"] = "YELLOW"

        return result

    except json.JSONDecodeError as e:
        return {
            "intent": "UNKNOWN",
            "skill": "/office-hours",
            "flag": "YELLOW",
            "reason": f"Failed to parse router response as JSON: {e}. Raw: {response[:200]}",
            "confidence": 0.0,
            "raw_response": response[:500],
        }


def log_route(decision: dict, task_input: str):
    """记录路由决策到 JSONL"""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "router_decision",
        "task_input": task_input[:200],
        "decision": decision,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Hermes Harness Router")
    parser.add_argument("task", help="Task input to route")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-log", action="store_true", help="Skip logging")
    args = parser.parse_args()

    decision = route_task(args.task)

    if not args.no_log:
        log_route(decision, args.task)

    if args.json:
        print(json.dumps(decision, ensure_ascii=False, indent=2))
    else:
        print(f"[{decision['flag']}] {decision['intent']} → {decision['skill']}")
        print(f"Reason: {decision['reason']}")
        if decision.get("confidence"):
            print(f"Confidence: {decision['confidence']:.2f}")


if __name__ == "__main__":
    main()
