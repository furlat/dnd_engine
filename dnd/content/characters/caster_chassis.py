"""Native structural contributions reused by the three prepared class composers."""

from uuid import UUID, uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.blocks.saving_throws import SAVING_THROW_TO_ABILITY
from dnd.classes.feats import lucky_processor
from dnd.content.characters.class_definitions import (
    ResolvedPreparedClassLevel,
    prepared_class_definition,
)
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.base_block import BaseBlock, PreparedConditionRemovals
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity
from dnd.types.character_receipts import CasterChassisReceipt
from dnd.core.values import Channel, Kind, add_modifier, remove_modifier


def class_level_source(entity: Entity, identity: str) -> UUID:
    return uuid5(entity.uuid, f"dnd-engine:prepared-class:{identity}:v1")


def apply_caster_chassis(
    entity: Entity, resolved: ResolvedPreparedClassLevel
) -> CasterChassisReceipt:
    level = resolved.level
    definition = prepared_class_definition(level.class_id)
    for ability, amount in resolved.ability_increases:
        if entity.ability_scores.get_ability(ability).ability_score.score + amount > 20:
            raise ValueError(f"ASI would raise {ability} above20")
    hit_dice = []
    creatures = []
    skills = []
    saves = []
    modifiers = []
    features = []
    handlers = []
    resources = []

    def receipt():
        return CasterChassisReceipt(
            hit_die_uuids=tuple(hit_dice),
            creature_proficiency_source_ids=tuple(creatures),
            skill_proficiency_sources=tuple(skills),
            saving_throw_proficiency_sources=tuple(saves),
            ability_score_modifier_ids=tuple(modifiers),
            feature_sources=tuple(features),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
        )

    try:
        hit_die = HitDice.create(
            source_entity_uuid=entity.uuid,
            name=level.step_id,
            identity_uuid=class_level_source(entity, level.step_id + ".hit_die"),
            config=HitDiceConfig(
                hit_dice_value=definition.hit_die,
                hit_dice_count=1,
                mode="maximums" if level.character_level == 1 else "average",
                ignore_first_level=level.character_level != 1,
            ),
        )
        entity.health.add_hit_dice(hit_die)
        hit_dice.append(hit_die.uuid)
        if resolved.proficiencies:
            source = class_level_source(entity, level.step_id + ".proficiencies")
            creatures.append(source)
            for value in resolved.proficiencies:
                if value == "weapon.simple":
                    entity.creature_proficiencies.add_weapon_source(
                        source, WeaponProperty.SIMPLE
                    )
                elif value == "weapon.martial":
                    entity.creature_proficiencies.add_weapon_source(
                        source, WeaponProperty.MARTIAL
                    )
                elif value == "shield.shield":
                    entity.creature_proficiencies.add_shield_source(source)
                elif value.startswith("armor."):
                    entity.creature_proficiencies.add_armor_source(
                        source,
                        {
                            "armor.light": ArmorType.LIGHT,
                            "armor.medium": ArmorType.MEDIUM,
                            "armor.heavy": ArmorType.HEAVY,
                        }[value],
                    )
                else:
                    entity.creature_proficiencies.add_specific_weapon_source(
                        source, value
                    )
        for skill in resolved.skills:
            source = class_level_source(entity, level.step_id + ".skill." + skill)
            entity.skill_set.get_skill(skill).add_proficiency_source(
                source, ProficiencyMode.FULL
            )
            skills.append((skill, source))
        for ability in resolved.saving_throws:
            source = class_level_source(entity, level.step_id + ".save." + ability)
            value = entity.saving_throws.get_saving_throw(ability)
            value.add_proficiency_source(source, ProficiencyMode.FULL)
            saves.append((value.name, source))
        for ability, amount in resolved.ability_increases:
            identity = class_level_source(entity, level.step_id + ".asi." + ability)
            add_modifier(entity.ability_scores.get_ability(
                ability
            ).ability_score, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    uuid=identity,
                    name=level.step_id + " ASI",
                    value=amount,
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                ))
            modifiers.append((ability, identity))
        for feature in resolved.feature_ids:
            source = class_level_source(entity, level.step_id + ".feature." + feature)
            entity.add_feature_source(feature, source)
            features.append((feature, source))
        if resolved.feat_id == "feat.lucky":
            source = class_level_source(entity, level.step_id + ".lucky")
            entity.action_economy.add_resource_contribution(
                "luck_points",
                source,
                maximum=3,
                recharge_type=RechargeType.LONG_REST,
                capacity_policy=ResourceCapacityPolicy.SUM,
            )
            resources.append(("luck_points", source))
            handler = EventHandler(
                uuid=class_level_source(entity, level.step_id + ".lucky.handler"),
                name="Lucky",
                semantic_key="feat.lucky",
                source_entity_uuid=entity.uuid,
                player_toggleable=True,
                behavior_binding=BehaviorBinding(
                    behavior_id="feat.lucky",
                    provided_by_id="feat.lucky",
                    origin_root_id=level.class_id.value,
                    runtime_owner_uuid=entity.uuid,
                ),
                trigger_conditions=[
                    Trigger(
                        event_type=kind,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity.uuid,
                    )
                    for kind in (
                        EventType.ATTACK_D20_ROLL_RESULT,
                        EventType.SAVE_D20_ROLL_RESULT,
                        EventType.CHECK_D20_ROLL_RESULT,
                    )
                ],
                event_processor=lucky_processor,
            )
            entity.add_event_handler(handler)
            handlers.append(handler.uuid)
        return receipt()
    except BaseException:
        remove_caster_chassis(entity, receipt())
        raise


