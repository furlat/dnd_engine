"""The one map from a recorded event to its change of an actor's HUD sheet.

A sheet's computed groups travel in the publisher's `ActorSheetEvent`; its other fields in their own
events: the birth (species, background, origin and the evented fields' first values) and the four
evented families, each carrying its after-value. HP, name and portrait are the body's (the client
reads them from the actor), so no event here carries them.
"""

from dataclasses import dataclass
from uuid import UUID

from dnd.core.events import (ActorSheetEvent, EntityCreatedEvent, Event, PermanentFeatureUsedEvent,
    SpellbookChangedEvent, SpellMasteryStudiedEvent, SpellPreparationChangedEvent)
from dnd.player.facts import SheetChanges
from dnd.types.actor_sheet import ActorSheetChange, PlayerResourceValue


@dataclass(frozen=True, slots=True)
class SheetFact:
    """One event's change of an actor's sheet; `publication`: it is the publisher's sheet event."""

    actor_uuid: UUID
    changes: SheetChanges
    resource_values: tuple[PlayerResourceValue, ...] = ()
    publication: bool = False


def _group_changes(change: ActorSheetChange) -> SheetChanges:
    changes: SheetChanges = {}
    if change.abilities is not None:
        changes["abilities"] = change.abilities
    if change.skills is not None:
        changes["skills"] = change.skills
    if change.expertise is not None:
        changes["expertise"] = change.expertise
    if change.saves is not None:
        changes["saves"] = change.saves
    if change.proficiency_bonus is not None:
        changes["proficiency_bonus"] = change.proficiency_bonus
    if change.resources is not None:
        changes["resources"] = change.resources
    if change.compatible_item_slots is not None:
        changes["compatible_item_slots"] = change.compatible_item_slots
    if change.handler_details is not None:
        changes["handler_details"] = change.handler_details
    return changes


def sheet_fact(event: Event) -> SheetFact | None:
    """The actor whose sheet this committed event changes, and the change; None for any other event."""
    match event:
        case ActorSheetEvent():
            return SheetFact(event.source_entity_uuid, _group_changes(event.change), event.change.resource_values,
                publication=True)
        case EntityCreatedEvent():
            return SheetFact(event.entity_uuid, SheetChanges(species=event.species, species_variant=event.species_variant,
                background=event.background, origin=event.applied_origin_state,
                class_levels=event.applied_class_levels, scribed_spell_ids=event.scribed_spell_ids,
                permanent_feature_uses=event.permanent_feature_uses,
                prepared_spell_selections=event.prepared_spell_selections))
        case SpellbookChangedEvent():
            return SheetFact(event.source_entity_uuid, SheetChanges(scribed_spell_ids=event.scribed_spell_ids))
        case SpellPreparationChangedEvent():
            return SheetFact(event.source_entity_uuid,
                SheetChanges(prepared_spell_selections=event.prepared_spell_selections))
        case PermanentFeatureUsedEvent():
            return SheetFact(event.source_entity_uuid, SheetChanges(permanent_feature_uses=event.permanent_feature_uses))
        case SpellMasteryStudiedEvent():
            return SheetFact(event.source_entity_uuid, SheetChanges(class_levels=event.applied_class_levels))
    return None
