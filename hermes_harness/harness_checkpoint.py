#!/usr/bin/env python3
"""
harness-checkpoint — Checkpoint 验证器
验证 skill 输出的 evidence 是否满足最小集
"""
import os
import json
import sys
import argparse
import subprocess
import yaml
from pathlib import Path
from datetime import datetime

HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", os.path.expanduser("~/.hermes/harness")))
TMP_DIR = HARNESS_DIR / "tmp"

# 各 skill 的最小 evidence 清单
MINIMAL_EVIDENCE = {
    "/review": {
        "required": ["tsc_output", "diff_summary", "findings"],
        "tsc_required": True,
        "min_findings": 0,  # 0 也可能是 PASS，但必须有证据
    },
    "/qa": {
        "required": ["test_results", "screenshots", "bugs_found"],
        "playwright_required": True,
    },
    "/office-hours": {
        "required": ["design_doc", "reframed_problem", "alternatives"],
    },
    "/plan-ceo-review": {
        "required": ["scope_analysis", "risk_assessment", "recommendation"],
    },
    "/ship": {
        "required": ["test_results", "coverage_audit", "pr_url"],
    },
    "/cso": {
        "required": ["owasp_findings", "stride_model", "severity_summary"],
        "min_critical": 0,  # 有 Critical 必须上报 RED
    },
}

def verify_tsc(project_dir: Path = None) -> dict:
    """运行 tsc --noEmit 验证类型错误"""
    result = {
        "tool": "tsc",
        "passed": False,
        "errors": [],
        "error_count": 0,
    }

    try:
        # 尝试在项目目录运行
        cmd = ["npx", "tsc", "--noEmit", "--json"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_dir or Path.cwd(),
        )

        if proc.returncode == 0:
            result["passed"] = True
        else:
            try:
                output = json.loads(proc.stdout)
                for item in output:
                    if item.get("severity") == "error":
                        result["errors"].append({
                            "file": item.get("file"),
                            "line": item.get("line"),
                            "message": item.get("message"),
                        })
                        result["error_count"] += 1
            except json.JSONDecodeError:
                result["errors"].append(proc.stdout[:500])

    except FileNotFoundError:
        result["errors"].append("tsc not found, skipping")
    except subprocess.TimeoutExpired:
        result["errors"].append("tsc timeout (>60s)")
    except Exception as e:
        result["errors"].append(str(e))

    return result

def verify_playwright(project_dir: Path = None) -> dict:
    """运行 Playwright 验证"""
    result = {
        "tool": "playwright",
        "passed": False,
        "test_results": [],
        "error_count": 0,
    }

    try:
        cmd = ["npx", "playwright", "test", "--reporter=json"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_dir or Path.cwd(),
        )

        result["passed"] = proc.returncode == 0

        # 尝试解析 JSON 输出
        try:
            output = json.loads(proc.stdout)
            result["test_results"] = output.get("suites", [])
        except json.JSONDecodeError:
            result["raw_output"] = proc.stdout[:500]

    except FileNotFoundError:
        result["errors"].append("playwright not found, skipping")
    except subprocess.TimeoutExpired:
        result["errors"].append("playwright timeout (>120s)")
    except Exception as e:
        result["errors"].append(str(e))

    return result

def check_evidence(skill: str, evidence: dict, project_dir: Path = None) -> dict:
    """检查 evidence 是否满足最小集"""
    minimal = MINIMAL_EVIDENCE.get(skill, {"required": []})

    result = {
        "skill": skill,
        "timestamp": datetime.now().isoformat() + "Z",
        "passed": True,
        "incomplete_reasons": [],
        "verification_results": {},
    }

    # 1. 检查必填字段
    for field in minimal.get("required", []):
        if field not in evidence or evidence[field] in [None, "", [], {}]:
            result["passed"] = False
            result["incomplete_reasons"].append(f"missing required field: {field}")

    # 2. 运行独立验证工具
    if skill == "/review":
        if minimal.get("tsc_required"):
            tsc_result = verify_tsc(project_dir)
            result["verification_results"]["tsc"] = tsc_result
            if not tsc_result["passed"]:
                result["passed"] = False
                result["incomplete_reasons"].append(
                    f"tsc found {tsc_result['error_count']} errors"
                )

    elif skill == "/qa":
        if minimal.get("playwright_required"):
            pw_result = verify_playwright(project_dir)
            result["verification_results"]["playwright"] = pw_result
            if not pw_result["passed"]:
                result["passed"] = False
                result["incomplete_reasons"].append(
                    f"playwright tests failed"
                )

    # 3. 检查 findings 数量
    if "findings" in evidence:
        min_findings = minimal.get("min_findings", 0)
        findings = evidence["findings"] if isinstance(evidence["findings"], list) else []
        if len(findings) < min_findings:
            result["incomplete_reasons"].append(
                f"findings count {len(findings)} < minimum {min_findings}"
            )

    # 4. 检查 Critical 安全漏洞
    if skill == "/cso":
        severity = evidence.get("severity_summary", {})
        critical_count = severity.get("critical", 0)
        if critical_count > 0:
            result["critical_found"] = True
            result["passed"] = False
            result["incomplete_reasons"].append(
                f"CRITICAL security vulnerabilities found: {critical_count}"
            )

    result["status"] = "PASS" if result["passed"] else "FAIL"
    if not result["passed"] and result["incomplete_reasons"]:
        result["status"] = "INCOMPLETE"

    return result

def main():
    parser = argparse.ArgumentParser(description="Hermes Harness Checkpoint 验证器")
    parser.add_argument("--skill", required=True, help="skill 名称 (e.g. /review)")
    parser.add_argument("--evidence", help="evidence JSON 字符串")
    parser.add_argument("--evidence-file", help="evidence JSON 文件路径")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--latest", action="store_true", help="读取最新任务的 evidence")
    parser.add_argument("--output", default="json", choices=["json", "text"])

    args = parser.parse_args()

    # 加载 evidence
    evidence = {}
    if args.evidence:
        evidence = json.loads(args.evidence)
    elif args.evidence_file:
        with open(args.evidence_file) as f:
            evidence = json.load(f)
    elif args.latest:
        # 读取最新任务的 evidence
        latest_req = None
        reqs = sorted((HARNESS_DIR / "requirements").glob("*"), reverse=True)
        for req in reqs:
            checkpoint_file = req / "checkpoint_latest.json"
            if checkpoint_file.exists():
                with open(checkpoint_file) as f:
                    evidence = json.load(f)
                break
    else:
        # 从 stdin 读取
        try:
            evidence = json.load(sys.stdin)
        except json.JSONDecodeError:
            print(json.dumps({
                "status": "ERROR",
                "reason": "invalid JSON input"
            }, ensure_ascii=False))
            sys.exit(1)

    project_dir = Path(args.project_dir) if args.project_dir else None

    result = check_evidence(args.skill, evidence, project_dir)

    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Skill: {result['skill']}")
        print(f"Status: {result['status']}")
        if result['incomplete_reasons']:
            print("Reasons:")
            for reason in result['incomplete_reasons']:
                print(f"  - {reason}")
        if result.get('verification_results'):
            print("Verification:")
            for tool, vr in result['verification_results'].items():
                print(f"  {tool}: {'PASS' if vr.get('passed') else 'FAIL'}")
                if vr.get('error_count'):
                    print(f"    Errors: {vr['error_count']}")

if __name__ == "__main__":
    main()