def remove_caster_chassis(entity: Entity, receipt: CasterChassisReceipt) -> None:
    for identity in receipt.handler_uuids:
        handler = entity.event_handlers[identity]
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for name, source in receipt.resource_contributions:
        entity.action_economy.remove_resource_contribution(name, source)
    for feature, source in receipt.feature_sources:
        entity.remove_feature_source(feature, source)
    for ability, identity in receipt.ability_score_modifier_ids:
        remove_modifier(entity.ability_scores.get_ability(
            ability
        ).ability_score, identity, Channel.SELF_STATIC, Kind.VALUE)
        NumericalModifier.unregister(identity)
    for name, source in receipt.saving_throw_proficiency_sources:
        entity.saving_throws.get_saving_throw(
            SAVING_THROW_TO_ABILITY[name]
        ).remove_proficiency_source(source)
    for name, source in receipt.skill_proficiency_sources:
        entity.skill_set.get_skill(name).remove_proficiency_source(source)
    for source in receipt.creature_proficiency_source_ids:
        entity.creature_proficiencies.remove_source(source)
    for identity in receipt.hit_die_uuids:
        entity.health.remove_hit_dice_by_uuid(identity)


def validate_caster_chassis(entity: Entity, receipt: CasterChassisReceipt) -> None:
    """Reject lost native ownership before removing any structural contribution."""
    queue_handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for identity in receipt.handler_uuids:
        handler = entity.event_handlers.get(identity)
        if handler is None or queue_handlers.get(identity) is not handler:
            raise RuntimeError("Class event handler ownership changed")
    for name, source in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(name)
        if resource is None or str(source) not in resource.capacity_contributions:
            raise RuntimeError("Class resource ownership changed")
    for feature, source in receipt.feature_sources:
        if source not in entity.feature_sources.get(feature, set()):
            raise RuntimeError("Class feature ownership changed")
    for ability, identity in receipt.ability_score_modifier_ids:
        value = entity.ability_scores.get_ability(
            ability
        ).modifier_of(ability_score, Channel.SELF_STATIC, Kind.VALUE, identity)
        if value is None or NumericalModifier.get(identity) is not value:
            raise RuntimeError("Class ability modifier ownership changed")
    for name, source in receipt.saving_throw_proficiency_sources:
        if (
            source
            not in entity.saving_throws.get_saving_throw(
                SAVING_THROW_TO_ABILITY[name]
            ).proficiency_sources.sources
        ):
            raise RuntimeError("Class saving throw ownership changed")
    for name, source in receipt.skill_proficiency_sources:
        if source not in entity.skill_set.get_skill(name).proficiency_sources.sources:
            raise RuntimeError("Class skill ownership changed")
    proficiencies = entity.creature_proficiencies
    for source in receipt.creature_proficiency_source_ids:
        if not any(
            source in owners.sources
            for owners in (
                *proficiencies.armor_sources.values(),
                *proficiencies.weapon_sources.values(),
                *proficiencies.specific_weapon_sources.values(),
                proficiencies.shield_sources,
            )
        ):
            raise RuntimeError("Class creature proficiency ownership changed")
    hit_dice = {die.uuid: die for die in entity.health.hit_dices}
    for identity in receipt.hit_die_uuids:
        die = hit_dice.get(identity)
        if die is None or die.source_entity_uuid != entity.uuid:
            raise RuntimeError("Class hit die ownership changed")


