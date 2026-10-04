"""Concrete engine conditions and condition-related event handlers."""

from types import MappingProxyType
from dataclasses import dataclass

from pydantic import Field, PrivateAttr
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, ConditionStateChangedEvent, Duration
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionCategory,
    ConditionTag,
    DurationType,
    InvoluntarySustainLoss,
    SustainLossCause,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.entity import Entity
from dnd.types.actor import ConditionState
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.core.item_types import ItemConcentrationSlot, ItemLocation
from dnd.types.residue_fear import PaidEntryRetreat, ResidueFearOrigin
from typing import Callable, Dict, Any, Optional, List, Literal, Set, Tuple, TypeVar
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    ContextAwareAdvantage,
    AutoHitModifier,
    AdvantageStatus,
    AutoHitStatus,
    ContextualNumericalModifier,
    ArithmeticFactor,
    NumericalModifier,
    ContextAwareNumerical,
    ContextAwareAutoHit,
    ContextualAutoHitModifier,
    ContextualAdvantageModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.blocks.skills import all_skills, skills_requiring_sight, skills_requiring_hearing, skills_social
from dnd.core.base_block import CommittedConditionRemovals, LightLevel, PreparedConditionRemovals
from dnd.core.geometry import bresenham_line
from dnd.core.elevation import support_distance_feet
from dnd.core.gridmap import get_map
from dnd.core.ground import ground_neighbors
from dnd.types.world import OccupancyLayer
from uuid import UUID
from functools import partial
from dnd.core.events import (
    DamageAppliedEvent,
    DeathEvent,
    Event,
    EventPhase,
    EventType,
    EventHandler,
    ReviveEvent,
    SavingThrowEvent,
    SpatialChangeEvent,
    StepMovementEvent,
    Trigger,
    EventQueue,
)
from dnd.core.base_actions import ActionEvent
from dnd.core.dice import RollType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SkillCheckLogData, DiceRollDisplay, ModifierBreakdown
from dnd.creature_transforms import (
    apply_incapacitated_transform,
    remove_modifier_ownership,
    apply_opportunity_attack_immunity_transform,
    apply_paralyzed_transform,
    apply_prone_geometry_transform,
    apply_stunned_transform,
    apply_unconscious_transform,
    apply_visual_denial_transform,
)

UNDERWATER_MELEE_EXCEPTION_WEAPONS: Tuple[str, ...] = ("dagger", "javelin", "shortsword", "spear", "trident")
UNDERWATER_RANGED_EXCEPTION_WEAPON_TOKENS: Tuple[str, ...] = ("crossbow", "net", "javelin", "spear", "trident", "dart")

_CoreConditionDefinition = TypeVar("_CoreConditionDefinition")


def _core_condition_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    source_anchor: str,
    sort_order: int,
) -> Callable[[_CoreConditionDefinition], _CoreConditionDefinition]:
    """Declare one independently provided public core condition."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.CONDITION,
        runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
        pack_id="core.rules",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("condition", "core", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id.removeprefix("condition."),
                ui_group="conditions.core",
            ),
            ordering=ContentOrdering(
                sort_group="conditions.core",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=source_anchor,
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Playable core condition identity; current implementation "
                "coverage remains tracked independently."
            ),
        ),
    )


def underwater_weapon_name(context: Optional[Dict[str, Any]]) -> str:
    """Extract a normalized weapon name from attack context.

    Args:
        context: Runtime attack context supplied by the attack action.

    Returns:
        Lowercase weapon name, or an empty string when context is missing.
    """
    weapon_name = context.get("weapon_name") if context else None
    return str(weapon_name or "").lower()


def underwater_range_type(context: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract the normalized attack range type from attack context.

    Args:
        context: Runtime attack context supplied by the attack action.

    Returns:
        The lowercase range type value, or None when context is missing.
    """
    range_type = context.get("range_type") if context else None
    return str(range_type).lower() if range_type is not None else None


