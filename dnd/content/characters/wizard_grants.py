"""Direct Wizard class composition with exact native receipts."""

from typing import cast
from dnd.core.base_block import BaseBlock
from dataclasses import replace
from dnd.classes import wizard
from dnd.blocks.spellcasting import FreeSpellCastGrant
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.core.content.runtime import BehaviorBinding
from dnd.content.characters.spellcasting_grants import class_casting_source
from dnd.content.characters.caster_chassis import (
    validate_class_feature_handles,
    remove_class_feature_handles,
    prepare_class_feature_removals,
)
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.content.characters.spellcasting_grants import wizard_book_changed

from dnd.content.characters.caster_chassis import (
    apply_caster_chassis,
    remove_caster_chassis,
    class_level_source,
    validate_caster_chassis,
)
from dnd.content.characters.class_definitions import resolve_wizard_level
from dnd.content.characters.spellcasting_grants import (
    reconcile_normal_spell_slots,
    reconcile_prepared_spell_entitlements,
    reconcile_prepared_casting_source,
    validate_normal_spell_slots,
    validate_prepared_casting_source,
)
from dnd.entity import Entity
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import WizardGrantReceipt


def apply_wizard_level(
    entity: Entity, level: AppliedClassLevel, *, initial_first_class: bool | None = None
) -> WizardGrantReceipt:
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.WIZARD)
    resolved = resolve_wizard_level(
        level,
        entity.applied_class_levels,
        initial_first_class=initial_first_class,
        scribed_spell_ids=entity.scribed_spell_ids,
    )
    try:
        entity.character_grant_receipt(level.step_id)
    except KeyError:
        pass
    else:
        raise RuntimeError("Class level receipt is already installed")
    chassis = apply_caster_chassis(entity, resolved)
    receipt = WizardGrantReceipt(
        step_id=level.step_id,
        source_id=class_level_source(entity, level.step_id),
        chassis=chassis,
    )
    state_created = None
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    stored = False
    try:
        if level.resulting_class_level == 1:
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + ".book_changed"),
                source_entity_uuid=entity.uuid,
                name="Wizard Spellbook",
                semantic_key="class_feature.wizard.spellbook",
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.SPELLBOOK_CHANGED,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity.uuid,
                    )
                ],
                event_processor=wizard_book_changed,
            )
            try:
                entity.add_event_handler(handler)
            except BaseException:
                handler.remove_from_register()
                raise
            chassis = replace(
                chassis, handler_uuids=(*chassis.handler_uuids, handler.uuid)
            )
            receipt = replace(receipt, chassis=chassis)
        entity.applied_class_levels = (*previous, level)
        reconcile_prepared_casting_source(entity, CharacterClass.WIZARD)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        n = level.resulting_class_level
        state = wizard.recovery_state(entity)
        if state is None:
            state = wizard.WizardRecoveryState(
                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
            )
            admitted = entity.add_condition(state)
            if admitted is None or admitted.canceled:
                raise RuntimeError("Wizard recovery state was not admitted")
            state_created = state
        if n % 2 == 1:
            resource_source = class_level_source(
                entity, level.step_id + ".arcane_recovery"
            )
            entity.action_economy.add_resource_contribution(
                "arcane_recovery",
                resource_source,
                maximum=(n + 1) // 2,
                recharge_type=RechargeType.LONG_REST,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            entity.action_economy.set_resource_current(
                "arcane_recovery",
                max(0, (n + 1) // 2 - state.resource_spent.get("arcane_recovery", 0)),
            )
            receipt = replace(
                receipt,
                resource_contributions=(
                    *receipt.resource_contributions,
                    ("arcane_recovery", resource_source),
                ),
            )
        if n == 1:
            action = wizard.ArcaneRecovery(
                uuid=class_level_source(entity, level.step_id + ".recovery_action"),
                source_entity_uuid=entity.uuid,
                semantic_key="action.class.wizard.arcane_recovery",
                template=True,
                behavior_binding=BehaviorBinding(
                    behavior_id="action.class.wizard.arcane_recovery",
                    provided_by_id="class_feature.wizard.arcane_recovery",
                    origin_root_id=CharacterClass.WIZARD.value,
                    runtime_owner_uuid=entity.uuid,
                ),
            )
            try:
                entity.register_action(action)
            except BaseException:
                action.remove_from_register()
                raise
            receipt = replace(receipt, action_uuids=(action.uuid,))
        passives = {
            2: (
                (
                    wizard.sculpt_spells,
                    EventType.CAST_SPELL,
                    EventPhase.EXECUTION,
                    "class_feature.wizard.sculpt_spells",
                    False,
                ),
                (
                    wizard.sculpt_field_application,
                    EventType.EFFECT_APPLICATION,
                    EventPhase.DECLARATION,
                    "class_feature.wizard.sculpt_spells.field",
                    False,
                ),
                (
                    wizard.sculpt_retained_damage,
                    EventType.SPELL_DAMAGE_ROLL_RESULT,
                    EventPhase.EFFECT,
                    "class_feature.wizard.sculpt_spells.retained",
                    False,
                ),
            ),
            6: (
                (
                    wizard.potent_cantrip,
                    EventType.SPELL_DAMAGE_ROLL_RESULT,
                    EventPhase.EFFECT,
                    "class_feature.wizard.potent_cantrip",
                    False,
                ),
            ),
            10: (
                (
                    wizard.empowered_evocation,
                    EventType.SPELL_DAMAGE_ROLL_RESULT,
                    EventPhase.EFFECT,
                    "class_feature.wizard.empowered_evocation",
                    False,
                ),
            ),
            14: (
                (
                    wizard.select_overchannel,
                    EventType.CAST_SPELL,
                    EventPhase.DECLARATION,
                    "class_feature.wizard.overchannel",
                    True,
                ),
                (
                    wizard.maximize_selected_spell,
                    EventType.SPELL_DAMAGE_ROLL_RESULT,
                    EventPhase.EFFECT,
                    "class_feature.wizard.overchannel.damage",
                    False,
                ),
            ),
        }.get(n, ())
        for processor, kind, phase, feature, toggle in passives:
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + "." + feature),
                source_entity_uuid=entity.uuid,
                name=feature,
                semantic_key=feature,
                event_processor=processor,
                application_preview_filter=wizard.sculpt_application_admitted
                if processor is wizard.sculpt_spells
                else None,
                player_toggleable=toggle,
                enabled=not toggle,
                trigger_conditions=[
                    Trigger(
                        event_type=kind,
                        event_phase=phase,
                        event_source_entity_uuid=entity.uuid,
                    )
                ],
                behavior_binding=BehaviorBinding(
                    behavior_id=feature,
                    provided_by_id=feature,
                    origin_root_id=CharacterClass.WIZARD.value,
                    runtime_owner_uuid=entity.uuid,
                ),
            )
            try:
                entity.add_event_handler(handler)
            except BaseException:
                handler.remove_from_register()
                raise
            receipt = replace(
                receipt, handler_uuids=(*receipt.handler_uuids, handler.uuid)
            )
        for spell_id in (*resolved.mastery_spell_ids, *resolved.signature_spell_ids):
            signature = spell_id in resolved.signature_spell_ids
            feature = (
                "class_feature.wizard.signature_spells"
                if signature
                else "class_feature.wizard.spell_mastery"
            )
            source_id = class_casting_source(entity, CharacterClass.WIZARD)
            identity = class_level_source(
                entity, level.step_id + ".free_cast." + spell_id
            )
            resource_name = "signature_spell." + spell_id if signature else None
            if resource_name is not None:
                entity.action_economy.add_resource_contribution(
                    resource_name,
                    identity,
                    maximum=1,
                    recharge_type=RechargeType.SHORT_REST,
                    capacity_policy=ResourceCapacityPolicy.MAXIMUM,
                )
                entity.action_economy.set_resource_current(
                    resource_name,
                    max(0, 1 - state.resource_spent.get(resource_name, 0)),
                )
                receipt = replace(
                    receipt,
                    resource_contributions=(
                        *receipt.resource_contributions,
                        (resource_name, identity),
                    ),
                )
            rank = (
                3
                if signature
                else (1 if spell_id == resolved.mastery_spell_ids[0] else 2)
            )
            entity.spellcasting.free_cast_grants[identity] = FreeSpellCastGrant(
                grant_id=identity,
                provider_id=feature,
                source_id=source_id,
                spell_id=spell_id,
                cast_rank=rank,
                label="Signature Spell" if signature else "Spell Mastery",
                resource_name=resource_name,
            )
            receipt = replace(
                receipt, free_cast_grant_ids=(*receipt.free_cast_grant_ids, identity)
            )
        entity.store_character_grant_receipt(receipt)
        stored = True
        return receipt
    except BaseException:
        if stored:
            entity.remove_character_grant_receipt(level.step_id)
        for identity in receipt.free_cast_grant_ids:
            entity.spellcasting.free_cast_grants.pop(identity, None)
        remove_class_feature_handles(entity, receipt)
        if state_created is not None:
            entity.remove_condition_by_uuid(state_created.uuid)
        entity.applied_class_levels = previous
        entity.prepared_spell_selections = previous_preparations
        reconcile_prepared_casting_source(entity, CharacterClass.WIZARD)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        remove_caster_chassis(entity, chassis)
        raise