def validate_class_feature_handles(entity, receipt) -> None:
    actions = {action.uuid for action in entity.registered_actions}
    if not set(receipt.action_uuids) <= actions:
        raise RuntimeError("Class feature action ownership changed")
    handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for identity in receipt.handler_uuids:
        if (
            identity not in entity.event_handlers
            or handlers.get(identity) is not entity.event_handlers[identity]
        ):
            raise RuntimeError("Class feature handler ownership changed")
    for name, source in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(name)
        if resource is None or str(source) not in resource.capacity_contributions:
            raise RuntimeError("Class feature resource ownership changed")
    for identity in receipt.condition_uuids:
        if identity not in entity.active_conditions_by_uuid:
            raise RuntimeError("Class feature condition ownership changed")
    grants = {
        row.grant_id for row in entity.action_economy.get_attack_multiplicity_grants()
    }
    if not set(receipt.attack_multiplicity_grant_ids) <= grants:
        raise RuntimeError("Class attack grant ownership changed")


def prepare_class_feature_removals(entity, receipt, parent_event=None):
    prepared = PreparedConditionRemovals([])
    visited = set()
    try:
        with BaseBlock.condition_removal_scope():
            for identity in receipt.condition_uuids:
                condition = entity.active_conditions_by_uuid[identity]
                canceled = BaseBlock._prepare_condition_removal_tree(
                    condition,
                    condition_owner=entity,
                    expire=False,
                    parent_event=parent_event,
                    prepared=prepared.entries,
                    visited=visited,
                )
                if canceled is not None:
                    raise RuntimeError("Class feature condition removal rejected")
    except BaseException:
        BaseBlock.cancel_owned_condition_removals(
            prepared, "Class level removal was rejected"
        )
        raise
    return prepared


def remove_class_feature_handles(
    entity, receipt, parent_event=None, *, prepared=None, publish=True
) -> None:
    removals = (
        prepared
        if prepared is not None
        else prepare_class_feature_removals(entity, receipt, parent_event)
    )
    with BaseBlock.condition_removal_scope():
        if not BaseBlock.validate_prepared_condition_removals(removals.entries):
            BaseBlock.cancel_owned_condition_removals(
                removals, "Class feature roots changed"
            )
            raise RuntimeError("Class feature roots changed")
        BaseBlock.commit_owned_condition_removals(removals)
    for identity in receipt.handler_uuids:
        handler = entity.event_handlers[identity]
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for identity in receipt.action_uuids:
        entity.unregister_action_by_uuid(identity)
    for name, source in receipt.resource_contributions:
        entity.action_economy.remove_resource_contribution(name, source)
    for identity in receipt.attack_multiplicity_grant_ids:
        entity.action_economy.remove_attack_multiplicity_grant(identity)

    if publish:
        BaseBlock.publish_owned_condition_removals(removals)
    return removals
