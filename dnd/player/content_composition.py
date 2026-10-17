"""Native content descriptors for the client, without SDL/media loading."""

from dataclasses import dataclass

from dnd.content.characters.class_definitions import FIGHTER_DEFINITION, BARBARIAN_DEFINITION, SORCERER_DEFINITION, CLERIC_DEFINITION, PALADIN_DEFINITION, WIZARD_DEFINITION
from dnd.content.items.authored_item_builders import DIRECT_ITEM_BUILDERS
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.player.content import UIContentManifest
from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.player.facts import (
    ActionFact, ActorChanges, AttackFact, SpellFact, ConditionChangeFact, ConditionFact, EquipmentFact, ItemFields,
    ItemPatch, MechanismActivationFact, ObjectDestroyedFact, PlayerActor, PlayerLineage, PlayerState,
    SensoryFact, VisualLoadout,
)


def _body_content(creature_content_ref: str | None, visual_loadout: VisualLoadout | None,
                  conditions: tuple[ConditionFact, ...]) -> set[str]:
    known = {creature_content_ref} if creature_content_ref is not None else set()
    known.update(row.item_id for row in (visual_loadout.layers if visual_loadout is not None else ()))
    known.update(row.behavior_id for row in conditions if row.behavior_id is not None)
    return known


def _item_content(fields: ItemFields) -> set[str]:
    known = {fields["item_id"]} if "item_id" in fields else set()
    known.update(effect.behavior_id for effect in fields.get("item_effects", ()))
    return known


def _actor_content(actor: PlayerActor) -> set[str]:
    return _body_content(actor.creature_content_ref, actor.visual_loadout, actor.conditions)


def _patch_content(changes: ActorChanges, items: tuple[ItemPatch, ...]) -> set[str]:
    """Identities a body or equipment patch discloses; omitted fields were disclosed when first sent."""
    known = _body_content(changes.get("creature_content_ref"), changes.get("visual_loadout"),
        changes.get("conditions", ()))
    for row in items:
        known.update(_item_content(row.changes))
    return known


def ui_content_manifest() -> UIContentManifest:
    loaded=SERVER_CONTENT_SYSTEM_RUNTIME.require()
    levels=(*FIGHTER_DEFINITION.levels,*FIGHTER_DEFINITION.champion_levels,
        *BARBARIAN_DEFINITION.levels,*BARBARIAN_DEFINITION.berserker_levels,
        *SORCERER_DEFINITION.levels,*SORCERER_DEFINITION.draconic_levels,
        *CLERIC_DEFINITION.levels,*CLERIC_DEFINITION.subclass_levels,*PALADIN_DEFINITION.levels,*PALADIN_DEFINITION.subclass_levels,
        *WIZARD_DEFINITION.levels,*WIZARD_DEFINITION.subclass_levels)
    features=frozenset(value for level in levels
        for value in (*level.feature_ids,*(value for choice in level.choices for value in choice.allowed_values))
        if value.startswith(('class_feature.','feat.','metamagic.')))
    return UIContentManifest(content=tuple((d.ref,d.descriptor) for d in loaded.registry.declarations.values()),
        feature_ids=features,item_ids=frozenset(DIRECT_ITEM_BUILDERS))



def _lineage_content(lineages: tuple[PlayerLineage, ...]) -> set[str]:
    """All content witnessed during these roots, including transient grants."""
    known: set[str] = set()
    for lineage in lineages:
        for observation in lineage.observations:
            known.update(_patch_content(observation.changes, observation.items))
        for update in lineage.world_updates:
            known.update(row.item.item_id for row in update.objects)
            known.update(effect.behavior_id for row in update.objects for effect in row.item.item_effects)
            known.update(item.item_id for row in update.objects for item in row.contained_items or ())
            known.update(effect.behavior_id for row in update.objects for item in row.contained_items or ()
                for effect in item.item_effects)
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
                known.update(_patch_content(fact.changes, fact.items))
            elif isinstance(fact, SensoryFact):
                known.update(row.content_ref.content_id for row in fact.spatial_effects_changed.values())
            elif isinstance(fact, ObjectDestroyedFact):
                known.add(fact.item_id)
            elif isinstance(fact, MechanismActivationFact):
                known.add(fact.mechanism_content_id)
            for row in node.content_attributions:
                known.update(identity for identity in (row.behavior_id, row.provided_by_id, row.origin_root_id)
                             if identity is not None)
    return known


def admitted_content(catalog: UIContentManifest, state: PlayerState,
                     lineages: tuple[PlayerLineage, ...] = ()) -> tuple[ContentDescriptor, ...]:
    """Public catalog plus independently observed identities; no encounter-wide scan."""
    known = {row.ref.content_id for row in state.content}
    for actor in state.actors.values():
        known.update(_actor_content(actor))
    for record in state.items.values():
        known.update(_item_content(record))
    known.update(row.item.item_id for row in state.objects.values())
    known.update(effect.behavior_id for row in state.objects.values() for effect in row.item.item_effects)
    known.update(item.item_id for row in state.objects.values() for item in row.contained_items or ())
    known.update(effect.behavior_id for row in state.objects.values() for item in row.contained_items or ()
        for effect in item.item_effects)
    if state.senses is not None:
        known.update(row.content_ref.content_id for row in state.senses.spatial_effects.values())
    known.update(_lineage_content(lineages))
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


@dataclass(frozen=True, slots=True)
class ContentCatalog:
    """Read-only lookup over the supplied manifest, shared by its audiences."""

    source: UIContentManifest
    observed: dict[str, tuple[ContentDescriptor, ...]]
    identity_content_ids: dict[str, str]


def index_content_catalog(catalog: UIContentManifest) -> ContentCatalog:
    public_ids = {ref.content_id for ref, descriptor in catalog.content
        if descriptor.visibility is ContentVisibility.PUBLIC}
    observed: dict[str, list[ContentDescriptor]] = {}
    for ref, descriptor in catalog.content:
        if descriptor.visibility is ContentVisibility.OBSERVED:
            observed.setdefault(ref.content_id, []).append(descriptor.model_copy(update={
                "related_content_refs": tuple(related for related in descriptor.related_content_refs
                    if related.content_id in public_ids)}))
    return ContentCatalog(catalog, {key: tuple(rows) for key, rows in observed.items()},
        {ref.identity_key: ref.content_id for ref, _ in catalog.content})


def observed_content_additions(catalog: ContentCatalog, retained: frozenset[str],
                               lineages: tuple[PlayerLineage, ...]) -> tuple[ContentDescriptor, ...]:
    """Resolve only newly witnessed identities; startup admits public content."""
    known = _lineage_content(lineages)
    known.update(catalog.identity_content_ids[value] for value in tuple(known)
        if value in catalog.identity_content_ids)
    additions = {row.ref.identity_key: row for identity in known
        for row in catalog.observed.get(identity, ()) if row.ref.identity_key not in retained}
    return tuple(additions[key] for key in sorted(additions))
