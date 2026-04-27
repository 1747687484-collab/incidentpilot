from incidentpilot.embeddings import embedding_literal
from incidentpilot.llm import normalize_root_cause_draft, parse_json_object
from incidentpilot.prompts import build_rca_messages
from incidentpilot.tools import propose_action_from_root_cause
from incidentpilot.workflow import classify_issue, derive_root_cause, merge_limitations


def test_embedding_literal_has_eight_dimensions():
    literal = embedding_literal("order cache latency")
    assert literal.startswith("[")
    assert literal.endswith("]")
    assert len(literal.strip("[]").split(",")) == 8


def test_classify_cache_stampede_from_fault():
    issue = classify_issue("order", "latency increased", [{"fault_type": "cache_stampede"}])
    assert issue == "cache_stampede"


def test_derive_payment_root_cause():
    root = derive_root_cause("payment", "payment_timeout", [{"fault_type": "payment_timeout", "intensity": 80}])
    assert "payment timeout" in root


def test_propose_cache_action_requires_approval():
    action = propose_action_from_root_cause("order", "cache stampede from hot key")
    assert action["type"] == "warm_cache"
    assert action["requires_approval"] is True


def test_parse_json_object_from_markdown_fence():
    payload = parse_json_object('```json\n{"root_cause":"cache stampede from hot key","confidence":0.8}\n```')
    assert payload["confidence"] == 0.8


def test_normalize_root_cause_requires_supplied_evidence_ids():
    draft = normalize_root_cause_draft(
        {
            "root_cause": "order service cache stampede is supported by logs and metrics",
            "confidence": 0.88,
            "evidence_ids": ["e1", "e2", "unknown"],
            "limitations": ["synthetic telemetry only"],
        },
        {"e1", "e2"},
        "openai-compatible",
    )
    assert draft.evidence_ids == ["e1", "e2"]
    assert draft.provider == "openai-compatible"


def test_normalize_root_cause_rejects_weak_citations():
    try:
        normalize_root_cause_draft(
            {
                "root_cause": "order service cache stampede is supported by logs and metrics",
                "confidence": 0.88,
                "evidence_ids": ["unknown"],
                "limitations": [],
            },
            {"e1", "e2"},
            "openai-compatible",
        )
    except ValueError as exc:
        assert "evidence IDs" in str(exc)
    else:
        raise AssertionError("expected weak citations to be rejected")


def test_build_rca_messages_includes_incident_and_evidence():
    messages = build_rca_messages(
        {
            "id": "incident-1",
            "service": "order",
            "symptom": "checkout latency",
            "severity": "SEV2",
        },
        "cache_stampede",
        [
            {
                "id": "e1",
                "source": "logs",
                "query": "service=order",
                "content": "cache miss storm",
                "score": 0.9,
            }
        ],
    )
    prompt = messages[1]["content"]
    assert "incident-1" in prompt
    assert "cache miss storm" in prompt
    assert "cache_stampede" in prompt


def test_merge_limitations_deduplicates_items():
    limitations = merge_limitations(["synthetic telemetry only"], ["Synthetic telemetry only", "manual approval required"])
    assert limitations == ["synthetic telemetry only", "manual approval required"]
