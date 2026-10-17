"""Divination spells that reveal information or grant special senses."""

from typing import Any, Optional, List, Set, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.action_types import ActionSelection, EntityTargetPerception
from dnd.core.dice import roll_die_face
from dnd.spells.hit_effects import QuarrySustain, ReapplyQuarry, install_hit_rider
from dnd.core.base_actions import (
    Cost,
    ActionInformationOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    InformationEffectProfile,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.base_block import SensesType, SenseMode
from dnd.types.discovery import ActorScan
from dnd.core.events import Event, EventPhase, Range, RangeType, EventType, EventHandler, Trigger, D20RollResultEvent
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.spells.content_metadata import srd_action_identity
from dnd.spells.spell_utils import living_recipients_error, spell_condition_profile
from dnd.core.base_conditions import Duration
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.blocks.skills import all_skills


class SeeInvisibilityEffect(BaseCondition):
    """Grants the ability to see invisible creatures and objects."""

    name: str = Field(default="See Invisibility", description="Condition name.")
    description: str = Field(default="You can see invisible creatures and objects", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    _granted_sense_mode: SenseMode | None = PrivateAttr(default=None)
    _sense_changed: bool = PrivateAttr(default=False)

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Sense recipient missing")
        return [], [], [], [], event.phase_to(EventPhase.EFFECT, update={"condition": self})

    def _commit_application(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            raise RuntimeError("Admitted sense recipient disappeared")
        self._granted_sense_mode = SenseMode(sense_type=SensesType.SEE_INVISIBLE, range_feet=0, contribution_owner_uuid=self.uuid)
        target.senses.add_sense_mode_source(self.uuid, self._granted_sense_mode)
        self._sense_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and self._granted_sense_mode is not None:
            target.senses.remove_sense_mode_source(self.uuid)
            self._granted_sense_mode = None
            self._sense_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._sense_changed = self._sense_changed, False
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)


class SeeInvisibility(SpellAction):
    """Second-level divination spell that grants see-invisible sense."""

    name: str = Field(default="See Invisibility", description="Spell name.")
    description: str = Field(default="See invisible creatures and objects", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")

    def get_world_effect_profile(self) -> ActionWorldEffectProfile:
        """Declare the granted see-invisible sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.see_invisibility",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.ACTOR,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=0,
                    sense_type=SensesType.SEE_INVISIBLE.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.ACTOR,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=0,
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply See Invisibility to the caster.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if the caster is missing.
        """
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts See Invisibility"
        )
        if effect_event.canceled:
            return effect_event

        see_invis = SeeInvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        see_invis.duration.duration_type = DurationType.ROUNDS
        see_invis.duration.duration = 600
        effect_event = self.apply_owned_condition(effect_event, see_invis)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{caster.name} can now see invisible creatures"
        )


class TrueSeeingEffect(BaseCondition):
    """Grants 120ft truesight."""

    name: str = Field(default="True Seeing", description="Condition name.")
    description: str = Field(default="You have truesight out to 120 feet", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    _granted_sense_mode: SenseMode | None = PrivateAttr(default=None)
    _sense_changed: bool = PrivateAttr(default=False)

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Sense recipient missing")
        return [], [], [], [], event.phase_to(EventPhase.EFFECT, update={"condition": self})

    def _commit_application(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            raise RuntimeError("Admitted sense recipient disappeared")
        self._granted_sense_mode = SenseMode(contribution_owner_uuid=self.uuid, sense_type=SensesType.TRUESIGHT, range_feet=120)
        target.senses.add_sense_mode_source(self.uuid, self._granted_sense_mode)
        self._sense_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and self._granted_sense_mode is not None:
            target.senses.remove_sense_mode_source(self.uuid)
            self._granted_sense_mode = None
            self._sense_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._sense_changed = self._sense_changed, False
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)


class TrueSeeing(SpellAction):
    """Sixth-level divination spell that grants 120-foot truesight."""

    name: str = Field(default="True Seeing", description="Spell name.")
    description: str = Field(default="Grant truesight 120ft", description="Spell description.")
    spell_level: int = Field(default=6, description="Spell slot level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")
    include_self: bool = Field(default=True, description="True Seeing may target its caster.")

    entity_target_perception: EntityTargetPerception = EntityTargetPerception.TOUCH_CONTACT

    def get_world_effect_profile(self) -> ActionWorldEffectProfile:
        """Declare the granted truesight sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.true_seeing",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=120,
                    sense_type=SensesType.TRUESIGHT.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=120,
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply the True Seeing condition to the target.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if caster or target is
            missing.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} grants True Seeing to {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        true_seeing = TrueSeeingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        true_seeing.duration.duration_type = DurationType.ROUNDS
        true_seeing.duration.duration = 600
        effect_event = self.apply_owned_condition(effect_event, true_seeing)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{target.name} gains truesight (120ft)"
        )


def _guidance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to one skill check and consume Guidance.

    Args:
        event: D20 roll-result event being modified.
        source_entity_uuid: Guided entity UUID.

    Returns:
        Modified event when Guidance applies, otherwise `None`.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = roll_die_face(4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    modified_event = event.replace_roll(
        new_roll,
        "Guidance",
        f"+{d4_value} (1d4)",
    )

    target = Entity.get(source_entity_uuid)
    if target and "Guidance" in target.active_conditions:
        target.remove_condition("Guidance", parent_event=modified_event)

    return modified_event


class GuidanceEffect(BaseCondition):
    """Guidance spell effect that adds 1d4 to one skill check.

    One-use: the handler removes itself after firing once.
    """
    name: str = Field(default="Guidance", description="Condition name.")
    description: str = Field(default="Add 1d4 to one ability check", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Register the one-use d20 result handler.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Handler UUID ownership plus the effect event, or a canceled event
            when the target cannot be found.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Guidance",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CHECK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_guidance_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Guidance to {target.name}",
        )
        return [], [handler.uuid], [], [], effect_event


class Guidance(SpellAction):
    """Guidance - Divination Cantrip (Concentration)

    You touch one willing creature. Once before the spell ends, the target
    can roll a d4 and add the number rolled to one ability check of its choice.

    Duration: Concentration, up to 1 minute (10 rounds).
    """
    name: str = Field(default="Guidance", description="Spell name.")
    description: str = Field(default="Touch: +1d4 to one ability check (concentration)", description="Spell description.")
    spell_level: int = Field(default=0, description="Cantrip spell level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Guidance and link it to concentration.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if the caster is missing.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        if not target:
            target = caster

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Guidance on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        guidance_effect = GuidanceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        guidance_effect.duration.duration_type = DurationType.ROUNDS
        guidance_effect.duration.duration = 10
        effect_event = self.apply_owned_condition(effect_event, guidance_effect)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{target.name} gains Guidance"
        )


class HuntersMarkQuarry(BaseCondition):
    name: str = "Hunter's Mark"
    description: str = "This caster's weapon hits add 1d6 matching weapon damage."
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"Hunter's Mark:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Hunter's Mark"


@srd_action_identity(content_id="action.spell.hunters_mark.reapply",display_name="Reapply Hunter's Mark",
    description="Choose a new quarry after the previous quarry is defeated.",parent_spell_name="Hunter's Mark",source_page=156,sort_order=3000)
class ReapplyHuntersMark(ReapplyQuarry):
    name: str = "Reapply Hunter's Mark"
    description: str = "Choose a new quarry after the previous quarry is defeated."


class HuntersMarkEffect(QuarrySustain):
    name: str = "Hunter's Mark Sustain"
    description: str = "Retains the caster's mark and free reapplication until rest."

    def create_quarry_condition(self,target: Entity) -> BaseCondition:
        return HuntersMarkQuarry(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid)

    def _apply(self,event: Event):
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(self.quarry_uuid)
        if caster is None or target is None or not self.set_quarry(target,event):
            return [],[],[],[],event.cancel(status_message="Quarry cannot be marked")
        handler=install_hit_rider(self,dice_count=1,die_size=6,damage_type=None,weapon_only=True,quarry=lambda:self.quarry_uuid)
        action=ReapplyHuntersMark(source_entity_uuid=caster.uuid,sustain_uuid=self.uuid,template=True)
        caster.register_action(action)
        self.action_uuid=action.uuid
        return [],[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)


class HuntersMark(SpellAction):
    name: str = "Hunter's Mark"
    description: str = "Mark a quarry: weapon hits add 1d6 matching weapon damage; reapply after defeat."
    spell_level: int = 1
    spell_school: str = "divination"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=60))
    concentration: bool = True
    harmful: bool = True
    costs: list[Cost] = Field(default_factory=lambda:[Cost(name="Hunter's Mark",cost_type="bonus_actions",cost=1,
        evaluator=entity_action_economy_cost_evaluator)])

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent):
        if event.target_entity_uuid is None:
            return event.cancel(status_message="Quarry is absent")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),HuntersMarkEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.source_entity_uuid,quarry_uuid=event.target_entity_uuid))


class ForesightEffect(BaseCondition):
    name: str = "Foresight"
    description: str = "Advantage on attacks, checks and saves; incoming attacks have disadvantage; cannot be surprised."
    prevents_surprise: bool = True
    duration: Duration = Field(default_factory=lambda: Duration(duration=4800, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        caster = Entity.get(self.source_entity_uuid)
        if target is None or caster is None: return [], [], [], [], event.cancel(status_message="Foresight recipient absent")
        modifiers = []
        values = [target.equipment.attack_bonus]
        for ability in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            values.extend((target.ability_scores.get_ability(ability).check_bonus,
                target.saving_throws.get_saving_throw(ability).bonus))
        values.extend(target.skill_set.get_skill(skill).skill_bonus for skill in all_skills)
        for value in values:
            ident = value.self_static.add_advantage_modifier(AdvantageModifier(name=self.name,
                value=AdvantageStatus.ADVANTAGE, source_entity_uuid=target.uuid))
            modifiers.append((value.uuid, ident))
        value = target.equipment.ac_bonus
        ident = value.to_target_static.add_advantage_modifier(AdvantageModifier(name=self.name,
            value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=target.uuid))
        modifiers.append((value.uuid, ident))
        return modifiers, [], [], [], event.phase_to(EventPhase.EFFECT)


class ForesightOwner(BaseCondition):
    name: str = "Foresight Owner"
    description: str = "One same-caster Foresight lease, retained across target changes."
    recipient_uuid: UUID
    duration: Duration = Field(default_factory=lambda: Duration(duration=4800, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event: Event):
        target = Entity.get(self.recipient_uuid)
        if target is None: return [], [], [], [], event.cancel(status_message="Foresight recipient absent")
        child = ForesightEffect(name=f"Foresight:{self.source_entity_uuid}", source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid, parent_condition=self.uuid, effect_origin=self.effect_origin,
            duration=Duration(duration_type=DurationType.PERMANENT))
        result = target.add_condition(child, parent_event=event)
        if result is None or result.canceled: return [], [], [], [], event.cancel(status_message="Foresight was not admitted")
        self.add_linked_condition(target.uuid, child.uuid)
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)


class Foresight(SpellAction):
    name: str = "Foresight"
    description: str = "Touch a willing creature for eight hours of foresight; tactical Action casting adaptation."
    spell_level: int = 9
    spell_school: str = "divination"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self, actor, key="foresight", condition_type=ForesightEffect, beneficial=True)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent):
        if event.target_entity_uuid is None: return event.cancel(status_message="Recipient absent")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT), ForesightOwner(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid,
            recipient_uuid=event.target_entity_uuid))
