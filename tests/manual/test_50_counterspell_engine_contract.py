"""Focused engine contracts for Counterspell and committed spell costs."""

from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from tests.spell_test_exports import MagicMissile
from dnd.spells.abjuration import register_counterspell_reaction
from tests.engine.support import reset_combat_state


def reset_counterspell_state(*, width: int = 40, height: int = 8) -> None:
    """Reset global registries and create a deterministic Counterspell grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    ModifiableValue._registry.clear()
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


