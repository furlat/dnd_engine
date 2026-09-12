"""Native True Seeing delivery preserves costs, effects, and causal history."""

from uuid import UUID

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_by_index, execute_use_action, get_available_actions, register_spell
from dnd.conditions import Invisible
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import BaseBlock
from dnd.core.events import Event, EventPhase, EventQueue, SensoryUpdateEvent
from dnd.core.content.provenance import ContentProvenanceRelation
from dnd.core.content.registration import get_content_declaration
from dnd.items.consumables import _DrinkTrueSeeingPotionAction
from dnd.spells.divination import TrueSeeing, TrueSeeingEffect
from dnd.types.senses import SensesType
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


def _assert_belongs_to(root: Event, child: Event) -> None:
    """A received visual transition must belong to its actual causal root."""
    ancestry = {event.lineage_uuid: event for _, event in EventQueue.iter_events_since(0)
                if event.phase is EventPhase.COMPLETION}
    parent = child
    while parent.lineage_uuid != root.lineage_uuid:
        assert parent.parent_lineage is not None
        parent = ancestry[parent.parent_lineage]


def _contact_transition(observer_uuid: UUID, subject_uuid: UUID, *, added: bool, since: int) -> SensoryUpdateEvent:
    transitions = [event for _, event in EventQueue.iter_events_since(since)
                   if isinstance(event, SensoryUpdateEvent) and event.phase is EventPhase.COMPLETION
                   and event.observer_uuid == observer_uuid
                   and subject_uuid in (event.entity_contacts_changed if added else event.entity_contacts_removed)]
    assert len(transitions) == 1
    return transitions[0]


def test_true_seeing_spell_and_removal_keep_their_sensory_children() -> None:
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor("Seer", (2, 3), "heroes", spell_slots={6: 1})
    subject = create_spell_regression_actor("Invisible subject", (5, 3), "enemies")
    subject.add_condition(Invisible(source_entity_uuid=subject.uuid, target_entity_uuid=subject.uuid))
    assert subject.uuid not in caster.senses.entities
    register_spell(caster, TrueSeeing, caster_level=11)
    available = get_available_actions(caster)
    offered = next(row for row in available.all_actions if row.behavior_id == "spell.true_seeing")
    selected = next(target for target in offered.valid_targets if target.target_uuid == caster.uuid)
    cursor = EventQueue.event_cursor()
    cast = execute_by_index(caster, offered.template_name, selected.index, available=available)
    assert isinstance(cast, SpellEvent) and not cast.canceled
    acquired = _contact_transition(caster.uuid, subject.uuid, added=True, since=cursor)
    assert acquired.sense_modes_changed and acquired.sense_modes is not None
    assert any(mode.sense_type is SensesType.TRUESIGHT and mode.range_feet == 120 for mode in acquired.sense_modes)
    _assert_belongs_to(cast, acquired)
    roots = [event for _, event in EventQueue.iter_events_since(cursor)
             if event.phase is EventPhase.COMPLETION and event.parent_lineage is None]
    assert [event.uuid for event in roots] == [cast.uuid]

    condition = caster.active_conditions["True Seeing"]
    cursor = EventQueue.event_cursor()
    caster.remove_condition_by_uuid(condition.uuid)
    lost = _contact_transition(caster.uuid, subject.uuid, added=False, since=cursor)
    removal, = (event for _, event in EventQueue.iter_events_since(cursor)
                if event.phase is EventPhase.COMPLETION and event.parent_lineage is None)
    _assert_belongs_to(removal, lost)
    assert subject.uuid not in caster.senses.entities


def test_true_seeing_potion_is_discovered_consumed_and_expires_after_ten_rounds() -> None:
    reset_spell_regression_arena(12, 7)
    drinker = create_spell_regression_actor("Drinker", (2, 3), "heroes")
    subject = create_spell_regression_actor("Invisible subject", (5, 3), "heroes")
    subject.add_condition(Invisible(source_entity_uuid=subject.uuid, target_entity_uuid=subject.uuid))
    potion = build_authored_item("consumable.potion_true_seeing", drinker.uuid)
    assert drinker.inventory.add_item(potion)
    offered = [row for row in get_available_actions(drinker).all_actions
               if row.behavior_id == "action.item.potion_true_seeing.drink"]
    assert len(offered) == 1
    cursor = EventQueue.event_cursor()
    bonus_before = drinker.action_economy.bonus_actions.normalized_score
    completion = execute_use_action(drinker, potion.uuid, "Drink True Seeing Potion")
    assert completion is not None and not completion.canceled
    assert drinker.action_economy.bonus_actions.normalized_score == bonus_before - 1
    assert not drinker.inventory.has_item(potion.uuid) and BaseBlock.get(potion.uuid) is None
    effect = drinker.active_conditions["True Seeing"]
    assert isinstance(effect, TrueSeeingEffect) and effect.duration.duration == 10
    assert effect.behavior_binding is not None
    assert effect.behavior_binding.provided_by_id == "action.item.potion_true_seeing.drink"
    assert "Concentrating" not in drinker.active_conditions
    _assert_belongs_to(completion, _contact_transition(drinker.uuid, subject.uuid, added=True, since=cursor))
    for _ in range(9):
        drinker.advance_duration("True Seeing")
    assert subject.uuid in drinker.senses.entities
    drinker.advance_duration("True Seeing")
    assert "True Seeing" not in drinker.active_conditions and subject.uuid not in drinker.senses.entities
    assert all(mode.sense_type is not SensesType.TRUESIGHT for mode in drinker.senses.get_sense_modes())


def test_true_seeing_potion_declaration_records_its_new_derived_origin() -> None:
    declaration = get_content_declaration(_DrinkTrueSeeingPotionAction)
    assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
    assert declaration.provenance.relation is ContentProvenanceRelation.DERIVED_CONTENT
    assert "2026-09-12" in declaration.provenance.source_anchor
    assert "not a baseline item" in declaration.provenance.notes
