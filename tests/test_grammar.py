import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mbxchat import bot, grammar, importer


@pytest.fixture
def points(db_url):
    importer.import_public()
    return grammar.load(db_url)


def keys(hits):
    return [p.data["form"] for p in hits]


@pytest.mark.parametrize("query, form", [
    ("-(으)면", "-으면"), ("면", "-으면"), ("으면서", "-으면서"), ("느라", "-느라고"), ("느라고", "-느라고"),
    ("-아서", "-어서"), ("~어서", "-어서"),
])
def test_match_is_loose_about_hyphens_allomorphs_and_optional_parts(points, query, form):
    assert form in keys(grammar.match(query, points))


def test_same_form_at_two_levels_gives_both(points):
    hits = grammar.match("는데", points)
    assert sorted((p.level, p.data["form"]) for p in hits) == [(2, "-는데1"), (2, "-는데2")]


@pytest.mark.parametrize("query", ["은/는", "은", "는"])
def test_slash_or_either_allomorph_finds_the_topic_particle(points, query):
    assert "은1" in keys(grammar.match(query, points))


def test_basics_are_known_after_import(points):
    assert [p.known for p in grammar.match("은/는", points) if p.data["form"] == "은1"] == [True]


def test_explainer_shows_refresher(points):
    point = next(p for p in points if p.data["form"] == "-으면")
    html = grammar.explainer(point)
    assert html.startswith("📖 <b>-(으)면</b>  ·  level 2")
    assert html.count("• ") == len(point.data["examples"])


def _cmd(*args):
    update, context = MagicMock(), MagicMock(args=list(args))
    update.message.reply_html = AsyncMock()
    return update, context


def _reply(update):
    call = update.message.reply_html.await_args
    return call.args[0], call.kwargs.get("reply_markup")


def test_grammar_cmd_single_match_explains_with_know_button(points):
    update, context = _cmd("-(으)면서")
    asyncio.run(bot.grammar_cmd(update, context))
    text, markup = _reply(update)
    assert "<b>-(으)면서</b>" in text
    assert markup.inline_keyboard[0][0].callback_data.startswith("known:")


def test_grammar_cmd_several_matches_offer_a_choice(points):
    update, context = _cmd("는데")
    asyncio.run(bot.grammar_cmd(update, context))
    text, markup = _reply(update)
    assert "Which one?" in text
    assert [row[0].callback_data[:5] for row in markup.inline_keyboard] == ["gram:", "gram:"]


def test_grammar_cmd_skips_basics(points):
    update, context = _cmd("을/를")
    asyncio.run(bot.grammar_cmd(update, context))
    assert "marked as known" in _reply(update)[0]


def test_grammar_cmd_no_match_and_no_args(points):
    update, context = _cmd("xyz")
    asyncio.run(bot.grammar_cmd(update, context))
    assert "No grammar point matches <b>xyz</b>" in _reply(update)[0]
    update, context = _cmd()
    asyncio.run(bot.grammar_cmd(update, context))
    assert "/grammar 는데" in _reply(update)[0]


def _tap(data):
    update = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def test_choosing_a_point_edits_in_place(points):
    point = grammar.match("는데", points)[0]
    update = _tap(f"gram:{point.id}")
    asyncio.run(bot.on_grammar(update, MagicMock()))
    call = update.callback_query.edit_message_text.await_args
    assert call.args[0] == grammar.explainer(point)
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"known:{point.id}"


def test_i_know_this_marks_known_and_removes_the_button(points, db_url):
    point = grammar.match("-(으)면서", points)[0]
    update = _tap(f"known:{point.id}")
    asyncio.run(bot.on_grammar(update, MagicMock()))
    assert grammar.get(db_url, point.id).known
    call = update.callback_query.edit_message_text.await_args
    assert "✓ Marked as known" in call.args[0] and "reply_markup" not in call.kwargs
