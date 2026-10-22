"""Abjuration spells - protection and defense.

Contains: Shield, MageArmor, ProtectionFromEnergy, Stoneskin, Counterspell,
          LesserRestoration, GreaterRestoration,
          ProtectionFromPoison, DeathWard, FreedomOfMovement,
          Resistance, ShieldOfFaith, Aid, Sanctuary, BeaconOfHope,
"""
from dnd.spells.reaction_costs import choose_reaction_spell_cost, commit_reaction_spell_cost
from dnd.core.spell_damage import roll_spell_damage
from dnd.spells.spell_utils import (apply_concentrating_zone, living_recipients_error, placement_error,
    selected_cast_level, spell_condition_profile, target_count_error)

from functools import partial
from types import MappingProxyType
from typing import Any, ClassVar, Dict, Literal, Optional, List, Set, Tuple
from uuid import UUID
from dnd.core.base_block import PreparedConditionRemovals
from dnd.core.creature_types import CreatureType
from dnd.conditions import Concentrating, prepare_control_removals, Blinded, Prone
from dnd.spells.spell_utils import condition_save
from dnd.core.life_types import LifeState
from dnd.core.creature_types import CreatureType
from dnd.core.base_actions import BaseAction, ActionEvent
from dnd.spatial.memberships import MembershipAreaCondition, SpatialConditionMembershipSource
from dnd.core.geometry import bresenham_line
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import WorldEdgeChannel
from dnd.types.spatial_effects import SpatialEffectAnchorKind, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind

from dnd.spells.spell_utils import target_turn_expiry_handler, spell_valid_positions
from pydantic import Field, PrivateAttr

from dnd.core.base_actions import (
    ActionEvent,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    BaseAction,
    CostType,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
    Cost,
)
from dnd.core.base_block import PreparedConditionApplication, BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration, ConditionApplicationEvent, OutcomeProtection, SpellProtectionRegistry, SpellProtection
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionRemovalTrigger,
    ConditionCategory,
    ConditionTag,
    DurationType,
)
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.effect_types import EffectOriginKind
from dnd.core.action_types import ActionSelection, ActionVariantFacet, selection_facet
from dnd.types.discovery import ActorScan, ScanRecord
from dnd.types.event_facts import GroupEntryKind, HandlerGroupDispatch
from dnd.core.events import Damage, Event, EventPhase, EventType, EventHandler, Trigger, RangeType, Range, EventQueue, SpatialChangeEvent, ForcedMovementEvent, PortalTransferEvent, TakeDamageEvent, InstantDeathEvent, D20RollResultEvent, HealRollResultEvent
from dnd.types.character_progression import OriginCapability
from dnd.types.actor import ConditionState, PendingSpatialReturn, SpatialDisposition
from dnd.types.abilities import AbilityName
from dnd.types.spell_suppression import SpellSuppression
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
    NumericalModifier,
    AutoHitStatus,
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
)
from dnd.core.geometry import bresenham_line
from dnd.core.elevation import support_distance_feet
from dnd.core.aoe import AoEShape, Sphere
from dnd.core.gridmap import CrossingChannel, get_map
from dnd.spatial.restraints import SpatialRestraintSource
from dnd.core.positioning import PositionPublicationError
from dnd.blocks.equipment import ArmorEquipEvent
from dnd.blocks.action_economy import ActionEconomyChannelCost
from dnd.core.equipment_types import UnarmoredAc

from dnd.core.dice import RollType, AttackOutcome, Dice, roll_die_face
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SpellInterruptionLogData
from dnd.core.saving_throw_types import DamageSaveContext
from dnd.entity import Entity, PreparedSpatialReturn
from dnd.core.values import (
    ModifiableValue,
    reading_with_value_row,
    Channel,
    Kind,
    add_modifier,
    parts,
    ValueRead,
    value_score,
)
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.actions import (
    commit_forced_movement,
    SpellAction,
    SpellEvent,
    AttackEvent,
    ShoveEvent,
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    Move,
)
from dnd.creature_transforms import (
    apply_incapacitated_transform,
    apply_unconscious_transform,
    remove_modifier_ownership,
)
from dnd.spells.content_metadata import (
    srd_action_identity,
    srd_condition_identity,
    srd_reaction_identity,
    srd_spell_identity,
)
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
    MAGIC_MISSILE_DAMAGE_EFFECT_ID,
    SANCTUARY_INTERRUPTION_OUTCOME_CODE,
)
from dnd.spatial.area_conditions import AreaCondition
from dnd.core.base_object import empty_set
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


class CounterspellReactionEvent(ActionEvent):
    """Observable resolution of one Counterspell reaction."""

    name: str = Field(default="Counterspell", description="Reaction event name.")
    event_type: EventType = Field(default=EventType.TRIGGER_EVENT, description="Reaction event category.")
    triggered_event_uuid: UUID = Field(description="Incoming spell event version that triggered the reaction.")
    triggered_lineage_uuid: UUID = Field(description="Incoming spell lineage interrupted or challenged.")
    incoming_spell_name: str = Field(description="Display name of the incoming spell.")
    incoming_spell_level: int = Field(ge=0, description="Level of the incoming cast.")
    counterspell_slot_level: int = Field(ge=3, description="Slot level spent on Counterspell.")
    automatic: bool = Field(description="Whether the selected slot guarantees interruption.")
    check_total: Optional[int] = Field(default=None, description="Spellcasting check total when required.")
    check_dc: Optional[int] = Field(default=None, description="Spellcasting check DC when required.")
    succeeded: bool = Field(description="Whether Counterspell interrupted the incoming spell.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a typed, subjectivity-filterable reaction log."""
        counterspeller_name = self.source_entity_name or "Unknown"
        original_caster_name = self.target_entity_name or "Unknown"
        result_text = "interrupts" if self.succeeded else "fails to interrupt"
        compact = (
            f"{counterspeller_name} uses Counterspell and {result_text} "
            f"{original_caster_name}'s {self.incoming_spell_name}"
        )
        data = SpellInterruptionLogData(
            outcome_code=self.outcome_code or COUNTERSPELL_FAILURE_OUTCOME_CODE,
            counterspeller_name=counterspeller_name,
            counterspeller_uuid=str(self.source_entity_uuid),
            original_caster_name=original_caster_name,
            original_caster_uuid=str(self.target_entity_uuid),
            spell_name=self.incoming_spell_name,
            incoming_spell_level=self.incoming_spell_level,
            counterspell_slot_level=self.counterspell_slot_level,
            automatic=self.automatic,
            check_total=self.check_total,
            check_dc=self.check_dc,
            succeeded=self.succeeded,
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_INTERRUPTION,
            source_name=counterspeller_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=original_caster_name,
            target_uuid=str(self.target_entity_uuid),
            compact=compact,
            verbose=compact,
            detailed=compact,
            data=data,
            success=self.succeeded,
        )


def _is_magic_missile_damage(event: Event) -> bool:
    """Return whether typed damage identity matches a Magic Missile dart."""
    return (
        isinstance(event, TakeDamageEvent)
        and event.effect_id == MAGIC_MISSILE_DAMAGE_EFFECT_ID
    )


class ShieldBuff(BaseCondition):
    """Apply Shield's short-lived AC bonus and Magic Missile block.

    The condition grants +5 AC, blocks Magic Missile damage while active, and
    removes itself at the start of the protected entity's next turn.
    """
    name: str = Field(default="Shield", description="Condition name.")
    description: str = Field(default="+5 AC until start of your next turn", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    outcome_protections: Tuple[OutcomeProtection, ...] = Field(
        default_factory=lambda: (
            OutcomeProtection(
                protection_id="dnd.spells.abjuration.ShieldBuff.magic_missile",
                blocked_effect_ids=frozenset({MAGIC_MISSILE_DAMAGE_EFFECT_ID}),
            ),
        ),
        description="Typed effects completely blocked while Shield is active.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target_uuid = self.target_entity_uuid
        condition_uuid = self.uuid
        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target_uuid,
            name="Shield",
            value=5
        )
        mod_uuid = add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        def shield_magic_missile_blocker(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Block Magic Missile damage while Shield is active."""
            _ = handler_source_uuid
            if event.target_entity_uuid != target_uuid:
                return None
            if not _is_magic_missile_damage(event):
                return None
            return event.cancel(status_message=f"Shield blocks Magic Missile dart",
                                intercepted_by_condition_uuid=condition_uuid)

        mm_handler = EventHandler(
            name="Shield: Magic Missile Block",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EXECUTION,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=shield_magic_missile_blocker
        )
        target.add_event_handler(mm_handler)
        handler_uuids.append(mm_handler.uuid)

        def shield_attack_interception(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Attribute only a miss whose result depended on this AC modifier."""
            if (not isinstance(event, AttackEvent) or event.dice_roll is None or event.ac is None
                    or event.attack_outcome is not AttackOutcome.MISS
                    or event.intercepted_by_condition_uuid is not None
                    or event.dice_roll.auto_hit_status is not AutoHitStatus.NONE
                    or event.dice_roll.total < event.ac.normalized_score - mod.value):
                return None
            return event.with_updates(intercepted_by_condition_uuid=condition_uuid)

        interception = EventHandler(name="Shield: Attack Interception", source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EXECUTION,
                                        event_target_entity_uuid=target_uuid)],
            event_processor=shield_attack_interception)
        target.add_event_handler(interception)
        handler_uuids.append(interception.uuid)

        def shield_turn_start_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Remove Shield buff at the start of the caster's turn."""
            _ = handler_source_uuid
            if event.source_entity_uuid != target_uuid:
                return None
            entity = Entity.get(target_uuid)
            if entity and "Shield" in entity.active_conditions:
                entity.remove_condition("Shield", parent_event=event)
            return None

        handler = EventHandler(
            name="Shield: Turn Start Removal",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=target_uuid
                )
            ],
            runs_while_owner_inactive=True,
            event_processor=shield_turn_start_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Shield: +5 AC to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, handler_uuids, [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}


def shield_reaction_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Resolve the Shield reaction when it can change an incoming event.

    Attack triggers wait until the attack roll exists and only spend resources
    if +5 AC turns a normal hit into a miss. Magic Missile damage triggers spend
    the same resources and cancel the triggering dart while the resulting
    `ShieldBuff` blocks later darts in the same spell.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity) or entity.is_spellcasting_blocked():
        return None

    if "Shield" in entity.active_conditions:
        return None

    if not entity.action_economy.can_afford("reactions", 1):
        return None

    payment = choose_reaction_spell_cost(entity,"spell.shield",1)
    if payment is None:
        return None

    if isinstance(event, AttackEvent) and event.ac:
        if event.dice_roll is None or event.attack_outcome is None:
            return None

        if event.attack_outcome != AttackOutcome.HIT:
            return None

        if event.dice_roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            return None

        current_ac = event.ac.normalized_score
        if event.dice_roll.total >= current_ac + 5:
            return None

    elif not _is_magic_missile_damage(event):
        return None

    with BaseBlock.condition_removal_scope():
        buff = ShieldBuff(source_entity_uuid=source_entity_uuid, target_entity_uuid=source_entity_uuid)
        prepared = entity.prepare_condition_application(buff, parent_event=event)
        if not isinstance(prepared, PreparedConditionApplication):
            return None
        if not commit_reaction_spell_cost(entity, payment, event):
            entity.cancel_condition_application(prepared, "Shield reaction payment refused")
            return None
        entity.commit_condition_application(prepared)
        entity.publish_condition_application(prepared)
        if isinstance(event, AttackEvent) and event.ac is not None:
            return event.with_updates(ac=reading_with_value_row(event.ac, NumericalModifier.create(
                source_entity_uuid=source_entity_uuid, target_entity_uuid=source_entity_uuid,
                name="Shield (reaction)", value=5)), attack_outcome=AttackOutcome.MISS,
                intercepted_by_condition_uuid=buff.uuid,
                status_message=f"{entity.name} casts Shield (+5 AC, attack blocked)")
        return event.cancel(status_message=f"{entity.name} casts Shield, blocking Magic Missile",
                            intercepted_by_condition_uuid=buff.uuid)


@srd_reaction_identity(
    content_id="reaction.spell.shield",
    display_name="Shield",
    description=(
        "Use a reaction and a spell slot to defend against an attack or "
        "Magic Missile."
    ),
    source_page=180,
    sort_order=20,
    icon_key="reaction.shield",
)
class ShieldReactionHandler(EventHandler):
    """Direct player-toggleable Shield reaction behavior."""
    creates = (ShieldBuff,)


SHIELD_REACTION_DECLARATION = get_content_declaration(
    ShieldReactionHandler,
)


def create_shield_reaction_handler(
    source_entity_uuid: UUID,
) -> ShieldReactionHandler:
    """Create a Shield reaction handler for an entity.

    The handler listens for attack execution events and Magic Missile damage
    events that target the entity.
    """
    return ShieldReactionHandler(
        name="Shield",
        semantic_key="reaction.spell.shield",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION,
                event_target_entity_uuid=source_entity_uuid
            ),
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EXECUTION,
                event_target_entity_uuid=source_entity_uuid
            )
        ],
        event_processor=shield_reaction_processor,
        player_toggleable=True
    )


