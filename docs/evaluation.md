# 评测说明

默认 Agent 工作流是确定性的，因此不需要 LLM Key 也能评测。

## 当前评测指标

- 根因命中率：使用 `tests/agent_eval/eval_cases.json` 中的 20 条合成样例。
- 证据覆盖率：每个完成报告至少引用 2 条 evidence。
- 安全性：所有修复动作在执行前必须是 `pending_approval`。
- 幂等性：重复审批同一个动作不会重复执行。

## 当前验收目标

- 根因命中率不低于 80%。
- `POST /api/incidents` 在 100 VU 压测下 p95 小于 200ms。
- worker 重启后，JetStream 中未处理任务不丢失。
- 端到端链路能完成：故障注入 -> 事故创建 -> RCA -> 审批 -> resolved。

## 运行评测

```bash
python tests/agent_eval/run_eval.py
```

期望输出类似：

```text
hit_rate=100.00% cases=20
```

## 后续 LLM 版本评测

- 将 `derive_root_cause` 替换为 OpenAI-compatible 模型调用。
- 保留 verifier 阶段做确定性安全校验。
- 增加“没有 evidence IDs 就失败”的幻觉检查。
- 记录模型延迟、token、错误率和置信度分布。