def underwater_attack_disadvantage(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[AdvantageModifier]:
    """Return SRD underwater attack disadvantage when it applies.

    Args:
        source_entity_uuid: Attacking entity UUID.
        target_entity_uuid: Optional attacked entity UUID.
        context: Runtime attack context with weapon and range metadata.

    Returns:
        Disadvantage modifier when the underwater attack is penalized,
        otherwise None.
    """
    source_entity = Entity.get(source_entity_uuid)
    if not isinstance(source_entity, Entity) or source_entity.ignore_underwater_penalties:
        return None

    range_type = underwater_range_type(context)
    weapon_name = underwater_weapon_name(context)
    if range_type == "reach":
        if source_entity.swimming_speed > 0 or weapon_name in UNDERWATER_MELEE_EXCEPTION_WEAPONS:
            return None
    elif range_type == "range":
        if any(token in weapon_name for token in UNDERWATER_RANGED_EXCEPTION_WEAPON_TOKENS):
            return None
    else:
        return None

    return AdvantageModifier(
        name="Underwater",
        value=AdvantageStatus.DISADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


def underwater_ranged_automiss(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[AutoHitModifier]:
    """Return SRD underwater automatic miss beyond normal range.

    Args:
        source_entity_uuid: Attacking entity UUID.
        target_entity_uuid: Optional attacked entity UUID.
        context: Runtime attack context with range metadata.

    Returns:
        Automatic miss modifier for ranged underwater attacks beyond normal
        range, otherwise None.
    """
    source_entity = Entity.get(source_entity_uuid)
    if not isinstance(source_entity, Entity) or source_entity.ignore_underwater_penalties:
        return None

    if underwater_range_type(context) != "range" or not (context and context.get("is_long_range")):
        return None

    return AutoHitModifier(
        name="Underwater",
        value=AutoHitStatus.AUTOMISS,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


class ExtraAttacksGranted(BaseCondition):
    """Internal marker for an ordinary Attack batch earned this turn.

    Attributes:
        name: Internal attack-batch marker.
        duration: One round, matching the attack credit lifetime.
        condition_category: Internal bookkeeping category.
    """

    name: str = Field(default="ExtraAttacksGranted", description="Internal attack-batch marker.")
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=1, duration_type=DurationType.ROUNDS),
        description="One round, matching the attack credit lifetime.",
    )
    condition_category: ConditionCategory = Field(default=ConditionCategory.INTERNAL, description="Internal bookkeeping category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        return [], [], [], [], declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Marked as ExtraAttacksGranted",
        )


class HasAttacked(BaseCondition):
    """Marker condition for an entity that attacked this turn.

    The global standard-action handler records all attacks and whether one
    targeted a hostile creature, so object attacks do not sustain Rage.
    """
    name: str = Field(default="HasAttacked", description="Condition name.")
    attacked_hostile_creature: bool = Field(
        default=False,
        description="Whether a committed attack targeted a hostile creature during this marker's lifetime.",
    )
    description: str = Field(default="Has made an attack this turn using an action", description="Condition description.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.INTERNAL, description="Internal marker category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Marked as HasAttacked"
        )
        return [], [], [], [], effect_event


class HasTakenDamage(BaseCondition):
    """Marker condition for an entity that took damage this turn.

    The global damage handler applies this marker. Class features can use it for
    rage maintenance decisions.
    """
    name: str = Field(default="HasTakenDamage", description="Condition name.")
    description: str = Field(default="Took damage this turn", description="Condition description.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.INTERNAL, description="Internal marker category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Marked as HasTakenDamage"
        )
        return [], [], [], [], effect_event


@_core_condition_identity(
    content_id="condition.underwater",
    display_name="Underwater",
    description="Applies the core penalties for fighting while underwater.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Underwater Combat",
    sort_order=10,
)
class Underwater(BaseCondition):
    """Environmental condition for SRD underwater attack penalties."""

    name: str = Field(default="Underwater", description="Condition name.")
    description: str = Field(
        default="Underwater combat imposes SRD attack penalties unless bypassed by swimming speed, weapon exceptions, or Freedom of Movement.",
        description="Condition description.",
    )
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            disadvantage_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Underwater",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=underwater_attack_disadvantage,
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, disadvantage_uuid))

            automiss_uuid = target_entity.equipment.attack_bonus.self_contextual.add_auto_hit_modifier(
                modifier=ContextualAutoHitModifier(
                    name="Underwater",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=underwater_ranged_automiss,
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, automiss_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Underwater to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


def has_attacked_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Apply HasAttacked when the source entity's attack reaches execution.

    Args:
        event: Event being processed by the handler.
        source_entity_uuid: Entity UUID that owns the handler.

    Returns:
        None; the attack event is not modified.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    if event.canceled:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if not EventQueue.is_first_at_phase(event):
        return None

    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    hostile_creature = target is not None and entity.is_enemy_of(target.uuid)
    current = entity.active_conditions.get("HasAttacked")
    if isinstance(current, HasAttacked):
        current.attacked_hostile_creature |= hostile_creature
    else:
        has_attacked = HasAttacked(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid,
            attacked_hostile_creature=hostile_creature,
        )
        has_attacked.duration.duration_type = DurationType.ROUNDS
        has_attacked.duration.duration = 1
        entity.add_condition(has_attacked, parent_event=event)

    return None


def has_taken_damage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Apply HasTakenDamage when the owner is the damage target.

    Args:
        event: Event being processed by the handler.
        source_entity_uuid: Entity UUID that owns the handler.

    Returns:
        None; the damage event is not modified.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if "HasTakenDamage" not in entity.active_conditions:
        has_taken_damage = HasTakenDamage(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        has_taken_damage.duration.duration_type = DurationType.ROUNDS
        has_taken_damage.duration.duration = 1
        entity.add_condition(has_taken_damage, parent_event=event)

    return None


def create_has_attacked_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an attack tracker handler for an entity.

    Args:
        source_entity_uuid: UUID of the entity that owns the handler.

    Returns:
        Event handler that applies HasAttacked on attack execution.
    """
    return EventHandler(
        name="HasAttacked Tracker",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=has_attacked_processor
    )


def create_has_taken_damage_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create a damage tracker handler for an entity.

    Args:
        source_entity_uuid: UUID of the entity that owns the handler.

    Returns:
        Event handler that applies HasTakenDamage when the entity takes damage.
    """
    return EventHandler(
        name="HasTakenDamage Tracker",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_APPLIED,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=has_taken_damage_processor
    )


@_core_condition_identity(
    content_id="condition.blinded",
    display_name="Blinded",
    description="Cannot see and suffers the standard blinded combat effects.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Blinded",
    sort_order=20,
)
class Blinded(BaseCondition):
    """Sight-loss condition with self attack penalties and attacker advantage."""

    name: str = Field(default="Blinded", description="Condition name.")
    description: str = Field(
        default="A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage.",
        description="Condition description.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        elif isinstance(target_entity,Entity):
            outs = []
            outs.extend(
                apply_visual_denial_transform(
                    target_entity,
                    name=self.name,
                    effect_source_uuid=self.source_entity_uuid,
                )
            )
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied attack advantage modifers from Blinded to {target_entity.name}")
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            for skill in skills_requiring_sight:
                skill_obj = target_entity.skill_set.get_skill(skill)

                modifier_uuid=skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Blinded",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied skill advantage modifers from Blinded to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


@_core_condition_identity(
    content_id="condition.charmed",
    display_name="Charmed",
    description="Cannot attack the charmer and grants the charmer social advantage.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Charmed",
    sort_order=30,
)
class Charmed(BaseCondition):
    """Charmer-contextual attack block and social-check support condition."""

    name: str = Field(default="Charmed", description="Condition name.")
    description: str = Field(
        default="A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects.",
        description="Condition description.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            charmed_attack_check = self.get_charmed_attack_check()
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_contextual.add_auto_hit_modifier(modifier=ContextualAutoHitModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_attack_check))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied contextual auto hit modifers from Charmed to {target_entity.name}")
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))

            charmed_skill_check = self.get_charmed_skill_check()
            for skill in skills_social:
                skill_obj = target_entity.skill_set.get_skill(skill)
                to_target_static_condition_uuid = skill_obj.skill_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_skill_check))
                outs.append((skill_obj.skill_bonus.uuid,to_target_static_condition_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied contextual advantage modifers from Charmed to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    @staticmethod
    def charmed_attack_check(charmer_id: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AutoHitModifier]:
        """Return automiss when the charmed creature targets its charmer.

        Args:
            charmer_id: UUID of the entity that caused the Charmed condition.
            source_entity_uuid: UUID of the conditioned creature.
            target_entity_uuid: UUID currently being targeted by the conditioned creature.
            context: Optional contextual data from the modifier evaluation.

        Returns:
            Automiss modifier if the target is the charmer, otherwise None.
        """
        if  target_entity_uuid:
            entity = Entity.get(target_entity_uuid)
            if entity and entity.uuid == charmer_id:
                return AutoHitModifier(name="Charmed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_charmed_attack_check(self) -> ContextAwareAutoHit:
        """Return the contextual automiss callable for this charmer."""
        partial_function = partial(self.charmed_attack_check, self.source_entity_uuid)
        return partial_function

    @staticmethod
    def charmed_skill_check(charmer_id: UUID,charmed_id: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """Return advantage for the charmer's social checks against the target.

        Args:
            charmer_id: UUID of the entity that caused the Charmed condition.
            charmed_id: UUID of the conditioned creature.
            source_entity_uuid: UUID supplied by the propagated skill modifier.
            target_entity_uuid: UUID supplied by the propagated skill modifier.
            context: Optional contextual data from the modifier evaluation.

        Returns:
            Advantage modifier if the check is charmer against charmed target.
        """
        if charmer_id == target_entity_uuid and charmed_id == source_entity_uuid:
            return AdvantageModifier(name="Charmed",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_charmed_skill_check(self) -> ContextAwareAdvantage:
        """Return the contextual social-check callable for this charmer."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualAdvantageModifier")
        partial_function = partial(self.charmed_skill_check, self.source_entity_uuid, self.target_entity_uuid)
        return partial_function


@_core_condition_identity(
    content_id="condition.dashing",
    display_name="Dashing",
    description="Temporarily gains additional movement equal to current speed.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Dash",
    sort_order=40,
)
class Dashing(BaseCondition):
    """Status condition that adds movement equal to the target's current speed."""

    name: str = Field(default="Dashing", description="Condition name.")
    description: str = Field(default="A dashing creature gains extra movement equal to its current speed.", description="Condition description.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Status-effect condition category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT,
            update={"condition": self}, status_message=f"{target_entity.name} gains a Dash movement credit")

    def on_membership_changed(self, event: Event) -> None:
        # Credit belongs to the turn, not to the expiring/replaced marker.
        if self.applied:
            target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
            if target is not None:
                target.action_economy.dash_count += 1


@_core_condition_identity(
    content_id="condition.deafened",
    display_name="Deafened",
    description="Cannot hear and automatically fails hearing-dependent checks.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Deafened",
    sort_order=50,
)
class Deafened(BaseCondition):
    """Hearing-loss condition that autofails hearing-based skills."""

    name: str = Field(default="Deafened", description="Condition name.")
    description: str = Field(default="A deafened creature can't hear and automatically fails any ability check that requires hearing.", description="Condition description.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            for skill in skills_requiring_hearing:
                skill_obj = target_entity.skill_set.get_skill(skill)
                modifier_uuid = skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Deafened",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied skills auto hit modifers from Deafened to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")



def apply_shared_sensory_condition(
    parent: BaseCondition,
    target: Entity,
    condition_type: type[Blinded] | type[Deafened],
    event: Event,
) -> Optional[Event]:
    """Retain one effective sense denial while any owning source remains."""
    existing = next((condition for condition in target.active_conditions_by_uuid.values()
                     if isinstance(condition, condition_type)), None)
    if existing is not None:
        parent.add_shared_subcondition(existing)
        return None
    condition = condition_type(
        source_entity_uuid=parent.source_entity_uuid,
        target_entity_uuid=target.uuid,
        parent_condition=parent.uuid,
        tags=set(parent.tags),
    )
    applied = target.add_condition(condition, parent_event=event)
    if applied is not None and not applied.canceled and applied.phase is EventPhase.COMPLETION:
        parent.add_shared_subcondition(condition)
    return applied


def exhaustion_revive_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Reduce the owning entity's Exhaustion when a revival permits it."""
    if (
        not isinstance(event, ReviveEvent)
        or event.entity_uuid != source_entity_uuid
        or not event.reduce_exhaustion
    ):
        return None

    entity = Entity.get(source_entity_uuid)
    if isinstance(entity, Entity):
        entity.reduce_condition_level("Exhaustion", parent_event=event)
    return None


@_core_condition_identity(
    content_id="condition.exhaustion",
    display_name="Exhaustion",
    description="Tracks cumulative levels of exhaustion and their penalties.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Exhaustion",
    sort_order=60,
)
class Exhaustion(BaseCondition):
    """Cumulative exhaustion condition with SRD level effects."""

    name: str = Field(default="Exhaustion", description="Condition name.")
    description: str = Field(
        default="Exhaustion is measured in six cumulative levels: ability-check disadvantage, halved speed, attack/save disadvantage, halved hit point maximum, speed zero, and death.",
        description="Condition description.",
    )
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.EXHAUSTION},
        description="Condition tags used by restoration and exhaustion-aware effects.",
    )
    level: int = Field(
        default=1,
        ge=1,
        le=6,
        description="Current exhaustion level from 1 to 6.",
    )

    def supports_level_reduction(self) -> bool:
        """Return whether Exhaustion can be reduced by level."""
        return True

    def get_reduced_level_condition(self, amount: int = 1) -> Optional[BaseCondition]:
        """Create the lower-level Exhaustion replacement.

        Args:
            amount: Number of exhaustion levels to remove.

        Returns:
            Replacement Exhaustion condition, or `None` when the reduction
            removes Exhaustion completely.
        """
        next_level = self.level - amount
        if next_level < 1:
            return None
        return Exhaustion(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name,
            tags=set(self.tags),
            level=next_level,
        )

    def long_rest(self) -> None:
        """Progress duration and reduce this condition by one owned level."""
        super().long_rest()
        if self.duration.is_expired or not self.target_entity_uuid:
            return
        target = Entity.get(self.target_entity_uuid)
        if (
            isinstance(target, Entity)
            and target.active_conditions_by_uuid.get(self.uuid) is self
        ):
            target.reduce_condition_level(self.name)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply all exhaustion effects up to the current level.

        Args:
            declaration_event: Condition-application declaration event.

        Returns:
            Owned modifier pairs, handler UUIDs, subcondition UUIDs, spatial
            handler UUIDs, and the final effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_uuid = self.target_entity_uuid
        source_uuid = self.source_entity_uuid or target_uuid
        target_entity = Entity.get(target_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {target_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Exhaustion level {self.level} to {target_entity.name}",
            )

            if self.level >= 1:
                for skill in all_skills:
                    skill_obj = target_entity.skill_set.get_skill(skill)
                    modifier_uuid = skill_obj.skill_bonus.self_static.add_advantage_modifier(
                        AdvantageModifier(
                            name="Exhaustion",
                            value=AdvantageStatus.DISADVANTAGE,
                            source_entity_uuid=source_uuid,
                            target_entity_uuid=target_uuid,
                        )
                    )
                    outs.append((skill_obj.skill_bonus.uuid, modifier_uuid))
                effect_event = effect_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Exhaustion ability-check disadvantage to {target_entity.name}",
                )

            if 2 <= self.level < 5:
                for speed in target_entity.action_economy.speed_values:
                    modifier_uuid = speed.self_static.add_factor(ArithmeticFactor(
                        name="Exhaustion", numerator=1, denominator=2,
                        source_entity_uuid=source_uuid, target_entity_uuid=target_uuid))
                    outs.append((speed.uuid, modifier_uuid))

            if self.level >= 3:
                attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Exhaustion",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_uuid,
                        target_entity_uuid=target_uuid,
                    )
                )
                outs.append((target_entity.equipment.attack_bonus.uuid, attack_uuid))
                for ability_name in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
                    saving_throw = target_entity.saving_throws.get_saving_throw(ability_name)
                    save_uuid = saving_throw.bonus.self_static.add_advantage_modifier(
                        AdvantageModifier(
                            name="Exhaustion",
                            value=AdvantageStatus.DISADVANTAGE,
                            source_entity_uuid=source_uuid,
                            target_entity_uuid=target_uuid,
                        )
                    )
                    outs.append((saving_throw.bonus.uuid, save_uuid))
                effect_event = effect_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Exhaustion attack and saving throw disadvantage to {target_entity.name}",
                )

            if self.level >= 4:
                constitution_modifier = target_entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
                current_max_hp = (
                    target_entity.health.get_max_hit_dices_points(constitution_modifier)
                    + target_entity.health.max_hit_points_bonus.normalized_score
                )
                target_max_hp = current_max_hp // 2
                penalty = target_max_hp - current_max_hp
                modifier_uuid = target_entity.health.max_hit_points_bonus.self_static.add_value_modifier(
                    NumericalModifier(
                        name="Exhaustion",
                        value=penalty,
                        source_entity_uuid=source_uuid,
                        target_entity_uuid=target_uuid,
                    )
                )
                outs.append((target_entity.health.max_hit_points_bonus.uuid, modifier_uuid))
                effect_event = effect_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Exhaustion hit point maximum reduction to {target_entity.name}",
                )

            if self.level >= 5:
                for speed in target_entity.action_economy.speed_values:
                    modifier_uuid = speed.self_static.add_max_constraint(
                        NumericalModifier(
                            name="Exhaustion",
                            value=0,
                            source_entity_uuid=source_uuid,
                            target_entity_uuid=target_uuid,
                        )
                    )
                    outs.append((speed.uuid, modifier_uuid))
                effect_event = effect_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Exhaustion zero speed to {target_entity.name}",
                )

            if self.level >= 6:
                target_entity.receive_instant_death(
                    source_entity_uuid=source_uuid,
                    source_description="Exhaustion level 6",
                    parent_event=effect_event.uuid,
                )

            revive_handler = EventHandler(
                name="Exhaustion: Revival Reduction",
                source_entity_uuid=target_uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.REVIVE,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target_uuid,
                    )
                ],
                event_processor=exhaustion_revive_processor,
            )
            target_entity.add_event_handler(revive_handler)

            return outs, [revive_handler.uuid], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {target_uuid} is not an entity but {type(target_entity)}")


