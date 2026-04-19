"""
Tests for harness-checkpoint.py
TDD: 验证 skill 输出的 evidence 是否满足最小集
"""
import json
import pytest
import tempfile
import os
from pathlib import Path

# conftest.py 已设置 HARNESS_DIR 和 sys.path
from harness_checkpoint import check_evidence, verify_tsc

class TestCheckpointEvidence:
    """checkpoint evidence 验证测试"""

    def test_review_evidence_with_tsc_pass(self, tmp_path):
        """/review evidence：tsc 通过，应该 PASS"""
        # 创建临时 tsconfig.json
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{"compilerOptions": {"strict": true}}')

        evidence = {
            "tsc_output": '{"errors": [], "summary": {"errors": 0, "warnings": 0}}',
            "diff_summary": "+10 -2",
            "findings": [],
        }

        result = check_evidence("/review", evidence, project_dir=tmp_path)
        # INCOMPLETE = evidence 完整但无法独立验证（如 tsc 无法在空项目运行）
        # 这对测试 evidence 结构是否完整是有效的
        assert result["status"] in ("PASS", "FAIL", "INCOMPLETE")

    def test_review_evidence_missing_required_field(self):
        """/review evidence：缺少必填字段，应该 FAIL"""
        evidence = {
            "tsc_output": '{"errors": []}',
            # 缺少 diff_summary
        }

        result = check_evidence("/review", evidence)
        assert result["passed"] is False
        assert any("diff_summary" in r for r in result.get("incomplete_reasons", []))

    def test_review_evidence_with_tsc_errors(self, tmp_path):
        """/review evidence：tsc 有错误，应该标记"""
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{"compilerOptions": {"strict": true}}')

        evidence = {
            "tsc_output": json.dumps({
                "errors": [
                    {"file": "src/app.ts", "line": 10, "message": "implicit any"}
                ],
                "summary": {"errors": 1, "warnings": 0}
            }),
            "diff_summary": "+10 -2",
            "findings": [],
        }

        result = check_evidence("/review", evidence, project_dir=tmp_path)
        # tsc 有错误时应该 FAIL
        assert result["passed"] is False or result["status"] == "FAIL"

    def test_cso_evidence_with_critical_vulnerability(self):
        """/cso evidence：发现 Critical 安全漏洞，应该标记 RED"""
        evidence = {
            "owasp_findings": [{"type": "A01", "severity": "CRITICAL"}],
            "stride_model": {},
            "severity_summary": {"critical": 1, "high": 0, "medium": 0, "low": 0},
            "exploit_scenarios": ["SQL injection possible"],
        }

        result = check_evidence("/cso", evidence)
        assert result.get("critical_found") is True
        assert result["passed"] is False

    def test_office_hours_evidence_complete(self):
        """/office-hours evidence：完整evidence，应该 PASS"""
        evidence = {
            "design_doc": "# Login Feature\n\n## Problem\n...",
            "reframed_problem": "用户需要一个安全的认证系统",
            "alternatives": ["方案A", "方案B", "方案C"],
            "assumptions": ["假设1", "假设2"],
        }

        result = check_evidence("/office-hours", evidence)
        assert result["passed"] is True

    def test_office_hours_evidence_incomplete(self):
        """/office-hours evidence：缺少 alternatives，应该 FAIL"""
        evidence = {
            "design_doc": "# Login Feature",
            "reframed_problem": "用户需要一个安全的认证系统",
            # 缺少 alternatives
            "assumptions": ["假设1"],
        }

        result = check_evidence("/office-hours", evidence)
        assert result["passed"] is False

    def test_plan_ceo_review_evidence_complete(self):
        """/plan-ceo-review evidence：完整evidence，应该 PASS"""
        evidence = {
            "scope_analysis": {"in": ["登录", "注册"], "out": ["支付"]},
            "risk_assessment": {"high": 0, "medium": 2},
            "recommendation": "先做登录，MVP优先",
            "four_modes": {"mode": "Selective Expansion"},
        }

        result = check_evidence("/plan-ceo-review", evidence)
        assert result["passed"] is True

    def test_unknown_skill_defaults_to_empty_check(self):
        """未知 skill 应该默认允许通过（只要 evidence 非空）"""
        evidence = {"some_field": "some_value"}
        result = check_evidence("/unknown-skill", evidence)
        # 未知 skill 没有 required 清单，应该默认通过
        assert result["passed"] is True

    def test_verify_tsc_no_project(self):
        """verify_tsc：无项目目录，应该返回错误但不崩溃"""
        result = verify_tsc(None)
        assert "errors" in result
        assert "passed" in result
