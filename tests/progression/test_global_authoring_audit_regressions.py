"""Public authoring/build outcomes for new global-audit failures awaiting repair."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.content.characters.builds import create_character
from dnd.content.items.authored_item_builders import materialize_item_definition
from dnd.content.items.authored_item_definitions import AUTHORED_WEARABLE_DEFINITIONS
from dnd.content.items.item_composition import with_armor_penalties
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.core.equipment_types import BodyPart
from dnd.entity import Entity
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture export
from tests.progression.test_direct_character_builds import _custom_build


@pytest.mark.parametrize("item_id", [
    pytest.param("unknown.audit_item", id="unknown-item-control"),
    pytest.param("environment.directional_wall", marks=pytest.mark.xfail(
        strict=True, raises=AssertionError, reason="GA-06: rejected build leaves registered wall",
    )),
    pytest.param("environment.wall_torch", marks=pytest.mark.xfail(
        strict=True, raises=AssertionError, reason="GA-06: rejected build leaves registered wall torch",
    )),
])
def test_rejected_character_loadout_leaves_no_world_items(game, item_id):
    before = frozenset(item.uuid for item in BaseItem.get_all_items())
    actor_uuid = uuid4()
    build = replace(_custom_build(), item_loadout=(ItemLoadoutEntry(item_id),))
    with pytest.raises(ValueError):
        create_character(build, runtime_entity_uuid=actor_uuid)
    assert Entity.get(actor_uuid) is None
    assert frozenset(item.uuid for item in BaseItem.get_all_items()) == before


@pytest.mark.parametrize("explicit_property", [
    pytest.param(True, id="existing-penalty-composition-control"),
    pytest.param(False, id="authored-strength-only", marks=pytest.mark.xfail(
        strict=True, raises=AssertionError, reason="GA-07: strength-only wearable field is inert",
    )),
])
def test_authored_strength_requirement_uses_existing_armor_penalty(game, explicit_property):
    actor = combatant(game)  # STR 10; normal speed 30.
    definition = replace(
        AUTHORED_WEARABLE_DEFINITIONS["armor.chain_mail"],
        stealth_disadvantage=False, strength_requirement=15, item_properties=(),
    )
    if explicit_property:
        definition = with_armor_penalties(definition, stealth_disadvantage=False, strength_requirement=15)
    armor = materialize_item_definition(definition, actor.uuid)
    assert actor.loot_item(armor)
    assert actor.equip_item(armor.uuid, BodyPart.BODY)
    assert armor.strength_requirement == 15
    assert not armor.stealth_disadvantage
    speed = actor.action_economy.current_speed()
    assert speed == 20
