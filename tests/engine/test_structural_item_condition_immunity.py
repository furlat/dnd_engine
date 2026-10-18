"""Structural immunity ownership remains independent of condition membership."""
from dnd.conditions import Poisoned
from dnd.content.items.authored_item_builders import build_authored_item
from tests.engine.test_roster_support_spells import game as game, actor


def test_structural_item_immunity_source_is_not_mistaken_for_a_condition(game):
    target = actor(game)
    item = build_authored_item('environment.furniture.clay_stove', source_entity_uuid=target.uuid)
    target.add_condition_immunity_source('Poisoned', item.uuid)
    poisoned = Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(poisoned)
    assert 'Poisoned' not in target.active_conditions
    assert target.remove_condition_immunity_source('Poisoned', item.uuid)
    target.add_condition(Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    assert 'Poisoned' in target.active_conditions
