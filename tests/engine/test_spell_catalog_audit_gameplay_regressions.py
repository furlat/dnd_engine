"""Native gameplay regressions confirmed by the full spell ownership audit.

The retained independent cases are ordinary regressions after repair.
Feature-specific Antimagic cases were retired with the feature.
"""

from dataclasses import replace

import pytest

from dnd.actions import Attack
from dnd.conditions import Charmed
from dnd.content.characters.builds import create_character
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.condition_types import DurationType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.entity import Entity
from dnd.spells.enchantment import CharmPerson, HoldMonster, HoldPerson
from dnd.spells.evocation import CureWounds, FireBolt
from dnd.spells.illusion import HypnoticPattern
from dnd.spells.necromancy import ChillTouch
from dnd.spells.transmutation import (
    BonusDash,
    EnlargeReduce,
    EnlargeReduceEffect,
    ExpeditiousRetreat,
    ExpeditiousRetreatEffect,
    Haste,
)
from dnd.types.character_progression import (
    CharacterClass,
    PreparedSpellSelection,
    Species,
)
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture re-export
from tests.manual.spell_regression_support import force_save_result
from tests.progression.prepared_class_support import prepared_build


def cast(spell_type, caster, target=None, **kwargs):
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell_type(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid if target is not None else caster.uuid,
        alt_skip_slot=True,
        **kwargs,
    ).apply()
    assert result is not None and not result.canceled, result
    return result


def wizard(game, prepared=(), *, species=Species.HUMAN):
    build = prepared_build(CharacterClass.WIZARD, 5)
    actor = create_character(
        replace(
            build,
            species=species,
            origin_choices=build.origin_choices if species is Species.HUMAN else (),
            faction="heroes",
            scribed_spell_ids=prepared,
            prepared_spells=(
                PreparedSpellSelection("class.wizard.spellcasting", prepared),
            ),
        )
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor




def reject_condition_application(actor, condition_type):
    def reject(event, _source_uuid):
        if isinstance(event, ConditionApplicationEvent) and isinstance(
            event.condition, condition_type
        ):
            return event.cancel(status_message="Audit scenario denies this condition")
        return None

    actor.add_event_handler(
        EventHandler(
            name="Audit condition admission",
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=actor.uuid,
                )
            ],
            event_processor=reject,
        )
    )


def test_ending_hold_person_preserves_another_active_hold(game):
    monster_caster = combatant(game)
    person_caster = combatant(game, "Second caster", (2, 3))
    target = combatant(game, "Held enemy", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)

    cast(HoldMonster, monster_caster, target)
    cast(HoldPerson, person_caster, target)
    target.remove_condition("Hold Person")

    conditions = set(target.active_conditions)
    actions = target.action_economy.actions.normalized_score
    assert "Hold Monster" in conditions
    assert "Paralyzed" in conditions
    assert actions == 0