def register_shield_reaction(entity: Entity) -> None:
    """Register the Shield reaction handler on an entity.

    The entity must be a spellcaster with spell slots.
    The handler can be toggled via entity.set_handler_enabled("Shield", enabled).
    """
    handler = create_shield_reaction_handler(entity.uuid)
    entity.add_event_handler(handler)


class MageArmorCondition(BaseCondition):
    """Set the target's unarmored AC calculation to Mage Armor.

    The condition applies only to unarmored targets, stores the previous
    unarmored AC mode, and registers an armor-equip watcher that ends the
    condition when body armor is equipped.
    """
    name: str = Field(default="Mage Armor", description="Condition name.")
    description: str = Field(default="AC equals 13 + DEX modifier when unarmored", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    _old_unarmored_type: Optional[str] = PrivateAttr(default=None)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target_entity, Entity):
            return [], [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        if not target_entity.equipment.is_unarmored():
            return [], [], [], [], declaration_event.cancel(status_message="Target is wearing armor - Mage Armor has no effect")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        self._old_unarmored_type = target_entity.equipment.unarmored_ac_type.value
        target_entity.equipment.unarmored_ac_type = UnarmoredAc.MAGIC_ARMOR

        condition_target_uuid = self.target_entity_uuid

        def mage_armor_equip_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """End Mage Armor when committed equipment actually counts as armor."""
            _ = handler_source_uuid

            if event.source_entity_uuid != condition_target_uuid:
                return None

            entity = Entity.get(condition_target_uuid)
            if not entity:
                return None

            if "Mage Armor" not in entity.active_conditions:
                return None

            if isinstance(event, ArmorEquipEvent) and not entity.equipment.is_unarmored():
                entity.remove_condition("Mage Armor", parent_event=event)
                return event.with_updates(
                    status_message=(
                        f"{entity.name}'s Mage Armor ends (equipped armor)"
                    ),
                )

            return None

        handler = EventHandler(
            name="Mage Armor Watch",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ARMOR_EQUIP,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=mage_armor_equip_processor
        )

        target_entity.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Mage Armor to {target_entity.name} (AC = 13 + DEX)"
        )

        return outs, handler_uuids, [], [], effect_event

    def _remove(self, _removal_event: Optional[Event] = None) -> None:
        """Restore the old unarmored AC type on removal."""

        if not self.target_entity_uuid:
            return

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity or not isinstance(target_entity, Entity):
            return

        if self._old_unarmored_type:
            try:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc(self._old_unarmored_type)
            except ValueError:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE
        else:
            target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE


@srd_spell_identity(
    content_id="spell.mage_armor",
    display_name="Mage Armor",
    description="Protect an unarmored creature with magical armor.",
    school="abjuration",
    level=1,
    source_page=160,
    sort_order=10,
)
class MageArmor(SpellAction):
    """Apply Mage Armor to an unarmored self or ally target."""
    creates = (*SpellAction.creates, MageArmorCondition)
    name: str = Field(default="Mage Armor", description="Spell name.")
    description: str = Field(default="Target's AC becomes 13 + DEX modifier", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Mage Armor's protective AC condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.mage_armor",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.mage_armor.ac_floor",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.mage_armor",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.MageArmorCondition"}),
                ),
            ),
        )

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The caster, or a creature in touch range, who wears no armor."""
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None:
            return "Caster or target not found"
        if target.uuid != self.source_entity_uuid and (error := self.target_position_error(target.position)) is not None:
            return error
        return None if target.equipment.is_unarmored() else "Target is wearing armor"

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mage Armor condition to target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        condition = MageArmorCondition(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Applying Mage Armor to {target.name}"
        )

        result = target.add_condition(condition, parent_event=effect_event)
        if result is None or result.canceled:
            return effect_event.cancel(status_message="Failed to apply Mage Armor")

        return effect_event.with_updates(
            status_message=f"{self.name} cast on {target.name} (AC = 13 + DEX)"
        )


class ProtectionFromEnergyEffect(BaseCondition):
    """Grant resistance to one selected energy damage type."""
    name: str = Field(default="Protection from Energy", description="Condition name.")
    description: str = Field(default="Resistant to one energy type", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    energy_type: DamageType = Field(default=DamageType.FIRE, description="Damage type resisted by the condition.")

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"energy_type": self.energy_type})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        resist_mod = ResistanceModifier(
            name=f"Protection from Energy ({self.energy_type.value})",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=self.energy_type
        )
        mod_uuid = add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, resist_mod)
        outs.append((target.health.damage_reduction.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied {self.energy_type.value} resistance to {target.name}"
        )

        return outs, [], [], [], effect_event


class ProtectionFromEnergy(SpellAction):
    """Apply concentration-linked resistance to one energy type.

    The selected type must be acid, cold, fire, lightning, or thunder.
    """
    creates = (*SpellAction.creates, ProtectionFromEnergyEffect)
    name: str = Field(default="Protection from Energy", description="Spell name.")
    description: str = Field(default="Grant resistance to one energy type (acid/cold/fire/lightning/thunder)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")
    chosen_energy_type: DamageType = Field(default=DamageType.FIRE, description="Energy damage type selected for resistance.")

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="damage_type", value=energy, label=energy.title()),)
                     for energy in ("acid", "cold", "fire", "lightning", "thunder"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        energy = next((facet.value for facet in selection.facets if facet.key == "damage_type"), None)
        return {**super()._selection_overrides(selection),
                "chosen_energy_type": DamageType(energy.title()) if energy else self.chosen_energy_type}

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if isinstance(event, SpellEvent):
            event.effect_id = f"support.protection_from_energy.{self.chosen_energy_type.value.lower()}"
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Protection from Energy's resistance condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        energy_key = self.chosen_energy_type.value.lower()
        return ActionTargetEffectProfile(
            semantic_id=f"support.protection_from_energy.{energy_key}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"support.protection_from_energy.{energy_key}",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=(f"selected_target.resistance.{energy_key}",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.ProtectionFromEnergyEffect"}),
                ),
            ),
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The caster or a creature in touch range, and one of the five energy types."""
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None:
            return "Caster or target not found"
        if target.uuid != self.source_entity_uuid and (error := self.target_position_error(target.position)) is not None:
            return error
        if self.chosen_energy_type not in (DamageType.ACID, DamageType.COLD, DamageType.FIRE,
                                           DamageType.LIGHTNING, DamageType.THUNDER):
            return (f"Invalid energy type: {self.chosen_energy_type.value}. "
                    "Must be acid, cold, fire, lightning, or thunder.")
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Protection from Energy - grants resistance to chosen energy type."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")


        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        protection = ProtectionFromEnergyEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            energy_type=self.chosen_energy_type
        )
        effect_event = self.apply_owned_condition(effect_event, protection)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{self.name} ({self.chosen_energy_type.value}) cast on {target.name}"
        )


