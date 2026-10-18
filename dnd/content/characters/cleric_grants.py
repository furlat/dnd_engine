"""Direct Cleric class composition with exact native receipts."""

from typing import cast
from dnd.core.base_block import BaseBlock
from dataclasses import replace

from dnd.classes import cleric
from dnd.classes import divine_intervention
from dnd.classes.divine import ClassFeatureLifetime
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.core.events import EventHandler, EventType, EventPhase, Trigger
from dnd.core.content.runtime import BehaviorBinding
from dnd.content.characters.spellcasting_grants import class_casting_source
from dnd.content.characters.caster_chassis import (
    validate_class_feature_handles,
    remove_class_feature_handles,
    prepare_class_feature_removals,
)

from dnd.content.characters.caster_chassis import (
    apply_caster_chassis,
    remove_caster_chassis,
    class_level_source,
    validate_caster_chassis,
)
from dnd.content.characters.class_definitions import resolve_cleric_level
from dnd.content.characters.spellcasting_grants import (
    reconcile_normal_spell_slots,
    reconcile_prepared_spell_entitlements,
    reconcile_prepared_casting_source,
    validate_normal_spell_slots,
    validate_prepared_casting_source,
)
from dnd.entity import Entity
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import ClericGrantReceipt


def apply_cleric_level(
    entity: Entity, level: AppliedClassLevel, *, initial_first_class: bool | None = None
) -> ClericGrantReceipt:
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.CLERIC)
    resolved = resolve_cleric_level(
        level, entity.applied_class_levels, initial_first_class=initial_first_class
    )
    try:
        entity.character_grant_receipt(level.step_id)
    except KeyError:
        pass
    else:
        raise RuntimeError("Class level receipt is already installed")
    chassis = apply_caster_chassis(entity, resolved)
    receipt = ClericGrantReceipt(
        step_id=level.step_id,
        source_id=class_level_source(entity, level.step_id),
        chassis=chassis,
    )
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    stored = False
    try:
        entity.applied_class_levels = (*previous, level)
        reconcile_prepared_casting_source(entity, CharacterClass.CLERIC)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        n = level.resulting_class_level
        actions = []
        handlers = []
        resources = []
        # Record every installed native handle immediately for bounded rollback.
        if n in (2, 6, 18):
            resource_source = class_level_source(entity, level.step_id + ".divinity")
            entity.action_economy.add_resource_contribution(
                "channel_divinity",
                resource_source,
                maximum={2: 1, 6: 2, 18: 3}[n],
                recharge_type=RechargeType.SHORT_REST,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            resources.append(("channel_divinity", resource_source))
            receipt = replace(receipt, resource_contributions=tuple(resources))
        if n == 8:
            resource_source = class_level_source(entity, level.step_id + ".strike")
            entity.action_economy.add_resource_contribution(
                "divine_strike",
                resource_source,
                maximum=1,
                recharge_type=RechargeType.TURN_START,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            resources.append(("divine_strike", resource_source))
            receipt = replace(receipt, resource_contributions=tuple(resources))
        if n == 2:
            root = ClassFeatureLifetime(
                name="Cleric Channel Divinity Owner",
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            )
            admitted = entity.add_condition(root)
            if admitted is None or admitted.canceled:
                raise RuntimeError("Cleric feature lifetime was rejected")
            receipt = replace(receipt, condition_uuids=(root.uuid,))
            for action_type, action_id, feature_id in (
                (
                    cleric.TurnUndead,
                    "action.class.cleric.turn_undead",
                    "class_feature.cleric.turn_undead",
                ),
                (
                    cleric.PreserveLife,
                    "action.class.cleric.preserve_life",
                    "class_feature.cleric.preserve_life",
                ),
            ):
                extra = (
                    {
                        "feature_owner_uuid": root.uuid,
                        "casting_source_id": class_casting_source(
                            entity, CharacterClass.CLERIC
                        ),
                    }
                    if action_type is cleric.TurnUndead
                    else {}
                )
                action = action_type(
                    uuid=class_level_source(entity, level.step_id + "." + action_id),
                    source_entity_uuid=entity.uuid,
                    template=True,
                    semantic_key=action_id,
                    behavior_binding=BehaviorBinding(
                        behavior_id=action_id,
                        provided_by_id=feature_id,
                        origin_root_id=CharacterClass.CLERIC.value,
                        runtime_owner_uuid=entity.uuid,
                    ),
                    **extra,
                )
                try:
                    entity.register_action(action)
                except BaseException:
                    action.remove_from_register()
                    raise
                actions.append(action.uuid)
                receipt = replace(receipt, action_uuids=tuple(actions))
        passive = {
            1: (
                cleric.disciple_of_life,
                EventType.HEAL,
                "class_feature.cleric.disciple_of_life",
            ),
            6: (
                cleric.blessed_healer,
                EventType.HEALING_APPLIED,
                "class_feature.cleric.blessed_healer",
            ),
            8: (
                cleric.divine_strike,
                EventType.DAMAGE_ROLL_RESULT,
                "class_feature.cleric.divine_strike",
            ),
            17: (
                cleric.supreme_healing,
                EventType.HEAL_ROLL_RESULT,
                "class_feature.cleric.supreme_healing",
            ),
        }.get(n)
        if passive is not None:
            processor, kind, feature_id = passive
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + "." + feature_id),
                source_entity_uuid=entity.uuid,
                name=feature_id,
                semantic_key=feature_id,
                player_toggleable=n == 8,
                event_processor=processor,
                trigger_conditions=[
                    Trigger(
                        event_type=kind,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity.uuid,
                    )
                ],
                behavior_binding=BehaviorBinding(
                    behavior_id=feature_id,
                    provided_by_id=feature_id,
                    origin_root_id=CharacterClass.CLERIC.value,
                    runtime_owner_uuid=entity.uuid,
                ),
            )
            try:
                entity.add_event_handler(handler)
            except BaseException:
                handler.remove_from_register()
                raise
            handlers.append(handler.uuid)
            receipt = replace(receipt, handler_uuids=tuple(handlers))
        if n == 5:
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + ".destroy_undead"),
                source_entity_uuid=entity.uuid,
                name="Destroy Undead",
                semantic_key="class_feature.cleric.destroy_undead",
                event_processor=cleric.destroy_undead,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.ACTION_APPLICATION_COMMITTED,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity.uuid,
                    )
                ],
            )
            entity.add_event_handler(handler)
            receipt = replace(
                receipt, handler_uuids=(*receipt.handler_uuids, handler.uuid)
            )
        if n == 10:
            source = class_level_source(entity, level.step_id + ".intervention")
            entity.action_economy.add_resource_contribution(
                "divine_intervention",
                source,
                maximum=1,
                recharge_type=RechargeType.NEVER,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            receipt = replace(
                receipt,
                resource_contributions=(
                    *receipt.resource_contributions,
                    ("divine_intervention", source),
                ),
            )
            if divine_intervention.INTERVENTION_ID in entity.permanent_feature_uses:
                entity.action_economy.resources["divine_intervention"].current = 0
            owner = divine_intervention.InterventionUseOwner(
                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
            )
            admitted = entity.add_condition(owner)
            if admitted is None or admitted.canceled:
                raise RuntimeError("Divine Intervention use owner was rejected")
            receipt = replace(
                receipt, condition_uuids=(*receipt.condition_uuids, owner.uuid)
            )
            for action_type, key in (
                (divine_intervention.SunderHeretical, "sunder_heretical"),
                (divine_intervention.OpulentRevival, "opulent_revival"),
                (divine_intervention.ArmThyServant, "arm_thy_servant"),
                (divine_intervention.GoldenGenerosity, "golden_generosity"),
            ):
                identity = "action.class.cleric.divine_intervention." + key
                parameters = (
                    {
                        "casting_source_id": class_casting_source(
                            entity, CharacterClass.CLERIC
                        )
                    }
                    if action_type is divine_intervention.SunderHeretical
                    else {}
                )
                action = action_type(
                    uuid=class_level_source(entity, level.step_id + "." + identity),
                    source_entity_uuid=entity.uuid,
                    template=True,
                    semantic_key=identity,
                    behavior_binding=BehaviorBinding(
                        behavior_id=identity,
                        provided_by_id=divine_intervention.INTERVENTION_ID,
                        origin_root_id=CharacterClass.CLERIC.value,
                        runtime_owner_uuid=entity.uuid,
                    ),
                    **parameters,
                )
                entity.register_action(action)
                receipt = replace(
                    receipt, action_uuids=(*receipt.action_uuids, action.uuid)
                )
        entity.store_character_grant_receipt(receipt)
        stored = True
        return receipt
    except BaseException:
        if stored:
            entity.remove_character_grant_receipt(level.step_id)
        remove_class_feature_handles(entity, receipt)
        entity.applied_class_levels = previous
        entity.prepared_spell_selections = previous_preparations
        reconcile_prepared_casting_source(entity, CharacterClass.CLERIC)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        remove_caster_chassis(entity, chassis)
        raise


def remove_last_cleric_level(entity: Entity, *, parent_event=None) -> AppliedClassLevel:
    if (
        not entity.applied_class_levels
        or entity.applied_class_levels[-1].class_id is not CharacterClass.CLERIC
    ):
        raise RuntimeError("Last level does not belong to Cleric")
    level = entity.applied_class_levels[-1]
    receipt = cast(ClericGrantReceipt, entity.character_grant_receipt(level.step_id))
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.CLERIC)
    validate_caster_chassis(entity, receipt.chassis)
    validate_class_feature_handles(entity, receipt)
    prepared = prepare_class_feature_removals(entity, receipt, parent_event)
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    entity.applied_class_levels = previous[:-1]
    try:
        reconcile_prepared_casting_source(entity, CharacterClass.CLERIC)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
    except BaseException:
        BaseBlock.cancel_owned_condition_removals(
            prepared, "Class source reconciliation failed"
        )
        entity.prepared_spell_selections = previous_preparations
        entity.applied_class_levels = previous
        reconcile_prepared_casting_source(entity, CharacterClass.CLERIC)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        raise
    reconcile_prepared_spell_entitlements(entity)
    removals = remove_class_feature_handles(
        entity, receipt, parent_event, prepared=prepared, publish=False
    )
    remove_caster_chassis(entity, receipt.chassis)
    entity.remove_character_grant_receipt(level.step_id)
    BaseBlock.publish_owned_condition_removals(removals)
    return level
