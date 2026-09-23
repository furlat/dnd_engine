"""Actual control spells retain effective sense denial until their last owner ends."""

from uuid import UUID

import pytest

from dnd.actions import SpellEvent
from dnd.conditions import Blinded, Deafened
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import AutoHitStatus
from dnd.entity import Entity
from dnd.spells.enchantment import CharmPerson
from dnd.spells.illusion import ColorSpray, Silence
from dnd.spells.necromancy import BlindnessDeafness
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena
from tests.engine.test_condition_lifecycle import EngineBookMarkerCondition


def actors() -> tuple[Entity, Entity, Entity]:
    reset_spell_regression_arena(20, 15)
    source = create_spell_regression_actor("Source", (2, 7), "heroes", spell_slots={1: 3, 2: 3})
    other = create_spell_regression_actor("Other", (7, 6), "heroes", spell_slots={1: 3, 2: 3})
    target = create_spell_regression_actor("Target", (8, 7), "monsters", hit_die_count=1)
    Entity.update_all_entities_senses(max_distance=120)
    return source, other, target


def cast(spell) -> SpellEvent:
    with fixed_dice_faces(*([1] * 16)):
        result = spell.apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    return result


def assert_deaf(target: Entity, expected: bool) -> None:
    assert ("Deafened" in target.active_conditions) is expected
    # Deafened's current mechanical contract is automatic failure for hearing skills.
    assert (target.skill_set.insight.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS) is expected


@pytest.mark.parametrize("first_cast", ("deafness", "silence"))
@pytest.mark.parametrize("first_remove", ("deafness", "silence"))
def test_silence_and_deafness_share_one_effective_lifetime(first_cast, first_remove) -> None:
    source, other, target = actors()
    spells = {
        "deafness": BlindnessDeafness(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                                     effect_type="deafened", cast_at_level=2),
        "silence": Silence(source_entity_uuid=other.uuid, end_position=target.position, cast_at_level=2),
    }
    # Keep the Silence caster outside its own zone so the second cast is legal.
    spells["silence"].source_entity_uuid = source.uuid
    spells["deafness"].source_entity_uuid = other.uuid
    # Other stands inside the eventual Silence: use its native nonverbal component
    # override in this overlap fixture to exercise either order, not spell blocking.
    spells["deafness"].verbal = False
    for key in (first_cast, "silence" if first_cast == "deafness" else "deafness"):
        cast(spells[key])
    original = target.active_conditions["Deafened"].uuid
    assert_deaf(target, True)
    cursor = EventQueue.event_cursor()
    def remove(key):
        assert (target if key == "deafness" else source).remove_condition(
            "Blindness/Deafness" if key == "deafness" else "Concentrating")
    remove(first_remove)
    assert_deaf(target, True)
    assert target.active_conditions["Deafened"].uuid == original
    assert not any(isinstance(event, ConditionRemovalEvent) and event.condition.uuid == original
                   and event.phase is EventPhase.COMPLETION
                   for _, event in EventQueue.iter_events_since(cursor))
    remove("silence" if first_remove == "deafness" else "deafness")
    assert_deaf(target, False)


@pytest.mark.parametrize("first_remove", ("Color Spray", "Blindness/Deafness"))
def test_color_spray_and_blindness_preserve_visual_denial(first_remove) -> None:
    source, other, target = actors()
    spray = ColorSpray(source_entity_uuid=other.uuid, end_position=(10, 8), cast_at_level=1)
    with fixed_dice_faces(*([10] * 6)):
        result = spray.apply()
    assert result is not None and not result.canceled and "Color Spray" in target.active_conditions
    cast(BlindnessDeafness(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                          effect_type="blinded", cast_at_level=2))
    original = target.active_conditions["Blinded"].uuid
    assert not target.can_see_visual_effects()
    assert target.remove_condition(first_remove)
    assert not target.can_see_visual_effects()
    assert target.active_conditions["Blinded"].uuid == original
    last = "Blindness/Deafness" if first_remove == "Color Spray" else "Color Spray"
    assert target.remove_condition(last)
    assert "Blinded" not in target.active_conditions and target.can_see_visual_effects()


def test_shared_last_child_removal_veto_preserves_owner_and_modifiers() -> None:
    source, other, target = actors()
    cast(BlindnessDeafness(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                          effect_type="deafened", cast_at_level=2))
    cast(Silence(source_entity_uuid=other.uuid, end_position=target.position, cast_at_level=2))
    child = target.active_conditions["Deafened"]
    assert target.remove_condition("Blindness/Deafness")
    assert target.active_conditions["Deafened"] is child
    parent = other.active_conditions["Concentrating"]

    def veto(event: Event, _: UUID) -> Event | None:
        if isinstance(event, ConditionRemovalEvent) and isinstance(event.condition, Deafened):
            return event.cancel("Keep hearing denial")
        return None

    handler = EventHandler(name="Retain Deafened", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION, event_target_entity_uuid=target.uuid)], event_processor=veto)
    target.add_event_handler(handler)
    assert other.remove_condition("Concentrating") is False
    assert other.active_conditions["Concentrating"] is parent
    assert target.active_conditions["Deafened"] is child
    assert_deaf(target, True)
    target.remove_event_handler(handler)
    assert other.remove_condition("Concentrating")
    assert_deaf(target, False)