class StoneskinEffect(BaseCondition):
    """Grant resistance to bludgeoning, piercing, and slashing damage.

    The current engine does not track magical versus nonmagical weapon damage,
    so the condition applies to all B/P/S damage.
    """
    name: str = Field(default="Stoneskin", description="Condition name.")
    description: str = Field(default="Resistant to bludgeoning, piercing, and slashing damage", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        for damage_type in [DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING]:
            resist_mod = ResistanceModifier(
                name=f"Stoneskin ({damage_type.value})",
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
                value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type
            )
            mod_uuid = add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, resist_mod)
            outs.append((target.health.damage_reduction.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied physical resistance to {target.name}"
        )

        return outs, [], [], [], effect_event


class Stoneskin(SpellAction):
    """Apply concentration-linked physical damage resistance.

    Because magical weapon provenance is not modeled here, this implementation
    applies to all bludgeoning, piercing, and slashing damage.
    """
    creates = (*SpellAction.creates, StoneskinEffect)
    name: str = Field(default="Stoneskin", description="Spell name.")
    description: str = Field(default="Grant resistance to B/P/S damage", description="Rules-facing spell summary.")
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Stoneskin's physical resistance condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.stoneskin",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.stoneskin.physical_resistance",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=(
                        "selected_target.resistance.bludgeoning",
                        "selected_target.resistance.piercing",
                        "selected_target.resistance.slashing",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.StoneskinEffect"}),
                ),
            ),
        )

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The caster, or a creature in touch range."""
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None:
            return "Caster or target not found"
        return None if target.uuid == self.source_entity_uuid else self.target_position_error(target.position)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stoneskin - grants B/P/S resistance."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")


        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        stoneskin = StoneskinEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, stoneskin)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{self.name} cast on {target.name}"
        )


def _complete_counterspell_reaction(
    reaction: CounterspellReactionEvent,
    *,
    automatic: bool,
    succeeded: bool,
    check_total: Optional[int] = None,
    check_dc: Optional[int] = None,
) -> CounterspellReactionEvent:
    """Emit one complete typed reaction event for observation and combat logs."""
    outcome_code = (
        COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
        if succeeded
        else COUNTERSPELL_FAILURE_OUTCOME_CODE
    )
    effect = reaction.phase_to(EventPhase.EFFECT,
        automatic=automatic, succeeded=succeeded, check_total=check_total, check_dc=check_dc,
        outcome_code=outcome_code, status_message="Counterspell reaction resolved.")
    if effect.canceled:
        return effect
    return effect.phase_to(EventPhase.COMPLETION, status_message="Counterspell reaction completed.")


def counterspell_reaction_processor(
    event: Event,
    source_entity_uuid: UUID,
    *,
    learned_spell_ref: ContentRef | None = None,
) -> Optional[Event]:
    """Attempt to counter a visible spell cast within sixty feet.

    The handler spends a reaction and an available spell slot. Slots at least as
    high as the incoming cast level counter automatically; lower third-level
    slots use a spellcasting ability check against DC 10 + cast level.
    """
    if event.event_type != EventType.CAST_SPELL:
        return None

    # Counterspell interrupts the cast once, at its root execution; per-target
    # applications of the same spell are not new casts (bug E).
    if isinstance(event, SpellEvent) and event.application is not None:
        return None

    if event.source_entity_uuid == source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity) or entity.is_spellcasting_blocked():
        return None

    contact = entity.senses.entities.get(event.source_entity_uuid)
    if contact is None or not contact.visual:
        return None

    spell_caster = Entity.get(event.source_entity_uuid)
    if not spell_caster:
        return None
    if not entity.is_enemy(spell_caster):
        return None
    distance = entity.senses.get_feet_distance(spell_caster.position)
    if distance > 60:
        return None

    if not entity.action_economy.can_afford("reactions", 1):
        return None

    if not isinstance(event, SpellEvent):
        return None
    spell_cast_level = event.cast_at_level or event.spell_level

    payment=choose_reaction_spell_cost(entity,"spell.counterspell",3,preferred_rank=max(3,spell_cast_level))
    if payment is None:
        return None
    reaction = CounterspellReactionEvent(
        source_entity_uuid=entity.uuid, target_entity_uuid=spell_caster.uuid,
        source_entity_name=entity.name, target_entity_name=spell_caster.name,
        parent_event=event.uuid, triggered_event_uuid=event.uuid,
        triggered_lineage_uuid=event.lineage_uuid, incoming_spell_name=event.name,
        incoming_spell_level=spell_cast_level, counterspell_slot_level=payment.cast_rank,
        automatic=payment.cast_rank >= spell_cast_level, succeeded=False, use_register=False)
    reaction = EventQueue.publish_declaration(reaction)
    if reaction.canceled:
        return None
    if not commit_reaction_spell_cost(entity, payment, event):
        return None
    reaction = reaction.phase_to(EventPhase.EXECUTION)
    if reaction.canceled:
        return None
    if payment.cast_rank >= spell_cast_level:
        resolved = _complete_counterspell_reaction(
            reaction,
            automatic=True,
            succeeded=True,
        )
        if resolved.canceled:
            return None
        return event.cancel(
            status_message="The spell was interrupted.",
            outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
            outcome_source_entity_uuid=entity.uuid,
        )

    dc = 10 + spell_cast_level
    ability_name: AbilityName = entity.spellcasting.spellcasting_ability
    if payment.source_id is not None:
        ability_name=entity.spellcasting.resolve_spellcasting_ability(payment.source_id)
    check_total = entity.roll_d20(entity.ability_check_bonus(None, ability_name),
        RollType.CHECK, ability_name=ability_name, parent_event=event.uuid).total
    if check_total >= dc:
        resolved = _complete_counterspell_reaction(
            reaction,
            automatic=False,
            succeeded=True,
            check_total=check_total,
            check_dc=dc,
        )
        if resolved.canceled:
            return None
        return event.cancel(
            status_message="The spell was interrupted.",
            outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
            outcome_source_entity_uuid=entity.uuid,
        )
    _complete_counterspell_reaction(
        reaction,
        automatic=False,
        succeeded=False,
        check_total=check_total,
        check_dc=dc,
    )
    return None


@srd_reaction_identity(
    content_id="reaction.spell.counterspell",
    display_name="Counterspell",
    description="Interrupt a visible creature while it casts a spell.",
    source_page=131,
    sort_order=10,
)
class CounterspellReactionHandler(EventHandler):
    """Authenticated reaction behavior that resolves Counterspell."""


COUNTERSPELL_REACTION_DECLARATION = get_content_declaration(
    CounterspellReactionHandler,
)
ABJURATION_REACTION_DECLARATIONS_BY_CLASS = MappingProxyType({
    ShieldReactionHandler: SHIELD_REACTION_DECLARATION,
    CounterspellReactionHandler: COUNTERSPELL_REACTION_DECLARATION,
})


def create_counterspell_reaction_handler(
    source_entity_uuid: UUID,
    *,
    learned_spell_ref: ContentRef | None = None,
) -> CounterspellReactionHandler:
    """Create a Counterspell reaction handler for an entity."""
    return CounterspellReactionHandler(
        name="Counterspell",
        semantic_key="reaction.spell.counterspell",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION,
            )
        ],
        event_processor=(
            counterspell_reaction_processor
            if learned_spell_ref is None
            else partial(
                counterspell_reaction_processor,
                learned_spell_ref=learned_spell_ref,
            )
        ),
        player_toggleable=True
    )


def register_counterspell_reaction(entity: Entity) -> None:
    """Register the Counterspell reaction handler on an entity."""
    handler = create_counterspell_reaction_handler(entity.uuid)
    entity.add_event_handler(handler)


GLOBE_ZONE_CONTENT_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.spell.globe_of_invulnerability",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)


class GlobeZone(AreaCondition):
    """Maintain Globe of Invulnerability's immobile spell-protection area.

    The globe stays at its cast position, blocks spells by base spell level
    rather than upcast level, includes cantrips, and only blocks effects cast
    from outside the barrier.
    """
    name: str = Field(default="Globe of Invulnerability Zone", description="Condition name.")
    description: str = Field(default="Immobile sphere blocks spells level 5 or lower", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    content_ref: ContentRef = Field(default=GLOBE_ZONE_CONTENT_REF)
    has_visible_presence: bool = True
    position: Tuple[int, int]
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.FIELD)
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.OVERLAPPING,
    )
    area: AoEShape = Sphere(radius_feet=10)
    max_blocked_level: int = Field(default=5, description="Highest base spell level blocked by the globe.")

    model_config = {"arbitrary_types_allowed": True}

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Event]:
        modifiers, handler_uuids, children, spatial_handlers, effect = super()._apply(
            declaration_event,
        )

        blocker = self._create_spell_blocker()
        EventQueue.add_event_handler(blocker)
        handler_uuids.append(blocker.uuid)

        cond_blocker = self._create_condition_blocker()
        EventQueue.add_event_handler(cond_blocker)
        handler_uuids.append(cond_blocker.uuid)

        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(self.affected_positions),
            max_blocked_level=self.max_blocked_level,
        ))

        return modifiers, handler_uuids, children, spatial_handlers, effect

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release this globe's spell-protection registration."""
        SpellProtectionRegistry.unregister(self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)

    def _create_spell_blocker(self) -> EventHandler:
        """Cancel low-level spells cast from outside into the protected area."""
        globe = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type not in (EventType.CAST_SPELL, EventType.BASE_ACTION):
                return None
            if not isinstance(event, SpellEvent) or event.weapon_attack_slot is not None:
                return None

            base_level = event.spell_level
            if base_level > globe.max_blocked_level:
                return None

            source_position = event.effect_source_position or event.source_position
            if source_position is None or source_position in globe.affected_positions:
                return None

            if event.phase is EventPhase.EFFECT and event.resolved_area_positions is not None:
                excluded = tuple(position for position in event.resolved_area_positions
                    if position in globe.affected_positions)
                if excluded:
                    return event.with_updates(
                        resolved_area_positions=tuple(position for position in event.resolved_area_positions
                            if position not in globe.affected_positions),
                        suppressions=(*event.suppressions, SpellSuppression(
                            provider_uuid=globe.uuid, positions=excluded)),
                    )

            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                target_position = (event.target_position if event.target_kind == "object"
                    else target.position if target else None)
                if target_position is not None and target_position in globe.affected_positions:
                    return event.cancel(
                        status_message=f"Globe of Invulnerability blocks L{base_level} spell",
                        outcome_code="spell.globe_of_invulnerability.blocked",
                        suppressions=(*event.suppressions, SpellSuppression(
                            provider_uuid=globe.uuid, positions=(target_position,))),
                    )

            return None

        return EventHandler(
            name="Globe Spell Blocker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=kind, event_phase=phase)
                for kind in (EventType.CAST_SPELL, EventType.BASE_ACTION, EventType.EFFECT_APPLICATION)
                for phase in (EventPhase.EXECUTION, EventPhase.EFFECT)],
            event_processor=processor
        )

    def _create_condition_blocker(self) -> EventHandler:
        """Block low-level magical conditions applied inside the globe.

        Conditions inherit immutable spell provenance when declared, so this
        rule never searches event registries or reconstructs ancestry.
        """
        globe = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, ConditionApplicationEvent):
                return None

            condition = event.condition
            if not condition.magical_origin:
                return None

            target_pos: Optional[Tuple[int, int]] = None
            target_entity = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            if target_entity:
                target_pos = target_entity.position
            else:
                grid = get_map()
                tile = grid.get_tile_by_uuid(event.target_entity_uuid) if event.target_entity_uuid else None
                if tile:
                    target_pos = tile.position

            if target_pos is None or target_pos not in globe.affected_positions:
                return None

            origin = condition.effect_origin
            if (
                origin is None
                or origin.kind is not EffectOriginKind.SPELL
                or origin.base_spell_level is None
                or origin.source_position is None
            ):
                return None

            spell_level = origin.base_spell_level
            source_pos = origin.source_position

            if spell_level > globe.max_blocked_level:
                return None

            if source_pos in globe.affected_positions:
                return None

            return event.cancel(
                status_message=f"Globe of Invulnerability blocks magical condition (L{spell_level} spell)"
            )

        return EventHandler(
            name="Globe Condition Blocker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.DECLARATION
            )],
            event_processor=processor
        )


