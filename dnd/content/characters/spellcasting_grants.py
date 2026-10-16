"""Direct shared-slot and prepared-source composition, below concrete grants."""

from collections import Counter

from dnd.actions import SpellAction
from dnd.blocks.spellcasting import FreeSpellCastGrant
from dnd.types.class_spells import BG3_RITUAL_SPELL_IDS
from dnd.characters.spellbook import wizard_book
from dnd.characters.preparation import always_prepared_spells, preparation_error
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events import (
    EventQueue,
    EventPhase,
    SpellbookChangedEvent,
    SpellPreparationChangedEvent,
)
from dnd.spells.infernal import Thaumaturgy
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_SPECS
from dnd.spells.reaction_spell_content import LEARNED_REACTION_SPELL_SPECS
from dnd.types.character_progression import PreparedSpellSelection
from uuid import UUID, uuid5

from dnd.core.progression import (
    CasterProgression,
    FULL_CASTER_SPELL_SLOTS,
    MulticlassSlotRoundingPolicy,
    SpellcastingClassContribution,
    effective_spellcaster_level,
)
from dnd.content.characters.class_definitions import prepared_class_definition
from dnd.entity import Entity
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    RitualPreparationPolicy,
)


_SPELL_TYPES = {
    spec.content_id: spec.spell_type for spec in SPELL_CONTENT_IDENTITY_SPECS
}
_SPELL_TYPES["spell.thaumaturgy"] = Thaumaturgy
_REACTION_SPECS = {
    spec.declaration.ref.content_id: spec for spec in LEARNED_REACTION_SPELL_SPECS
}


CASTER_PROGRESSIONS = {
    CharacterClass.CLERIC: CasterProgression.FULL_CASTER,
    CharacterClass.PALADIN: CasterProgression.HALF_CASTER,
    CharacterClass.WIZARD: CasterProgression.FULL_CASTER,
    CharacterClass.SORCERER: CasterProgression.FULL_CASTER,
}


def aggregate_slot_source(entity: Entity) -> UUID:
    return uuid5(entity.uuid, "dnd-engine:character:shared-normal-slots:v1")


def shared_slot_capacities(levels: tuple[AppliedClassLevel, ...]) -> dict[int, int]:
    counts = Counter(row.class_id for row in levels)
    contributions = tuple(
        SpellcastingClassContribution(
            class_level=count,
            progression=CASTER_PROGRESSIONS[class_id],
            spellcasting_feature_class_level=2
            if class_id is CharacterClass.PALADIN
            else 1,
        )
        for class_id, count in counts.items()
        if class_id in CASTER_PROGRESSIONS
    )
    caster_level = effective_spellcaster_level(
        contributions, policy=MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN
    )
    return dict(FULL_CASTER_SPELL_SLOTS[caster_level]) if caster_level else {}


def reconcile_normal_spell_slots(
    entity: Entity, levels: tuple[AppliedClassLevel, ...] | None = None
) -> None:
    """Replace one capacity owner without touching spent costs or converted slots."""
    capacities = shared_slot_capacities(
        entity.applied_class_levels if levels is None else levels
    )
    owner = entity.action_economy.get_normal_spell_slot_capacity_source()
    previous = entity.action_economy.get_normal_spell_slot_capacities()
    desired_owner = aggregate_slot_source(entity)
    if owner is not None and owner != desired_owner:
        raise RuntimeError("Shared normal spell-slot capacity ownership changed")
    if previous == capacities and (
        owner == desired_owner or not capacities and owner is None
    ):
        return
    if owner is not None:
        entity.action_economy.remove_normal_spell_slot_capacity(owner)
    try:
        if capacities:
            entity.action_economy.set_normal_spell_slot_capacity(
                desired_owner, capacities
            )
    except BaseException:
        if owner is not None:
            entity.action_economy.set_normal_spell_slot_capacity(owner, previous)
        raise


