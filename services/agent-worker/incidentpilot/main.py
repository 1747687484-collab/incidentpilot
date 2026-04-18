import asyncio
import json
import logging
import signal

import asyncpg
import nats
from nats.errors import TimeoutError as NATSTimeoutError
from prometheus_client import start_http_server

from .config import load_settings
from .tools import MCPToolService
from .workflow import AgentWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("incidentpilot.agent")


async def ensure_stream(js) -> None:
    try:
        await js.stream_info("INCIDENTS")
    except Exception:
        await js.add_stream(name="INCIDENTS", subjects=["incident.*", "remediation.*", "simulation.*"])


async def consume_incidents(workflow: AgentWorkflow, sub) -> None:
    while True:
        try:
            messages = await sub.fetch(5, timeout=1)
        except NATSTimeoutError:
            continue
        for message in messages:
            try:
                payload = json.loads(message.data.decode())
                await workflow.process_incident(payload["incident_id"])
                await message.ack()
            except Exception:
                logger.exception("failed to process incident message")
                await message.nak(delay=5)


async def consume_actions(workflow: AgentWorkflow, sub) -> None:
    while True:
        try:
            messages = await sub.fetch(5, timeout=1)
        except NATSTimeoutError:
            continue
        for message in messages:
            try:
                payload = json.loads(message.data.decode())
                await workflow.process_approved_action(
                    payload["incident_id"],
                    payload["action_id"],
                    payload.get("operator", "local-demo"),
                )
                await message.ack()
            except Exception:
                logger.exception("failed to process action message")
                await message.nak(delay=5)


async def main() -> None:
    settings = load_settings()
    start_http_server(settings.metrics_port)
    logger.info("agent metrics listening on %s", settings.metrics_port)

    db = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=8)
    nc = await nats.connect(settings.nats_url, name="incidentpilot-agent-worker")
    js = nc.jetstream()
    await ensure_stream(js)

    incident_sub = await js.pull_subscribe("incident.created", durable="agent-worker", stream="INCIDENTS")
    action_sub = await js.pull_subscribe("remediation.approved", durable="action-worker", stream="INCIDENTS")

    workflow = AgentWorkflow(db, MCPToolService(db))
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    tasks = [
        asyncio.create_task(consume_incidents(workflow, incident_sub)),
        asyncio.create_task(consume_actions(workflow, action_sub)),
    ]
    logger.info("agent worker started")
    await stop_event.wait()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await nc.drain()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
