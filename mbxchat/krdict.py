"""krdict, the NIKL Korean learners' dictionary (Open API; free key from krdict.korean.go.kr).

Sparse by design (CLAUDE.md rule 3): every answer cached in Postgres, network calls 3 s apart,
never retried; the first failure pauses all calls for 30 min, across restarts.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import psycopg

from mbxchat import config

SEARCH_URL = "https://krdict.korean.go.kr/api/search"
VIEW_URL = "https://krdict.korean.go.kr/api/view"
GAP = 3.0
COOLDOWN = 30 * 60
_lock = threading.Lock()
_last = 0.0


class Unavailable(Exception):
    pass


def enabled() -> bool:
    return bool(config.KRDICT_API_KEY)


def _blocked_until(conn) -> float | None:
    row = conn.execute("SELECT value FROM setting WHERE key = 'krdict_blocked_until'").fetchone()
    return float(row[0]) if row and float(row[0]) > time.time() else None


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read().decode("utf-8")


def _get(url: str, params: dict) -> ET.Element:
    global _last
    key = json.dumps([url, params], sort_keys=True, ensure_ascii=False)
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        row = conn.execute("SELECT body FROM krdict_cache WHERE key = %s", (key,)).fetchone()
        if row:
            return ET.fromstring(row[0])
        with _lock:
            if until := _blocked_until(conn):
                raise Unavailable(f"krdict paused after a failure, until {datetime.fromtimestamp(until):%H:%M}")
            time.sleep(max(0.0, _last + GAP - time.monotonic()))
            try:
                body = _fetch(f"{url}?{urllib.parse.urlencode({'key': config.KRDICT_API_KEY, **params})}")
                root = ET.fromstring(body)
                if root.tag == "error":
                    raise ValueError(root.findtext("message", "") or "error")
            except Exception as e:
                conn.execute(
                    "INSERT INTO setting (key, value) VALUES ('krdict_blocked_until', %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (str(time.time() + COOLDOWN),))
                raise Unavailable(f"krdict request failed ({e}); paused for {COOLDOWN // 60} min") from e
            finally:
                _last = time.monotonic()
        conn.execute("INSERT INTO krdict_cache (key, body) VALUES (%s, %s) ON CONFLICT DO NOTHING", (key, body))
    return root


def search(word: str, max_entries: int = 3) -> list[dict]:
    """[{word, pos, target_code, glosses: [English]}] for up to `max_entries` homographs; one request."""
    root = _get(SEARCH_URL, {"q": word, "translated": "y", "trans_lang": "1", "advanced": "n"})
    return [{
        "word": item.findtext("word", ""),
        "pos": item.findtext("pos", ""),
        "target_code": item.findtext("target_code", ""),
        "glosses": [g for s in item.findall("sense")[:3] if (g := s.findtext("translation/trans_word", "").strip())],
    } for item in root.findall(".//item")[:max_entries]]


def examples(target_code: str, k: int = 4) -> list[str]:
    """Example sentences of one entry; one request, so only call it for the entry you need."""
    root = _get(VIEW_URL, {"method": "target_code", "q": target_code, "target_code": target_code,
                           "translated": "y", "trans_lang": "1"})
    out: list[str] = []
    for ex in root.findall(".//example_info/example"):
        if (text := (ex.text or "").strip()) and text not in out:
            out.append(text)
    return out[:k]
