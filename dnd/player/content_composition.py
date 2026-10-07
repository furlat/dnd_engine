"""Native content descriptors for the client, without SDL/media loading."""

from dnd.content.characters.class_definitions import FIGHTER_DEFINITION, BARBARIAN_DEFINITION, SORCERER_DEFINITION
from dnd.content.items.authored_item_builders import DIRECT_ITEM_BUILDERS
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.player.content import UIContentManifest
from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.player.facts import (
    ActionFact, AttackFact, SpellFact, ConditionChangeFact, EquipmentFact,
    MechanismActivationFact, ObjectDestroyedFact, PlayerActor, PlayerLineage, PlayerState,
    SensoryFact,
)


def _actor_content(actor: PlayerActor) -> set[str]:
    known = {actor.creature_content_ref} if actor.creature_content_ref is not None else set()
    known.update(row.item_id for row in actor.visual_loadout.layers)
    known.update(effect.behavior_id for row in actor.visual_loadout.layers for effect in row.item_effects)
    known.update(row.item_id for row in actor.controlled_items or ())
    known.update(effect.behavior_id for row in actor.controlled_items or () for effect in row.item_effects)
    known.update(row.behavior_id for row in actor.conditions if row.behavior_id is not None)
    return known


def ui_content_manifest() -> UIContentManifest:
    loaded=SERVER_CONTENT_SYSTEM_RUNTIME.require()
    levels=(*FIGHTER_DEFINITION.levels,*FIGHTER_DEFINITION.champion_levels,
        *BARBARIAN_DEFINITION.levels,*BARBARIAN_DEFINITION.berserker_levels,
        *SORCERER_DEFINITION.levels,*SORCERER_DEFINITION.draconic_levels)
    features=frozenset(value for level in levels
        for value in (*level.feature_ids,*(value for choice in level.choices for value in choice.allowed_values))
        if value.startswith(('class_feature.','feat.','metamagic.')))
    return UIContentManifest(content=tuple((d.ref,d.descriptor) for d in loaded.registry.declarations.values()),
        feature_ids=features,item_ids=frozenset(DIRECT_ITEM_BUILDERS))



def admitted_content(catalog: UIContentManifest, state: PlayerState,
                     lineages: tuple[PlayerLineage, ...] = ()) -> tuple[ContentDescriptor, ...]:
    """Public catalog plus independently observed identities; no encounter-wide scan."""
    known = {row.ref.content_id for row in state.content}
    for actor in state.actors.values():
        known.update(_actor_content(actor))
    known.update(row.item.item_id for row in state.objects.values())
    known.update(effect.behavior_id for row in state.objects.values() for effect in row.item.item_effects)
    if state.senses is not None:
        known.update(row.content_ref.content_id for row in state.senses.spatial_effects.values())
    for lineage in lineages:
        for observation in lineage.observations:
            known.update(_actor_content(observation.actor))
        for update in lineage.world_updates:
            known.update(row.item.item_id for row in update.objects)
            known.update(effect.behavior_id for row in update.objects for effect in row.item.item_effects)
        for node in lineage.events:
            fact = node.fact
            if isinstance(fact, (ActionFact, AttackFact, SpellFact)) and fact.behavior_id is not None:
                known.add(fact.behavior_id)
            if isinstance(fact, AttackFact):
                if fact.source_item_id is not None:
                    known.add(fact.source_item_id)
                known.update(effect.behavior_id for effect in fact.item_effects)
            elif isinstance(fact, ConditionChangeFact):
                if fact.condition.behavior_id is not None:
                    known.add(fact.condition.behavior_id)
                if fact.condition.resulting_item is not None:
                    known.add(fact.condition.resulting_item.item_id)
                    known.update(effect.behavior_id for effect in fact.condition.resulting_item.item_effects)
            elif isinstance(fact, EquipmentFact):
                known.update(row.item_id for row in fact.visual_loadout.layers)
                known.update(row.item_id for row in fact.controlled_items or ())
                known.update(effect.behavior_id for row in fact.visual_loadout.layers for effect in row.item_effects)
                known.update(effect.behavior_id for row in fact.controlled_items or () for effect in row.item_effects)
            elif isinstance(fact, SensoryFact):
                known.update(row.content_ref.content_id for row in fact.spatial_effects_changed.values())
            elif isinstance(fact, ObjectDestroyedFact):
                known.add(fact.item_id)
            elif isinstance(fact, MechanismActivationFact):
                known.add(fact.mechanism_content_id)
            for row in node.content_attributions:
                known.update(identity for identity in (row.behavior_id, row.provided_by_id, row.origin_root_id)
                             if identity is not None)
    # Creature facts retain the exact existing ContentRef identity string.
    known.update(ref.content_id for ref, _ in catalog.content if ref.identity_key in known)
    # Admitted descriptors are immutable, already stripped of private links, and
    # retained by the existing player state. Do not copy the whole public catalog
    # again for every action; only an actual new disclosure needs that work.
    retained = {row.ref.identity_key for row in state.content}
    additions = tuple(descriptor for ref, descriptor in catalog.content
        if ref.identity_key not in retained and (
            descriptor.visibility is ContentVisibility.PUBLIC or (
                descriptor.visibility is ContentVisibility.OBSERVED and ref.content_id in known)))
    if not additions:
        return state.content
    public_ids = {ref.content_id for ref, descriptor in catalog.content
                  if descriptor.visibility is ContentVisibility.PUBLIC}
    additions = tuple(descriptor.model_copy(update={"related_content_refs": tuple(
        ref for ref in descriptor.related_content_refs if ref.content_id in public_ids)})
        for descriptor in additions)
    return tuple(sorted((*state.content, *additions), key=lambda row: row.ref.identity_key))
