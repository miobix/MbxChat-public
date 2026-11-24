"""Grader eval (SPEC §9): the proofread set against Ollama models, each run a Phoenix experiment.

Host only, eval deps installed: .venv/Scripts/python -m evals.grader_eval [--with-pending] MODEL [MODEL ...]
--with-pending adds items marked `check: pending` (not yet proofread); results go to separate files.
MODEL is an Ollama model, `dadeum`, or `<ollama model>+dadeum` (dadeum's edit as a hint).
"""
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

from mbxchat.practice import bare, grade

HERE = Path(__file__).parent
PHOENIX = "http://127.0.0.1:6006"
DADEUM = ("onelastkissforme/dadeum-gec-base", "d2af339da05d89750c38db6331b3ddbd3b3d5219")


def parse(text: str, pending: bool = False) -> list[dict]:
    """Checked items only (`check: ok` or `check: fix ...`), plus `check: pending` if asked."""
    items = []
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        head, *lines = block.strip().splitlines()
        f = {m[1]: m[2].strip() for m in (re.match(r"- (\w+): ?(.*)", ln) for ln in lines) if m}
        if f.get("check", "").startswith(("ok", "fix") + (("pending",) if pending else ())):
            items.append({"id": head.split()[0], "group": head.split("·")[-1].strip()} | f)
    return items


def fixes(errors: str) -> list[list[str]]:
    """Each labeled fix as its accepted spellings: '끝나지 → 끝내지 (or 마무리하지): why' → ['끝내지', '마무리하지']."""
    out = []
    for part in errors.split(";"):
        if "→" in part:
            right = part.split("→", 1)[1].split(":")[0]
            out.append([a.strip() for a in re.split(r"\(or |\)", right) if a.strip()])
    return out


def prompt(item: dict) -> dict:
    return {"kind": item["task"], "en": item["prompt"], "word": item.get("word"),
            "situation": item.get("situation", ""), "register": "", "reference": item.get("reference")}


def corrected_ok(item: dict, out: dict) -> bool:
    # ponytail: substring match on the fix; a short fix (와) can match by accident, a rephrased fix is missed
    if "corrected" not in out:
        return False
    if item["verdict"] == "correct":
        return bare(out["corrected"]) == bare(item["answer"])
    return all(any(bare(a) in bare(out["corrected"]) for a in alts) for alts in fixes(item["errors"]))


def summary(model: str, items: list[dict], outs: list[dict]) -> dict:
    pairs = list(zip(items, outs))
    ok = [o for o in outs if "verdict" in o]
    secs = sorted(o["seconds"] for o in ok) or [0.0]
    return {
        "model": model,
        "n": len(items),
        "verdict": sum(o.get("verdict") == i["verdict"] for i, o in pairs),
        "false_alarms": sum(i["verdict"] == "correct" and o.get("verdict") != "correct" for i, o in pairs),
        "correct_items": sum(i["verdict"] == "correct" for i in items),
        "missed": sum(i["verdict"] != "correct" and o.get("verdict") == "correct" for i, o in pairs),
        "corrected_ok": sum(corrected_ok(i, o) for i, o in pairs),
        "failures": len(outs) - len(ok),
        "reference_hits": sum(bool(i.get("reference")) and bare(i["answer"]) == bare(i["reference"]) for i in items),
        "median_s": round(statistics.median(secs), 1),
        "p90_s": round(secs[int(0.9 * (len(secs) - 1))], 1),
    }


def dadeum():
    """The GEC model as a grader: an unchanged answer counts as 'correct', any edit as 'minor'."""
    import importlib.util

    from huggingface_hub import snapshot_download

    path = Path(snapshot_download(DADEUM[0], revision=DADEUM[1]))
    spec = importlib.util.spec_from_file_location("dadeum_correct", path / "dadeum_correct.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    corrector = mod.Corrector(path)

    def fix(item: dict) -> dict:
        out = corrector.correct(item["answer"])
        return {"corrected": out, "verdict": "correct" if out == item["answer"] else "minor"}
    return fix


def run(model: str, items: list[dict], client, dataset, tag: str = "") -> dict:
    from phoenix.client.experiments import run_experiment

    by_id = {i["id"]: i for i in items}
    outs = {}
    if model == "dadeum":
        fn = dadeum()
    elif model.endswith("+dadeum"):  # dadeum's edit, when it makes one, goes in as a hint
        fix = dadeum()

        def fn(i):
            hint = fix(i)["corrected"]
            p = prompt(i) | {"hint": hint if hint != i["answer"] else None}
            return grade(p, i["answer"], model.removesuffix("+dadeum")).model_dump()
    else:
        fn = lambda i: grade(prompt(i), i["answer"], model).model_dump()
    fn(items[0])  # load the model outside the timings

    def task(input):
        t = time.perf_counter()
        try:
            out = fn(input)
        except Exception as e:  # an invalid answer twice is a score, not a crash
            out = {"error": str(e)}
        outs[input["id"]] = out | {"seconds": round(time.perf_counter() - t, 1)}
        return outs[input["id"]]

    def verdict(output, input):
        return output.get("verdict") == by_id[input["id"]]["verdict"]

    def flag_agrees(output, input):
        return (output.get("verdict", "correct") == "correct") == (by_id[input["id"]]["verdict"] == "correct")

    def correction(output, input):
        return corrected_ok(by_id[input["id"]], output)

    run_experiment(dataset=dataset, task=task, evaluators=[verdict, flag_agrees, correction],
                   experiment_name=f"grader {model}", experiment_metadata={"model": model},
                   client=client, timeout=600, retries=0, print_summary=False)
    ordered = [outs.get(i["id"], {"error": "not run"}) for i in items]
    slug = re.sub(r"[^\w.-]+", "_", model) + tag
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"grader-{slug}.json").write_text(
        json.dumps([{"id": i["id"]} | o for i, o in zip(items, ordered)], ensure_ascii=False, indent=1),
        encoding="utf-8")
    return summary(model, items, ordered)


def main(models: list[str]) -> None:
    from phoenix.client import Client

    pending = "--with-pending" in models
    models = [m for m in models if m != "--with-pending"]
    text = (HERE / "grader_set.md").read_text(encoding="utf-8")
    items = parse(text, pending)
    client = Client(base_url=PHOENIX)
    name = f"grader_set-{hashlib.sha256(json.dumps(items).encode()).hexdigest()[:8]}"
    try:
        dataset = client.datasets.get_dataset(dataset=name)
    except Exception:
        dataset = client.datasets.create_dataset(
            name=name, inputs=[{k: v for k, v in i.items() if k not in ("verdict", "errors", "check")} for i in items],
            outputs=[{"verdict": i["verdict"], "errors": i["errors"]} for i in items])
    for m in models:
        line = json.dumps({"date": time.strftime("%Y-%m-%d"), "set": name} | run(m, items, client, dataset, "-pending" * pending),
                          ensure_ascii=False)
        print(line, flush=True)
        with (HERE / "results" / "grader_summary.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