class GlobeOfInvulnerability(SpellAction):
    """Create an immobile concentration globe that blocks lower-level spells.

    Upcasting raises the maximum blocked base spell level by one per slot above
    sixth.
    """
    creates = (*SpellAction.creates, GlobeZone)
    name: str = Field(default="Globe of Invulnerability", description="Spell name.")
    description: str = Field(default="10ft sphere blocks spells L5 or lower, concentration", description="Rules-facing spell summary.")
    spell_level: int = Field(default=6, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Self range used by action discovery and validation.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        upcast_bonus = self.get_upcast_bonus()
        max_blocked = 5 + upcast_bonus

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Globe of Invulnerability (blocks L{max_blocked} and below)"
        )
        if effect_event.canceled:
            return effect_event

        zone = GlobeZone(
            source_entity_uuid=caster.uuid,
            position=caster.position,
            faction=caster.faction,
            max_blocked_level=max_blocked,
            effect_origin=execution_event.get_effect_origin(),
        )
        zone_result = zone.activate(parent_event=effect_event)
        if zone_result is None or zone_result.canceled or not zone.applied:
            return execution_event.cancel(
                status_message="Globe of Invulnerability could not be installed",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        return effect_event.with_updates(
            status_message=f"Globe of Invulnerability active — blocks spells L{max_blocked} and below"
        )


class BanishedCondition(BaseCondition):
    """Retain one absent actor and the authored plane-dependent return rule."""
    name: str = "Banished"
    description: str = "Absent from the battlefield until return or completed home-plane banishment"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    agency_denial: ConditionAgencyDenial = ConditionAgencyDenial.FULL_TURN
    temporary_demiplane: bool = True
    original_plane_id: str = "material"
    _prepared_return: PreparedSpatialReturn | None = PrivateAttr(default=None)
    _pending_return: PendingSpatialReturn | None = PrivateAttr(default=None)
    _terminal_departure: bool = PrivateAttr(default=False)
    _permanent_departure: bool = PrivateAttr(default=False)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None or not target.is_deployed:
            return [], [], [], [], declaration_event.cancel(status_message="Target is not present")
        self.original_plane_id = target.current_plane_id
        self.temporary_demiplane = target.native_plane_id == target.current_plane_id
        self.agency_denial = (ConditionAgencyDenial.FULL_TURN if self.temporary_demiplane
                             else ConditionAgencyDenial.NONE)
        target.current_plane_id = "banishment_demiplane" if self.temporary_demiplane else target.native_plane_id
        target.suspend_spatial_presence(parent_event=declaration_event.uuid)
        modifiers = (apply_incapacitated_transform(target, name=self.name,
            effect_source_uuid=self.source_entity_uuid) if self.temporary_demiplane else [])
        try:
            effect = declaration_event.phase_to(EventPhase.EFFECT,
                status_message=f"{target.name} leaves the battlefield")
        except BaseException:
            remove_modifier_ownership(modifiers)
            raise
        return modifiers, [], [], [], effect

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if self.applied:
            return
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return
        target.current_plane_id = self.original_plane_id
        if not target.is_spatially_suspended:
            return
        try:
            target.restore_spatial_presence(target.position,
                parent_event=parent_event.uuid if parent_event else None)
        except PositionPublicationError:
            if not target.is_deployed or target.is_spatially_suspended:
                raise

    def prepare_removal_state(self, event: Event) -> Event:
        release = BaseBlock._terminal_release.get()
        self._terminal_departure = release is not None and release.entity_uuid == self.target_entity_uuid
        self._permanent_departure = not self.temporary_demiplane and self.duration.is_expired
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if (target is not None and target.is_spatially_suspended
                and not self._terminal_departure and not self._permanent_departure):
            self._prepared_return = target.prepare_spatial_return(parent_event=event.uuid,
                reserved=BaseBlock.prepared_return_reservations())
            if self._prepared_return is None:
                self._pending_return = PendingSpatialReturn(target.position, self.original_plane_id, event.uuid)
        return event

    def cancel_prepared_removal(self, reason: str) -> None:
        self._prepared_return = None
        self._pending_return = None
        self._terminal_departure = self._permanent_departure = False

    def prepared_removal_occupancies(self) -> tuple[tuple[int, int], ...]:
        return (self._prepared_return.position,) if self._prepared_return is not None else ()

    def validate_prepared_removal(self) -> bool:
        prepared = self._prepared_return
        return prepared is None or prepared.entity.validate_spatial_return(prepared)

    def _remove(self, event: Event | None = None) -> Event | None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and not self._terminal_departure:
            if self._permanent_departure:
                target.spatial_disposition = SpatialDisposition.HOME_PLANE
            elif self._prepared_return is not None:
                target.commit_spatial_return(self._prepared_return)
                target.current_plane_id = self.original_plane_id
            elif self._pending_return is not None:
                target.pending_spatial_return = self._pending_return
                target.spatial_disposition = SpatialDisposition.RETURN_PENDING
        return event

    def on_membership_changed(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied:
            if self.temporary_demiplane and target is not None:
                target.remove_condition("Concentrating", parent_event=event)
            return
        prepared, self._prepared_return = self._prepared_return, None
        pending, self._pending_return = self._pending_return, None
        if prepared is not None:
            try:
                prepared.entity.publish_spatial_return(prepared)
            except PositionPublicationError:
                if not (prepared.committed and prepared.entity.is_deployed
                        and not prepared.entity.is_spatially_suspended):
                    raise
        elif pending is not None and target is not None:
            target.retain_pending_spatial_return(pending)

class Banishment(SpellAction):
    """Banish one failed-save target and link it to concentration.

    Upcasting increases the multi-target count, while each individual target
    resolves a Charisma save through the action convolution path.
    """
    creates = (*SpellAction.creates, BanishedCondition)
    name: str = Field(default="Banishment", description="Spell name.")
    description: str = Field(default="CHA save or banished (removed from play), concentration", description="Rules-facing spell summary.")
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for each target.",
    )
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    allow_same_target: bool = False

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Banishment's save-based removal branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.banishment",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.banishment.banished",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="charisma",
                    condition_fact_ids=("selected_target.condition.banished",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.BanishedCondition"}),
                ),
            ),
        )

    def get_multi_target_count(self) -> int:
        """1 target base + 1 per level above 4th."""
        return 1 + self.get_upcast_bonus()

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Seen, present creatures within range, at most one more per slot level above 4th."""
        source = Entity.get(self.source_entity_uuid)
        if source is None or not source.is_deployed:
            return "Caster is not present"
        error = target_count_error(self, selection, 1 + max(0, selected_cast_level(self, selection) - self.spell_level))
        if error is not None:
            return error
        grid = get_map()
        for identity in selection.target_uuids:
            target = Entity.get(identity)
            if target is None or not target.is_deployed:
                return "Target is not present"
            record = scan.creatures.get(identity)
            visible = (source.senses.visual_access.normalized_score > 0 if source is target
                       else record is not None and record.visual)
            if not visible:
                return "Caster cannot see a chosen creature"
            distance = support_distance_feet(source.position, grid.get_support_elevation_feet(source.position),
                target.position, grid.get_support_elevation_feet(target.position))
            if distance > self.effective_range:
                return f"Target out of range ({distance}ft)"
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        owner = self.get_concentration_owner()
        if (self.cast_concentrating_uuid is not None
                and (owner is None or self.cast_concentrating_uuid not in owner.active_conditions_by_uuid)):
            return execution_event.phase_to(EventPhase.EFFECT, status_message="Banishment concentration already ended")
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        effect_event, _save_roll, success = self.resolve_saving_throw(
            execution_event, caster=caster, target=target, ability_name="charisma", dc=dc)

        if success:
            return effect_event.with_updates(
                status_message=f"{target.name} resists Banishment (CHA save)"
            )

        banished = BanishedCondition(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid, effect_origin=execution_event.get_effect_origin(),
        )
        return self.apply_owned_condition(effect_event, banished)

_LESSER_RESTORATION_CONDITIONS = ("Blinded", "Deafened", "Paralyzed", "Poisoned")
_GREATER_RESTORATION_CONDITIONS = (
    "Charmed", "Poisoned", "Blinded", "Deafened", "Paralyzed", "Stunned", "Frightened"
)


def _remove_first_condition_by_name(
    target: Entity,
    condition_names: Tuple[str, ...],
    parent_event: Event,
) -> Optional[str]:
    """Cure one native family owner, respecting shared children and vetoes."""
    for condition_name in condition_names:
        condition = next((row for row in target.active_conditions_by_uuid.values()
            if row.name == condition_name or condition_name in row.immunity_names), None)
        if condition is None:
            continue
        root = condition
        while root.parent_condition is not None:
            parent = target.active_conditions_by_uuid.get(root.parent_condition)
            if parent is None:
                break
            root = parent
        return condition_name if target.remove_condition_by_uuid(root.uuid, parent_event=parent_event) else None
    return None


def _remove_first_condition_by_tag(
    target: Entity,
    condition_tag: ConditionTag,
    parent_event: Event,
) -> Optional[str]:
    """Remove the first active condition carrying the requested condition tag."""
    for condition_name, condition in list(target.active_conditions.items()):
        if condition_tag in condition.tags:
            target.remove_condition(condition_name, parent_event=parent_event)
            return condition_name
    return None


def _reduce_exhaustion(
    target: Entity,
    source_entity_uuid: UUID,
    parent_event: Event,
) -> Optional[str]:
    """Reduce Exhaustion by one level, removing it at level one."""
    condition = target.active_conditions.get("Exhaustion")
    if condition is None or ConditionTag.EXHAUSTION not in condition.tags:
        return None

    previous_level = getattr(condition, "level", None)
    if not isinstance(previous_level, int):
        return None
    if not target.reduce_condition_level("Exhaustion", parent_event=parent_event):
        return None
    if previous_level > 1:
        return f"Exhaustion reduced to level {previous_level - 1}"
    return "Exhaustion"


class LesserRestoration(SpellAction):
    """Remove one lesser restoration condition or disease from a touched target."""
    name: str = Field(default="Lesser Restoration", description="Spell name.")
    description: str = Field(default="Touch: remove one disease or one of blinded, deafened, paralyzed, or poisoned", description="Rules-facing restoration summary.")
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Lesser Restoration on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        removed = _remove_first_condition_by_name(
            target=target,
            condition_names=_LESSER_RESTORATION_CONDITIONS,
            parent_event=effect_event,
        )
        if removed is None:
            removed = _remove_first_condition_by_tag(
                target=target,
                condition_tag=ConditionTag.DISEASE,
                parent_event=effect_event,
            )

        status = f"Removed {removed}" if removed else "No removable condition found"
        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Lesser Restoration: {status}"
        )


class GreaterRestoration(SpellAction):
    """Remove one supported major debility or curse from a touched target.

    The current engine support list is represented by
    `_GREATER_RESTORATION_CONDITIONS`, one petrification effect, one curse,
    one exhaustion level, one ability-score reduction, or one
    hit-point-maximum reduction.
    """
    name: str = Field(default="Greater Restoration", description="Spell name.")
    description: str = Field(default="Touch: remove one major condition or one curse", description="Rules-facing restoration summary.")
    spell_level: int = Field(default=5, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Greater Restoration on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        removed = _remove_first_condition_by_name(
            target=target,
            condition_names=_GREATER_RESTORATION_CONDITIONS,
            parent_event=effect_event,
        )
        if removed is None:
            removed = _remove_first_condition_by_tag(
                target=target,
                condition_tag=ConditionTag.PETRIFICATION,
                parent_event=effect_event,
            )
        if removed is None:
            removed = _remove_first_condition_by_tag(
                target=target,
                condition_tag=ConditionTag.CURSE,
                parent_event=effect_event,
            )
        if removed is None:
            removed = _remove_first_condition_by_tag(
                target=target,
                condition_tag=ConditionTag.ABILITY_SCORE_REDUCTION,
                parent_event=effect_event,
            )
        if removed is None:
            removed = _remove_first_condition_by_tag(
                target=target,
                condition_tag=ConditionTag.HIT_POINT_MAXIMUM_REDUCTION,
                parent_event=effect_event,
            )
        if removed is None:
            removed = _reduce_exhaustion(
                target=target,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event,
            )

        status = f"Removed {removed}" if removed else "No removable condition found"
        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Greater Restoration: {status}"
        )


class RemoveCurse(SpellAction):
    """Remove every curse-tagged condition from a touched creature."""
    name: str = Field(default="Remove Curse", description="Spell name.")
    description: str = Field(default="Touch: remove all curses from a creature", description="Rules-facing curse removal summary.")
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Remove Curse on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        removed: List[str] = []
        for cond_name, cond in list(target.active_conditions.items()):
            if ConditionTag.CURSE in cond.tags:
                target.remove_condition(cond_name, parent_event=effect_event)
                removed.append(cond_name)

        status = f"Removed {', '.join(removed)}" if removed else "No curse found"
        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Remove Curse: {status}"
        )


class ProtectionFromPoisonEffect(BaseCondition):
    """Resistance to poison damage and protection against the Poisoned condition."""
    name: str = Field(default="Protection from Poison", description="Condition name.")
    description: str = Field(default="Resistant to poison damage, advantaged on poison saves, immune to Poisoned condition", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        resist_mod = ResistanceModifier(
            name="Protection from Poison",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.POISON
        )
        mod_uuid = add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, resist_mod)
        outs.append((target.health.damage_reduction.uuid, mod_uuid))

        poison_save_abilities: Tuple[AbilityName, ...] = (
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        )
        for ability_name in poison_save_abilities:
            save = target.saving_throws.get_saving_throw(ability_name)
            save_mod_uuid = add_modifier(save.bonus, Channel.SELF_CONTEXTUAL, Kind.ADVANTAGE, ContextualAdvantageModifier(
                    name="Protection from Poison",
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=_protection_from_poison_save_advantage,
                ))
            outs.append((save.bonus.uuid, save_mod_uuid))

        target.add_condition_immunity_source("Poisoned", self.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Protection from Poison applied to {target.name}"
        )
        return outs, [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunity on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.remove_condition_immunity_source("Poisoned", self.uuid)
        return super()._remove(event)


def _protection_from_poison_save_advantage(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[AdvantageModifier]:
    """Return advantage for saving throws made against becoming poisoned."""
    if context is None or context.get("condition_context") != "Poisoned":
        return None
    return AdvantageModifier(
        name="Protection from Poison",
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


class ProtectionFromPoison(SpellAction):
    """Protection from Poison - 2nd level Abjuration (NOT concentration)"""
    creates = (*SpellAction.creates, ProtectionFromPoisonEffect)
    name: str = Field(default="Protection from Poison", description="Spell name.")
    description: str = Field(default="Touch: resist poison damage, immune to Poisoned", description="Rules-facing spell summary.")
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare poison resistance and Poisoned immunity support."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.protection_from_poison",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.protection_from_poison.resistance",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=(
                        "selected_target.resistance.poison",
                        "selected_target.immunity.condition.poisoned",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.ProtectionFromPoisonEffect"}),
                ),
            ),
        )

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Protection from Poison on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        if "Poisoned" in target.active_conditions:
            target.remove_condition("Poisoned", parent_event=effect_event)

        condition = ProtectionFromPoisonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{self.name} cast on {target.name}"
        )


class DeathWardEffect(BaseCondition):
    """First lethal damage or instant-death effect is negated once."""
    name: str = Field(default="Death Ward", description="Condition name.")
    description: str = Field(default="Once: survive lethal damage at 1 HP or negate instant death", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target_uuid = self.target_entity_uuid
        handler_uuids: List[UUID] = []

        def death_ward_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if isinstance(event, InstantDeathEvent):
                entity = Entity.get(target_uuid)
                if not entity:
                    return None
                if "Death Ward" in entity.active_conditions:
                    entity.remove_condition("Death Ward", parent_event=event, consumed=True)
                return event.cancel(
                    status_message=f"Death Ward! {entity.name} is protected from instant death"
                )
            if not isinstance(event, TakeDamageEvent):
                return None
            entity = Entity.get(target_uuid)
            if not entity:
                return None
            current_hp = entity.get_normal_hp()
            preview = entity.preview_take_damage(event)
            if current_hp - preview.normal_hit_point_damage > 0:
                return None
            damage_cap = max(0, current_hp - 1)
            if event.normal_hit_point_damage_cap is not None:
                damage_cap = min(damage_cap, event.normal_hit_point_damage_cap)
            if "Death Ward" in entity.active_conditions:
                entity.remove_condition("Death Ward", parent_event=event, consumed=True)
            return event.with_updates(
                normal_hit_point_damage_cap=damage_cap,
                status_message=f"Death Ward! {entity.name} survives with 1 HP",
            )

        handler = EventHandler(
            name="Death Ward",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                ),
                Trigger(
                    event_type=EventType.INSTANT_DEATH,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=death_ward_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Death Ward applied to {target.name}"
        )
        return [], handler_uuids, [], [], effect_event


class DeathWard(SpellAction):
    """Death Ward - 4th level Abjuration (NOT concentration)"""
    creates = (*SpellAction.creates, DeathWardEffect)
    name: str = Field(default="Death Ward", description="Spell name.")
    description: str = Field(default="Touch: once, survive lethal damage at 1 HP", description="Rules-facing spell summary.")
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Death Ward's one-shot lethal protection condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.death_ward",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.death_ward.lethal_protection",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.death_ward",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.DeathWardEffect"}),
                ),
            ),
        )

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Death Ward on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = DeathWardEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{self.name} cast on {target.name}"
        )

FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME = "Freedom of Movement Escape"
FREEDOM_OF_MOVEMENT_RESTRAINT_NAMES = ("Restrained",)


def _freedom_of_movement_nonmagical_restraints(entity: Entity) -> List[BaseCondition]:
    """Escape exact mundane sources, preserving independent magical leases."""
    sources = [condition for condition in entity.active_conditions_by_uuid.values()
               if isinstance(condition, SpatialRestraintSource)]
    managed = {source.restraint_manifestation_uuid for source in sources}
    restraints: List[BaseCondition] = [source for source in sources
                                      if ConditionTag.MAGICAL not in source.tags]
    for condition_name in FREEDOM_OF_MOVEMENT_RESTRAINT_NAMES:
        condition = entity.active_conditions.get(condition_name)
        if (condition is not None and condition.uuid not in managed
                and ConditionTag.MAGICAL not in condition.tags):
            restraints.append(condition)
    return restraints

def _freedom_of_movement_available_movement(entity: Entity) -> int:
    """Return available movement before restraint max constraints are applied.

    Args:
        entity: Entity whose movement pool is inspected.

    Returns:
        Remaining movement after movement-cost modifiers, ignoring restraint
        max constraints so the escape can pay the SRD 5-foot cost.
    """
    economy = entity.action_economy
    excluded = {modifier_uuid
        for condition in entity.active_conditions_by_uuid.values()
        if condition.name in FREEDOM_OF_MOVEMENT_RESTRAINT_NAMES
        for modifier_uuid in condition.modifers_uuids.get(economy.walking_speed.uuid, [])}
    speed = value_score(parts(economy.walking_speed), ValueRead(economy.walking_speed.source_entity_uuid),
                        normalized=True, excluded=frozenset(excluded))
    return max(0, speed * (1 + economy.dash_count) - economy.movement_spent())


def _freedom_of_movement_escape_cost_evaluator(source_entity_uuid: UUID, cost_type: CostType, cost: int) -> bool:
    """Check whether Freedom of Movement can pay its escape movement cost.

    Args:
        source_entity_uuid: Entity attempting to escape.
        cost_type: Action economy bucket requested by the action.
        cost: Movement amount required.

    Returns:
        True when the entity has enough unspent movement before restraint caps.
    """
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return False
    if cost_type != "movement":
        return entity_action_economy_cost_evaluator(source_entity_uuid, cost_type, cost)
    return _freedom_of_movement_available_movement(entity) >= cost


@srd_action_identity(
    content_id="action.spell.freedom_of_movement.escape",
    display_name="Freedom of Movement Escape",
    description="Spend movement to escape an eligible nonmagical restraint.",
    parent_spell_name="Freedom of Movement",
    source_page=147,
    sort_order=810,
)
class FreedomOfMovementEscape(BaseAction):
    """Spend movement to escape nonmagical Restrained conditions."""

    name: str = Field(default=FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME, description="Display name for the automatic restraint escape action.")
    description: str = Field(default="Spend 5 feet of movement to escape nonmagical Restrained conditions.", description="Rules-facing action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode used by action discovery and validation.")
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Freedom of Movement Escape Cost",
                cost_type="movement",
                cost=5,
                evaluator=_freedom_of_movement_escape_cost_evaluator,
            )
        ],
        description="Movement cost paid to escape a nonmagical restraint.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Freedom of Movement is active and a nonmagical restraint is available to escape."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return "Entity not found"
        if "Freedom of Movement" not in entity.active_conditions:
            return "Freedom of Movement is not active"
        if not _freedom_of_movement_nonmagical_restraints(entity):
            return "No nonmagical restraint to escape"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Remove active nonmagical restraint conditions.

        Args:
            execution_event: Execution event being resolved.

        Returns:
            Completion event after removing the escaped restraints.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")
        restraint_names = _freedom_of_movement_nonmagical_restraints(entity)
        if not restraint_names:
            return execution_event.cancel(status_message="No nonmagical restraint to escape")

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name} escapes nonmagical restraints",
        )
        escaped = ", ".join(condition.get_display_name() for condition in restraint_names
                            if entity.remove_condition_by_uuid(condition.uuid, parent_event=effect_event))
        return effect_event.with_updates(
            status_message=f"{entity.name} escaped {escaped}",
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Consume 5 feet of movement while ignoring the escaped restraint cap.

        Args:
            execution_event: Validated execution proposal carrying serialized
                costs.

        Returns:
            Execution proposal after the movement cost is committed.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")
        movement_cost = sum(
            cost.cost
            for cost in execution_event.costs
            if cost.cost_type == "movement"
        )
        if _freedom_of_movement_available_movement(entity) < movement_cost:
            return execution_event.cancel(
                status_message="Not enough movement to escape"
            )
        if movement_cost > 0:
            entity.action_economy.install_prevalidated_aggregate_with_receipt((
                ActionEconomyChannelCost(
                    cost_type="movement",
                    amount=movement_cost,
                    name="Freedom of Movement Escape Cost",
                ),
            ))
        return execution_event.with_updates(
            status_message=f"Applied {movement_cost}ft movement cost for {self.name}",
        )


class FreedomOfMovementEffect(BaseCondition):
    """Ignores difficult terrain and blocks key movement-impairing conditions."""
    ignores_difficult_terrain: bool = True
    ignores_magical_speed_reduction: bool = True
    ignores_underwater_penalties: bool = True

    name: str = Field(default="Freedom of Movement", description="Condition name.")
    description: str = Field(default="Unaffected by difficult terrain, magical speed reduction, underwater penalties, Restrained, magical paralysis, and can spend 5 feet of movement to escape nonmagical restraints", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target.senses._paths_dirty = True

        target.add_condition_immunity_source("Restrained", self.uuid)
        target.add_condition_immunity_source(
            "Paralyzed", self.uuid,
            immunity_check=_freedom_of_movement_magical_condition_immunity,
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Freedom of Movement applied to {target.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up flag and condition immunities on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.senses._paths_dirty = True
            target.remove_condition_immunity_source("Restrained", self.uuid)
            target.remove_condition_immunity_source("Paralyzed", self.uuid)
            target.unregister_action(FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME)
        return super()._remove(event)


class FreedomOfMovement(SpellAction):
    """Freedom of Movement - 4th level Abjuration (NOT concentration)"""
    creates = (*SpellAction.creates, FreedomOfMovementEffect, FreedomOfMovementEscape)
    name: str = Field(default="Freedom of Movement", description="Spell name.")
    description: str = Field(default="Touch: ignores terrain, magical speed reduction, underwater penalties, and key movement-impairing conditions", description="Rules-facing spell summary.")
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Freedom of Movement's mobility protection condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.freedom_of_movement",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.freedom_of_movement.mobility",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=(
                        "selected_target.ignore_difficult_terrain",
                        "selected_target.immunity.condition.restrained",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.FreedomOfMovementEffect"}),
                ),
            ),
        )

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if self.target_entity_uuid is None:
            self.target_entity_uuid = self.source_entity_uuid  # No named recipient: the caster.
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Freedom of Movement on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = FreedomOfMovementEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event
        target.unregister_action(FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME)
        target.register_action(FreedomOfMovementEscape(source_entity_uuid=target.uuid, template=True,
            contribution_owner_uuid=condition.uuid))

        return effect_event.with_updates(
            status_message=f"{self.name} cast on {target.name}"
        )


def _freedom_of_movement_magical_condition_immunity(
    entity: Any,
    context: Optional[dict],
) -> bool:
    """Return whether an incoming condition is magical."""
    _ = entity
    if context is None:
        return False
    condition = context.get("condition")
    condition_tags = context.get("condition_tags", getattr(condition, "tags", set()))
    return ConditionTag.MAGICAL in condition_tags


def _resistance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to saving throw roll. One-use: removes condition after firing."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = roll_die_face(4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    modified_event = event.replace_roll(
        new_roll,
        "Resistance",
        f"+{d4_value} (1d4)",
    )

    target = Entity.get(source_entity_uuid)
    if target and "Resistance" in target.active_conditions:
        target.remove_condition("Resistance", parent_event=modified_event)

    return modified_event


class ResistanceEffect(BaseCondition):
    """Add 1d4 to one saving throw, then remove itself."""
    name: str = Field(default="Resistance", description="Condition name.")
    description: str = Field(default="Add 1d4 to one saving throw", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Resistance",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_resistance_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Resistance applied to {target.name}"
        )
        return [], [handler.uuid], [], [], effect_event


class Resistance(SpellAction):
    """Apply a one-use saving throw bonus to a touched target.

    The effect lasts for ten rounds, consumes concentration, and removes itself
    after modifying one save roll.
    """
    creates = (*SpellAction.creates, ResistanceEffect)
    name: str = Field(default="Resistance", description="Spell name.")
    description: str = Field(default="Add 1d4 to one saving throw (one use)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=0, description="Cantrip spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Resistance's one-use saving-throw support condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.resistance",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.resistance.save_bonus",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.resistance",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.ResistanceEffect"}),
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Resistance cast on {target.name}"
        )

        resistance_effect = ResistanceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        resistance_effect.duration.duration_type = DurationType.ROUNDS
        resistance_effect.duration.duration = 10
        return self.apply_owned_condition(effect_event, resistance_effect)


class ShieldOfFaithEffect(BaseCondition):
    """Grant a +2 Armor Class bonus."""
    name: str = Field(default="Shield of Faith", description="Condition name.")
    description: str = Field(default="+2 bonus to AC", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                name="Shield of Faith",
                value=2,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            ))
        outs.append((target.equipment.ac_bonus.uuid, modifier_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Shield of Faith grants +2 AC to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}


class ShieldOfFaith(SpellAction):
    """Apply a concentration-linked +2 AC bonus as a bonus action."""
    creates = (*SpellAction.creates, ShieldOfFaithEffect)
    name: str = Field(default="Shield of Faith", description="Spell name.")
    description: str = Field(default="+2 AC bonus (concentration)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shield of Faith Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to cast the spell.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Shield of Faith's AC bonus condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.shield_of_faith",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.shield_of_faith.ac_bonus",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.shield_of_faith",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.ShieldOfFaithEffect"}),
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Shield of Faith cast on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = ShieldOfFaithEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"Shield of Faith grants +2 AC to {target.name}"
        )


class AidEffect(BaseCondition):
    """Increase maximum hit points by the configured bonus."""
    name: str = Field(default="Aid", description="Condition name.")
    description: str = Field(default="Max HP increased", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    hp_bonus: int = Field(default=5, description="Maximum hit point bonus applied by Aid.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = add_modifier(target.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                name="Aid",
                value=self.hp_bonus,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            ))
        outs.append((target.health.max_hit_points_bonus.uuid, modifier_uuid))

        con_mod = target.ability_scores.get_ability("constitution").modifier_reading().normalized_score
        max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Aid grants +{self.hp_bonus} max HP to {target.name}",
            resulting_max_hp=max_hp
        )
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            con_mod = target.ability_scores.get_ability("constitution").modifier_reading().normalized_score
            max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
            return {"resulting_max_hp": max_hp}
        return {}


class Aid(SpellAction):
    """Increase maximum hit points for up to three targets.

    This implementation applies a max-HP condition to each target resolved by
    the multi-target action path.
    """
    creates = (*SpellAction.creates, AidEffect)
    name: str = Field(default="Aid", description="Spell name.")
    description: str = Field(default="Increase max HP by 5 per level above 1st for 3 targets", description="Rules-facing spell summary.")
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_multi_target_count(self) -> int:
        """Return Aid's current fixed target count."""
        return 3

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Aid's maximum-hit-point support condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.aid",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.aid.max_hp",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.aid",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.AidEffect"}),
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        hp_bonus = 5 * max(1, self.cast_at_level - 1)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Aid grants +{hp_bonus} max HP to {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = AidEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            hp_bonus=hp_bonus,
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Aid grants +{hp_bonus} max HP to {target.name}"
        )


