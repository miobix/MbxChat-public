import functools
import http.server
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

DEMO = json.loads((Path(__file__).parents[1] / "demo" / "conversations.json").read_text(encoding="utf-8"))


def _items():
    for group in DEMO["groups"]:
        assert group["title"] and group["note"] and group["items"], group["title"]
        for item in group["items"]:
            yield group["title"] + " | " + item["label"], item["events"]


def test_every_event_replays_against_what_was_on_screen():
    for name, events in _items():
        scene = {"title": name}
        shown: dict[int, list[list[str]]] = {}
        last_t = 0
        for e in events:
            assert e["t"] >= last_t, (scene["title"], e)
            last_t = e["t"]
            if e["op"] in ("user", "send"):
                assert e["id"] not in shown
                shown[e["id"]] = e.get("buttons") or []
                assert e.get("reply_to") is None or e["reply_to"] in shown
            elif e["op"] in ("edit", "edit_buttons"):
                shown[e["id"]] = e.get("buttons") or []
            elif e["op"] == "tap":
                assert any(e["label"] in row for row in shown[e["id"]]), (scene["title"], e)
            elif e["op"] == "delete":
                shown.pop(e["id"])
            else:
                assert e["op"] in ("react", "toast"), e


def test_the_demo_names_what_it_leaves_out():
    page = (Path(__file__).parents[1] / "demo" / "index.html").read_text(encoding="utf-8")
    assert "MbxRead" in page and "Anki" in page and "recorded" in page


def test_counts_add_up_and_no_kept_run_carries_a_failure():
    assert DEMO["kept"] == sum(len(g["items"]) for g in DEMO["groups"])
    for name, events in _items():
        assert not any("⚠️" in e.get("html", "") for e in events), name


def _chrome() -> str | None:
    found = shutil.which("google-chrome") or shutil.which("chrome")
    win = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    return found or (str(win) if win.exists() else None)


def test_every_scene_renders_in_a_browser(tmp_path):
    chrome = _chrome()
    if not chrome:
        assert not os.environ.get("CI"), "CI needs Chrome for the demo smoke test"
        pytest.skip("no Chrome")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=Path(__file__).parents[1] / "demo")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for n in range(len(DEMO["groups"])):
            dom = subprocess.run(
                [chrome, "--headless=new", "--no-sandbox", "--force-prefers-reduced-motion",
                 f"--user-data-dir={tmp_path}", "--virtual-time-budget=8000", "--dump-dom",
                 f"http://127.0.0.1:{server.server_port}/#{n}"],
                capture_output=True, text=True, encoding="utf-8", timeout=60,
            ).stdout
            assert dom.count('class="bubble"') >= 2, f"scene {n} rendered no chat"
    finally:
        server.shutdown()
