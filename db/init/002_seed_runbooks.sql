INSERT INTO knowledge_documents (id, title, source, content)
VALUES
  ('00000000-0000-0000-0000-000000000101', 'Payment timeout runbook', 'seed', '# Payment timeout runbook

Symptoms: payment service p95 latency rises, checkout requests wait for payment authorization, order service reports downstream timeout.

Checks: inspect payment error rate, gateway latency, and recent retry storms. Compare payment metrics with order service timeout logs.

Mitigation: reduce retry concurrency, open circuit breaker for payment provider, scale payment workers, and replay failed payment callbacks after recovery.'),
  ('00000000-0000-0000-0000-000000000102', 'Inventory database slow query runbook', 'seed', '# Inventory database slow query runbook

Symptoms: inventory reservation becomes slow, database latency rises, stock lock contention appears in logs.

Checks: query inventory slow SQL logs, lock wait duration, and order to inventory dependency latency.

Mitigation: enable degraded stock cache, add missing index, pause non-critical stock synchronization jobs, and retry reservations with bounded backoff.'),
  ('00000000-0000-0000-0000-000000000103', 'Order cache stampede runbook', 'seed', '# Order cache stampede runbook

Symptoms: order service QPS to database jumps, cache hit rate drops, Redis hot key expires, latency and error rate rise together.

Checks: inspect Redis key expiration, order database read volume, and logs containing cache miss storm.

Mitigation: warm hot keys, enable request coalescing, add randomized TTL jitter, and apply temporary rate limiting to low-priority reads.');

INSERT INTO knowledge_chunks (document_id, chunk_index, content, embedding)
VALUES
  ('00000000-0000-0000-0000-000000000101', 0, 'payment service p95 latency rises checkout requests wait for payment authorization downstream timeout retry storm circuit breaker scale payment workers', '[0.1,0.9,0.1,0.8,0.3,0.1,0.2,0.1]'),
  ('00000000-0000-0000-0000-000000000102', 0, 'inventory reservation slow database latency slow query stock lock contention missing index degraded stock cache bounded backoff', '[0.2,0.1,0.9,0.4,0.2,0.9,0.1,0.2]'),
  ('00000000-0000-0000-0000-000000000103', 0, 'order cache stampede Redis hot key expires cache miss storm database read volume randomized TTL jitter request coalescing', '[0.9,0.1,0.2,0.5,0.9,0.2,0.4,0.3]');