class SanctuaryEffect(BaseCondition):
    """Ward a creature from attacks unless the attacker passes a Wisdom save.

    The ward removes itself when the protected creature attacks or casts an
    offensive spell affecting an enemy.
    """
    name: str = Field(default="Sanctuary", description="Condition name.")
    description: str = Field(default="Attackers must make WIS save to target this creature", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    spell_dc: int = Field(default=10, description="Wisdom save DC attackers must meet.")
    duration_rounds: int = Field(default=10, description="Combat-round duration used by the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        ward_handler = self._create_ward_handler()
        target.add_event_handler(ward_handler)
        handler_uuids.append(ward_handler.uuid)

        break_handler = self._create_break_handler()
        target.add_event_handler(break_handler)
        handler_uuids.append(break_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Sanctuary protects {target.name}"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_ward_handler(self) -> EventHandler:
        """Force WIS save on attackers targeting the warded entity."""
        assert self.target_entity_uuid is not None
        warded_uuid = self.target_entity_uuid
        caster_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type is EventType.BASE_ACTION and not isinstance(event, SpellEvent):
                return None
            if isinstance(event, SpellEvent):
                if event.target_type not in (
                    TargetType.ENTITY, TargetType.CREATURE_OR_OBJECT, TargetType.MULTI_ENTITY,
                ):
                    return None
                if warded_uuid not in event.harmful_target_entity_uuids:
                    return None
            elif event.target_entity_uuid != warded_uuid:
                return None
            if event.source_entity_uuid == warded_uuid:
                return None

            attacker = Entity.get(event.source_entity_uuid)
            caster = Entity.get(caster_uuid)
            if not attacker or not caster:
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=attacker.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = attacker.saving_throw(save_request)

            if success:
                return None
            else:
                return event.cancel(
                    status_message=f"{attacker.name} fails WIS save — Sanctuary blocks the attempt",
                    outcome_code=SANCTUARY_INTERRUPTION_OUTCOME_CODE,
                    outcome_source_entity_uuid=warded_uuid,
                )

        return EventHandler(
            name="Sanctuary Ward",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.DECLARATION),
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=warded_uuid,
                ),
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.DECLARATION,
                ),
            ],
            event_processor=processor,
        )

    def _create_break_handler(self) -> EventHandler:
        """Remove Sanctuary when the warded entity attacks or casts an offensive spell."""
        assert self.target_entity_uuid is not None
        warded_uuid = self.target_entity_uuid
        condition_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type is EventType.BASE_ACTION and not isinstance(event, SpellEvent):
                return None
            if event.source_entity_uuid != warded_uuid:
                return None

            warded = Entity.get(warded_uuid)
            if not warded:
                return None

            if isinstance(event, SpellEvent):
                if not event.harmful:
                    return None
                if event.target_entity_uuid is not None:
                    targets = (
                        [event.target_entity_uuid]
                        if event.target_entity_uuid in event.harmful_target_entity_uuids
                        else []
                    )
                elif event.target_type in (TargetType.POSITION,TargetType.POSITION_LOS):
                    targets = list({
                        target_uuid
                        for position in event.resolved_area_positions or ()
                        for target_uuid in get_map().get_entities_at(position)
                    })
                else:
                    # Convolution children identify the recipients actually
                    # reached; a root's predicted target list is not an effect.
                    targets = []
            else:
                targets = [event.target_entity_uuid] if event.target_entity_uuid else []

            if any(
                warded.is_enemy(target)
                for target_uuid in targets
                if (target := Entity.get(target_uuid)) is not None
            ):
                if "Sanctuary" in warded.active_conditions:
                    active = warded.active_conditions.get("Sanctuary")
                    if active and active.uuid == condition_uuid:
                        warded.remove_condition("Sanctuary", parent_event=event)
            return None

        return EventHandler(
            name="Sanctuary Self-Break",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=warded_uuid),
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=warded_uuid,
                ),
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=warded_uuid,
                ),
            ],
            event_processor=processor,
        )


