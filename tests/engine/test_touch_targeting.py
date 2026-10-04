"""Touch grants use physical contact without manufacturing visual perception."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_available_action, register_spell
from dnd.conditions import Blinded, Invisible
from dnd.content.items.window_builders import place_window
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.core.base_tiles import dark_floor_factory
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.spells.divination import TrueSeeing
from dnd.spells.evocation import FireBolt
from dnd.spells.transmutation import DarkvisionSpell, Longstrider
from dnd.types.world import CardinalDirection
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


def scene(spell_type, *, dark=True):
    reset_spell_regression_arena(8, 8)
    if dark:
        for x in range(8):
            for y in range(8):
                get_map().set_tile(x, y, tile=dark_floor_factory((x, y)), fire_event=False)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={spell_type(source_entity_uuid=uuid4()).spell_level: 2, 2: 2})
    ally = create_spell_regression_actor("Ally", (3, 2), "heroes")
    register_spell(caster, spell_type)
    register_spell(caster, FireBolt)
    Entity.update_all_entities_senses()
    return caster, ally


def recipients(caster, name):
    return {target.target_uuid for row in caster.get_available_actions().entity_actions
            if row.display_name.startswith(name) for target in row.valid_targets}


@pytest.mark.parametrize("spell_type", [DarkvisionSpell, TrueSeeing, Longstrider])
@pytest.mark.parametrize("dark", [False, True])
def test_touch_grants_discover_self_and_neighbors_without_sight(spell_type, dark):
    caster, ally = scene(spell_type, dark=dark)
    if not dark:
        caster.add_condition(Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    assert ally.uuid not in caster.senses.entities
    assert recipients(caster, spell_type(source_entity_uuid=uuid4()).name) == {caster.uuid, ally.uuid}
    assert recipients(caster, "Fire Bolt") == set()
    assert ally.uuid not in caster.senses.entities
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled
    assert spell_type(source_entity_uuid=uuid4()).name in ally.active_conditions


@pytest.mark.parametrize("spell_type", [DarkvisionSpell, TrueSeeing, Longstrider])
@pytest.mark.parametrize("concealment", ["invisible", "hidden", "distant", "undeployed", "enemy", "dead"])
def test_touch_grants_do_not_disclose_or_accept_ineligible_recipients(spell_type, concealment):
    caster, ally = scene(spell_type)
    if concealment == "invisible":
        ally.add_condition(Invisible(source_entity_uuid=ally.uuid, target_entity_uuid=ally.uuid))
    elif concealment == "hidden":
        ally.set_stealth_dc(100)
    elif concealment == "distant":
        Entity.update_entity_position(ally, (5, 2))
    elif concealment == "undeployed":
        ally = Entity.create(uuid4(), "Unplaced", config=EntityConfig(position=(3, 2), faction="heroes"))
        ally.compose_entity()
    elif concealment == "dead":
        ally.receive_damage(1000, DamageType.FORCE, caster.uuid)
    else:
        ally.faction = "monsters"
    Entity.update_all_entities_senses()
    assert ally.uuid not in recipients(caster, spell_type(source_entity_uuid=uuid4()).name)
    before = caster.action_economy.actions.normalized_score
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == before


@pytest.mark.parametrize("spell_type", [DarkvisionSpell, TrueSeeing, Longstrider])
def test_touch_grant_requires_real_window_contact_even_when_window_unseen(spell_type):
    caster, ally = scene(spell_type)
    assembly = place_window("environment.window.fantasy_g8", (2, 2), CardinalDirection.EAST)
    assert assembly.insert is not None
    assert ally.uuid not in recipients(caster, spell_type(source_entity_uuid=uuid4()).name)
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and result.canceled
    assembly.insert.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assert ally.uuid in recipients(caster, spell_type(source_entity_uuid=uuid4()).name)
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled


@pytest.mark.parametrize("spell_type", [DarkvisionSpell, TrueSeeing, Longstrider])
def test_touch_grant_cannot_reach_diagonally_around_a_closed_boundary(spell_type):
    caster, ally = scene(spell_type)
    Entity.update_entity_position(ally, (3, 3))
    place_window("environment.window.fantasy_g8", (2, 2), CardinalDirection.EAST)
    assert ally.uuid not in recipients(caster, spell_type(source_entity_uuid=uuid4()).name)
    before = caster.action_economy.actions.normalized_score
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == before


@pytest.mark.parametrize("spell_type", [DarkvisionSpell, TrueSeeing, Longstrider])
def test_item_grant_uses_the_same_unseen_contact_candidates_and_execution(spell_type):
    caster, ally = scene(spell_type)
    grant = spell_type(source_entity_uuid=caster.uuid, template=True)
    item = build_spell_device(item_id="environment.fireball_cannon", name="Touch grant", spell_templates=[grant], charges=1)
    item.is_pickable = True
    assert caster.loot_item(item)
    available = caster.get_available_actions()
    row = next(row for row in available.entity_actions if row.source_item_uuid == item.uuid)
    target = next(target for target in row.valid_targets if target.target_uuid == ally.uuid)
    assert ally.uuid not in caster.senses.entities
    result = execute_available_action(caster, row, target)
    assert result is not None and not result.canceled
    assert grant.name in ally.active_conditions and item.charges == 0


@pytest.mark.parametrize("slot", [1, 2])
def test_longstrider_upcast_admits_all_touch_recipients_before_spending(slot):
    caster, ally = scene(Longstrider)
    other = create_spell_regression_actor("Other ally", (2, 3), "heroes")
    Entity.update_all_entities_senses()
    before = caster.action_economy.actions.normalized_score
    result = Longstrider(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[other.uuid], cast_at_level=slot).apply()
    assert result is not None
    assert result.canceled == (slot == 1)
    assert ("Longstrider" in ally.active_conditions) == (slot == 2)
    assert ("Longstrider" in other.active_conditions) == (slot == 2)
    if slot == 1:
        assert caster.action_economy.actions.normalized_score == before
