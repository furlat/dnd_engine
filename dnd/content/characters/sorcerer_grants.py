"""Direct Sorcerer/Draconic Bloodline component grants and exact cleanup."""

from typing import cast
from uuid import UUID, uuid5

from dnd.actions import SpellAction
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.classes import feats, sorcerer
from dnd.content.characters.class_definitions import (
    ResolvedSorcererLevel,
    SORCERER_SPELL_RANKS,
    resolve_sorcerer_level,
)
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.core.progression import CasterProgression, FULL_CASTER_SPELL_SLOTS
from dnd.entity import Entity
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_SPECS
from dnd.spells.reaction_spell_content import LEARNED_REACTION_SPELL_SPECS
from dnd.types.abilities import AbilityName, SavingThrowName
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    RitualPreparationPolicy,
)
from dnd.types.character_receipts import SorcererGrantReceipt


_SORCERY_POINTS = "class_feature.sorcerer.sorcery_points"
_DRACONIC_RESILIENCE = "class_feature.sorcerer.draconic_resilience"
_ELEMENTAL_AFFINITY = "class_feature.sorcerer.elemental_affinity"
_DRAGON_WINGS = "class_feature.sorcerer.dragon_wings"
_DRACONIC_PRESENCE = "class_feature.sorcerer.draconic_presence"
_SORCEROUS_RESTORATION = "class_feature.sorcerer.sorcerous_restoration"
_METAMAGIC_ACTION_BY_ID = {
    "class_feature.sorcerer.metamagic.distant_spell": (
        sorcerer.DistantSpell,
        "action.class.sorcerer.distant_spell",
    ),
    "class_feature.sorcerer.metamagic.quickened_spell": (
        sorcerer.QuickenedSpell,
        "action.class.sorcerer.quickened_spell",
    ),
    "class_feature.sorcerer.metamagic.twinned_spell": (
        sorcerer.TwinnedSpell,
        "action.class.sorcerer.twinned_spell",
    ),
}
_METAMAGIC_ACTION_IDS = frozenset(
    action_id for _, action_id in _METAMAGIC_ACTION_BY_ID.values()
)
_SPELL_TYPE_BY_ID = {
    spec.content_id: spec.spell_type
    for spec in SPELL_CONTENT_IDENTITY_SPECS
    if spec.content_id in SORCERER_SPELL_RANKS
}
_REACTION_SPEC_BY_ID = {
    spec.declaration.ref.content_id: spec
    for spec in LEARNED_REACTION_SPELL_SPECS
    if spec.declaration.ref.content_id in SORCERER_SPELL_RANKS
}
if set(SORCERER_SPELL_RANKS) != set(_SPELL_TYPE_BY_ID) | set(
    _REACTION_SPEC_BY_ID
):
    raise RuntimeError("Sorcerer spell table has no exact runtime surface")


def _source(entity: Entity, identity: str) -> UUID:
    return uuid5(entity.uuid, f"dnd-engine:sorcerer:v1:{identity}")


def _spellcasting_source(entity: Entity) -> UUID:
    return _source(entity, "spellcasting")


def _binding(
    entity: Entity,
    *,
    behavior_id: str,
    provided_by_id: str,
    origin_root_id: str = CharacterClass.SORCERER.value,
) -> BehaviorBinding:
    return BehaviorBinding(
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=origin_root_id,
        runtime_owner_uuid=entity.uuid,
    )


def _register_action(entity: Entity, actions: list[UUID], action) -> None:
    try:
        entity.register_action(action)
    except BaseException:
        action.remove_from_register()
        raise
    actions.append(action.uuid)


def _register_handler(
    entity: Entity,
    handlers: list[UUID],
    handler: EventHandler,
) -> None:
    try:
        entity.add_event_handler(handler)
    except BaseException:
        handler.remove_from_register()
        raise
    handlers.append(handler.uuid)


def _registered_action(entity: Entity, action_uuid: UUID):
    action = next(
        (
            candidate
            for candidate in entity.registered_actions
            if candidate.uuid == action_uuid
        ),
        None,
    )
    if action is None:
        raise RuntimeError(f"Sorcerer action {action_uuid} is missing")
    return action


def _set_spellcasting_source(entity: Entity, class_level: int) -> None:
    source_id = _spellcasting_source(entity)
    entity.spellcasting.remove_source(source_id)
    entity.spellcasting.add_source(
        source_id,
        "charisma",
        provider_id=CharacterClass.SORCERER.value,
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=class_level,
        maximum_spell_rank=max(FULL_CASTER_SPELL_SLOTS[class_level], default=0),
        ritual_policy=RitualPreparationPolicy.NONE,
    )


def _register_spell_action(
    entity: Entity,
    actions: list[UUID],
    *,
    spell_id: str,
    caster_level: int,
    action_uuid: UUID | None = None,
    action_index: int | None = None,
) -> UUID:
    spell_type = _SPELL_TYPE_BY_ID[spell_id]
    if action_uuid is None:
        action = spell_type(
            uuid=_source(entity, f"spell_action.{spell_id}"),
            source_entity_uuid=entity.uuid,
            caster_level=caster_level,
            spellcasting_source_id=_spellcasting_source(entity),
            template=True,
            semantic_key=spell_id,
            behavior_binding=_binding(
                entity,
                behavior_id=spell_id,
                provided_by_id=spell_id,
                origin_root_id=spell_id,
            ),
        )
    else:
        action = spell_type(
            uuid=action_uuid,
            source_entity_uuid=entity.uuid,
            caster_level=caster_level,
            spellcasting_source_id=_spellcasting_source(entity),
            template=True,
            semantic_key=spell_id,
            behavior_binding=_binding(
                entity,
                behavior_id=spell_id,
                provided_by_id=spell_id,
                origin_root_id=spell_id,
            ),
        )
    _register_action(entity, actions, action)
    if action_index is not None:
        if action_index > len(entity.registered_actions) - 1:
            raise RuntimeError("restored Sorcerer spell action index is invalid")
        registered = entity.registered_actions.pop()
        entity.registered_actions.insert(action_index, registered)
    return action.uuid


