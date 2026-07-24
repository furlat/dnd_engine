"""Illusion spells that deceive senses, alter perception, and obscure areas.

Implemented here: Blur, Fear, Hypnotic Pattern, Color Spray, Invisibility,
Greater Invisibility, Mirror Image, and Silence.
"""

import random
from typing import Any, Dict, Optional, List, Set, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr
from typing import cast as type_cast

from dnd.core.base_actions import (
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import (
    BaseCondition,
    Duration,
)
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionRemovalTrigger,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Event, EventQueue
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, NumericalModifier
from dnd.core.dice import AttackOutcome
from dnd.core.aoe import AoEShape, Cone, Cube
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, AttackEvent
from dnd.conditions import Frightened, Charmed, Blinded, Deafened, InvisibilityEffect, GreaterInvisibilityEffect
from dnd.creature_transforms import apply_incapacitated_transform
from dnd.tile_conditions import ZoneControlCondition
from dnd.core.gridmap import get_map
from dnd.core.events import SpatialChangeEvent


class BlurEffect(BaseCondition):
    """Effect from Blur spell.

    Attackers have disadvantage on attack rolls against you.
    """
    name: str = Field(default="Blur", description="Condition name.")
    description: str = Field(default="Your body becomes blurred, giving attackers disadvantage", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply attacker disadvantage against the blurred target.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Modifier ownership entries and the condition effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        disadv_mod = AdvantageModifier(
            name="Blur",
            value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.source_entity_uuid or self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(disadv_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Blur to {target.name}"
        )
        return outs, [], [], [], effect_event


class Blur(SpellAction):
    """Blur - 2nd level Illusion (Concentration)

    Your body becomes blurred, shifting and wavering to all who can see you.
    For the duration, any creature has disadvantage on attack rolls against you.
    An attacker is immune to this effect if it doesn't rely on sight, as with
    blindsight, or can see through illusions, as with truesight.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Blur", description="Spell name.")
    description: str = Field(default="Concentration. Attackers have disadvantage against you.", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Blur's defensive self condition."""
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="defense.blur",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="defense.blur.incoming_disadvantage",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("actor.condition.blur",),
                    condition_semantic_keys=frozenset({"dnd.spells.illusion.BlurEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate that the caster exists for this self spell."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Blur to the caster and link it to concentration."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} becomes blurred"
        )

        blur_effect = BlurEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        caster.add_condition(blur_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(caster.uuid, blur_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Blur (concentration)"
        )


class FearEffect(BaseCondition):
    """Effect from Fear spell.

    Target is Frightened of the caster and must Dash away on each turn.
    Repeat WIS save at end of each turn (only if can't see caster).
    """
    name: str = Field(default="Fear", description="Condition name.")
    description: str = Field(default="Frightened of the caster, must Dash away", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that frightened the target.")
    spell_dc: int = Field(default=10, description="Wisdom save DC used for repeat saves.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Fear and register its conditional repeat-save handler.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Handler and sub-condition ownership entries plus the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        frightened = Frightened(
            source_entity_uuid=self.caster_uuid or self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(frightened, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(frightened.uuid)

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Fear effect to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create the end-turn repeat save handler for Fear."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def repeat_save_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            fear_effect = target.active_conditions.get("Fear")
            if not fear_effect or fear_effect.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Fear", parent_event=event)
                return None

            if caster_uuid in target.senses.entities:
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _roll, _outcome, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Fear", parent_event=event)
            return None

        return EventHandler(
            name=f"Fear Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class Fear(SpellAction):
    """Fear - 3rd level Illusion (Concentration)

    You project a phantasmal image of a creature's worst fears. Each creature
    in a 30-foot cone must succeed on a WIS save or drop whatever it is holding
    and become frightened for the duration.

    While frightened, a creature must Dash away from you each turn by the safest
    available route. If there is nowhere to move, the creature can use the Dodge
    action. If the creature ends its turn in a location where it doesn't have line
    of sight to you, the creature can make a WIS save. On success, the spell ends.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Fear", description="Spell name.")
    description: str = Field(default="30ft cone, WIS save or Frightened + must Dash away", description="Spell description.")
    spell_level: int = Field(default=3, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Cone area used by Fear.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the area.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def model_post_init(self, __context: Any) -> None:
        """Initialize the default cone area when no custom shape is supplied."""
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=30
            )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Fear's save-based frightened branch."""
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.fear",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.fear",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(),
                    save_ability="wisdom",
                    condition_fact_ids=("selected_target.condition.frightened",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.illusion.FearEffect",
                        "dnd.conditions.Frightened",
                    }),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Fear to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "wisdom").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Fear"
            )

        fear_effect = FearEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(fear_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        if fear_effect.applied:
            concentration.add_linked_condition(target.uuid, fear_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Frightened by Fear"
        )


class HypnoticPatternEffect(BaseCondition):
    """Effect from Hypnotic Pattern spell.

    Target is Charmed and Incapacitated (incapacitated + speed 0).
    Breaks when target takes damage or is shaken awake.
    """
    name: str = Field(default="Hypnotic Pattern", description="Condition name.")
    description: str = Field(default="Charmed and incapacitated by swirling pattern", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    removal_triggers: frozenset[ConditionRemovalTrigger] = Field(
        default_factory=lambda: frozenset({
            ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED,
            ConditionRemovalTrigger.SHAKE_AWAKE,
        }),
        description="Positive damage or external assistance ends this effect.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="The complete effect removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Charmed plus a directly owned incapacitation transform.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Handler and sub-condition ownership entries plus the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        charmed = Charmed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(charmed, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(charmed.uuid)

        outs = apply_incapacitated_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )

        handler = self._create_damage_break_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Hypnotic Pattern effect to {target.name}"
        )
        return outs, handler_uuids, sub_condition_uuids, [], effect_event

    def _create_damage_break_handler(self) -> EventHandler:
        """Break Hypnotic Pattern when target takes damage."""
        assert self.target_entity_uuid is not None

        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def damage_break_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None

            hp_effect = target.active_conditions.get("Hypnotic Pattern")
            if not hp_effect or hp_effect.uuid != effect_uuid:
                return None

            target.remove_condition("Hypnotic Pattern", parent_event=event)
            return None

        return EventHandler(
            name=f"Hypnotic Pattern Damage Break ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT)
            ],
            event_processor=damage_break_processor
        )


class HypnoticPattern(SpellAction):
    """Hypnotic Pattern - 3rd level Illusion (Concentration)

    You create a twisting pattern of colors that weaves through the air inside
    a 30-foot cube within range. Each creature in the area who sees the pattern
    must make a WIS save. On a failed save, the creature becomes charmed for the
    duration. While charmed, the creature is incapacitated and has a speed of 0.

    The spell ends for an affected creature if it takes any damage or if someone
    else uses an action to shake the creature out of its stupor.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Hypnotic Pattern", description="Spell name.")
    description: str = Field(default="30ft cube, WIS save or Charmed + Incapacitated", description="Spell description.")
    spell_level: int = Field(default=3, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120), description="Spell range.")
    projectile_type: Optional[str] = Field(default="orb", description="Client-facing projectile visual key.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Cube area used by Hypnotic Pattern.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the area.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def model_post_init(self, __context: Any) -> None:
        """Initialize the default cube area when no custom shape is supplied."""
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                size_feet=30,
                centered=True
            )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Hypnotic Pattern's save-based agency denial."""
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.hypnotic_pattern",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.hypnotic_pattern",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(),
                    save_ability="wisdom",
                    condition_fact_ids=("selected_target.condition.hypnotic_pattern",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.illusion.HypnoticPatternEffect",
                        "dnd.conditions.Charmed",
                    }),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not in LOS")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Hypnotic Pattern to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "wisdom").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Hypnotic Pattern"
            )

        hp_effect = HypnoticPatternEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(hp_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        if hp_effect.applied:
            concentration.add_linked_condition(target.uuid, hp_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is mesmerized by Hypnotic Pattern"
        )


class ColorSprayEffect(BaseCondition):
    """Effect from Color Spray spell.

    Target is Blinded for 1 round (until end of caster's next turn).
    """
    name: str = Field(default="Color Spray", description="Condition name.")
    description: str = Field(default="Blinded by dazzling colors", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Color Spray and its Blinded sub-condition.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Sub-condition ownership entries plus the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []

        blinded = Blinded(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(blinded, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(blinded.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Color Spray blindness to {target.name}"
        )
        return [], [], sub_condition_uuids, [], effect_event


class ColorSpray(SpellAction):
    """Color Spray - 1st level Illusion

    Roll 6d10 HP pool. Creatures in 15ft cone are Blinded for 1 round
    in order of lowest HP until pool exhausted.

    Skip: creatures that cannot currently see, creatures immune to Blinded
    Upcast: +2d10 per slot level above 1st.
    """
    name: str = Field(default="Color Spray", description="Spell name.")
    description: str = Field(default="Roll 6d10 HP pool. Affects creatures in order of lowest HP.", description="Spell description.")
    spell_level: int = Field(default=1, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Cone area used by Color Spray.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the cone.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")
    hp_pool_rolled: int = Field(
        default=0,
        description="Total hit point pool rolled for this Color Spray spell instance.",
    )
    hp_pool_remaining: int = Field(
        default=0,
        description="Hit point pool remaining after this Color Spray instance selects targets.",
    )
    _selected_hp_pool_targets: Optional[List[UUID]] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Initialize the default cone area when no custom shape is supplied."""
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=15
            )

    def get_hp_pool_dice(self) -> Tuple[int, int]:
        """Return the Color Spray HP-pool dice tuple."""
        base_dice = 6
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 2
        return (base_dice + upcast_bonus, 10)

    def get_all_targets(self) -> List[UUID]:
        """Select targets by HP pool instead of all AoE targets.

        Returns:
            Target UUIDs selected by current HP order and remaining HP pool.
        """
        if self._selected_hp_pool_targets is not None:
            return list(self._selected_hp_pool_targets)

        if not (self.aoe_shape and self.end_position):
            return []

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return []

        self.aoe_shape.compute_objective(caster.position)

        candidates: List[Tuple[int, UUID]] = []
        for uid in self.aoe_shape.affected_entity_uuids:
            if uid == self.source_entity_uuid:
                continue

            entity = Entity.get(uid)
            if not entity or not entity.has_hp:
                continue

            if not entity.can_see_visual_effects():
                continue

            if entity.check_condition_immunity("Blinded"):
                continue

            candidates.append((entity.get_hp(), uid))

        candidates.sort(key=lambda x: (x[0], str(x[1])))

        if self.hp_pool_rolled == 0:
            dice_count, dice_value = self.get_hp_pool_dice()
            roll_results = [random.randint(1, dice_value) for _ in range(dice_count)]
            total = sum(roll_results)
            self.hp_pool_rolled = total
            self.hp_pool_remaining = total

        targets: List[UUID] = []
        remaining = self.hp_pool_remaining if self.hp_pool_remaining > 0 else self.hp_pool_rolled
        for hp, uid in candidates:
            if hp <= remaining:
                targets.append(uid)
                remaining -= hp

        self.hp_pool_remaining = remaining
        self._selected_hp_pool_targets = targets
        return list(targets)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction. Self-range means no LOS check to target position."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Color Spray blindness to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Color Spray affecting {target.name} ({target.get_hp()} HP)"
        )

        color_spray_effect = ColorSprayEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
        )
        target.add_condition(color_spray_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is blinded by Color Spray ({target.get_hp()} HP)"
        )


class Invisibility(SpellAction):
    """Invisibility - 2nd level Illusion (Concentration)

    A creature you touch becomes invisible until the spell ends.
    Anything the target is wearing or carrying is invisible as long as it
    is on the target's person. The spell ends for a target that attacks
    or casts a spell.

    Duration: Concentration, up to 1 hour.
    Range: Touch (5ft).
    """
    name: str = Field(default="Invisibility", description="Spell name.")
    description: str = Field(default="Concentration. Touch target becomes invisible until attacking or casting.", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Invisibility's selected-target stealth condition."""
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="defense.invisibility",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="defense.invisibility.hidden",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.invisible",),
                    condition_semantic_keys=frozenset({"dnd.conditions.InvisibilityEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate touch range (5ft)."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft, max {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Invisibility to target."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not target or not isinstance(target, Entity):
            return execution_event.cancel(status_message="Target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Invisibility on {target.name}"
        )

        invis_effect = InvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(invis_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        if invis_effect.applied:
            concentration.add_linked_condition(target.uuid, invis_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Invisibility on {target.name} (concentration)"
        )


class GreaterInvisibility(SpellAction):
    """Greater Invisibility - 4th level Illusion (Concentration)

    BG3-style: A creature you touch becomes invisible. On attack or spell cast,
    rolls a Stealth check vs escalating DC to maintain invisibility
    (DC 15, +1 per success).

    Duration: Concentration, up to 10 rounds.
    Range: Touch (5ft).
    """
    name: str = Field(default="Greater Invisibility", description="Spell name.")
    description: str = Field(default="Concentration. Touch target becomes invisible, Stealth check to maintain on attack/cast.", description="Spell description.")
    spell_level: int = Field(default=4, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Greater Invisibility's maintained stealth condition."""
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="defense.greater_invisibility",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="defense.greater_invisibility.hidden",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.greater_invisibility",),
                    condition_semantic_keys=frozenset({"dnd.conditions.GreaterInvisibilityEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate touch range (5ft)."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft, max {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Greater Invisibility to target."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not target or not isinstance(target, Entity):
            return execution_event.cancel(status_message="Target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Greater Invisibility on {target.name}"
        )

        invis_effect = GreaterInvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(invis_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        if invis_effect.applied:
            concentration.add_linked_condition(target.uuid, invis_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Greater Invisibility on {target.name} (concentration)"
        )


class MirrorImageEffect(BaseCondition):
    """Effect from Mirror Image spell (BG3 version).

    Creates 3 illusory duplicates. Each duplicate grants +3 AC.
    When an attack misses the caster, one duplicate disappears (AC drops by 3).
    Condition removed when all duplicates are destroyed or after 10 rounds.

    - 3 duplicates: +9 AC
    - 2 duplicates: +6 AC
    - 1 duplicate:  +3 AC
    - 0 duplicates: condition ends
    """
    name: str = Field(default="Mirror Image", description="Condition name.")
    description: str = Field(default="Illusory duplicates increase AC by 3 each", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    duplicates: int = Field(default=3, description="Number of remaining duplicates")

    _ac_modifier_uuid: Optional[UUID] = None
    _ac_mv_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        """Apply Mirror Image AC bonus and miss handler.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Modifier and handler ownership entries plus the effect event.
        """
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        self.duplicates = 3

        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 10

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        ac_mod = NumericalModifier(
            name="Mirror Image",
            value=9,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))
        self._ac_modifier_uuid = ac_mod.uuid
        self._ac_mv_uuid = target.equipment.ac_bonus.uuid

        miss_handler = self._create_miss_handler()
        target.add_event_handler(miss_handler)
        handler_uuids.append(miss_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Mirror Image (+9 AC, 3 duplicates) to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, handler_uuids, [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        """Return target AC after Mirror Image cleanup."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}

    def _create_miss_handler(self) -> EventHandler:
        """When an attack misses the caster, destroy one duplicate."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None

            if not isinstance(event, AttackEvent):
                return None
            if event.attack_outcome is None:
                return None

            if event.attack_outcome not in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS):
                return None

            if condition.duplicates <= 0:
                return None

            condition.duplicates -= 1
            remaining = condition.duplicates

            if condition._ac_modifier_uuid and condition._ac_mv_uuid:
                mv = ModifiableValue.get(condition._ac_mv_uuid)
                if mv:
                    mod = mv.self_static.value_modifiers.get(condition._ac_modifier_uuid)
                    if mod:
                        mod.value = remaining * 3

            if remaining <= 0:
                target = Entity.get(target_uuid)
                if target:
                    target.remove_condition("Mirror Image", parent_event=event)

            return None

        return EventHandler(
            name="Mirror Image: Evade",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )


class MirrorImage(SpellAction):
    """Mirror Image - 2nd level Illusion (NO Concentration) — BG3 Version

    Create 3 illusory duplicates of yourself to distract attackers.
    Each duplicate increases your AC by 3. When you successfully evade
    an attack, one of the duplicates disappears.

    Duration: 10 turns. No concentration.
    """
    name: str = Field(default="Mirror Image", description="Spell name.")
    description: str = Field(default="3 duplicates, +3 AC each, lost on evade", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Mirror Image's defensive duplicate condition."""
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="defense.mirror_image",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="defense.mirror_image.duplicates",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("actor.condition.mirror_image",),
                    condition_semantic_keys=frozenset({"dnd.spells.illusion.MirrorImageEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate that the caster exists for this self spell."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mirror Image to self."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} creates mirror images"
        )

        mirror_effect = MirrorImageEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        caster.add_condition(mirror_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Mirror Image (3 duplicates, +9 AC)"
        )


class SilenceZone(ZoneControlCondition):
    """Silence zone that blocks verbal spells and deafens creatures inside.

    20ft radius sphere, concentration, 10 rounds.
    """
    name: str = Field(default="Silence Zone", description="Condition name.")
    description: str = Field(default="Area of magical silence - no sound, blocks verbal spells", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    zone_shape: str = Field(default="sphere", description="Zone shape key.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet.")

    marker_name: Optional[str] = Field(default="Silence", description="Tile marker name.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=None, description="Optional hazard visibility filter for the tile marker.")

    spell_dc: int = Field(default=0, description="Spell save DC placeholder for zone contracts.")
    _deafened_uuids: List[UUID] = []
    _spell_block_handler_uuid: Optional[UUID] = None

    def _has_entry_effect(self) -> bool:
        """Return whether entering the zone has an effect."""
        return True

    def _has_exit_effect(self) -> bool:
        """Return whether leaving the zone has an effect."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Apply Deafened when entity enters the silence zone."""
        source_uuid = self.source_entity_uuid
        zone_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if "Silence Deafened" not in entity.active_conditions:
                deafened = _SilenceDeafened(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    zone_uuid=zone_uuid
                )
                entity.add_condition(deafened, parent_event=event)

            return None

        return EventHandler(
            name="Silence Zone Entry",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_exit_handler(self) -> EventHandler:
        """Remove Deafened when entity leaves the silence zone."""
        source_uuid = self.source_entity_uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if "Silence Deafened" in entity.active_conditions:
                entity.remove_condition("Silence Deafened", parent_event=event)

            return None

        return EventHandler(
            name="Silence Zone Exit",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone and register spell-blocking handler."""
        result = super()._apply(declaration_event)
        outs, handler_uuids, sub_cond_uuids, spatial_uuids, effect_event = result

        spell_block_handler = self._create_spell_block_handler()
        EventQueue.add_event_handler(spell_block_handler)
        handler_uuids.append(spell_block_handler.uuid)
        self._spell_block_handler_uuid = spell_block_handler.uuid

        grid = get_map()
        for pos in self.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if "Silence Deafened" not in ent.active_conditions:
                    deafened = _SilenceDeafened(
                        source_entity_uuid=self.source_entity_uuid,
                        target_entity_uuid=ent.uuid,
                        zone_uuid=self.uuid
                    )
                    ent.add_condition(deafened, parent_event=effect_event)

        return outs, handler_uuids, sub_cond_uuids, spatial_uuids, effect_event

    def _create_spell_block_handler(self) -> EventHandler:
        """Block verbal spellcasting within the silence zone."""
        zone_positions = self.affected_positions
        zone_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            caster = Entity.get(event.source_entity_uuid) if event.source_entity_uuid else None
            if not caster:
                return None

            if caster.position not in zone_positions:
                return None

            if isinstance(event, SpellEvent) and event.verbal:
                return event.cancel(status_message="Cannot cast verbal spell in Silence zone")

            return None

        return EventHandler(
            name=f"Silence Spell Block ({zone_uuid})",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove deafened conditions from all entities in zone."""
        grid = get_map()
        for pos in self.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if "Silence Deafened" in ent.active_conditions:
                    active = ent.active_conditions.get("Silence Deafened")
                    if active and isinstance(active, _SilenceDeafened) and active.zone_uuid == self.uuid:
                        ent.remove_condition("Silence Deafened", parent_event=event)
        return super()._remove(event)


class _SilenceDeafened(BaseCondition):
    """Deafened condition specifically from Silence zone.

    Uses a unique name so it doesn't conflict with regular Deafened.
    """
    name: str = Field(default="Silence Deafened", description="Condition name.")
    description: str = Field(default="Deafened by Silence spell", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    zone_uuid: Optional[UUID] = Field(default=None, description="Silence zone condition UUID that owns this deafened condition.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        """Apply the underlying Deafened sub-condition.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Sub-condition ownership entry plus the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        deafened = Deafened(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(deafened, parent_event=declaration_event)
        sub_conditions_uuids.append(deafened.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is deafened by Silence"
        )
        return [], [], sub_conditions_uuids, [], effect_event


class Silence(SpellAction):
    """Silence - 2nd level Illusion (Concentration)

    For the duration, no sound can be created within or pass through a
    20-foot-radius sphere centered on a point you choose within range.
    Any creature or object entirely inside the sphere is immune to thunder
    damage, and creatures are deafened while entirely inside. Casting a
    spell that includes a verbal component is impossible there.

    Duration: Concentration, up to 10 minutes (10 rounds).
    """
    name: str = Field(default="Silence", description="Spell name.")
    description: str = Field(default="20ft sphere: no sound, blocks verbal spells, deafens (concentration)", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="illusion", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120), description="Spell range.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate the Silence target position.

        Args:
            declaration_event: Spell declaration event.

        Returns:
            Execution-ready or canceled spell event.
        """
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Create the Silence zone and link it to concentration.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event when setup fails.
        """
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        position = self.end_position
        if not position:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Silence"
        )

        zone = SilenceZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=position,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Silence zone covers a 20ft radius at {position}"
        )
