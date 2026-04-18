import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";
const eventNames = [
  "incident.created",
  "agent.started",
  "tool.called",
  "agent.step",
  "action.proposed",
  "report.ready",
  "action.approved",
  "action.execution.started",
  "action.executed",
  "action.execution.skipped",
  "agent.failed",
];

const faultPresets = {
  order: ["cache_stampede", "payment_timeout"],
  payment: ["payment_timeout"],
  inventory: ["db_slow_query"],
};

export default function App() {
  const [incident, setIncident] = useState(null);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [incidentForm, setIncidentForm] = useState({
    service: "order",
    symptom: "Order checkout latency is rising and users report intermittent failures.",
    severity: "SEV2",
  });
  const [faultForm, setFaultForm] = useState({
    service: "order",
    fault_type: "cache_stampede",
    intensity: 82,
  });
  const [docForm, setDocForm] = useState({
    title: "Checkout pressure runbook",
    source: "manual-demo",
    content:
      "When order checkout latency rises, compare cache hit rate, payment timeout logs, database reads, and retry volume. Warm hot keys, open a circuit breaker for payment timeout, or enable degraded inventory cache after approval.",
  });

  const status = incident?.incident?.status || "idle";
  const actions = incident?.actions || [];
  const pendingActions = actions.filter((action) => action.status === "pending_approval");

  useEffect(() => {
    if (!incident?.incident?.id) return undefined;
    const id = incident.incident.id;
    const source = new EventSource(`${API_BASE}/api/incidents/${id}/events`);

    const handleEvent = (event) => {
      const payload = safeJSON(event.data);
      setEvents((current) => [{ type: event.type, payload, id: event.lastEventId }, ...current].slice(0, 40));
      refreshIncident(id);
    };

    eventNames.forEach((name) => source.addEventListener(name, handleEvent));
    source.onerror = () => setMessage("Event stream reconnecting...");

    return () => source.close();
  }, [incident?.incident?.id]);

  const healthText = useMemo(() => {
    if (status === "resolved") return "Resolved";
    if (status === "awaiting_approval") return "Approval needed";
    if (status === "running") return "Agents running";
    if (status === "failed") return "Needs review";
    if (status === "queued") return "Queued";
    return "Ready";
  }, [status]);

  async function refreshIncident(id = incident?.incident?.id) {
    if (!id) return;
    const response = await fetch(`${API_BASE}/api/incidents/${id}`);
    if (response.ok) {
      setIncident(await response.json());
    }
  }

  async function createFault(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/simulations/faults`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...faultForm, intensity: Number(faultForm.intensity), details: {} }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Failed to inject fault");
      setMessage(`Injected ${body.fault_type} on ${body.service}`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function createIncident(event) {
    event.preventDefault();
    setBusy(true);
    setEvents([]);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/incidents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(incidentForm),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Failed to create incident");
      setIncident(body);
      setMessage("Incident accepted");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadRunbook(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/knowledge/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(docForm),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Failed to upload runbook");
      setMessage(`Indexed ${body.chunks} chunk(s)`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function approveAction(actionId) {
    if (!incident?.incident?.id) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/incidents/${incident.incident.id}/approve-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: actionId, operator: "demo-user" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Failed to approve action");
      setMessage("Approval sent");
      refreshIncident();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  function updateIncidentService(service) {
    setIncidentForm((current) => ({ ...current, service }));
    setFaultForm((current) => ({ ...current, service, fault_type: faultPresets[service][0] }));
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">IncidentPilot</p>
          <h1>多 Agent 智能排障台</h1>
          <p className="subtle">注入故障，创建事故，等待证据链和根因报告，再审批安全修复。</p>
        </div>
        <div className={`status-pill status-${status}`}>{healthText}</div>
      </section>

      <section className="workspace">
        <aside className="control-panel">
          <img
            className="ops-image"
            src="https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80"
            alt="Circuit board detail"
          />
          <form onSubmit={createFault} className="form-block">
            <h2>故障注入</h2>
            <label>
              Service
              <select value={faultForm.service} onChange={(event) => updateIncidentService(event.target.value)}>
                <option value="order">order</option>
                <option value="payment">payment</option>
                <option value="inventory">inventory</option>
              </select>
            </label>
            <label>
              Fault
              <select
                value={faultForm.fault_type}
                onChange={(event) => setFaultForm({ ...faultForm, fault_type: event.target.value })}
              >
                {faultPresets[faultForm.service].map((fault) => (
                  <option key={fault} value={fault}>
                    {fault}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Intensity
              <input
                type="number"
                min="1"
                max="100"
                value={faultForm.intensity}
                onChange={(event) => setFaultForm({ ...faultForm, intensity: event.target.value })}
              />
            </label>
            <button disabled={busy}>Inject fault</button>
          </form>

          <form onSubmit={createIncident} className="form-block">
            <h2>事故创建</h2>
            <label>
              Severity
              <select
                value={incidentForm.severity}
                onChange={(event) => setIncidentForm({ ...incidentForm, severity: event.target.value })}
              >
                <option value="SEV1">SEV1</option>
                <option value="SEV2">SEV2</option>
                <option value="SEV3">SEV3</option>
              </select>
            </label>
            <label>
              Symptom
              <textarea
                value={incidentForm.symptom}
                onChange={(event) => setIncidentForm({ ...incidentForm, symptom: event.target.value })}
                rows="4"
              />
            </label>
            <button disabled={busy}>Create incident</button>
          </form>

          <form onSubmit={uploadRunbook} className="form-block">
            <h2>知识库</h2>
            <label>
              Title
              <input value={docForm.title} onChange={(event) => setDocForm({ ...docForm, title: event.target.value })} />
            </label>
            <label>
              Content
              <textarea
                value={docForm.content}
                onChange={(event) => setDocForm({ ...docForm, content: event.target.value })}
                rows="5"
              />
            </label>
            <button disabled={busy}>Index runbook</button>
          </form>
          {message && <p className="message">{message}</p>}
        </aside>

        <section className="main-panel">
          <div className="summary-grid">
            <Metric label="Incident" value={incident?.incident?.id?.slice(0, 8) || "none"} />
            <Metric label="Evidence" value={incident?.evidence?.length || 0} />
            <Metric label="Steps" value={incident?.steps?.length || 0} />
            <Metric label="Actions" value={actions.length} />
          </div>

          <section className="report-band">
            <h2>Root cause</h2>
            {incident?.report ? (
              <>
                <p className="root-cause">{incident.report.root_cause}</p>
                <p className="subtle">Confidence {(incident.report.confidence * 100).toFixed(0)}%</p>
              </>
            ) : (
              <p className="empty">Create an incident and the report will land here.</p>
            )}
          </section>

          <section className="approval-band">
            <div>
              <h2>Approval</h2>
              <p className="subtle">Write actions stay paused until you approve them.</p>
            </div>
            {pendingActions.length === 0 ? (
              <p className="empty">No pending action.</p>
            ) : (
              pendingActions.map((action) => (
                <article className="action-item" key={action.id}>
                  <div>
                    <strong>{action.type}</strong>
                    <p>{JSON.stringify(action.params)}</p>
                  </div>
                  <button disabled={busy} onClick={() => approveAction(action.id)}>
                    Approve
                  </button>
                </article>
              ))
            )}
          </section>

          <section className="columns">
            <Panel title="Agent timeline">
              {(incident?.steps || []).map((step) => (
                <article className="timeline-item" key={step.id}>
                  <span>{step.agent_name}</span>
                  <strong>{step.tool_name || "reasoning"}</strong>
                  <p>{step.output_summary}</p>
                </article>
              ))}
              {(!incident?.steps || incident.steps.length === 0) && <p className="empty">No agent steps yet.</p>}
            </Panel>

            <Panel title="Evidence chain">
              {(incident?.evidence || []).map((item) => (
                <article className="evidence-item" key={item.id}>
                  <span>{item.source}</span>
                  <p>{item.content}</p>
                </article>
              ))}
              {(!incident?.evidence || incident.evidence.length === 0) && <p className="empty">No evidence yet.</p>}
            </Panel>
          </section>

          <section className="event-strip">
            <h2>Live events</h2>
            {events.map((event) => (
              <article className="event-item" key={`${event.id}-${event.type}`}>
                <span>{event.type}</span>
                <code>{JSON.stringify(event.payload)}</code>
              </article>
            ))}
            {events.length === 0 && <p className="empty">SSE events will stream here.</p>}
          </section>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Panel({ title, children }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function safeJSON(value) {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

