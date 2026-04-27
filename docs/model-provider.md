# 模型 Provider 接入说明

IncidentPilot 默认使用确定性 RCA 工作流，不需要任何模型 Key。需要展示 Agent 推理能力时，可以开启 OpenAI-compatible Provider，让 `rca_agent` 使用模型生成根因草稿，再由系统校验证据引用并写入报告。

## 默认行为

默认配置：

```env
LLM_PROVIDER=disabled
```

此时 worker 会继续使用内置规则：

- `triage_agent` 根据症状和模拟故障分类。
- `evidence_agent` 调用工具收集日志、指标、拓扑和 Runbook。
- `rca_agent` 使用确定性规则生成根因。
- `verifier_agent` 校验证据数量和置信度。
- `action_agent` 生成待审批动作。

## 启用模型

在项目根目录创建 `.env`，填入兼容 OpenAI Chat Completions 的服务：

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=replace-with-your-key
LLM_MODEL=replace-with-provider-model
LLM_TIMEOUT_SECONDS=12
LLM_MAX_TOKENS=700
LLM_TEMPERATURE=0.1
```

然后重启 worker：

```powershell
docker compose up --build -d agent-worker
```

兼容方向：

- OpenAI-compatible API。
- DeepSeek 兼容接口。
- 本地 Ollama 的 OpenAI-compatible endpoint。
- 腾讯混元或其他内部兼容封装。

## 安全边界

模型只参与 RCA 文本生成，不直接执行写操作。

实现上的边界：

- `LLM_API_KEY` 只作为 HTTP Authorization header 使用，不写入 prompt、数据库或事件流。
- prompt 只包含事故字段、分类结果和已收集证据。
- 模型必须返回 JSON。
- `evidence_ids` 必须来自系统提供的证据 ID，且至少引用 2 条证据。
- 模型失败、超时、返回无效 JSON 或证据引用不合格时，系统自动回退到确定性 RCA。
- 修复动作仍由 `action_agent` 生成，并且默认需要人工审批。

## 模型输出格式

模型必须返回：

```json
{
  "root_cause": "order service cache stampede is supported by logs and metrics.",
  "confidence": 0.86,
  "evidence_ids": ["evidence-id-1", "evidence-id-2"],
  "limitations": ["synthetic telemetry only"]
}
```

系统会校验：

- `root_cause` 不能为空。
- `confidence` 会被限制在 `0.05` 到 `0.95`。
- `evidence_ids` 必须是本次事故已写入的证据 ID。
- `limitations` 最多保留 5 条。

## 可观测性

worker 暴露以下 Prometheus 指标：

- `incidentpilot_agent_llm_calls_total{provider,status}`
- `incidentpilot_agent_llm_duration_seconds{provider}`

`status` 常见值：

- `ok`：模型返回有效 RCA。
- `fallback`：模型调用失败或输出不合格，系统回退到确定性 RCA。

## 本地验证

不开模型也能验证主链路：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1 -ApproveAction
```

启用模型后，可以在 Web 看板的 Agent timeline 中看到 `rca_agent / llm_root_cause` 步骤。失败时会出现 `fallback` 状态，报告仍会继续生成。
