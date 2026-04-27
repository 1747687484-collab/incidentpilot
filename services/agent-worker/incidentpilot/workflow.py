from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any
from uuid import UUID

try:
    import asyncpg
except ModuleNotFoundError:
    asyncpg = None

from .llm import LLMClient
from .metrics import LLM_CALLS, LLM_LATENCY, WORKFLOW_RUNS
from .prompts import build_rca_messages
from .tools import MCPToolService

logger = logging.getLogger(__name__)


class AgentWorkflow:
    def __init__(self, db: asyncpg.Pool, tools: MCPToolService, llm_client: LLMClient | None = None):
        self.db = db
        self.tools = tools
        self.llm_client = llm_client

    async def process_incident(self, incident_id: str) -> None:
        started = time.perf_counter()
        try:
            incident = await self._load_incident(incident_id)
            await self._update_status(incident_id, "running")
            await self._event(incident_id, "agent.started", {"workflow": "multi_agent_rca"})

            issue_type = await self._triage(incident)
            evidence_ids = await self._collect_evidence(incident, issue_type)
            root_cause, confidence, limitations = await self._rca(incident, issue_type, evidence_ids)
            await self._verify(incident, confidence, evidence_ids)
            action_id = await self._propose_action(incident, root_cause)
            await self._write_report(incident_id, root_cause, confidence, evidence_ids, [action_id], limitations)

            await self._update_status(incident_id, "awaiting_approval")
            await self._event(
                incident_id,
                "report.ready",
                {
                    "root_cause": root_cause,
                    "confidence": confidence,
                    "recommended_actions": [action_id],
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            WORKFLOW_RUNS.labels(status="ok").inc()
        except Exception as exc:
            logger.exception("incident workflow failed", extra={"incident_id": incident_id})
            await self._update_status(incident_id, "failed")
            await self._event(incident_id, "agent.failed", {"error": str(exc)})
            WORKFLOW_RUNS.labels(status="error").inc()
            raise

    async def process_approved_action(self, incident_id: str, action_id: str, operator: str) -> None:
        action = await self._load_action(incident_id, action_id)
        if action["status"] == "executed":
            await self._event(incident_id, "action.execution.skipped", {"action_id": action_id, "reason": "already_executed"})
            return

        raw_params = action["params"]
        params = json.loads(raw_params) if isinstance(raw_params, str) else dict(raw_params)
        params["approved"] = True
        await self._event(incident_id, "action.execution.started", {"action_id": action_id, "operator": operator})
        await self._insert_step(incident_id, "action_agent", "execute_action", params, "Executing approved remediation action", "running", 0)
        result = await self.tools.call_tool("execute_action", params, incident_id=incident_id)
        async with self.db.acquire() as conn:
            await conn.execute("UPDATE remediation_actions SET status = 'executed' WHERE incident_id = $1 AND id = $2", incident_id, action_id)
            await conn.execute("UPDATE incidents SET status = 'resolved' WHERE id = $1", incident_id)
        await self._insert_step(incident_id, "action_agent", "execute_action", params, result["content"], "completed", 0)
        await self._event(incident_id, "action.executed", {"action_id": action_id, "result": result["content"]})

    async def _triage(self, incident: asyncpg.Record) -> str:
        faults = await self._active_faults(incident["service"])
        issue_type = classify_issue(incident["service"], incident["symptom"], [dict(row) for row in faults])
        await self._insert_step(
            incident["id"],
            "triage_agent",
            "",
            {"service": incident["service"], "symptom": incident["symptom"]},
            f"Classified incident as {issue_type}",
            "completed",
            0,
        )
        return issue_type

    async def _collect_evidence(self, incident: asyncpg.Record, issue_type: str) -> list[str]:
        service = incident["service"]
        calls = [
            ("query_logs", {"service": service}),
            ("query_metrics", {"service": service}),
            ("get_topology", {"service": service}),
            ("search_runbook", {"query": f"{service} {issue_type} {incident['symptom']}", "limit": 3}),
        ]
        evidence_ids: list[str] = []
        for tool_name, args in calls:
            started = time.perf_counter()
            result = await self.tools.call_tool(tool_name, args, incident_id=incident["id"])
            evidence_id = await self._insert_evidence(incident["id"], result)
            evidence_ids.append(evidence_id)
            await self._insert_step(
                incident["id"],
                "evidence_agent",
                tool_name,
                args,
                summarize(result["content"]),
                "completed",
                int((time.perf_counter() - started) * 1000),
            )
        return evidence_ids

    async def _rca(self, incident: asyncpg.Record, issue_type: str, evidence_ids: list[str]) -> tuple[str, float, list[str]]:
        if self.llm_client and self.llm_client.enabled:
            draft = await self._rca_with_llm(incident, issue_type, evidence_ids)
            if draft:
                return draft

        faults = await self._active_faults(incident["service"])
        root_cause = derive_root_cause(incident["service"], issue_type, [dict(row) for row in faults])
        confidence = 0.86 if len(evidence_ids) >= 3 and faults else 0.68
        limitations = ["synthetic telemetry only", "manual approval required for write actions"]
        await self._insert_step(
            incident["id"],
            "rca_agent",
            "",
            {"issue_type": issue_type, "evidence_ids": evidence_ids},
            root_cause,
            "completed",
            0,
        )
        return root_cause, confidence, limitations

    async def _rca_with_llm(
        self,
        incident: asyncpg.Record,
        issue_type: str,
        evidence_ids: list[str],
    ) -> tuple[str, float, list[str]] | None:
        evidence = await self._load_evidence_by_ids(incident["id"], evidence_ids)
        messages = build_rca_messages(dict(incident), issue_type, evidence)
        started = time.perf_counter()
        provider = self.llm_client.provider if self.llm_client else "disabled"
        try:
            draft = await self.llm_client.generate_root_cause(messages, set(evidence_ids))  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("llm rca failed; using deterministic fallback", extra={"incident_id": incident["id"], "provider": provider})
            LLM_CALLS.labels(provider=provider, status="fallback").inc()
            LLM_LATENCY.labels(provider=provider).observe(time.perf_counter() - started)
            await self._insert_step(
                incident["id"],
                "rca_agent",
                "llm_root_cause",
                {"issue_type": issue_type, "evidence_ids": evidence_ids, "provider": provider},
                f"LLM RCA failed; using deterministic fallback: {type(exc).__name__}",
                "fallback",
                int((time.perf_counter() - started) * 1000),
            )
            return None

        LLM_CALLS.labels(provider=draft.provider, status="ok").inc()
        LLM_LATENCY.labels(provider=draft.provider).observe(time.perf_counter() - started)
        limitations = merge_limitations(
            draft.limitations,
            [
                f"LLM provider: {draft.provider}",
                "manual approval required for write actions",
            ],
        )
        await self._insert_step(
            incident["id"],
            "rca_agent",
            "llm_root_cause",
            {"issue_type": issue_type, "evidence_ids": draft.evidence_ids, "provider": draft.provider},
            draft.root_cause,
            "completed",
            int((time.perf_counter() - started) * 1000),
        )
        return draft.root_cause, draft.confidence, limitations

    async def _verify(self, incident: asyncpg.Record, confidence: float, evidence_ids: list[str]) -> None:
        status = "completed" if confidence >= 0.6 and len(evidence_ids) >= 2 else "needs_review"
        summary = "Evidence coverage is sufficient for a bounded remediation proposal."
        if status != "completed":
            summary = "Evidence coverage is weak; require human review."
        await self._insert_step(
            incident["id"],
            "verifier_agent",
            "",
            {"confidence": confidence, "evidence_count": len(evidence_ids)},
            summary,
            status,
            0,
        )

    async def _propose_action(self, incident: asyncpg.Record, root_cause: str) -> str:
        result = await self.tools.call_tool(
            "propose_action",
            {"service": incident["service"], "root_cause": root_cause},
            incident_id=incident["id"],
        )
        action = result["action"]
        action_id = await self._insert_action(incident["id"], action)
        await self._insert_step(
            incident["id"],
            "action_agent",
            "propose_action",
            {"root_cause": root_cause},
            f"Proposed action {action['type']} and is waiting for approval.",
            "completed",
            0,
        )
        await self._event(incident["id"], "action.proposed", {"action_id": action_id, **action})
        return action_id

    async def _load_incident(self, incident_id: str) -> asyncpg.Record:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id::text, service, symptom, severity, status, created_at
                FROM incidents
                WHERE id = $1
                """,
                incident_id,
            )
        if not row:
            raise ValueError(f"incident not found: {incident_id}")
        return row

    async def _load_action(self, incident_id: str, action_id: str) -> asyncpg.Record:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id::text, type, params, risk_level, requires_approval, status
                FROM remediation_actions
                WHERE incident_id = $1 AND id = $2
                """,
                incident_id,
                action_id,
            )
        if not row:
            raise ValueError(f"action not found: {action_id}")
        return row

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

    async def _load_evidence_by_ids(self, incident_id: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
        if not evidence_ids:
            return []
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id::text, source, query, content, score, timestamp
                FROM evidence
                WHERE incident_id = $1 AND id = ANY($2::uuid[])
                ORDER BY timestamp ASC
                """,
                incident_id,
                [UUID(value) for value in evidence_ids],
            )
        return [dict(row) for row in rows]

    async def _insert_evidence(self, incident_id: str, result: dict[str, Any]) -> str:
        async with self.db.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO evidence (incident_id, source, query, content, score)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id::text
                """,
                incident_id,
                result["source"],
                result["query"],
                result["content"],
                float(result.get("score", 0)),
            )

    async def _insert_step(
        self,
        incident_id: str,
        agent_name: str,
        tool_name: str,
        input_payload: dict[str, Any],
        output_summary: str,
        status: str,
        latency_ms: int,
    ) -> None:
        input_hash = hashlib.sha256(json.dumps(input_payload, sort_keys=True).encode()).hexdigest()[:16]
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_steps
                  (incident_id, agent_name, tool_name, input_hash, output_summary, latency_ms, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                incident_id,
                agent_name,
                tool_name,
                input_hash,
                output_summary,
                latency_ms,
                status,
            )
        await self._event(
            incident_id,
            "agent.step",
            {"agent_name": agent_name, "tool_name": tool_name, "summary": output_summary, "status": status},
        )

    async def _insert_action(self, incident_id: str, action: dict[str, Any]) -> str:
        key_material = f"{incident_id}:{action['type']}:{json.dumps(action['params'], sort_keys=True)}"
        idempotency_key = hashlib.sha256(key_material.encode()).hexdigest()[:24]
        async with self.db.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO remediation_actions
                  (incident_id, type, params, risk_level, requires_approval, status, idempotency_key)
                VALUES ($1, $2, $3::jsonb, $4, $5, 'pending_approval', $6)
                ON CONFLICT (idempotency_key) DO UPDATE
                SET updated_at = now()
                RETURNING id::text
                """,
                incident_id,
                action["type"],
                json.dumps(action["params"]),
                action["risk_level"],
                bool(action["requires_approval"]),
                idempotency_key,
            )

    async def _write_report(
        self,
        incident_id: str,
        root_cause: str,
        confidence: float,
        evidence_ids: list[str],
        action_ids: list[str],
        limitations: list[str],
    ) -> None:
        evidence_uuid = [UUID(value) for value in evidence_ids]
        action_uuid = [UUID(value) for value in action_ids]
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO root_cause_reports
                  (incident_id, root_cause, confidence, evidence_ids, recommended_actions, limitations)
                VALUES ($1, $2, $3, $4::uuid[], $5::uuid[], $6::text[])
                ON CONFLICT (incident_id) DO UPDATE
                SET root_cause = EXCLUDED.root_cause,
                    confidence = EXCLUDED.confidence,
                    evidence_ids = EXCLUDED.evidence_ids,
                    recommended_actions = EXCLUDED.recommended_actions,
                    limitations = EXCLUDED.limitations,
                    created_at = now()
                """,
                incident_id,
                root_cause,
                confidence,
                evidence_uuid,
                action_uuid,
                limitations,
            )

    async def _update_status(self, incident_id: str, status: str) -> None:
        async with self.db.acquire() as conn:
            await conn.execute("UPDATE incidents SET status = $2 WHERE id = $1", incident_id, status)

    async def _event(self, incident_id: str, event_type: str, payload: dict[str, Any]) -> None:
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO incident_events (incident_id, event_type, payload)
                VALUES ($1, $2, $3::jsonb)
                """,
                incident_id,
                event_type,
                json.dumps(payload),
            )


def classify_issue(service: str, symptom: str, faults: list[dict[str, Any]]) -> str:
    joined = " ".join([symptom.lower()] + [str(fault.get("fault_type", "")).lower() for fault in faults])
    if "cache" in joined or "redis" in joined or "hot key" in joined:
        return "cache_stampede"
    if "timeout" in joined or "payment" in joined:
        return "payment_timeout" if service in {"order", "payment"} else "downstream_timeout"
    if "db" in joined or "database" in joined or "slow query" in joined or "lock" in joined:
        return "db_slow_query"
    if "error" in joined:
        return "error_rate_spike"
    return "unknown_degradation"


def derive_root_cause(service: str, issue_type: str, faults: list[dict[str, Any]]) -> str:
    if faults:
        fault = faults[0]
        fault_type = str(fault.get("fault_type", issue_type))
        intensity = fault.get("intensity", 50)
        if "cache" in fault_type:
            return f"{service} service is experiencing a cache stampede from an expired hot key; intensity={intensity}."
        if "timeout" in fault_type:
            return f"{service} service latency is driven by downstream payment timeout and retry exhaustion; intensity={intensity}."
        if "db" in fault_type or "database" in fault_type:
            return f"{service} service is blocked by database slow queries and lock contention; intensity={intensity}."
        return f"{service} service has active fault {fault_type}; intensity={intensity}."
    if issue_type == "cache_stampede":
        return f"{service} service likely has cache stampede symptoms, but no active synthetic fault was found."
    if issue_type == "payment_timeout":
        return f"{service} service likely waits on payment timeout, but no active synthetic fault was found."
    if issue_type == "db_slow_query":
        return f"{service} service likely has database slow query pressure, but no active synthetic fault was found."
    return f"{service} service degradation requires human investigation because evidence is inconclusive."


def summarize(content: str, limit: int = 180) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def merge_limitations(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = " ".join(str(item).strip().split())
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                merged.append(normalized)
    return merged
