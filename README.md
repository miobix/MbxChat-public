# MbxChat

A Telegram bot for practising written Korean, built as a LangGraph agent over local open
models. Given something the learner wants to say, it writes the Korean, checks the words in
the learners' dictionary and turns the useful bits into [Anki](https://apps.ankiweb.net/) cards. In practice mode it sends
writing prompts through the day, grades the answers, remembers repeated mistakes and steers
the next prompts at them. Everything runs locally in Docker; no paid model API.

- **What it does and how it works:** [docs/FEATURES.md](docs/FEATURES.md) (screen captures,
  diagrams, eval numbers, design notes)
- **Try it without installing:** [recorded demo](https://miobix.github.io/MbxChat-public/)
  (replays of real bot runs, no model behind it)

## Quick start

Needs Docker (Compose 2.18+), git, and [Ollama](https://ollama.com) on the same computer.

1. Create a bot with Telegram's [@BotFather](https://t.me/BotFather) (`/newbot`) and copy its
   token. Get the numeric Telegram user ID of the account that will use it (for example from
   @userinfobot): the bot answers only that user.
2. Pull the model once: `ollama pull gemma4:e4b`.
3. Run:

```sh
git clone https://github.com/miobix/MbxChat-public.git
cd MbxChat-public
cp .env.example .env          # set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_ID
docker compose up -d --build
curl http://127.0.0.1:8005/health
```

Send `/start` to the bot. After pulling changes, run `docker compose up -d --build` again
(plain, with no service name: `bot` and `mcp` share one image). Every service has
`restart: unless-stopped`, so the stack comes back whenever Docker starts.

## Configuration (`.env`)

| Variable | Needed for | |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | everything | From @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | everything | Numeric Telegram ID of the one allowed user; anyone else is ignored |
| `KRDICT_API_KEY` | dictionary checks | Free at https://krdict.korean.go.kr/openApi/openApiInfo; unset = no checks |
| `PRACTICE_TZ`, `PRACTICE_PINGS` | practice pings | IANA zone and local times (default UTC, 10:00, 13:00, 17:00, 21:00) |
| `ANKI_DECK`, `ANKI_WORD_DECK` | Anki | Decks for chunk and word cards (created on first use) |
| `MBXREAD_URL` | optional | A running [MbxRead](https://github.com/miobix/MbxRead-public): library examples and saved terms |
| `CAPTURE_MODEL`, `CAPTURE_MODEL_ID` | optional | Another Ollama model and its digest prefix (checked at startup) |
| `POSTGRES_PASSWORD`, `BACKUP_DIR` | optional | Default `mbxchat`, `./backups`; the database listens on 127.0.0.1 only |

The bot reaches Ollama at `host.docker.internal:11434`. When MbxRead runs on the same
machine, its compose `ollama` service on that port works as is, and both apps share one copy
of the model.

## Optional parts

- **Anki:** Anki desktop with the AnkiConnect add-on (code `2055492159`), open on the same
  computer. While Anki is closed, approved cards queue and are sent within a minute of it
  opening (`/queue` shows them).
- **MbxRead:** with `MBXREAD_URL` set, captures also look for example sentences in the MbxRead
  library, and practice can use the words being learned there. Unset, both are off and the
  rest works the same. Import saved terms on the host (the importer doesn't read `.env`):
  `MBXREAD_URL=http://127.0.0.1:8002 python -m mbxchat.importer`.
- **Tracing:** Arize Phoenix at http://127.0.0.1:6006 shows every model and tool call.
- **Monitoring:** Grafana at http://127.0.0.1:3005, Prometheus at http://127.0.0.1:9090. If the
  bot stops or its polling stalls, Alertmanager sends a Telegram message to the allowed chat within
  about two minutes, and another when it recovers.
- All web UIs listen on 127.0.0.1 only and have no login. Don't publish their ports.

Not in scope: voice messages. Telegram allows them, but audio ingestion is not part of this
project; the bot handles text.

## Hardware

The model runs where Ollama runs. Measured on the same machine with the grader set of 66
answers (median / p90 seconds per answer):

| Model | CPU | GPU |
|---|---|---|
| gemma4:e4b (the one used) | 11.0 / 14.0 | 1.4 / 1.7 |
| A.X 4.0 Light | 15.5 / 18.8 | 1.6 / 1.9 |
| Mi:dm 2.0 Mini | 4.9 / 6.6 | 0.8 / 0.9 |
| Nemotron 3.5 Bolt | 59.9 / 74.5 | 7.0 / 8.5 |
| Qwen3.5-4B | 17.2 / 26.5 | 2.1 / 2.8 |

Quality scores are the same on both; only speed changes. On CPU a capture takes tens of
seconds, which works but feels slow in a chat.

## Known problems

Each was found in testing; the reason it's still there is technical.

- **The grader is soft on missing required grammar.** When a grammar prompt's answer is a fine
  sentence that uses a near-synonym (처럼 instead of -듯이, -아서 instead of -는 바람에), the grader
  usually says "Nearly" instead of "Not quite", and sometimes "Correct": 11 of 12 labeled items
  were not marked wrong. Tried: two prompt rewrites and a separate "does it use the form?"
  check, each measured on the labeled set; none passed the bar set before it ran (one cut false
  alarms but nearly doubled missed errors). A stronger model would likely do better, and the
  ones that fit this machine's GPU were all evaluated (FEATURES has the table). Further grader
  and model changes wait for more real-use data, so they're tuned on real answers rather than
  a 66-item set.
- **The grader misses some honorific and connective rules** (할머니가 자고 있어요 for 주무시고
  계세요, -아서 leading into a command) and flags about 1 in 9 correct answers. Same reason: it's
  the best of the local models evaluated.
- **Capture's "casual" line isn't always casual.** When the situation is a boss, client or
  customer, the model softens the 반말 line into 요 form (4 of 12 sentences in the demo
  recording). The polite line is right; it's the label that's off. Fixing it needs either a
  stronger model or a rule that drops the casual line for such situations, and the bot doesn't
  classify situations yet.
- **The capture agent sometimes runs out of steps.** It has 6 model turns to call its tools and
  submit; one recording run hit that limit on 2 of 6 sentences, the next on 0 of 12. It
  reports a clear error and nothing is saved. Not reproduced since, so not diagnosed.
- **Spacing-only fixes still count as correct.** Grading compares sentences with spaces
  removed, so 집에가서 → 집에 가서 keeps a "Correct". The slip is still recorded in the mistake
  memory and shows in `/weak`.
- **A pending ✏️ edit lives in memory:** restarting the bot during a chunk edit forgets
  the edit; tapping ✏️ again starts it over.

## Backups and moving machines

The `backup` service writes `mbxchat-<date>.dump` (`pg_dump -Fc`) daily into `BACKUP_DIR` and
keeps the newest 14 (`docker compose logs backup` shows each run). The database holds the
captures, answers and mistake memory, which exist nowhere else, so copy the dumps off the
machine.

To restore: clone, copy `.env`, then

```sh
docker compose up -d --wait db
docker compose exec -T db pg_restore -U mbxchat -d mbxchat --clean --if-exists < backups/mbxchat-<date>.dump
docker compose up -d --build
```

## Development

Python 3.14. Dependencies are locked with hashes (`requirements*.txt`, compiled from
`requirements*.in` with pip-tools).

```sh
py -3.14 -m venv .venv                      # Linux/macOS: python3.14 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-dev.txt
docker compose up -d --wait db              # tests use it (127.0.0.1:5434)
.venv/Scripts/python -m pytest tests -q     # offline: Telegram, models, krdict, Anki faked
```

- Each test gets a throwaway database, so tests never touch real data.
- To add a dependency: edit the `.in` file, recompile `requirements.txt`, then the dev and eval
  files (they're constrained by it).
- Evals (`evals/`) score models on labeled sets and log runs to Phoenix; see
  [docs/SPEC.md](docs/SPEC.md) §9.
- The demo is rerecorded with `demo/record.py`; see SPEC §7h.
- Contributor docs live in `docs/`: start with `STATUS.md`. `SPEC.md` is the contract,
  `DECISIONS.md` the log of what was decided and why, `DATA.md` the sources and licences.
- This repository is a sanitized public copy of a private one; what was rewritten, and the
  evidence that nothing else was: [docs/PUBLIC_COPY.md](docs/PUBLIC_COPY.md).

## Layout

```
mbxchat/        the bot: handlers, capture graph and agent, practice, grader, MCP server, metrics
data/           public content pools (NIKL grammar and vocabulary, refreshers, sentences)
evals/          labeled sets, eval harnesses, results
demo/           the recorded demo page, its recordings and the recorder
monitoring/     Prometheus config and alert rule (with tests), Grafana dashboard
tests/          offline test suite
docs/           features, spec, decision log, status, data provenance
compose.yaml    bot + MCP server + Postgres + backup + Phoenix + Prometheus + Alertmanager + Grafana
Dockerfile      the bot image; .dockerignore is an allowlist
```

## License

Code: MIT, see [LICENSE](LICENSE). Content keeps its own licences, listed with attribution in
[docs/DATA.md](docs/DATA.md): NIKL grammar and vocabulary lists (KOGL type 1), krdict text in
the demo (CC BY-SA 2.0 KR).
