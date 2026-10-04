"""Native observer packets disclose conversion direction without private amounts."""

import pytest

from game.player_facts import ActionFact
from tests.game.class_feature_scenarios import class_feature_history
from tests.game.player_helpers import player_history


@pytest.mark.parametrize("program,label", [
    ("font_gather", "Convert slot to sorcery points"),
    ("font_shape", "Convert sorcery points to slot"),
])
def test_identified_foreign_font_conversion_redacts_amounts_from_fact_and_log(program, label):
    history = class_feature_history(program=program)
    for role in ("owner", "observer"):
        _, roots = player_history(history, role=role)
        rows = [node for root in roots for node in root.events
            if isinstance(node.fact, ActionFact) and node.fact.font_conversion is not None]
        assert len(rows) == 1
        node = rows[0]
        fact = node.fact
        assert isinstance(fact, ActionFact) and fact.font_conversion is not None
        if role == "owner":
            assert fact.font_conversion.slot_level == 2
            assert fact.font_conversion.sorcery_points_delta in (2, -3)
            assert fact.name is not None and "L2" in fact.name
        else:
            assert fact.font_conversion.slot_level is None
            assert fact.font_conversion.sorcery_points_delta is None
            assert fact.font_conversion.spell_slots_delta is None
            assert fact.name == label
            assert node.combat_log is not None
            assert node.combat_log.data["action_name"] == label
            for text in (node.combat_log.compact, node.combat_log.verbose, node.combat_log.detailed):
                assert label in text and "L2" not in text and "3SP" not in text


@pytest.mark.parametrize("program", ["font_gather", "font_shape"])
def test_unidentified_conversion_does_not_gain_a_foreign_action_fact(program):
    history = class_feature_history(program=program, hidden_owner=True)
    _, roots = player_history(history, role="observer")
    assert not any(isinstance(node.fact, ActionFact) and node.fact.font_conversion is not None
        for root in roots for node in root.events)
    assert not any(node.combat_log is not None and any(label in node.combat_log.compact
        for label in ("Slot→SP", "SP→Slot", "Convert slot to sorcery", "Convert sorcery points"))
        for root in roots for node in root.events)
