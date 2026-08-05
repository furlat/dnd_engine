"""Focused engine contracts for Counterspell and committed spell costs."""

import json
from unittest.mock import patch
from uuid import uuid4

import pytest

from server.agent_runtime.observation_journal import (
    build_observation_snapshot,
    iter_observation_frames,
)
from dnd.actions import SpellAction, SpellEvent
from dnd.actions_functional import register_spell
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    SpellInterruptionLogData,
)
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.conditions import Invisible
from dnd.classes.sorcerer import QuickenedSpell
from dnd.blocks.action_economy import RechargeType
from dnd.controller import PassController
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from tests.spell_test_exports import Fireball, FireBolt, MagicMissile
from dnd.spells.abjuration import (
    CounterspellReactionEvent,
    register_counterspell_reaction,
)
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
)
from tests.engine.support import reset_combat_state
from server.event_server import sim
from server.session import PlayerType
from tests.manual.test_28_subjective_observation_stream import reset_observation_state


def reset_counterspell_state(*, width: int = 40, height: int = 8) -> None:
    """Reset global registries and create a deterministic Counterspell grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_counterspell_caster(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int],
) -> Entity:
    """Create a visible spellcaster with explicit action-economy resources."""
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=18),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=12),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=6, mode="maximums")],
            ),
            proficiency_bonus=3,
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def test_counterspell_spends_both_casters_resources_and_records_one_cancel() -> None:
    """An execution-phase interruption spends both casts and has one cancel version."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1})
    counterspeller = create_counterspell_caster("Abjurer", (6, 2), "monsters", {3: 1})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    combat_logs: list[CombatLogEntry] = []

    def capture_combat_log(log_event: Event) -> None:
        if log_event.combat_log is not None:
            combat_logs.append(log_event.combat_log)

    EventQueue.set_combat_log_callback(capture_combat_log)

    try:
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=counterspeller.uuid,
            template=False,
        ).apply()
    finally:
        EventQueue.set_combat_log_callback(None)

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.phase is EventPhase.CANCEL
    assert event.canceled_from_phase is EventPhase.EXECUTION
    assert event.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert event.status_message == "The spell was interrupted."
    assert counterspeller.name not in event.status_message
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0

    cancel_versions = [
        row
        for row in EventQueue._all_events
        if row.lineage_uuid == event.lineage_uuid and row.phase is EventPhase.CANCEL
    ]
    assert [row.uuid for row in cancel_versions] == [event.uuid]
    assert len(EventQueue._all_events) == len({row.uuid for row in EventQueue._all_events})
    interruption_logs = [
        log for log in combat_logs if log.entry_type is CombatLogEntryType.SPELL_INTERRUPTION
    ]
    assert len(interruption_logs) == 1
    assert interruption_logs[0].source_uuid == str(counterspeller.uuid)
    assert interruption_logs[0].target_uuid == str(caster.uuid)
    assert interruption_logs[0].data["outcome_code"] == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert interruption_logs[0].data["counterspell_slot_level"] == 3
    assert interruption_logs[0].data["succeeded"] is True
    assert interruption_logs[0].data["reaction_content_identity"] is not None


