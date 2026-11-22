"""Chunk cards to Anki through AnkiConnect. The chunk table is the outbox: anki_note_id is null
until Anki has the note. Each note carries the tag mbxchat-<chunk uid>, so a retry finds it
(a uuid, since chunk ids restart if the database is ever recreated)."""
import json
import logging
import threading
import urllib.request

import psycopg

from mbxchat import config
from mbxchat.capture import _kiwi

log = logging.getLogger(__name__)

MODEL = "MbxChat Chunk"
FIELDS = ["Gloss", "Blanked", "Chunk", "Sentence", "Register"]
FRONT = "{{Gloss}}{{#Blanked}}<br><br>{{Blanked}}{{/Blanked}}"
BACK = "{{FrontSide}}<hr id=answer><b>{{Chunk}}</b><br>{{Sentence}}<br><i>{{Register}}</i>"
CSS = ".card { font-family: sans-serif; font-size: 22px; text-align: center; }"
BLANK = "[…]"
SKIP_TAGS = {"SO", "SSO", "SSC", "SW", "SF", "SP"}

_lock = threading.Lock()  # the bot's push and the retry loop must not add the same chunk twice


class Closed(Exception):
    """Anki (or AnkiConnect) is not reachable; everything stays queued."""


def invoke(action: str, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(config.ANKI_URL, data=body), timeout=10) as resp:
            answer = json.load(resp)
    except OSError as e:
        raise Closed(str(e)) from e
    if answer.get("error"):
        raise RuntimeError(answer["error"])
    return answer["result"]


def blank(chunk: str, sentence: str) -> str:
    """The sentence with the longest run of the chunk's morphemes blanked; "" when none match."""
    want = [t.form for t in _kiwi().tokenize(chunk) if t.tag not in SKIP_TAGS]
    if want and want[-1] == "다":
        want.pop()
    toks = _kiwi().tokenize(sentence)
    forms = [t.form for t in toks]
    best = None
    for n in range(len(want), 0, -1):
        for i in range(len(want) - n + 1):
            run = want[i:i + n]
            if n == 1 and len(run[0]) < 2:
                continue
            for j in range(len(forms) - n + 1):
                if forms[j:j + n] == run:
                    best = (toks[j].start, toks[j + n - 1].end)
                    break
            if best:
                break
        if best:
            break
    if not best:
        return ""
    return sentence[:best[0]] + BLANK + sentence[best[1]:]


def _setup() -> None:
    if MODEL not in invoke("modelNames"):
        invoke("createModel", modelName=MODEL, inOrderFields=FIELDS, css=CSS,
               cardTemplates=[{"Name": "Chunk", "Front": FRONT, "Back": BACK}])
    invoke("createDeck", deck=config.ANKI_DECK)


def push() -> int:
    """Send every queued chunk; returns how many reached Anki. Raises Closed if Anki is closed."""
    with _lock, psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT id, uid, ko, gloss, sentence, register_note FROM chunk "
            "WHERE anki_note_id IS NULL AND anki_error IS NULL ORDER BY id"
        ).fetchall()
        if not rows:
            return 0
        _setup()
        sent = 0
        for chunk_id, uid, ko, gloss, sentence, register in rows:
            tag = f"mbxchat-{uid}"
            try:
                found = invoke("findNotes", query=f"tag:{tag}")
                note_id = found[0] if found else invoke("addNote", note={
                    "deckName": config.ANKI_DECK, "modelName": MODEL, "tags": [tag],
                    "fields": dict(zip(FIELDS, [gloss, blank(ko, sentence), ko, sentence, register])),
                    "options": {"allowDuplicate": True},
                })
            except RuntimeError as e:
                log.warning("chunk %s refused by Anki: %s", chunk_id, e)
                conn.execute("UPDATE chunk SET anki_error = %s WHERE id = %s", (str(e)[:500], chunk_id))
                conn.commit()
                continue
            conn.execute("UPDATE chunk SET anki_note_id = %s WHERE id = %s", (note_id, chunk_id))
            conn.commit()
            sent += 1
        return sent


def queued() -> list[tuple[str, str | None]]:
    """(chunk, error) for every chunk not in Anki yet."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        return conn.execute(
            "SELECT ko, anki_error FROM chunk WHERE anki_note_id IS NULL ORDER BY id"
        ).fetchall()
