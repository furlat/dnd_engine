"""Paladin class features.

Contains: Divine Smite (per-level handlers that add radiant damage on melee hit).
"""

from typing import Optional, List, Tuple
from uuid import UUID

from dnd.core.aoe import AoEShape, Sphere
from dnd.core.base_actions import spell_slot_cost_type
from dnd.types.event_facts import HandlerGroupDispatch
from dnd.core.events import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
    Damage,
    DamageRollResultEvent,
    EntityFactionChangedEvent,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.dice import AttackOutcome
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.blocks.spellcasting import DivineSmiteEntitlement
from dnd.spells.content_metadata import srd_reaction_identity
from dnd.core.content.registration import get_content_declaration

from dnd.entity import Entity

from typing import Literal
from pydantic import Field, PrivateAttr
from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.blocks.equipment import Weapon
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock, PreparedConditionRemovals
from dnd.core.base_conditions import BaseCondition, Duration, ConditionApplicationEvent
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.action_types import ActionSelection, ActionVariantFacet, EntityTargetPerception, selection_facet
from dnd.types.discovery import ActorScan, Relationship, ScanRecord
from dnd.types.physical_access import PhysicalAccess
from dnd.core.events import Range, RangeType, SpatialChangeEvent
from dnd.core.modifiers import (
    ContextualNumericalModifier,
    ContextualAdvantageModifier,
    NumericalModifier,
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.saving_throw_types import SAVING_THROW_CONTEXT_KEY, SavingThrowContext
from dnd.conditions import Unconscious, Poisoned, prepare_control_removals
from dnd.classes.divine import turn_creature, turning_targets, Turned
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)
from dnd.types.character_progression import CharacterClass


MAX_SMITE_DICE = 5
MAX_SMITE_DICE_VS_UNDEAD_OR_FIEND = 6


def _is_melee_weapon_slot(weapon_slot: WeaponSlot) -> bool:
    """Check if weapon slot is a melee slot."""
    return weapon_slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF)


def _target_grants_extra_smite_die(target_entity_uuid: Optional[UUID]) -> bool:
    """Return whether Divine Smite gains its creature-type bonus die."""
    if target_entity_uuid is None:
        return False

    target = Entity.get(target_entity_uuid)
    if not isinstance(target, Entity):
        return False

    return target.creature_type in (CreatureType.UNDEAD, CreatureType.FIEND)


def create_divine_smite_processor(slot_level: int):
    """Create a closure-based processor for a specific spell slot level.

    Args:
        slot_level: The spell slot level this handler uses (1-5).

    Returns:
        EventProcessor callable for this smite level.
    """

    def divine_smite_processor(
        event: Event, source_entity_uuid: UUID
    ) -> Optional[Event]:
        """Divine Smite: on melee weapon hit, add radiant damage dice and consume spell slot."""
        if not isinstance(event, DamageRollResultEvent):
            return None

        if event.source_entity_uuid != source_entity_uuid:
            return None

        if (
            event.attack_kind != "weapon"
            or event.weapon_slot is None
            or not _is_melee_weapon_slot(event.weapon_slot)
        ):
            return None

        if event.attack_outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT):
            return None

        if event.context is not None and event.context.get("divine_smite_applied"):
            return None

        if (
            event.target_entity_uuid is None
            or Entity.get(event.target_entity_uuid) is None
        ):
            return None

        entity = Entity.get(source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return None

        entitlements = [
            row
            for row in entity.spellcasting.divine_smite_entitlements.values()
            if row.maximum_slot_rank >= slot_level
        ]
        class_origin = any(row.origin_kind == "class" for row in entitlements)
        if not entitlements or entity.is_spellcasting_blocked() and not class_origin:
            return None
        if not entity.action_economy.can_afford(spell_slot_cost_type(slot_level), 1):
            return None

        target = Entity.get(event.target_entity_uuid)
        if (
            target is None
            or (
                not class_origin
                and SpellProtectionRegistry.is_protected(
                    target.position, entity.position, slot_level
                )
            )
        ):
            return None
        if any(
            level > slot_level
            and (handler := entity.event_handlers.get(identity)) is not None
            and handler.enabled
            and entity.action_economy.can_afford(spell_slot_cost_type(level), 1)
            for level, identity in entity.spellcasting.divine_smite_handler_uuids.items()
        ):
            return None
        creature_type_bonus = (
            1 if _target_grants_extra_smite_die(event.target_entity_uuid) else 0
        )
        dice_count = min(
            min(1 + slot_level, MAX_SMITE_DICE) + creature_type_bonus,
            MAX_SMITE_DICE_VS_UNDEAD_OR_FIEND,
        )

        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        smite_damage_bonus = ModifiableValue(
            source_entity_uuid=source_entity_uuid, name="Divine Smite Damage Bonus"
        )
        smite_damage = Damage(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            name="Divine Smite",
            effect_origin=(
                EffectOrigin(
                    kind=EffectOriginKind.ACTION,
                    magical=True,
                    source_id="class_feature.paladin.divine_smite",
                    source_position=entity.position,
                    source_event_lineage_uuid=str(event.lineage_uuid),
                )
                if class_origin
                else EffectOrigin.spell(
                    source_id="spell.divine_smite",
                    source_event_lineage_uuid=str(event.lineage_uuid),
                    source_position=entity.position,
                    base_spell_level=1,
                    effective_spell_level=slot_level,
                )
            ),
            damage_dice=8,
            dice_numbers=dice_count,
            damage_bonus=smite_damage_bonus,
            damage_type=DamageType.RADIANT,
        )

        smite_dice = smite_damage.get_dice(
            attack_outcome=event.attack_outcome, crit_extra_dice=0
        )
        smite_roll = smite_dice.roll

        modified_event = event.append_damage_roll(
            smite_damage,
            smite_roll,
            "Divine Smite",
            f"Level {slot_level} spell slot",
        )
        context = {
            **(modified_event.context or {}),
            "divine_smite_applied": True,
            "divine_smite_slot_level": slot_level,
            "divine_smite_dice_count": dice_count,
            "divine_smite_creature_type_bonus": creature_type_bonus,
        }

        entity_name = entity.name if entity else "Unknown"
        return modified_event.with_updates(
            context=context,
            status_message=(
                f"{entity_name} uses Divine Smite "
                f"(L{slot_level} slot, {dice_count}d8 radiant)"
            ),
        )

    return divine_smite_processor


class DivineSmiteHandler(EventHandler):
    """One authored reaction whose selected spell-slot level remains runtime data."""

    slot_level: int = Field(default=1, ge=1, le=5)
    owns_entitlement: bool = True

    def on_admitted(self):
        actor = Entity.get(self.source_entity_uuid)
        if self.owns_entitlement and actor is not None:
            actor.spellcasting.divine_smite_entitlements[self.uuid] = (
                DivineSmiteEntitlement(
                    maximum_slot_rank=self.slot_level, origin_kind="class"
                )
            )

    def on_removed(self):
        actor = Entity.get(self.source_entity_uuid)
        if self.owns_entitlement and actor is not None:
            actor.spellcasting.divine_smite_entitlements.pop(self.uuid, None)


def create_divine_smite_handler(
    source_entity_uuid: UUID,
    slot_level: int,
    *,
    owns_entitlement: bool = True,
) -> DivineSmiteHandler:
    """Create a Divine Smite handler for a specific spell slot level.

    Args:
        source_entity_uuid: The entity UUID (paladin).
        slot_level: The spell slot level this handler covers (1-5).
    """
    return DivineSmiteHandler(
        name=f"Divine Smite (L{slot_level})",
        slot_level=slot_level,
        owns_entitlement=owns_entitlement,
        semantic_key="reaction.class_feature.paladin.divine_smite",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=source_entity_uuid,
            )
        ],
        event_processor=create_divine_smite_processor(slot_level),
        player_toggleable=True,
    )


