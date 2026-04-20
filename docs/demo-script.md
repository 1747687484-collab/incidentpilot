# 演示脚本

## 2-3 分钟演示流程

1. 启动项目：

   ```bash
   docker compose up --build
   ```

   如果只想先跑 API 链路，也可以使用 PowerShell 演示脚本：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1
   ```

2. 打开 Web 看板：

   ```text
   http://localhost:5173
   ```

3. 注入 `order / cache_stampede` 故障，强度设为 `82`。

4. 创建一条 `order` 事故，使用默认 checkout latency 症状。

5. 在最近事故列表按 `order` 或 `running` 筛选，说明历史事故支持快速定位。

6. 说明链路：

   - Go API 写入事故。
   - API 发布 `incident.created` 到 NATS JetStream。
   - Python worker 消费任务。
   - 前端通过 SSE 实时看到 Agent 步骤。

7. 观察 Agent 时间线：

   - `triage_agent` 判断事故类型。
   - `evidence_agent` 查询日志、指标、拓扑和 Runbook。
   - `rca_agent` 输出根因。
   - `verifier_agent` 校验证据覆盖。
   - `action_agent` 生成待审批修复动作。

8. 展示证据链：

   - 日志中出现 cache miss storm。
   - 指标中 p95、error rate 升高，cache hit rate 下降。
   - 拓扑显示 `order` 依赖 Redis。
   - Runbook 命中 cache stampede 文档。

9. 展示已索引 Runbook 列表，说明知识库可由团队持续维护。

10. 点击审批动作，说明写操作不会由 Agent 直接执行，必须人工确认。

11. 观察事故状态变为 `resolved`。

12. 打开 Prometheus 或 Grafana，说明 API 和 Agent 工具调用指标。

## 面试讲解重点

- 这个项目不是聊天机器人，而是一个有队列、状态、审批、审计和可观测性的工程系统。
- Agent 不是直接“猜答案”，而是通过工具收集证据，再输出带引用的 RCA。
- 写操作和推理分离，所有修复动作默认需要审批。
- 当前默认不依赖 LLM，方便本地稳定演示；后续可以接入 OpenAI-compatible 模型。
