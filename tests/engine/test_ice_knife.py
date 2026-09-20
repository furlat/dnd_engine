"""Discovered Ice Knife casts preserve attack, burst, costs and native geometry."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import register_counterspell_reaction
from dnd.spells.ice_knife import ICE_KNIFE_BURST, IceKnife
from dnd.types.world import CardinalDirection


@pytest.fixture
def world() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 7))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(world: Game, name: str, position: tuple[int, int], faction: str, *, caster: bool = False,
          counterspell: bool = False) -> Entity:
    entity = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction=faction,
        ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(spell_slots={1: 2, 3: 2}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=10, mode="maximums")]),
    ))
    setup_standard_actions(entity)
    if caster:
        register_spell(entity, IceKnife)
    if counterspell:
        register_counterspell_reaction(entity)
    entity.compose_entity()
    world.deploy_entity(entity, position)
    return entity


def cast(caster: Entity, target: Entity, dice: tuple[int, ...], *, level: int = 1):
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    offered = next(row for row in available.all_actions
                   if row.behavior_id == "spell.ice_knife" and row.cast_at_level == level)
    selected = next(row for row in offered.valid_targets if row.target_uuid == target.uuid)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*dice):
        result = execute_available_action(caster, offered, selected)
    assert isinstance(result, SpellEvent)
    return result, [event for _, event in EventQueue.iter_events_since(cursor)]


@pytest.mark.parametrize("outcome,level,save_success,piercing,cold", (
    (AttackOutcome.HIT, 1, False, 3, 4),
    (AttackOutcome.MISS, 1, False, 0, 4),
    (AttackOutcome.CRIT, 1, False, 6, 4),
    (AttackOutcome.HIT, 3, False, 3, 8),
    (AttackOutcome.CRIT, 3, False, 6, 8),
    (AttackOutcome.HIT, 1, True, 3, 0),
    (AttackOutcome.MISS, 1, True, 0, 0),
))
def test_attack_then_burst_once_per_paid_cast(world, outcome, level, save_success, piercing, cold):
    caster = actor(world, "Caster", (1, 3), "heroes", caster=True)
    victim = actor(world, "Victim", (4, 3), "enemies")
    ally = actor(world, "Ally", (4, 4), "heroes")
    outside = actor(world, "Outside", (6, 3), "enemies")
    roll = {AttackOutcome.HIT: 18, AttackOutcome.MISS: 2, AttackOutcome.CRIT: 20}[outcome]
    dice = (roll,) + (3,) * (2 if outcome is AttackOutcome.CRIT else int(outcome is AttackOutcome.HIT))
    dice += (2,) * (level + 1) + (20 if save_success else 1,) * 2
    health = {entity.uuid: entity.get_hp() for entity in (caster, victim, ally, outside)}
    result, events = cast(caster, victim, dice, level=level)
    assert result.phase is EventPhase.COMPLETION and not result.canceled
    assert result.attack_outcome is outcome
    assert victim.get_hp() == health[victim.uuid] - piercing - cold
    assert ally.get_hp() == health[ally.uuid] - cold
    assert outside.get_hp() == health[outside.uuid]
    assert caster.get_hp() == health[caster.uuid]
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_value(level).normalized_score == 1
    spells = [event for event in events if isinstance(event, SpellEvent)]
    assert len([event for event in spells if event.phase is EventPhase.DECLARATION]) == 1
    assert len([event for event in spells if event.phase is EventPhase.EXECUTION]) == 1
    burst, = [event for event in spells if event.effect_id == ICE_KNIFE_BURST
              and event.phase is EventPhase.COMPLETION and event.application_id is None]
    assert burst.behavior_id == result.behavior_id == "spell.ice_knife"
    assert burst.aoe_position == victim.position
    assert burst.parent_event is not None
    parent = EventQueue.get_event_by_uuid(burst.parent_event)
    assert parent is not None and parent.lineage_uuid == result.lineage_uuid
    applications = [event for event in spells if event.application_id is not None and event.phase is EventPhase.COMPLETION]
    assert {event.target_entity_uuid for event in applications} == {victim.uuid, ally.uuid}
    for application in applications:
        assert application.parent_event is not None
        owner = EventQueue.get_event_by_uuid(application.parent_event)
        assert owner is not None and owner.lineage_uuid == burst.lineage_uuid
    injuries = [event for event in events if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
    assert sum(event.normal_hit_point_damage for event in injuries if event.damage_type is DamageType.PIERCING) == piercing
    assert sum(event.normal_hit_point_damage for event in injuries if event.damage_type is DamageType.COLD) == cold * 2


def test_nearby_caster_is_included_but_boundary_blocks_burst(world):
    caster = actor(world, "Caster", (3, 3), "heroes", caster=True)
    victim = actor(world, "Victim", (4, 3), "enemies")
    sheltered = actor(world, "Sheltered", (5, 3), "enemies")
    build_directional_wall().place_on_grid((4, 3), boundary_direction=CardinalDirection.EAST)
    initial = [entity.get_hp() for entity in (caster, victim, sheltered)]
    # The nearby hostile imposes ranged disadvantage, then one damage roll and
    # the burst's shared cold roll precede the caster/victim saves.
    result, events = cast(caster, victim, (18, 18, 3, 2, 2, 1, 1))
    assert not result.canceled
    assert [entity.get_hp() for entity in (caster, victim, sheltered)] == [initial[0] - 4, initial[1] - 7, initial[2]]
    burst, = [event for event in events if isinstance(event, SpellEvent)
              and event.effect_id == ICE_KNIFE_BURST and event.phase is EventPhase.COMPLETION
              and event.application_id is None]
    assert burst.resolved_area_positions is not None
    assert caster.position in burst.resolved_area_positions
    assert sheltered.position not in burst.resolved_area_positions


def test_counterspell_cancels_the_cast_before_either_damage_branch(world):
    caster = actor(world, "Caster", (1, 3), "heroes", caster=True)
    victim = actor(world, "Counterspeller", (4, 3), "enemies", counterspell=True)
    health = victim.get_hp()
    result, events = cast(caster, victim, ())
    assert result.canceled
    assert victim.get_hp() == health
    assert victim.action_economy.reactions.normalized_score == 0
    assert victim.action_economy.spell_slot_3.normalized_score == 1
    assert not any(isinstance(event, SpellEvent) and event.effect_id == ICE_KNIFE_BURST for event in events)


def test_cold_affinity_applies_to_shared_cold_roll_not_piercing(world):
    caster = actor(world, "Caster", (1, 3), "heroes", caster=True)
    victim = actor(world, "Victim", (4, 3), "enemies")
    ally = actor(world, "Ally", (4, 4), "heroes")
    caster.spellcasting.add_spell_damage_affinity_contribution(
        source_id=uuid4(), damage_type=DamageType.COLD, ability_name="intelligence")
    initial = victim.get_hp(), ally.get_hp()
    result, _ = cast(caster, victim, (18, 3, 2, 2, 1, 1))
    assert not result.canceled
    assert result.total_damage == 3
    assert victim.get_hp() == initial[0] - 3 - 8
    assert ally.get_hp() == initial[1] - 8