def register_divine_smite(
    entity: Entity,
    max_slot_level: int = 5,
    *,
    entitlement_uuid: UUID | None = None,
    origin_kind: str = "class",
) -> List[EventHandler]:
    """Register Divine Smite handlers on an entity.

    Feature and learned origins share one toggle per entitled slot level.
    Each processor selects the highest enabled affordable level independently
    of registration order; the hit context prevents duplicate payment.

    Args:
        entity: The paladin entity.
        max_slot_level: Maximum spell slot level to register handlers for (default 5).

    Returns:
        List of registered EventHandler objects.
    """
    identity_key = entitlement_uuid or entity.uuid
    if identity_key in entity.spellcasting.divine_smite_entitlements:
        raise ValueError("Divine Smite entitlement is already installed")
    entity.spellcasting.divine_smite_entitlements[identity_key] = (
        DivineSmiteEntitlement(
            maximum_slot_rank=max_slot_level, origin_kind=origin_kind
        )
    )
    handlers: List[EventHandler] = []
    installed = []
    try:
        for level in range(max_slot_level, 0, -1):
            identity = entity.spellcasting.divine_smite_handler_uuids.get(level)
            existing = (
                entity.event_handlers.get(identity) if identity is not None else None
            )
            if existing is not None:
                handlers.append(existing)
                continue
            handler = create_divine_smite_handler(
                entity.uuid, level, owns_entitlement=False
            )
            try:
                entity.add_event_handler(handler)
            except BaseException:
                if handler.uuid in entity.event_handlers:
                    entity.remove_event_handler(handler)
                handler.remove_from_register()
                raise
            entity.spellcasting.divine_smite_handler_uuids[level] = handler.uuid
            installed.append((level, handler))
            handlers.append(handler)
        return handlers
    except BaseException:
        entity.spellcasting.divine_smite_entitlements.pop(identity_key)
        for level, handler in reversed(installed):
            entity.remove_event_handler(handler)
            handler.remove_from_register()
            entity.spellcasting.divine_smite_handler_uuids.pop(level)
        raise


def unregister_divine_smite(entity: Entity, entitlement_uuid: UUID) -> None:
    """Remove only this entitlement; feature and learned spell share five toggles."""
    entity.spellcasting.divine_smite_entitlements.pop(entitlement_uuid, None)
    maximum = max(
        (
            row.maximum_slot_rank
            for row in entity.spellcasting.divine_smite_entitlements.values()
        ),
        default=0,
    )
    for level, identity in tuple(
        entity.spellcasting.divine_smite_handler_uuids.items()
    ):
        if level <= maximum:
            continue
        handler = entity.event_handlers.get(identity)
        if handler is not None:
            entity.remove_event_handler(handler)
            handler.remove_from_register()
        entity.spellcasting.divine_smite_handler_uuids.pop(level, None)


@srd_reaction_identity(
    content_id="reaction.spell.divine_smite",
    display_name="Divine Smite Entitlement",
    description="Knowing Divine Smite supplies the shared automatic per-slot toggles.",
    source_page=None,
    srd_version="5.2",
    sort_order=3020,
    adaptation_notes="BG3 automatic on-hit adaptation; five existing slot toggles, no accept-reaction UI.",
)
class LearnedDivineSmiteHandler(EventHandler):
    """Own the learned spell's entitlement without a second damage processor."""

    def on_admitted(self) -> None:
        caster = Entity.get(self.source_entity_uuid)
        if caster is not None:
            register_divine_smite(
                caster, entitlement_uuid=self.uuid, origin_kind="spell"
            )

    def on_removed(self) -> None:
        caster = Entity.get(self.source_entity_uuid)
        if caster is not None:
            unregister_divine_smite(caster, self.uuid)