def _learn_reaction_spell(
    entity: Entity,
    learned: list[tuple[str, UUID, UUID]],
    spell_id: str,
    *,
    handler_uuid: UUID | None = None,
) -> None:
    source_id = _spellcasting_source(entity)
    live_handler_uuid = entity.spellcasting.learned_reaction_spell_handler_uuid(
        spell_id,
    )
    created_handler: EventHandler | None = None
    if live_handler_uuid is None:
        spec = _REACTION_SPEC_BY_ID[spell_id]
        created_handler = spec.handler_factory(entity.uuid)
        if handler_uuid is not None:
            created_handler.remove_from_register()
            created_handler.uuid = handler_uuid
            created_handler.add_to_register()
        created_handler.behavior_binding = _binding(
            entity,
            behavior_id=f"reaction.{spell_id}",
            provided_by_id=spell_id,
            origin_root_id=spell_id,
        )
        try:
            entity.add_event_handler(created_handler)
        except BaseException:
            created_handler.remove_from_register()
            raise
        live_handler_uuid = created_handler.uuid
    elif handler_uuid is not None and live_handler_uuid != handler_uuid:
        raise RuntimeError("restored reaction spell handler identity changed")
    elif live_handler_uuid not in entity.event_handlers:
        raise RuntimeError("learned reaction spell handler is missing")
    try:
        entity.spellcasting.add_learned_reaction_spell_source(
            spell_id=spell_id,
            source_id=source_id,
            handler_uuid=live_handler_uuid,
        )
    except BaseException:
        if created_handler is not None:
            entity.remove_event_handler(created_handler)
            created_handler.remove_from_register()
        raise
    learned.append((spell_id, source_id, live_handler_uuid))


def _remove_reaction_spell(
    entity: Entity,
    row: tuple[str, UUID, UUID],
) -> None:
    spell_id, source_id, handler_uuid = row
    remove_handler = entity.spellcasting.remove_learned_reaction_spell_source(
        spell_id=spell_id,
        source_id=source_id,
        handler_uuid=handler_uuid,
    )
    if not remove_handler:
        return
    handler = entity.event_handlers.get(handler_uuid)
    if handler is None:
        raise RuntimeError("Sorcerer reaction spell handler is missing")
    entity.remove_event_handler(handler)
    handler.remove_from_register()


def _learn_spell(
    entity: Entity,
    actions: list[UUID],
    learned: list[tuple[str, UUID, UUID]],
    spell_id: str,
    class_level: int,
) -> None:
    if spell_id in _REACTION_SPEC_BY_ID:
        _learn_reaction_spell(
            entity,
            learned,
            spell_id,
            handler_uuid=_source(entity, f"reaction_spell.{spell_id}.handler"),
        )
        return
    _register_spell_action(
        entity,
        actions,
        spell_id=spell_id,
        caster_level=class_level,
    )


def _apply_proficiencies(
    entity: Entity,
    resolved: ResolvedSorcererLevel,
    creature_sources: list[UUID],
    skills: list[tuple[str, UUID]],
    saves: list[tuple[SavingThrowName, UUID]],
) -> None:
    if resolved.proficiencies:
        source_id = _source(entity, f"{resolved.level.step_id}.proficiencies")
        for proficiency in resolved.proficiencies:
            entity.creature_proficiencies.add_specific_weapon_source(
                source_id,
                proficiency,
            )
        creature_sources.append(source_id)
    for skill in resolved.skills:
        source_id = _source(entity, f"{resolved.level.step_id}.skill.{skill}")
        entity.skill_set.get_skill(skill).add_proficiency_source(
            source_id,
            ProficiencyMode.FULL,
        )
        skills.append((skill, source_id))
    for ability in resolved.saving_throws:
        source_id = _source(entity, f"{resolved.level.step_id}.save.{ability}")
        entity.saving_throws.get_saving_throw(ability).add_proficiency_source(
            source_id,
            ProficiencyMode.FULL,
        )
        saves.append((f"{ability}_saving_throw", source_id))


def _apply_lucky(
    entity: Entity,
    resolved: ResolvedSorcererLevel,
    resources: list[tuple[str, UUID]],
    handlers: list[UUID],
) -> None:
    if resolved.feat_id != "feat.lucky":
        return
    source_id = _source(entity, f"{resolved.level.step_id}.feat.lucky")
    entity.action_economy.add_resource_contribution(
        "luck_points",
        source_id,
        maximum=3,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    resources.append(("luck_points", source_id))
    _register_handler(
        entity,
        handlers,
        EventHandler(
            uuid=_source(
                entity,
                f"{resolved.level.step_id}.feat.lucky.handler",
            ),
            name="Lucky",
            semantic_key="feat.lucky",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=event_type,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=entity.uuid,
                )
                for event_type in (
                    EventType.ATTACK_D20_ROLL_RESULT,
                    EventType.SAVE_D20_ROLL_RESULT,
                    EventType.CHECK_D20_ROLL_RESULT,
                )
            ],
            event_processor=feats.lucky_processor,
            player_toggleable=True,
            behavior_binding=_binding(
                entity,
                behavior_id="feat.lucky",
                provided_by_id="feat.lucky",
            ),
        ),
    )


def _register_feature_action(
    entity: Entity,
    actions: list[UUID],
    action,
    *,
    behavior_id: str,
    provided_by_id: str,
) -> UUID:
    action.semantic_key = behavior_id
    action.behavior_binding = _binding(
        entity,
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
    )
    _register_action(entity, actions, action)
    return action.uuid


