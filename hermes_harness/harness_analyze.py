#!/usr/bin/env python3
"""
harness-analyze — 每日性能分析脚本
从 CRITICAL 日志中提取指标，生成优化建议
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict

HARNESS_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = HARNESS_DIR / "logs"
LEARN_DIR = HARNESS_DIR / "learn"
REPORTS_DIR = LOG_DIR / "reports"

# 日志级别
LOG_LEVELS = ["critical"]

# 效率分层阈值（相对于基准时间的倍数）
EFFICIENCY_THRESHOLDS = {
    "GOOD_EXEMPLAR": 1.0,      # <= 1x 基准
    "OK": 1.5,                  # <= 1.5x 基准
    "SLOW_BUT_DONE": 3.0,      # <= 3x 基准
    "FAILED": float("inf"),
}

BENCHMARK_TASK_SECONDS = 600  # 10 分钟

def load_logs_since(hours: int = 24) -> List[dict]:
    """加载过去 N 小时的 CRITICAL 日志"""
    logs = []
    cutoff = datetime.now() - timedelta(hours=hours)

    for level in LOG_LEVELS:
        log_dir = LOG_DIR / level
        if not log_dir.exists():
            continue

        for log_file in sorted(log_dir.glob("*.jsonl"), reverse=True):
            file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
            if file_date < cutoff.replace(hour=0, minute=0, second=0):
                continue

            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        entry_ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                        if entry_ts.replace(tzinfo=None) >= cutoff:
                            logs.append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue

    return logs

def analyze_task_metrics(logs: List[dict]) -> dict:
    """分析任务级指标"""
    task_events = [l for l in logs if l.get("event_type") in ("task_start", "task_end")]

    completed = len([l for l in logs if l.get("event_type") == "task_end" and l.get("status") == "completed"])
    failed = len([l for l in logs if l.get("event_type") == "task_end" and l.get("status") == "failed"])
    total = completed + failed

    # 效率分层
    efficiency_dist = defaultdict(int)
    task_durations = []

    for log in logs:
        if log.get("event_type") == "task_end" and log.get("duration_ms"):
            duration_sec = int(log["duration_ms"]) / 1000
            task_durations.append(duration_sec)

            ratio = duration_sec / BENCHMARK_TASK_SECONDS
            for tier, threshold in sorted(EFFICIENCY_THRESHOLDS.items(), key=lambda x: x[1]):
                if ratio <= threshold:
                    efficiency_dist[tier] += 1
                    break

    avg_duration = sum(task_durations) / len(task_durations) if task_durations else 0

    return {
        "total_tasks": total,
        "completed": completed,
        "failed": failed,
        "success_rate": completed / total if total > 0 else 0,
        "avg_duration_minutes": avg_duration / 60,
        "benchmark_minutes": BENCHMARK_TASK_SECONDS / 60,
        "duration_delta_percent": ((avg_duration / BENCHMARK_TASK_SECONDS) - 1) * 100 if BENCHMARK_TASK_SECONDS > 0 else 0,
        "efficiency_distribution": dict(efficiency_dist),
    }

def analyze_agent_metrics(logs: List[dict]) -> dict:
    """分析各 Agent 指标"""
    metrics = defaultdict(lambda: {
        "total": 0,
        "failures": 0,
        "stuck": 0,
        "retries": 0,
        "corrections": 0,
    })

    for log in logs:
        agent = log.get("agent", "unknown")
        event = log.get("event_type")

        metrics[agent]["total"] += 1

        if event == "checkpoint" and log.get("status") == "FAIL":
            metrics[agent]["failures"] += 1
        if event == "stuck":
            metrics[agent]["stuck"] += 1
        if log.get("retry_count", 0) > 0:
            metrics[agent]["retries"] += max(0, int(log.get("retry_count", 0)) - 1)
        if event == "correction":
            metrics[agent]["corrections"] += 1

    # 计算比率
    for agent, m in metrics.items():
        m["failure_rate"] = m["failures"] / m["total"] if m["total"] > 0 else 0
        m["stuck_rate"] = m["stuck"] / m["total"] if m["total"] > 0 else 0
        m["correction_rate"] = m["corrections"] / m["total"] if m["total"] > 0 else 0

    return dict(metrics)

def analyze_flag_triggers(logs: List[dict]) -> dict:
    """分析三色旗触发情况"""
    yellows = [l for l in logs if l.get("event_type") == "yellow_trigger"]
    reds = [l for l in logs if l.get("event_type") == "red_trigger"]

    yellow_by_reason = defaultdict(int)
    for y in yellows:
        yellow_by_reason[y.get("reason", "unknown")] += 1

    # YELLOW 准确率（AI 上报 vs 实际）
    ai_reported_yellow = len([y for y in yellows if y.get("ai_reported") == "true"])
    actual_yellow = len(yellows)

    return {
        "yellow_count": len(yellows),
        "red_count": len(reds),
        "yellow_by_reason": dict(yellow_by_reason),
        "ai_reported_vs_actual_ratio": ai_reported_yellow / actual_yellow if actual_yellow > 0 else 1.0,
    }

def detect_optimization_candidates(logs: List[dict]) -> List[dict]:
    """检测优化候选项"""
    candidates = []

    # 检测 SLOW_BUT_DONE 模式
    slow_tasks = [l for l in logs if l.get("event_type") == "task_end" and l.get("efficiency_tier") == "SLOW_BUT_DONE"]
    if slow_tasks:
        # 找出慢的原因（重试次数多、checkpoint 失败多）
        for task in slow_tasks:
            reasons = []
            if task.get("retry_count", 0) > 2:
                reasons.append(f"high_retry_count:{task.get('retry_count')}")
            if task.get("checkpoint_failures", 0) > 1:
                reasons.append(f"checkpoint_failures:{task.get('checkpoint_failures')}")

            if reasons:
                candidates.append({
                    "type": "SLOW_BUT_DONE",
                    "task_id": task.get("task_id"),
                    "reasons": reasons,
                    "suggestion": "检查大文件处理或复杂逻辑路径",
                })

    # 检测频繁出现的错误类型
    error_types = defaultdict(int)
    for log in logs:
        if log.get("event_type") == "checkpoint" and log.get("status") == "FAIL":
            for reason in log.get("incomplete_reasons", []):
                error_types[reason] += 1

    for error, count in error_types.items():
        if count >= 3:
            candidates.append({
                "type": "FREQUENT_ERROR",
                "error": error,
                "count": count,
                "suggestion": f"考虑在 skill 前增加预检查步骤",
            })

    # 检测 YELLOW 上报偏差
    yellow_corrections = [l for l in logs if l.get("event_type") == "correction" and "YELLOW" in str(l.get("before", ""))]
    if len(yellow_corrections) >= 3:
        candidates.append({
            "type": "YELLOW_UNDERRERPORTING",
            "count": len(yellow_corrections),
            "suggestion": "Router 对边界判断不够准确，考虑强化高风险类型的人工确认",
        })

    return candidates

def generate_report(date_str: str, logs: List[dict], task_metrics: dict, agent_metrics: dict, flag_metrics: dict, candidates: List[dict]) -> str:
    """生成 Markdown 报告"""
    report = f"""## Day {date_str} Performance

