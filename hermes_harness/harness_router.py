#!/usr/bin/env python3
"""
harness-router — MiniMax Router 实现
MiniMax 2.7 作为 Router/Validator，根据 SYSTEM_PROMPT.md 做意图分类和任务路由
"""
import os
import json
import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", os.path.expanduser("~/.hermes/harness")))
LOG_FILE = HARNESS_DIR / "logs" / "router.jsonl"

def get_minimax_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY environment variable not set")
    return key

def call_minimax(prompt: str, model: str = "MiniMax-Text-01", max_tokens: int = 2048) -> str:
    """调用 MiniMax API"""
    import urllib.request
    import urllib.parse

    api_key = get_minimax_key()
    url = "https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId=your_group_id"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"MiniMax API error {e.code}: {error_body}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected MiniMax response format: {e}")

def build_router_prompt(task_input: str, context: Optional[dict] = None) -> str:
    """构建 Router prompt"""
    system_prompt = Path(__file__).parent.parent / "agents" / "router" / "SYSTEM_PROMPT.md"
    if system_prompt.exists():
        system = system_prompt.read_text()
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

def route_task(task_input: str, context: Optional[dict] = None) -> dict:
    """主路由函数：输入任务，输出路由决策"""
    prompt = build_router_prompt(task_input, context)

    try:
        response = call_minimax(prompt)
    except Exception as e:
        # API 失败时降级为 UNKNOWN + YELLOW
        return {
            "intent": "UNKNOWN",
            "skill": "/office-hours",
            "flag": "YELLOW",
            "reason": f"MiniMax API failed: {e}. Defaulting to manual routing.",
            "confidence": 0.0,
            "error": str(e)
        }

    # 解析 JSON 响应
    try:
        # 尝试提取 JSON 代码块
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

        # 验证必填字段
        for field in ["intent", "skill", "flag", "reason"]:
            if field not in result:
                result[field] = ""

        if result["flag"] not in ("GREEN", "YELLOW", "RED"):
            result["flag"] = "YELLOW"

        return result

    except json.JSONDecodeError as e:
        return {
            "intent": "UNKNOWN",
            "skill": "/office-hours",
            "flag": "YELLOW",
            "reason": f"Failed to parse MiniMax response as JSON: {e}. Raw response: {response[:200]}",
            "confidence": 0.0,
            "raw_response": response[:500]
        }

def log_route(decision: dict, task_input: str):
    """记录路由决策到 JSONL"""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "router_decision",
        "task_input": task_input[:200],
        "decision": decision
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def main():
    parser = argparse.ArgumentParser(description="MiniMax Router")
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
