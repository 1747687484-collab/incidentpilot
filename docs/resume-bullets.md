# 简历描述参考

## 后端开发实习版本

- 设计并实现 IncidentPilot 多 Agent AIOps 智能排障平台，技术栈包括 Go、PostgreSQL/pgvector、Redis、NATS JetStream、Python、React、Prometheus、Grafana 和 Docker Compose。
- 实现事故创建、SSE 实时事件流、持久化任务分发、幂等审批、证据链存储和根因报告查询等核心后端能力。
- 构建模拟故障注入、压测脚本、指标看板和 worker 消费链路，展示分布式后端系统的可靠性设计。

## Agent 应用开发实习版本

- 设计多 Agent RCA 工作流，包含 triage、evidence collection、Runbook RAG retrieval、verification 和 human-approved action execution。
- 实现 MCP-style tools，支持日志查询、指标查询、拓扑查询、知识库检索、动作建议和安全执行，并记录工具调用审计。
- 构建覆盖 cache stampede、payment timeout、database slow query 的离线评测集，默认根因命中率达到 80% 以上。

## 面试一句话介绍

IncidentPilot 是一个面向微服务故障排查的多 Agent AIOps 平台：它通过工具收集证据，用 Agent 工作流生成根因报告，并通过人工审批机制保证修复动作安全可控。

