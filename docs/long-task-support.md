# 超长时间任务支持 — 结构化 Checkpoint 系统

## 问题

Context window 满 → 压缩 → `## Active Task` 丢失 → 继续工作时不知道"上一步做到哪里了"

## 解决原则

**每次完成一个子任务，立即写 checkpoint 文件到磁盘，不依赖 session memory。**

## Checkpoint 格式

```yaml
# ~/Projects/hermes-harness/.checkpoint/当前任务名.yaml
task: "实现 harness-router"
task_id: "router-v1"
started_at: "2026-04-19T10:00:00"
last_checkpoint: "2026-04-19T10:15:00"

# 当前进度（超重要！压缩后第一件事就是读这个）
current_step: 3
total_steps: 7
step_description: "修复 call_router_llm mock 测试"

# 已经完成的步骤（每完成一个就追加）
completed_steps:
  - step: 1
    name: "重写 harness_router.py，移除 MiniMax API 调用"
    completed_at: "2026-04-19T10:05:00"
    artifact: "hermes_harness/harness_router.py"
    git_commit: "7beed37"
  - step: 2
    name: "修复 CLI 参数 --print/-p, --output-format json"
    completed_at: "2026-04-19T10:12:00"
    artifact: "hermes_harness/harness_claude_code.py"
    git_commit: "7beed37"
  - step: 3
    name: "更新 test_harness_router.py mock"
    completed_at: "2026-04-19T10:15:00"
    artifact: "tests/unit/test_harness_router.py"
    # 测试结果
    test_result:
      passed: 12
      failed: 0

# 正在进行的步骤
in_progress:
  step: 3
  started_at: "2026-04-19T10:15:00"
  action: "真实测试 Claude Code 调用"
  command: "python3 -m hermes_harness.harness_claude_code --skill review"

# 下一步（计划）
next_steps:
  - step: 4
    name: "真实测试 Router 调用"
    command: "python3 -m hermes_harness.harness_router '测试路由'"

# 关键文件状态
files_modified:
  - path: "hermes_harness/harness_router.py"
    status: modified
    last_saved: "2026-04-19T10:15:00"
  - path: "hermes_harness/harness_claude_code.py"
    status: modified
    last_saved: "2026-04-19T10:12:00"

# 未解决的问题（需要外部依赖）
open_issues:
  - id: 1
    description: "Claude Code 路径可能因版本更新而变化，需要软链接"
    severity: medium
```

## 工作流

### 开始新任务
```bash
# 1. 创建 checkpoint
./bin/hg checkpoint new "hermes-router-fix" --steps 7

# 2. 开始第一步
# ... 工作 ...
./bin/hg checkpoint done 1 --commit "feat: step 1 done"
```

### 压缩恢复（压缩后第一件事）
```bash
# 压缩后第一句话：
"读取 ~/Projects/hermes-harness/.checkpoint/当前任务.yaml，告诉我当前进度"

# agent 会读取：
# - current_step 和 step_description
# - completed_steps（知道完成了什么）
# - next_steps（知道下一步做什么）
# - open_issues（知道卡在哪里）
```

### 子任务完成
```bash
./bin/hg checkpoint advance 3 --description "真实测试通过" --commit
```

### 任务完成
```bash
./bin/hg checkpoint complete --tag "v1.0"
```

## 实现

```bash
# hg checkpoint 命令
hg checkpoint new <name> --steps N
hg checkpoint advance <step> --description "..."
hg checkpoint done [--commit "msg"]
hg checkpoint status    # 显示当前进度
hg checkpoint recover  # 从 checkpoint 恢复状态
hg checkpoint complete  # 标记任务完成
hg checkpoint log       # 显示所有步骤历史
```

## 为什么比 memory tool 更好

| | memory tool | checkpoint 文件 |
|---|---|---|
| 压缩免疫 | ✅ | ✅ |
| 结构化（可解析） | ❌ 纯文本 | ✅ YAML/JSON |
| 可被命令行读取 | ❌ | ✅ `hg checkpoint status` |
| 包含文件路径 | ❌ | ✅ |
| 包含 git commit | ❌ | ✅ |
| 自动生成 | ❌ 需要手动记忆 | ✅ `./hg checkpoint advance` |
| 跨 session 恢复 | ✅ | ✅ |