def create_learned_divine_smite_handler(
    source_entity_uuid: UUID,
) -> LearnedDivineSmiteHandler:
    return LearnedDivineSmiteHandler(
        name="Divine Smite Entitlement",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[],
        event_processor=lambda event, source: None,
        player_toggleable=False,
        content_kind=RuntimeBehaviorKind.REACTION,
        semantic_key="reaction.spell.divine_smite",
    )


DIVINE_SMITE_REACTION_DECLARATION = get_content_declaration(LearnedDivineSmiteHandler)

# Native Paladin/Devotion composition. All cross-effect policy stays here.


def paladin_level(actor):
    return sum(
        row.class_id is CharacterClass.PALADIN for row in actor.applied_class_levels
    )


def feature_cost(resource, amount=1, channel="actions"):
    return [
        Cost(
            name=resource,
            cost_type=channel,
            cost=1,
            evaluator=entity_action_economy_cost_evaluator,
            resource_name=resource,
            resource_cost=amount,
            resource_evaluator=entity_resource_cost_evaluator,
        )
    ]


def attach_feature_effect(root_uuid, target, condition, event):
    root = BaseCondition.get(root_uuid) if root_uuid is not None else None
    if root_uuid is not None and (root is None or not root.applied):
        return event.cancel(status_message="Class feature lifetime is absent")
    result = target.add_condition(condition, parent_event=event)
    if (
        root is not None
        and not root.applied
        and result is not None
        and not result.canceled
    ):
        target.remove_condition_by_uuid(condition.uuid, parent_event=event)
        return event.cancel(
            status_message="Class feature lifetime ended during admission"
        )
    if root is not None and result is not None and not result.canceled:
        root.add_linked_condition(target.uuid, condition.uuid)
    return result


class DivineSenseEffect(BaseCondition):
    description: str = (
        "Two-turn attack advantage against celestial, fiend and undead creatures."
    )
    name: str = "Divine Sense"
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=2, duration_type=DurationType.ROUNDS)
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        actor = Entity.get(self.target_entity_uuid)

        def advantage(source_uuid, target_uuid=None, context=None):
            target = Entity.get(target_uuid)
            if target is not None and target.creature_type in (
                CreatureType.CELESTIAL,
                CreatureType.FIEND,
                CreatureType.UNDEAD,
            ):
                return AdvantageModifier(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target_uuid,
                    name="Divine Sense",
                    value=AdvantageStatus.ADVANTAGE,
                    use_register=False,
                )

        modifiers = []
        for value in (
            actor.equipment.attack_bonus,
            actor.spellcasting.spell_attack_bonus,
        ):
            identity = value.self_contextual.add_advantage_modifier(
                ContextualAdvantageModifier(
                    source_entity_uuid=actor.uuid,
                    callable=advantage,
                    name="Divine Sense",
                )
            )
            modifiers.append((value.uuid, identity))
        return modifiers, [], [], [], event.phase_to(EventPhase.EFFECT)


class DivineSense(BaseAction):
    creates = (DivineSenseEffect,)
    name: str = "Divine Sense"
    target_type: TargetType = TargetType.SELF
    feature_owner_uuid: UUID
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.paladin.divine_sense",
        )
    )
    costs: list[Cost] = Field(
        default_factory=lambda: feature_cost("divine_sense", channel="bonus_actions")
    )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            actor = Entity.get(self.source_entity_uuid)
            result = attach_feature_effect(
                self.feature_owner_uuid,
                actor,
                DivineSenseEffect(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=actor.uuid,
                    effect_origin=effect.get_effect_origin(),
                ),
                effect,
            )
            if result is None or result.canceled:
                return effect.cancel(status_message="Divine Sense was rejected")
        return effect


class LayOnHands(BaseAction):
    entity_target_perception: EntityTargetPerception = (
        EntityTargetPerception.TOUCH_CONTACT
    )

    def get_physical_access(self):
        return PhysicalAccess.HAND

    def apply(self, *args, **kwargs):
        try:
            return super().apply(*args, **kwargs)
        finally:
            prepared = self._cures
            if prepared is not None and prepared.committed_result is None:
                BaseBlock.cancel_owned_condition_removals(
                    prepared, "Touch action did not commit"
                )
            self._cures = None

    name: str = "Lay on Hands"
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    mode: Literal["lesser", "greater", "cure"] = "lesser"
    _cures: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def get_range(self):
        return Range(type=RangeType.REACH, normal=5)

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=mode, label=mode.title()),) for mode in ("lesser", "greater", "cure"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "mode": selection_facet(selection, "form")}

    def get_discovery_display_name(self):
        return f"Lay on Hands ({self.mode.title()})"

    def get_source_dynamic_costs(self):
        return feature_cost("lay_on_hands", 1 if self.mode == "lesser" else 2)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None or target.creature_type in (
            CreatureType.UNDEAD,
            CreatureType.CONSTRUCT,
        ):
            return "Lay on Hands requires a living eligible creature"
        return None

    def _apply_costs(self, event):
        if self.mode == "cure":
            target = Entity.get(self.target_entity_uuid)
            roots = [
                condition
                for condition in target.active_conditions_by_uuid.values()
                if isinstance(condition, Poisoned)
                or condition.tags.intersection(
                    {ConditionTag.POISON, ConditionTag.DISEASE}
                )
            ]
            self._cures = prepare_exact_removals(target, roots, event)
            if self._cures is None:
                return event.cancel(status_message="Cure removal was rejected")
        result = entity_action_economy_cost_applier(event, self.source_entity_uuid)
        if result.canceled and self._cures is not None:
            BaseBlock.cancel_owned_condition_removals(
                self._cures, "Lay on Hands costs were rejected"
            )
        return result

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            if self._cures is not None:
                BaseBlock.cancel_owned_condition_removals(
                    self._cures, "Lay on Hands was rejected"
                )
            return effect
        actor, target = (
            Entity.get(self.source_entity_uuid),
            Entity.get(event.target_entity_uuid),
        )
        if self._cures is not None:
            with BaseBlock.condition_removal_scope():
                BaseBlock.commit_owned_condition_removals(self._cures)
            BaseBlock.publish_owned_condition_removals(self._cures)
        else:
            target.receive_healing(
                (2 if self.mode == "lesser" else 4) * paladin_level(actor),
                actor.uuid,
                source_description="Lay on Hands",
                parent_event=effect.uuid,
            )
        return effect


