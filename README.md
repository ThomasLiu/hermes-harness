# Hermes Harness

> AI Development Harness for Hermes — 用 MiniMax 2.7 做 Router + Claude Code + gstack skills 做执行的开发工作流

## 项目状态

**开发中** — 核心框架已完成，TDD 测试全部通过

```
pytest tests/ -v
# 44 tests passed (27 unit + 17 integration)
```

## 目录结构

```
hermes-harness/
├── SKILL.md                      # Hermes skill 入口
├── README.md                     # 本文件
├── config.yaml                   # 全局配置
├── pyproject.toml                # Python 项目配置
├── bin/
│   └── hg                        # 主入口脚本（bash）
├── hermes_harness/               # Python 包
│   ├── __init__.py
│   ├── harness_log.py            # 结构化 JSONL 日志
│   ├── harness_checkpoint.py     # Evidence 验证器
│   ├── harness_router.py         # MiniMax Router
│   ├── harness_analyze.py        # 每日性能分析
│   └── harness_claude_code.py    # Claude Code 接口
├── agents/                       # 各 Agent 的定义
│   ├── router/SYSTEM_PROMPT.md
│   └── coder/RULES.md
├── gstack-mappings/
│   └── gstack-mappings.yaml      # skill → evidence 映射
├── logs/                         # 日志存储（运行时创建）
│   ├── critical/
│   ├── normal/
│   └── reports/
├── learn/                        # 学习产出（运行时创建）
│   ├── router/
│   ├── coder/
│   └── shared/
└── requirements/                 # 需求追踪（运行时创建）
```

## 安装

```bash
git clone https://github.com/ThomasLiu/hermes-harness.git ~/Projects/hermes-harness
cd ~/Projects/hermes-harness
./bin/hg init
```

## 测试

```bash
PYTHONPATH=hermes_harness:$PYTHONPATH pytest tests/ -v
```

## 使用

```bash
# 初始化
./bin/hg init

# 启动新任务
./bin/hg new "帮我做一个用户登录功能"

# 查看状态
./bin/hg status

# 需求对齐
./bin/hg align

# 触发学习分析
./bin/hg learn

# 查看性能报告
./bin/hg report

# 运行测试
./bin/hg test
```

## 三色旗机制

| 旗色 | 含义 | 行动 |
|------|------|------|
| 🟢 GREEN | AI 可自主完成 | 直接执行 |
| 🟡 YELLOW | AI 可完成但需用户确认 | 暂停等待输入 |
| 🔴 RED | 危险操作 | 立即人工介入 |

## 四阶段流程

```
STAGE 0: 需求对齐（人类必须参与）
    ↓
STAGE 1: 规划（MiniMax Router + gstack）
    ↓
STAGE 2: 执行与验证（Claude Code + checkpoint）
    ↓
STAGE 3: 最终交付（自动验收门控）
```

## 依赖

- Python 3.8+
- `curl`, `jq`
- Claude Code（用于执行 gstack skills）
- gstack skills（安装在 `~/.claude/skills/gstack`）
- pyyaml（`pip3 install pyyaml`）

## 核心设计

- **MiniMax 做裁判**：深度执行委托给 Claude Code + gstack skills
- **Evidence-based 验证**：每个 checkpoint 必须有独立可验证的证据
- **每日自优化**：结构化日志 + Python 分析脚本 + 规则更新
- **TDD 开发**：所有功能都有对应测试
