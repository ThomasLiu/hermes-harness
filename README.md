# Hermes Harness

> AI Development Harness for Hermes — 用 MiniMax 2.7 做 Router + Claude Code + gstack skills 做执行的开发工作流

**设计文档**: [hermes-harness-design.md](./hermes-harness-design.md)

## 目录结构

```
hermes-harness/
├── SKILL.md                      # Hermes skill 入口
├── README.md                     # 本文件
├── config.yaml                   # 全局配置
├── bin/                          # 可执行脚本
│   ├── hg                        # 主入口（bash）
│   ├── harness-log.py            # 结构化日志
│   ├── harness-checkpoint.py     # Checkpoint 验证器
│   ├── harness-analyze.py        # 每日性能分析
│   └── harness-claude-code.py    # Claude Code 接口
├── agents/                       # 各 Agent 的定义
│   ├── router/
│   │   └── SYSTEM_PROMPT.md
│   ├── coder/
│   │   └── RULES.md
│   ├── reviewer/
│   └── qa/
├── gstack-mappings/
│   └── gstack-mappings.yaml      # skill → evidence 映射
├── logs/                          # 日志存储
│   ├── critical/
│   ├── normal/
│   └── reports/
├── learn/                         # 学习产出
│   ├── router/
│   ├── coder/
│   ├── reviewer/
│   └── shared/
└── requirements/                  # 需求追踪
```

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/hermes-harness.git ~/.hermes/harness
cd ~/.hermes/harness
./bin/hg init
```

## 使用

```bash
# 启动新任务
hg new "帮我做一个用户登录功能"

# 查看状态
hg status

# 触发验证
hg verify

# 查看性能报告
hg report

# 触发学习分析
hg learn
```

## 四阶段流程

```
STAGE 0: 需求对齐（人类必须参与）
    ↓
STAGE 1: 规划（MiniMax + Claude Code + gstack）
    ↓
STAGE 2: 执行与验证（AI 自主，人类不看过程）
    ↓
STAGE 3: 最终交付（自动验收门控）
```

详见 [hermes-harness-design.md](./hermes-harness-design.md)

## 依赖

- Python 3.8+
- `curl`, `jq`
- Claude Code（用于执行 gstack skills）
- gstack（安装在 `~/.claude/skills/gstack`）

## 状态

**开发中** — 核心框架已搭建，Phase 0-1 可运行

- [x] 最小可运行脚本 (`hg` 入口)
- [x] 结构化日志 (`harness-log.py`)
- [x] Checkpoint 验证器 (`harness-checkpoint.py`)
- [x] 每日分析脚本 (`harness-analyze.py`)
- [x] gstack skill 映射配置
- [ ] MiniMax Router 集成（待实现）
- [ ] Claude Code subprocess 集成（待测试）
- [ ] 需求追踪链（待实现）
- [ ] EXPLORE/OPTIMIZE 双模式（待实现）