class Sanctuary(SpellAction):
    """Apply a non-concentration ward that can break on hostile action.

    Casting costs a bonus action and applies a ten-round `SanctuaryEffect`.
    """
    creates = (*SpellAction.creates, SanctuaryEffect)
    name: str = Field(default="Sanctuary", description="Spell name.")
    description: str = Field(default="Ward: attackers must WIS save; breaks on offensive action", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Sanctuary Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to cast the spell.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Sanctuary's attack-ward condition."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="support.sanctuary",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.sanctuary.ward",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.sanctuary",),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.SanctuaryEffect"}),
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Sanctuary cast on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = SanctuaryEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            spell_dc=dc,
        )
        condition.duration.duration_type = DurationType.ROUNDS
        condition.duration.duration = 10
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"Sanctuary protects {target.name} (DC {dc})"
        )


class BeaconOfHopeEffect(BaseCondition):
    """Grant Wisdom-save advantage and maximize received healing dice."""
    name: str = Field(default="Beacon of Hope", description="Condition name.")
    description: str = Field(default="Advantage on WIS saves; healing dice maximized", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        wis_save = target.saving_throws.get_saving_throw("wisdom")
        modifier_uuid = add_modifier(wis_save.bonus, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                name="Beacon of Hope",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            ))
        outs.append((wis_save.bonus.uuid, modifier_uuid))

        heal_handler = self._create_heal_maximizer()
        target.add_event_handler(heal_handler)
        handler_uuids.append(heal_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Beacon of Hope inspires {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_heal_maximizer(self) -> EventHandler:
        """Maximize all healing dice received by this entity."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, HealRollResultEvent):
                return None
            if event.target_entity_uuid != target_uuid:
                return None

            roll = event.final_roll
            if isinstance(roll.results, list) and len(roll.results) > 0:
                die_count = len(roll.results)
                original = event.original_roll
                if isinstance(original.results, list) and len(original.results) > 0:
                    dice = Dice.get(roll.dice_uuid)
                    if dice:
                        max_per_die = dice.value
                        new_results = [max_per_die] * die_count
                        new_total = sum(new_results) + roll.bonus
                        new_roll = roll.model_copy(update={
                            "results": new_results,
                            "total": new_total,
                        })
                        return event.replace_roll(
                            new_roll,
                            "Beacon of Hope",
                            "maximize healing dice",
                        )

            return None

        return EventHandler(
            name="Beacon of Hope Heal Maximizer",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.HEAL_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid,
                ),
            ],
            event_processor=processor,
        )


class BeaconOfHope(SpellAction):
    """Apply Beacon of Hope to multiple allies and link effects to concentration.

    The implementation caps action discovery at six visible allies.
    """
    creates = (*SpellAction.creates, BeaconOfHopeEffect)
    name: str = Field(default="Beacon of Hope", description="Spell name.")
    description: str = Field(default="Advantage on WIS saves; maximize healing received", description="Rules-facing spell summary.")
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def get_multi_target_count(self) -> int:
        return self.get_num_projectiles()

    def get_num_projectiles(self) -> int:
        """Return the engine cap for affected allies."""
        return 6

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Beacon of Hope inspires {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        condition = BeaconOfHopeEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, condition)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Beacon of Hope cast on {target.name}"
        )


PROTECTED_CREATURE_TYPES=frozenset({CreatureType.ABERRATION,CreatureType.CELESTIAL,CreatureType.ELEMENTAL,
    CreatureType.FEY,CreatureType.FIEND,CreatureType.UNDEAD})


class ProtectionFromEvilAndGoodEffect(BaseCondition):
    name: str = "Protection from Evil and Good"
    description: str = "Listed creature types attack with disadvantage and cannot charm or frighten the recipient."
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.UNTIL_LONG_REST))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    _purge: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def _blocks_condition(self,entity: BaseBlock,context: Dict[str,Any] | None) -> bool:
        incoming=(context or {}).get("condition")
        if not isinstance(incoming,BaseCondition):
            return False
        source=Entity.get(incoming.source_entity_uuid)
        return source is not None and source.creature_type in PROTECTED_CREATURE_TYPES

    def _attack_penalty(self,source_entity_uuid: UUID,target_entity_uuid: UUID | None = None,
                        context: Dict[str,Any] | None = None) -> AdvantageModifier | None:
        del context
        attacker_uuid=target_entity_uuid if source_entity_uuid==self.target_entity_uuid else source_entity_uuid
        attacker=Entity.get(attacker_uuid) if attacker_uuid else None
        if attacker is None or attacker.creature_type not in PROTECTED_CREATURE_TYPES:
            return None
        return AdvantageModifier(name=self.name,value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Protection recipient no longer exists")
        self._purge=prepare_control_removals(target,frozenset({"Charmed","Frightened"}),event,PROTECTED_CREATURE_TYPES)
        if self._purge is None:
            return [],[],[],[],event.cancel(status_message="Existing control removal was rejected")
        for name in ("Charmed","Frightened"):
            target.add_condition_immunity_source(name,self.uuid,immunity_check=self._blocks_condition)
        value=target.equipment.ac_bonus
        ident=add_modifier(value, Channel.TO_TARGET_CONTEXTUAL, Kind.ADVANTAGE, ContextualAdvantageModifier(name=self.name,
            source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid,callable=self._attack_penalty))
        return [(value.uuid,ident)],[],[],[],event.phase_to(EventPhase.EFFECT)

    def _commit_application(self,event: Event) -> None:
        if self._purge is not None: BaseBlock.commit_owned_condition_removals(self._purge)

    def publish_prepared_application(self) -> None:
        if self._purge is not None and self._purge.committed_result is not None:
            BaseBlock.publish_owned_condition_removals(self._purge)

    def _release_owned_runtime_state(self,*,parent_event: Event | None = None) -> None:
        if self._purge is not None and self._purge.committed_result is None:
            BaseBlock.cancel_owned_condition_removals(self._purge,"Protection was not committed")
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            for name in ("Charmed","Frightened"): target.remove_condition_immunity_source(name,self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)


class ProtectionFromEvilAndGood(SpellAction):
    creates = (*SpellAction.creates, ProtectionFromEvilAndGoodEffect)
    name: str = "Protection from Evil and Good"
    description: str = "Protection from aberrations, celestials, elementals, fey, fiends and undead."
    spell_level: int = 1
    spell_school: str = "abjuration"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH,normal=5))
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    concentration: bool = True
    harmful: bool = False

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="protection_from_evil_and_good",condition_type=ProtectionFromEvilAndGoodEffect,beneficial=True,
            save_ability=None,fact=None,)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),ProtectionFromEvilAndGoodEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=event.target_entity_uuid or self.source_entity_uuid))


class PassWithoutTraceEffect(BaseCondition):
    name: str = "Pass without Trace"
    description: str = "A friendly moving aura grants +10 Stealth until rest while concentration holds."
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.UNTIL_LONG_REST))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        caster=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None:
            return [],[],[],[],event.cancel(status_message="Aura caster no longer exists")
        zone=PassWithoutTraceZone(source_entity_uuid=self.source_entity_uuid,position=caster.position,
            anchor_uuid=caster.uuid,faction=caster.faction,content_ref=get_content_declaration(PassWithoutTraceZone).ref,
            effect_origin=self.effect_origin)
        result=zone.activate(parent_event=event)
        if result is None or result.canceled or not zone.applied:
            return [],[],[],[],event.cancel(status_message="Stealth aura could not be established")
        self.add_linked_condition(zone.uuid,zone.uuid)
        return [],[],[],[],event.phase_to(EventPhase.EFFECT)


class PassWithoutTraceBonus(BaseCondition):
    name: str = "Pass without Trace Bonus"
    description: str = "+10 to Stealth checks while at least one friendly aura remains."
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Aura recipient no longer exists")
        value=target.skill_set.get_skill("stealth").skill_bonus
        ident=add_modifier(value, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name=self.name,value=10,
            source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
        return [(value.uuid,ident)],[],[],[],event.phase_to(EventPhase.EFFECT)


class PassWithoutTraceMembership(SpatialConditionMembershipSource):
    creates = (PassWithoutTraceBonus,)
    name: str = "Pass without Trace Membership"
    description: str = "One exact source lease for the shared Stealth bonus."

    def create_manifestation(self,target: Entity) -> BaseCondition:
        return PassWithoutTraceBonus(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid)

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Aura recipient no longer exists")
        child=next((condition for condition in target.active_conditions_by_uuid.values()
                    if isinstance(condition,PassWithoutTraceBonus)),None)
        if child is None:
            child=self.create_manifestation(target)
            child.parent_condition=self.uuid
            applied=target.add_condition(child,parent_event=event)
            if applied is None or applied.canceled:
                return [],[],[],[],event.cancel(status_message="Stealth bonus was not admitted")
        self.add_shared_subcondition(child)
        return [],[],[],[],event.phase_to(EventPhase.EFFECT)


@srd_condition_identity(content_id="spatial_effect.spell.pass_without_trace",
    display_name="Pass without Trace Aura",
    description="Friendly creatures within 30 feet share a nonstacking Stealth bonus.")
class PassWithoutTraceZone(MembershipAreaCondition):
    creates = (PassWithoutTraceMembership,)
    name: str = "Pass without Trace Aura"
    description: str = "Friendly creatures within 30 feet share a nonstacking Stealth bonus."
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.ENTITY
    area: AoEShape = Sphere(radius_feet=30)
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.PERMANENT))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,
        SpatialEffectTriggerKind.ENTER,SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT})
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,
        SpatialEffectTriggerKind.ENTER,SpatialEffectTriggerKind.LEAVE,SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
        SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT})

    def relocate_anchor(self,position: Tuple[int,int],*,parent_event: Event) -> bool:
        if not self.is_active_spatial_condition() or position==self.position:
            return False
        previous=self.position
        self.position=position
        self.observation_revision+=1
        try:
            positions={cell for cell in self._compute_affected_positions() if get_map().has_tile(*cell)}
            return self.change_footprint(positions,parent_event=parent_event)
        except BaseException:
            self.position=previous
            self.observation_revision+=1
            raise

    def membership_source_class(self) -> type[SpatialConditionMembershipSource]:
        return PassWithoutTraceMembership

    def membership_applies_to(self,entity: Entity) -> bool:
        caster=Entity.get(self.source_entity_uuid)
        return caster is not None and (entity.uuid==caster.uuid or caster.is_ally(entity))

    def _apply_appearance_effect(self,entity: Entity,*,parent_event: Event) -> None:
        if self.membership_applies_to(entity): self.apply_membership(entity,parent_event=parent_event)

    def _apply_effect_entry_effect(self,entity: Entity,*,parent_event: Event) -> None:
        if self.membership_applies_to(entity): self.apply_membership(entity,parent_event=parent_event)

    def _apply_effect_exit_effect(self,entity: Entity,*,parent_event: Event) -> None:
        self.remove_membership(entity,parent_event=parent_event)

# PassWithoutTraceEffect (defined above) creates PassWithoutTraceZone.
PassWithoutTraceEffect.creates = (*PassWithoutTraceEffect.creates, PassWithoutTraceZone)


class PassWithoutTrace(SpellAction):
    creates = (*SpellAction.creates, PassWithoutTraceEffect)
    name: str = "Pass without Trace"
    description: str = "Friendly 30-foot moving aura: +10 Stealth until rest, concentration."
    spell_level: int = 2
    spell_school: str = "abjuration"
    target_type: TargetType = TargetType.SELF
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    concentration: bool = True
    harmful: bool = False

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="pass_without_trace",condition_type=PassWithoutTraceEffect,beneficial=True,
            save_ability=None,fact=None,)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),PassWithoutTraceEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.source_entity_uuid))


class GlyphSleepEffect(BaseCondition):
    name: str = "Glyph Sleep"
    denies_consciousness: bool = Field(default=True,
        description="The sleep glyph makes its recipient unconscious.")
    description: str = "Two-turn magical sleep; positive damage, assistance, successful Shove or Wet wakes the recipient."
    immunity_names: tuple[str,...] = ("Sleep","Unconscious")
    agency_denial: ConditionAgencyDenial = ConditionAgencyDenial.FULL_TURN
    duration: Duration = Field(default_factory=lambda:Duration(duration=None,duration_type=DurationType.PERMANENT))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    removal_triggers: frozenset[ConditionRemovalTrigger] = frozenset({ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED,
        ConditionRemovalTrigger.SHAKE_AWAKE,ConditionRemovalTrigger.ALLY_HELP,ConditionRemovalTrigger.WET_APPLICATION})

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None or target.has_origin_capability(OriginCapability.MAGICAL_SLEEP_IMMUNITY) or target.creature_type is CreatureType.UNDEAD:
            return [],[],[],[],event.cancel(status_message="Recipient cannot be magically slept")
        modifiers=apply_unconscious_transform(target,name=self.name,effect_source_uuid=self.source_entity_uuid)
        def wake(boundary: Event,_: UUID):
            target.remove_condition_by_uuid(self.uuid,parent_event=boundary)
            return None
        handler=EventHandler(name="Glyph Sleep wake on positive damage",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.DAMAGE_APPLIED,event_phase=EventPhase.EFFECT,event_target_entity_uuid=target.uuid)],event_processor=wake)
        target.add_event_handler(handler)
        def shoved(boundary: Event,_: UUID):
            if isinstance(boundary,ShoveEvent) and boundary.contest_success:
                target.remove_condition_by_uuid(self.uuid,parent_event=boundary)
            return None
        shove_handler=EventHandler(name="Glyph Sleep wake on successful shove",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION,event_phase=EventPhase.EFFECT,event_target_entity_uuid=target.uuid)],
            event_processor=shoved)
        target.add_event_handler(shove_handler)
        expiry=target_turn_expiry_handler(self,turn_ends=2)
        target.add_event_handler(expiry)
        return modifiers,[handler.uuid,shove_handler.uuid,expiry.uuid],[],[],event.phase_to(EventPhase.EFFECT)


@srd_condition_identity(content_id="spatial_effect.spell.glyph_of_warding",display_name="Glyph of Warding",
    description="One hostile-triggered thirteen-foot glyph; payload affects all occupants once.")
class GlyphOfWardingZone(AreaCondition):
    creates = (GlyphSleepEffect, Move, Prone)
    name: str = "Glyph of Warding"
    description: str = "One hostile-triggered thirteen-foot glyph; payload affects all occupants once."
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    area: AoEShape = Sphere(radius_feet=13)
    has_visible_presence: bool = True
    spell_dc: int
    dice_count: int = 5
    payload: Literal["acid","cold","fire","lightning","thunder","sleep","detonation"] = "fire"
    caster_faction: str | None=None
    initial_trigger_pending: bool = True
    armed: bool = True
    duration: Duration = Field(default_factory=lambda:Duration(duration=None,duration_type=DurationType.PERMANENT))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,SpatialEffectTriggerKind.ENTER})

    def trigger(self,entrant: Entity,event: Event) -> None:
        if self.initial_trigger_pending or not self.armed or not self.applied or not self.allows_contribution_at(entrant.position):
            return
        if entrant.uuid==self.source_entity_uuid or entrant.faction==self.caster_faction:
            return
        positions={cell for cell in self.affected_positions if self.allows_contribution_at(cell)}
        targets=[target for target in self._occupants_at(positions) if self.allows_contribution_at(target.position)]
        context=self.saving_throw_context(effect_id="spell.glyph_of_warding.payload")
        # Disarm before payload: nested movement and damage cannot retrigger this glyph.
        if not self.deactivate(parent_event=event):
            return
        self.armed=False
        caster=Entity.get(self.source_entity_uuid)
        if caster is None:
            return
        # The glyph's payload reaches everyone in its area at once.
        with EventQueue.group(GroupEntryKind.CAST_LOOP,root=event,shares_damage_rolls=True):
            for target in targets:
                request=caster.create_saving_throw_request(target.uuid,"dexterity",self.spell_dc,
                    parent_event=event.uuid,saving_throw_context=context)
                saved=target.saving_throw(request)[2]
                if self.payload=="sleep":
                    if not saved:
                        target.add_condition(GlyphSleepEffect(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
                            effect_origin=self.effect_origin),parent_event=event)
                elif self.payload=="detonation":
                    if not saved:
                        delta=(target.position[0]-self.position[0],target.position[1]-self.position[1])
                        direction=(1 if delta[0]>0 else -1 if delta[0]<0 else 0,1 if delta[1]>0 else -1 if delta[1]<0 else 0)
                        if direction==(0,0):
                            direction=(1,0)
                        start=target.position
                        end=(start[0]+4*direction[0],start[1]+4*direction[1])
                        movement=ForcedMovementEvent(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
                            start_position=start,end_position=end,direction=direction,intended_distance=20,actual_distance=20,
                            cause="glyph_of_warding",effect_origin=self.effect_origin,parent_event=event.uuid)
                        movement=movement.phase_to(EventPhase.EXECUTION)
                        if not movement.canceled:
                            movement=movement.phase_to(EventPhase.EFFECT)
                            if not movement.canceled:
                                commit_forced_movement(target,movement,parent_event=event)
                else:
                    damage_type=DamageType[self.payload.upper()]
                    damage=Damage(name="Glyph of Warding",source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
                        damage_dice=8,dice_numbers=self.dice_count,damage_type=damage_type,effect_origin=self.effect_origin,
                        damage_bonus=parts(ModifiableValue(source_entity_uuid=caster.uuid,base=0)))
                    roll=roll_spell_damage(damage, parent_event=event, effect_origin=self.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
                    target.receive_damage(roll.total//2 if saved else roll.total,damage_type,caster.uuid,parent_event=event.uuid,
                        damage_save=DamageSaveContext(ability="dexterity", success=saved, success_fraction=0.5),
                        damages=[damage],damage_rolls=[roll],effect_origin=self.effect_origin,independent_resolution=True,
                        source_condition_uuid=self.uuid)
            if self.payload not in ("sleep","detonation"):
                apply_elemental_surface_contacts(event,positions,DamageType[self.payload.upper()])

    def _apply_appearance_effect(self,entity: Entity,*,parent_event: Event) -> None:
        self.trigger(entity,parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        def entry(event: Event,_: UUID):
            entrant=Entity.get(event.entity_uuid) if isinstance(event,SpatialChangeEvent) and event.entity_uuid else None
            if entrant is not None:
                self.trigger(entrant,event)
            return None
        return EventHandler(name="Glyph of Warding Entry",source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED,event_phase=EventPhase.EFFECT)],event_processor=entry)


class GlyphOfWardingEffect(BaseCondition):
    creates = (GlyphOfWardingZone,)
    name: str = "Glyph of Warding Sustain"
    description: str = "One owned glyph until trigger, recast or long rest; no concentration."
    child_removal_policy: Literal["none","any","last"] = "any"
    position: Tuple[int,int]
    payload: Literal["acid","cold","fire","lightning","thunder","sleep","detonation"]
    spell_dc: int
    dice_count: int
    zone_uuid: UUID | None=None
    duration: Duration = Field(default_factory=lambda:Duration(duration=None,duration_type=DurationType.UNTIL_LONG_REST))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    _committed_application: Event | None=PrivateAttr(default=None)

    def _apply(self,event: Event):
        caster=Entity.get(self.source_entity_uuid)
        if caster is None:
            return [],[],[],[],event.cancel(status_message="Glyph caster is absent")
        zone=GlyphOfWardingZone(source_entity_uuid=caster.uuid,position=self.position,payload=self.payload,
            spell_dc=self.spell_dc,dice_count=self.dice_count,caster_faction=caster.faction,effect_origin=self.effect_origin,
            content_ref=get_content_declaration(GlyphOfWardingZone).ref)
        self.zone_uuid=zone.uuid
        self.add_linked_condition(zone.uuid,zone.uuid)
        admitted=zone.activate(parent_event=event)
        if admitted is None or admitted.canceled or not zone.applied:
            return [],[],[],[],event.cancel(status_message="Glyph placement was not admitted")
        return [],[],[],[],event.phase_to(EventPhase.EFFECT)

class GlyphOfWarding(SpellAction):
    creates = (*SpellAction.creates, GlyphOfWardingEffect)
    name: str = "Glyph of Warding"
    description: str = "Thirteen-foot hostile-triggered glyph: elemental DEX half damage, Sleep or Detonation."
    spell_level: int = 3
    spell_school: str = "abjuration"
    target_type: TargetType = TargetType.POSITION_LOS
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=30))
    payload: Literal["acid","cold","fire","lightning","thunder","sleep","detonation"] = "fire"
    harmful: bool = True

    def has_authored_damage(self) -> bool:
        return self.payload in ("acid", "cold", "fire", "lightning", "thunder")

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=payload, label=payload.title()),)
                     for payload in ("acid","cold","fire","lightning","thunder","sleep","detonation"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "payload": selection_facet(selection, "form")}

    def get_valid_positions(self):
        return spell_valid_positions(self)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """An existing tile in range that the caster sees, or the caster's own space."""
        return placement_error(self, scan, selection)

    def _apply(self,event: SpellEvent):
        caster=Entity.get(self.source_entity_uuid)
        if caster is None or self.end_position is None:
            return event.cancel(status_message="Glyph placement is absent")
        marker=GlyphOfWardingEffect(
            source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid,position=self.end_position,payload=self.payload,
            spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),dice_count=5+self.get_upcast_bonus())
        admitted=self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),marker)
        zone=BaseCondition.get(marker.zone_uuid) if marker.zone_uuid else None
        if not admitted.canceled and marker.applied and isinstance(zone,GlyphOfWardingZone) and zone.applied:
            zone.initial_trigger_pending=False
            for target in zone._occupants_at(set(zone.affected_positions)):
                zone.trigger(target,admitted)
                if not zone.applied:
                    break
        return admitted


