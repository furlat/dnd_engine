"""Direct Paladin class composition with exact native receipts."""

from typing import cast
from dataclasses import replace
from dnd.classes import paladin, fighter
from dnd.classes.divine import ClassFeatureLifetime
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events import EventHandler, EventType, EventPhase, Trigger
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.content.characters.spellcasting_grants import class_casting_source
from dnd.core.base_block import BaseBlock

from dnd.content.characters.caster_chassis import (
    apply_caster_chassis,
    remove_caster_chassis,
    class_level_source,
    validate_caster_chassis,
    validate_class_feature_handles,
    remove_class_feature_handles,
    prepare_class_feature_removals,
)
from dnd.content.characters.class_definitions import resolve_paladin_level
from dnd.content.characters.spellcasting_grants import (
    reconcile_normal_spell_slots,
    reconcile_prepared_spell_entitlements,
    reconcile_prepared_casting_source,
    validate_normal_spell_slots,
    validate_prepared_casting_source,
)
from dnd.entity import Entity
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import PaladinGrantReceipt


def apply_paladin_level(
    entity: Entity, level: AppliedClassLevel, *, initial_first_class: bool | None = None
) -> PaladinGrantReceipt:
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.PALADIN)
    resolved = resolve_paladin_level(
        level, entity.applied_class_levels, initial_first_class=initial_first_class
    )
    try:
        entity.character_grant_receipt(level.step_id)
    except KeyError:
        pass
    else:
        raise RuntimeError("Class level receipt is already installed")
    chassis = apply_caster_chassis(entity, resolved)
    receipt = PaladinGrantReceipt(
        step_id=level.step_id,
        source_id=class_level_source(entity, level.step_id),
        chassis=chassis,
    )
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    stored = False
    try:
        entity.applied_class_levels = (*previous, level)
        reconcile_prepared_casting_source(entity, CharacterClass.PALADIN)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        n = level.resulting_class_level

        def resource(name, maximum, recharge):
            nonlocal receipt
            source = class_level_source(entity, level.step_id + "." + name)
            entity.action_economy.add_resource_contribution(
                name,
                source,
                maximum=maximum,
                recharge_type=recharge,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            receipt = replace(
                receipt,
                resource_contributions=(
                    *receipt.resource_contributions,
                    (name, source),
                ),
            )

        def condition(effect):
            nonlocal receipt
            result = entity.add_condition(effect)
            if result is None or result.canceled:
                raise RuntimeError("Paladin feature condition was rejected")
            receipt = replace(
                receipt, condition_uuids=(*receipt.condition_uuids, effect.uuid)
            )
            return effect

        def action(action_type, key, **parameters):
            nonlocal receipt
            identity = "action.class.paladin." + key
            template = action_type(
                source_entity_uuid=entity.uuid,
                template=True,
                uuid=class_level_source(entity, level.step_id + "." + identity),
                semantic_key=identity,
                behavior_binding=BehaviorBinding(
                    behavior_id=identity,
                    provided_by_id="class_feature.paladin." + key,
                    origin_root_id=CharacterClass.PALADIN.value,
                    runtime_owner_uuid=entity.uuid,
                ),
                **parameters,
            )
            try:
                entity.register_action(template)
            except BaseException:
                template.remove_from_register()
                raise
            receipt = replace(
                receipt, action_uuids=(*receipt.action_uuids, template.uuid)
            )

        if n == 1:
            resource("channel_oath", 1, RechargeType.SHORT_REST)
            resource("divine_sense", 1, RechargeType.SHORT_REST)
            root = condition(
                ClassFeatureLifetime(
                    name="Divine Sense Owner",
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                )
            )
            action(paladin.DivineSense, "divine_sense", feature_owner_uuid=root.uuid)
            action(paladin.LayOnHands, "lay_on_hands")
        if n in (1, 4, 10):
            resource("lay_on_hands", {1: 3, 4: 4, 10: 5}[n], RechargeType.LONG_REST)
        if n == 2:
            entitlement = class_level_source(entity, level.step_id + ".smite")
            smite_handlers = paladin.register_divine_smite(
                entity, entitlement_uuid=entitlement
            )
            selection = next(
                (
                    row
                    for row in entity.feature_toggle_selections
                    if row.feature_id == "class_feature.paladin.divine_smite"
                ),
                None,
            )
            if selection is not None:
                for handler in smite_handlers:
                    entity.set_handler_enabled_by_uuid(handler.uuid, selection.enabled)
            receipt = replace(receipt, smite_entitlement_uuid=entitlement)
            style = resolved.fighting_style_id
            binding = BehaviorBinding(
                behavior_id=style,
                provided_by_id=style,
                origin_root_id=CharacterClass.PALADIN.value,
                runtime_owner_uuid=entity.uuid,
            )
            suffix = style.rsplit(".", 1)[1]
            if suffix in ("defense", "dueling"):
                style_type = (
                    fighter.FightingStyleDefense
                    if suffix == "defense"
                    else fighter.FightingStyleDueling
                )
                condition(
                    style_type(
                        source_entity_uuid=entity.uuid,
                        target_entity_uuid=entity.uuid,
                        behavior_binding=binding,
                    )
                )
            else:
                identity = class_level_source(
                    entity, level.step_id + "." + style + ".handler"
                )
                if suffix == "great_weapon_fighting":
                    handler = EventHandler(
                        uuid=identity,
                        source_entity_uuid=entity.uuid,
                        name="Great Weapon Fighting",
                        semantic_key=style,
                        behavior_binding=binding,
                        player_toggleable=True,
                        trigger_conditions=[
                            Trigger(
                                event_type=EventType.DAMAGE_ROLL_RESULT,
                                event_phase=EventPhase.EFFECT,
                            )
                        ],
                        event_processor=fighter.great_weapon_fighting_processor,
                    )
                else:
                    handler = fighter.create_protection_handler(
                        entity.uuid, handler_uuid=identity
                    )
                    handler.behavior_binding = binding.model_copy(
                        update={
                            "behavior_id": "reaction.class_feature.fighter.protection"
                        }
                    )
                try:
                    entity.add_event_handler(handler)
                except BaseException:
                    handler.remove_from_register()
                    raise
                receipt = replace(
                    receipt, handler_uuids=(*receipt.handler_uuids, handler.uuid)
                )
        if n == 3:
            root = condition(
                ClassFeatureLifetime(
                    name="Devotion Channel Oath Owner",
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                )
            )
            action(
                paladin.TurnUnholy,
                "turn_unholy",
                feature_owner_uuid=root.uuid,
                casting_source_id=class_casting_source(entity, CharacterClass.PALADIN),
            )
            action(paladin.SacredWeapon, "sacred_weapon", feature_owner_uuid=root.uuid)
        if n in (3, 11):
            feature = "divine_health" if n == 3 else "improved_divine_smite"
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + ".handler." + feature),
                name=feature,
                source_entity_uuid=entity.uuid,
                semantic_key="class_feature.paladin." + feature,
                event_processor=paladin.divine_health
                if n == 3
                else paladin.improved_divine_smite,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.CONDITION_APPLICATION
                        if n == 3
                        else EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                        event_target_entity_uuid=entity.uuid if n == 3 else None,
                        event_source_entity_uuid=entity.uuid if n == 11 else None,
                    )
                ],
            )
            entity.add_event_handler(handler)
            receipt = replace(
                receipt, handler_uuids=(*receipt.handler_uuids, handler.uuid)
            )
        if n == 5:
            identity = class_level_source(entity, level.step_id + ".extra_attack")
            entity.action_economy.add_attack_multiplicity_grant(
                AttackMultiplicityGrant(
                    grant_id=identity,
                    provider_id="class_feature.paladin.extra_attack",
                    attacks_per_attack_action=2,
                    acquisition_ordinal=level.character_level,
                )
            )
            receipt = replace(receipt, attack_multiplicity_grant_ids=(identity,))
        if n in (6, 7, 10):
            kind = {6: "protection", 7: "devotion", 10: "courage"}[n]
            condition(
                paladin.PaladinAuraRoot(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name="Aura of " + kind.title() + " Owner",
                    aura_kind=kind,
                )
            )
        if n == 14:
            resource(
                "cleansing_touch",
                max(1, entity.ability_scores.charisma.modifier),
                RechargeType.LONG_REST,
            )
            condition(
                paladin.CleansingTouchCapacity(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    resource_source_uuid=class_level_source(
                        entity, level.step_id + ".cleansing_touch"
                    ),
                )
            )
            action(paladin.CleansingTouch, "cleansing_touch")
        if n == 15:
            condition(
                paladin.PurityOfSpirit(
                    source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
                )
            )
        if n == 20:
            resource("holy_nimbus", 1, RechargeType.LONG_REST)
            root = condition(
                ClassFeatureLifetime(
                    name="Holy Nimbus Owner",
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                )
            )
            action(paladin.HolyNimbus, "holy_nimbus", feature_owner_uuid=root.uuid)
        paladin.refresh_cleansing_capacity(entity)
        entity.store_character_grant_receipt(receipt)
        stored = True
        return receipt
    except BaseException:
        if stored:
            entity.remove_character_grant_receipt(level.step_id)
        if receipt.smite_entitlement_uuid is not None:
            paladin.unregister_divine_smite(entity, receipt.smite_entitlement_uuid)
        remove_class_feature_handles(entity, receipt)
        entity.prepared_spell_selections = previous_preparations
        entity.applied_class_levels = previous
        reconcile_prepared_casting_source(entity, CharacterClass.PALADIN)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        remove_caster_chassis(entity, chassis)
        raise