def validate_normal_spell_slots(entity: Entity) -> None:
    expected = shared_slot_capacities(entity.applied_class_levels)
    expected_owner = aggregate_slot_source(entity) if expected else None
    if (
        entity.action_economy.get_normal_spell_slot_capacity_source() != expected_owner
        or entity.action_economy.get_normal_spell_slot_capacities() != expected
    ):
        raise RuntimeError("Shared normal spell-slot capacity ownership changed")


def class_casting_source(entity: Entity, class_id: CharacterClass) -> UUID:
    """New prepared classes own distinct permanent casting source identities."""
    return uuid5(entity.uuid, f"dnd-engine:character:spellcasting:{class_id.value}:v1")


def validate_prepared_casting_source(entity: Entity, class_id: CharacterClass) -> None:
    definition = prepared_class_definition(class_id)
    level = sum(row.class_id is class_id for row in entity.applied_class_levels)
    source = entity.spellcasting.sources.get(class_casting_source(entity, class_id))
    if level < definition.spellcasting_level:
        if source is not None:
            raise RuntimeError("Unexpected prepared class casting source")
        return
    if (
        source is None
        or source.provider_id != class_id.value
        or source.provider_level != level
        or source.ability != definition.spellcasting_ability
        or source.caster_progression != CASTER_PROGRESSIONS[class_id]
        or source.ritual_policy != RitualPreparationPolicy.PREPARED
    ):
        raise RuntimeError("Prepared class casting source ownership changed")


def reconcile_prepared_casting_source(entity: Entity, class_id: CharacterClass) -> None:
    definition = prepared_class_definition(class_id)
    level = sum(row.class_id is class_id for row in entity.applied_class_levels)
    source_id = class_casting_source(entity, class_id)
    previous = entity.spellcasting.sources.get(source_id)
    entity.spellcasting.remove_source(source_id)
    try:
        if level >= definition.spellcasting_level:
            rank = max(
                FULL_CASTER_SPELL_SLOTS[
                    (level + 1) // 2 if class_id is CharacterClass.PALADIN else level
                ]
            )
            entity.spellcasting.add_source(
                source_id,
                definition.spellcasting_ability,
                provider_id=class_id.value,
                caster_progression=CASTER_PROGRESSIONS[class_id],
                provider_level=level,
                maximum_spell_rank=rank,
                ritual_policy=RitualPreparationPolicy.PREPARED,
            )
    except BaseException:
        if previous is not None:
            entity.spellcasting.sources[source_id] = previous
        raise