def _apply_level_features(
    entity: Entity,
    resolved: ResolvedSorcererLevel,
    *,
    actions: list[UUID],
    resources: list[tuple[str, UUID]],
    recoveries: list[tuple[str, UUID]],
    affinities: list[UUID],
    armor_formulas: list[UUID],
    metamagic_root_owners: list[UUID],
    elemental_affinity_root_owners: list[UUID],
    dragon_wings_root_owners: list[UUID],
    draconic_presence_root_owners: list[UUID],
) -> None:
    level = resolved.level.resulting_class_level
    step_id = resolved.level.step_id
    features = set(resolved.feature_ids)

    if level >= 2:
        source_id = _source(entity, f"{step_id}.sorcery_points")
        entity.action_economy.add_resource_contribution(
            "sorcery_points",
            source_id,
            maximum=level,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append(("sorcery_points", source_id))

    newly_convertible_rank = {
        2: 1,
        3: 2,
        5: 3,
        7: 4,
        9: 5,
    }.get(level)
    if newly_convertible_rank is not None:
        for action_type, behavior_id in (
            (
                sorcerer.ConvertSlotToSP,
                "action.class.sorcerer.convert_slot_to_sorcery_points",
            ),
            (
                sorcerer.ConvertSPToSlot,
                "action.class.sorcerer.convert_sorcery_points_to_slot",
            ),
        ):
            _register_feature_action(
                entity,
                actions,
                action_type(
                    uuid=_source(
                        entity,
                        f"{step_id}.{behavior_id}.{newly_convertible_rank}.action",
                    ),
                    source_entity_uuid=entity.uuid,
                    slot_level=newly_convertible_rank,
                    template=True,
                ),
                behavior_id=behavior_id,
                provided_by_id=_SORCERY_POINTS,
            )

    for metamagic_id in resolved.metamagic_ids:
        action_type, behavior_id = _METAMAGIC_ACTION_BY_ID[metamagic_id]
        metamagic_root_owners.append(_register_feature_action(
            entity,
            actions,
            action_type(
                uuid=_source(entity, f"{step_id}.{behavior_id}.action"),
                source_entity_uuid=entity.uuid,
                template=True,
            ),
            behavior_id=behavior_id,
            provided_by_id=metamagic_id,
        ))

    if _DRACONIC_RESILIENCE in features:
        formula_id = _source(entity, f"{step_id}.{_DRACONIC_RESILIENCE}.ac")
        entity.equipment.add_armor_class_formula_candidate(
            ArmorClassFormulaCandidate(
                source_id=formula_id,
                base_ac=13,
                ability_names=("dexterity",),
                requires_unarmored=True,
                allows_shield=True,
            ),
        )
        armor_formulas.append(formula_id)

    if _ELEMENTAL_AFFINITY in features:
        if resolved.ancestry_damage_type is None:
            raise RuntimeError("Elemental Affinity has no Draconic ancestry")
        affinity_id = _source(entity, f"{step_id}.{_ELEMENTAL_AFFINITY}")
        damage_type = DamageType[resolved.ancestry_damage_type.upper()]
        entity.spellcasting.add_spell_damage_affinity_contribution(
            affinity_id,
            damage_type=damage_type,
            ability_name="charisma",
        )
        affinities.append(affinity_id)
        elemental_affinity_root_owners.append(_register_feature_action(
            entity,
            actions,
            sorcerer.ElementalAffinityResistanceAction(
                uuid=_source(
                    entity,
                    f"{step_id}.{_ELEMENTAL_AFFINITY}.action",
                ),
                source_entity_uuid=entity.uuid,
                damage_type=damage_type,
                template=True,
            ),
            behavior_id="action.class.sorcerer.elemental_affinity.resistance",
            provided_by_id=_ELEMENTAL_AFFINITY,
        ))

    if _DRAGON_WINGS in features:
        for action, behavior_id in (
            (
                sorcerer.DragonWings(
                    uuid=_source(entity, f"{step_id}.{_DRAGON_WINGS}.action"),
                    source_entity_uuid=entity.uuid,
                    template=True,
                ),
                "action.class.sorcerer.dragon_wings.toggle",
            ),
            (
                sorcerer.Fly(
                    uuid=_source(
                        entity,
                        f"{step_id}.{_DRAGON_WINGS}.fly_action",
                    ),
                    source_entity_uuid=entity.uuid,
                    template=True,
                ),
                "action.class.sorcerer.dragon_wings.fly",
            ),
        ):
            action_uuid = _register_feature_action(
                entity,
                actions,
                action,
                behavior_id=behavior_id,
                provided_by_id=_DRAGON_WINGS,
            )
            if behavior_id == "action.class.sorcerer.dragon_wings.toggle":
                dragon_wings_root_owners.append(action_uuid)

    if _DRACONIC_PRESENCE in features:
        for mode in ("awe", "fear"):
            draconic_presence_root_owners.append(_register_feature_action(
                entity,
                actions,
                sorcerer.DraconicPresence(
                    uuid=_source(
                        entity,
                        f"{step_id}.{_DRACONIC_PRESENCE}.{mode}.action",
                    ),
                    source_entity_uuid=entity.uuid,
                    mode=mode,
                    template=True,
                ),
                behavior_id="action.class.sorcerer.draconic_presence",
                provided_by_id=_DRACONIC_PRESENCE,
            ))

    if _SORCEROUS_RESTORATION in features:
        source_id = _source(entity, f"{step_id}.{_SORCEROUS_RESTORATION}")
        entity.action_economy.add_resource_recovery_contribution(
            "sorcery_points",
            source_id,
            trigger=RechargeType.SHORT_REST,
            amount=4,
        )
        recoveries.append(("sorcery_points", source_id))


def _metamagic_root(entity: Entity, action_uuid: UUID) -> UUID | None:
    return cast(
        sorcerer.QuickenedSpell,
        _registered_action(entity, action_uuid),
    ).active_metamagic_condition_uuid


def _elemental_affinity_root(entity: Entity, action_uuid: UUID) -> UUID | None:
    return cast(
        sorcerer.ElementalAffinityResistanceAction,
        _registered_action(entity, action_uuid),
    ).active_resistance_condition_uuid


def _dragon_wings_root(entity: Entity, action_uuid: UUID) -> UUID | None:
    return cast(
        sorcerer.DragonWings,
        _registered_action(entity, action_uuid),
    ).active_wings_condition_uuid


def _draconic_presence_roots(
    entity: Entity,
    action_uuid: UUID,
) -> tuple[tuple[BaseBlock, UUID], ...]:
    action = cast(
        sorcerer.DraconicPresence,
        _registered_action(entity, action_uuid),
    )
    rows: list[tuple[BaseBlock, UUID]] = []
    if action.active_concentrating_condition_uuid is not None:
        rows.append((entity, action.active_concentrating_condition_uuid))
    for target_uuid, condition_uuid in action.immunity_condition_uuids.items():
        target = Entity.get(target_uuid)
        if target is None:
            raise RuntimeError("Draconic Presence immunity target is missing")
        rows.append((target, condition_uuid))
    return tuple(rows)


def _owned_condition_rows(
    entity: Entity,
    receipt: SorcererGrantReceipt,
) -> tuple[tuple[BaseBlock, UUID], ...]:
    rows: list[tuple[BaseBlock, UUID]] = []
    for action_uuid in receipt.metamagic_root_owner_action_uuids:
        root_uuid = _metamagic_root(entity, action_uuid)
        if root_uuid is not None:
            rows.append((entity, root_uuid))
    for action_uuid in receipt.elemental_affinity_root_owner_action_uuids:
        root_uuid = _elemental_affinity_root(entity, action_uuid)
        if root_uuid is not None:
            rows.append((entity, root_uuid))
    for action_uuid in receipt.dragon_wings_root_owner_action_uuids:
        root_uuid = _dragon_wings_root(entity, action_uuid)
        if root_uuid is not None:
            rows.append((entity, root_uuid))
    for action_uuid in receipt.draconic_presence_root_owner_action_uuids:
        rows.extend(_draconic_presence_roots(entity, action_uuid))
    return tuple(rows)


def _remove_owned_condition_rows(
    entity: Entity,
    receipt: SorcererGrantReceipt,
    parent_event: Event | None,
) -> None:
    prepared = []
    visited: set[UUID] = set()
    for owner, condition_uuid in _owned_condition_rows(entity, receipt):
        condition = owner.active_conditions_by_uuid.get(condition_uuid)
        if condition is None:
            raise RuntimeError("Sorcerer action lost its exact active root")
        canceled = BaseBlock._prepare_condition_removal_tree(
            condition,
            condition_owner=owner,
            expire=False,
            parent_event=parent_event,
            prepared=prepared,
            visited=visited,
        )
        if canceled is not None:
            BaseBlock._cancel_prepared_condition_removals(prepared, canceled)
            raise RuntimeError("Sorcerer active-root removal was canceled")
    BaseBlock._commit_prepared_condition_removals(prepared)


def _restore_replaced_spell(
    entity: Entity,
    receipt: SorcererGrantReceipt,
    caster_level: int,
) -> None:
    if receipt.replaced_spell_id is None:
        return
    if receipt.replaced_reaction_spell_source is not None:
        spell_id, source_id, handler_uuid = (
            receipt.replaced_reaction_spell_source
        )
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None:
            raise RuntimeError("restored Sorcerer reaction handler is missing")
        entity.spellcasting.add_learned_reaction_spell_source(
            spell_id=spell_id,
            source_id=source_id,
            handler_uuid=handler_uuid,
        )
        handler.enabled = cast(
            bool,
            receipt.replaced_reaction_spell_handler_was_enabled,
        )
        return
    if (
        receipt.replaced_spell_action_uuid is None
        or receipt.replaced_spell_action_index is None
    ):
        raise RuntimeError("Sorcerer replacement receipt is incomplete")
    restored_actions: list[UUID] = []
    _register_spell_action(
        entity,
        restored_actions,
        spell_id=receipt.replaced_spell_id,
        caster_level=caster_level,
        action_uuid=receipt.replaced_spell_action_uuid,
        action_index=receipt.replaced_spell_action_index,
    )


def _sorcerer_creature_source_is_owned(entity: Entity, source_id: UUID) -> bool:
    owner = entity.creature_proficiencies
    return any(
        source_id in sources.sources
        for sources in (
            owner.shield_sources,
            *owner.weapon_sources.values(),
            *owner.specific_weapon_sources.values(),
            *owner.armor_sources.values(),
            *owner.language_sources.values(),
            *owner.tool_sources.values(),
        )
    )


def _validate_sorcerer_receipt_ownership(
    entity: Entity,
    receipt: SorcererGrantReceipt,
    *,
    require_normal_slot: bool,
) -> None:
    """Fail before mutation when one Sorcerer handle changed owner."""
    actions = {action.uuid: action for action in entity.registered_actions}
    for action_uuid in receipt.action_uuids:
        if action_uuid not in actions:
            raise RuntimeError("Sorcerer action template is missing")
    for action_uuid in receipt.metamagic_root_owner_action_uuids:
        action = actions.get(action_uuid)
        expected_binding = next(
            (
                _binding(
                    entity,
                    behavior_id=behavior_id,
                    provided_by_id=metamagic_id,
                )
                for metamagic_id, (_action_type, behavior_id)
                in _METAMAGIC_ACTION_BY_ID.items()
                if action_uuid == _source(
                    entity,
                    f"{receipt.step_id}.{behavior_id}.action",
                )
            ),
            None,
        )
        if (
            action is None
            or expected_binding is None
            or action.behavior_binding != expected_binding
        ):
            raise RuntimeError("Sorcerer metamagic root ownership changed")
    for action_uuid in receipt.elemental_affinity_root_owner_action_uuids:
        action = actions.get(action_uuid)
        if action is None or action.behavior_binding != _binding(
            entity,
            behavior_id="action.class.sorcerer.elemental_affinity.resistance",
            provided_by_id=_ELEMENTAL_AFFINITY,
        ):
            raise RuntimeError("Sorcerer Elemental Affinity root ownership changed")
    for action_uuid in receipt.dragon_wings_root_owner_action_uuids:
        action = actions.get(action_uuid)
        if action is None or action.behavior_binding != _binding(
            entity,
            behavior_id="action.class.sorcerer.dragon_wings.toggle",
            provided_by_id=_DRAGON_WINGS,
        ):
            raise RuntimeError("Sorcerer Dragon Wings root ownership changed")
    for action_uuid in receipt.draconic_presence_root_owner_action_uuids:
        action = actions.get(action_uuid)
        expected_mode = next(
            (
                mode
                for mode in ("awe", "fear")
                if action_uuid == _source(
                    entity,
                    f"{receipt.step_id}.{_DRACONIC_PRESENCE}.{mode}.action",
                )
            ),
            None,
        )
        if action is None or expected_mode is None:
            raise RuntimeError("Sorcerer Draconic Presence root ownership changed")
        presence = cast(sorcerer.DraconicPresence, action)
        if (
            presence.behavior_binding != _binding(
                entity,
                behavior_id="action.class.sorcerer.draconic_presence",
                provided_by_id=_DRACONIC_PRESENCE,
            )
            or presence.mode != expected_mode
        ):
            raise RuntimeError("Sorcerer Draconic Presence root ownership changed")
    for owner, condition_uuid in _owned_condition_rows(entity, receipt):
        if condition_uuid not in owner.active_conditions_by_uuid:
            raise RuntimeError("Sorcerer action lost its exact active root")
    queue_handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for handler_uuid in receipt.handler_uuids:
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("Sorcerer event handler ownership changed")
    for spell_id, source_id, handler_uuid in receipt.learned_reaction_spell_sources:
        ownership = entity.spellcasting.learned_reaction_spell_handlers.get(spell_id)
        if (
            ownership is None
            or ownership.handler_uuid != handler_uuid
            or source_id not in ownership.sources
        ):
            raise RuntimeError("Sorcerer reaction-spell ownership changed")
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("Sorcerer reaction handler ownership changed")
    for resource_name, source_id in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(resource_name)
        if resource is None or str(source_id) not in resource.capacity_contributions:
            raise RuntimeError("Sorcerer resource contribution ownership changed")
    for resource_name, source_id in receipt.resource_recovery_contributions:
        resource = entity.action_economy.resources.get(resource_name)
        if resource is None or str(source_id) not in resource.recovery_contributions:
            raise RuntimeError("Sorcerer recovery contribution ownership changed")
    for source_id in receipt.spell_affinity_contribution_ids:
        if source_id not in entity.spellcasting.spell_damage_affinity_contributions:
            raise RuntimeError("Sorcerer spell affinity ownership changed")
    for source_id in receipt.armor_class_formula_ids:
        if source_id not in entity.equipment.armor_class_formula_candidates:
            raise RuntimeError("Sorcerer armor formula ownership changed")
    for modifier_id in receipt.maximum_hit_point_modifier_ids:
        modifiers = entity.health.max_hit_points_bonus.self_static.value_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
            raise RuntimeError("Sorcerer hit-point modifier ownership changed")
    for ability, modifier_id in receipt.ability_score_modifier_ids:
        modifiers = entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.value_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
            raise RuntimeError("Sorcerer ability modifier ownership changed")
    for feature_id, source_id in receipt.feature_sources:
        if source_id not in entity.feature_sources.get(feature_id, set()):
            raise RuntimeError("Sorcerer feature source ownership changed")
    for source_id in receipt.creature_proficiency_source_ids:
        if not _sorcerer_creature_source_is_owned(entity, source_id):
            raise RuntimeError("Sorcerer creature proficiency ownership changed")
    for saving_throw, source_id in receipt.saving_throw_proficiency_sources:
        if source_id not in entity.saving_throws.get_saving_throw(
            saving_throw.removesuffix("_saving_throw"),
        ).proficiency_sources.sources:
            raise RuntimeError("Sorcerer saving-throw source ownership changed")
    for skill, source_id in receipt.skill_proficiency_sources:
        if source_id not in entity.skill_set.get_skill(
            skill,
        ).proficiency_sources.sources:
            raise RuntimeError("Sorcerer skill source ownership changed")
    hit_dice = {hit_die.uuid: hit_die for hit_die in entity.health.hit_dices}
    for hit_die_uuid in receipt.hit_die_uuids:
        hit_die = hit_dice.get(hit_die_uuid)
        if hit_die is None or hit_die.source_entity_uuid != entity.uuid:
            raise RuntimeError("Sorcerer hit-die ownership changed")
    for source_id in receipt.spell_source_ids:
        if source_id not in entity.spellcasting.sources:
            raise RuntimeError("Sorcerer spell source ownership changed")
    if require_normal_slot:
        if receipt.normal_spell_slot_capacity_ids != (
            entity.action_economy.get_normal_spell_slot_capacity_source(),
        ):
            raise RuntimeError("Sorcerer spell-slot capacity ownership changed")
    if receipt.replaced_spell_action_uuid is not None:
        if receipt.replaced_spell_action_uuid in actions:
            raise RuntimeError("replaced Sorcerer spell identity is unexpectedly live")
        if cast(int, receipt.replaced_spell_action_index) > len(actions):
            raise RuntimeError("replaced Sorcerer spell action index is invalid")
    if receipt.replaced_reaction_spell_source is not None:
        spell_id, source_id, handler_uuid = receipt.replaced_reaction_spell_source
        ownership = entity.spellcasting.learned_reaction_spell_handlers.get(spell_id)
        if ownership is not None and source_id in ownership.sources:
            raise RuntimeError("replaced Sorcerer reaction source is unexpectedly live")
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("replaced Sorcerer reaction handler is missing")


def _remove_sorcerer_receipt(
    entity: Entity,
    receipt: SorcererGrantReceipt,
    *,
    restore_replacement: bool,
    restored_caster_level: int,
) -> None:
    _validate_sorcerer_receipt_ownership(
        entity,
        receipt,
        require_normal_slot=False,
    )
    if _owned_condition_rows(entity, receipt):
        raise RuntimeError("Sorcerer receipt cleanup still has active child state")
    for row in reversed(receipt.learned_reaction_spell_sources):
        _remove_reaction_spell(entity, row)
    for action_uuid in reversed(receipt.action_uuids):
        if not entity.unregister_action_by_uuid(action_uuid):
            raise RuntimeError("Sorcerer action template is missing")
    for handler_uuid in reversed(receipt.handler_uuids):
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None:
            raise RuntimeError("Sorcerer event handler is missing")
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for resource_name, source_id in reversed(
        receipt.resource_recovery_contributions,
    ):
        if not entity.action_economy.remove_resource_recovery_contribution(
            resource_name,
            source_id,
        ):
            raise RuntimeError("Sorcerer recovery contribution is missing")
    for resource_name, source_id in reversed(receipt.resource_contributions):
        if not entity.action_economy.remove_resource_contribution(
            resource_name,
            source_id,
        ):
            raise RuntimeError("Sorcerer resource contribution is missing")
    for source_id in reversed(receipt.spell_affinity_contribution_ids):
        if not entity.spellcasting.remove_spell_damage_affinity_contribution(source_id):
            raise RuntimeError("Sorcerer spell affinity is missing")
    for source_id in reversed(receipt.armor_class_formula_ids):
        if not entity.equipment.remove_armor_class_formula_candidate(source_id):
            raise RuntimeError("Sorcerer armor formula is missing")
    for modifier_id in reversed(receipt.maximum_hit_point_modifier_ids):
        entity.health.max_hit_points_bonus.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for ability, modifier_id in reversed(receipt.ability_score_modifier_ids):
        entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)
    for feature_id, source_id in reversed(receipt.feature_sources):
        if not entity.remove_feature_source(feature_id, source_id):
            raise RuntimeError("Sorcerer feature source is missing")
    for source_id in reversed(receipt.creature_proficiency_source_ids):
        if not entity.creature_proficiencies.remove_source(source_id):
            raise RuntimeError("Sorcerer creature proficiency source is missing")
    for saving_throw, source_id in reversed(
        receipt.saving_throw_proficiency_sources,
    ):
        if not entity.saving_throws.get_saving_throw(
            saving_throw.removesuffix("_saving_throw"),
        ).remove_proficiency_source(source_id):
            raise RuntimeError("Sorcerer saving-throw source is missing")
    for skill, source_id in reversed(receipt.skill_proficiency_sources):
        if not entity.skill_set.get_skill(skill).remove_proficiency_source(source_id):
            raise RuntimeError("Sorcerer skill source is missing")
    for hit_die_uuid in reversed(receipt.hit_die_uuids):
        if not entity.health.remove_hit_dice_by_uuid(hit_die_uuid):
            raise RuntimeError("Sorcerer hit die is missing")
    if restore_replacement:
        _restore_replaced_spell(entity, receipt, restored_caster_level)