def prepare_exact_removals(target, roots, event):
    if not roots:
        return None
    prepared = PreparedConditionRemovals([])
    visited = set()
    try:
        with BaseBlock.condition_removal_scope():
            for condition in roots:
                rejected = BaseBlock._prepare_condition_removal_tree(
                    condition,
                    condition_owner=target,
                    expire=False,
                    parent_event=event,
                    prepared=prepared.entries,
                    visited=visited,
                )
                if rejected is not None:
                    BaseBlock.cancel_owned_condition_removals(
                        prepared, "Feature removal was rejected"
                    )
                    return None
        if not BaseBlock.validate_prepared_condition_removals(prepared.entries):
            BaseBlock.cancel_owned_condition_removals(
                prepared, "Selected removals conflict"
            )
            return None
        return prepared
    except BaseException:
        BaseBlock.cancel_owned_condition_removals(
            prepared, "Selected removal admission raised"
        )
        raise


def divine_health(event, source_uuid):
    if (
        isinstance(event, ConditionApplicationEvent)
        and ConditionTag.DISEASE in event.condition.tags
    ):
        return event.cancel(status_message="Divine Health prevents disease")


def improved_divine_smite(event, source_uuid):
    if (
        not isinstance(event, DamageRollResultEvent)
        or event.attack_kind != "weapon"
        or event.weapon_slot is None
        or not _is_melee_weapon_slot(event.weapon_slot)
        or event.attack_outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT)
    ):
        return None
    actor, target = Entity.get(source_uuid), Entity.get(event.target_entity_uuid)
    if (
        actor is None
        or target is None
    ):
        return None
    damage = Damage(
        name="Improved Divine Smite",
        source_entity_uuid=source_uuid,
        target_entity_uuid=target.uuid,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.RADIANT,
        effect_origin=EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.paladin.improved_divine_smite",
        ),
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_uuid, base_value=0
        ),
    )
    return event.append_damage_roll(
        damage,
        damage.get_dice(event.attack_outcome).roll,
        "Improved Divine Smite",
        "Every melee weapon hit",
    )


def aura_provider_active(actor):
    return (
        actor is not None
        and actor.is_deployed
        and actor.get_normal_hp() > 0
        and actor.health.life_state is LifeState.ALIVE
        and not any(
            isinstance(condition, Unconscious) and condition.contributions_active()
            for condition in actor.active_conditions_by_uuid.values()
        )
    )


class PaladinAuraBenefit(BaseCondition):
    description: str = "One exact active aura contribution from a conscious Paladin."
    name: str = "Paladin Aura"
    aura_kind: Literal["protection", "devotion", "courage"]
    zone_uuid: UUID
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )
    _purge: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def model_post_init(self, context):
        super().model_post_init(context)
        self.name = f"Aura of {self.aura_kind.title()}:{self.zone_uuid}"

    def contributions_active(self):
        zone = BaseCondition.get(self.zone_uuid)
        source, target = (
            Entity.get(self.source_entity_uuid),
            Entity.get(self.target_entity_uuid),
        )
        return (
            super().contributions_active()
            and isinstance(zone, PaladinAuraZone)
            and zone.contributions_active()
            and aura_provider_active(source)
            and target is not None
            and source.faction == target.faction
            and grid_distance_feet(source.position, target.position)
            <= (30 if paladin_level(source) >= 18 else 10)
        )

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        if self.aura_kind == "protection":

            def bonus(source_uuid, target_uuid=None, context=None):
                eligible = [
                    condition
                    for condition in target.active_conditions_by_uuid.values()
                    if isinstance(condition, PaladinAuraBenefit)
                    and condition.aura_kind == "protection"
                    and condition.contributions_active()
                ]
                winner = max(
                    eligible,
                    key=lambda condition: (
                        max(
                            1,
                            Entity.get(
                                condition.source_entity_uuid
                            ).ability_scores.charisma.modifier,
                        ),
                        str(condition.uuid),
                    ),
                    default=None,
                )
                if winner is self:
                    return NumericalModifier(
                        name="Aura of Protection",
                        value=max(
                            1,
                            Entity.get(
                                self.source_entity_uuid
                            ).ability_scores.charisma.modifier,
                        ),
                        source_entity_uuid=source_uuid,
                        target_entity_uuid=target_uuid,
                        use_register=False,
                    )

            modifiers = []
            for save in target.saving_throws.get_blocks():
                value = save.bonus
                identity = value.self_contextual.add_value_modifier(
                    ContextualNumericalModifier(
                        source_entity_uuid=target.uuid,
                        target_entity_uuid=self.source_entity_uuid,
                        name="Aura of Protection",
                        callable=bonus,
                    )
                )
                modifiers.append((value.uuid, identity))
            value = target.health.death_save_bonus
            identity = value.self_contextual.add_value_modifier(
                ContextualNumericalModifier(
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    name="Aura of Protection",
                    callable=bonus,
                )
            )
            modifiers.append((value.uuid, identity))
            return modifiers, [], [], [], event.phase_to(EventPhase.EFFECT)
        identity = "Charmed" if self.aura_kind == "devotion" else "Frightened"
        self._purge = prepare_control_removals(target, frozenset({identity}), event)
        if self._purge is None:
            return (
                [],
                [],
                [],
                [],
                event.cancel(status_message="Aura control removal was rejected"),
            )
        target.add_condition_immunity_source(identity, self.uuid)
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _commit_application(self, event):
        if self._purge is not None:
            BaseBlock.commit_owned_condition_removals(self._purge)

    def publish_prepared_application(self):
        if self._purge is not None:
            BaseBlock.publish_owned_condition_removals(self._purge)

    def _release_owned_runtime_state(self, *, parent_event=None):
        if self._purge is not None and self._purge.committed_result is None:
            BaseBlock.cancel_owned_condition_removals(
                self._purge, "Aura admission did not commit"
            )
        target = Entity.get(self.target_entity_uuid)
        if target is not None and self.aura_kind != "protection":
            target.remove_condition_immunity_source(
                "Charmed" if self.aura_kind == "devotion" else "Frightened", self.uuid
            )
        super()._release_owned_runtime_state(parent_event=parent_event)


