# Hermes Harness — Coder Agent Rules

## 执行原则

1. **每次修改必须携带 evidence** — 不能只说「改了」，要说「改了哪里+为什么」
2. **大文件优先 split** — >200 LOC 的文件先 split 再处理（避免 hash mismatch）
3. **每个 task 声明 AC 映射** — 「实现 T001，对应 AC1」
4. **Checkpoint 验证后才能继续** — 不能跳过验证步骤

## 效率规则

### 大文件处理
- 文件 > 200 LOC → 自动请求 MiniMax split 决策
- 大文件修改前先运行 `tsc --noEmit`，将错误列表加入 context
- 大文件修改后额外运行一次 `/review`

### 重试规则
- Hash mismatch 导致编辑失败 → 重试 1 次（全文件刷新）
- 连续 2 次 hash mismatch → 标记 STUCK，触发 handoff
- 任何 checkpoint FAIL → 修复后再继续，不跳过

## 学习记录

每次实现完成后，记录到 `learn/coder/implementation_log.jsonl`：
```jsonl
{"task_id": "R001", "file": "src/api.js", "lines_changed": 45, "ac_mapping": "T001", "review_status": "PASS|FAIL", "timestamp": "..."}
```

## Antipattern（避免的模式）

- 不要在实现过程中改变 scope
- 不要跳过 review 直接提交
- 不要忽略 tsc 错误继续运行
- 不要在没有 evidence 的情况下说「测试通过了」
