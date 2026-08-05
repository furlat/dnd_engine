"""Abjuration spells - protection and defense.

Contains: Shield, MageArmor, ProtectionFromEnergy, Stoneskin, Counterspell,
          LesserRestoration, GreaterRestoration,
          ProtectionFromPoison, DeathWard, FreedomOfMovement,
          Resistance, ShieldOfFaith, Aid, Sanctuary, BeaconOfHope,
          AntimagicField
"""
import random
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field, PrivateAttr, model_validator

from dnd.core.base_actions import (
    ActionEvent,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    BaseAction,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
    Cost,
)
from dnd.core.action_types import CostType, spell_slot_cost_type
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, OutcomeProtection, SpellProtectionRegistry, SpellProtection
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionCategory,
    ConditionTag,
    DurationType,
)
from dnd.core.base_object import BaseObject
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.identities import ContentRef
from dnd.core.content.runtime import (
    BehaviorBinding,
    RuntimeBehaviorKind,
    active_runtime_behavior_binding,
)
from dnd.core.effect_types import EffectOriginKind
from dnd.core.events import AbilityName, Event, EventPhase, EventType, EventHandler, Trigger, RangeType, Range, EventQueue, SpatialChangeEvent, TakeDamageEvent, InstantDeathEvent, D20RollResultEvent, HealRollResultEvent
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
from dnd.core.aoe import Sphere
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import ArmorEquipEvent
from dnd.core.equipment_types import UnarmoredAc
from dnd.content_system.spatial_effect_materialization import (
    materialize_spatial_effect,
)

from dnd.core.dice import AttackOutcome, Dice
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SpellInterruptionLogData
from dnd.entity import Entity
from dnd.actions import (
    AttackEvent,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.conditions import Exhaustion
from dnd.creature_transforms import apply_incapacitated_transform
from dnd.spells.content_metadata import (
    srd_action_identity,
    srd_reaction_identity,
    srd_spell_identity,
)
from dnd.spells.transmutation import HasteEffect
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
    MAGIC_MISSILE_DAMAGE_EFFECT_ID,
)
from dnd.spatial_effect_content import (
    ANTIMAGIC_FIELD_RECIPE,
    GLOBE_OF_INVULNERABILITY_FIELD_RECIPE,
)
from dnd.spatial_effects import FieldEffect, SpatialEffect, SpatialEffectController


class CounterspellReactionEvent(ActionEvent):
    """Observable resolution of one Counterspell reaction."""

    name: str = Field(default="Counterspell", description="Reaction event name.")
    event_type: EventType = Field(
        default=EventType.TRIGGER_EVENT,
        description="Reaction event category.",
    )
    triggered_event_uuid: UUID = Field(
        description="Incoming spell event version that triggered the reaction.",
    )
    triggered_lineage_uuid: UUID = Field(
        description="Incoming spell lineage interrupted or challenged.",
    )
    incoming_spell_name: str = Field(
        description="Display name of the incoming spell.",
    )
    incoming_spell_level: int = Field(
        ge=0,
        le=9,
        description="Level of the incoming cast.",
    )
    counterspell_slot_level: int = Field(
        ge=3,
        le=9,
        description="Slot level spent on Counterspell.",
    )
    automatic: bool = Field(
        description="Whether the selected slot guarantees interruption.",
    )
    check_total: Optional[int] = Field(
        default=None,
        description="Spellcasting check total when required.",
    )
    check_dc: Optional[int] = Field(
        default=None,
        description="Spellcasting check DC when required.",
    )
    succeeded: bool = Field(
        description="Whether Counterspell interrupted the incoming spell.",
    )
    outcome_code: str = type_cast(
        str,
        Field(
            min_length=1,
            description="Stable Counterspell result code matching succeeded.",
        ),
    )
    reaction_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authored Counterspell reaction identity frozen at "
            "declaration."
        ),
    )
    incoming_spell_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authored incoming spell identity frozen at declaration."
        ),
    )

    @model_validator(mode="after")
    def validate_counterspell_resolution(
        self,
    ) -> "CounterspellReactionEvent":
        """Reject contradictory reaction, roll, and outcome-code facts."""
        binding = self.behavior_binding
        expected_reaction_identity = (
            binding.definition_ref.identity_key
            if isinstance(binding, BehaviorBinding)
            else None
        )
        if self.reaction_content_identity != expected_reaction_identity:
            raise ValueError(
                "reaction content identity must match its behavior binding",
            )

        expected_outcome_code = (
            COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
            if self.succeeded
            else COUNTERSPELL_FAILURE_OUTCOME_CODE
        )
        if self.outcome_code != expected_outcome_code:
            raise ValueError(
                "Counterspell outcome code contradicts its success result",
            )

        if self.automatic:
            if self.counterspell_slot_level < self.incoming_spell_level:
                raise ValueError(
                    "automatic Counterspell requires a sufficient slot",
                )
            if not self.succeeded:
                raise ValueError("automatic Counterspell must succeed")
            if self.check_total is not None or self.check_dc is not None:
                raise ValueError(
                    "automatic Counterspell forbids check evidence",
                )
            return self

        if self.counterspell_slot_level >= self.incoming_spell_level:
            raise ValueError(
                "checked Counterspell requires a lower-level slot",
            )
        if self.check_total is None or self.check_dc is None:
            raise ValueError(
                "checked Counterspell requires total and DC",
            )
        if self.check_dc != 10 + self.incoming_spell_level:
            raise ValueError(
                "Counterspell check DC must equal 10 plus spell level",
            )
        if self.succeeded != (self.check_total >= self.check_dc):
            raise ValueError("Counterspell success contradicts its check")
        return self

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
            outcome_code=self.outcome_code,
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
            reaction_content_identity=self.reaction_content_identity,
            incoming_spell_content_identity=(
                self.incoming_spell_content_identity
            ),
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
            data=data.model_dump(mode="json"),
            success=self.succeeded,
        )

    def validate_handler_result(self, result: Event) -> Event:
        """Cancel an evidence or event-type rewrite before queue storage."""
        evidence = _CounterspellEvidenceSnapshot.capture(self)
        if (
            type(result) is not CounterspellReactionEvent
            or not isinstance(result, CounterspellReactionEvent)
            or not self.handler_result_preserves_lifecycle(result)
            or not evidence.matches(result)
        ):
            return self.invalid_handler_result_cancellation(
                result,
                status_message=(
                    "Counterspell evidence or lifecycle changed after "
                    "resolution."
                ),
            )
        return result