class PaladinAuraMembership(SpatialConditionMembershipSource):
    creates = (PaladinAuraBenefit,)
    description: str = "One exact Paladin aura lease."
    aura_kind: Literal["protection", "devotion", "courage"]

    def create_manifestation(self, target):
        return PaladinAuraBenefit(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            aura_kind=self.aura_kind,
            zone_uuid=self.source_spatial_condition_uuid,
        )


class PaladinAuraZone(MembershipAreaCondition):
    creates = (PaladinAuraMembership,)
    description: str = "Moving Paladin aura with ordinary native occupant memberships."
    name: str = "Paladin Aura"
    aura_kind: Literal["protection", "devotion", "courage"]
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.ENTITY
    occupancy_policy: SpatialEffectOccupancyPolicy = (
        SpatialEffectOccupancyPolicy.OVERLAPPING
    )
    area: AoEShape = Sphere(radius_feet=10)
    membership_tags: frozenset[ConditionTag] = frozenset()
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
        }
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
            SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT,
        }
    )

    def membership_source_class(self):
        return PaladinAuraMembership

    def membership_source_kwargs(self):
        return {"aura_kind": self.aura_kind}

    def membership_applies_to(self, entity):
        source = Entity.get(self.source_entity_uuid)
        return aura_provider_active(source) and source.faction == entity.faction

    def refresh_membership(self, entity, *, parent_event):
        if (
            entity.is_deployed
            and entity.position in self.affected_positions
            and self.membership_applies_to(entity)
        ):
            self.apply_membership(entity, parent_event=parent_event)
        else:
            self.remove_membership(entity, parent_event=parent_event)

    def relocate_anchor(self, position, *, parent_event):
        previous = self.position
        self.position = position
        try:
            return self.change_footprint(
                {
                    cell
                    for cell in self._compute_affected_positions()
                    if get_map().has_tile(*cell)
                },
                parent_event=parent_event,
            )
        except BaseException:
            self.position = previous
            raise

    def _apply_effect_entry_effect(self, entity, *, parent_event):
        if self.membership_applies_to(entity):
            self.apply_membership(entity, parent_event=parent_event)

    def _apply_effect_exit_effect(self, entity, *, parent_event):
        self.remove_membership(entity, parent_event=parent_event)


class PaladinAuraRoot(BaseCondition):
    creates = (PaladinAuraZone,)
    description: str = "Owns one moving passive Paladin aura and its memberships."
    name: str = "Paladin Aura Owner"
    zone_uuid: UUID | None = None
    _refreshing: bool = PrivateAttr(default=False)
    aura_kind: Literal["protection", "devotion", "courage"]
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )

    def _apply(self, event):
        actor = Entity.get(self.target_entity_uuid)
        if actor.is_deployed:
            self._place_zone(actor, event)

        def refresh(boundary, _):
            if (
                isinstance(boundary, SpatialChangeEvent)
                and boundary.entity_uuid != actor.uuid
            ):
                return None
            if (
                isinstance(boundary, EntityFactionChangedEvent)
                and boundary.entity_uuid != actor.uuid
            ):
                zone = BaseCondition.get(self.zone_uuid)
                recipient = Entity.get(boundary.entity_uuid)
                if (
                    isinstance(zone, PaladinAuraZone)
                    and recipient is not None
                    and (
                        recipient.position in zone.affected_positions
                        or any(
                            target_uuid == recipient.uuid
                            for target_uuid, _ in zone.linked_conditions
                        )
                    )
                ):
                    zone.refresh_membership(recipient, parent_event=boundary)
                return None
            self.on_owner_placement_committed(boundary)

        handler = EventHandler(
            name="Paladin aura deployment",
            source_entity_uuid=actor.uuid,
            group_dispatch=HandlerGroupDispatch.AFTER_GROUP,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_ENTITY_ENTERED,
                    event_phase=EventPhase.EFFECT,
                ),
                Trigger(
                    event_type=EventType.CONDITION_MEMBERSHIP_COMMITTED,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.ENTITY_FACTION_CHANGED,
                    event_phase=EventPhase.EFFECT,
                ),
                Trigger(
                    event_type=EventType.DAMAGE_APPLIED,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.HEALING_APPLIED,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.ENTITY_LEVEL_ADDED,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.ENTITY_LEVEL_REMOVED,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=actor.uuid,
                ),
            ],
            event_processor=refresh,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _place_zone(self, actor, event):
        if self.zone_uuid is not None:
            existing = BaseCondition.get(self.zone_uuid)
            if (
                isinstance(existing, PaladinAuraZone)
                and existing.is_active_spatial_condition()
            ):
                return
            self.linked_conditions = [
                row for row in self.linked_conditions if row[1] != self.zone_uuid
            ]
            self.zone_uuid = None
        zone = PaladinAuraZone(
            effect_origin=None,
            content_ref=get_content_declaration(PaladinAuraZone).ref,
            source_entity_uuid=actor.uuid,
            position=actor.position,
            anchor_uuid=actor.uuid,
            faction=actor.faction,
            aura_kind=self.aura_kind,
            area=Sphere(radius_feet=30 if paladin_level(actor) >= 18 else 10),
        )
        self.zone_uuid = zone.uuid
        result = zone.activate(parent_event=event)
        if result is None or result.canceled:
            self.zone_uuid = None
            raise RuntimeError("Paladin aura placement was rejected")
        self.add_linked_condition(zone.uuid, zone.uuid)

    def on_owner_placement_committed(self, event):
        actor = Entity.get(self.target_entity_uuid)
        if actor is None or not actor.is_deployed or self._refreshing:
            return
        self._refreshing = True
        try:
            self._place_zone(actor, event)
            zone = BaseCondition.get(self.zone_uuid)
            if isinstance(zone, PaladinAuraZone):
                area = Sphere(radius_feet=30 if paladin_level(actor) >= 18 else 10)
                if zone.area != area:
                    zone.area = area
                    zone.relocate_anchor(actor.position, parent_event=event)
                recipient_uuids = {
                    recipient.uuid
                    for recipient in zone._occupants_at(set(zone.affected_positions))
                }
                recipient_uuids.update(
                    target_uuid for target_uuid, _ in zone.linked_conditions
                )
                for recipient_uuid in sorted(recipient_uuids, key=str):
                    recipient = Entity.get(recipient_uuid)
                    if recipient is not None:
                        zone.refresh_membership(recipient, parent_event=event)
        finally:
            self._refreshing = False


