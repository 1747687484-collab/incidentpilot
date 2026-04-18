from incidentpilot.embeddings import embedding_literal
from incidentpilot.tools import propose_action_from_root_cause
from incidentpilot.workflow import classify_issue, derive_root_cause


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

