"""Direct aggregate class progression over the three authored class owners."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid5

from dnd.content.characters.barbarian_grants import (
    apply_barbarian_level,
    barbarian_level_has_active_child,
    remove_last_barbarian_level,
)
from dnd.content.characters.fighter_grants import (
    apply_fighter_level,
    remove_last_fighter_level,
)
from dnd.content.characters.origin_grants import reconcile_origin_total_level
from dnd.content.characters.origin_definitions import resolve_origin
from dnd.content.characters.origin_grants import (
    ORIGIN_STEP_ID,
    apply_origin,
    remove_origin,
)
from dnd.content.characters.sorcerer_grants import (
    apply_sorcerer_level,
    remove_last_sorcerer_level,
    sorcerer_level_has_active_child,
)
from dnd.core.events import (
    EntityLevelAddedEvent,
    EntityLevelRemovedEvent,
    Event,
    EventPhase,
    EventQueue,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.progression import proficiency_bonus_for_level
from dnd.entity import Entity
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import (
    BarbarianGrantReceipt,
    CharacterGrantReceipt,
    FighterGrantReceipt,
    SorcererGrantReceipt,
)


def _proficiency_source(entity: Entity) -> UUID:
    return uuid5(entity.uuid, "dnd-engine:character:total-level-proficiency:v1")


def _class_levels(
    levels: tuple[AppliedClassLevel, ...],
) -> tuple[tuple[CharacterClass, int], ...]:
    counts = {
        class_id: sum(row.class_id is class_id for row in levels)
        for class_id in CharacterClass
    }
    return tuple(
        (class_id, counts[class_id])
        for class_id in CharacterClass
        if counts[class_id]
    )


def _validate_multiclass_prerequisites(
    entity: Entity,
    incoming: CharacterClass,
) -> None:
    existing = {row.class_id for row in entity.applied_class_levels}
    if not existing or incoming in existing:
        return
    for class_id in (*tuple(existing), incoming):
        if class_id is CharacterClass.BARBARIAN:
            valid = entity.ability_scores.strength.ability_score.score >= 13
        elif class_id is CharacterClass.FIGHTER:
            valid = (
                entity.ability_scores.strength.ability_score.score >= 13
                or entity.ability_scores.dexterity.ability_score.score >= 13
            )
        else:
            valid = entity.ability_scores.charisma.ability_score.score >= 13
        if not valid:
            raise ValueError(
                f"multiclass prerequisite is not met for {class_id.value}",
            )


def _reconcile_proficiency(entity: Entity, total_level: int) -> None:
    if entity.character_body_id is None:
        return
    source_id = _proficiency_source(entity)
    existing = entity.proficiency_bonus.self_static.value_modifiers.get(source_id)
    if existing is not None:
        entity.proficiency_bonus.self_static.remove_value_modifier(source_id)
        NumericalModifier.unregister(source_id)
    if total_level == 0:
        return
    progression_bonus = proficiency_bonus_for_level(total_level) - 2
    if progression_bonus == 0:
        return
    entity.proficiency_bonus.self_static.add_value_modifier(NumericalModifier(
        uuid=source_id,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name="Character Total-Level Proficiency",
        value=progression_bonus,
    ))


def _apply_family(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    initial_first_class: bool | None = None,
) -> CharacterGrantReceipt:
    if level.class_id is CharacterClass.FIGHTER:
        return apply_fighter_level(
            entity,
            level,
            initial_first_class=initial_first_class,
        )
    if level.class_id is CharacterClass.BARBARIAN:
        return apply_barbarian_level(
            entity,
            level,
            initial_first_class=initial_first_class,
        )
    return apply_sorcerer_level(
        entity,
        level,
        initial_first_class=initial_first_class,
    )


def _remove_family(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    parent_event: Event | None = None,
) -> AppliedClassLevel:
    if level.class_id is CharacterClass.FIGHTER:
        return remove_last_fighter_level(entity)
    if level.class_id is CharacterClass.BARBARIAN:
        return remove_last_barbarian_level(entity, parent_event=parent_event)
    return remove_last_sorcerer_level(entity, parent_event=parent_event)


def _has_active_child(entity: Entity, level: AppliedClassLevel) -> bool:
    if level.class_id is CharacterClass.BARBARIAN:
        return barbarian_level_has_active_child(entity)
    if level.class_id is CharacterClass.SORCERER:
        return sorcerer_level_has_active_child(entity)
    return False


def _changed_facts(
    entity: Entity,
    level: AppliedClassLevel,
    receipt: CharacterGrantReceipt,
) -> dict[str, tuple[str, ...]]:
    if level.class_id is CharacterClass.FIGHTER:
        fighter_receipt = cast(FighterGrantReceipt, receipt)
        action_uuids = fighter_receipt.action_uuids
        handler_uuids = fighter_receipt.handler_uuids
        features = fighter_receipt.feature_sources
        resources = fighter_receipt.resource_contributions
        spell_sources: tuple[str, ...] = ()
    elif level.class_id is CharacterClass.BARBARIAN:
        barbarian_receipt = cast(BarbarianGrantReceipt, receipt)
        action_uuids = barbarian_receipt.action_uuids
        handler_uuids = barbarian_receipt.handler_uuids
        features = barbarian_receipt.feature_sources
        resources = barbarian_receipt.resource_contributions
        spell_sources = ()
    else:
        sorcerer_receipt = cast(SorcererGrantReceipt, receipt)
        action_uuids = sorcerer_receipt.action_uuids
        handler_uuids = sorcerer_receipt.handler_uuids
        features = sorcerer_receipt.feature_sources
        resources = (
            *sorcerer_receipt.resource_contributions,
            *sorcerer_receipt.resource_recovery_contributions,
        )
        spell_sources = ("class.sorcerer.spellcasting",)
    action_ids = tuple(
        action.semantic_key
        for action in entity.registered_actions
        if action.uuid in action_uuids
    )
    handler_ids = tuple(
        entity.event_handlers[handler_uuid].semantic_key
        for handler_uuid in handler_uuids
        if handler_uuid in entity.event_handlers
    )
    spell_ids = tuple(
        value
        for choice in level.choices
        if choice.choice_id.endswith((
            ".cantrips",
            ".spell_known",
            ".spell_replacement",
        ))
        for value in choice.values
    )
    return {
        "changed_feature_ids": tuple(dict.fromkeys(row[0] for row in features)),
        "changed_action_ids": tuple(dict.fromkeys(action_ids)),
        "changed_handler_ids": tuple(dict.fromkeys(handler_ids)),
        "changed_resource_ids": tuple(
            dict.fromkeys(resource_name for resource_name, _ in resources)
        ),
        "changed_spell_source_ids": spell_sources,
        "changed_spell_ids": tuple(dict.fromkeys(spell_ids)),
    }


def _added_event(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    phase: EventPhase,
    previous_levels: tuple[AppliedClassLevel, ...],
    changed: dict[str, tuple[str, ...]] | None = None,
) -> EntityLevelAddedEvent:
    resulting = (*previous_levels, level)
    return EntityLevelAddedEvent(
        source_entity_uuid=entity.uuid,
        source_entity_name=entity.name,
        target_entity_uuid=entity.uuid,
        target_entity_name=entity.name,
        use_register=False,
        phase=phase,
        entity_uuid=entity.uuid,
        previous_total_level=len(previous_levels),
        new_total_level=len(resulting),
        level=level,
        resulting_class_levels=_class_levels(resulting),
        applied_origin_state=entity.applied_origin_state,
        applied_class_levels=resulting,
        prepared_spell_selections=entity.prepared_spell_selections,
        feature_toggle_selections=entity.feature_toggle_selections,
        **(changed or {}),
    )


def _removed_event(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    phase: EventPhase,
    previous_levels: tuple[AppliedClassLevel, ...],
    changed: dict[str, tuple[str, ...]] | None = None,
) -> EntityLevelRemovedEvent:
    resulting = previous_levels[:-1]
    return EntityLevelRemovedEvent(
        source_entity_uuid=entity.uuid,
        source_entity_name=entity.name,
        target_entity_uuid=entity.uuid,
        target_entity_name=entity.name,
        use_register=False,
        phase=phase,
        entity_uuid=entity.uuid,
        previous_total_level=len(previous_levels),
        new_total_level=len(resulting),
        level=level,
        resulting_class_levels=_class_levels(resulting),
        applied_origin_state=entity.applied_origin_state,
        applied_class_levels=resulting,
        prepared_spell_selections=entity.prepared_spell_selections,
        feature_toggle_selections=entity.feature_toggle_selections,
        **(changed or {}),
    )


def _preflight_level_event(event: Event) -> Event:
    declaration = EventQueue.preflight(event)
    if declaration.canceled:
        raise ValueError(declaration.status_message or "level declaration canceled")
    execution = EventQueue.preflight(declaration.model_copy(update={
        "phase": EventPhase.EXECUTION,
        "use_register": False,
    }))
    if execution.canceled:
        raise ValueError(execution.status_message or "level execution canceled")
    return execution


def add_class_level(
    entity: Entity,
    level: AppliedClassLevel,
) -> EntityLevelAddedEvent:
    """Validate, apply, and publish one direct post-birth class level."""
    previous_levels = entity.applied_class_levels
    if len(previous_levels) >= 20:
        raise ValueError("total character level cannot exceed 20")
    _validate_multiclass_prerequisites(entity, level.class_id)
    execution = _preflight_level_event(_added_event(
        entity,
        level,
        phase=EventPhase.DECLARATION,
        previous_levels=previous_levels,
    ))
    del execution

    receipt = _apply_family(entity, level, initial_first_class=False)
    try:
        if entity.applied_origin_state is not None and previous_levels:
            reconcile_origin_total_level(
                entity,
                previous_level=len(previous_levels),
                new_level=len(previous_levels) + 1,
            )
        _reconcile_proficiency(entity, len(previous_levels) + 1)
        completed = _added_event(
            entity,
            level,
            phase=EventPhase.COMPLETION,
            previous_levels=previous_levels,
            changed=_changed_facts(entity, level, receipt),
        )
        return EventQueue.publish_completed_fact(completed)
    except BaseException:
        _remove_family(entity, level)
        if entity.applied_origin_state is not None and previous_levels:
            reconcile_origin_total_level(
                entity,
                previous_level=len(previous_levels) + 1,
                new_level=len(previous_levels),
            )
        _reconcile_proficiency(entity, len(previous_levels))
        raise


def apply_initial_class_levels(
    entity: Entity,
    levels: tuple[AppliedClassLevel, ...],
) -> None:
    """Install one already-resolved initial level sequence without Events."""
    if entity.creation_committed:
        raise RuntimeError("initial class levels require an unpublished Entity")
    if entity.applied_class_levels:
        raise RuntimeError("initial class progression is already installed")
    if not levels:
        raise ValueError("a character build requires at least one class level")
    if len(levels) > 20:
        raise ValueError("total character level cannot exceed 20")

    try:
        for index, level in enumerate(levels):
            _validate_multiclass_prerequisites(entity, level.class_id)
            _apply_family(
                entity,
                level,
                initial_first_class=index == 0,
            )
        _reconcile_proficiency(entity, len(levels))
    except BaseException:
        while entity.applied_class_levels:
            installed = entity.applied_class_levels[-1]
            _remove_family(entity, installed)
        _reconcile_proficiency(entity, 0)
        raise


def remove_last_class_level(entity: Entity) -> EntityLevelRemovedEvent:
    """Remove and publish the last direct class level in exact LIFO order."""
    previous_levels = entity.applied_class_levels
    if not previous_levels:
        raise RuntimeError("entity has no applied class level")
    if entity.applied_origin_state is not None and len(previous_levels) == 1:
        raise ValueError("a character origin cannot be reconciled to level zero")
    level = previous_levels[-1]
    receipt = entity.character_grant_receipt(level.step_id)
    changed = _changed_facts(entity, level, receipt)
    prior_action_order = tuple(action.uuid for action in entity.registered_actions)
    prior_block_handler_order = tuple(entity.event_handlers)
    prior_global_handler_order = EventQueue.event_handler_order()
    prior_handler_enabled = tuple(
        (handler_uuid, handler.enabled)
        for handler_uuid, handler in entity.event_handlers.items()
    )
    prior_resource_current = tuple(
        (name, resource.current)
        for name, resource in entity.action_economy.resources.items()
    )
    prior_origin_receipt = (
        entity.character_grant_receipt(ORIGIN_STEP_ID)
        if entity.applied_origin_state is not None
        else None
    )
    execution = _preflight_level_event(_removed_event(
        entity,
        level,
        phase=EventPhase.DECLARATION,
        previous_levels=previous_levels,
    ))
    parent_event = (
        EventQueue.publish_preflighted(execution)
        if _has_active_child(entity, level)
        else None
    )

    _remove_family(entity, level, parent_event=parent_event)
    if entity.applied_origin_state is not None:
        reconcile_origin_total_level(
            entity,
            previous_level=len(previous_levels),
            new_level=len(previous_levels) - 1,
            parent_event=parent_event,
        )
    _reconcile_proficiency(entity, len(previous_levels) - 1)
    completed = _removed_event(
        entity,
        level,
        phase=EventPhase.COMPLETION,
        previous_levels=previous_levels,
        changed=changed,
    )
    if parent_event is not None:
        completed.lineage_uuid = parent_event.lineage_uuid
        completed.parent_event = parent_event.parent_event
        completed.children_events = list(parent_event.children_events)
        completed.lineage_children_events = list(dict.fromkeys((
            *parent_event.lineage_children_events,
            *parent_event.children_events,
        )))
    try:
        return EventQueue.publish_completed_fact(completed)
    except BaseException:
        if parent_event is not None:
            committed = completed.model_copy(update={
                "use_register": True,
                "is_first": True,
                "is_last": True,
                "timestamp": datetime.now(UTC),
            })
            EventQueue.register_completion_sequence((committed,))
            raise
        restored_receipt = _apply_family(
            entity,
            level,
            initial_first_class=any(
                ".first_class." in choice.choice_id
                for choice in level.choices
            ),
        )
        if entity.applied_origin_state is not None:
            reconcile_origin_total_level(
                entity,
                previous_level=len(previous_levels) - 1,
                new_level=len(previous_levels),
            )
        _reconcile_proficiency(entity, len(previous_levels))
        if restored_receipt != receipt:
            raise RuntimeError("class-level removal restoration changed its receipt")
        if prior_origin_receipt is not None:
            restored_origin_receipt = entity.character_grant_receipt(ORIGIN_STEP_ID)
            if restored_origin_receipt != prior_origin_receipt:
                raise RuntimeError("class-level removal restoration changed origin ownership")
        if set(entity.action_economy.resources) != {
            name for name, _ in prior_resource_current
        }:
            raise RuntimeError("class-level removal restoration changed resources")
        for name, current in prior_resource_current:
            entity.action_economy.set_resource_current(name, current)
        for handler_uuid, enabled in prior_handler_enabled:
            handler = entity.event_handlers.get(handler_uuid)
            if handler is None:
                raise RuntimeError("class-level removal restoration lost a handler")
            handler.enabled = enabled
        entity.set_registered_action_order(prior_action_order)
        entity.set_event_handler_order(prior_block_handler_order)
        EventQueue.set_event_handler_order(prior_global_handler_order)
        raise


def hydrate_class_progression(entity: Entity) -> None:
    """Rebuild class owners and receipts from already-loaded semantic rows."""
    semantic_levels = entity.applied_class_levels
    if not semantic_levels:
        return
    origin_state = entity.applied_origin_state
    origin_identity = (
        entity.character_species,
        entity.character_species_variant,
        entity.character_background,
    )
    origin_installed = False
    entity.applied_class_levels = ()
    try:
        if origin_state is not None:
            species, species_variant, background = origin_identity
            if species is None or background is None:
                raise RuntimeError("loaded origin semantic identity is incomplete")
            try:
                entity.character_grant_receipt(ORIGIN_STEP_ID)
            except KeyError:
                pass
            else:
                raise RuntimeError("loaded origin already has runtime receipt state")
            entity.applied_origin_state = None
            entity.clear_character_origin_identity()
            apply_origin(
                entity,
                resolve_origin(
                    species=species,
                    species_variant=species_variant,
                    background=background,
                    state=origin_state,
                ),
                character_level=len(semantic_levels),
            )
            origin_installed = True
        for level in semantic_levels:
            _apply_family(
                entity,
                level,
                initial_first_class=any(
                    ".first_class." in choice.choice_id
                    for choice in level.choices
                ),
            )
        _reconcile_proficiency(entity, len(semantic_levels))
    except BaseException:
        while entity.applied_class_levels:
            _remove_family(entity, entity.applied_class_levels[-1])
        if origin_installed:
            remove_origin(entity)
        if origin_state is not None:
            species, species_variant, background = origin_identity
            if species is None or background is None:
                raise RuntimeError("loaded origin semantic identity is incomplete")
            entity.set_character_origin_identity(
                species=species,
                species_variant=species_variant,
                background=background,
            )
            entity.applied_origin_state = origin_state
        entity.applied_class_levels = semantic_levels
        _reconcile_proficiency(entity, 0)
        raise


__all__ = [
    "add_class_level",
    "apply_initial_class_levels",
    "hydrate_class_progression",
    "remove_last_class_level",
]