class TurnUnholy(BaseAction):
    creates = (Turned,)
    name: str = "Turn the Unholy"
    target_type: TargetType = TargetType.SELF
    casting_source_id: UUID
    feature_owner_uuid: UUID
    costs: list[Cost] = Field(default_factory=lambda: feature_cost("channel_oath"))
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.paladin.turn_unholy",
        )
    )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if not effect.canceled:
            if event.application is None:
                self._apply_target_batch(
                    event,
                    turning_targets(actor, (CreatureType.UNDEAD, CreatureType.FIEND)),
                    parent_event=effect,
                )
            else:
                turn_creature(
                    actor,
                    Entity.get(event.target_entity_uuid),
                    effect,
                    casting_source_id=self.casting_source_id,
                    feature_owner_uuid=self.feature_owner_uuid,
                )
        return effect


class SacredWeaponEffect(BaseCondition):
    description: str = "The exact weapon gains current wielder CHA on attacks and sheds light for ten turns."
    name: str = "Sacred Weapon"
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS)
    )
    _light_uuid: UUID | None = PrivateAttr(default=None)
    _anchor_uuid: UUID | None = PrivateAttr(default=None)

    def _apply(self, event):
        weapon = BaseBlock.get(self.target_entity_uuid)
        if not isinstance(weapon, Weapon):
            return (
                [],
                [],
                [],
                [],
                event.cancel(status_message="Sacred Weapon requires the exact weapon"),
            )
        weapon.magical_attack_sources.add(self.uuid)

        def bonus(source_uuid, target_uuid=None, context=None):
            holder = Entity.get(weapon.owner_uuid) if weapon.is_equipped else None
            if holder is not None:
                return NumericalModifier(
                    name="Sacred Weapon",
                    value=max(1, holder.ability_scores.charisma.modifier),
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target_uuid,
                    use_register=False,
                )

        identity = weapon.attack_bonus.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                name="Sacred Weapon", source_entity_uuid=weapon.uuid, callable=bonus
            )
        )
        return (
            [(weapon.attack_bonus.uuid, identity)],
            [],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )

    def _commit_application(self, event):
        self.on_owner_placement_committed(event)

    def on_owner_placement_committed(self, event):
        weapon = BaseBlock.get(self.target_entity_uuid)
        if not isinstance(weapon, Weapon):
            return
        placement = get_map().get_object_placement(weapon.uuid)
        anchor_uuid = (
            weapon.uuid
            if placement is not None
            else weapon.owner_uuid
            if weapon.is_equipped
            else None
        )
        anchor = BaseBlock.get(anchor_uuid)
        position = (
            placement.position
            if placement is not None
            else anchor.position
            if anchor is not None
            else None
        )
        if anchor_uuid != self._anchor_uuid and self._light_uuid is not None:
            get_map().remove_light_source(self._light_uuid, parent_event=event.uuid)
            self._light_uuid = None
        self._anchor_uuid = anchor_uuid
        if position is not None:
            if self._light_uuid is None:
                self._light_uuid = get_map().add_light_source(
                    position,
                    bright_radius_feet=20,
                    dim_radius_feet=20,
                    anchor_uuid=anchor_uuid,
                    contribution_owner_uuid=self.uuid,
                    parent_event=event.uuid,
                )
            else:
                get_map().move_light_source(
                    self._light_uuid, position, parent_event=event.uuid
                )

    def _release_owned_runtime_state(self, *, parent_event=None):
        weapon = BaseBlock.get(self.target_entity_uuid)
        if isinstance(weapon, Weapon):
            weapon.magical_attack_sources.discard(self.uuid)
        if self._light_uuid is not None:
            get_map().remove_light_source(
                self._light_uuid,
                parent_event=parent_event.uuid if parent_event else None,
            )
            self._light_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)


