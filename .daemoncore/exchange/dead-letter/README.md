# Dead Letter Queue

Messages that have exceeded maximum retry attempts are moved here.

## Purpose

- Store messages that failed processing after all retries
- Preserve failed messages for debugging and manual intervention
- Prevent message loss while isolating problematic items

## Recovery

Dead letter messages require human intervention:

1. Review the message and failure reason
2. Fix the underlying issue
3. Move the message back to the appropriate queue's `pending/` folder
4. Or delete if the message is no longer relevant