def remove_last_wizard_level(entity: Entity, *, parent_event=None) -> AppliedClassLevel:
    if (
        not entity.applied_class_levels
        or entity.applied_class_levels[-1].class_id is not CharacterClass.WIZARD
    ):
        raise RuntimeError("Last level does not belong to Wizard")
    level = entity.applied_class_levels[-1]
    receipt = cast(WizardGrantReceipt, entity.character_grant_receipt(level.step_id))
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.WIZARD)
    validate_caster_chassis(entity, receipt.chassis)
    validate_class_feature_handles(entity, receipt)
    if any(
        identity not in entity.spellcasting.free_cast_grants
        for identity in receipt.free_cast_grant_ids
    ):
        raise RuntimeError("Wizard free-cast grant ownership changed")
    prepared = prepare_class_feature_removals(entity, receipt, parent_event)
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    entity.applied_class_levels = previous[:-1]
    try:
        reconcile_prepared_casting_source(entity, CharacterClass.WIZARD)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
    except BaseException:
        BaseBlock.cancel_owned_condition_removals(
            prepared, "Class source reconciliation failed"
        )
        entity.prepared_spell_selections = previous_preparations
        entity.applied_class_levels = previous
        reconcile_prepared_casting_source(entity, CharacterClass.WIZARD)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        raise
    reconcile_prepared_spell_entitlements(entity)
    for identity in receipt.free_cast_grant_ids:
        entity.spellcasting.free_cast_grants.pop(identity)
    removals = remove_class_feature_handles(
        entity, receipt, parent_event, prepared=prepared, publish=False
    )
    remove_caster_chassis(entity, receipt.chassis)
    entity.remove_character_grant_receipt(level.step_id)
    BaseBlock.publish_owned_condition_removals(removals)
    return level
