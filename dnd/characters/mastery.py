"""Bounded native eight-hour Spell Mastery study, with no calendar service."""

from dataclasses import dataclass, replace
from typing import ClassVar
from pydantic import ConfigDict

from dnd.characters.spellbook import wizard_book
from dnd.core.events import EventQueue, EventPhase, SpellMasteryStudiedEvent
from dnd.entity import Entity
from dnd.types.character_progression import CharacterClass, ClassChoiceSelection
from dnd.types.class_spells import WIZARD_SPELL_RANKS


@dataclass(frozen=True, slots=True)
class SpellMasteryStudy:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    rank_one_spell_id: str
    rank_two_spell_id: str
    hours: int = 8


def study_spell_mastery(
    actor: Entity, selection: SpellMasteryStudy
) -> SpellMasteryStudiedEvent:
    if actor.active_encounter_uuid is not None:
        raise ValueError("Spell Mastery study requires being outside combat")
    if selection.hours != 8:
        raise ValueError(
            "Spell Mastery requires one complete eight-hour study operation"
        )
    index = next(
        (
            index
            for index, row in enumerate(actor.applied_class_levels)
            if row.class_id is CharacterClass.WIZARD and row.resulting_class_level == 18
        ),
        None,
    )
    if index is None:
        raise ValueError("Spell Mastery requires Wizard18")
    book = wizard_book(actor)
    for spell_id, rank in (
        (selection.rank_one_spell_id, 1),
        (selection.rank_two_spell_id, 2),
    ):
        if spell_id not in book or WIZARD_SPELL_RANKS.get(spell_id) != rank:
            raise ValueError(
                "Mastery choices must be rank1 and rank2 Wizard-book spells"
            )
    row = actor.applied_class_levels[index]
    receipt = actor.character_grant_receipt(row.step_id)
    grants = [
        actor.spellcasting.free_cast_grants.get(identity)
        for identity in receipt.free_cast_grant_ids
    ]
    if len(grants) != 2 or any(
        grant is None or grant.provider_id != "class_feature.wizard.spell_mastery"
        for grant in grants
    ):
        raise RuntimeError("Spell Mastery exact grants are absent")
    choices = tuple(
        ClassChoiceSelection(choice.choice_id, (selection.rank_one_spell_id,))
        if choice.choice_id.endswith(".mastery_1")
        else ClassChoiceSelection(choice.choice_id, (selection.rank_two_spell_id,))
        if choice.choice_id.endswith(".mastery_2")
        else choice
        for choice in row.choices
    )
    rows = list(actor.applied_class_levels)
    rows[index] = replace(row, choices=choices)
    for grant in grants:
        actor.spellcasting.free_cast_grants[grant.grant_id] = grant.model_copy(
            update={
                "spell_id": selection.rank_one_spell_id
                if grant.cast_rank == 1
                else selection.rank_two_spell_id
            }
        )
    actor.applied_class_levels = tuple(rows)
    return EventQueue.publish_completed_fact(
        SpellMasteryStudiedEvent(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
            hours=8,
            applied_class_levels=actor.applied_class_levels,
        )
    )
