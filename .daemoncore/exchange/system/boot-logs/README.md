# Boot Logs

Agent boot sequence logs are stored here.

## Format

Log files follow the naming convention:
`<timestamp>-<vendor>-<model>.md`

Example: `2026-01-14T10-30-00Z-claude-sonnet.md`

## Contents

Each boot log contains:
- Timestamp
- Vendor, model, version
- Environment report (host class, network, sandbox)
- Boot status (SUCCESS | FAILURE | DEGRADED)
- Context files loaded
- Session state (fresh | resumed)
