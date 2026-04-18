from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

try:
    import asyncpg
except ModuleNotFoundError:
    asyncpg = None

from .embeddings import embedding_literal
from .metrics import TOOL_CALLS, TOOL_LATENCY


TOPOLOGY = {
    "order": ["payment", "inventory", "redis", "postgres"],
    "payment": ["payment-gateway", "postgres"],
    "inventory": ["postgres", "redis"],
}


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {"name": "query_logs", "description": "Return synthetic service logs for an incident window."},
        {"name": "query_metrics", "description": "Return synthetic SLI metrics shaped by active faults."},
        {"name": "get_topology", "description": "Return service dependency topology."},
        {"name": "search_runbook", "description": "Hybrid search over seeded and uploaded runbooks."},
        {"name": "propose_action", "description": "Generate a safe remediation proposal."},
        {"name": "execute_action", "description": "Execute an approved remediation by disabling simulated faults."},
    ]


class MCPToolService:
    """MCP-style tool facade with schemas, audit, timeouts, and deterministic outputs."""

    def __init__(self, db: asyncpg.Pool):
        self.db = db
        self._tools = {
            "query_logs": self.query_logs,
            "query_metrics": self.query_metrics,
            "get_topology": self.get_topology,
            "search_runbook": self.search_runbook,
            "propose_action": self.propose_action,
            "execute_action": self.execute_action,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return tool_catalog()

    async def call_tool(self, name: str, arguments: dict[str, Any], incident_id: str | None = None) -> dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"unknown tool: {name}")

        start = time.perf_counter()
        status = "ok"
        try:
            result = await asyncio.wait_for(self._tools[name](arguments), timeout=8)
            return result
        except Exception:
            status = "error"
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            args_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()[:16]
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tool_audit (incident_id, tool_name, args_hash, status, latency_ms)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    incident_id,
                    name,
                    args_hash,
                    status,
                    latency_ms,
                )
                if incident_id:
                    await conn.execute(
                        """
                        INSERT INTO incident_events (incident_id, event_type, payload)
                        VALUES ($1, $2, $3::jsonb)
                        """,
                        incident_id,
                        "tool.called",
                        json.dumps({"tool": name, "status": status, "latency_ms": latency_ms}),
                    )
            TOOL_CALLS.labels(tool=name, status=status).inc()
            TOOL_LATENCY.labels(tool=name).observe(time.perf_counter() - start)

    async def query_logs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = require_service(arguments)
        faults = await self._active_faults(service)
        lines = [f"INFO service={service} message=health-check-ok"]
        for fault in faults:
            fault_type = fault["fault_type"]
            intensity = fault["intensity"]
            if "timeout" in fault_type:
                lines.append(f"ERROR service={service} event=downstream_timeout elapsed_ms={900 + intensity * 12} retry=exhausted")
            elif "cache" in fault_type:
                lines.append(f"WARN service={service} event=cache_miss_storm hot_key=order:summary miss_rate={min(99, 45 + intensity)}")
            elif "db" in fault_type or "database" in fault_type:
                lines.append(f"WARN service={service} event=slow_query table=reservations lock_wait_ms={500 + intensity * 10}")
            else:
                lines.append(f"ERROR service={service} event={fault_type} intensity={intensity}")
        return {
            "source": "logs",
            "query": f"service={service} active_faults",
            "content": "\n".join(lines),
            "score": 0.86 if faults else 0.42,
        }

    async def query_metrics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = require_service(arguments)
        faults = await self._active_faults(service)
        p95_ms = 90
        error_rate = 0.005
        cache_hit_rate = 0.96
        db_latency_ms = 35
        for fault in faults:
            intensity = fault["intensity"]
            fault_type = fault["fault_type"]
            p95_ms += intensity * 9
            error_rate += intensity / 500
            if "cache" in fault_type:
                cache_hit_rate = max(0.08, cache_hit_rate - intensity / 110)
            if "db" in fault_type or "database" in fault_type:
                db_latency_ms += intensity * 12
        return {
            "source": "metrics",
            "query": f"service={service} sli-window=5m",
            "content": (
                f"service={service} p95_ms={p95_ms} error_rate={error_rate:.3f} "
                f"cache_hit_rate={cache_hit_rate:.2f} db_latency_ms={db_latency_ms}"
            ),
            "score": 0.9 if faults else 0.5,
            "values": {
                "p95_ms": p95_ms,
                "error_rate": round(error_rate, 3),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "db_latency_ms": db_latency_ms,
            },
        }

    async def get_topology(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = require_service(arguments)
        dependencies = TOPOLOGY.get(service, [])
        return {
            "source": "topology",
            "query": f"service={service}",
            "content": f"{service} depends on {', '.join(dependencies)}",
            "score": 0.72,
            "dependencies": dependencies,
        }

    async def search_runbook(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        limit = int(arguments.get("limit", 3))
        if not query:
            raise ValueError("query is required")
        vector = embedding_literal(query)
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT kc.id::text AS id, kd.title, kc.content,
                       greatest(ts_rank_cd(kc.tsv, plainto_tsquery('simple', $1)), 0) AS text_score,
                       (1 - (kc.embedding <=> $2::vector)) AS vector_score
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kd.id = kc.document_id
                ORDER BY (greatest(ts_rank_cd(kc.tsv, plainto_tsquery('simple', $1)), 0) * 0.7
                         + (1 - (kc.embedding <=> $2::vector)) * 0.3) DESC
                LIMIT $3
                """,
                query,
                vector,
                limit,
            )
        chunks = [
            {
                "chunk_id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "score": round(float(row["text_score"] or 0) * 0.7 + float(row["vector_score"] or 0) * 0.3, 3),
            }
            for row in rows
        ]
        content = "\n\n".join(f"{chunk['title']}: {chunk['content']}" for chunk in chunks)
        return {
            "source": "runbook",
            "query": query,
            "content": content or "No runbook matched the query.",
            "score": chunks[0]["score"] if chunks else 0,
            "chunks": chunks,
        }

    async def propose_action(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = require_service(arguments)
        root_cause = str(arguments.get("root_cause", "")).lower()
        action = propose_action_from_root_cause(service, root_cause)
        return {
            "source": "policy",
            "query": root_cause[:120],
            "content": f"Proposed {action['type']} with risk={action['risk_level']}",
            "score": 0.82,
            "action": action,
        }

    async def execute_action(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not arguments.get("approved"):
            raise PermissionError("execute_action requires approval")
        service = require_service(arguments)
        fault_type = str(arguments.get("fault_type", "")).strip()
        async with self.db.acquire() as conn:
            if fault_type:
                result = await conn.execute(
                    "UPDATE faults SET active = false WHERE service = $1 AND active = true AND fault_type = $2",
                    service,
                    fault_type,
                )
            else:
                result = await conn.execute(
                    "UPDATE faults SET active = false WHERE service = $1 AND active = true",
                    service,
                )
        return {
            "source": "executor",
            "query": f"service={service} fault_type={fault_type or '*'}",
            "content": f"Remediation executed: {result}",
            "score": 1.0,
        }

    async def _active_faults(self, service: str) -> list[asyncpg.Record]:
        async with self.db.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, service, fault_type, intensity, details
                FROM faults
                WHERE service = $1 AND active = true
                ORDER BY created_at DESC
                """,
                service,
            )


def require_service(arguments: dict[str, Any]) -> str:
    service = str(arguments.get("service", "")).strip()
    if service not in {"order", "payment", "inventory"}:
        raise ValueError("service must be order, payment, or inventory")
    return service


def propose_action_from_root_cause(service: str, root_cause: str) -> dict[str, Any]:
    if "cache" in root_cause:
        return {
            "type": "warm_cache",
            "params": {"service": service, "fault_type": "cache_stampede", "command": "warm_hot_keys"},
            "risk_level": "low",
            "requires_approval": True,
        }
    if "payment" in root_cause or "timeout" in root_cause:
        return {
            "type": "open_circuit_breaker",
            "params": {"service": service, "fault_type": "payment_timeout", "command": "open_breaker_5m"},
            "risk_level": "medium",
            "requires_approval": True,
        }
    if "database" in root_cause or "slow query" in root_cause or "lock" in root_cause:
        return {
            "type": "enable_degraded_cache",
            "params": {"service": service, "fault_type": "db_slow_query", "command": "enable_stock_cache"},
            "risk_level": "medium",
            "requires_approval": True,
        }
    return {
        "type": "raise_human_review",
        "params": {"service": service, "fault_type": "", "command": "page_oncall"},
        "risk_level": "high",
        "requires_approval": True,
    }