### 任务级
- 完成任务: {task_metrics['completed']} | 失败: {task_metrics['failed']} | 成功率: {task_metrics['success_rate']:.1%}
- 平均任务时长: {task_metrics['avg_duration_minutes']:.1f}min（基准 {task_metrics['benchmark_minutes']:.0f}min，{task_metrics['duration_delta_percent']:+.0f}%)
- 🟡 YELLOW 触发: {flag_metrics['yellow_count']} 次
- 🔴 RED 触发: {flag_metrics['red_count']} 次

### 效率分层
"""

    for tier, count in task_metrics.get("efficiency_distribution", {}).items():
        pct = count / task_metrics["total_tasks"] * 100 if task_metrics["total_tasks"] > 0 else 0
        report += f"- {tier}: {count} ({pct:.0f}%)\n"

    report += "\n### Agent 级\n"
    for agent, m in agent_metrics.items():
        report += f"- **{agent}**: 失败率 {m['failure_rate']:.1%}，卡住率 {m['stuck_rate']:.1%}，纠正率 {m['correction_rate']:.1%}\n"

    if flag_metrics.get("yellow_by_reason"):
        report += "\n### YELLOW 触发原因\n"
        for reason, count in flag_metrics["yellow_by_reason"].items():
            report += f"- {reason}: {count} 次\n"

    if candidates:
        report += "\n### 优化候选\n"
        for i, c in enumerate(candidates, 1):
            report += f"{i}. [{c['type']}] {c.get('suggestion', c.get('error', ''))}\n"

    return report

def update_rules_from_candidates(candidates: List[dict], logs: List[dict]):
    """将优化候选写入规则文件"""
    for candidate in candidates:
        if candidate["type"] == "FREQUENT_ERROR":
            # 更新 Reviewer 规则
            rule_file = LEARN_DIR / "reviewer" / "learned_patterns.md"
            rule_file.parent.mkdir(parents=True, exist_ok=True)

            existing = rule_file.read_text() if rule_file.exists() else ""
            new_rule = f"\n## Auto-added {datetime.now().strftime('%Y-%m-%d')}\n"
            new_rule += f"- Pattern: {candidate['error']}\n"
            new_rule += f"- Count: {candidate['count']}\n"
            new_rule += f"- Suggestion: {candidate['suggestion']}\n"

            rule_file.write_text(existing + new_rule)

        elif candidate["type"] == "YELLOW_UNDERRERPORTING":
            # 更新 Router 规则
            rule_file = LEARN_DIR / "router" / "high_risk_types.md"
            rule_file.parent.mkdir(parents=True, exist_ok=True)

            existing = rule_file.read_text() if rule_file.exists() else ""
            new_rule = f"\n## Auto-added {datetime.now().strftime('%Y-%m-%d')}\n"
            new_rule += f"- Rule: 涉及 {candidate['count']}+ 次 YELLOW 纠正的类型，强制人工确认\n"

            rule_file.write_text(existing + new_rule)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", action="store_true", help="分析过去 24 小时")
    parser.add_argument("--hours", type=int, default=24, help="分析过去 N 小时")
    parser.add_argument("--output", default="report", choices=["report", "json"])
    args = parser.parse_args()

    logs = load_logs_since(hours=args.hours)

    if not logs:
        print("# No logs found for the specified period")
        return

    task_metrics = analyze_task_metrics(logs)
    agent_metrics = analyze_agent_metrics(logs)
    flag_metrics = analyze_flag_triggers(logs)
    candidates = detect_optimization_candidates(logs)

    date_str = datetime.now().strftime("%Y-%m-%d")

    if args.output == "report":
        report = generate_report(date_str, logs, task_metrics, agent_metrics, flag_metrics, candidates)
        print(report)

        # 保存报告
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORTS_DIR / f"daily-{date_str}.md"
        report_file.write_text(report)

        # 更新规则
        if candidates:
            update_rules_from_candidates(candidates, logs)
    else:
        print(json.dumps({
            "date": date_str,
            "task_metrics": task_metrics,
            "agent_metrics": agent_metrics,
            "flag_metrics": flag_metrics,
            "candidates": candidates,
        }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
