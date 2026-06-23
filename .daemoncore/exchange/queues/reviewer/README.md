# Reviewer Queue

Messages for the reviewer role (code review, quality assurance).

## Message Lifecycle

1. **pending/** — Messages waiting to be claimed
2. **processing/** — Message claimed, review in progress
3. **processed/** — Review completed successfully
4. **failed/** — Review failed (may retry)

## Claiming Messages

To claim a message:
1. Move atomically from `pending/` to `processing/`
2. Process the message
3. Move to `processed/` on success, `failed/` on failure

Never read directly from `pending/` without moving first.
