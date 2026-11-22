# DECISIONS (append-only log: never rewrite, never compress)

## 2026-11-22 Scope and stack
- **Telegram bot, long polling:** the phone's chat app is the UI, nothing listens on a public port, and a chat gives practice a session shape.
- **LangGraph** for orchestration: `interrupt()` plus a Postgres checkpointer match the Approve/Edit/Skip flow. Alternatives considered: Strands, Pydantic AI, OpenAI Agents SDK, a hand-written loop.
- **CPU-only open models, no paid APIs.** A cost router (rules → small GEC model → local LLM) keeps the expensive tier rare. Models are configuration; an unscoped model is added as an eval experiment.
- **Arize Phoenix via OpenTelemetry** for traces and evals: one container, where a self-hosted Langfuse needs about six. Moving to Langfuse is an exporter change; datasets would not migrate. LangSmith skipped: traces would leave the machine.
- **Prometheus + Grafana**, kept to one dashboard and one alert.
- **Cards hold chunks, the bot drills sentences:** long sentences make poor Anki cards, and the bot can grade full sentences where Anki cannot. Provisional until used.
- **Build the fixed workflow first (unit 3), then the agent (unit 7)**, and compare them on the same eval: the agent has to earn its extra cost.
- **MbxRead is an optional tool** over `host.docker.internal`; the bot works without it.
- **Content imported wide and pruned later**; personal sources stay in the local database.