def _update_spell_action_levels(entity: Entity, class_level: int) -> None:
    source_id = _spellcasting_source(entity)
    for action in entity.registered_actions:
        if (
            action.semantic_key in SORCERER_SPELL_RANKS
            and cast(SpellAction, action).spellcasting_source_id == source_id
        ):
            cast(SpellAction, action).caster_level = class_level


def apply_sorcerer_level(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    initial_first_class: bool | None = None,
) -> SorcererGrantReceipt:
    """Apply one next resolved Sorcerer/Draconic row without publishing Events."""
    resolved = resolve_sorcerer_level(
        level,
        entity.applied_class_levels,
        initial_first_class=initial_first_class,
    )
    for ability, amount in resolved.ability_increases:
        current = entity.ability_scores.get_ability(ability).ability_score.score
        if current + amount > 20:
            raise ValueError(f"ASI would raise {ability} above 20")
    try:
        entity.character_grant_receipt(level.step_id)
    except KeyError:
        pass
    else:
        raise RuntimeError(f"Sorcerer receipt {level.step_id} is already installed")

    source_id = _source(entity, level.step_id)
    previous_class_level = level.resulting_class_level - 1
    hit_dice: list[UUID] = []
    skills: list[tuple[str, UUID]] = []
    saves: list[tuple[SavingThrowName, UUID]] = []
    creature_sources: list[UUID] = []
    ability_modifiers: list[tuple[AbilityName, UUID]] = []
    maximum_hp: list[UUID] = []
    actions: list[UUID] = []
    metamagic_root_owners: list[UUID] = []
    elemental_affinity_root_owners: list[UUID] = []
    dragon_wings_root_owners: list[UUID] = []
    draconic_presence_root_owners: list[UUID] = []
    handlers: list[UUID] = []
    resources: list[tuple[str, UUID]] = []
    recoveries: list[tuple[str, UUID]] = []
    spell_sources: list[UUID] = []
    slot_sources: list[UUID] = []
    learned_reactions: list[tuple[str, UUID, UUID]] = []
    affinities: list[UUID] = []
    armor_formulas: list[UUID] = []
    features: list[tuple[str, UUID]] = []
    replaced_spell_id: str | None = None
    replaced_action_uuid: UUID | None = None
    replaced_action_index: int | None = None
    replaced_reaction: tuple[str, UUID, UUID] | None = None
    replaced_reaction_was_enabled: bool | None = None
    source_updated = False
    slots_updated = False
    receipt_stored = False
    state_stored = False

    def receipt() -> SorcererGrantReceipt:
        return SorcererGrantReceipt(
            step_id=level.step_id,
            source_id=source_id,
            hit_die_uuids=tuple(hit_dice),
            skill_proficiency_sources=tuple(skills),
            saving_throw_proficiency_sources=tuple(saves),
            creature_proficiency_source_ids=tuple(creature_sources),
            ability_score_modifier_ids=tuple(ability_modifiers),
            maximum_hit_point_modifier_ids=tuple(maximum_hp),
            action_uuids=tuple(actions),
            metamagic_root_owner_action_uuids=tuple(metamagic_root_owners),
            elemental_affinity_root_owner_action_uuids=tuple(
                elemental_affinity_root_owners
            ),
            dragon_wings_root_owner_action_uuids=tuple(
                dragon_wings_root_owners
            ),
            draconic_presence_root_owner_action_uuids=tuple(
                draconic_presence_root_owners
            ),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
            resource_recovery_contributions=tuple(recoveries),
            spell_source_ids=tuple(spell_sources),
            normal_spell_slot_capacity_ids=tuple(slot_sources),
            learned_reaction_spell_sources=tuple(learned_reactions),
            spell_affinity_contribution_ids=tuple(affinities),
            armor_class_formula_ids=tuple(armor_formulas),
            feature_sources=tuple(features),
            replaced_spell_id=replaced_spell_id,
            replaced_spell_action_uuid=replaced_action_uuid,
            replaced_spell_action_index=replaced_action_index,
            replaced_reaction_spell_source=replaced_reaction,
            replaced_reaction_spell_handler_was_enabled=(
                replaced_reaction_was_enabled
            ),
        )

    try:
        hit_die = HitDice.create(
            source_entity_uuid=entity.uuid,
            name=level.step_id,
            config=HitDiceConfig(
                hit_dice_value=6,
                hit_dice_count=1,
                mode="maximums" if level.character_level == 1 else "average",
                ignore_first_level=level.character_level != 1,
            ),
            identity_uuid=_source(entity, f"{level.step_id}.hit_die"),
        )
        entity.health.add_hit_dice(hit_die)
        hit_dice.append(hit_die.uuid)
        _apply_proficiencies(entity, resolved, creature_sources, skills, saves)

        for ability, amount in resolved.ability_increases:
            modifier_id = _source(entity, f"{level.step_id}.asi.{ability}")
            entity.ability_scores.get_ability(
                ability,
            ).ability_score.self_static.add_value_modifier(NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"Sorcerer level {level.resulting_class_level} ASI",
                value=amount,
            ))
            ability_modifiers.append((ability, modifier_id))

        hp_modifier_id = _source(entity, f"{level.step_id}.draconic_resilience.hp")
        entity.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier(
                uuid=hp_modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Draconic Resilience HP",
                value=1,
            ),
        )
        maximum_hp.append(hp_modifier_id)

        for feature_id in resolved.feature_ids:
            feature_source = _source(
                entity,
                f"{level.step_id}.feature.{feature_id}",
            )
            entity.add_feature_source(feature_id, feature_source)
            features.append((feature_id, feature_source))

        _set_spellcasting_source(entity, level.resulting_class_level)
        source_updated = True
        if level.resulting_class_level == 1:
            spell_sources.append(_spellcasting_source(entity))

        for spell_id in (*resolved.cantrip_ids, *resolved.spell_ids):
            _learn_spell(
                entity,
                actions,
                learned_reactions,
                spell_id,
                level.resulting_class_level,
            )

        if resolved.replacement is not None:
            old_spell, new_spell = resolved.replacement
            replaced_spell_id = old_spell
            if old_spell in _REACTION_SPEC_BY_ID:
                handler_uuid = (
                    entity.spellcasting.learned_reaction_spell_handler_uuid(
                        old_spell,
                    )
                )
                if handler_uuid is None:
                    raise RuntimeError("replaced Sorcerer reaction spell is missing")
                if _spellcasting_source(entity) not in (
                    entity.spellcasting.learned_reaction_spell_source_ids(
                        old_spell,
                    )
                ):
                    raise RuntimeError(
                        "replaced reaction spell is not Sorcerer-owned"
                    )
                replaced_reaction = (
                    old_spell,
                    _spellcasting_source(entity),
                    handler_uuid,
                )
                handler = entity.event_handlers.get(handler_uuid)
                if handler is None:
                    raise RuntimeError("replaced reaction handler is missing")
                replaced_reaction_was_enabled = handler.enabled
                remove_handler = (
                    entity.spellcasting.remove_learned_reaction_spell_source(
                        spell_id=old_spell,
                        source_id=_spellcasting_source(entity),
                        handler_uuid=handler_uuid,
                    )
                )
                if remove_handler:
                    handler.enabled = False
            else:
                old_action = next(
                    (
                        action
                        for action in entity.registered_actions
                        if action.semantic_key == old_spell
                        and cast(
                            SpellAction,
                            action,
                        ).spellcasting_source_id == _spellcasting_source(entity)
                    ),
                    None,
                )
                if old_action is None:
                    raise RuntimeError("replaced Sorcerer spell action is missing")
                replaced_action_uuid = old_action.uuid
                replaced_action_index = entity.registered_actions.index(old_action)
                if not entity.unregister_action_by_uuid(old_action.uuid):
                    raise RuntimeError("replaced Sorcerer spell could not be removed")
            _learn_spell(
                entity,
                actions,
                learned_reactions,
                new_spell,
                level.resulting_class_level,
            )

        _apply_lucky(entity, resolved, resources, handlers)
        _apply_level_features(
            entity,
            resolved,
            actions=actions,
            resources=resources,
            recoveries=recoveries,
            affinities=affinities,
            armor_formulas=armor_formulas,
            metamagic_root_owners=metamagic_root_owners,
            elemental_affinity_root_owners=elemental_affinity_root_owners,
            dragon_wings_root_owners=dragon_wings_root_owners,
            draconic_presence_root_owners=draconic_presence_root_owners,
        )

        slot_source = _source(entity, f"{level.step_id}.normal_spell_slots")
        entity.action_economy.set_normal_spell_slot_capacity(
            slot_source,
            dict(resolved.normal_spell_slots),
        )
        slot_sources.append(slot_source)
        slots_updated = True

        completed = receipt()
        entity.store_character_grant_receipt(completed)
        receipt_stored = True
        entity.applied_class_levels = (*entity.applied_class_levels, level)
        state_stored = True
        _update_spell_action_levels(entity, level.resulting_class_level)
        return completed
    except BaseException:
        if state_stored:
            entity.applied_class_levels = entity.applied_class_levels[:-1]
        if receipt_stored:
            entity.remove_character_grant_receipt(level.step_id)
        if slots_updated:
            entity.action_economy.remove_normal_spell_slot_capacity(
                slot_sources[-1],
            )
            if previous_class_level > 0:
                entity.action_economy.set_normal_spell_slot_capacity(
                    _source(
                        entity,
                        f"class.sorcerer.level_{previous_class_level}.normal_spell_slots",
                    ),
                    FULL_CASTER_SPELL_SLOTS[previous_class_level],
                )
        _remove_sorcerer_receipt(
            entity,
            receipt(),
            restore_replacement=True,
            restored_caster_level=max(1, previous_class_level),
        )
        if source_updated:
            if previous_class_level > 0:
                _set_spellcasting_source(entity, previous_class_level)
                _update_spell_action_levels(entity, previous_class_level)
            else:
                entity.spellcasting.remove_source(_spellcasting_source(entity))
        raise