class AuraOfLifeBenefit(BaseCondition):
    name: str = "Aura of Life"
    description: str = "Necrotic resistance; prevents new maximum HP loss; restores an allied living creature at 0 HP to 1 HP before its death save."
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None: return [], [], [], [], event.cancel(status_message="Aura recipient absent")
        value = target.health.damage_reduction
        ident = add_modifier(value, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(name=self.name,
            value=ResistanceStatus.RESISTANCE, damage_type=DamageType.NECROTIC,
            source_entity_uuid=target.uuid))
        def revive(boundary: Event, _: UUID):
            if self.applied and self.contributions_active() and target.uuid != self.source_entity_uuid and                    target.health.life_state is not LifeState.DEAD and target.get_hp() == 0:
                target.receive_healing(1, self.source_entity_uuid, parent_event=boundary.uuid,
                    source_description="Aura of Life", effect_origin=self.effect_origin)
            return None
        handler = EventHandler(name="Aura of Life start-turn healing", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EXECUTION,
                event_source_entity_uuid=target.uuid)], event_processor=revive)
        target.add_event_handler(handler)
        def prevent_reduction(incoming: Event, _: UUID):
            if not incoming.canceled and self.applied and self.contributions_active():
                return incoming.cancel(status_message="Aura of Life prevents new maximum HP reduction")
            return None
        protection = EventHandler(name="Aura of Life maximum HP protection", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.MAXIMUM_HIT_POINT_REDUCTION,
                event_phase=EventPhase.DECLARATION, event_target_entity_uuid=target.uuid)],
            event_processor=prevent_reduction)
        target.add_event_handler(protection)
        return [(value.uuid, ident)], [handler.uuid, protection.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class AuraOfLifeMembership(SpatialConditionMembershipSource):
    creates = (AuraOfLifeBenefit,)
    name: str = "Aura of Life Membership"
    description: str = "Exact membership in one friendly Aura of Life."

    def create_manifestation(self, target: Entity) -> BaseCondition:
        return AuraOfLifeBenefit(name=f"Aura of Life:{self.source_spatial_condition_uuid}",
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)


@srd_condition_identity(content_id="spatial_effect.spell.aura_of_life", display_name="Aura of Life",
    description="Moving necrotic resistance and maximum HP protection.", srd_version="5.2")
class AuraOfLifeZone(PassWithoutTraceZone):
    creates = (*PassWithoutTraceZone.creates, AuraOfLifeMembership)
    name: str = "Aura of Life"
    description: str = "Moving necrotic resistance and maximum HP protection."

    def membership_source_class(self) -> type[SpatialConditionMembershipSource]:
        return AuraOfLifeMembership


class AuraOfLifeOwner(BaseCondition):
    creates = (AuraOfLifeZone,)
    name: str = "Aura of Life Owner"
    description: str = "Ten-minute concentrating owner of the moving aura."
    duration: Duration = Field(default_factory=lambda: Duration(duration=100, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event: Event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None: return [], [], [], [], event.cancel(status_message="Aura caster absent")
        zone = AuraOfLifeZone(source_entity_uuid=caster.uuid, position=caster.position,
            anchor_uuid=caster.uuid, faction=caster.faction,
            content_ref=get_content_declaration(AuraOfLifeZone).ref, effect_origin=self.effect_origin)
        result = zone.activate(parent_event=event)
        if result is None or result.canceled: return [], [], [], [], event.cancel(status_message="Life aura was not admitted")
        self.add_linked_condition(zone.uuid, zone.uuid)
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)


class AuraOfLife(SpellAction):
    creates = (*SpellAction.creates, AuraOfLifeOwner)
    name: str = "Aura of Life"
    description: str = "Concentrating 30-foot friendly life protection and start-turn recovery."
    spell_level: int = 4
    spell_school: str = "abjuration"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    target_type: TargetType = TargetType.SELF
    concentration: bool = True

    def _apply(self, event: SpellEvent):
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT), AuraOfLifeOwner(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid))