def test_counterspell_declaration_veto_preserves_reaction_and_slot() -> None:
    """A canceled reaction declaration cannot spend resources or interrupt."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1})
    counterspeller = create_counterspell_caster(
        "Abjurer",
        (6, 2),
        "monsters",
        {3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    def veto_counterspell(
        event: Event,
        _handler_source_uuid,
    ) -> Event | None:
        if isinstance(event, CounterspellReactionEvent):
            return event.cancel(status_message="Counterspell vetoed")
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name="Veto Counterspell",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TRIGGER_EVENT,
                    event_phase=EventPhase.DECLARATION,
                    event_source_entity_uuid=counterspeller.uuid,
                )
            ],
            event_processor=veto_counterspell,
        )
    )

    event = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.phase is EventPhase.COMPLETION
    assert not event.canceled
    assert counterspeller.action_economy.reactions.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 1
    reaction_lineages = {
        row.lineage_uuid
        for row in EventQueue._all_events
        if isinstance(row, CounterspellReactionEvent)
    }
    assert len(reaction_lineages) == 1
    assert all(
        row.phase in {EventPhase.DECLARATION, EventPhase.CANCEL}
        for row in EventQueue._all_events
        if row.lineage_uuid in reaction_lineages
    )


@pytest.mark.parametrize(
    ("phase", "updates"),
    (
        (
            EventPhase.DECLARATION,
            {
                "succeeded": False,
                "outcome_code": COUNTERSPELL_FAILURE_OUTCOME_CODE,
            },
        ),
        (
            EventPhase.EXECUTION,
            {"counterspell_slot_level": 4},
        ),
        (
            EventPhase.EFFECT,
            {
                "reaction_content_identity": (
                    "fixture.counterspell:reaction:reaction.forged@1"
                ),
                "incoming_spell_content_identity": (
                    "fixture.counterspell:spell:spell.forged@1"
                ),
            },
        ),
        (
            EventPhase.EFFECT,
            {"__replace_event_type__": True},
        ),
        (
            EventPhase.EXECUTION,
            {"__post_cancel__": True},
        ),
        (
            EventPhase.EFFECT,
            {"__post_completion__": True},
        ),
        (
            EventPhase.EFFECT,
            {"__phase_to_completion__": True},
        ),
        (
            EventPhase.DECLARATION,
            {"phase": EventPhase.COMPLETION},
        ),
        (
            EventPhase.DECLARATION,
            {"phase": EventPhase.COMPLETION, "canceled": True},
        ),
        (
            EventPhase.EFFECT,
            {"__mutate_in_place__": True},
        ),
    ),
)
def test_counterspell_evidence_mutation_fails_closed_before_resource_commit(
    phase: EventPhase,
    updates: dict[str, object],
) -> None:
    """Handlers cannot rewrite resolved reaction facts before commit."""
    reset_counterspell_state()
    caster = create_counterspell_caster(
        "Caster",
        (2, 2),
        "heroes",
        {1: 1},
    )
    counterspeller = create_counterspell_caster(
        "Abjurer",
        (6, 2),
        "monsters",
        {3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    combat_logs: list[CombatLogEntry] = []
    observed_reactions: list[
        tuple[
            type[CounterspellReactionEvent],
            EventPhase,
            bool,
            EventPhase | None,
            int,
            str | None,
        ]
    ] = []

    def capture_reaction(event: Event) -> None:
        if isinstance(event, CounterspellReactionEvent):
            observed_reactions.append(
                (
                    type(event),
                    event.phase,
                    event.canceled,
                    event.canceled_from_phase,
                    event.counterspell_slot_level,
                    event.reaction_content_identity,
                ),
            )

    EventQueue.add_on_event_callback(capture_reaction)
    EventQueue.set_combat_log_callback(
        lambda event: combat_logs.append(event.combat_log)
        if event.combat_log is not None
        else None
    )

    def rewrite_evidence(
        event: Event,
        _handler_source_uuid,
    ) -> Event | None:
        if isinstance(event, CounterspellReactionEvent):
            if updates.get("__mutate_in_place__"):
                event.counterspell_slot_level = 4
                event.modified = True
                return event
            if updates.get("__post_cancel__"):
                return event.cancel(
                    status_message="forged Counterspell cancel",
                    counterspell_slot_level=4,
                    reaction_content_identity=(
                        "fixture.counterspell:reaction:reaction.forged@1"
                    ),
                )
            if updates.get("__post_completion__"):
                return event.post(phase=EventPhase.COMPLETION)
            if updates.get("__phase_to_completion__"):
                return event.phase_to(
                    EventPhase.COMPLETION,
                    lineage_uuid=uuid4(),
                    reaction_content_identity=(
                        "fixture.counterspell:reaction:reaction.forged@1"
                    ),
                )
            if updates.get("__replace_event_type__"):
                class CounterspellSubtype(CounterspellReactionEvent):
                    pass

                payload = event.model_dump()
                payload["behavior_binding"] = event.behavior_binding
                payload["use_register"] = False
                replacement = CounterspellSubtype(**payload)
                return replacement.model_copy(
                    update={"modified": True, "use_register": True},
                )
            return event.model_copy(
                update={**updates, "modified": True},
            )
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name=f"Rewrite Counterspell {phase.value}",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TRIGGER_EVENT,
                    event_phase=phase,
                    event_source_entity_uuid=counterspeller.uuid,
                )
            ],
            event_processor=rewrite_evidence,
        )
    )

    try:
        event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=counterspeller.uuid,
            template=False,
        ).apply()
    finally:
        EventQueue.set_combat_log_callback(None)
        EventQueue.remove_on_event_callback(capture_reaction)

    assert isinstance(event, SpellEvent)
    assert event.phase is EventPhase.COMPLETION
    assert not event.canceled
    assert counterspeller.action_economy.reactions.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 1
    reaction_versions = [
        row
        for row in EventQueue._all_events
        if isinstance(row, CounterspellReactionEvent)
    ]
    declaration = next(
        row
        for row in reaction_versions
        if row.phase is EventPhase.DECLARATION and not row.modified
    )
    terminal = reaction_versions[-1]
    assert terminal.phase is EventPhase.CANCEL
    assert terminal.canceled
    assert terminal.canceled_from_phase is phase
    assert all(
        type(row) is CounterspellReactionEvent
        for row in reaction_versions
    )
    assert not any(
        row.phase is EventPhase.COMPLETION
        for row in reaction_versions
    )
    for row in reaction_versions:
        for field_name in (
            "triggered_event_uuid",
            "triggered_lineage_uuid",
            "incoming_spell_name",
            "incoming_spell_level",
            "counterspell_slot_level",
            "automatic",
            "check_total",
            "check_dc",
            "succeeded",
            "outcome_code",
            "reaction_content_identity",
            "incoming_spell_content_identity",
            "behavior_binding",
        ):
            assert getattr(row, field_name) == getattr(
                declaration,
                field_name,
            )
    assert observed_reactions
    assert all(
        row_type is CounterspellReactionEvent
        and slot_level == declaration.counterspell_slot_level
        and reaction_identity == declaration.reaction_content_identity
        and (
            (
                not canceled
                and observed_phase
                in {
                    EventPhase.DECLARATION,
                    EventPhase.EXECUTION,
                    EventPhase.EFFECT,
                }
                and canceled_from_phase is None
            )
            or (
                canceled
                and observed_phase is EventPhase.CANCEL
                and canceled_from_phase is phase
            )
        )
        for (
            row_type,
            observed_phase,
            canceled,
            canceled_from_phase,
            slot_level,
            reaction_identity,
        ) in observed_reactions
    )
    assert not any(
        log.entry_type is CombatLogEntryType.SPELL_INTERRUPTION
        for log in combat_logs
    )


def test_registered_counterspell_freezes_both_reaction_and_spell_bindings() -> None:
    """Live handler/action scopes survive every event phase but no raw dump."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1})
    counterspeller = create_counterspell_caster(
        "Abjurer",
        (6, 2),
        "monsters",
        {3: 1},
    )
    register_spell(caster, MagicMissile, caster_level=3)
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    template = caster.get_action_template("Magic Missile")
    assert isinstance(template, SpellAction)
    handler = counterspeller.get_event_handler_by_name("Counterspell")
    assert handler is not None
    assert template.behavior_binding is not None
    assert handler.behavior_binding is not None

    event = template.instantiate(
        target_entity_uuid=counterspeller.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    incoming_versions = [
        row
        for row in EventQueue._all_events
        if isinstance(row, SpellEvent)
        and row.lineage_uuid == event.lineage_uuid
    ]
    assert incoming_versions
    assert all(
        row.behavior_binding == template.behavior_binding
        for row in incoming_versions
    )
    reaction = next(
        row
        for row in EventQueue._all_events
        if isinstance(row, CounterspellReactionEvent)
        and row.phase is EventPhase.COMPLETION
    )
    trigger = EventQueue.get_event_by_uuid(reaction.triggered_event_uuid)
    assert isinstance(trigger, SpellEvent)
    assert reaction.behavior_binding == handler.behavior_binding
    assert trigger.behavior_binding == template.behavior_binding
    assert reaction.reaction_content_identity == (
        handler.behavior_binding.definition_ref.identity_key
    )
    assert reaction.incoming_spell_content_identity == (
        template.behavior_binding.definition_ref.identity_key
    )
    assert reaction.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert reaction.combat_log is not None
    typed_log = SpellInterruptionLogData.model_validate(
        reaction.combat_log.data,
    )
    assert typed_log.reaction_content_identity == (
        reaction.reaction_content_identity
    )
    assert typed_log.incoming_spell_content_identity == (
        reaction.incoming_spell_content_identity
    )
    assert "behavior_binding" not in reaction.model_dump()
    assert "behavior_binding" not in trigger.model_dump()


def test_counterspell_does_not_interrupt_an_allied_spell() -> None:
    """An allied spell completes without spending the observer's reaction or slot."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1})
    counterspeller = create_counterspell_caster("Allied Abjurer", (6, 2), "heroes", {3: 1})
    target = create_counterspell_caster("Target", (8, 2), "monsters", {})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.phase is EventPhase.COMPLETION
    assert counterspeller.action_economy.reactions.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 1


def test_counterspell_consumes_quickened_override_after_committed_cast() -> None:
    """An interrupted Quickened cast restores ordinary costs for later spells."""
    reset_counterspell_state()
    caster = create_counterspell_caster(
        "Quickened Caster",
        (2, 2),
        "heroes",
        {3: 2},
    )
    counterspeller = create_counterspell_caster(
        "Abjurer",
        (6, 2),
        "monsters",
        {3: 1},
    )
    register_spell(caster, Fireball, caster_level=5)
    caster.action_economy.add_resource_contribution(
        "sorcery_points",
        "fixture.quickened_spell",
        maximum=2,
        recharge_type=RechargeType.LONG_REST,
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    fireball_template = caster.get_action_template("Fireball")
    assert isinstance(fireball_template, SpellAction)

    quickened = QuickenedSpell(source_entity_uuid=caster.uuid).apply()
    assert quickened is not None and not quickened.canceled
    assert "MetamagicActive" in caster.active_conditions
    quickened_template = caster.get_action_template("Fireball")
    assert isinstance(quickened_template, SpellAction)
    assert quickened_template.effective_costs[0].cost_type == "bonus_actions"

    invalid = quickened_template.instantiate(end_position=(39, 7)).apply()

    assert isinstance(invalid, SpellEvent)
    assert invalid.canceled
    assert invalid.canceled_from_phase is EventPhase.DECLARATION
    assert "MetamagicActive" in caster.active_conditions
    quickened_template = caster.get_action_template("Fireball")
    assert isinstance(quickened_template, SpellAction)
    assert quickened_template.effective_costs[0].cost_type == "bonus_actions"

    interrupted = quickened_template.instantiate(
        end_position=counterspeller.position,
    ).apply()

    assert isinstance(interrupted, SpellEvent)
    assert interrupted.canceled
    assert interrupted.canceled_from_phase is EventPhase.EXECUTION
    assert interrupted.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert "MetamagicActive" not in caster.active_conditions
    restored_template = caster.get_action_template("Fireball")
    assert isinstance(restored_template, SpellAction)
    assert restored_template.alt_cost_type is None
    assert restored_template.effective_costs[0].cost_type == "actions"
    assert restored_template.instantiate(
        end_position=counterspeller.position,
    ).pre_validate()


def test_counterspell_never_spends_a_slot_below_third_level() -> None:
    """A low-level incoming spell still requires a third-level Counterspell slot."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1})
    counterspeller = create_counterspell_caster(
        "Abjurer",
        (6, 2),
        "monsters",
        {1: 1, 2: 1, 3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert counterspeller.action_economy.spell_slot_1.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_2.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0


def test_counterspell_can_interrupt_a_cantrip_with_a_third_level_slot() -> None:
    """Cantrips are level-zero spells and remain valid Counterspell targets."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {})
    counterspeller = create_counterspell_caster("Abjurer", (6, 2), "monsters", {3: 1})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    event = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0


def test_declaration_validation_cancel_spends_no_resources() -> None:
    """A spell rejected before execution is not committed by either caster."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (1, 1), "heroes", {1: 1})
    counterspeller = create_counterspell_caster("Distant Abjurer", (30, 1), "monsters", {3: 1})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.canceled_from_phase is EventPhase.DECLARATION
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_1.normalized_score == 1
    assert counterspeller.action_economy.reactions.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 1


def test_failed_counterspell_check_spends_reaction_and_original_cast_completes() -> None:
    """A failed low-slot check pays its costs without canceling the upcast spell."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {5: 1})
    counterspeller = create_counterspell_caster("Abjurer", (6, 2), "monsters", {3: 1})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    with patch("dnd.spells.abjuration.random.randint", return_value=1):
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=counterspeller.uuid,
            cast_at_level=5,
            template=False,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.phase is EventPhase.COMPLETION
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_5.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0


def test_successful_counterspell_check_spends_the_selected_upcast_slot() -> None:
    """An interrupted upcast consumes its actual slot rather than its base slot."""
    reset_counterspell_state()
    caster = create_counterspell_caster("Caster", (2, 2), "heroes", {1: 1, 5: 1})
    counterspeller = create_counterspell_caster("Abjurer", (6, 2), "monsters", {3: 1})
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    with patch("dnd.spells.abjuration.random.randint", return_value=20):
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=counterspeller.uuid,
            cast_at_level=5,
            template=False,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0


def test_handler_model_copy_becomes_a_stored_event_version() -> None:
    """Distinct handler mutations receive identity and remain stream-visible."""
    reset_counterspell_state()
    source_uuid = uuid4()
    downstream_messages: list[str | None] = []
    callback_messages: list[str | None] = []

    def mutate(event: Event, _handler_source_uuid) -> Event:
        return event.model_copy(update={
            "modified": True,
            "status_message": "handler changed it",
        })

    def observe(event: Event, _handler_source_uuid) -> None:
        downstream_messages.append(event.status_message)
        return None

    mutator = EventHandler(
        name="Mutator",
        source_entity_uuid=source_uuid,
        trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.DECLARATION)],
        event_processor=mutate,
    )
    observer = EventHandler(
        name="Observer",
        source_entity_uuid=source_uuid,
        trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.DECLARATION)],
        event_processor=observe,
    )
    EventQueue.add_event_handler(mutator)
    EventQueue.add_event_handler(observer)

    def capture(event: Event) -> None:
        callback_messages.append(event.status_message)

    EventQueue.add_on_event_callback(capture)
    try:
        declaration = Event(
            source_entity_uuid=source_uuid,
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.DECLARATION,
            status_message="declared",
            use_register=False,
        )
        result = EventQueue.register(declaration)
    finally:
        EventQueue.remove_on_event_callback(capture)
        EventQueue.remove_event_handler(mutator)
        EventQueue.remove_event_handler(observer)

    assert result.uuid != declaration.uuid
    assert result.lineage_uuid == declaration.lineage_uuid
    assert result.status_message == "handler changed it"
    assert EventQueue.get_event_by_uuid(result.uuid) is result
    assert downstream_messages == ["handler changed it"]
    assert callback_messages == ["declared", "handler changed it"]
    assert len(EventQueue._all_events) == len({row.uuid for row in EventQueue._all_events})


def test_subjective_counterspell_log_redacts_an_unseen_reactor() -> None:
    """Interruption logs preserve visibility without leaking a hidden reactor."""
    reset_observation_state(width=40, height=10)
    caster = create_counterspell_caster("Visible Caster", (3, 3), "heroes", {1: 1})
    spell_target = create_counterspell_caster("Visible Target", (7, 3), "monsters", {})
    counterspeller = create_counterspell_caster("Hidden Abjurer", (6, 4), "monsters", {3: 1})
    witness = create_counterspell_caster("Visible Witness", (4, 4), "witnesses", {})
    unrelated = create_counterspell_caster("Distant Observer", (35, 8), "outsiders", {})
    counterspeller.add_condition(
        Invisible(
            source_entity_uuid=counterspeller.uuid,
            target_entity_uuid=counterspeller.uuid,
        ),
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses(max_distance=10)

    assert counterspeller.uuid not in caster.senses.entities
    assert caster.uuid in counterspeller.senses.entities
    assert counterspeller.uuid not in witness.senses.entities
    assert caster.uuid in witness.senses.entities

    encounter = Encounter(name="Subjective Counterspell", source_entity_uuid=uuid4())
    for entity in (caster, spell_target, counterspeller, witness, unrelated):
        encounter.add_combatant(entity, PassController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [
        caster.uuid,
        spell_target.uuid,
        counterspeller.uuid,
        witness.uuid,
        unrelated.uuid,
    ]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    sim.encounter = encounter
    game = sim.create_game_session(encounter)
    manager = sim.get_session_manager()

    session_ids: dict[str, str] = {}
    for label, entity in (
        ("caster", caster),
        ("counterspeller", counterspeller),
        ("witness", witness),
        ("unrelated", unrelated),
    ):
        session = manager.create_session(PlayerType.AI, f"{label} session")
        game.add_player(session)
        game.assign_entity(entity.uuid, session.session_id)
        session_ids[label] = str(session.session_id)

    snapshots = {
        label: build_observation_snapshot(session_id, session_manager=manager)
        for label, session_id in session_ids.items()
    }
    assert str(counterspeller.uuid) not in {
        fact.uuid for fact in snapshots["caster"].known_entities
    }

    event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=spell_target.uuid,
        template=False,
    ).apply()
    assert isinstance(event, SpellEvent)
    assert event.canceled

    interruption_logs: dict[str, list[dict]] = {}
    for label, session_id in session_ids.items():
        response = iter_observation_frames(
            session_id,
            since=snapshots[label].observation_cursor,
            limit=0,
            session_manager=manager,
        )
        interruption_logs[label] = [
            frame.combat_log
            for frame in response.frames
            if frame.combat_log is not None
            and frame.combat_log.get("entry_type") == CombatLogEntryType.SPELL_INTERRUPTION.value
        ]

    assert len(interruption_logs["caster"]) == 1
    assert len(interruption_logs["counterspeller"]) == 1
    assert len(interruption_logs["witness"]) == 1
    assert interruption_logs["unrelated"] == []

    for label in ("caster", "witness"):
        serialized = json.dumps(interruption_logs[label])
        assert counterspeller.name not in serialized
        assert str(counterspeller.uuid) not in serialized
        assert interruption_logs[label][0]["source_name"] == "Unknown"
        assert interruption_logs[label][0]["source_uuid"] == ""
        assert interruption_logs[label][0]["data"]["outcome_code"] == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE

    own_log = interruption_logs["counterspeller"][0]
    assert own_log["source_name"] == counterspeller.name
    assert own_log["source_uuid"] == str(counterspeller.uuid)
