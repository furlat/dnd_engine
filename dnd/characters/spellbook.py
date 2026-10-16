"""Character-owned Wizard knowledge, below scrolls and concrete class composers."""

from dnd.core.events import Event, EventPhase, EventQueue, SpellbookChangedEvent
from dnd.entity import Entity
from dnd.types.class_spells import WIZARD_SPELL_RANKS
from dnd.types.character_progression import CharacterClass


def wizard_book(entity: Entity) -> tuple[str, ...]:
    learned = (
        spell
        for row in entity.applied_class_levels
        if row.class_id is CharacterClass.WIZARD
        for choice in row.choices
        if choice.choice_id.endswith((".cantrips", ".spellbook"))
        for spell in choice.values
    )
    return tuple(dict.fromkeys((*learned, *entity.scribed_spell_ids)))


def scroll_learning_error(entity: Entity, spell_id: str) -> str | None:
    if not any(
        source.provider_id == CharacterClass.WIZARD.value
        for source in entity.spellcasting.sources.values()
    ):
        return "Learning a scroll requires Wizard spellcasting"
    if spell_id not in WIZARD_SPELL_RANKS:
        return "This scroll is not on the implemented Wizard spell list"
    if spell_id in wizard_book(entity):
        return "This spell is already in the Wizard book"
    rank = WIZARD_SPELL_RANKS[spell_id]
    if rank and not any(
        entity.has_spell_slot_capacity(level) for level in range(rank, 10)
    ):
        return "The spell exceeds shared spell-slot capacity"
    return None


def learn_scroll_spell(
    entity: Entity, spell_id: str, parent_event: Event
) -> SpellbookChangedEvent:
    error = scroll_learning_error(entity, spell_id)
    if error is not None:
        raise ValueError(error)
    entity.scribed_spell_ids = (*entity.scribed_spell_ids, spell_id)
    fact = EventQueue.publish_committed_phase(
        SpellbookChangedEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            parent_event=parent_event.uuid,
            phase=EventPhase.EFFECT,
            use_register=False,
            learned_spell_id=spell_id,
            scribed_spell_ids=entity.scribed_spell_ids,
        )
    )
    return fact.phase_to(EventPhase.COMPLETION)
