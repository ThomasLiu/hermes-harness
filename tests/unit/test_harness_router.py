"""
Tests for harness-router.py
TDD: Router 决策逻辑、call_router_llm mock
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from harness_router import route_task, build_router_prompt, _default_router_system

class TestRouterBuildPrompt:
    """Router prompt 构建测试"""

    def test_build_prompt_with_context(self):
        """带 context 的 prompt 构建"""
        prompt = build_router_prompt("帮我写一个登录功能", {"project": "myapp"})
        assert "帮我写一个登录功能" in prompt
        assert "myapp" in prompt
        assert "Intent Classification" in prompt

    def test_build_prompt_without_context(self):
        """不带 context 的 prompt 构建"""
        prompt = build_router_prompt("修复bug")
        assert "修复bug" in prompt
        assert "Context" not in prompt or "null" in prompt or "{}" in prompt

    def test_default_system_includes_routing_rules(self):
        """默认 system prompt 包含路由规则"""
        system = _default_router_system()
        assert "GREEN" in system
        assert "YELLOW" in system
        assert "RED" in system
        assert "/office-hours" in system

class TestRouterDecision:
    """Router 决策测试（mock call_router_llm）"""

    @patch("harness_router.call_router_llm")
    def test_route_explore_task(self, mock_call):
        """探索任务应该路由到 /office-hours"""
        mock_call.return_value = json.dumps({
            "intent": "EXPLORE",
            "skill": "/office-hours",
            "flag": "GREEN",
            "reason": "New feature, needs planning first",
            "confidence": 0.9
        })

        result = route_task("实现一个新的支付模块")
        assert result["intent"] == "EXPLORE"
        assert result["skill"] == "/office-hours"
        assert result["flag"] == "GREEN"
        assert result["confidence"] == 0.9

    @patch("harness_router.call_router_llm")
    def test_route_optimize_task(self, mock_call):
        """优化任务应该路由到 /review"""
        mock_call.return_value = json.dumps({
            "intent": "OPTIMIZE",
            "skill": "/review",
            "flag": "GREEN",
            "reason": "Known task, improve performance",
            "confidence": 0.85
        })

        result = route_task("优化数据库查询性能")
        assert result["intent"] == "OPTIMIZE"
        assert result["skill"] == "/review"

    @patch("harness_router.call_router_llm")
    def test_route_review_task(self, mock_call):
        """Review 任务路由到 /review"""
        mock_call.return_value = json.dumps({
            "intent": "REVIEW",
            "skill": "/review",
            "flag": "YELLOW",
            "reason": "Code review, human should confirm findings",
            "confidence": 0.8
        })

        result = route_task("审查 src/auth.py 的安全性")
        assert result["intent"] == "REVIEW"
        assert result["flag"] == "YELLOW"

    @patch("harness_router.call_router_llm")
    def test_route_red_flag_task(self, mock_call):
        """危险任务应该 RED"""
        mock_call.return_value = json.dumps({
            "intent": "EXPLORE",
            "skill": "/office-hours",
            "flag": "RED",
            "reason": "Production database migration, human must supervise",
            "confidence": 0.95
        })

        result = route_task("直接修改生产数据库")
        assert result["flag"] == "RED"

    @patch("harness_router.call_router_llm")
    def test_api_failure_graceful_degradation(self, mock_call):
        """MiniMax API 失败时优雅降级"""
        mock_call.side_effect = RuntimeError("API timeout")

        result = route_task("测试任务")
        assert result["intent"] == "UNKNOWN"
        assert result["skill"] == "/office-hours"
        assert result["flag"] == "YELLOW"
        assert "error" in result

    @patch("harness_router.call_router_llm")
    def test_invalid_json_response_fallback(self, mock_call):
        """MiniMax 返回非 JSON 时降级"""
        mock_call.return_value = "Oops, something went wrong"

        result = route_task("测试任务")
        assert result["intent"] == "UNKNOWN"
        assert result["flag"] == "YELLOW"
        assert "raw_response" in result

    @patch("harness_router.call_router_llm")
    def test_missing_fields_in_response(self, mock_call):
        """MiniMax 响应缺少字段时补默认值"""
        mock_call.return_value = json.dumps({
            "intent": "EXPLORE",
            "skill": "/review"
            # 缺少 flag, reason, confidence
        })

        result = route_task("测试")
        assert result["flag"] == "YELLOW"  # 默认值
        assert result["reason"] == ""  # 默认空

    @patch("harness_router.call_router_llm")
    def test_invalid_flag_normalized(self, mock_call):
        """无效的 flag 值被规范化为 YELLOW"""
        mock_call.return_value = json.dumps({
            "intent": "EXPLORE",
            "skill": "/review",
            "flag": "ORANGE",  # 无效值
            "reason": "test"
        })

        result = route_task("test")
        assert result["flag"] == "YELLOW"  # 规范化

    @patch("harness_router.call_router_llm")
    def test_json_code_block_extraction(self, mock_call):
        """从 markdown 代码块中提取 JSON"""
        mock_call.return_value = """Here is the routing decision:

```json
{
  "intent": "EXPLORE",
  "skill": "/office-hours",
  "flag": "GREEN",
  "reason": "New task needs planning",
  "confidence": 0.85
}
```

Based on the analysis..."""

        result = route_task("实现新功能")
        assert result["intent"] == "EXPLORE"
        assert result["confidence"] == 0.85