class SacredWeapon(BaseAction):
    creates = (SacredWeaponEffect,)
    name: str = "Sacred Weapon"
    target_type: TargetType = TargetType.SELF
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    selected_weapon_uuid: UUID | None = None
    feature_owner_uuid: UUID
    costs: list[Cost] = Field(default_factory=lambda: feature_cost("channel_oath"))
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.paladin.sacred_weapon",
        )
    )

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """Each slot holding a weapon."""
        actor = Entity.get(self.source_entity_uuid)
        return tuple((ActionVariantFacet(key="form", value=slot.value, label=slot.value),)
                     for slot in WeaponSlot if actor is not None and actor.equipment.get_weapon(slot) is not None)

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "weapon_slot": WeaponSlot(selection_facet(selection, "form"))}

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(self.weapon_slot) if actor is not None else None
        if weapon is None or weapon.is_body_attack:
            return "Sacred Weapon requires a held weapon"
        return None

    def _create_declaration_event(self, parent_event=None, use_register=True):
        """Remember the exact weapon this declaration admits; `_apply` refuses a swapped one."""
        event = super()._create_declaration_event(parent_event, use_register)
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(self.weapon_slot) if actor is not None else None
        self.selected_weapon_uuid = weapon.uuid if weapon is not None else None
        return event

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(self.weapon_slot)
        if weapon is None or weapon.uuid != self.selected_weapon_uuid:
            return event.cancel(status_message="Exact weapon is no longer held")
        effect = event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            result = attach_feature_effect(
                self.feature_owner_uuid,
                weapon,
                SacredWeaponEffect(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=weapon.uuid,
                    effect_origin=effect.get_effect_origin(),
                ),
                effect,
            )
            if result is None or result.canceled:
                return effect.cancel(status_message="Sacred Weapon was rejected")
        return effect


PROTECTED_TYPES = frozenset(
    {
        CreatureType.ABERRATION,
        CreatureType.CELESTIAL,
        CreatureType.ELEMENTAL,
        CreatureType.FEY,
        CreatureType.FIEND,
        CreatureType.UNDEAD,
    }
)


class PurityOfSpirit(BaseCondition):
    description: str = "Permanent magical defense against attacks, charm and fear from the protected creature types."
    name: str = "Purity of Spirit"
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)

        def prevents(_entity, _selected, context):
            incoming = (context or {}).get("condition")
            source = (
                Entity.get(incoming.source_entity_uuid)
                if isinstance(incoming, BaseCondition)
                else None
            )
            return source is not None and source.creature_type in PROTECTED_TYPES

        def penalty(source_uuid, target_uuid=None, context=None):
            attacker = Entity.get(
                target_uuid if source_uuid == target.uuid else source_uuid
            )
            if attacker is not None and attacker.creature_type in PROTECTED_TYPES:
                return AdvantageModifier(
                    name="Purity of Spirit",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target_uuid,
                    use_register=False,
                )

        for name in ("Charmed", "Frightened"):
            target.add_condition_immunity_source(
                name, self.uuid, immunity_check=prevents
            )
        value = target.equipment.ac_bonus
        identity = value.to_target_contextual.add_advantage_modifier(
            ContextualAdvantageModifier(
                source_entity_uuid=target.uuid,
                name="Purity of Spirit",
                callable=penalty,
            )
        )
        return [(value.uuid, identity)], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event=None):
        target = Entity.get(self.target_entity_uuid)
        if target is not None:
            for name in ("Charmed", "Frightened"):
                target.remove_condition_immunity_source(name, self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)


def cleansing_candidates(target):
    candidates = []
    for condition in target.active_conditions_by_uuid.values():
        origin = condition.effect_origin
        if (
            origin is None
            or origin.kind is not EffectOriginKind.SPELL
            or ConditionTag.CONCENTRATION in condition.tags
            or isinstance(condition, SpatialConditionMembershipSource)
        ):
            continue
        parents = condition.additional_parent_conditions | (
            {condition.parent_condition} if condition.parent_condition else set()
        )
        if any(
            (parent := BaseCondition.get(identity)) is not None
            and parent.target_entity_uuid == target.uuid
            and (
                ConditionTag.CONCENTRATION not in parent.tags
                or isinstance(parent, SpatialConditionMembershipSource)
            )
            for identity in parents
        ):
            continue
        candidates.append(condition)
    return candidates


class CleansingTouch(BaseAction):
    entity_target_perception: EntityTargetPerception = (
        EntityTargetPerception.TOUCH_CONTACT
    )

    def get_physical_access(self):
        return PhysicalAccess.HAND

    def apply(self, *args, **kwargs):
        try:
            return super().apply(*args, **kwargs)
        finally:
            prepared = self._removal
            if prepared is not None and prepared.committed_result is None:
                BaseBlock.cancel_owned_condition_removals(
                    prepared, "Touch action did not commit"
                )
            self._removal = None

    name: str = "Cleansing Touch"
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    condition_uuid: UUID | None = None
    costs: list[Cost] = Field(default_factory=lambda: feature_cost("cleansing_touch"))
    _removal: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def get_range(self):
        return Range(type=RangeType.REACH, normal=5)

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """The supported spells on the actor and on the perceived allies within touch (plan §14.4).

        Never a whole-world scan: allies the actor does not perceive are not listed.
        """
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return ()
        recipients = [actor, *(ally for identity, record in scan.creatures.items()
                               if record.relationship is Relationship.ALLY
                               and max(abs(record.position[0] - scan.position[0]), abs(record.position[1] - scan.position[1])) <= 1
                               and (ally := Entity.get(identity)) is not None)]
        return tuple((ActionVariantFacet(key="form", value=str(condition.uuid), label=condition.get_display_name()),)
                     for recipient in recipients for condition in cleansing_candidates(recipient))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "condition_uuid": UUID(selection_facet(selection, "form"))}

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None or not any(
            condition.uuid == self.condition_uuid
            for condition in cleansing_candidates(target)
        ):
            return "Selected recipient-local spell is absent or unsupported"
        return None

    def _apply_costs(self, event):
        target = Entity.get(self.target_entity_uuid)
        condition = target.active_conditions_by_uuid.get(self.condition_uuid)
        self._removal = (
            prepare_exact_removals(target, [condition], event)
            if condition is not None and condition in cleansing_candidates(target)
            else None
        )
        if self._removal is None:
            return event.cancel(status_message="Selected spell removal was rejected")
        result = entity_action_economy_cost_applier(event, self.source_entity_uuid)
        if result.canceled:
            BaseBlock.cancel_owned_condition_removals(
                self._removal, "Cleansing Touch cost was rejected"
            )
        return result

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            BaseBlock.cancel_owned_condition_removals(
                self._removal, "Cleansing Touch was rejected"
            )
            return effect
        with BaseBlock.condition_removal_scope():
            BaseBlock.commit_owned_condition_removals(self._removal)
        BaseBlock.publish_owned_condition_removals(self._removal)
        return effect