@_core_condition_identity(
    content_id="condition.dodging",
    display_name="Dodging",
    description="Applies the defensive benefits of the Dodge action.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Dodge",
    sort_order=70,
)
class Dodging(BaseCondition):
    """Status condition for the Dodge action's defensive effects."""

    name: str = Field(default="Dodging", description="Condition name.")
    description: str = Field(default="A dodging creature has advantage on Dexterity saving throws against being grappled.", description="Condition description.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Status-effect condition category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Dodging self to others advantage modifier to {target_entity.name}")
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_modifier_uuid = dex_save.bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_modifier_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Dodging Dexterity saving throw advantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


@_core_condition_identity(
    content_id="condition.disengaging",
    display_name="Disengaging",
    description="Prevents movement from provoking opportunity attacks this turn.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Disengage",
    sort_order=80,
)
class Disengaging(BaseCondition):
    """Status condition that owns immunity to opportunity-attack provocation."""
    name: str = Field(default="Disengaging", description="Condition name.")
    description: str = Field(default="Your movement doesn't provoke opportunity attacks for the rest of the turn.", description="Condition description.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Status-effect condition category.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )
        outs = apply_opportunity_attack_immunity_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Disengaging to {self.target_entity_uuid}"
        )
        return outs, [], [], [], effect_event


def ground_has_residue(position: Tuple[int, int], residue_id: str) -> bool:
    """Read current material from its existing tile-owned condition."""
    tile = get_map().get_tile(*position)
    return tile is not None and any(
        condition.affects_occupancy_layer(OccupancyLayer.GROUND)
        and (residue := condition.snapshot_tile_residue()) is not None
        and residue.residue_id == residue_id
        for condition in tile.active_conditions.values()
    )


def same_residue_ground(start: Tuple[int, int], end: Tuple[int, int], residue_id: str) -> bool:
    """Query one connected material region without retaining a pool owner."""
    if not ground_has_residue(start, residue_id) or not ground_has_residue(end, residue_id):
        return False
    pending = [start]
    visited = {start}
    while pending:
        current = pending.pop()
        if current == end:
            return True
        for neighbor in ground_neighbors(current) - visited:
            visited.add(neighbor)
            if ground_has_residue(neighbor, residue_id):
                pending.append(neighbor)
    return False


def residue_fear_origin(
    entry: SpatialChangeEvent, *, tile_uuid: UUID, condition_uuid: UUID, residue_id: str,
) -> ResidueFearOrigin:
    """Derive one reverse step from the real entry, including jump or teleport."""
    previous = entry.old_position
    if previous == entry.position:
        previous = None
        parent = entry.get_parent_event()
        while parent is not None:
            if isinstance(parent, StepMovementEvent) and parent.source_entity_uuid == entry.entity_uuid:
                previous = parent.from_position
                break
            if parent.event_type is EventType.MOVEMENT:
                committed = [child for child in parent.get_children_events()
                    if isinstance(child, StepMovementEvent) and child.committed
                    and child.source_entity_uuid == entry.entity_uuid
                    and child.to_position == entry.position]
                if committed:
                    previous = max(committed, key=lambda step: step.path_index).from_position
                    break
            parent = parent.get_parent_event()
    reverse_path = bresenham_line(entry.position, previous) if previous is not None else []
    retreat_position = reverse_path[1] if len(reverse_path) > 1 else None
    return ResidueFearOrigin(
        tile_uuid=tile_uuid, condition_uuid=condition_uuid, residue_id=residue_id, position=entry.position,
        retreat_position=retreat_position, entry_event_uuid=entry.uuid,
    )


def apply_frightened_disadvantage(
    target: Entity, source_uuid: UUID, disadvantage: ContextAwareAdvantage,
) -> List[Tuple[UUID, UUID]]:
    """Install fear penalties returned to the exact condition's normal ownership list."""
    values = [target.equipment.attack_bonus]
    values.extend(target.skill_set.get_skill(skill).skill_bonus for skill in all_skills)
    values.extend(ability.check_bonus for ability in (
        target.ability_scores.strength, target.ability_scores.dexterity, target.ability_scores.constitution,
        target.ability_scores.intelligence, target.ability_scores.wisdom, target.ability_scores.charisma))
    return [(value.uuid, value.self_contextual.add_advantage_modifier(ContextualAdvantageModifier(
        name="Frightened", source_entity_uuid=target.uuid, target_entity_uuid=source_uuid,
        callable=disadvantage))) for value in values]