@dataclass(frozen=True)
class _CounterspellEvidenceSnapshot:
    """Immutable resolution and attribution accepted at declaration."""

    name: str
    event_type: EventType
    lineage_uuid: UUID
    parent_event: Optional[UUID]
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID]
    outcome_source_entity_uuid: Optional[UUID]
    source_entity_name: Optional[str]
    target_entity_name: Optional[str]
    triggered_event_uuid: UUID
    triggered_lineage_uuid: UUID
    incoming_spell_name: str
    incoming_spell_level: int
    counterspell_slot_level: int
    automatic: bool
    check_total: Optional[int]
    check_dc: Optional[int]
    succeeded: bool
    outcome_code: str
    reaction_content_identity: Optional[str]
    incoming_spell_content_identity: Optional[str]
    behavior_binding: Optional[BehaviorBinding]

    @classmethod
    def capture(
        cls,
        event: CounterspellReactionEvent,
    ) -> "_CounterspellEvidenceSnapshot":
        """Capture every fact handlers must not rewrite after resolution."""
        return cls(
            name=event.name,
            event_type=event.event_type,
            lineage_uuid=event.lineage_uuid,
            parent_event=event.parent_event,
            source_entity_uuid=event.source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            outcome_source_entity_uuid=event.outcome_source_entity_uuid,
            source_entity_name=event.source_entity_name,
            target_entity_name=event.target_entity_name,
            triggered_event_uuid=event.triggered_event_uuid,
            triggered_lineage_uuid=event.triggered_lineage_uuid,
            incoming_spell_name=event.incoming_spell_name,
            incoming_spell_level=event.incoming_spell_level,
            counterspell_slot_level=event.counterspell_slot_level,
            automatic=event.automatic,
            check_total=event.check_total,
            check_dc=event.check_dc,
            succeeded=event.succeeded,
            outcome_code=event.outcome_code,
            reaction_content_identity=event.reaction_content_identity,
            incoming_spell_content_identity=(
                event.incoming_spell_content_identity
            ),
            behavior_binding=event.behavior_binding,
        )

    def event_updates(self) -> Dict[str, Any]:
        """Return the exact facts used to close a rewritten lifecycle."""
        return {
            "name": self.name,
            "event_type": self.event_type,
            "lineage_uuid": self.lineage_uuid,
            "parent_event": self.parent_event,
            "source_entity_uuid": self.source_entity_uuid,
            "target_entity_uuid": self.target_entity_uuid,
            "outcome_source_entity_uuid": self.outcome_source_entity_uuid,
            "source_entity_name": self.source_entity_name,
            "target_entity_name": self.target_entity_name,
            "triggered_event_uuid": self.triggered_event_uuid,
            "triggered_lineage_uuid": self.triggered_lineage_uuid,
            "incoming_spell_name": self.incoming_spell_name,
            "incoming_spell_level": self.incoming_spell_level,
            "counterspell_slot_level": self.counterspell_slot_level,
            "automatic": self.automatic,
            "check_total": self.check_total,
            "check_dc": self.check_dc,
            "succeeded": self.succeeded,
            "outcome_code": self.outcome_code,
            "reaction_content_identity": self.reaction_content_identity,
            "incoming_spell_content_identity": (
                self.incoming_spell_content_identity
            ),
            "behavior_binding": self.behavior_binding,
        }

    def matches(self, event: CounterspellReactionEvent) -> bool:
        """Return whether a phase preserves exact values and runtime types."""
        return all(
            type(getattr(event, field_name)) is type(expected_value)
            and getattr(event, field_name) == expected_value
            for field_name, expected_value in self.event_updates().items()
        )


