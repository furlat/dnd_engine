"""Combat ends when a side has no conscious bodies, preserving surviving lives."""

import pytest
from uuid import uuid4

from dnd.conditions import Incapacitated, Paralyzed, Stunned, Unconscious
from dnd.controller import HumanController
from dnd.entity import Entity, EntityConfig
from dnd.blocks.health import HealthConfig
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DeathSaveEvent, EncounterEndEvent, EventPhase, EventQueue
from dnd.core.life_types import LifeState
from dnd.encounter import EncounterState
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import GlyphSleepEffect
from dnd.spells.enchantment import SleepEffect
from dnd.spells.necromancy import EyebiteAsleepEffect
from dnd.spells.summoning import SpiritualWeapon
from tests.engine.test_encounter_apis import create_book_pair, reset_chapter_18_state, start_ordered_encounter
from tests.engine.test_summoning_lifecycle import battle, cast_one


@pytest.mark.parametrize('condition_type,ends', [
    (Unconscious, True), (SleepEffect, True), (EyebiteAsleepEffect, True), (GlyphSleepEffect, True),
    (Incapacitated, False), (Paralyzed, False), (Stunned, False),
])
@pytest.mark.parametrize('renamed', [False, True], ids=['authored-name', 'renamed'])
def test_positive_hp_unconsciousness_ends_combat_but_conscious_incapacitation_does_not(condition_type, ends, renamed):
    reset_chapter_18_state()
    hero, enemy = create_book_pair()
    encounter = start_ordered_encounter(hero, enemy, HumanController(source_entity_uuid=hero.uuid),
        HumanController(source_entity_uuid=enemy.uuid), enemy)
    hp = hero.get_normal_hp()
    applied = hero.add_condition(condition_type(source_entity_uuid=enemy.uuid, target_entity_uuid=hero.uuid,
        **({'name': 'Scenario impairment'} if renamed else {})))
    assert applied is not None and not applied.canceled
    assert not hero.can_take_actions()
    cursor = EventQueue.event_cursor()
    encounter.check_deaths()
    assert (encounter.state is EncounterState.ENDED) is ends
    assert hero.health.life_state is LifeState.ALIVE and hero.get_normal_hp() == hp
    finished = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    assert sum(isinstance(event, EncounterEndEvent) for event in finished) == int(ends)
    assert not any(isinstance(event, DeathSaveEvent) for event in finished)
    reset_engine_runtime()


@pytest.mark.parametrize('stable', [False, True], ids=['dying', 'stable'])
@pytest.mark.parametrize('summon', [False, True], ids=['alone', 'conscious-summon'])
def test_downed_caster_cannot_keep_side_fighting_through_its_summon(battle, stable, summon):
    _, encounter, _, caster, enemy = battle
    caster.uses_death_saves = True
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3) if summon else None
    caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
    if stable:
        caster.stabilize()
    expected_life = LifeState.STABLE if stable else LifeState.DYING
    cursor = EventQueue.event_cursor()
    encounter.check_deaths()
    assert encounter.state is EncounterState.ENDED
    assert caster.health.life_state is expected_life
    assert caster.get_normal_hp() == 0
    assert not any(isinstance(event, DeathSaveEvent) for _, event in EventQueue.iter_events_since(cursor))
    if member is not None:
        assert member.entity.uuid not in encounter.combatants
        assert not member.entity.has_runtime_agency()


def test_conscious_ally_keeps_a_dying_casters_death_save_turn(battle):
    game, encounter, _, caster, enemy = battle
    ally = Entity.create(source_entity_uuid=uuid4(), name='Standing ally', config=EntityConfig(
        faction=caster.faction, position=(4, 3), health=HealthConfig(max_hit_points_bonus=20)))
    ally.compose_entity()
    game.deploy_entity(ally, ally.position)
    encounter.add_combatant(ally, HumanController(source_entity_uuid=ally.uuid))
    encounter.initiative_order.append(ally.uuid)
    caster.uses_death_saves = True
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
    encounter.check_deaths()
    assert encounter.state is EncounterState.ACTIVE
    encounter.next_turn()
    assert encounter.get_current_entity() is enemy
    encounter.next_turn()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(10):
        encounter.next_turn()
    assert encounter.get_current_entity() is caster
    saves = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DeathSaveEvent) and event.phase is EventPhase.COMPLETION]
    assert len(saves) == 1 and caster.death_save_successes == 1
    assert caster.health.life_state is LifeState.DYING
    assert encounter.state is EncounterState.ACTIVE
