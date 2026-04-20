# 开发路线图

## 已完成 MVP

- Docker Compose 全栈。
- PostgreSQL + pgvector schema。
- Go API service。
- Python Agent worker。
- React 看板。
- 最近事故筛选、列表和历史事故切换。
- Runbook 文档列表。
- 模拟故障注入。
- Runbook 检索。
- 证据驱动 RCA 报告。
- 人工审批修复动作。
- Prometheus 和 Grafana 配置。
- 单元测试和合成评测集。

## Phase 1：团队协作和工程加固

- 增加 CI workflow，覆盖 Go、Python、Web 和 Compose 配置。
- 增加 API 集成测试。
- 增加 seed data reset 脚本。
- 补充环境变量说明。
- 补充 PowerShell 和 curl API 示例。已完成基础版，后续可继续扩展更多异常场景。

## Phase 2：Agent 能力增强

- 增加 OpenAI-compatible model provider interface。
- 增加 RCA 和 verifier prompt templates。
- 增加 evidence ID 强制校验，减少幻觉。
- 增加更完整的评测集和评分报告。
- 增加模型耗时、token 和错误率指标。

## Phase 3：后端可靠性

- 增加 JetStream dead-letter queue。
- 增加可配置重试策略。
- 增加 rate limiting middleware。
- 增加结构化请求日志。
- 增加 API、queue、worker、tools 的 OpenTelemetry trace。

## Phase 4：产品体验

- 增加更完整的事故列表页。
- 增加 Runbook 编辑、删除和版本管理。
- 增加动作风险详情。
- 增加 SLI 变化图表。
- 增加演示视频和截图。

## Phase 5：部署能力

- 增加 Kubernetes manifests。
- 增加 Helm chart。
- 增加云部署指南。
- 增加生产安全检查清单。