@_core_condition_identity(
    content_id="condition.frightened",
    display_name="Frightened",
    description="Suffers fear penalties while the source of fear is visible.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Frightened",
    sort_order=90,
)
class Frightened(BaseCondition):
    """Contextual fear condition keyed to whether the source is sensed."""

    name: str = Field(default="Frightened", description="Condition name.")
    residue_origin: Optional[ResidueFearOrigin] = None
    allow_retreat: bool = False
    source_rules_owned_by_parent: bool = False
    _source_parent_uuid: UUID | None = PrivateAttr(default=None)
    _inherited_shared_parents: tuple[UUID, ...] = PrivateAttr(default=())
    _retiring_shared_parents: tuple[UUID, ...] = PrivateAttr(default=())
    description: str = Field(
        default="A frightened creature has disadvantage on attack rolls and ability checks and cannot move while the frightener is in sight.",
        description="Condition description.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            self._source_parent_uuid = self.parent_condition
            existing = target_entity.active_conditions.get("Frightened")
            if isinstance(existing, Frightened):
                parents = set(existing.additional_parent_conditions)
                if (existing.parent_condition is not None and (existing.source_rules_owned_by_parent
                        or existing.parent_condition != existing._source_parent_uuid)):
                    parents.add(existing.parent_condition)
                self._inherited_shared_parents = tuple(parents)
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self},
                status_message=f"Applied Frightened to {target_entity.name}")
            if self.source_rules_owned_by_parent:
                return [], [], [], [], effect_event
            outs = apply_frightened_disadvantage(target_entity, self.source_entity_uuid,
                self.get_frightener_in_senses_disadvantage())
            if self.residue_origin is None and self.allow_retreat:
                direction = EventHandler(
                    name="Frightened Retreat Direction", source_entity_uuid=target_entity.uuid,
                    trigger_conditions=[Trigger(event_type=EventType.STEP_MOVEMENT,
                        event_phase=EventPhase.EFFECT, event_source_entity_uuid=target_entity.uuid)],
                    event_processor=self._on_retreat_step,
                )
                target_entity.add_event_handler(direction)
                return outs, [direction.uuid], [], [], effect_event
            if self.residue_origin is None:
                for speed in target_entity.action_economy.speed_values:
                    max_movement_constraint_uuid = speed.self_contextual.add_max_constraint(constraint=ContextualNumericalModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frigthener_in_senses_zero_max_speed()))
                    outs.append((speed.uuid,max_movement_constraint_uuid))
                effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Frightened movement constraint to {target_entity.name}")
                return outs, [], [], [], effect_event
            direction = EventHandler(
                name="Residue Fear Retreat Direction", source_entity_uuid=target_entity.uuid,
                trigger_conditions=[Trigger(event_type=EventType.STEP_MOVEMENT,
                    event_phase=EventPhase.EFFECT, event_source_entity_uuid=target_entity.uuid)],
                event_processor=self._on_residue_step,
            )
            target_entity.add_event_handler(direction)
            exit_handler = EventHandler(
                name="Residue Fear Exit", source_entity_uuid=target_entity.uuid,
                trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_LEFT,
                    event_phase=EventPhase.EFFECT, event_source_entity_uuid=target_entity.uuid)],
                event_processor=self._on_residue_exit,
            )
            target_entity.add_event_handler(exit_handler)
            material_removed = EventHandler(
                name="Residue Fear Material Removed", source_entity_uuid=target_entity.uuid,
                trigger_conditions=[Trigger(event_type=EventType.SPATIAL_TILE_CHANGED,
                    event_phase=EventPhase.EFFECT)],
                event_processor=self._on_residue_removed,
            )
            target_entity.add_event_handler(material_removed)
            return outs, [direction.uuid, exit_handler.uuid, material_removed.uuid], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    def _own_source_active(self) -> bool:
        if self.source_rules_owned_by_parent or self.duration.is_expired:
            return False
        parent = BaseCondition.get(self._source_parent_uuid) if self._source_parent_uuid else None
        return self._source_parent_uuid is None or isinstance(parent, BaseCondition) and parent.applied

    def has_surviving_parent(self, removing: Set[UUID]) -> bool:
        if self.parent_condition is None and not self._own_source_active():
            return bool(self.additional_parent_conditions - removing)
        return super().has_surviving_parent(removing)

    def progress_for_interval(self, interval: Optional[Tuple[UUID, int]]) -> bool:
        expired = super().progress_for_interval(interval)
        # The independent fear expires; borrowed membership still belongs to
        # its live source parents. Its own contextual contributions now gate off.
        return expired and not self.additional_parent_conditions

    def _end_own_source(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return
        if self.additional_parent_conditions:
            self.duration.duration_type = DurationType.ROUNDS
            self.duration.duration = 0
        else:
            target.remove_condition_by_uuid(self.uuid, parent_event=event)

    def _commit_application(self, effect_event: Event) -> None:
        # A later ordinary fear keeps the live shared parents when replacing
        # their membership-only child. The replacement remains atomic.
        for parent_uuid in self._inherited_shared_parents:
            parent = BaseCondition.get(parent_uuid)
            if isinstance(parent, BaseCondition) and parent.applied:
                parent.add_shared_subcondition(self)
        self._inherited_shared_parents = ()

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        parents = set(self.additional_parent_conditions)
        if (self.parent_condition is not None and (self.source_rules_owned_by_parent
                or self.parent_condition != self._source_parent_uuid)):
            parents.add(self.parent_condition)
        cause = event.get_parent_event() if event is not None else None
        if isinstance(cause, ConditionApplicationEvent) and isinstance(cause.condition, Frightened):
            parents.difference_update(cause.condition._inherited_shared_parents)
        self._retiring_shared_parents = tuple(parents)
        return event

    def on_membership_changed(self, event: Event) -> None:
        if self.applied:
            return
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            for parent_uuid in self._retiring_shared_parents:
                target.remove_condition_by_uuid(parent_uuid, parent_event=event)
        self._retiring_shared_parents = ()

    @staticmethod
    def frightener_in_senses_disadvantage(frightener_uuid: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """Return disadvantage while the frightened entity senses the source.

        Args:
            frightener_uuid: UUID of the source of fear.
            source_entity_uuid: UUID of the frightened entity.
            target_entity_uuid: Optional target UUID for the active roll.
            context: Optional contextual data from modifier evaluation.

        Returns:
            Disadvantage modifier if the source is sensed, otherwise None.
        """
        source_entity = Entity.get(source_entity_uuid)
        contact = source_entity.senses.entities.get(frightener_uuid) if isinstance(source_entity, Entity) else None
        if contact is not None and contact.visual:
            return AdvantageModifier(name="Frightened",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_frightener_in_senses_disadvantage(self) -> ContextAwareAdvantage:
        """Return the contextual disadvantage callable for this fear source."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualAdvantageModifier")
        return self._source_disadvantage

    def _source_disadvantage(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None,
                            context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        if not self._own_source_active():
            return None
        if self.residue_origin is not None:
            return self.residue_in_senses_disadvantage(self.residue_origin, source_entity_uuid, target_entity_uuid, context)
        return self.frightener_in_senses_disadvantage(self.source_entity_uuid, source_entity_uuid, target_entity_uuid, context)

    @staticmethod
    def residue_in_senses_disadvantage(
        origin: ResidueFearOrigin, source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None,
    ) -> Optional[AdvantageModifier]:
        """Use current material contact and visual access, never its donor."""
        target = Entity.get(source_entity_uuid)
        if (target is not None and target.get_occupancy_layer() is OccupancyLayer.GROUND
                and ground_has_residue(target.position, origin.residue_id)
                and target.senses.visible.get(target.position, False)):
            return AdvantageModifier(name="Frightened", value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
        return None

    def get_paid_entry_retreat(self, *, since_cursor: int) -> Optional[PaidEntryRetreat]:
        """Request the initial response once, at the movement's completed entry boundary."""
        if (not self._own_source_active() or self.residue_origin is None or self.applied_source_event_cursor is None
                or self.applied_source_event_cursor <= since_cursor):
            return None
        return PaidEntryRetreat(destination=self.residue_origin.retreat_position)

    def _on_retreat_step(self, event: Event, source_uuid: UUID) -> Event:
        if self.target_entity_uuid is None or not self._own_source_active():
            return event
        return self.retreat_step_for_source(self.source_entity_uuid, self.target_entity_uuid, event, source_uuid)

    @staticmethod
    def retreat_step_for_source(frightener_uuid: UUID, target_uuid: UUID, event: Event, _source_uuid: UUID) -> Event:
        """Constrain a paid step against the explicit owner's visible frightener."""
        if not isinstance(event, StepMovementEvent):
            return event
        target, source = Entity.get(target_uuid), Entity.get(frightener_uuid)
        if target is None or source is None:
            return event
        contact = target.senses.entities.get(source.uuid)
        if contact is None or not contact.visual:
            return event
        grid = get_map()
        before = support_distance_feet(source.position, grid.get_support_elevation_feet(source.position),
            event.from_position, grid.get_support_elevation_feet(event.from_position))
        after = support_distance_feet(source.position, grid.get_support_elevation_feet(source.position),
            event.to_position, grid.get_support_elevation_feet(event.to_position))
        return event.cancel(status_message="Frightened: cannot approach the source") if after < before else event

    def _on_residue_step(self, event: Event, _source_uuid: UUID) -> Event:
        """Retain the original outward heading across internal pool cells."""
        origin = self.residue_origin
        if self._own_source_active() and origin is not None and isinstance(event, StepMovementEvent) and origin.retreat_position is not None:
            destination = (event.from_position[0] + origin.retreat_position[0] - origin.position[0],
                           event.from_position[1] + origin.retreat_position[1] - origin.position[1])
            if event.to_position != destination:
                return event.cancel(status_message="Frightened: retreat toward the entry cell")
        return event

    def _on_residue_exit(self, event: Event, _source_uuid: UUID) -> Event:
        """Internal material movement retains fear; an actual exit releases it."""
        origin = self.residue_origin
        if (self._own_source_active() and origin is not None and self.target_entity_uuid is not None
                and isinstance(event, SpatialChangeEvent)
                and event.entity_uuid == self.target_entity_uuid):
            destination = event.old_position  # LEFT stores its arrival here.
            if (destination is not None and event.occupancy_layer is OccupancyLayer.GROUND
                    and same_residue_ground(event.position, destination, origin.residue_id)):
                return event
            self._end_own_source(event)
        return event

    def _on_residue_removed(self, event: Event, _source_uuid: UUID) -> Event:
        """Removing the currently contacted material releases only this fear."""
        origin = self.residue_origin
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if origin is None or target is None or not self._own_source_active():
            return event
        if (isinstance(event, SpatialChangeEvent) and event.position == target.position
                and not ground_has_residue(target.position, origin.residue_id)):
            self._end_own_source(event)
        return event

    @staticmethod
    def frigthener_in_senses_zero_max_speed(frightener_uuid: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[NumericalModifier]:
        """Return a zero-movement cap while the frightened entity senses the source.

        Args:
            frightener_uuid: UUID of the source of fear.
            source_entity_uuid: UUID of the frightened entity.
            target_entity_uuid: Optional target UUID for the active roll.
            context: Optional contextual data from modifier evaluation.

        Returns:
            Zero max-speed modifier if the source is sensed, otherwise None.
        """
        source_entity = Entity.get(source_entity_uuid)
        contact = source_entity.senses.entities.get(frightener_uuid) if isinstance(source_entity, Entity) else None
        if contact is not None and contact.visual:
            return NumericalModifier(name="Frightened",value=0,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_frigthener_in_senses_zero_max_speed(self) -> ContextAwareNumerical:
        """Return the contextual zero-movement callable for this fear source."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualNumericalModifier")
        return self._source_zero_speed

    def _source_zero_speed(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None,
                           context: Optional[Dict[str, Any]] = None) -> Optional[NumericalModifier]:
        if not self._own_source_active():
            return None
        return self.frigthener_in_senses_zero_max_speed(self.source_entity_uuid,
            source_entity_uuid, target_entity_uuid, context)


@_core_condition_identity(
    content_id="condition.grappled",
    display_name="Grappled",
    description="Has speed reduced to zero by a grappling effect.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Grappled",
    sort_order=100,
)
class Grappled(BaseCondition):
    """Movement-lock condition that caps speed at zero."""

    name: str = Field(default="Grappled", description="Condition name.")
    description: str = Field(default="A grappled creature can't move through the space of the grappler.", description="Condition description.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            for speed in target_entity.action_economy.speed_values:
                grappled_modifer_uuid = speed.self_static.add_max_constraint(constraint=NumericalModifier(name="Grappled",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((speed.uuid,grappled_modifer_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Grappled max speed constraint to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

@_core_condition_identity(
    content_id="condition.incapacitated",
    display_name="Incapacitated",
    description="Cannot take actions or reactions.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Incapacitated",
    sort_order=110,
)
class Incapacitated(BaseCondition):
    """Action-economy lock condition used by severe status effects."""

    name: str = Field(default="Incapacitated", description="Condition name.")
    description: str = Field(default="An incapacitated creature can't take actions.", description="Condition description.")
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Incapacitation removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = apply_incapacitated_transform(
                target_entity,
                name=self.name,
                effect_source_uuid=self.source_entity_uuid,
            )
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Incapacitated transform to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

@_core_condition_identity(
    content_id="condition.invisible",
    display_name="Invisible",
    description="Cannot be seen without a sense or rule that bypasses invisibility.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Invisible",
    sort_order=120,
)
class Invisible(BaseCondition):
    """Invisibility condition with unseen-attacker and unseen-target modifiers."""

    name: str = Field(default="Invisible", description="Condition name.")
    description: str = Field(default="An invisible creature is impossible to see without the aid of magic or a special sense.", description="Condition description.")
    grants_invisibility: bool = True
    obscures_perceivability: bool = Field(default=True, description="Removing invisibility may reveal the target.")

    _invisibility_changed: bool = PrivateAttr(default=False)

    def _commit_application(self, effect_event: Event) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            self._invisibility_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied and target is not None:
            self._invisibility_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._invisibility_changed = self._invisibility_changed, False
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)

    def format_application_log(self, target_name: str) -> str:
        """Render the invisibility-specific application message."""
        return f"{{cyan:{target_name}}} becomes **invisible**"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            self_contextual_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=unseen_attacker_advantage))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_contextual_uuid))
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=unseen_target_disadvantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            try:
                effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Invisible to target disadvantage modifier to {target_entity.name}")
            except BaseException:
                remove_modifier_ownership(outs)
                raise
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

def unseen_attacker_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
    """Return advantage when an attacker is absent from the defender's senses.

    Args:
        source_entity_uuid: UUID of the unseen attacker.
        target_entity_uuid: UUID of the defender, if known.
        context: Optional contextual data from modifier evaluation.

    Returns:
        Advantage modifier if the attacker is unseen, otherwise None.
    """
    if target_entity_uuid:
        target_entity = Entity.get(target_entity_uuid)
        contact = target_entity.senses.entities.get(source_entity_uuid) if isinstance(target_entity, Entity) else None
        if isinstance(target_entity, Entity) and (contact is None or not contact.visual):
            return AdvantageModifier(name="Unseen Attacker", value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


def unseen_target_disadvantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
    """Return disadvantage when a defender is absent from the attacker's senses.

    Args:
        source_entity_uuid: UUID of the unseen defender.
        target_entity_uuid: UUID of the attacker, if known.
        context: Optional contextual data from modifier evaluation.

    Returns:
        Disadvantage modifier if the defender is unseen, otherwise None.
    """
    if target_entity_uuid:
        attacker = Entity.get(target_entity_uuid)
        contact = attacker.senses.entities.get(source_entity_uuid) if isinstance(attacker, Entity) else None
        if isinstance(attacker, Entity) and (contact is None or not contact.visual):
            return AdvantageModifier(name="Unseen Target", value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


@_core_condition_identity(
    content_id="condition.paralyzed",
    display_name="Paralyzed",
    description="Is incapacitated, immobile, and vulnerable to nearby attacks.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Paralyzed",
    sort_order=130,
)
class Paralyzed(BaseCondition):
    """Severe condition owning incapacitation, failed saves, and auto-crits."""

    name: str = Field(default="Paralyzed", description="Condition name.")
    description: str = Field(
        default="A paralyzed creature is incapacitated (see the condition) and can't move or speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage. Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature.",
        description="Condition description.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Paralysis removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            execution_event = declaration_event
            outs = apply_paralyzed_transform(
                target_entity,
                name=self.name,
                effect_source_uuid=self.source_entity_uuid,
            )
            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Paralyzed transform to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


@_core_condition_identity(
    content_id="condition.petrified",
    display_name="Petrified",
    description="Is transformed into an inert solid substance.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Petrified",
    sort_order=140,
)
class Petrified(BaseCondition):
    """Stone-form condition with severe-control and all-damage resistance effects."""

    name: str = Field(default="Petrified", description="Condition name.")
    description: str = Field(
        default="A petrified creature is incapacitated, can't move or speak, is unaware of its surroundings, automatically fails Strength and Dexterity saving throws, grants attacker advantage, has resistance to all damage, and is immune to poison and disease.",
        description="Condition description.",
    )
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.PETRIFICATION},
        description="Condition tags used by Greater Restoration and petrification-aware effects.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Petrification removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the directly owned severe-control and resistance transforms.

        Args:
            declaration_event: Condition-application declaration event.

        Returns:
            Owned modifier pairs, handler UUIDs, subcondition UUIDs, spatial
            handler UUIDs, and the final effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_uuid = self.target_entity_uuid
        source_uuid = self.source_entity_uuid or target_uuid
        target_entity = Entity.get(target_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {target_uuid} not found")
        elif isinstance(target_entity, Entity):
            execution_event = declaration_event
            outs = apply_stunned_transform(
                target_entity,
                name=self.name,
                effect_source_uuid=source_uuid,
            )

            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Petrified severe-control transform to {target_entity.name}",
            )

            for damage_type in DamageType:
                resistance_modifier = ResistanceModifier(
                    name=f"Petrified resistance to {damage_type.value}",
                    value=ResistanceStatus.RESISTANCE,
                    damage_type=damage_type,
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target_uuid,
                )
                resistance_uuid = target_entity.health.damage_reduction.self_static.add_resistance_modifier(resistance_modifier)
                outs.append((target_entity.health.damage_reduction.uuid, resistance_uuid))
            target_entity.add_condition_immunity_source("Poisoned", self.uuid)
            effect_event = effect_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Petrified all-damage resistance and poison immunity to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {target_uuid} is not an entity but {type(target_entity)}")

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove petrification-owned condition immunity.

        Args:
            event: Removal event created by condition cleanup.

        Returns:
            Removal event after standard phase progression.
        """
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.remove_condition_immunity_source("Poisoned", self.uuid)
        return super()._remove(event)


@_core_condition_identity(
    content_id="condition.poisoned",
    display_name="Poisoned",
    description="Has disadvantage on attack rolls and ability checks.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Poisoned",
    sort_order=150,
)
class Poisoned(BaseCondition):
    """Poison condition that penalizes attacks and ability checks."""

    name: str = Field(default="Poisoned", description="Condition name.")
    description: str = Field(default="A poisoned creature has disadvantage on all ability checks and attack rolls.", description="Condition description.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Poisoned self to others advantage modifier to {target_entity.name}")
            for skill in all_skills:
                skill_obj = target_entity.skill_set.get_skill(skill)
                skill_static_modifier_uuid = skill_obj.skill_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,skill_static_modifier_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Poisoned to all skills disadvantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

@_core_condition_identity(
    content_id="condition.prone",
    display_name="Prone",
    description="Is lying down and subject to the standard prone combat effects.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Prone",
    sort_order=160,
)
class Prone(BaseCondition):
    """Prone condition with distance-sensitive incoming attack modifiers.

    The engine also implements an immediate stand-up branch if the target is
    knocked prone during its own turn and has enough movement.
    """
    name: str = Field(default="Prone", description="Condition name.")
    description: str = Field(default="A prone creature has disadvantage on all attack rolls. Attack rolls against the creature have advantage if within 5ft, disadvantage otherwise. Automatically stands at turn start (costs half movement).", description="Condition description.")
    _suppress_immediate_stand: bool = PrivateAttr(default=False)

    def suppress_immediate_stand_for_application(self) -> None:
        """Keep this application prone through the current turn.

        Ordinary Prone applications during the target's turn still use the
        immediate stand branch. Rules that explicitly require the creature to
        remain prone for that turn may opt out before adding the condition.
        """
        self._suppress_immediate_stand = True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            if (
                target_entity.is_my_turn
                and not self._suppress_immediate_stand
            ):
                base_movement = target_entity.action_economy.get_base_value("movement")
                half_movement = base_movement // 2
                current_movement = target_entity.action_economy.movement_remaining()
                if current_movement >= half_movement:
                    target_entity.action_economy.consume("movement", half_movement)
                    return [], [], [], [], declaration_event.cancel(
                        status_message=f"{target_entity.name} fell prone but immediately stood up"
                    )

            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(name="Prone", value=AdvantageStatus.DISADVANTAGE,
                                  source_entity_uuid=self.target_entity_uuid, target_entity_uuid=self.source_entity_uuid)
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_static_attack_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self},
                                                       status_message=f"Applied Prone to {target_entity.name}")

            outs.extend(
                apply_prone_geometry_transform(
                    target_entity,
                    name=self.name,
                    effect_source_uuid=self.source_entity_uuid,
                )
            )
            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

@_core_condition_identity(
    content_id="condition.stunned",
    display_name="Stunned",
    description="Is incapacitated, immobile, and easier to attack.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Stunned",
    sort_order=170,
)
class Stunned(BaseCondition):
    """Severe condition owning incapacitation, save failures, and vulnerability."""

    name: str = Field(default="Stunned", description="Condition name.")
    description: str = Field(
        default="A stunned creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage.",
        description="Condition description.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Stunning removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            execution_event = declaration_event
            outs = apply_stunned_transform(
                target_entity,
                name=self.name,
                effect_source_uuid=self.source_entity_uuid,
            )
            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Stunned transform to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

@_core_condition_identity(
    content_id="condition.restrained",
    display_name="Restrained",
    description="Has no movement and suffers the standard restrained penalties.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Restrained",
    sort_order=180,
)
class Restrained(BaseCondition):
    """Movement-lock condition with attack and Dexterity-save penalties."""

    name: str = Field(default="Restrained", description="Condition name.")
    description: str = Field(default="A restrained creature can't move and has disadvantage on Dexterity saving throws. Attack rolls against the creature have advantage.", description="Condition description.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            for speed in target_entity.action_economy.speed_values:
                speed_max_constrain_uuid = speed.self_static.add_max_constraint(constraint=NumericalModifier(name="Restrained",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((speed.uuid,speed_max_constrain_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained max speed constraint to {target_entity.name}")
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained to self disadvantage modifier to {target_entity.name}")
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_disadvantage_uuid = dex_save.bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_disadvantage_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained disadvantage to dex saves for {target_entity.name}")
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained to target contextual advantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


@_core_condition_identity(
    content_id="condition.unconscious",
    display_name="Unconscious",
    description="Is unaware, incapacitated, immobile, and vulnerable to attacks.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Appendix PH-A: Conditions — Unconscious",
    sort_order=190,
)
class Unconscious(BaseCondition):
    """Severe condition owning the complete unconscious mechanical transform."""

    name: str = Field(default="Unconscious", description="Condition name.")
    description: str = Field(
        default="An unconscious creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage.",
        description="Condition description.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Unconsciousness removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            execution_event = declaration_event
            outs = apply_unconscious_transform(
                target_entity,
                name=self.name,
                effect_source_uuid=self.source_entity_uuid,
            )
            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Unconscious transform to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class ConcentrationSlot(BaseObject):
    """A single concentration slot tracking one spell's linked conditions.

    Inherits from BaseObject for UUID registry integration.
    source_entity_uuid = caster UUID.
    """
    name: Optional[str] = "Concentration Slot"
    spell_name: str = ""
    spell_id: Optional[str] = None
    cast_lineage_uuid: UUID | None = None
    linked_entries: List[Tuple[UUID, UUID]] = Field(default_factory=list)


@dataclass
class PreparedConcentrationTransfer:
    previous: "Concentrating | None"
    removals: list[tuple[BaseBlock | None, BaseCondition, Event, bool]]
    retained_slots: dict[UUID, ConcentrationSlot]
    retained_links: list[tuple[UUID, UUID]]
    committed_removals: CommittedConditionRemovals | None = None


@_core_condition_identity(
    content_id="condition.concentrating",
    display_name="Concentrating",
    description="Maintains one or more concentration-dependent spell effects.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Spellcasting: Concentration",
    sort_order=200,
)
class Concentrating(BaseCondition):
    """
    Tracks concentration on a spell.

    When a caster concentrates on a spell:
    - Only one concentration spell can be active at a time (configurable via max_concentration_slots)
    - Taking damage requires a CON save (DC = max(10, damage/2))
    - Failing the save or casting another concentration spell ends this effect
    - When concentration ends, the spell effect is also removed via linked_conditions

    All spells should use SpellAction.ensure_concentration() which:
    1. Creates or reuses this condition on the caster
    2. Returns it for linking via add_linked_condition()

    Multi-slot support: When max_concentration_slots > 1, multiple different spells
    can coexist via concentration_slots dict. Each slot tracks one spell's linked conditions.
    """
    name: str = "Concentrating"
    description: str = "Concentrating on a spell"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    child_removal_policy: Literal["none", "any", "last"] = "last"
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.CONCENTRATION},
        description="Typed concentration classification used by subjective projection.",
    )

    spell_name: str = ""
    spell_id: Optional[str] = None

    concentration_slots: Dict[UUID, ConcentrationSlot] = Field(default_factory=dict)

    _active_slot_uuid: Optional[UUID] = PrivateAttr(default=None)
    _prepared_transfer: PreparedConcentrationTransfer | None = PrivateAttr(default=None)

    def prepares_own_replacement(self) -> bool:
        return True

    def sustained_links_for_slot(self, slot_uuid: UUID | None) -> tuple[tuple[UUID, UUID], ...]:
        if slot_uuid is None:
            return tuple(self.linked_conditions)
        slot = self.concentration_slots.get(slot_uuid)
        return tuple(slot.linked_entries) if slot is not None else ()

    def release_sustain_slot(self, slot_uuid: UUID | None, *, parent_event: Event) -> bool:
        if slot_uuid is not None:
            return self.drop_slot(slot_uuid, parent_event=parent_event)
        owner = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        return owner.remove_condition_by_uuid(self.uuid, parent_event=parent_event) if owner else False

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        if self.spell_name and not self.concentration_slots:
            self._active_slot_uuid = self.add_slot(self.spell_name, spell_id=self.spell_id)

    def _sync_spell_name(self) -> None:
        """Keep spell_name field in sync with slots (slots are source of truth)."""
        self.spell_name = ", ".join(slot.spell_name for slot in self.concentration_slots.values()) or ""

    def get_slot_by_spell_name(self, spell_name: str) -> Optional[UUID]:
        """Find a slot UUID by spell name. Returns None if not found."""
        for slot_uuid, slot in self.concentration_slots.items():
            if slot.spell_name == spell_name:
                return slot_uuid
        return None

    def add_slot(self, spell_name: str, *, spell_id: Optional[str] = None) -> UUID:
        """Add a new concentration slot for a spell. Returns the slot UUID."""

        existing = self.get_slot_by_spell_name(spell_name)
        if existing is not None:
            self._active_slot_uuid = existing
            self._sync_spell_name()
            return existing
        source_uuid = self.source_entity_uuid if self.source_entity_uuid else self.target_entity_uuid
        assert source_uuid is not None
        slot = ConcentrationSlot(
            source_entity_uuid=source_uuid,
            spell_name=spell_name,
            spell_id=spell_id,
        )
        self.concentration_slots[slot.uuid] = slot
        self._active_slot_uuid = slot.uuid
        self._sync_spell_name()
        return slot.uuid

    def drop_slot(
        self,
        slot_uuid: UUID,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Remove a single spell slot and its linked conditions.

        If this is the last slot, removes the entire Concentrating condition.
        Otherwise, removes just this slot's conditions and updates state.
        """
        with BaseBlock.condition_removal_scope():
            return self._drop_slot(slot_uuid, parent_event=parent_event)

    def _drop_slot(self, slot_uuid: UUID, *, parent_event: Event | None) -> bool:
        if slot_uuid not in self.concentration_slots:
            return False

        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return False

        if len(self.concentration_slots) <= 1:
            return target.remove_condition(
                "Concentrating",
                parent_event=parent_event,
            )

        slot = self.concentration_slots[slot_uuid]
        prepared: List[
            Tuple[Optional[BaseBlock], BaseCondition, Event, bool]
        ] = []
        visited: Set[UUID] = {self.uuid}
        try:
            for block_uuid, condition_uuid in tuple(slot.linked_entries):
                child = BaseCondition.get(condition_uuid)
                if not isinstance(child, BaseCondition) or not child.applied:
                    continue
                block = BaseBlock.get(block_uuid)
                owner: Optional[BaseBlock]
                if (
                    isinstance(block, BaseBlock)
                    and block.active_conditions_by_uuid.get(condition_uuid) is child
                ):
                    owner = block
                elif child.is_active_spatial_condition():
                    owner = None
                else:
                    continue
                canceled = BaseBlock._prepare_condition_removal_tree(
                    child,
                    condition_owner=owner,
                    expire=False,
                    parent_event=parent_event,
                    prepared=prepared,
                    visited=visited,
                )
                if canceled is not None:
                    BaseBlock._cancel_prepared_condition_removals(
                        prepared,
                        canceled,
                    )
                    return False
        except BaseException:
            BaseBlock.cancel_owned_condition_removals(PreparedConditionRemovals(prepared), "Concentration slot removal admission raised")
            raise

        BaseBlock._commit_prepared_condition_removals(prepared)
        for pair in list(slot.linked_entries):
            if pair in self.linked_conditions:
                self.linked_conditions.remove(pair)

        if self.concentration_slots.pop(slot_uuid, None) is not None:
            slot.remove_from_register()
        self._sync_spell_name()
        self.publish_owner_state(parent_event)
        return True

    def cleanup_if_no_effects(self, parent_event: Optional[Event] = None) -> None:
        """Remove Concentrating if it has no linked children (0-children bug fix)."""
        if not self.linked_conditions:
            target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
            if target and "Concentrating" in target.active_conditions:
                target.remove_condition("Concentrating", parent_event=parent_event)

    def add_linked_condition(self, target_block_uuid: UUID, condition_uuid: UUID) -> None:
        """Override to also route into the active slot."""
        if (target_block_uuid, condition_uuid) in self.linked_conditions:
            return
        super().add_linked_condition(target_block_uuid, condition_uuid)

        if self._active_slot_uuid and self._active_slot_uuid in self.concentration_slots:
            self.concentration_slots[self._active_slot_uuid].linked_entries.append((target_block_uuid, condition_uuid))

    def record_cast_owner(self, lineage_uuid: UUID) -> None:
        if self._active_slot_uuid is not None:
            self.concentration_slots[self._active_slot_uuid].cast_lineage_uuid = lineage_uuid

    def snapshot_concentration_slots(self) -> tuple[ItemConcentrationSlot, ...]:
        return tuple(ItemConcentrationSlot(slot_uuid=slot.uuid, spell_id=slot.spell_id,
            spell_name=slot.spell_name, cast_lineage_uuid=slot.cast_lineage_uuid) for slot in self.concentration_slots.values() if slot.linked_entries)

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={
            "concentration_slots": self.snapshot_concentration_slots(),
        })

    def publish_owner_state(self, parent_event: Event | None) -> None:
        """Publish only a changed committed snapshot, using the existing event history."""
        owner = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if owner is None or owner.active_conditions_by_uuid.get(self.uuid) is not self:
            return
        recorded = EventQueue.get_events_by_target(owner.uuid)
        if isinstance(owner, BaseItem) and owner.tile_uuid is not None:
            previous = next((event for event in reversed(recorded)
                if isinstance(event, ItemLocationStateEvent) and event.phase is EventPhase.COMPLETION), None)
            if previous is None or previous.item_state != owner.to_item_presentation_state():
                owner.publish_location_state(ItemLocation.FLOOR, parent_event=parent_event)
        elif isinstance(owner, Entity):
            state, stats = self.snapshot_state(), owner.snapshot_entity_stats()
            previous = next((event for event in reversed(recorded)
                if isinstance(event, (ConditionApplicationEvent, ConditionStateChangedEvent))
                and event.phase is EventPhase.COMPLETION and event.condition_state is not None
                and event.condition_state.condition_uuid == self.uuid), None)
            if previous is not None and previous.condition_state == state and previous.resulting_stats == stats:
                return
            ConditionStateChangedEvent(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=owner.uuid,
                parent_event=parent_event.uuid if parent_event is not None else None,
                parent_lineage=parent_event.lineage_uuid if parent_event is not None else None,
                phase=EventPhase.COMPLETION,
                condition_state=state,
                resulting_stats=stats,
                behavior_id=self.behavior_binding.behavior_id if self.behavior_binding is not None else None,
            )

    def unlink_condition(self, condition_uuid: UUID, *, parent_event: Event) -> None:
        super().unlink_condition(condition_uuid, parent_event=parent_event)
        for slot_uuid, slot in tuple(self.concentration_slots.items()):
            if not any(link[1] == condition_uuid for link in slot.linked_entries):
                continue
            slot.linked_entries = [link for link in slot.linked_entries if link[1] != condition_uuid]
            if not slot.linked_entries:
                slot.remove_from_register()
                del self.concentration_slots[slot_uuid]
        self._sync_spell_name()

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = BaseBlock.get(self.target_entity_uuid)
        if not isinstance(target, (Entity, BaseItem)):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        existing = target.active_conditions.get("Concentrating")
        prepared: List[Tuple[Optional[BaseBlock], BaseCondition, Event, bool]] = []
        retained_slots: Dict[UUID, ConcentrationSlot] = {}
        retained_links: List[Tuple[UUID, UUID]] = []
        if isinstance(existing, Concentrating):
            max_slots = (target.max_concentration_slots.normalized_score
                         if isinstance(target, Entity) else target.concentration_capacity)
            if isinstance(target, BaseItem) and len(existing.concentration_slots) >= max_slots:
                return [], [], [], [], declaration_event.cancel(status_message="Device concentration capacity is full")
            evicted_count = max(0, len(existing.concentration_slots) - max_slots + 1)
            evicted_slots = set(list(existing.concentration_slots)[:evicted_count])
            retained_slots = {key: value for key, value in existing.concentration_slots.items()
                              if key not in evicted_slots}
            removed_links = list(dict.fromkeys(
                link for key, slot in existing.concentration_slots.items()
                if key in evicted_slots for link in slot.linked_entries))
            retained_links = [link for link in existing.linked_conditions if link not in removed_links]

            self._prepared_transfer = PreparedConcentrationTransfer(
                existing, prepared, retained_slots, retained_links,
            )
            # Ownership transfer releases the old root but preserves retained children.
            accepted = BaseBlock._accepted_condition_removals.get()
            entry = accepted.get(existing.uuid) if accepted is not None else None
            if entry is None:
                removal = EventQueue.publish_declaration(
                    existing._declare_removal_event(parent_event=declaration_event))
                if removal.canceled:
                    return [], [], [], [], declaration_event.cancel(
                        status_message="Existing concentration could not be replaced")
                try:
                    removal_effect = existing.publish_removal_effect(removal)
                except BaseException:
                    existing.cancel_prepared_removal("Concentration replacement admission raised")
                    raise
                if removal_effect.canceled:
                    return [], [], [], [], declaration_event.cancel(
                        status_message="Existing concentration could not be replaced")
                entry = (target, existing, removal_effect, False)
                if accepted is not None:
                    accepted[existing.uuid] = entry
            prepared.append(entry)
            visited: Set[UUID] = {existing.uuid}
            for block_uuid, condition_uuid in removed_links:
                child = BaseCondition.get(condition_uuid)
                owner = BaseBlock.get(block_uuid)
                if not isinstance(child, BaseCondition) or not child.applied:
                    continue
                child_owner = owner if isinstance(owner, BaseBlock) else None
                canceled = BaseBlock._prepare_condition_removal_tree(
                    child, condition_owner=child_owner, expire=False,
                    parent_event=entry[2], prepared=prepared, visited=visited,
                )
                if canceled is not None:
                    return [], [], [], [], declaration_event.cancel(
                        status_message="Existing concentration could not be released")

        self._prepared_transfer = PreparedConcentrationTransfer(
            existing if isinstance(existing, Concentrating) else None,
            prepared, retained_slots, retained_links,
        )
        if not self.validate_prepared_removal():
            return [], [], [], [], declaration_event.cancel(
                status_message="Condition removal destinations conflict or changed")
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT, update={"condition": self},
            status_message=f"{target.name} is concentrating on {self.spell_name}",
        )
        return [], [], [], [], effect_event

    def prepared_removal_occupancies(self) -> tuple[tuple[int, int], ...]:
        transfer = self._prepared_transfer
        if transfer is None:
            return ()
        return tuple(dict.fromkeys(position for _, condition, _, _ in transfer.removals
                                   for position in condition.prepared_removal_occupancies()))

    def validate_prepared_removal(self) -> bool:
        transfer = self._prepared_transfer
        return transfer is None or BaseBlock.validate_prepared_condition_removals(
            [row for row in transfer.removals if row[1] is not transfer.previous])

    def _install_concentration_handler(self) -> None:
        assert self.target_entity_uuid is not None
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        handler_uuids: list[UUID] = []
        def concentration_break_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """On damage, make CON save or lose concentration. On death, auto-break."""

            if event.target_entity_uuid != source_entity_uuid:
                return None

            entity = Entity.get(source_entity_uuid)
            if not entity:
                return None

            if "Concentrating" not in entity.active_conditions:
                return None

            if isinstance(event, DeathEvent):
                conc = entity.active_conditions.get("Concentrating")
                spell_name = "spell"
                if conc is not None and isinstance(conc, Concentrating):
                    spell_name = conc.spell_name
                entity.release_involuntary_sustain(InvoluntarySustainLoss(
                    cause=SustainLossCause.DEATH,
                    sustaining_condition_uuid=self.uuid,
                    parent_event_uuid=event.uuid,
                ))
                return None

            if not isinstance(event, DamageAppliedEvent):
                return None

            if event.resulting_normal_hp <= 0:
                entity.release_involuntary_sustain(InvoluntarySustainLoss(
                    cause=SustainLossCause.ZERO_HP,
                    sustaining_condition_uuid=self.uuid,
                    parent_event_uuid=event.uuid,
                ))
                return None

            damage = event.applied_damage

            dc = max(10, damage // 2)

            save_request = SavingThrowEvent(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=source_entity_uuid,
                ability_name="constitution",
                dc=dc,
                source_entity_name=entity.name,
                target_entity_name=entity.name,
                parent_event=event.uuid
            )

            _, _, success = entity.saving_throw(save_request)

            if not success:

                conc = entity.active_conditions.get("Concentrating")
                spell_name = "spell"
                if conc is not None and isinstance(conc, Concentrating):
                    spell_name = conc.spell_name

                entity.release_involuntary_sustain(InvoluntarySustainLoss(
                    cause=SustainLossCause.FAILED_SAVE,
                    sustaining_condition_uuid=self.uuid,
                    parent_event_uuid=event.uuid,
                ))
                return event.with_updates(
                    concentration_broken=True,
                    status_message=(
                        f"{entity.name} lost concentration on {spell_name} "
                        f"(failed DC {dc} CON save)"
                    ),
                )

            return None

        if isinstance(target, Entity):
            handler = EventHandler(
                name=f"Concentration Check ({self.spell_name})",
                source_entity_uuid=self.target_entity_uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=self.target_entity_uuid),
                    Trigger(event_type=EventType.DEATH, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=self.target_entity_uuid),
                ],
                event_processor=concentration_break_processor,
            )
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        self.event_handlers_uuids.extend(handler_uuids)

    def _commit_application(self, effect_event: Event) -> None:
        transfer = self._prepared_transfer
        if transfer is None:
            raise RuntimeError("Concentration was not prepared")
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            raise RuntimeError("Prepared concentration owner disappeared")
        if not self.validate_prepared_removal():
            raise RuntimeError("Prepared concentration replacement no longer matches native state")
        existing = transfer.previous
        retained_slots, retained_links, prepared = transfer.retained_slots, transfer.retained_links, transfer.removals
        if existing is not None:
            for slot_uuid, slot in retained_slots.items():
                self.concentration_slots[slot_uuid] = slot
            for pair in retained_links:
                if pair not in self.linked_conditions:
                    self.linked_conditions.append(pair)
                child = BaseCondition.get(pair[1])
                if isinstance(child, BaseCondition):
                    child.parent_link = (target.uuid, self.uuid)
            existing.linked_conditions.clear()
            existing.sub_conditions.clear()
            for slot_uuid, slot in existing.concentration_slots.items():
                if slot_uuid not in retained_slots:
                    slot.remove_from_register()
            existing.concentration_slots.clear()
            self._sync_spell_name()
            transfer.committed_removals = BaseBlock._commit_prepared_condition_removals(prepared, publish=False)
        self._install_concentration_handler()

    def publish_prepared_application(self) -> None:
        transfer = self._prepared_transfer
        if transfer is not None and transfer.committed_removals is not None:
            BaseBlock._publish_committed_condition_removals(transfer.committed_removals)
        self._prepared_transfer = None

    def _release_owned_runtime_state(self, *, parent_event: Optional[Event] = None) -> None:
        """Release concentration slots on committed removal and provisional rollback."""
        transfer = self._prepared_transfer
        self._prepared_transfer = None
        try:
            if transfer is not None and transfer.committed_removals is None:
                BaseBlock.cancel_owned_condition_removals(
                    PreparedConditionRemovals(transfer.removals), "Concentration admission canceled",
                )
        finally:
            for slot in self.concentration_slots.values():
                slot.remove_from_register()
            self.concentration_slots.clear()
            self._active_slot_uuid = None
            super()._release_owned_runtime_state(parent_event=parent_event)


class ConcentrationActionMarker(BaseCondition):
    """Marker condition for action-grant concentration spells (CallLightning, Sunbeam).

    When removed (via concentration break), deregisters the granted action template.
    """
    name: str = "Concentration Action"
    description: str = "Tracking concentration on an action-grant spell"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    action_name: str = ""
    action_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Tracking concentration on {self.action_name}"
        )
        return [], [], [], [], effect_event

    def _release_owned_runtime_state(self, *, parent_event: Optional[Event] = None) -> None:
        entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if entity and self.action_uuid is not None:
            entity.unregister_action_by_uuid(self.action_uuid)
        elif entity and self.action_name:
            entity.unregister_action(self.action_name)
        super()._release_owned_runtime_state(parent_event=parent_event)


@_core_condition_identity(
    content_id="condition.no_reactions",
    display_name="No Reactions",
    description="Cannot take reactions for the condition duration.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Reactions",
    sort_order=210,
)
class NoReactions(BaseCondition):
    """
    Prevents the target from taking reactions.

    Used by Shocking Grasp - "target can't take reactions until the start
    of its next turn."

    This condition sets max reactions to 0 via self_static.
    Duration: 1 round (expires at start of target's next turn).
    """
    name: str = "No Reactions"
    description: str = "Cannot take reactions"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        outs: List[Tuple[UUID, UUID]] = []

        reaction_max_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(
            constraint=NumericalModifier(
                name="No Reactions",
                value=0,
                source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target_entity.action_economy.reactions.uuid, reaction_max_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied No Reactions to {target_entity.name}"
        )
        return outs, [], [], [], effect_event


@_core_condition_identity(
    content_id="condition.hidden",
    display_name="Hidden",
    description="Is concealed from observers whose perception does not reveal it.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Using Ability Scores: Hiding",
    sort_order=220,
)
class Hidden(BaseCondition):
    """Stealth condition that hides an entity from low-perception observers.

    The condition stores a stealth DC, grants unseen-attacker advantage, and
    installs a reveal handler for attacks, damage, incapacitation, revealing
    actions, bright light, and hidden movement collisions.
    """
    name: str = Field(default="Hidden", description="Condition name.")
    description: str = Field(default="Hidden from observers via Stealth", description="Condition description.")
    obscures_perceivability: bool = Field(default=True, description="Removing hidden status may reveal the target.")
    stealth_result: int = Field(default=0, description="Stealth check result used as perception DC.")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition.")

    _stealth_changed: bool = PrivateAttr(default=False)

    def format_application_log(self, target_name: str) -> str:
        """Render the hidden-specific application message with its Stealth DC."""
        return f"{{cyan:{target_name}}} gains **Hidden** (Stealth DC {self.stealth_result})"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            adv_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Hidden (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, adv_uuid))

            try:
                effect_event = declaration_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Hidden to {target_entity.name} (Stealth DC {self.stealth_result})"
                )
            except BaseException:
                remove_modifier_ownership(outs)
                raise

            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            handler = EventHandler(
                name="Hidden: Reveal",
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.SPATIAL_LIGHT_CHANGED, event_phase=EventPhase.EFFECT),
                    Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.MOVEMENT_COLLISION, event_phase=EventPhase.EFFECT),
                ],
                event_processor=hidden_reveal_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    def _commit_application(self, event: Event) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            self._stealth_changed = target.set_stealth_dc(self.stealth_result, publish=False)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied and target is not None:
            remaining = max((condition.stealth_result for condition in target.active_conditions_by_uuid.values()
                if condition.uuid != self.uuid and condition.applied and isinstance(condition, Hidden)), default=None)
            self._stealth_changed = target.set_stealth_dc(remaining, publish=False) or self._stealth_changed

    def on_membership_changed(self, event: Event) -> None:
        changed, self._stealth_changed = self._stealth_changed, False
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)

NON_REVEALING_ACTIONS = {
    "Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone",
    "Open Door", "Close Door",
    "Ignite Torch", "Extinguish Torch", "Light Wall Torch", "Extinguish Wall Torch",
}


def hidden_reveal_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Remove Hidden when an event reveals the entity.

    Args:
        event: Event that may reveal the hidden entity.
        source_entity_uuid: UUID of the hidden entity.

    Returns:
        None; reveal is performed through condition removal side effects.
    """
    if not event.is_last:
        return None

    if event.event_type == EventType.MOVEMENT_COLLISION:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and isinstance(event, SpatialChangeEvent):
            if event.position == entity.position and "Hidden" in entity.active_conditions:
                entity.remove_condition("Hidden", parent_event=event)
        return None

    if event.event_type == EventType.SPATIAL_LIGHT_CHANGED:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
            changed_positions = {event.position} if isinstance(event, SpatialChangeEvent) else set()
            if (
                isinstance(event, SpatialChangeEvent)
                and event.senses_hint is not None
                and event.senses_hint.light_changed_positions
            ):
                changed_positions.update(event.senses_hint.light_changed_positions)
            if entity.position in changed_positions:
                tile = get_map().get_tile(*entity.position)
                if tile and tile.resolved_light_level == LightLevel.VERY_BRIGHT:
                    removal_parent = event.get_parent_event() or event
                    entity.remove_condition("Hidden", parent_event=removal_parent)
        return None

    if event.event_type == EventType.SPATIAL_ENTITY_ENTERED:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
            tile = get_map().get_tile(*entity.position)
            if tile and tile.resolved_light_level == LightLevel.VERY_BRIGHT:
                entity.remove_condition("Hidden", parent_event=event)
        return None

    if event.event_type == EventType.CONDITION_APPLICATION:
        if (
            not isinstance(event, ConditionApplicationEvent)
            or event.condition.agency_denial is not ConditionAgencyDenial.FULL_TURN
        ):
            return None

    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
        condition = entity.active_conditions.get("Hidden")
        if isinstance(condition, Hidden) and condition.creation_lineage_uuid == event.lineage_uuid:
            return None
        entity.remove_condition("Hidden", parent_event=event)
    return None


class InvisibilityEffect(BaseCondition):
    """Spell invisibility that breaks on attacks, spells, or revealing actions."""

    name: str = Field(default="Invisible", description="Condition name.")
    description: str = Field(default="Invisible until attacking or casting a spell", description="Condition description.")
    grants_invisibility: bool = True
    obscures_perceivability: bool = Field(default=True, description="Removing invisibility may reveal the target.")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition.")
    reveal_on_spell: bool = True
    reveal_on_other_actions: bool = True

    _invisibility_changed: bool = PrivateAttr(default=False)

    def _commit_application(self, effect_event: Event) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            self._invisibility_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied and target is not None:
            self._invisibility_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._invisibility_changed = self._invisibility_changed, False
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)

    def format_application_log(self, target_name: str) -> str:
        """Render the invisibility-specific application message."""
        return f"{{cyan:{target_name}}} becomes **invisible**"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []


            self_ctx_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Invisible (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_ctx_uuid))

            to_target_ctx_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Invisible (Unseen Target)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_target_disadvantage
                )
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, to_target_ctx_uuid))

            try:
                effect_event = declaration_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Invisibility to {target_entity.name}"
                )
            except BaseException:
                remove_modifier_ownership(outs)
                raise

            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            handler = EventHandler(
                name="Invisibility: Reveal", runs_while_suppressed=True,
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                ],
                event_processor=invisibility_reveal_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity")


def invisibility_reveal_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Remove spell invisibility when an event reveals the entity.

    Args:
        event: Event that may reveal the invisible entity.
        source_entity_uuid: UUID of the invisible entity.

    Returns:
        None; reveal is performed through condition removal side effects.
    """
    if not event.is_last:
        return None

    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if entity and isinstance(entity, Entity) and "Invisible" in entity.active_conditions:
        condition = entity.active_conditions.get("Invisible")
        if isinstance(condition, InvisibilityEffect):
            if condition.creation_lineage_uuid == event.lineage_uuid:
                return None
            if event.event_type == EventType.CAST_SPELL and not condition.reveal_on_spell:
                return None
            if event.event_type == EventType.BASE_ACTION and not condition.reveal_on_other_actions:
                return None
            entity.remove_condition("Invisible", parent_event=event)
    return None


class GreaterInvisibilityEffect(BaseCondition):
    """BG3-style Greater Invisibility with escalating stealth checks."""

    name: str = Field(default="Invisible", description="Condition name.")
    description: str = Field(default="Greater Invisibility - Stealth check to maintain", description="Condition description.")
    grants_invisibility: bool = True
    obscures_perceivability: bool = Field(default=True, description="Removing invisibility may reveal the target.")
    check_count: int = Field(default=0, description="Number of successful stealth checks")
    base_dc: int = Field(default=15, description="Starting DC for stealth check")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition")

    _invisibility_changed: bool = PrivateAttr(default=False)

    def _commit_application(self, effect_event: Event) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            self._invisibility_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied and target is not None:
            self._invisibility_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._invisibility_changed = self._invisibility_changed, False
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)

    def format_application_log(self, target_name: str) -> str:
        """Render the invisibility-specific application message."""
        return f"{{cyan:{target_name}}} becomes **invisible**"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if self.duration.duration_type is DurationType.PERMANENT and self.duration.duration is None:
            self.duration.duration_type = DurationType.ROUNDS
            self.duration.duration = 10
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []


            self_ctx_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Greater Invisibility (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_ctx_uuid))

            to_target_ctx_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Greater Invisibility (Unseen Target)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_target_disadvantage
                )
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, to_target_ctx_uuid))

            try:
                effect_event = declaration_event.phase_to(
                    EventPhase.EFFECT,
                    update={"condition": self},
                    status_message=f"Applied Greater Invisibility to {target_entity.name}"
                )
            except BaseException:
                remove_modifier_ownership(outs)
                raise

            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            handler = EventHandler(
                name="Greater Invisibility: Stealth Check",
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                ],
                event_processor=greater_invisibility_check_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity")


def greater_invisibility_check_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Roll a stealth check to maintain Greater Invisibility."""
    if not event.is_last:
        return None

    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity):
        return None
    condition = entity.active_conditions.get("Invisible")
    if not condition or not isinstance(condition, GreaterInvisibilityEffect):
        return None

    if condition.creation_lineage_uuid == event.lineage_uuid:
        return None

    dc = condition.base_dc + condition.check_count
    skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    stealth_roll, check_event = entity.roll_d20_event(
        skill_bonus,
        RollType.CHECK,
        skill_name="stealth",
        parent_event=event.uuid,
    )
    success = stealth_roll.total >= dc

    if success:
        condition.check_count += 1
    else:
        entity.remove_condition("Invisible", parent_event=check_event)

    entity_name = entity.name
    roll_results = stealth_roll.results if isinstance(stealth_roll.results, list) else [stealth_roll.results]
    d20_used = roll_results[0] if roll_results else 0
    adv_status = None
    if stealth_roll.advantage_status == AdvantageStatus.ADVANTAGE:
        adv_status = "advantage"
    elif stealth_roll.advantage_status == AdvantageStatus.DISADVANTAGE:
        adv_status = "disadvantage"

    roll_display = DiceRollDisplay(
        dice_str="d20",
        results=roll_results,
        bonus=stealth_roll.bonus,
        total=stealth_roll.total,
        all_d20_rolls=roll_results if len(roll_results) > 1 else None,
        d20_used=d20_used,
        advantage_status=adv_status
    )

    if success:
        compact = f"{{cyan:{entity_name}}} maintains invisibility (Stealth {stealth_roll.total} vs DC {dc})"
    else:
        compact = f"{{cyan:{entity_name}}} loses invisibility! (Stealth {stealth_roll.total} vs DC {dc})"

    verbose = f"{{cyan:{entity_name}}} Stealth check: d20({d20_used}) +{stealth_roll.bonus} = {stealth_roll.total} vs DC {dc}"
    if success:
        verbose += " → maintains invisibility"
    else:
        verbose += " → {{red:loses invisibility!}}"

    stealth_bonus_breakdown: List[ModifierBreakdown] = []
    stealth_advantage_breakdown: List[ModifierBreakdown] = []
    for mod in skill_bonus.get_breakdown():
        stealth_bonus_breakdown.append(ModifierBreakdown(
            name=mod.get('name', 'Unknown'),
            value=mod.get('value', 0),
            source=mod.get('source', 'self')
        ))
    for mod in skill_bonus.get_full_advantage_breakdown():
        adv_val = mod.get('value', 'inactive')
        if adv_val == 'advantage':
            stealth_advantage_breakdown.append(ModifierBreakdown(
                name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
            ))
        elif adv_val == 'disadvantage':
            stealth_advantage_breakdown.append(ModifierBreakdown(
                name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
            ))

    check_event.combat_log = CombatLogEntry(
        entry_type=CombatLogEntryType.SKILL_CHECK,
        source_name=entity_name,
        source_uuid=str(entity.uuid),
        compact=compact,
        verbose=verbose,
        detailed=verbose,
        success=success,
        data=SkillCheckLogData(
            entity_name=entity_name,
            entity_uuid=str(entity.uuid),
            skill="stealth",
            dc=dc,
            roll=roll_display,
            bonus_breakdown=stealth_bonus_breakdown,
            advantage_breakdown=stealth_advantage_breakdown,
            success=success
        ).model_dump()
    )

    check_event.phase_to(EventPhase.COMPLETION)
    return None



_CORE_STANDARD_CONDITION_TYPES = (
        Underwater,
        Blinded,
        Charmed,
        Dashing,
        Deafened,
        Exhaustion,
        Dodging,
        Disengaging,
        Frightened,
        Grappled,
        Incapacitated,
        Invisible,
        Paralyzed,
        Petrified,
        Poisoned,
        Prone,
        Stunned,
        Restrained,
        Unconscious,
        Concentrating,
        NoReactions,
        Hidden,
)
CORE_STANDARD_CONDITION_DECLARATIONS_BY_CLASS = MappingProxyType({
    condition_type: get_content_declaration(condition_type)
    for condition_type in _CORE_STANDARD_CONDITION_TYPES
})
CORE_STANDARD_CONDITION_DECLARATIONS = tuple(
    CORE_STANDARD_CONDITION_DECLARATIONS_BY_CLASS[condition_type]
    for condition_type in _CORE_STANDARD_CONDITION_TYPES
)