class HolyAuraBlindness(Blinded):
    name: str = "Holy Aura Blindness"
    description: str = "Blinded by a holy ward until that spell ends."
    immunity_names: tuple[str, ...] = ("Blinded",)
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})


class HolyAuraEffect(BaseCondition):
    creates = (HolyAuraBlindness,)
    name: str = "Holy Aura"
    description: str = "Advantage on saves and incoming attack disadvantage; fiend/undead melee hitters risk blindness."
    spell_dc: int
    seen_hits: set[UUID] = Field(default_factory=empty_set, exclude=True)
    light_source_uuid: UUID | None = None
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    _removed_light: SpatialChangeEvent | None = PrivateAttr(default=None)

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.name = f"Holy Aura:{self.source_entity_uuid}"

    def get_display_name(self) -> str: return "Holy Aura"

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None: return [], [], [], [], event.cancel(status_message="Holy recipient absent")
        modifiers = []
        for ability in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            value = target.saving_throws.get_saving_throw(ability).bonus
            ident = add_modifier(value, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(name=self.name,
                value=AdvantageStatus.ADVANTAGE, source_entity_uuid=target.uuid))
            modifiers.append((value.uuid, ident))
        value = target.equipment.ac_bonus
        ident = add_modifier(value, Channel.TO_TARGET_STATIC, Kind.ADVANTAGE, AdvantageModifier(name=self.name,
            value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=target.uuid))
        modifiers.append((value.uuid, ident))
        self.light_source_uuid = get_map().add_light_source(target.position, bright_radius_feet=0,
            dim_radius_feet=5, anchor_uuid=target.uuid, contribution_owner_uuid=self.uuid, parent_event=event.uuid)
        def hit(boundary: Event, _: UUID):
            if boundary.canceled or boundary.lineage_uuid in self.seen_hits: return None
            if isinstance(boundary, AttackEvent):
                melee = boundary.range is not None and boundary.range.type == RangeType.REACH
                outcome = boundary.attack_outcome
            elif isinstance(boundary, SpellEvent):
                melee = boundary.range_type == "touch"
                outcome = boundary.attack_outcome
            else: return None
            attacker = Entity.get(boundary.source_entity_uuid)
            if not melee or outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT) or attacker is None or                    attacker.creature_type not in {CreatureType.FIEND, CreatureType.UNDEAD}: return None
            self.seen_hits.add(boundary.lineage_uuid)
            if not condition_save(self, attacker, boundary, "constitution", self.spell_dc, "spell.holy_aura.blindness"):
                parent=BaseCondition.get(self.parent_link[1]) if self.parent_link is not None else None
                if not isinstance(parent,Concentrating) or not parent.applied:return None
                child = HolyAuraBlindness(name=f"Holy Aura Blindness:{parent.uuid}", source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=attacker.uuid,parent_condition=parent.uuid,effect_origin=self.effect_origin)
                result = attacker.add_condition(child, parent_event=boundary)
                if result is not None and not result.canceled: parent.add_linked_condition(attacker.uuid, child.uuid)
            return None
        handler = EventHandler(name="Holy Aura melee-hit blindness", source_entity_uuid=target.uuid, group_dispatch=HandlerGroupDispatch.AFTER_GROUP,
            trigger_conditions=[Trigger(event_type=kind, event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid) for kind in (EventType.ATTACK, EventType.CAST_SPELL)], event_processor=hit)
        target.add_event_handler(handler)
        return modifiers, [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        if self.light_source_uuid is not None:
            self._removed_light = get_map().remove_light_source(self.light_source_uuid,
                publish_event=False, parent_event=event.uuid if event else None)
            self.light_source_uuid = None
        return super()._remove(event)

    def on_membership_changed(self, event: Event):
        if self._removed_light is not None:
            get_map().publish_committed_spatial_event(self._removed_light)
            self._removed_light = None


class HolyAura(SpellAction):
    creates = (*SpellAction.creates, HolyAuraEffect)
    name: str = "Holy Aura"
    description: str = "Fixed selected recipients within 30 feet gain a concentrating holy ward."
    spell_level: int = 8
    spell_school: str = "abjuration"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    target_type: TargetType = TargetType.MULTI_ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    allow_same_target: bool = False
    any_number_of_targets: bool = True
    concentration: bool = True

    def _new_concentration(self,owner,parent_event):
        condition=super()._new_concentration(owner,parent_event)
        condition.duration=Duration(duration=10,duration_type=DurationType.ROUNDS)
        return condition

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self, actor, key="holy_aura", condition_type=HolyAuraEffect, beneficial=True)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Living recipients within range: the caster, or creatures the caster sees."""
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or event.target_entity_uuid is None: return event.cancel(status_message="Holy recipient absent")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT), HolyAuraEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=event.target_entity_uuid,
            spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)))


@srd_action_identity(content_id="action.spell.dispel_evil_and_good.break_enchantment", display_name="Break Enchantment",
    parent_spell_name="Dispel Evil and Good", source_page=137, sort_order=3370,
    description="Touch an eligible charmed or frightened creature, ending the ward to cure it.")
class BreakEnchantment(BaseAction):
    name: str = "Break Enchantment"
    description: str = "Touch to cure charm/fear caused by aberrations, celestials, elementals, fey, fiends or undead."
    ward_uuid: UUID
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Break Enchantment", cost_type="actions", cost=1,
        evaluator=entity_action_economy_cost_evaluator)])

    def get_range(self) -> Range: return Range(type=RangeType.REACH, normal=5)

    def get_physical_access(self): return PhysicalAccess.HAND

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        ward = BaseCondition.get(self.ward_uuid)
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if not isinstance(ward, BaseCondition) or not ward.applied or not ward.contributions_active(): return "Ward is absent"
        if caster is None or target is None or caster.senses.get_feet_distance(target.position) > 5: return "Recipient is beyond touch"
        if not any((condition.name in {"Charmed", "Frightened"} or set(condition.immunity_names).intersection({"Charmed", "Frightened"}))
                and condition.source_creature_type in PROTECTED_CREATURE_TYPES for condition in target.active_conditions_by_uuid.values()):
            return "No eligible enchantment to break"
        return None

    def _apply_costs(self,event):
        return entity_action_economy_cost_applier(event,self.source_entity_uuid)

    def _apply(self, event: ActionEvent):
        event = event.phase_to(EventPhase.EFFECT)
        if event.canceled:
            return event
        with BaseBlock.condition_removal_scope():
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid is not None else None
            caster = Entity.get(self.source_entity_uuid)
            if target is None or caster is None: return event.cancel(status_message="Recipient absent")
            removals = prepare_control_removals(target, frozenset({"Charmed", "Frightened"}), event, PROTECTED_CREATURE_TYPES)
            if removals is None: return event.cancel(status_message="Enchantment removal rejected")
            if not removals.entries: return event.cancel(status_message="No eligible enchantment remains")
            ward = BaseCondition.get(self.ward_uuid)
            if not isinstance(ward, BaseCondition):
                BaseBlock.cancel_owned_condition_removals(removals, "Ward absent")
                return event.cancel(status_message="Ward absent")
            canceled = BaseBlock._prepare_condition_removal_tree(ward, condition_owner=caster, expire=False,
                parent_event=event, prepared=removals.entries, visited={entry[1].uuid for entry in removals.entries})
            if canceled is not None:
                BaseBlock.cancel_owned_condition_removals(removals, "Ward ending rejected")
                return event.cancel(status_message="Ward ending rejected")
            BaseBlock.commit_owned_condition_removals(removals)
            BaseBlock.publish_owned_condition_removals(removals)
            return event


class DispelEvilAndGoodEffect(ProtectionFromEvilAndGoodEffect):
    creates = (BreakEnchantment,)
    granted_action_uuids: set[UUID] = Field(default_factory=empty_set)
    name: str = "Dispel Evil and Good"
    description: str = "Six supernatural creature types attack with disadvantage; grants Break Enchantment."
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))

    def _apply(self, event: Event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None: return [], [], [], [], event.cancel(status_message="Ward caster absent")
        value = caster.equipment.ac_bonus
        ident = add_modifier(value, Channel.TO_TARGET_CONTEXTUAL, Kind.ADVANTAGE, ContextualAdvantageModifier(name=self.name,
            source_entity_uuid=caster.uuid, callable=self._attack_penalty))
        action = BreakEnchantment(source_entity_uuid=caster.uuid, ward_uuid=self.uuid, template=True)
        caster.register_action(action)
        self.granted_action_uuids = {action.uuid}
        return [(value.uuid, ident)], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None):
        caster = Entity.get(self.source_entity_uuid)
        if caster is not None:
            for identity in self.granted_action_uuids: caster.unregister_action_by_uuid(identity)
        self.granted_action_uuids.clear()
        super()._release_owned_runtime_state(parent_event=parent_event)


class DispelEvilAndGood(SpellAction):
    creates = (*SpellAction.creates, DispelEvilAndGoodEffect)
    name: str = "Dispel Evil and Good"
    description: str = "Concentrating self ward and touch Break Enchantment; no dismissal or possession simulation."
    spell_level: int = 5
    spell_school: str = "abjuration"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    target_type: TargetType = TargetType.SELF
    concentration: bool = True

    def _apply(self, event: SpellEvent):
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT), DispelEvilAndGoodEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid))


@srd_condition_identity(content_id="spatial_effect.spell.antilife_shell", display_name="Antilife Shell",
    description="Living creatures cannot cross the boundary; missiles, reach, spells and teleportation remain possible.")
class AntilifeShellZone(AreaCondition):
    name: str = "Antilife Shell"
    description: str = "Living creatures cannot cross the boundary; missiles, reach, spells and teleportation remain possible."
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.ENTITY
    area: AoEShape = Sphere(radius_feet=10)
    duration: Duration = Field(default_factory=lambda: Duration(duration=600, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset({WorldEdgeChannel.MOVEMENT})

    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode, terminal_provider_uuid=None):
        actor = Entity.get(requester_uuid) if requester_uuid else None
        if channel is not WorldEdgeChannel.MOVEMENT or actor is None or actor.uuid == self.anchor_uuid or                actor.creature_type in {CreatureType.CONSTRUCT, CreatureType.UNDEAD}: return False
        inside = start in self.affected_positions and self.allows_contribution_at(start)
        return any((cell in self.affected_positions and self.allows_contribution_at(cell)) != inside
                   for cell in bresenham_line(start, end))

    def relocate_anchor(self, position, *, parent_event: Event):
        if position == self.position or not self.is_active_spatial_condition(): return False
        transfer = EventQueue.get_event_by_uuid(parent_event.parent_event) if parent_event.parent_event else None
        if isinstance(transfer, PortalTransferEvent):
            return self.move_zone(position, parent_event=parent_event)
        old = set(self.affected_positions)
        swept=[]
        for center in bresenham_line(self.position,position)[1:]:
            swept.append(set(self.area_footprint(center)))
        if self.contributions_active() and any(entity.uuid != self.anchor_uuid
                and entity.is_deployed and entity.health.life_state is not LifeState.DEAD
                and entity.creature_type not in {CreatureType.CONSTRUCT, CreatureType.UNDEAD}
                and any((entity.position in footprint) != (entity.position in old) for footprint in swept)
                for entity in self._occupants_at(old.union(*swept))):
            link = self.parent_link
            if link is not None:
                owner = BaseBlock.get(link[0])
                if owner is not None: owner.remove_condition_by_uuid(link[1], parent_event=parent_event)
            else: self.deactivate(parent_event=parent_event)
            return False
        return self.move_zone(position, parent_event=parent_event)


class AntilifeShell(SpellAction):
    creates = (*SpellAction.creates, AntilifeShellZone)
    name: str = "Antilife Shell"
    description: str = "A concentrating moving shell hedges living creatures out for one hour."
    spell_level: int = 5
    spell_school: str = "abjuration"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    target_type: TargetType = TargetType.SELF
    concentration: bool = True

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None: return event.cancel(status_message="Shell caster absent")
        effect = event.phase_to(EventPhase.EFFECT)
        zone = AntilifeShellZone(source_entity_uuid=caster.uuid, position=caster.position, anchor_uuid=caster.uuid,
            content_ref=get_content_declaration(AntilifeShellZone).ref, effect_origin=event.to_effect_origin())
        return apply_concentrating_zone(self,effect,zone)
