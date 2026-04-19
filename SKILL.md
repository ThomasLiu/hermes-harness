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
# 安装
git clone https://github.com/thomas(你的username)/hermes-harness.git ~/.hermes/harness

# 在 Hermes 中激活 skill
# 运行 /harness-init 完成初始化

# 使用
/hg new "帮我做一个用户登录功能"
/hg status      # 查看当前任务状态
/hg verify      # 手动触发 checkpoint 验证
/hg report      # 查看今日性能报告
```

## 可用命令

| 命令 | 功能 |
|------|------|
| `/hg new <需求>` | 启动新任务，走完整四阶段流程 |
| `/hg status` | 查看当前任务状态 + 三色旗 |
| `/hg verify` | 手动触发 checkpoint 验证 |
| `/hg report` | 查看今日性能报告 |
| `/hg align` | 交互式需求对齐 |
| `/hg deploy` | 执行 /ship + /land-and-deploy |
| `/hg handoff` | 查看 handoff 历史 |
| `/hg learn` | 触发学习分析（通常每日自动） |
| `/hg rollback` | 回滚上一次部署 |