def _accept_counterspell_phase(
    candidate: Event,
    evidence: _CounterspellEvidenceSnapshot,
    expected_phase: EventPhase,
) -> Optional[CounterspellReactionEvent]:
    """Accept cancellation or exact evidence; fail closed on any rewrite."""
    if not isinstance(candidate, CounterspellReactionEvent):
        return None
    if type(candidate) is not CounterspellReactionEvent:
        candidate.cancel(
            status_message="Counterspell event type changed after resolution.",
            use_register=True,
            **evidence.event_updates(),
        )
        return None
    valid_lifecycle = (
        candidate.use_register
        and (
            (
                candidate.canceled
                and candidate.phase is EventPhase.CANCEL
                and candidate.canceled_from_phase is expected_phase
            )
            or (
                not candidate.canceled
                and candidate.phase is expected_phase
                and candidate.canceled_from_phase is None
            )
        )
    )
    if not evidence.matches(candidate) or not valid_lifecycle:
        candidate.cancel(
            status_message=(
                "Counterspell evidence changed after resolution."
            ),
            use_register=True,
            **evidence.event_updates(),
        )
        return None
    return None if candidate.canceled else candidate


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

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target_uuid = self.target_entity_uuid
        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target_uuid,
            name="Shield",
            value=5
        )
        mod_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        def shield_magic_missile_blocker(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Block Magic Missile damage while Shield is active."""
            _ = handler_source_uuid
            if event.target_entity_uuid != target_uuid:
                return None
            if not _is_magic_missile_damage(event):
                return None
            return event.cancel(status_message=f"Shield blocks Magic Missile dart")

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
    if not entity or not isinstance(entity, Entity):
        return None

    if "Shield" in entity.active_conditions:
        return None

    if not entity.action_economy.can_afford("reactions", 1):
        return None

    slot_level = entity.get_lowest_spell_slot(1)
    if slot_level is None:
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

        event.ac.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=source_entity_uuid,
                name="Shield (reaction)",
                value=5
            )
        )

        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        buff = ShieldBuff(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        entity.add_condition(buff, parent_event=event)

        return event.with_updates(
            attack_outcome=AttackOutcome.MISS,
            status_message=f"{entity.name} casts Shield (+5 AC, attack blocked)",
        )

    if _is_magic_missile_damage(event):
        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        buff = ShieldBuff(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        entity.add_condition(buff, parent_event=event)

        return event.cancel(status_message=f"{entity.name} casts Shield, blocking Magic Missile")

    return None


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
    The handler can be toggled through its exact UUID.
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
            """End Mage Armor if any armor is equipped."""
            _ = handler_source_uuid

            if event.source_entity_uuid != condition_target_uuid:
                return None

            entity = Entity.get(condition_target_uuid)
            if not entity:
                return None

            if "Mage Armor" not in entity.active_conditions:
                return None

            if isinstance(event, ArmorEquipEvent):
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

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """Restore the old unarmored AC type on removal."""

        if not self.target_entity_uuid:
            return super()._remove(removal_event)

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity or not isinstance(target_entity, Entity):
            return super()._remove(removal_event)

        if self._old_unarmored_type:
            try:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc(self._old_unarmored_type)
            except ValueError:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE
        else:
            target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE
        return super()._remove(removal_event)


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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Mage Armor's protective AC condition."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target is unarmored and in range."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Caster not found")

        target_entity = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid
            else source_entity
        )
        if target_entity is None:
            return declaration_event.cancel(status_message="Target not found")

        if not target_entity.equipment.is_unarmored():
            return declaration_event.cancel(status_message="Target is wearing armor")

        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mage Armor condition to target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
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
        mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Protection from Energy's resistance condition."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target and range."""
        allowed_types = [DamageType.ACID, DamageType.COLD, DamageType.FIRE, DamageType.LIGHTNING, DamageType.THUNDER]
        if self.chosen_energy_type not in allowed_types:
            return declaration_event.cancel(
                status_message=f"Invalid energy type: {self.chosen_energy_type.value}. Must be acid, cold, fire, lightning, or thunder."
            )

        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Protection from Energy - grants resistance to chosen energy type."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )

        protection = ProtectionFromEnergyEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            energy_type=self.chosen_energy_type
        )
        target.add_condition(protection, parent_event=effect_event)

        if protection.applied:
            concentration.add_linked_condition(target.uuid, protection.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        target = Entity.get(self.target_entity_uuid)
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
            mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Stoneskin's physical resistance condition."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target and range."""
        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stoneskin - grants B/P/S resistance."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )

        stoneskin = StoneskinEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(stoneskin, parent_event=effect_event)

        if stoneskin.applied:
            concentration.add_linked_condition(target.uuid, stoneskin.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


def _begin_counterspell_reaction(
    incoming_event: SpellEvent,
    counterspeller: Entity,
    original_caster: Entity,
    *,
    slot_level: int,
    automatic: bool,
    succeeded: bool,
    check_total: Optional[int] = None,
    check_dc: Optional[int] = None,
) -> Optional[CounterspellReactionEvent]:
    """Publish Counterspell through Effect before committing its resources."""
    outcome_code = (
        COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
        if succeeded
        else COUNTERSPELL_FAILURE_OUTCOME_CODE
    )
    reaction_binding = active_runtime_behavior_binding()
    incoming_spell_binding = incoming_event.behavior_binding
    declaration = CounterspellReactionEvent(
        source_entity_uuid=counterspeller.uuid,
        target_entity_uuid=original_caster.uuid,
        source_entity_name=counterspeller.name,
        target_entity_name=original_caster.name,
        triggered_event_uuid=incoming_event.uuid,
        triggered_lineage_uuid=incoming_event.lineage_uuid,
        incoming_spell_name=incoming_event.name,
        incoming_spell_level=incoming_event.cast_at_level or incoming_event.spell_level,
        counterspell_slot_level=slot_level,
        automatic=automatic,
        check_total=check_total,
        check_dc=check_dc,
        succeeded=succeeded,
        outcome_code=outcome_code,
        behavior_binding=reaction_binding,
        reaction_content_identity=(
            reaction_binding.definition_ref.identity_key
            if isinstance(reaction_binding, BehaviorBinding)
            else None
        ),
        incoming_spell_content_identity=(
            incoming_spell_binding.definition_ref.identity_key
            if isinstance(incoming_spell_binding, BehaviorBinding)
            else None
        ),
        use_register=False,
    )
    evidence = _CounterspellEvidenceSnapshot.capture(declaration)
    accepted_declaration = _accept_counterspell_phase(
        EventQueue.publish_declaration(declaration),
        evidence,
        EventPhase.DECLARATION,
    )
    if accepted_declaration is None:
        return None
    execution = _accept_counterspell_phase(
        accepted_declaration.phase_to(
            EventPhase.EXECUTION,
            status_message="Counterspell reaction accepted.",
        ),
        evidence,
        EventPhase.EXECUTION,
    )
    if execution is None:
        return None
    effect = _accept_counterspell_phase(
        execution.phase_to(
            EventPhase.EFFECT,
            status_message="Counterspell reaction resolved.",
        ),
        evidence,
        EventPhase.EFFECT,
    )
    return effect


def _complete_counterspell_reaction(
    effect: CounterspellReactionEvent,
) -> CounterspellReactionEvent:
    """Publish the post-commit terminal Counterspell fact."""
    return effect.phase_to(
        EventPhase.COMPLETION,
        status_message="Counterspell reaction completed.",
    )


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

    if event.source_entity_uuid == source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity):
        return None

    if event.source_entity_uuid not in entity.senses.entities:
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

    if entity.get_lowest_spell_slot(3) is None:
        return None

    if not isinstance(event, SpellEvent):
        return None
    spell_cast_level = event.cast_at_level or event.spell_level

    auto_slot = entity.get_lowest_spell_slot(max(3, spell_cast_level))
    if auto_slot is not None:
        reaction = _begin_counterspell_reaction(
            event,
            entity,
            spell_caster,
            slot_level=auto_slot,
            automatic=True,
            succeeded=True,
        )
        if reaction is None:
            return None
        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(
            spell_slot_cost_type(reaction.counterspell_slot_level),
            1,
        )
        completion = _complete_counterspell_reaction(reaction)
        if completion.succeeded:
            return event.cancel(
                status_message="The spell was interrupted.",
                outcome_code=completion.outcome_code,
                outcome_source_entity_uuid=entity.uuid,
            )
        return None

    cheap_slot = entity.get_lowest_spell_slot(3)
    if cheap_slot is None:
        return None

    dc = 10 + spell_cast_level
    ability_name: AbilityName = entity.spellcasting.spellcasting_ability
    if learned_spell_ref is not None:
        source_ids = (
            entity.spellcasting.learned_reaction_spell_source_ids(
                learned_spell_ref,
            )
        )
        if not source_ids:
            return None
        ability_name = max(
            (
                entity.spellcasting.resolve_spellcasting_ability(source_id)
                for source_id in source_ids
            ),
            key=lambda candidate: (
                entity.ability_scores.get_ability(candidate).modifier,
                candidate,
            ),
        )
    ability_mod = entity.ability_scores.get_ability(ability_name).modifier
    d20 = random.randint(1, 20)
    check_total = d20 + ability_mod
    succeeded = check_total >= dc
    reaction = _begin_counterspell_reaction(
        event,
        entity,
        spell_caster,
        slot_level=cheap_slot,
        automatic=False,
        succeeded=succeeded,
        check_total=check_total,
        check_dc=dc,
    )
    if reaction is None:
        return None
    entity.action_economy.consume("reactions", 1)
    entity.action_economy.consume(
        spell_slot_cost_type(reaction.counterspell_slot_level),
        1,
    )
    completion = _complete_counterspell_reaction(reaction)
    if completion.succeeded:
        return event.cancel(
            status_message="The spell was interrupted.",
            outcome_code=completion.outcome_code,
            outcome_source_entity_uuid=entity.uuid,
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


class GlobeZone(SpatialEffectController):
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
    zone_center: Tuple[int, int] = Field(default=(0, 0), description="Grid position used as the immobile globe center.")
    zone_radius_feet: int = Field(default=10, description="Zone radius in feet.")
    affected_positions: set = Field(default_factory=set, description="Grid positions protected by the globe.")
    max_blocked_level: int = Field(default=5, description="Highest base spell level blocked by the globe.")
    _installed_handler_uuids: List[UUID] = PrivateAttr(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def _compute_positions(self) -> set:
        """Compute positions in the 10ft radius sphere around center."""
        shape = Sphere(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet
        )
        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def resolve_effect_footprint(self) -> Set[Tuple[int, int]]:
        """Return protected positions that exist on the active map."""
        grid = get_map()
        return {
            position
            for position in self._compute_positions()
            if grid.has_tile(*position)
        }

    def rollback_failed_install(self) -> None:
        """Release global blocker registrations after an interrupted install."""
        self._release_owned_runtime_state()

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release global blocker registrations on removal or rollback."""
        del parent_event
        SpellProtectionRegistry.unregister(self.uuid)
        for handler_uuid in self._installed_handler_uuids:
            handler = EventHandler.get(handler_uuid)
            if isinstance(handler, EventHandler):
                handler.remove()
        self._installed_handler_uuids.clear()

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        self.affected_positions = self.resolve_effect_footprint()
        handler_uuids = []

        blocker = self._create_spell_blocker()
        EventQueue.add_event_handler(blocker)
        handler_uuids.append(blocker.uuid)
        self._installed_handler_uuids.append(blocker.uuid)

        cond_blocker = self._create_condition_blocker()
        EventQueue.add_event_handler(cond_blocker)
        handler_uuids.append(cond_blocker.uuid)
        self._installed_handler_uuids.append(cond_blocker.uuid)

        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(self.affected_positions),
            max_blocked_level=self.max_blocked_level,
        ))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Globe of Invulnerability active"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_spell_blocker(self) -> EventHandler:
        """Cancel low-level spells cast from outside into the protected area."""
        globe = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.CAST_SPELL:
                return None
            if not isinstance(event, SpellEvent):
                return None

            base_level = event.spell_level
            if base_level > globe.max_blocked_level:
                return None

            source = Entity.get(event.source_entity_uuid)
            if not source or source.position in globe.affected_positions:
                return None

            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target and target.position in globe.affected_positions:
                    return event.cancel(
                        status_message=f"Globe of Invulnerability blocks L{base_level} spell"
                    )

            return None

        return EventHandler(
            name="Globe Spell Blocker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION
            )],
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_self_cast(declaration_event)

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

        field = materialize_spatial_effect(
            GLOBE_OF_INVULNERABILITY_FIELD_RECIPE,
            caster.uuid,
            position=caster.senses.position,
            faction=caster.faction,
            expected_type=FieldEffect,
        )
        zone = GlobeZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=field.uuid,
            zone_center=caster.senses.position,
            max_blocked_level=max_blocked
        )
        field.install_controller(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(field.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Globe of Invulnerability active — blocks spells L{max_blocked} and below"
        )


class BanishedCondition(BaseCondition):
    """Remove a banished entity from spatial play until cleanup.

    The condition stores the original position, owns incapacitation directly,
    removes the target from spatial registries, and restores it when removed.
    """
    name: str = Field(default="Banished", description="Condition name.")
    description: str = Field(default="Banished to another plane - removed from play", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Banishment removes the target's turn agency.",
    )
    original_position: Tuple[int, int] = Field(default=(0, 0), description="Grid position restored when banishment ends.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], None

        self.original_position = target.position
        outs = apply_incapacitated_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )

        grid = get_map()
        pos = self.original_position
        grid._entity_positions.pop(target.uuid, None)
        if pos in grid._entities_by_position:
            grid._entities_by_position[pos].discard(target.uuid)

        if target in Entity._entity_by_position[pos]:
            Entity._entity_by_position[pos].remove(target)

        if grid._events_enabled:
            spatial_event = SpatialChangeEvent.entity_left(pos, target.uuid, None, parent_event=declaration_event.uuid)
            grid._fire_spatial_event(spatial_event)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} banished from the battlefield"
        )
        return outs, [], [], [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """Return entity to original position when banishment ends."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            grid = get_map()
            pos = self.original_position

            occupants = grid.get_entities_at(pos) - {target.uuid}
            if occupants:
                for occ_uuid in occupants:
                    occ = Entity.get(occ_uuid)
                    if occ:
                        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                            adj = (pos[0] + dx, pos[1] + dy)
                            if grid.is_walkable_for(adj[0], adj[1], occ_uuid):
                                Entity.update_entity_position(occ, adj)
                                break
                    break

            grid._entity_positions[target.uuid] = pos
            if pos not in grid._entities_by_position:
                grid._entities_by_position[pos] = set()
            grid._entities_by_position[pos].add(target.uuid)

            if target not in Entity._entity_by_position[pos]:
                Entity._entity_by_position[pos].append(target)

            if grid._events_enabled:
                spatial_event = SpatialChangeEvent.entity_entered(pos, target.uuid, None,
                                                                   parent_event=removal_event.uuid if removal_event else None)
                grid._fire_spatial_event(spatial_event)

        return super()._remove(removal_event)


class Banishment(SpellAction):
    """Banish one failed-save target and link it to concentration.

    Upcasting increases the multi-target count, while each individual target
    resolves a Charisma save through the action convolution path.
    """
    name: str = Field(default="Banishment", description="Spell name.")
    description: str = Field(default="CHA save or banished (removed from play), concentration", description="Rules-facing spell summary.")
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for each target.",
    )
    valid_target_filter: str = Field(default="enemies", description="Target filter key for available action discovery.")
    include_self: bool = Field(default=False, description="Whether self-targeting is allowed.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Banishment's save-based removal branch."""
        if not isinstance(actor, Entity):
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="charisma",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "charisma").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="charisma",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CHA save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Banishment (CHA save)"
            )

        banished = BanishedCondition(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(banished, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if banished.applied:
            concentration.add_linked_condition(target.uuid, banished.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} banished!"
        )

_LESSER_RESTORATION_CONDITIONS = ("Blinded", "Deafened", "Paralyzed", "Poisoned")
_GREATER_RESTORATION_CONDITIONS = (
    "Charmed", "Poisoned", "Blinded", "Deafened", "Paralyzed", "Stunned", "Frightened"
)


def _remove_first_condition_by_name(
    target: Entity,
    condition_names: Tuple[str, ...],
    parent_event: Event,
) -> Optional[str]:
    """Remove the first active condition found in a deterministic name order."""
    for condition_name in condition_names:
        if condition_name in target.active_conditions:
            target.remove_condition(condition_name, parent_event=parent_event)
            return condition_name
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
    if not isinstance(condition, Exhaustion):
        return None

    previous_level = condition.level
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Lesser Restoration on {target.name}"
        )

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Greater Restoration on {target.name}"
        )

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Remove Curse on {target.name}"
        )

        removed: List[str] = []
        for cond_name, cond in list(target.active_conditions.items()):
            if ConditionTag.CURSE in cond.tags:
                target.remove_condition(cond_name, parent_event=effect_event)
                removed.append(cond_name)

        status = f"Removed {', '.join(removed)}" if removed else "No curse found"
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        target = Entity.get(self.target_entity_uuid)
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
        mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
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
            save_mod_uuid = save.bonus.self_contextual.add_advantage_modifier(
                ContextualAdvantageModifier(
                    name="Protection from Poison",
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=_protection_from_poison_save_advantage,
                )
            )
            outs.append((save.bonus.uuid, save_mod_uuid))

        target.add_condition_immunity("Poisoned", immunity_name="Protection from Poison")

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Protection from Poison applied to {target.name}"
        )
        return outs, [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunity on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target._remove_static_condition_immunity("Poisoned", "Protection from Poison")
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare poison resistance and Poisoned immunity support."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Protection from Poison on {target.name}"
        )

        if "Poisoned" in target.active_conditions:
            target.remove_condition("Poisoned", parent_event=effect_event)

        condition = ProtectionFromPoisonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        target = Entity.get(self.target_entity_uuid)
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
                    entity.remove_condition("Death Ward", parent_event=event)
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
                entity.remove_condition("Death Ward", parent_event=event)
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Death Ward's one-shot lethal protection condition."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Death Ward on {target.name}"
        )

        condition = DeathWardEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )

FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME = "Freedom of Movement Escape"
FREEDOM_OF_MOVEMENT_RESTRAINT_NAMES = ("Grappled", "Restrained")


def _freedom_of_movement_nonmagical_restraints(entity: Entity) -> List[str]:
    """Return active nonmagical restraints that Freedom of Movement can escape.

    Args:
        entity: Entity protected by Freedom of Movement.

    Returns:
        Names of active `Grappled` or `Restrained` conditions without the
        magical tag.
    """
    restraint_names: List[str] = []
    for condition_name in FREEDOM_OF_MOVEMENT_RESTRAINT_NAMES:
        condition = entity.active_conditions.get(condition_name)
        if condition is not None and ConditionTag.MAGICAL not in condition.tags:
            restraint_names.append(condition_name)
    return restraint_names


def _freedom_of_movement_available_movement(entity: Entity) -> int:
    """Return available movement before restraint max constraints are applied.

    Args:
        entity: Entity whose movement pool is inspected.

    Returns:
        Remaining movement after movement-cost modifiers, ignoring restraint
        max constraints so the escape can pay the SRD 5-foot cost.
    """
    movement_modifiers = entity.action_economy.movement.self_static.value_modifiers.values()
    return max(0, sum(modifier.normalized_value for modifier in movement_modifiers))


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
    """Spend movement to escape nonmagical Grappled or Restrained conditions."""

    name: str = Field(default=FREEDOM_OF_MOVEMENT_ESCAPE_ACTION_NAME, description="Display name for the automatic restraint escape action.")
    description: str = Field(default="Spend 5 feet of movement to escape nonmagical Grappled or Restrained conditions.", description="Rules-facing action summary.")
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

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate that a nonmagical restraint is available to escape.

        Args:
            declaration_event: Declaration event to advance or cancel.

        Returns:
            Execution event when escape is currently possible.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return declaration_event.cancel(status_message="Entity not found")
        if "Freedom of Movement" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Freedom of Movement is not active")
        restraint_names = _freedom_of_movement_nonmagical_restraints(entity)
        if not restraint_names:
            return declaration_event.cancel(status_message="No nonmagical restraint to escape")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

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
        for condition_name in restraint_names:
            entity.remove_condition(condition_name, parent_event=effect_event)
        escaped = ", ".join(restraint_names)
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} escaped {escaped}",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Consume 5 feet of movement while ignoring the escaped restraint cap.

        Args:
            completion_event: Completed action event carrying serialized costs.

        Returns:
            Completion event after the movement cost is recorded.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return completion_event.cancel(status_message="Entity not found")
        movement_cost = sum(cost.cost for cost in completion_event.costs if cost.cost_type == "movement")
        if _freedom_of_movement_available_movement(entity) < movement_cost:
            return completion_event.cancel(status_message="Not enough movement to escape")
        if movement_cost > 0:
            cost_modifier = NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                name="Freedom of Movement Escape Cost_cost",
                value=-movement_cost,
            )
            entity.action_economy.movement.self_static.add_value_modifier(cost_modifier)
        return completion_event