class HolyNimbusEffect(BaseCondition):
    description: str = "Ten-turn moving light, enemy turn-start radiant damage and fiend/undead spell save advantage."
    name: str = "Holy Nimbus"
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS)
    )
    _light_uuid: UUID | None = PrivateAttr(default=None)

    def _apply(self, event):
        actor = Entity.get(self.target_entity_uuid)
        self._light_uuid = get_map().add_light_source(
            actor.position,
            bright_radius_feet=30,
            dim_radius_feet=30,
            anchor_uuid=actor.uuid,
            contribution_owner_uuid=self.uuid,
            parent_event=event.uuid,
        )

        def burn(boundary, _):
            enemy = Entity.get(boundary.source_entity_uuid)
            if (
                enemy is not None
                and enemy.is_deployed
                and actor.is_enemy(enemy)
                and grid_distance_feet(actor.position, enemy.position) <= 10
            ):
                enemy.receive_damage(
                    10,
                    DamageType.RADIANT,
                    actor.uuid,
                    parent_event=boundary.uuid,
                    effect_origin=self.effect_origin,
                )

        def advantage(source_uuid, target_uuid=None, context=None):
            cause = (context or {}).get(SAVING_THROW_CONTEXT_KEY)
            enemy = Entity.get(target_uuid)
            if (
                isinstance(cause, SavingThrowContext)
                and cause.cause_id.startswith("spell.")
                and enemy is not None
                and enemy.creature_type in (CreatureType.FIEND, CreatureType.UNDEAD)
            ):
                return AdvantageModifier(
                    name="Holy Nimbus",
                    value=AdvantageStatus.ADVANTAGE,
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target_uuid,
                    use_register=False,
                )

        handler = EventHandler(
            name="Holy Nimbus start-turn damage",
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT)
            ],
            event_processor=burn,
        )
        actor.add_event_handler(handler)
        modifiers = []
        for save in actor.saving_throws.get_blocks():
            identity = save.bonus.self_contextual.add_advantage_modifier(
                ContextualAdvantageModifier(
                    source_entity_uuid=actor.uuid,
                    name="Holy Nimbus",
                    callable=advantage,
                )
            )
            modifiers.append((save.bonus.uuid, identity))
        return modifiers, [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event=None):
        if self._light_uuid is not None:
            get_map().remove_light_source(
                self._light_uuid,
                parent_event=parent_event.uuid if parent_event else None,
            )
            self._light_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)


class HolyNimbus(BaseAction):
    creates = (HolyNimbusEffect,)
    name: str = "Holy Nimbus"
    target_type: TargetType = TargetType.SELF
    feature_owner_uuid: UUID
    costs: list[Cost] = Field(default_factory=lambda: feature_cost("holy_nimbus"))
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.paladin.holy_nimbus",
        )
    )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            actor = Entity.get(self.source_entity_uuid)
            result = attach_feature_effect(
                self.feature_owner_uuid,
                actor,
                HolyNimbusEffect(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=actor.uuid,
                    effect_origin=effect.get_effect_origin(),
                ),
                effect,
            )
            if result is None or result.canceled:
                return effect.cancel(status_message="Holy Nimbus was rejected")
        return effect


class CleansingTouchCapacity(BaseCondition):
    name: str = "Cleansing Touch Capacity"
    description: str = (
        "Owns the current CHA-based Cleansing Touch capacity, preserving spent uses."
    )
    resource_source_uuid: UUID
    spent_uses: int = 0
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )

    def refresh(self):
        actor = Entity.get(self.target_entity_uuid)
        resource = (
            actor.action_economy.resources.get("cleansing_touch")
            if actor is not None
            else None
        )
        if (
            resource is not None
            and str(self.resource_source_uuid) in resource.capacity_contributions
        ):
            self.spent_uses = max(self.spent_uses, resource.spent)
            resource.set_capacity_contribution(
                self.resource_source_uuid,
                max(1, actor.ability_scores.charisma.modifier),
            )
            resource.current = max(0, resource.maximum - self.spent_uses)

    def _apply(self, event):
        self.refresh()

        def changed(boundary, _):
            if boundary.event_type is EventType.ACTION_COSTS_COMMITTED:
                self.spent_uses += sum(
                    amount
                    for name, amount in boundary.named_resource_costs
                    if name == "cleansing_touch"
                )
            elif (
                boundary.event_type is EventType.REST_COMPLETED
                and boundary.rest_type == "long_rest"
            ):
                self.spent_uses = 0
            elif (
                boundary.event_type is EventType.REST_RESOURCES_RECOVERED
                and "cleansing_touch" in boundary.resource_names
            ):
                self.spent_uses = 0
            self.refresh()

        handler = EventHandler(
            name="Cleansing Touch CHA capacity",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=kind,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=self.target_entity_uuid,
                )
                for kind in (
                    EventType.ENTITY_LEVEL_ADDED,
                    EventType.ENTITY_LEVEL_REMOVED,
                    EventType.CONDITION_MEMBERSHIP_COMMITTED,
                )
            ]
            + [
                Trigger(
                    event_type=kind,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                )
                for kind in (
                    EventType.ACTION_COSTS_COMMITTED,
                    EventType.REST_COMPLETED,
                    EventType.REST_RESOURCES_RECOVERED,
                )
            ],
            event_processor=changed,
        )
        Entity.get(self.target_entity_uuid).add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


def refresh_cleansing_capacity(actor):
    for condition in actor.active_conditions_by_uuid.values():
        if isinstance(condition, CleansingTouchCapacity):
            condition.refresh()
