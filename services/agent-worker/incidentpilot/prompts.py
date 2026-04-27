from __future__ import annotations

from typing import Any


RCA_SYSTEM_PROMPT = """You are IncidentPilot's RCA agent.
Produce a conservative root cause analysis from the supplied incident and evidence only.
Do not invent systems, logs, metrics, tools, credentials, or actions.
Return strict JSON with keys: root_cause, confidence, evidence_ids, limitations.
confidence must be a number from 0.0 to 1.0.
evidence_ids must only contain IDs from the supplied evidence list."""


def build_rca_messages(
    incident: dict[str, Any],
    issue_type: str,
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    evidence_lines = []
    for item in evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"id: {item['id']}",
                    f"source: {item['source']}",
                    f"query: {item['query']}",
                    f"content: {item['content']}",
                    f"score: {item['score']}",
                ]
            )
        )

    user_prompt = "\n\n".join(
        [
            "Incident:",
            f"id: {incident['id']}",
            f"service: {incident['service']}",
            f"symptom: {incident['symptom']}",
            f"severity: {incident['severity']}",
            f"classified_issue_type: {issue_type}",
            "Evidence:",
            "\n---\n".join(evidence_lines),
            "JSON response only. Keep root_cause under 360 characters.",
        ]
    )
    return [
        {"role": "system", "content": RCA_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
