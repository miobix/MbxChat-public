from evals.grader_eval import HERE, corrected_ok, fixes, parse, summary


def test_the_set_parses_and_fixes_score():
    items = parse((HERE / "grader_set.md").read_text(encoding="utf-8"))
    assert len(items) == 66 and sum(i["verdict"] == "correct" for i in items) == 18
    g65 = next(i for i in items if i["id"] == "g65")
    assert fixes(g65["errors"]) == [["끝내지", "마무리하지"], ["못했습니다", "못했어요"]]
    assert corrected_ok(g65, {"corrected": "아파서 보고서를 마무리하지 못했어요."})
    assert not corrected_ok(g65, {"corrected": "아파서 보고서를 끝내지 못했어."})
    g01 = items[0]
    assert corrected_ok(g01, {"corrected": g01["answer"] + "!"}) and not corrected_ok(g01, {"error": "x"})
    s = summary("m", [g01, g65], [{"verdict": "minor", "corrected": "", "seconds": 2.0}, {"error": "x"}])
    assert (s["false_alarms"], s["failures"], s["verdict"]) == (1, 1, 0)


def test_unchecked_items_are_left_out():
    text = "### g1 · x\n- answer: a\n- check:\n\n### g2 · x\n- answer: b\n- check: drop\n\n### g3 · x\n- check: fix y\n"
    assert [i["id"] for i in parse(text)] == ["g3"]
