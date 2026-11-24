"""Chunk and word cards to Anki through AnkiConnect. The chunk and word_card tables are the
outbox: anki_note_id is null until Anki has the note. Each note carries the tag mbxchat-<uid>, so a
retry finds it (a uuid, since ids restart if the database is ever recreated). A word already in
its deck (any note type with a Korean field, e.g. MbxRead's) is marked duplicate, not added."""
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
WORD_MODEL = "MbxChat Word"
WORD_FIELDS = ["English", "Korean", "Dictionary", "Examples"]
WORD_FRONT = "{{English}}"
WORD_BACK = ("{{FrontSide}}<hr id=answer><b>{{Korean}}</b><br><i>{{Dictionary}}</i>"
             '<div style="font-size:16px;text-align:left;margin-top:1em">{{Examples}}</div>')
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


def _setup(model: str, fields: list[str], front: str, back: str, deck: str) -> None:
    if model not in invoke("modelNames"):
        invoke("createModel", modelName=model, inOrderFields=fields, css=CSS,
               cardTemplates=[{"Name": model.split()[-1], "Front": front, "Back": back}])
    invoke("createDeck", deck=deck)


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def push() -> int:
    """Send every queued chunk and word; returns how many reached Anki. Raises Closed if Anki is closed."""
    with _lock, psycopg.connect(config.DATABASE_URL) as conn:
        return _push_chunks(conn) + _push_words(conn)


def _push_words(conn) -> int:
    rows = conn.execute(
        "SELECT id, uid, korean, english, dictionary, examples FROM word_card "
        "WHERE anki_note_id IS NULL AND anki_error IS NULL ORDER BY id"
    ).fetchall()
    if not rows:
        return 0
    deck = config.ANKI_WORD_DECK
    _setup(WORD_MODEL, WORD_FIELDS, WORD_FRONT, WORD_BACK, deck)
    sent = 0
    for word_id, uid, korean, english, dictionary, examples in rows:
        tag = f"mbxchat-{uid}"
        duplicate = False
        try:
            found = invoke("findNotes", query=f"tag:{tag}")
            if not found and (found := invoke("findNotes", query=f'"deck:{_quote(deck)}" "Korean:{_quote(korean)}"')):
                duplicate = True
            note_id = found[0] if found else invoke("addNote", note={
                "deckName": deck, "modelName": WORD_MODEL, "tags": [tag],
                "fields": dict(zip(WORD_FIELDS, [english, korean, dictionary, "<br>".join(examples)])),
                "options": {"allowDuplicate": True},
            })
        except RuntimeError as e:
            log.warning("word %s refused by Anki: %s", word_id, e)
            conn.execute("UPDATE word_card SET anki_error = %s WHERE id = %s", (str(e)[:500], word_id))
            conn.commit()
            continue
        conn.execute("UPDATE word_card SET anki_note_id = %s, duplicate = %s WHERE id = %s", (note_id, duplicate, word_id))
        conn.commit()
        sent += not duplicate
    return sent


def _push_chunks(conn) -> int:
    rows = conn.execute(
        "SELECT id, uid, ko, gloss, sentence, register_note FROM chunk "
        "WHERE anki_note_id IS NULL AND anki_error IS NULL ORDER BY id"
    ).fetchall()
    if not rows:
        return 0
    _setup(MODEL, FIELDS, FRONT, BACK, config.ANKI_DECK)
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
    """(chunk or word, error) for every card not in Anki yet."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        return conn.execute(
            "SELECT ko, anki_error FROM chunk WHERE anki_note_id IS NULL "
            "UNION ALL SELECT korean, anki_error FROM word_card WHERE anki_note_id IS NULL"
        ).fetchall()


def word_outcome(capture_id: int) -> str | None:
    """'in' / 'duplicate' / 'queued' / 'refused' for a capture's word card, None if there is none."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        row = conn.execute("SELECT anki_note_id, duplicate, anki_error FROM word_card WHERE capture_id = %s",
                           (capture_id,)).fetchone()
    if row is None:
        return None
    note_id, duplicate, error = row
    return "refused" if error else "duplicate" if duplicate else "in" if note_id else "queued"
