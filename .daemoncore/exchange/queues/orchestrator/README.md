# Orchestrator Queue

Messages for the orchestrator role (task coordination, workflow management).

## Message Lifecycle

1. **pending/** — Messages waiting to be claimed
2. **processing/** — Message claimed, coordination in progress
3. **processed/** — Coordination completed successfully
4. **failed/** — Coordination failed (may retry)

## Claiming Messages

To claim a message:
1. Move atomically from `pending/` to `processing/`
2. Process the message
3. Move to `processed/` on success, `failed/` on failure

Never read directly from `pending/` without moving first.
