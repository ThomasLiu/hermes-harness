# Hermes Harness — AI Development Harness for Hermes

> 让 Hermes 通过 Claude Code + gstack skills 执行完整的开发工作流
> MiniMax 2.7 作为 Router + Validator，不做深度执行

## 核心概念

**Harness** 是 AI coding agent 的执行框架——它定义 agent 如何接收任务、如何分解、如何验证、如何学习。

本 harness 的核心理念：
- **MiniMax 做裁判，不做选手** — 深度执行委托给 Claude Code + gstack
- **三色旗机制** — GREEN（AI自主）/ YELLOW（等用户）/ RED（强制介入）
- **Evidence-based 验证** — 每个 checkpoint 必须有独立可验证的证据
- **每日自优化** — 结构化日志 + 脚本分析 + 规则更新

## 快速开始

```bash
cd ~/Projects/hermes-harness

# 初始化
./bin/hg init

# 启动新任务
./bin/hg new "帮我做一个用户登录功能"
./bin/hg status      # 查看当前任务状态
./bin/hg align       # 完成需求对齐
./bin/hg learn       # 触发学习分析
./bin/hg report      # 查看今日性能报告

# 运行测试
PYTHONPATH=hermes_harness:$PYTHONPATH pytest tests/ -v
```

## 项目结构

```
hermes-harness/
├── bin/
│   └── hg              # 主入口脚本
├── hermes_harness/     # Python 包
│   ├── __init__.py
│   ├── harness_log.py      # 结构化 JSONL 日志
│   ├── harness_checkpoint.py  # Evidence 验证器
│   ├── harness_router.py   # MiniMax Router
│   ├── harness_analyze.py  # 每日性能分析
│   └── harness_claude_code.py  # Claude Code 接口
├── agents/
│   ├── router/SYSTEM_PROMPT.md
│   └── coder/RULES.md
├── gstack-mappings/gstack-mappings.yaml
├── tests/
│   ├── unit/          # 单元测试
│   └── integration/   # 端到端测试
├── config.yaml
└── pyproject.toml
```

## 测试

```bash
PYTHONPATH=hermes_harness:$PYTHONPATH pytest tests/ -v
# 当前: 44 tests, 全部通过
```

## 可用命令

| 命令 | 功能 |
|------|------|
| `hg init` | 初始化 harness 环境 |
| `hg new <需求>` | 启动新任务，创建需求文档 |
| `hg status` | 查看当前任务状态 + 三色旗 |
| `hg align` | 交互式需求对齐 |
| `hg verify` | 手动触发 checkpoint 验证 |
| `hg deploy` | 执行 /ship + /land-and-deploy |
| `hg report` | 查看今日性能报告 |
| `hg handoff` | 查看 handoff 历史 |
| `hg learn` | 触发学习分析 |
| `hg test` | 运行 pytest 测试 |
| `hg rollback` | 回滚上一次部署 |