def reconcile_prepared_spell_entitlements(entity: Entity) -> None:
    """Install exact-source templates and shared reaction leases from plain state."""
    # Unsourced items use BG3's last newly entered qualifying class; Champion
    # Fighter does not change it (a pure custom Fighter defaults to INT). Exact
    # class/innate sources continue to resolve independently.
    entered = tuple(dict.fromkeys(row.class_id for row in entity.applied_class_levels))
    item_abilities = {
        CharacterClass.WIZARD: "intelligence",
        CharacterClass.CLERIC: "wisdom",
        CharacterClass.PALADIN: "charisma",
        CharacterClass.SORCERER: "charisma",
        CharacterClass.BARBARIAN: "charisma",
    }
    qualified = [class_id for class_id in entered if class_id in item_abilities]
    if qualified:
        entity.spellcasting.spellcasting_ability = item_abilities[qualified[-1]]
    elif entered:
        entity.spellcasting.spellcasting_ability = "intelligence"
    for class_id in (
        CharacterClass.CLERIC,
        CharacterClass.PALADIN,
        CharacterClass.WIZARD,
    ):
        definition = prepared_class_definition(class_id)
        source_id = class_casting_source(entity, class_id)
        source = entity.spellcasting.sources.get(source_id)
        desired: tuple[str, ...] = ()
        accessible: tuple[str, ...] = ()
        if source is not None:
            own_levels = tuple(
                row for row in entity.applied_class_levels if row.class_id is class_id
            )
            cantrips = tuple(
                spell
                for row in own_levels
                for choice in row.choices
                if choice.choice_id.endswith(".cantrips")
                for spell in choice.values
            )
            if class_id is CharacterClass.WIZARD:
                cantrips = (
                    *cantrips,
                    *(
                        spell
                        for spell in entity.scribed_spell_ids
                        if definition.spell_ranks[spell] == 0
                    ),
                )
            selected = next(
                (
                    row.spell_ids
                    for row in entity.prepared_spell_selections
                    if row.source_id == class_id.value + ".spellcasting"
                ),
                (),
            )
            maximum = (
                max(shared_slot_capacities(entity.applied_class_levels), default=0)
                if class_id is CharacterClass.WIZARD
                else source.maximum_spell_rank
            )
            accessible = tuple(
                spell
                for spell in selected
                if spell in definition.spell_ranks
                and definition.spell_ranks[spell] <= maximum
            )
            if class_id is CharacterClass.WIZARD:
                accessible = tuple(
                    spell for spell in accessible if spell in wizard_book(entity)
                )
            desired = tuple(
                dict.fromkeys(
                    (
                        *cantrips,
                        *accessible,
                        *always_prepared_spells(class_id, entity.applied_class_levels),
                    )
                )
            )
        semantic_source = class_id.value + ".spellcasting"
        entity.prepared_spell_selections = tuple(
            PreparedSpellSelection(row.source_id, accessible)
            if row.source_id == semantic_source
            else row
            for row in entity.prepared_spell_selections
            if row.source_id != semantic_source or source is not None
        )
        entity.spellcasting.spell_entitlements[source_id] = desired
        existing = {
            action.semantic_key: action
            for action in entity.registered_actions
            if isinstance(action, SpellAction)
            and action.spellcasting_source_id == source_id
            and action.semantic_key in _SPELL_TYPES
        }
        old_reactions = {
            spell_id: ownership
            for spell_id, ownership in entity.spellcasting.learned_reaction_spell_handlers.items()
            if source_id in ownership.sources
        }
        for spell_id in desired:
            if spell_id in _REACTION_SPECS:
                if spell_id in old_reactions:
                    continue
                ownership = entity.spellcasting.learned_reaction_spell_handler_uuid(
                    spell_id
                )
                if ownership is None:
                    handler = _REACTION_SPECS[spell_id].handler_factory(entity.uuid)
                    handler.enabled = (
                        entity.spellcasting.learned_reaction_preferences.get(
                            spell_id, handler.enabled
                        )
                    )
                    handler.behavior_binding = BehaviorBinding(
                        behavior_id="reaction." + spell_id,
                        provided_by_id=spell_id,
                        origin_root_id=spell_id,
                        runtime_owner_uuid=entity.uuid,
                    )
                    try:
                        entity.add_event_handler(handler)
                    except BaseException:
                        handler.remove_from_register()
                        raise
                    ownership = handler.uuid
                try:
                    entity.spellcasting.add_learned_reaction_spell_source(
                        spell_id=spell_id, source_id=source_id, handler_uuid=ownership
                    )
                except BaseException:
                    if (
                        entity.spellcasting.learned_reaction_spell_handler_uuid(
                            spell_id
                        )
                        is None
                    ):
                        failed_handler = entity.event_handlers[ownership]
                        entity.remove_event_handler(failed_handler)
                        failed_handler.remove_from_register()
                    raise
            elif spell_id not in existing:
                action = _SPELL_TYPES[spell_id](
                    uuid=uuid5(source_id, spell_id),
                    source_entity_uuid=entity.uuid,
                    spellcasting_source_id=source_id,
                    caster_level=len(entity.applied_class_levels),
                    semantic_key=spell_id,
                    template=True,
                    behavior_binding=BehaviorBinding(
                        behavior_id=spell_id,
                        provided_by_id=spell_id,
                        origin_root_id=spell_id,
                        runtime_owner_uuid=entity.uuid,
                    ),
                )
                try:
                    entity.register_action(action)
                except BaseException:
                    action.remove_from_register()
                    raise
        for spell_id, action in existing.items():
            if spell_id not in desired:
                entity.unregister_action_by_uuid(action.uuid)
        for spell_id, ownership in old_reactions.items():
            if spell_id not in desired:
                last = entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_id=spell_id,
                    source_id=source_id,
                    handler_uuid=ownership.handler_uuid,
                )
                if last:
                    handler = entity.event_handlers[ownership.handler_uuid]
                    if handler.player_toggleable:
                        entity.spellcasting.learned_reaction_preferences[spell_id] = (
                            handler.enabled
                        )
                    entity.remove_event_handler(handler)
                    handler.remove_from_register()
    entity.spellcasting.free_cast_grants = {
        identity: grant
        for identity, grant in entity.spellcasting.free_cast_grants.items()
        if grant.provider_id != "rule.bg3_ritual"
    }
    for action in entity.registered_actions:
        if (
            isinstance(action, SpellAction)
            and action.semantic_key in BG3_RITUAL_SPELL_IDS
        ):
            source = entity.spellcasting.sources.get(action.spellcasting_source_id)
            if source is not None and source.ritual_policy in (
                RitualPreparationPolicy.KNOWN,
                RitualPreparationPolicy.PREPARED,
            ):
                grant_id = uuid5(source.source_id, "ritual." + action.semantic_key)
                entity.spellcasting.free_cast_grants[grant_id] = FreeSpellCastGrant(
                    grant_id=grant_id,
                    source_id=source.source_id,
                    provider_id="rule.bg3_ritual",
                    spell_id=action.semantic_key,
                    cast_rank=action.spell_level,
                    label="Ritual",
                    outside_encounter_only=True,
                )
    for action in entity.registered_actions:
        if isinstance(action, SpellAction) and action.spell_level == 0:
            action.caster_level = max(1, len(entity.applied_class_levels))


