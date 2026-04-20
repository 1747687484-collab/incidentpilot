# API 调试示例

这份文档用于本地联调和演示。默认 API 地址是 `http://localhost:8080`，启动方式：

```powershell
docker compose up --build
```

## PowerShell 一键演示

仓库提供了脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1
```

脚本会依次执行：

- 检查 API 健康状态。
- 查询已索引 Runbook。
- 注入模拟故障。
- 创建事故。
- 轮询事故状态直到生成根因报告或超时。
- 输出待审批动作。
- 查询最近事故列表。

如果希望脚本自动审批第一条待审批动作：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1 -ApproveAction
```

如果 Docker 还没启动，只想检查脚本将发起哪些请求：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1 -DryRun
```

常用参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-incident.ps1 `
  -ApiBase "http://localhost:8080" `
  -Service order `
  -FaultType cache_stampede `
  -Intensity 82 `
  -Severity SEV2 `
  -PollSeconds 60
```

## 重置本地演示数据

反复演示后，事故、证据链、故障状态和工具审计会越积越多。可以使用重置脚本清理运行数据，同时保留 seed Runbook 和手动上传的 Runbook：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo-data.ps1 -Force
```

脚本默认执行 [reset_demo_data.sql](../db/maintenance/reset_demo_data.sql)，会清理：

- `incidents` 以及级联的事件、证据、Agent 步骤、报告、修复动作。
- `faults` 模拟故障。
- `tool_audit` 工具调用审计。

不会清理：

- `knowledge_documents`
- `knowledge_chunks`

如果只想看将执行的 SQL：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo-data.ps1 -DryRun
```

如果还希望清掉 Redis 里的演示缓存和幂等键：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo-data.ps1 -Force -FlushRedis
```

## PowerShell 手动调用

健康检查：

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/api/healthz"
```

查询 Runbook：

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/api/knowledge/documents?limit=5" |
  ConvertTo-Json -Depth 8
```

注入故障：

```powershell
$faultBody = @{
  service = "order"
  fault_type = "cache_stampede"
  intensity = 82
  details = @{}
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8080/api/simulations/faults" `
  -ContentType "application/json" `
  -Body $faultBody
```

创建事故：

```powershell
$incidentBody = @{
  service = "order"
  symptom = "Order checkout latency is rising and users report intermittent failures."
  severity = "SEV2"
} | ConvertTo-Json -Depth 8

$incident = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8080/api/incidents" `
  -Headers @{ "Idempotency-Key" = [guid]::NewGuid().ToString() } `
  -ContentType "application/json" `
  -Body $incidentBody

$incident | ConvertTo-Json -Depth 10
```

查询事故：

```powershell
$incidentId = $incident.incident.id
Invoke-RestMethod -Uri "http://localhost:8080/api/incidents/$incidentId" |
  ConvertTo-Json -Depth 10
```

查询最近事故并筛选：

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/api/incidents?limit=6&service=order&status=resolved" |
  ConvertTo-Json -Depth 8
```

审批修复动作：

```powershell
$detail = Invoke-RestMethod -Uri "http://localhost:8080/api/incidents/$incidentId"
$actionId = ($detail.actions | Where-Object { $_.status -eq "pending_approval" } | Select-Object -First 1).id

$approvalBody = @{
  action_id = $actionId
  operator = "local-demo"
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8080/api/incidents/$incidentId/approve-action" `
  -ContentType "application/json" `
  -Body $approvalBody
```

## curl 示例

健康检查：

```bash
curl http://localhost:8080/api/healthz
```

查询 Runbook：

```bash
curl "http://localhost:8080/api/knowledge/documents?limit=5"
```

注入故障：

```bash
curl -X POST http://localhost:8080/api/simulations/faults \
  -H "Content-Type: application/json" \
  -d '{"service":"order","fault_type":"cache_stampede","intensity":82,"details":{}}'
```

创建事故：

```bash
curl -X POST http://localhost:8080/api/incidents \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-001" \
  -d '{"service":"order","symptom":"Order checkout latency is rising and users report intermittent failures.","severity":"SEV2"}'
```

查询最近事故：

```bash
curl "http://localhost:8080/api/incidents?limit=6&service=order"
```

## 排障提示

- 如果 PowerShell 报“无法连接到远程服务器”，先确认 Docker Desktop 已启动，再运行 `docker compose ps`。
- 如果 `POST /api/incidents` 返回同一条事故，检查是否复用了同一个 `Idempotency-Key`。
- 如果事故一直停在 `queued`，检查 `agent-worker` 容器日志。
- 如果审批后状态没有变化，等待 3 到 5 秒后重新查询事故详情。
- 如果演示数据太多，运行 `scripts/reset-demo-data.ps1 -Force` 后重新演示。
