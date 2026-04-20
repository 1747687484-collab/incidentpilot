-- Reset demo runtime data while keeping seeded and manually uploaded runbooks.
-- This is intended for local demos and integration testing, not production use.

TRUNCATE TABLE
  tool_audit,
  faults,
  incidents
RESTART IDENTITY CASCADE;
