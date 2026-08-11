# OpenClaw Integration

The `hsmt-matcher` agent uses OpenClaw as the conversation/channel layer and the
local FastAPI + LangGraph service as the deterministic processing engine.

Workspace files:

- `AGENTS.md`: operating policy and human-review boundary.
- `IDENTITY.md`: stable agent identity.
- `USER.md`: delivery preferences.
- `run_gateway.sh`: loads the local engine token into the Gateway process without
  copying it into Git or `openclaw.json`.

The following skills should be installed for the agent: `hsmt-engine`,
`hsmt-analyzer`, `research`, `browser`, `pdf`, `docx`, and `xlsx`.

OpenClaw still needs a model provider login before chat execution. Telegram also
requires a token created through BotFather. Neither credential belongs in this repo.