def sorcerer_level_has_active_child(entity: Entity) -> bool:
    """Return whether removing the last Sorcerer row commits child facts."""
    if not entity.applied_class_levels:
        return False
    level = entity.applied_class_levels[-1]
    if level.class_id is not CharacterClass.SORCERER:
        return False
    receipt = cast(
        SorcererGrantReceipt,
        entity.character_grant_receipt(level.step_id),
    )
    _validate_sorcerer_receipt_ownership(
        entity,
        receipt,
        require_normal_slot=True,
    )
    return bool(_owned_condition_rows(entity, receipt))


def remove_last_sorcerer_level(
    entity: Entity,
    *,
    parent_event: Event | None = None,
) -> AppliedClassLevel:
    """Remove the last applied Sorcerer row through its exact typed receipt."""
    if not entity.applied_class_levels:
        raise RuntimeError("entity has no applied class level")
    level = entity.applied_class_levels[-1]
    if level.class_id is not CharacterClass.SORCERER:
        raise RuntimeError("the last applied class level is not Sorcerer")
    receipt = cast(
        SorcererGrantReceipt,
        entity.character_grant_receipt(level.step_id),
    )
    if receipt.normal_spell_slot_capacity_ids != (
        _source(entity, f"{level.step_id}.normal_spell_slots"),
    ):
        raise RuntimeError("Sorcerer spell-slot capacity receipt is inconsistent")
    _validate_sorcerer_receipt_ownership(
        entity,
        receipt,
        require_normal_slot=True,
    )
    slot_source = receipt.normal_spell_slot_capacity_ids[0]
    _remove_owned_condition_rows(entity, receipt, parent_event)
    if not entity.action_economy.remove_normal_spell_slot_capacity(slot_source):
        raise RuntimeError("Sorcerer spell-slot capacity owner is missing")

    previous_class_level = level.resulting_class_level - 1
    _remove_sorcerer_receipt(
        entity,
        receipt,
        restore_replacement=True,
        restored_caster_level=max(1, previous_class_level),
    )
    entity.remove_character_grant_receipt(level.step_id)
    entity.applied_class_levels = entity.applied_class_levels[:-1]
    if previous_class_level > 0:
        _set_spellcasting_source(entity, previous_class_level)
        entity.action_economy.set_normal_spell_slot_capacity(
            _source(
                entity,
                f"class.sorcerer.level_{previous_class_level}.normal_spell_slots",
            ),
            FULL_CASTER_SPELL_SLOTS[previous_class_level],
        )
        _update_spell_action_levels(entity, previous_class_level)
    else:
        if receipt.spell_source_ids != (_spellcasting_source(entity),):
            raise RuntimeError("Sorcerer spell source receipt is inconsistent")
        entity.spellcasting.remove_source(receipt.spell_source_ids[0])
    return level


__all__ = [
    "apply_sorcerer_level",
    "remove_last_sorcerer_level",
    "sorcerer_level_has_active_child",
]
