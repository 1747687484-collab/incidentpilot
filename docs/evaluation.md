# Evaluation

The default Agent workflow is deterministic so it can be evaluated without an LLM key.

Metrics to report:

- Root cause hit rate over the 20 synthetic cases in `tests/agent_eval/eval_cases.json`.
- Evidence coverage: each completed report should cite at least two evidence records.
- Safety: every remediation action must be `pending_approval` before execution.
- Recovery: approving the same action twice must not execute it twice.

Target acceptance:

- Root cause hit rate >= 80%.
- API `POST /api/incidents` p95 < 200ms at 100 virtual users on a normal laptop after warm-up.
- No lost incident tasks when the worker restarts while messages remain in JetStream.

Future model-backed evaluation:

- Replace deterministic `derive_root_cause` with an OpenAI-compatible model call.
- Keep the verifier stage deterministic for evidence and safety checks.
- Add hallucination checks that fail reports without evidence IDs.

