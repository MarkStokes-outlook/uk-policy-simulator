# Developer Queue

Messages for the developer role (implementation, coding, documentation).

## Message Lifecycle

1. **pending/** — Messages waiting to be claimed
2. **processing/** — Message claimed, work in progress
3. **processed/** — Work completed successfully
4. **failed/** — Processing failed (may retry)

## Claiming Messages

To claim a message:
1. Move atomically from `pending/` to `processing/`
2. Process the message
3. Move to `processed/` on success, `failed/` on failure

Never read directly from `pending/` without moving first.