def test_charmed_actor_cannot_hold_its_charmer(game):
    charmer = combatant(game)
    target = combatant(game, "Charmed enemy", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    force_save_result(charmer, "wisdom", succeeds=False)
    cast(CharmPerson, charmer, target)
    assert any(c.get_display_name() == "Charmed" for c in target.active_conditions_by_uuid.values())

    result = HoldPerson(
        source_entity_uuid=target.uuid,
        target_entity_uuid=charmer.uuid,
        alt_skip_slot=True,
    ).apply()

    canceled = result.canceled if result is not None else None
    conditions = set(charmer.active_conditions)
    actions = target.action_economy.actions.normalized_score
    assert canceled is True
    assert "Paralyzed" not in conditions
    assert actions == 1


def test_charm_person_ends_when_the_charmer_harms_its_recipient(game):
    charmer = combatant(game)
    target = combatant(game, "Charmed enemy", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(CharmPerson, charmer, target)
    assert any(c.get_display_name() == "Charmed" for c in target.active_conditions_by_uuid.values())

    target.receive_damage(1, DamageType.FORCE, charmer.uuid)

    conditions = {c.get_display_name() for c in target.active_conditions_by_uuid.values()}
    assert "Charmed" not in conditions


def test_charm_person_has_a_finite_owning_spell_duration(game):
    charmer = combatant(game)
    target = combatant(game, "Charmed enemy", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(CharmPerson, charmer, target)

    durations = tuple(
        condition.snapshot_state().duration
        for condition in target.active_conditions_by_uuid.values()
        if condition.effect_origin is not None
        and condition.effect_origin.source_id == "spell.charm_person"
    )
    finite = any(
        duration is not None
        and duration.duration_type is DurationType.ROUNDS
        and duration.remaining_rounds > 0
        for duration in durations
    )
    assert durations
    assert finite is True, durations








def test_replacing_enlarge_stays_enlarged_and_final_removal_restores_base_size(game):
    first = combatant(game)
    second = combatant(game, "Second caster", (2, 3))
    target = combatant(game, "Recipient", (3, 2))
    original_size = target.size
    cast(EnlargeReduce, first, target)
    enlarged_size = target.size
    assert enlarged_size != original_size

    cast(EnlargeReduce, second, target)
    replacement_size = target.size
    target.remove_condition("Enlarge/Reduce")

    final_size = target.size
    assert (replacement_size, final_size) == (enlarged_size, original_size)


def test_rejected_enlarge_condition_does_not_change_creature_size(game):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3, 2))
    original_size = target.size
    reject_condition_application(target, EnlargeReduceEffect)

    EnlargeReduce(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        alt_skip_slot=True,
    ).apply()

    conditions = set(target.active_conditions)
    size = target.size
    assert "Enlarge/Reduce" not in conditions
    assert size == original_size


def test_rejected_retreat_condition_does_not_grant_bonus_dash(game):
    caster = combatant(game)
    reject_condition_application(caster, ExpeditiousRetreatEffect)

    ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        alt_skip_slot=True,
    ).apply()

    conditions = set(caster.active_conditions)
    dash_count = sum(isinstance(action, BonusDash) for action in caster.registered_actions)
    assert "Expeditious Retreat" not in conditions
    assert dash_count == 0






def test_haste_can_target_its_own_caster_with_normal_costs(game):
    caster = combatant(game)
    slots = caster.action_economy.spell_slot_3.normalized_score

    result = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    canceled = result.canceled if result is not None else None
    conditions = set(caster.active_conditions)
    actions = caster.action_economy.actions.normalized_score
    remaining_slots = caster.action_economy.spell_slot_3.normalized_score
    assert canceled is False
    assert "Haste" in conditions
    assert "Concentrating" in conditions
    assert actions == 0
    assert remaining_slots == slots - 1


@pytest.mark.parametrize(
    "denial",
    [
        pytest.param("immunity"),
        pytest.param("admission"),
        None,
    ],
)
def test_hypnotic_pattern_requires_its_charm_before_incapacitating(game, denial):
    caster = combatant(game)
    target = combatant(game, "Recipient", (5, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    if denial == "immunity":
        target.add_condition_immunity("Charmed", immunity_name="Native charm immunity")
    elif denial == "admission":
        reject_condition_application(target, Charmed)

    result = HypnoticPattern(
        source_entity_uuid=caster.uuid,
        end_position=target.position,
        alt_skip_slot=True,
    ).apply()
    assert result is not None

    expected_actions = 0 if denial is None else 1
    actions = target.action_economy.actions.normalized_score
    conditions = set(target.active_conditions)
    assert actions == expected_actions
    assert ("Hypnotic Pattern" in conditions) is (denial is None)


def test_ending_one_chill_touch_preserves_another_casters_healing_block(game):
    first = combatant(game)
    second = combatant(game, "Second caster", (2, 3))
    target = combatant(game, "Recipient", (4, 2), "foes")
    healer = combatant(game, "Recipient ally", (5, 2), "foes")
    for caster in (first, second):
        with fixed_dice_faces(20, *([2] * 10)):
            cast(ChillTouch, caster, target)
    effects = [c for c in target.active_conditions_by_uuid.values() if c.blocks_healing]
    assert len(effects) == 2
    second.on_turn_start()
    assert any(c.get_display_name() == "Chill Touch Effect" for c in target.active_conditions_by_uuid.values())
    before = target.get_hp()

    with fixed_dice_faces(2):
        cast(CureWounds, healer, target)

    hp = target.get_hp()
    assert hp == before