def test_rejected_same_name_parent_replacement_does_not_remove_borrowed_child() -> None:
    source, other, target = actors()
    cast(BlindnessDeafness(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                          effect_type="blinded", cast_at_level=2))
    original_parent = target.active_conditions["Blindness/Deafness"]
    original_child = target.active_conditions["Blinded"]
    def veto(event: Event, _: UUID) -> Event | None:
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == original_parent.uuid:
            return event.cancel("Keep original blindness source")
        return None
    target.add_event_handler(EventHandler(name="Retain source", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION, event_target_entity_uuid=target.uuid)], event_processor=veto))
    cast(BlindnessDeafness(source_entity_uuid=other.uuid, target_entity_uuid=target.uuid,
                          effect_type="blinded", cast_at_level=2))
    assert target.active_conditions["Blindness/Deafness"] is original_parent
    assert target.active_conditions["Blinded"] is original_child
    assert not target.can_see_visual_effects()
    assert original_child.additional_parent_conditions == set()


def test_charm_retains_existing_same_name_replacement_policy() -> None:
    source, other, target = actors()
    cast(CharmPerson(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, cast_at_level=1))
    first = target.active_conditions["Charmed"]
    cast(CharmPerson(source_entity_uuid=other.uuid, target_entity_uuid=target.uuid, cast_at_level=1))
    assert target.active_conditions["Charmed"].source_entity_uuid == other.uuid
    assert first.uuid not in target.active_conditions_by_uuid


@pytest.mark.parametrize("mode", ("blinded", "deafened"))
@pytest.mark.parametrize("saved", (True, False))
def test_cast_retains_selected_rule_branch_even_when_saved(mode, saved) -> None:
    source, _, target = actors()
    with fixed_dice_faces(20 if saved else 1):
        result = BlindnessDeafness(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                                  effect_type=mode, cast_at_level=2).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.effect_id == f"control.{mode}"
    resolved = [event for _, event in EventQueue.iter_events_since(0)
                if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION
                and event.effect_id == f"control.{mode}" and event.save_success is not None]
    assert resolved and all(event.save_success is saved for event in resolved)
    assert ("Blindness/Deafness" in target.active_conditions) is not saved


def test_silence_borrowing_independent_deafened_preserves_its_lifetime() -> None:
    source, _, target = actors()
    independent = Deafened(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)
    target.add_condition(independent)
    cast(Silence(source_entity_uuid=source.uuid, end_position=target.position, cast_at_level=2))
    assert source.remove_condition("Concentrating")
    assert target.active_conditions["Deafened"] is independent
    assert_deaf(target, True)
    assert target.remove_condition("Deafened")
    assert_deaf(target, False)


def test_registered_color_spray_uses_selected_direction_not_template_origin() -> None:
    _, source, target = actors()
    template = ColorSpray(source_entity_uuid=source.uuid, template=True)
    source.register_action(template)
    with fixed_dice_faces(*([10] * 6)):
        result = template.instantiate(end_position=target.position).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.behavior_id == "spell.color_spray"
    assert "Color Spray" in target.active_conditions
    assert not target.can_see_visual_effects()


@pytest.mark.parametrize("reverse", (False, True))
def test_one_removal_graph_ending_both_sources_removes_shared_effect_once(reverse) -> None:
    """A joint owner teardown resolves both links before removing the shared child."""
    source, _, target = actors()
    root = EngineBookMarkerCondition(name="Joint owner", source_entity_uuid=source.uuid,
                                     target_entity_uuid=target.uuid)
    first = EngineBookMarkerCondition(name="First source", source_entity_uuid=source.uuid,
                                      target_entity_uuid=target.uuid, parent_condition=root.uuid)
    second = EngineBookMarkerCondition(name="Second source", source_entity_uuid=source.uuid,
                                       target_entity_uuid=target.uuid, parent_condition=root.uuid)
    for condition in (root, first, second):
        target.add_condition(condition)
    child = Blinded(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                    parent_condition=first.uuid)
    target.add_condition(child)
    root.sub_conditions.extend((second.uuid, first.uuid) if reverse else (first.uuid, second.uuid))
    first.add_shared_subcondition(child)
    second.add_shared_subcondition(child)
    cursor = EventQueue.event_cursor()
    assert target.remove_condition("Joint owner")
    assert target.can_see_visual_effects()
    assert all(condition.uuid not in target.active_conditions_by_uuid
               for condition in (root, first, second, child))
    removals = [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == child.uuid
                and event.phase is EventPhase.COMPLETION]
    assert len(removals) == 1