def remove_last_paladin_level(
    entity: Entity, *, parent_event=None
) -> AppliedClassLevel:
    if (
        not entity.applied_class_levels
        or entity.applied_class_levels[-1].class_id is not CharacterClass.PALADIN
    ):
        raise RuntimeError("Last level does not belong to Paladin")
    level = entity.applied_class_levels[-1]
    receipt = cast(PaladinGrantReceipt, entity.character_grant_receipt(level.step_id))
    validate_normal_spell_slots(entity)
    validate_prepared_casting_source(entity, CharacterClass.PALADIN)
    validate_caster_chassis(entity, receipt.chassis)
    validate_class_feature_handles(entity, receipt)
    prepared = prepare_class_feature_removals(entity, receipt, parent_event)
    previous_preparations = entity.prepared_spell_selections
    previous = entity.applied_class_levels
    entity.applied_class_levels = previous[:-1]
    try:
        reconcile_prepared_casting_source(entity, CharacterClass.PALADIN)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
    except BaseException:
        BaseBlock.cancel_owned_condition_removals(
            prepared, "Class source reconciliation failed"
        )
        entity.prepared_spell_selections = previous_preparations
        entity.applied_class_levels = previous
        reconcile_prepared_casting_source(entity, CharacterClass.PALADIN)
        reconcile_normal_spell_slots(entity)
        reconcile_prepared_spell_entitlements(entity)
        raise
    reconcile_prepared_spell_entitlements(entity)
    removals = remove_class_feature_handles(
        entity, receipt, parent_event, prepared=prepared, publish=False
    )
    if receipt.smite_entitlement_uuid is not None:
        paladin.unregister_divine_smite(entity, receipt.smite_entitlement_uuid)
    paladin.refresh_cleansing_capacity(entity)
    remove_caster_chassis(entity, receipt.chassis)
    entity.remove_character_grant_receipt(level.step_id)
    BaseBlock.publish_owned_condition_removals(removals)
    return level
