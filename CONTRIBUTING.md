# 贡献指南

IncidentPilot 按多人协作项目组织。每次改动都应该小而清晰，能被测试，能被队友快速理解。不要把多个不相关的功能塞进同一个 PR。

## 分支规范

使用短而明确的分支名：

```text
feature/incident-list
fix/action-idempotency
docs/architecture-update
test/agent-eval-cases
```

## 提交规范

建议使用类似 Conventional Commits 的格式：

```text
feat(api): add incident list endpoint
fix(worker): avoid duplicate action execution
docs: add product requirements
test(agent): add payment timeout cases
chore: update compose config
```

常用前缀：

- `feat`：新增功能。
- `fix`：修复 bug。
- `docs`：文档修改。
- `test`：测试或评测集修改。
- `refactor`：不改变行为的代码整理。
- `chore`：依赖、配置、CI 等杂项。

## PR 要求

每个 PR 至少说明：

- 改了什么。
- 为什么要改。
- 如何测试。
- 是否影响 API、数据库 schema、Docker Compose 或前端交互。
- 是否有后续工作。

如果涉及 UI 或 API，建议附截图、请求示例或响应结果。

## 模块归属

- `services/api-service`：后端/API 负责人。
- `services/agent-worker`：Agent/workflow 负责人。
- `services/web`：前端负责人。
- `db/init`：数据模型负责人。
- `configs`：基础设施/可观测性负责人。
- `tests`：测试和评测负责人。
- `docs`：产品需求和架构文档负责人。

## 本地检查

根据修改范围运行对应检查：

```bash
docker compose config --quiet
docker run --rm -v ${PWD}/services/api-service:/src -w /src golang:1.23-alpine go test ./...
docker run --rm -v ${PWD}/services/agent-worker:/app -w /app incidentpilot-agent-worker python -m pytest
cd services/web && npm install && npm run build
python tests/agent_eval/run_eval.py
```

## Code Review 清单

- 是否保持了公开 API 兼容性？
- 写操作是否仍然需要人工审批？
- 工具调用是否有审计记录？
- 是否需要更新 README 或 docs？
- 队友是否能在没有私有凭证的情况下运行项目？
- 是否引入了与当前任务无关的大改动？

## 安全边界

- 不接入真实生产系统。
- 不提交 `.env` 或任何密钥。
- 不在 prompt、日志或数据库里写入敏感配置。
- 默认修复动作只修改模拟故障数据，不操作宿主机或真实资源。

