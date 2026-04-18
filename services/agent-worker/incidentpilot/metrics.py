try:
    from prometheus_client import Counter, Histogram
except ModuleNotFoundError:
    class _NoopMetric:
        def labels(self, **_kwargs):
            return self

        def inc(self, *_args, **_kwargs):
            return None

        def observe(self, *_args, **_kwargs):
            return None

    def Counter(*_args, **_kwargs):
        return _NoopMetric()

    def Histogram(*_args, **_kwargs):
        return _NoopMetric()


TOOL_CALLS = Counter(
    "incidentpilot_agent_tool_calls_total",
    "Total Agent tool calls.",
    ["tool", "status"],
)

TOOL_LATENCY = Histogram(
    "incidentpilot_agent_tool_duration_seconds",
    "Agent tool call duration.",
    ["tool"],
)

WORKFLOW_RUNS = Counter(
    "incidentpilot_agent_workflow_runs_total",
    "Total Agent workflow runs.",
    ["status"],
)