def change_prepared_spells(
    entity: Entity, selection: PreparedSpellSelection
) -> SpellPreparationChangedEvent:
    """Replace one preparation outside an authoritative active encounter."""
    if entity.active_encounter_uuid is not None:
        raise ValueError("Spell preparation cannot change during an encounter")
    classes = {
        class_id.value + ".spellcasting": class_id
        for class_id in (
            CharacterClass.CLERIC,
            CharacterClass.PALADIN,
            CharacterClass.WIZARD,
        )
    }
    class_id = classes.get(selection.source_id)
    if class_id is None:
        raise ValueError("Unknown prepared casting source")
    validate_prepared_casting_source(entity, class_id)
    definition = prepared_class_definition(class_id)
    error = preparation_error(
        class_id,
        entity.applied_class_levels,
        entity.scribed_spell_ids,
        selection.spell_ids,
        entity.ability_scores.get_ability(definition.spellcasting_ability)
        .get_combined_values(use_register=False)
        .normalized_score,
        max(shared_slot_capacities(entity.applied_class_levels), default=0),
    )
    if error:
        raise ValueError(error)
    previous = entity.prepared_spell_selections
    entity.prepared_spell_selections = (
        *tuple(row for row in previous if row.source_id != selection.source_id),
        selection,
    )
    try:
        reconcile_prepared_spell_entitlements(entity)
    except BaseException:
        entity.prepared_spell_selections = previous
        reconcile_prepared_spell_entitlements(entity)
        raise
    return EventQueue.publish_completed_fact(
        SpellPreparationChangedEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
            casting_source_id=selection.source_id,
            prepared_spell_selections=entity.prepared_spell_selections,
        )
    )


def wizard_book_changed(event: SpellbookChangedEvent, context: UUID) -> None:
    actor = Entity.get(event.source_entity_uuid)
    if actor is not None:
        reconcile_prepared_spell_entitlements(actor)
