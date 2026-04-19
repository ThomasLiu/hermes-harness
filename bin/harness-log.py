#!/usr/bin/env python3
"""
harness-log — 结构化日志写入工具
将事件写入 JSONL，支持 CRITICAL/NORMAL/VERBOSE 分级
"""
import json
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", os.path.expanduser("~/.hermes/harness")))
LOG_DIR = HARNESS_DIR / "logs"
SCHEMA_DIR = LOG_DIR / "schema"

LOG_LEVELS = {
    "critical": LOG_DIR / "critical",
    "normal": LOG_DIR / "normal",
    "verbose": LOG_DIR / "verbose",
}

def ensure_dirs():
    for d in LOG_LEVELS.values():
        d.mkdir(parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

def write_log(level: str, event_type: str, **kwargs):
    """写入单条日志"""
    ensure_dirs()

    log_file = LOG_LEVELS.get(level, LOG_LEVELS["normal"]) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    entry = {
        "ts": datetime.now().isoformat() + "Z",
        "level": level,
        "event_type": event_type,
        **kwargs
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry

def query_logs(levels=None, event_types=None, limit=100):
    """查询日志"""
    if levels is None:
        levels = list(LOG_LEVELS.keys())

    logs = []
    for level in levels:
        log_dir = LOG_LEVELS.get(level)
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.glob("*.jsonl"), reverse=True):
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if event_types and entry.get("event_type") not in event_types:
                            continue
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
                    if len(logs) >= limit:
                        return logs
    return logs

def main():
    parser = argparse.ArgumentParser(description="Hermes Harness 日志工具")
    parser.add_argument("event", nargs="?", help="事件类型 (e.g. task_start)")
    parser.add_argument("--level", default="normal", choices=["critical", "normal", "verbose"])
    parser.add_argument("--query", action="store_true")
    parser.add_argument("--query-flag", dest="query_flag")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("kv", nargs="*", help="key=value 对")

    args = parser.parse_args()

    if args.query:
        logs = query_logs(limit=args.limit)
        for log in logs:
            print(json.dumps(log, ensure_ascii=False))
        return

    if not args.event:
        parser.print_help()
        return

    # 解析 kv 对
    data = {}
    for item in args.kv:
        if "=" in item:
            k, v = item.split("=", 1)
            data[k] = v

    entry = write_log(args.level, args.event, **data)
    print(json.dumps(entry, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