class FreedomOfMovementEffect(BaseCondition):
    """Ignores difficult terrain and blocks key movement-impairing conditions."""
    name: str = Field(default="Freedom of Movement", description="Condition name.")
    description: str = Field(default="Unaffected by difficult terrain, magical speed reduction, underwater penalties, magical Grappled, Restrained, or paralysis, and can spend 5 feet of movement to escape nonmagical restraints", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target.add_mobility_protection_source(
            self.uuid,
            ignores_difficult_terrain=True,
            ignores_magical_speed_reduction=True,
            ignores_underwater_penalties=True,
        )
        for condition_name in (
            "Grappled",
            "Restrained",
            "Paralyzed",
        ):
            target.add_condition_immunity_source(
                condition_name,
                self.uuid,
                immunity_check=(
                    _freedom_of_movement_magical_condition_immunity
                ),
            )
        target.register_condition_action(
            self,
            FreedomOfMovementEscape(
                source_entity_uuid=target.uuid,
                template=True,
            ),
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Freedom of Movement applied to {target.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove only this spell instance's movement-protection sources."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.remove_mobility_protection_source(self.uuid)
            for condition_name in (
                "Grappled",
                "Restrained",
                "Paralyzed",
            ):
                target.remove_condition_immunity_source(
                    condition_name,
                    self.uuid,
                )
        return super()._remove(event)


class FreedomOfMovement(SpellAction):
    """Freedom of Movement - 4th level Abjuration (NOT concentration)"""
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Freedom of Movement's mobility protection condition."""
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
                        "selected_target.immunity.condition.grappled",
                        "selected_target.immunity.condition.restrained",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.abjuration.FreedomOfMovementEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Freedom of Movement on {target.name}"
        )

        condition = FreedomOfMovementEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


def _freedom_of_movement_magical_condition_immunity(
    entity: Any,
    target_entity: Optional[Any],
    context: Optional[dict],
) -> bool:
    """Return whether an incoming condition is magical."""
    _ = entity, target_entity
    if context is None:
        return False
    condition_tags = context.get("condition_tags", set())
    return ConditionTag.MAGICAL in condition_tags


def _resistance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to saving throw roll. One-use: removes condition after firing."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = random.randint(1, 4)
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
        target = Entity.get(self.target_entity_uuid)
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Resistance's one-use saving-throw support condition."""
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
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
        target.add_condition(resistance_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if resistance_effect.applied:
            concentration.add_linked_condition(target.uuid, resistance_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Resistance cast on {target.name}"
        )


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
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(
            NumericalModifier(
                name="Shield of Faith",
                value=2,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Shield of Faith's AC bonus condition."""
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Shield of Faith cast on {target.name}"
        )

        condition = ShieldOfFaithEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if condition.applied:
            concentration.add_linked_condition(target.uuid, condition.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = target.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier(
                name="Aid",
                value=self.hp_bonus,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
        outs.append((target.health.max_hit_points_bonus.uuid, modifier_uuid))

        con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
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
            con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
            max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
            return {"resulting_max_hp": max_hp}
        return {}


class Aid(SpellAction):
    """Increase maximum hit points for up to three targets.

    This implementation applies a max-HP condition to each target resolved by
    the multi-target action path.
    """
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

    def get_num_projectiles(self) -> int:
        """Return Aid's current fixed target count."""
        return 3

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Aid's maximum-hit-point support condition."""
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        hp_bonus = 5 * max(1, self.cast_at_level - 1)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Aid grants +{hp_bonus} max HP to {target.name}"
        )

        condition = AidEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            hp_bonus=hp_bonus,
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        target = Entity.get(self.target_entity_uuid)
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
            if event.target_entity_uuid != warded_uuid:
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
                return event.cancel(status_message=f"{attacker.name} fails WIS save — Sanctuary blocks attack")

        return EventHandler(
            name="Sanctuary Ward",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=warded_uuid,
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
            if event.source_entity_uuid != warded_uuid:
                return None

            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            warded = Entity.get(warded_uuid)
            if not warded:
                return None

            if target and warded.is_enemy(target):
                if "Sanctuary" in warded.active_conditions:
                    active = warded.active_conditions.get("Sanctuary")
                    if active and active.uuid == condition_uuid:
                        warded.remove_condition("Sanctuary", parent_event=event)
            return None

        return EventHandler(
            name="Sanctuary Self-Break",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Sanctuary's attack-ward condition."""
        if not isinstance(actor, Entity):
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Sanctuary cast on {target.name}"
        )

        condition = SanctuaryEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            spell_dc=dc,
        )
        condition.duration.duration_type = DurationType.ROUNDS
        condition.duration.duration = 10
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        wis_save = target.saving_throws.get_saving_throw("wisdom")
        modifier_uuid = wis_save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Beacon of Hope",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
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

    def get_num_projectiles(self) -> int:
        """Return the engine cap for affected allies."""
        return 6

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Beacon of Hope inspires {target.name}"
        )

        condition = BeaconOfHopeEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if condition.applied:
            concentration.add_linked_condition(target.uuid, condition.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Beacon of Hope cast on {target.name}"
        )


class AntimagicSuppression(BaseCondition):
    """Hold one magical condition suppressed by Antimagic Field.

    The marker has a unique condition name per suppressed condition. Removing
    the marker attempts to restore the saved condition and reconnect its parent
    concentration link if that parent is still active.
    """
    name: str = Field(default="Antimagic Suppression", description="Condition name.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.INTERNAL, description="Condition category.")
    suppressed_condition: BaseCondition = Field(description="The condition object being suppressed")
    saved_parent_link: Optional[Tuple[UUID, UUID]] = Field(
        default=None,
        description="Saved (parent_block_uuid, parent_condition_uuid) for reconnection"
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Antimagic Suppression stores {self.suppressed_condition.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Re-add the suppressed condition when the marker is removed."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        cond = self.suppressed_condition
        if target and target.is_active and not cond.duration.is_expired:
            if self.saved_parent_link:
                _, parent_cond_uuid = self.saved_parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if not isinstance(parent_cond, BaseCondition) or not parent_cond.applied:
                    return super()._remove(event)

            cond.modifers_uuids.clear()
            cond.event_handlers_uuids.clear()
            cond.spatial_handler_uuids.clear()
            cond.sub_conditions.clear()
            cond.linked_conditions.clear()

            target.add_condition(cond, parent_event=event)

            if self.saved_parent_link and cond.applied:
                _, parent_cond_uuid = self.saved_parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if isinstance(parent_cond, BaseCondition) and parent_cond.applied:
                    parent_cond.add_linked_condition(target.uuid, cond.uuid)

        return super()._remove(event)


class AntimagicFieldZone(SpatialEffectController):
    """Maintain the caster-following Antimagic Field suppression zone.

    The zone blocks spell casts from or into the area, suppresses existing
    magical conditions with `AntimagicSuppression` markers, restores those
    conditions when entities leave, and updates spell-protection positions as
    the caster moves.
    """
    name: str = Field(default="Antimagic Field Zone", description="Condition name.")
    description: str = Field(default="10ft sphere suppresses all magic", description="Rules-facing condition summary.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    zone_center: Tuple[int, int] = Field(default=(0, 0), description="Current grid position at the zone center.")
    zone_radius_feet: int = Field(default=10, description="Zone radius in feet.")
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Grid positions currently inside the field.")
    suppression_markers: Dict[UUID, List[UUID]] = Field(
        default_factory=dict,
        description="Suppression marker condition UUIDs keyed by suppressed entity UUID.",
    )
    _installed_handler_uuids: List[UUID] = PrivateAttr(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def _compute_positions(self) -> Set[Tuple[int, int]]:
        """Compute positions in the 10ft radius sphere around center."""
        shape = Sphere(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet
        )
        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def resolve_effect_footprint(self) -> Set[Tuple[int, int]]:
        """Return suppressed positions that exist on the active map."""
        grid = get_map()
        return {
            position
            for position in self._compute_positions()
            if grid.has_tile(*position)
        }

    def rollback_failed_install(self) -> None:
        """Release global handlers and suppression leases after failed setup."""
        self._release_owned_runtime_state()

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release global handlers and suppression leases on every exit."""
        SpellProtectionRegistry.unregister(self.uuid)
        for handler_uuid in self._installed_handler_uuids:
            handler = EventHandler.get(handler_uuid)
            if isinstance(handler, EventHandler):
                handler.remove()
        self._installed_handler_uuids.clear()
        self._unsuppress_all_entities(parent_event=parent_event)

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        self.affected_positions = self.resolve_effect_footprint()
        handler_uuids: List[UUID] = []

        blocker = self._create_spell_blocker()
        EventQueue.add_event_handler(blocker)
        handler_uuids.append(blocker.uuid)
        self._installed_handler_uuids.append(blocker.uuid)

        entry = self._create_entity_entry_handler()
        EventQueue.add_event_handler(entry)
        handler_uuids.append(entry.uuid)
        self._installed_handler_uuids.append(entry.uuid)

        exit_handler = self._create_entity_exit_handler()
        EventQueue.add_event_handler(exit_handler)
        handler_uuids.append(exit_handler.uuid)
        self._installed_handler_uuids.append(exit_handler.uuid)

        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(self.affected_positions),
            max_blocked_level=9,
        ))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Antimagic Field active"
        )

        grid = get_map()
        for pos in self.affected_positions:
            for entity_uuid in grid.get_entities_at(pos):
                self._suppress_entity(entity_uuid, parent_event=effect_event)

        return [], handler_uuids, [], [], effect_event

    def _suppress_entity(self, entity_uuid: UUID, parent_event: Optional[Event] = None) -> None:
        """Suppress all top-level magical conditions on an entity."""
        entity = Entity.get(entity_uuid)
        if not entity:
            return

        to_suppress: List[BaseCondition] = []
        for cond in list(entity.active_conditions.values()):
            if not cond.magical_origin:
                continue
            if cond.parent_condition is not None:
                continue
            if cond.name == "Concentrating":
                continue
            if cond.uuid == self.uuid:
                continue
            if not cond.applied:
                continue
            to_suppress.append(cond)

        for cond in to_suppress:
            if not cond.applied:
                continue

            saved_parent_link: Optional[Tuple[UUID, UUID]] = None
            if cond.parent_link:
                saved_parent_link = cond.parent_link
                _, parent_cond_uuid = cond.parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if isinstance(parent_cond, BaseCondition):
                    parent_cond.linked_conditions = [
                        lc for lc in parent_cond.linked_conditions
                        if lc[1] != cond.uuid
                    ]
                cond.parent_link = None

            if isinstance(cond, HasteEffect):
                cond.apply_lethargy = False

            assert cond.name is not None
            entity.remove_condition(cond.name, parent_event=parent_event)

            if isinstance(cond, HasteEffect):
                cond.apply_lethargy = True

            marker = AntimagicSuppression(
                name=f"Antimagic Suppression: {cond.name}",
                source_entity_uuid=type_cast(UUID, self.source_entity_uuid),
                target_entity_uuid=entity.uuid,
                suppressed_condition=cond,
                saved_parent_link=saved_parent_link
            )
            entity.add_condition(marker, parent_event=parent_event)

            if marker.applied:
                if entity.uuid not in self.suppression_markers:
                    self.suppression_markers[entity.uuid] = []
                self.suppression_markers[entity.uuid].append(marker.uuid)

    def _unsuppress_entity(self, entity_uuid: UUID, parent_event: Optional[Event] = None) -> None:
        """Remove all suppression markers from an entity, restoring conditions."""
        marker_uuids = self.suppression_markers.pop(entity_uuid, [])
        entity = Entity.get(entity_uuid)
        if not entity:
            return

        for marker_uuid in list(marker_uuids):
            entity.remove_condition_by_uuid(marker_uuid, parent_event=parent_event)

    def _unsuppress_all_entities(self, parent_event: Optional[Event] = None) -> None:
        """Unsuppress all tracked entities."""
        for entity_uuid in list(self.suppression_markers.keys()):
            self._unsuppress_entity(entity_uuid, parent_event=parent_event)

    def _create_spell_blocker(self) -> EventHandler:
        """Block ALL spells when caster or target is in the zone."""
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpellEvent):
                return None

            source = Entity.get(event.source_entity_uuid)
            if source and source.position in zone.affected_positions:
                return event.cancel(
                    status_message=f"Antimagic Field blocks {event.name}"
                )

            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target and target.position in zone.affected_positions:
                    return event.cancel(
                        status_message=f"Antimagic Field blocks {event.name}"
                    )

            return None

        return EventHandler(
            name="Antimagic Spell Blocker",
            source_entity_uuid=type_cast(UUID, self.source_entity_uuid),
            trigger_conditions=[Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Recenter suppression and membership when the field anchor moves."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        old_positions = set(self.affected_positions)
        self.zone_center = position
        new_positions = self.resolve_effect_footprint()
        self.affected_positions = new_positions
        effect = (
            SpatialEffect.get_effect(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if effect is None:
            raise RuntimeError("Antimagic Field effect owner is unavailable")
        effect.set_position(position)
        effect.synchronize_footprint(
            new_positions,
            parent_event=parent_event,
        )

        SpellProtectionRegistry.unregister(self.uuid)
        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(new_positions),
            max_blocked_level=9,
        ))

        grid = get_map()
        for old_position in old_positions - new_positions:
            for entity_uuid in grid.get_entities_at(old_position):
                if entity_uuid in self.suppression_markers:
                    self._unsuppress_entity(
                        entity_uuid,
                        parent_event=parent_event,
                    )

        for new_position in new_positions - old_positions:
            for entity_uuid in grid.get_entities_at(new_position):
                if entity_uuid != caster_uuid:
                    self._suppress_entity(
                        entity_uuid,
                        parent_event=parent_event,
                    )

    def _create_entity_entry_handler(self) -> EventHandler:
        """Suppress magical conditions when an entity enters the zone."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            if event.entity_uuid == caster_uuid:
                return None
            if event.position not in zone.affected_positions:
                return None
            zone._suppress_entity(event.entity_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Antimagic Entry Suppress",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_entity_exit_handler(self) -> EventHandler:
        """Restore suppressed conditions when an entity leaves the zone."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            if event.entity_uuid == caster_uuid:
                return None
            if event.entity_uuid in zone.suppression_markers:
                zone._unsuppress_entity(event.entity_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Antimagic Exit Restore",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class AntimagicField(SpellAction):
    """Create a caster-following field that suppresses magic.

    The maintained zone blocks spell casts and temporarily removes magical
    conditions while preserving concentration parents for restoration.
    """
    name: str = Field(default="Antimagic Field", description="Spell name.")
    description: str = Field(default="10ft sphere suppresses all magic, concentration", description="Rules-facing spell summary.")
    spell_level: int = Field(default=8, description="Base spell level.")
    spell_school: str = Field(default="abjuration", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Self range used by action discovery and validation.",
    )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_self_cast(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Antimagic Field"
        )

        field = materialize_spatial_effect(
            ANTIMAGIC_FIELD_RECIPE,
            caster.uuid,
            position=caster.senses.position,
            faction=caster.faction,
            expected_type=FieldEffect,
        )
        zone = AntimagicFieldZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=field.uuid,
            zone_center=caster.senses.position
        )
        field.install_controller(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if zone.applied:
            concentration.add_linked_condition(field.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Antimagic Field active around {caster.name}"
        )
