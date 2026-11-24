import json
from pathlib import Path

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
