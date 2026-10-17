"""Enchantment spells - affecting minds and behavior.

Contains: HoldPerson, HoldPersonEffect, CharmPerson, TestBless, Sleep,
          Bane, BaneEffect, Bless, BlessEffect
"""
from dnd.core.spell_damage import roll_spell_damage, finalize_spell_damage_roll, resolve_saved_spell_damage
from dnd.spells.spell_utils import spell_condition_profile

from typing import Any, FrozenSet, Optional, List, Set, Tuple
from uuid import UUID
from dnd.core.base_block import BaseBlock, PreparedConditionRemovals
from dnd.blocks.skills import all_skills, SKILL_TO_ABILITY
from dnd.creature_transforms import apply_incapacitated_transform
from dnd.core.modifiers import NumericalModifier, ContextualAdvantageModifier
from dnd.core.values import ModifiableValue
from dnd.conditions import prepare_control_removals
from dnd.spells.hit_effects import QuarrySustain, ReapplyQuarry, install_hit_rider
from dnd.core.action_types import ActionSelection, ActionVariantFacet
from dnd.types.discovery import ActorScan
from dnd.core.base_actions import Cost
from dnd.actions import entity_action_economy_cost_evaluator
from dnd.types.abilities import AbilityName
from dnd.spells.content_metadata import srd_action_identity
from uuid import uuid4

from pydantic import Field, PrivateAttr

from dnd.core.base_actions import (
    ActionOutcomeProfile, DamageRollProfile,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import (
    BaseCondition, Duration,
)
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionRemovalTrigger,
    ConditionTag, DurationType,
)
from dnd.types.character_progression import OriginCapability
from dnd.core.events import (
    DamageAppliedEvent,
    ActionApplicationCommittedEvent,
    Event, EventPhase, RangeType, Range, EventType, EventHandler, Trigger,
    D20RollResultEvent, SavingThrowEvent,
)
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.core.aoe import AoEShape, Sphere, objective_footprint
from dnd.core.gridmap import get_map

from dnd.entity import Entity
from dnd.actions import Move, SpellAction, SpellEvent
from dnd.conditions import Paralyzed, Charmed, Stunned, Prone
from dnd.creature_transforms import (
    apply_turn_spent_transform,
    apply_unconscious_transform,
)
from dnd.spells.content_metadata import srd_spell_identity
from dnd.spells.spell_utils import target_turn_expiry_handler, deliver_spell_damage, condition_save
from dnd.spells.spell_utils import (living_recipients_error, seen_point_error, seen_recipients_error,
    selected_cast_level, target_count_error)

from dnd.core.events import Damage
from dnd.core.dice import AttackOutcome, roll_die_face


class CharmPersonEffect(BaseCondition):
    """One caster's finite spell owner and shared exact-charmer relationship."""
    name: str = "Charm Person"
    description: str = "Charmed by this caster; their or their allies' damage ends this ten-turn charm."
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.name = f"Charm Person:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Charm Person"

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Charm recipient absent")
        key = f"Charmed:{self.source_entity_uuid}"
        charmed = target.active_conditions.get(key)
        if charmed is None:
            charmed = Charmed(name=key, immunity_names=("Charmed",),
                source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid,
                parent_condition=self.uuid, tags={ConditionTag.MAGICAL})
            result = target.add_condition(charmed, parent_event=event)
            if result is None or result.canceled or not charmed.applied:
                return [], [], [], [], event.cancel(status_message="Charmed was not admitted")
        self.add_shared_subcondition(charmed)

        def damage_break(damaged: Event, _source_uuid: UUID) -> Event | None:
            if not isinstance(damaged, DamageAppliedEvent) or damaged.applied_damage <= 0:
                return None
            source = Entity.get(damaged.source_entity_uuid)
            charmer = Entity.get(self.source_entity_uuid)
            if charmer is not None and source is not None and (
                    source.uuid == charmer.uuid or charmer.is_ally(source)):
                target.remove_condition_by_uuid(self.uuid, parent_event=damaged)
            return None
        handler = EventHandler(name="Charm Person allied damage", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid)], event_processor=damage_break)
        target.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT, update={"condition": self})





class CharmPerson(SpellAction):
    """Charm one or more humanoids after Wisdom saves.

    Upcasting increases the target count, and targets that are fighting the
    caster receive advantage on the save.
    """
    harmful: Optional[bool] = Field(default=True, description="This spell imposes a harmful effect on its recipients.")
    name: str = Field(default="Charm Person", description="Spell name.")
    description: str = Field(
        default="WIS save or charmed. Advantage if fighting.",
        description="Rules-facing charm summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = Field(
        default=(SavingThrowEffectTag.CHARM,),
        description="Exact origin-rule semantics carried by Charm Person saves.",
    )
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    include_self: bool = Field(default=False, description="Whether action discovery includes the caster.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    max_targets: int = Field(default=1, description="Base target count before upcasting.")

    def get_num_targets(self) -> int:
        """Return the number of allowed targets after upcasting."""
        return 1 + max(0, self.cast_at_level - self.spell_level)

    def get_multi_target_count(self) -> Optional[int]:
        """Return the action discovery multi-target count."""
        return self.get_num_targets()

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to the slot limit."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:self.get_num_targets()]

    def _is_target_fighting_caster(self, target: Entity, caster: Entity) -> bool:
        """Return whether the target currently treats the caster as an enemy."""
        if caster.is_enemy(target):
            return caster.uuid in target.get_visible_enemies()
        return False

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Seen targets in range, a humanoid primary, at most the slot's targets, all within 30 feet of each other."""
        error = (seen_recipients_error(self, scan, selection.target_uuids) or target_count_error(
            self, selection, 1 + max(0, selected_cast_level(self, selection) - self.spell_level)))
        if error is not None:
            return error
        creature_type = scan.creatures[selection.target_uuids[0]].facts.creature_type
        if creature_type != CreatureType.HUMANOID:
            return f"Charm Person only affects humanoids, not {creature_type.value}"
        targets = [target for identity in selection.target_uuids if (target := Entity.get(identity)) is not None]
        for index, first in enumerate(targets):
            for second in targets[index + 1:]:
                distance = first.senses.get_feet_distance(second.position)
                if distance > 30:
                    return (f"Targets must be within 30ft of each other "
                            f"({first.name} and {second.name} are {distance}ft apart)")
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the Wisdom save and apply Charmed on failure."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        is_fighting = self._is_target_fighting_caster(target, caster)

        advantage_mod_uuid: Optional[UUID] = None
        if is_fighting:
            adv_mod = AdvantageModifier(
                name="Charm Person (Fighting)",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            advantage_mod_uuid = target.saving_throws.get_saving_throw("wisdom").bonus.self_static.add_advantage_modifier(adv_mod)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        if advantage_mod_uuid:
            target.saving_throws.get_saving_throw("wisdom").bonus.self_static.remove_modifier(advantage_mod_uuid)

        save_bonus = save_roll.bonus  # the bonus the save applied

        fighting_text = " (advantage: fighting)" if is_fighting else ""
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc}{fighting_text} - {'Success' if success else 'Failure'}"
        )

        if effect_event.canceled:
            return effect_event
        if success:
            return effect_event.with_updates(
                status_message=f"{self.name} - {target.name} resists the charm"
            )

        charmed = CharmPersonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, charmed)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{self.name} - {target.name} is charmed"
        )


class HoldPersonEffect(BaseCondition):
    """Apply Hold Person's spell-specific parent condition."""
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    name: str = Field(default="Hold Person", description="Condition name.")
    description: str = Field(default="Magically held in place", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the repeat-save DC.")
    spell_dc: int = Field(default=10, description="Wisdom save DC to end the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Paralyzed as a sub-condition and register repeat saves."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event

        existing = target.active_conditions.get("Paralyzed")
        if existing is not None:
            self.add_shared_subcondition(existing)
        else:
            paralyzed = Paralyzed(source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid, parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL})
            result = target.add_condition(paralyzed, parent_event=execution_event)
            if result is None or result.canceled or not paralyzed.applied:
                return [], [], [], [], declaration_event.cancel(status_message="Paralyzed was not admitted")
            self.add_shared_subcondition(paralyzed)

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Hold Person effect to {target.name}"
        )

        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create the end-of-turn Wisdom save handler."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid: UUID = self.target_entity_uuid
        caster_uuid: UUID = self.caster_uuid
        effect_uuid: UUID = self.uuid
        dc: int = self.spell_dc

        def repeat_save_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """Resolve the repeat Wisdom save for this condition instance."""
            _ = source_entity_uuid

            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            hold_person = target.active_conditions.get("Hold Person")
            if not hold_person or hold_person.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Hold Person", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Hold Person", parent_event=event)

            return None

        return EventHandler(
            name=f"Hold Person Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT
                , event_source_entity_uuid=target_uuid)
            ],
            event_processor=repeat_save_processor
        )


@srd_spell_identity(
    content_id="spell.hold_person",
    display_name="Hold Person",
    description="Paralyze a humanoid that fails its saving throw.",
    school="enchantment",
    level=2,
    source_page=154,
    sort_order=10,
)
class HoldPerson(SpellAction):
    """Paralyze a humanoid after a failed Wisdom save."""
    name: str = Field(default="Hold Person", description="Spell name.")
    description: str = Field(
        default="Target must succeed on WIS save or be paralyzed",
        description="Rules-facing hold summary.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single humanoid target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Hold Person's save-based paralysis branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.hold_person",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.hold_person.paralyze",
                    disposition=TargetEffectDisposition.HARMFUL,
                    included_creature_types=frozenset({CreatureType.HUMANOID.value}),
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=("selected_target.condition.paralyzed",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.enchantment.HoldPersonEffect",
                        "dnd.conditions.Paralyzed",
                    }),
                ),
            ),
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen humanoid within range."""
        error = self.single_recipient_error(scan, selection)
        if error is not None:
            return error
        creature_type = scan.creatures[selection.target_uuids[0]].facts.creature_type
        if creature_type != CreatureType.HUMANOID:
            return f"Hold Person only affects humanoids, not {creature_type.value}"
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and link a failed hold effect to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        effect_event, _, success = self.resolve_saving_throw(
            execution_event,
            caster=caster,
            target=target,
            ability_name="wisdom",
            dc=dc,
        )
        if effect_event.canceled:
            return effect_event

        if success:
            self.ensure_concentration(effect_event)
            return effect_event.with_updates(
                status_message=f"{self.name} - {target.name} saved"
            )

        hold_effect = HoldPersonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        effect_event = self.apply_owned_condition(effect_event, hold_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{self.name} - {target.name} is held (concentration)"
        )


class HoldMonsterEffect(BaseCondition):
    """Apply Hold Monster's spell-specific parent condition."""
    name: str = Field(default="Hold Monster", description="Condition name.")
    description: str = Field(default="Magically held in place", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the repeat-save DC.")
    spell_dc: int = Field(default=10, description="Wisdom save DC to end the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Paralyzed as a sub-condition and register repeat saves."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event

        existing = target.active_conditions.get("Paralyzed")
        if existing is not None:
            self.add_shared_subcondition(existing)
        else:
            paralyzed = Paralyzed(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL},
            )
            sub_event = target.add_condition(paralyzed, parent_event=execution_event)
            if sub_event is None or sub_event.canceled or sub_event.phase != EventPhase.COMPLETION:
                return [], [], [], [], declaration_event.cancel(status_message="Paralyzed was not applied")
            self.add_shared_subcondition(paralyzed)

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Hold Monster effect to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create the end-of-turn Wisdom save handler."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def repeat_save_processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            hold_monster = target.active_conditions.get("Hold Monster")
            if not hold_monster or hold_monster.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Hold Monster", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Hold Monster", parent_event=event)
            return None

        return EventHandler(
            name=f"Hold Monster Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT, event_source_entity_uuid=target_uuid)
            ],
            event_processor=repeat_save_processor
        )


class HoldMonster(SpellAction):
    """Paralyze one or more non-undead creatures after Wisdom saves."""
    name: str = Field(default="Hold Monster", description="Spell name.")
    description: str = Field(
        default="Target must succeed on WIS save or be paralyzed (not undead)",
        description="Rules-facing hold summary.",
    )
    spell_level: int = Field(default=5, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=90),
        description="Maximum range for each target.",
    )
    include_self: bool = Field(default=False, description="Whether action discovery includes the caster.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    max_targets: int = Field(default=1, description="Base target count before upcasting.")

    def get_max_targets_for_level(self) -> int:
        """Return the target count allowed by the slot level."""
        return 1 + max(0, self.cast_at_level - self.spell_level)

    def get_multi_target_count(self) -> Optional[int]:
        """Return the action discovery multi-target count."""
        return self.get_max_targets_for_level()

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to the slot limit."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:self.get_max_targets_for_level()]

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Hold Monster's save-based paralysis branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.hold_monster",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.hold_monster.paralyze",
                    disposition=TargetEffectDisposition.HARMFUL,
                    excluded_creature_types=frozenset({CreatureType.UNDEAD.value}),
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=("selected_target.condition.paralyzed",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.enchantment.HoldMonsterEffect",
                        "dnd.conditions.Paralyzed",
                    }),
                ),
            ),
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Admit the whole selected group before spending or applying any hold."""
        error = (target_count_error(self, selection, 1 + max(0, selected_cast_level(self, selection) - self.spell_level))
                 or seen_recipients_error(self, scan, selection.target_uuids))
        if error is not None:
            return error
        if any(scan.creatures[identity].facts.creature_type == CreatureType.UNDEAD for identity in selection.target_uuids):
            return "Hold Monster has no effect on undead"
        targets = [target for identity in selection.target_uuids if (target := Entity.get(identity)) is not None]
        if any(first.senses.get_feet_distance(second.position) > 30
               for index, first in enumerate(targets) for second in targets[index + 1:]):
            return "Targets must be within 30 feet of each other"
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and link a failed hold effect to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event, _, success = self.resolve_saving_throw(
            execution_event,
            caster=caster,
            target=target,
            ability_name="wisdom",
            dc=dc,
        )
        if effect_event.canceled:
            return effect_event

        if success:
            self.ensure_concentration(effect_event)
            return effect_event.with_updates(
                status_message=f"{self.name} - {target.name} saved"
            )

        hold_effect = HoldMonsterEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        effect_event = self.apply_owned_condition(effect_event, hold_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{self.name} - {target.name} is held"
        )


class PowerWordKill(SpellAction):
    """Kill a target whose current hit points are at or below the threshold."""
    name: str = Field(default="Power Word Kill", description="Spell name.")
    description: str = Field(
        default="If target has <=100 HP, it dies instantly. No save.",
        description="Rules-facing threshold summary.",
    )
    spell_level: int = Field(default=9, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    include_self: bool = Field(default=False, description="Whether action discovery includes the caster.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    hp_threshold: int = Field(default=100, description="Maximum current HP affected by the spell.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen creature within range."""
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply instant death when the target is below the HP threshold."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        current_hp = target.get_normal_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Power Word Kill targeting {target.name} ({current_hp} HP)"
        )

        if current_hp <= self.hp_threshold:
            instant_death_event = target.receive_instant_death(
                source_entity_uuid=caster.uuid,
                source_description=self.name,
                parent_event=effect_event.uuid
            )
            if instant_death_event.canceled:
                return effect_event.with_updates(
                    status_message=f"{target.name} is protected from {self.name}"
                )
            return effect_event.with_updates(
                status_message=f"{target.name} is slain by Power Word Kill!"
            )
        else:
            return effect_event.with_updates(
                status_message=f"Power Word Kill has no effect - {target.name} has {current_hp} HP (threshold: {self.hp_threshold})"
            )


class TestBless(SpellAction):
    """Test spell for multi-target self-or-ally targeting rules."""
    name: str = Field(default="Test Bless", description="Spell name.")
    description: str = Field(
        default="Bless up to 3 allies (each target only once)",
        description="Test-facing multi-target summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Action discovery target filter.")
    max_targets: int = Field(default=3, description="Maximum number of targets.")

    def get_multi_target_count(self) -> Optional[int]:
        """Return the fixed maximum number of targets."""
        return self.max_targets

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to max_targets."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:self.max_targets]

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """At most max_targets, each the caster or a seen creature within range."""
        others = [identity for identity in selection.target_uuids if identity != self.source_entity_uuid]
        return target_count_error(self, selection, self.max_targets) or (
            seen_recipients_error(self, scan, others) if others else None)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Complete the current target branch of the test spell."""
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not target:
            return execution_event.cancel(status_message="Target not found")

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{target.name} is blessed"
        )


class SleepEffect(BaseCondition):
    """Own Sleep's unconscious transform and wake-on-damage handler."""
    name: str = Field(default="Sleep", description="Condition name.")
    description: str = Field(default="Magically asleep", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    removal_triggers: frozenset[ConditionRemovalTrigger] = Field(
        default_factory=lambda: frozenset({
            ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED,
            ConditionRemovalTrigger.SHAKE_AWAKE,
        }),
        description="Positive damage or external assistance wakes this target.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Magical sleep removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the unconscious transform and register damage cleanup."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []
        outs = apply_unconscious_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )

        handler = self._create_wake_on_damage_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Sleep effect to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_wake_on_damage_handler(self) -> EventHandler:
        """Create the damage-triggered wake handler."""
        assert self.target_entity_uuid is not None

        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def wake_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            sleep_effect = target.active_conditions.get("Sleep")
            if not sleep_effect or sleep_effect.uuid != effect_uuid:
                return None

            target.remove_condition("Sleep", parent_event=event)
            return None

        return EventHandler(
            name=f"Sleep Wake Handler ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT, event_target_entity_uuid=target_uuid)
            ],
            event_processor=wake_processor
        )


class Sleep(SpellAction):
    """Select creatures in an HP pool and apply magical sleep."""
    name: str = Field(default="Sleep", description="Spell name.")
    description: str = Field(
        default="Roll 5d8 HP pool. Affects creatures in order of lowest HP.",
        description="Rules-facing HP-pool summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Position-centered area target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=90),
        description="Maximum range for the area origin.",
    )
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used for target selection.")
    include_self: bool = Field(default=False, description="Whether the caster can be selected by the HP pool.")
    valid_target_filter: str = Field(default="all", description="Action discovery target filter.")
    hp_pool_rolled: int = Field(
        default=0,
        description="Total hit point pool rolled for this Sleep spell instance.",
    )
    hp_pool_remaining: int = Field(
        default=0,
        description="Hit point pool remaining after this Sleep instance selects targets.",
    )
    _selected_hp_pool_targets: Optional[List[UUID]] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                radius_feet=20
            )

    def get_hp_pool_dice(self) -> Tuple[int, int]:
        """Return the HP-pool dice count and die size."""
        base_dice = 5
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 2
        return (base_dice + upcast_bonus, 8)

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Sleep's automatic agency-denial condition for selected targets."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="control.sleep",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.sleep",
                    disposition=TargetEffectDisposition.HARMFUL,
                    excluded_creature_types=frozenset({CreatureType.UNDEAD.value}),
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.sleep",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.enchantment.SleepEffect",
                    }),
                ),
            ),
        )

    def get_all_targets(self) -> List[UUID]:
        """Select targets by current HP and cache the selection."""
        if self._selected_hp_pool_targets is not None:
            return list(self._selected_hp_pool_targets)
        candidates = self._hp_pool_candidates()
        self._ensure_hp_pool()
        targets: List[UUID] = []
        remaining = self.hp_pool_remaining if self.hp_pool_remaining > 0 else self.hp_pool_rolled
        for hp, uid in candidates:
            if hp <= remaining:
                targets.append(uid)
                remaining -= hp

        self.hp_pool_remaining = remaining
        self._selected_hp_pool_targets = targets
        return list(targets)

    def _ensure_hp_pool(self) -> None:
        if self.hp_pool_rolled == 0:
            dice_count, dice_value = self.get_hp_pool_dice()
            total = sum(roll_die_face(dice_value) for _ in range(dice_count))
            self.hp_pool_rolled = total
            self.hp_pool_remaining = total

    def _apply_target_applications(self, execution_event: SpellEvent, effect_event: SpellEvent,
                                   target_uuids: List[UUID]) -> SpellEvent:
        """Spend the pool only on admitted applications; a vetoed creature costs nothing (Q3)."""
        del target_uuids
        self._ensure_hp_pool()
        remaining = self.hp_pool_rolled
        applied: List[UUID] = []
        for hp, uid in self._hp_pool_candidates():
            if hp > remaining:
                continue
            result = self._apply_target_application(execution_event, uid, parent_event=effect_event,
                application_index=len(applied))
            if result is None:
                continue
            remaining -= hp
            applied.append(uid)
        self.hp_pool_remaining = remaining
        self._selected_hp_pool_targets = applied
        return effect_event.with_updates(total_targets=len(applied), total_damage=0, aoe_position=self.end_position,
            status_message=f"{self.name} affected {len(applied)} targets")

    def _hp_pool_candidates(self) -> List[Tuple[int, UUID]]:
        """Eligible creatures in the area, lowest current HP first."""
        area = self._sleep_area()
        if area is None:
            return []
        grid = get_map()

        candidates: List[Tuple[int, UUID]] = []
        for uid in {identity for cell in area for identity in grid.get_entities_at(cell)}:
            if not self.include_self and uid == self.source_entity_uuid:
                continue

            entity = Entity.get(uid)
            if not entity or not entity.has_hp:
                continue

            if (
                entity.senses.visual_access.normalized_score == 0
                and entity.action_economy.action_permission.normalized_score == 0
            ):
                continue

            if entity.creature_type == CreatureType.UNDEAD:
                continue

            if entity.has_origin_capability(
                OriginCapability.MAGICAL_SLEEP_IMMUNITY,
            ):
                continue

            if entity.check_condition_immunity("Charmed"):
                continue

            candidates.append((entity.get_hp(), uid))

        candidates.sort(key=lambda x: (x[0], str(x[1])))
        return candidates

    def _sleep_area(self) -> Optional[FrozenSet[Tuple[int, int]]]:
        """Return the objective area the HP pool chooses its targets from."""
        caster = Entity.get(self.source_entity_uuid)
        if self.aoe_shape is None or self.end_position is None or caster is None:
            return None
        return objective_footprint(self.aoe_shape, self.end_position, caster.position)

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        """Record the same area used by the HP-pool selection for replay."""
        targets = self.get_all_targets()
        area = self._sleep_area()
        return targets, tuple(sorted(area)) if area is not None else None

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen area origin within range."""
        return seen_point_error(self, scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Sleep effect to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Sleep affecting {target.name} ({target.get_hp()} HP)"
        )
        if effect_event.canceled:
            return effect_event

        sleep_effect = SleepEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, sleep_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{target.name} falls asleep ({target.get_hp()} HP)"
        )


class PowerWordStunEffect(BaseCondition):
    """Apply Power Word Stun's condition tree and repeat save."""
    name: str = Field(default="Power Word Stun", description="Condition name.")
    description: str = Field(default="Stunned by power word", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the repeat-save DC.")
    spell_dc: int = Field(default=10, description="Constitution save DC to end the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Stunned as a sub-condition and register repeat saves."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        existing = target.active_conditions.get("Stunned")
        if existing is not None:
            self.add_shared_subcondition(existing)
        else:
            stunned = Stunned(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL},
            )
            sub_event = target.add_condition(stunned, parent_event=declaration_event)
            if sub_event is None or sub_event.canceled or sub_event.phase != EventPhase.COMPLETION:
                return [], [], [], [], declaration_event.cancel(status_message="Stunned was not applied")
            self.add_shared_subcondition(stunned)

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Power Word Stun to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create the end-of-turn Constitution save handler."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def repeat_save_processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            pw_stun = target.active_conditions.get("Power Word Stun")
            if not pw_stun or pw_stun.uuid != effect_uuid:
                return None

            save_request = SavingThrowEvent(
                source_entity_uuid=caster_uuid,
                target_entity_uuid=target.uuid,
                target_entity_name=target.name,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid,
                condition_context="Stunned",
                saving_throw_context=SavingThrowContext(
                    cause_id="spell.power_word_stun",
                    effect_id="spell.power_word_stun.repeat_save",
                    condition_id="condition.stunned",
                    is_magical=True,
                ),
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Power Word Stun", parent_event=event)
            return None

        return EventHandler(
            name=f"Power Word Stun Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT, event_source_entity_uuid=target_uuid)
            ],
            event_processor=repeat_save_processor
        )


class PowerWordStun(SpellAction):
    """Stun a target whose current hit points are at or below the threshold."""
    harmful: Optional[bool] = Field(default=True, description="This spell imposes a harmful effect on its recipients.")
    name: str = Field(default="Power Word Stun", description="Spell name.")
    description: str = Field(
        default="If target has <=150 HP, it is stunned. CON save each turn to end.",
        description="Rules-facing threshold summary.",
    )
    spell_level: int = Field(default=8, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    hp_threshold: int = Field(default=150, description="Maximum current HP affected by the spell.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen creature within range."""
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stunned when the target is below the HP threshold."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        current_hp = target.get_normal_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Power Word Stun targeting {target.name} ({current_hp} HP)"
        )
        if effect_event.canceled:
            return effect_event

        if current_hp <= self.hp_threshold:
            dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

            stun_effect = PowerWordStunEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc
            )
            target.add_condition(stun_effect, parent_event=effect_event)

            return effect_event.with_updates(
                status_message=f"{target.name} is stunned by Power Word Stun!"
            )
        else:
            return effect_event.with_updates(
                status_message=f"Power Word Stun has no effect - {target.name} has {current_hp} HP (threshold: {self.hp_threshold})"
            )


def _bane_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Subtract 1d4 from d20 roll (attack or save)."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = roll_die_face(4)
    effective = event.get_effective_roll()
    new_total = effective.total - d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    return event.replace_roll(new_roll, "Bane", f"-{d4_value} (1d4)")


def _bless_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to d20 roll (attack or save)."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = roll_die_face(4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    return event.replace_roll(new_roll, "Bless", f"+{d4_value} (1d4)")


class BaneEffect(BaseCondition):
    """Register Bane's d20 roll-result handler."""
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    name: str = Field(default="Bane", description="Condition name.")
    description: str = Field(
        default="Subtract 1d4 from attack rolls and saving throws",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Register the attack/save d20 subtraction handler."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Bane",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_bane_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Bane to {target.name}",
        )
        return [], [handler.uuid], [], [], effect_event


class BlessEffect(BaseCondition):
    """Register Bless's d20 roll-result handler."""
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    name: str = Field(default="Bless", description="Condition name.")
    description: str = Field(
        default="Add 1d4 to attack rolls and saving throws",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Register the attack/save d20 addition handler."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Bless",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_bless_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Bless to {target.name}",
        )
        return [], [handler.uuid], [], [], effect_event


class Bane(SpellAction):
    """Apply Bane to failed Charisma saves across multiple targets."""
    name: str = Field(default="Bane", description="Spell name.")
    description: str = Field(
        default="Up to 3 enemies: CHA save or -1d4 on attacks and saves",
        description="Rules-facing d20 penalty summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Bane's failed-save d20 penalty branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.bane",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.bane.penalty",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="charisma",
                    condition_fact_ids=("selected_target.condition.bane",),
                    condition_semantic_keys=frozenset({"dnd.spells.enchantment.BaneEffect"}),
                ),
            ),
        )

    def get_multi_target_count(self) -> Optional[int]:
        """Return the number of targets allowed by the slot level."""
        return 3 + self.get_upcast_bonus()

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to the slot limit."""
        max_targets = 3 + self.get_upcast_bonus()
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:max_targets]

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """At most three creatures, plus one per slot level above 1st."""
        return target_count_error(self, selection, 3 + max(0, selected_cast_level(self, selection) - self.spell_level))

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the Charisma save and apply Bane on failure."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="charisma",
            dc=dc,
            parent_event=execution_event.uuid,
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="charisma",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"CHA save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}",
        )
        if effect_event.canceled:
            return effect_event

        if success:
            self.ensure_concentration(effect_event)
            return effect_event.with_updates(
                status_message=f"Bane - {target.name} resists",
            )

        bane_effect = BaneEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        effect_event = self.apply_owned_condition(effect_event, bane_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"Bane - {target.name} is baned",
        )


class Bless(SpellAction):
    """Apply Bless across multiple allies without a saving throw."""
    name: str = Field(default="Bless", description="Spell name.")
    description: str = Field(
        default="Up to 3 allies: +1d4 on attacks and saves",
        description="Rules-facing d20 bonus summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Action discovery target filter.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Bless's automatic d20 support branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        _ = actor
        return ActionTargetEffectProfile(
            semantic_id="support.bless",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.bless.bonus",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.bless",),
                    condition_semantic_keys=frozenset({"dnd.spells.enchantment.BlessEffect"}),
                ),
            ),
        )

    def get_multi_target_count(self) -> Optional[int]:
        """Return the number of targets allowed by the slot level."""
        return 3 + self.get_upcast_bonus()

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to the slot limit."""
        max_targets = 3 + self.get_upcast_bonus()
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:max_targets]

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """At most three creatures, plus one per slot level above 1st."""
        return target_count_error(self, selection, 3 + max(0, selected_cast_level(self, selection) - self.spell_level))

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Bless to the current target in the convolution loop."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Bless - {target.name} is blessed",
        )
        if effect_event.canceled:
            return effect_event

        bless_effect = BlessEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        effect_event = self.apply_owned_condition(effect_event, bless_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"Bless - {target.name} is blessed",
        )


class CommandNextTurnEffect(BaseCondition):
    """Own one Command branch from application through its commanded turn."""

    name: str = Field(default="Command", description="Condition name.")
    description: str = Field(
        default=(
            "Must follow the named command on its next turn and spend that turn "
            "as specified by the command."
        ),
        description="Rules-facing summary for a pending Command effect.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="The target's next commanded turn is fully spent.",
    )
    _commanded_turn_started: bool = PrivateAttr(default=False)

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        """Register exact next-turn activation and turn-end cleanup handlers."""
        target = self._target_if_active()
        if target is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        turn_start_handler = self._create_turn_start_handler()
        turn_end_handler = self._create_turn_end_handler()
        target.add_event_handler(turn_start_handler)
        target.add_event_handler(turn_end_handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=self._application_status(target),
        )
        return (
            [],
            [turn_start_handler.uuid, turn_end_handler.uuid],
            [],
            [],
            effect_event,
        )

    def _target_if_active(self) -> Optional[Entity]:
        """Resolve the exact target while this condition remains authoritative."""
        if self.target_entity_uuid is None:
            return None
        target = Entity.get(self.target_entity_uuid)
        if not isinstance(target, Entity):
            return None
        command_name = self._canonical_name()
        active = target.active_conditions.get(command_name)
        if self.applied and (active is None or active.uuid != self.uuid):
            return None
        return target

    def _canonical_name(self) -> str:
        """Return the required stable key used to own this command branch."""
        command_name = self.name
        if command_name is None:
            raise ValueError(
                f"{type(self).__name__} requires a canonical condition name"
            )
        return command_name

    def _create_turn_start_handler(self) -> EventHandler:
        """Create the one-shot next-turn branch activator."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        condition_uuid = self.uuid
        command_name = self._canonical_name()

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if (
                event.source_entity_uuid != target_uuid
                or self._commanded_turn_started
            ):
                return None

            target = Entity.get(target_uuid)
            if not isinstance(target, Entity):
                return None
            active = target.active_conditions.get(command_name)
            if active is None or active.uuid != condition_uuid:
                return None

            self._commanded_turn_started = True
            if self.contributions_active():
                self._activate_commanded_turn(event, target)
            return None

        return EventHandler(
            name=f"{command_name} Turn Start ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid,
                )
            ],

            event_processor=processor,
        )

    def _create_turn_end_handler(self) -> EventHandler:
        """Remove this branch only after the commanded turn has completed."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        condition_uuid = self.uuid
        command_name = self._canonical_name()

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if (
                event.source_entity_uuid != target_uuid
                or not self._commanded_turn_started
            ):
                return None

            target = Entity.get(target_uuid)
            if not isinstance(target, Entity):
                return None
            active = target.active_conditions.get(command_name)
            if active is None or active.uuid != condition_uuid:
                return None

            target.remove_condition_by_uuid(condition_uuid, parent_event=event)
            return None

        return EventHandler(
            name=f"{command_name} Turn End ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid,
                )
            ],

            event_processor=processor,
        )

    def _spend_commanded_turn(self, target: Entity) -> None:
        """Install and record this condition's reaction-preserving turn caps."""
        command_name = self._canonical_name()
        ownership = apply_turn_spent_transform(
            target,
            name=command_name,
            effect_source_uuid=self.source_entity_uuid,
        )
        for value_uuid, modifier_uuid in ownership:
            self.modifers_uuids.setdefault(value_uuid, []).append(modifier_uuid)

    def _activate_commanded_turn(self, event: Event, target: Entity) -> None:
        """Apply branch-specific behavior at the target's next turn start."""
        _ = event
        self._spend_commanded_turn(target)

    def _application_status(self, target: Entity) -> str:
        """Describe the pending next-turn command."""
        return f"{target.name} is commanded"


class CommandGrovelEffect(CommandNextTurnEffect):
    """Make the target fall prone and spend its next turn."""
    name: str = Field(default="Command: Grovel", description="Condition name.")
    description: str = Field(default="Commanded to grovel - falls prone", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )

    def _activate_commanded_turn(self, event: Event, target: Entity) -> None:
        """Apply an independent Prone condition after normal auto-stand timing."""
        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )
        prone.suppress_immediate_stand_for_application()
        target.add_condition(prone, parent_event=event)
        self._spend_commanded_turn(target)

    def _application_status(self, target: Entity) -> str:
        """Describe the pending grovel command."""
        return f"{target.name} is commanded to grovel"


class CommandHaltEffect(CommandNextTurnEffect):
    """Spend the target's next turn without suppressing reactions."""
    name: str = Field(default="Command: Halt", description="Condition name.")
    description: str = Field(
        default="Commanded to halt - can take no actions",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )

    def _application_status(self, target: Entity) -> str:
        """Describe the pending halt command."""
        return f"{target.name} is commanded to halt"


class CommandFleeEffect(CommandNextTurnEffect):
    """Move away voluntarily and spend the rest of the target's next turn."""
    name: str = Field(default="Command: Flee", description="Condition name.")
    description: str = Field(
        default="Commanded to flee - must move away from caster",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster the target must flee from.")

    def _activate_commanded_turn(self, event: Event, target: Entity) -> None:
        """Use ordinary voluntary movement before closing the remaining turn."""
        caster_uuid = self.caster_uuid or self.source_entity_uuid
        caster = Entity.get(caster_uuid)
        if isinstance(caster, Entity):
            path_distance = max(
                0,
                (target.action_economy.movement_remaining() + 4) // 5,
            )
            target.materialize_navigation(
                max_distance=20,
                path_max_distance=path_distance,
            )
            caster_pos = caster.position
            original_distance = (
                abs(target.position[0] - caster_pos[0])
                + abs(target.position[1] - caster_pos[1])
            )
            farther_positions = [
                position
                for position, path in target.senses.paths.items()
                if (
                    len(path) > 1
                    and (
                        abs(position[0] - caster_pos[0])
                        + abs(position[1] - caster_pos[1])
                    )
                    > original_distance
                )
            ]
            if farther_positions:
                best_position = max(
                    farther_positions,
                    key=lambda position: (
                        abs(position[0] - caster_pos[0])
                        + abs(position[1] - caster_pos[1]),
                        position[0],
                        position[1],
                    ),
                )
                path = list(target.senses.paths[best_position])
                Move(
                    source_entity_uuid=target.uuid,
                    end_position=best_position,
                    path=path,
                ).apply(parent_event=event)

        self._spend_commanded_turn(target)

    def _application_status(self, target: Entity) -> str:
        """Describe the pending flee command."""
        return f"{target.name} is commanded to flee"


class Command(SpellAction):
    """Force a creature to follow a one-word command after a failed save."""
    name: str = Field(default="Command", description="Spell name.")
    description: str = Field(
        default="WIS save or follow a one-word command (Grovel/Flee/Halt)",
        description="Rules-facing command summary.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="enchantment", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    command_word: str = Field(default="grovel", description="Command word: grovel, flee, or halt.")

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare the save-based condition applied by the selected command."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        word = self.command_word.lower()
        condition_fact, condition_keys = {
            "halt": (
                "selected_target.condition.command_halt",
                frozenset({"dnd.spells.enchantment.CommandHaltEffect"}),
            ),
            "flee": (
                "selected_target.condition.command_flee",
                frozenset({"dnd.spells.enchantment.CommandFleeEffect"}),
            ),
        }.get(
            word,
            (
                "selected_target.condition.command_grovel",
                frozenset({"dnd.spells.enchantment.CommandGrovelEffect", "dnd.conditions.Prone"}),
            ),
        )
        return ActionTargetEffectProfile(
            semantic_id=f"control.command.{word}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"control.command.{word}",
                    disposition=TargetEffectDisposition.HARMFUL,
                    excluded_creature_types=frozenset({CreatureType.UNDEAD.value}),
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=(condition_fact,),
                    condition_semantic_keys=condition_keys,
                ),
            ),
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen creature within range that is not undead."""
        error = self.single_recipient_error(scan, selection)
        if error is not None:
            return error
        if scan.creatures[selection.target_uuids[0]].facts.creature_type == CreatureType.UNDEAD:
            return "Command has no effect on undead"
        return None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and apply the selected command effect."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        if target.creature_type == CreatureType.UNDEAD:
            return execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                status_message=f"Command has no effect on undead {target.name}"
            )

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom", save_dc=dc,
            save_success=success, save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc}"
        )

        if success:
            return effect_event.with_updates(
                status_message=f"{target.name} resists Command"
            )

        word = self.command_word.lower()
        if word == "grovel":
            effect = CommandGrovelEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(effect, parent_event=effect_event)
        elif word == "halt":
            effect = CommandHaltEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(effect, parent_event=effect_event)
        elif word == "flee":
            flee_effect = CommandFleeEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid
            )
            target.add_condition(flee_effect, parent_event=effect_event)

        return effect_event.with_updates(
            status_message=f"{target.name} is commanded to {self.command_word}"
        )


class MockedEffect(BaseCondition):
    """Spend disadvantage only when this recipient actually rolls an attack."""
    name: str = "Vicious Mockery"
    description: str = "Disadvantage on the next actual attack roll."
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.PERMANENT))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Recipient no longer exists")
        value = target.equipment.attack_bonus
        modifier = value.self_static.add_advantage_modifier(AdvantageModifier(name=self.name,
            value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
        def consume(rolled: Event, _: UUID) -> Optional[Event]:
            target.remove_condition_by_uuid(self.uuid,parent_event=rolled)
            return None
        handler = EventHandler(name="Consume Mockery after attack roll",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK_D20_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,event_source_entity_uuid=target.uuid)],event_processor=consume)
        target.add_event_handler(handler)
        expiry=target_turn_expiry_handler(self,turn_ends=1)
        target.add_event_handler(expiry)
        return [(value.uuid,modifier)],[handler.uuid,expiry.uuid],[],[],event.phase_to(EventPhase.EFFECT)


class ViciousMockery(SpellAction):
    name: str = "Vicious Mockery"
    description: str = "WIS save or psychic damage and disadvantage on the next attack."
    spell_level: int = 0
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE,normal=60))
    target_type: TargetType = TargetType.ENTITY
    spell_damage_type: DamageType = DamageType.PSYCHIC

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="vicious_mockery",condition_type=MockedEffect,beneficial=False,
            save_ability='wisdom',fact=None,)

    def get_outcome_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return self.saving_throw_damage_outcome_profile(actor,dice_count=self._get_cantrip_dice_count(self.caster_level),die_size=4,damage_type=DamageType.PSYCHIC,save_ability="wisdom",half_damage_on_save=False)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None:
            return event.cancel(status_message="Caster or recipient no longer exists")
        effect,_,saved=self.resolve_saving_throw(event,caster=caster,target=target,ability_name="wisdom",
            dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id))
        if effect.canceled:
            return effect
        damage=Damage(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,damage_dice=4,
            dice_numbers=self._get_cantrip_dice_count(self.caster_level),damage_bonus=caster.get_spell_damage_bonus(),
            damage_type=DamageType.PSYCHIC)
        packet=resolve_saved_spell_damage(damage, parent_event=effect, saved=saved, success_fraction=0)
        roll=packet.final_roll
        effect=deliver_spell_damage(effect,target,damage,roll,amount=packet.applied_amount)
        if effect.canceled or saved:
            return effect
        target.add_condition(MockedEffect(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid),parent_event=effect)
        return effect


class AnimalFriendshipEffect(Charmed):
    """A separate beast charm, broken by damage from the caster's original allies."""
    name: str = "Animal Friendship"
    immunity_names: tuple[str,...] = ("Charmed",)
    caster_faction: Optional[str] = None
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda: Duration(duration=10,duration_type=DurationType.ROUNDS))

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"{self.get_display_name()}:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Animal Friendship"

    def _apply(self,event: Event):
        modifiers,handlers,children,spatial,effect=super()._apply(event)
        if effect is None or effect.canceled:
            return modifiers,handlers,children,spatial,effect
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        assert target is not None
        def broken_by_damage(damaged: Event, _: UUID) -> Optional[Event]:
            source=Entity.get(damaged.source_entity_uuid)
            if source is not None and (source.uuid==self.source_entity_uuid or
                    (self.caster_faction is not None and source.faction==self.caster_faction)):
                target.remove_condition_by_uuid(self.uuid,parent_event=damaged)
            return None
        handler=EventHandler(name="Animal Friendship allied damage",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.DAMAGE_APPLIED,event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid)],event_processor=broken_by_damage)
        target.add_event_handler(handler)
        return modifiers,[*handlers,handler.uuid],children,spatial,effect


class AnimalFriendship(SpellAction):
    name: str = "Animal Friendship"
    description: str = "Charm a beast of Intelligence 3 or less; caster-allied damage ends the charm."
    spell_level: int = 1
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE,normal=60))
    target_type: TargetType = TargetType.MULTI_ENTITY
    harmful: bool = True
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag,...] = (SavingThrowEffectTag.CHARM,)
    max_targets: int = 1
    include_self: bool = False
    allow_same_target: bool = False

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="animal_friendship",condition_type=AnimalFriendshipEffect,beneficial=False,
            save_ability='wisdom',fact=None,included=frozenset({CreatureType.BEAST.value}),)

    def get_multi_target_count(self) -> Optional[int]:
        return max(1,self.cast_at_level)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        for identity in selection.target_uuids:
            target=Entity.get(identity)
            if target is None or target.creature_type is not CreatureType.BEAST or target.ability_scores.intelligence.ability_score.score>3:
                return "Only beasts with Intelligence 3 or less are eligible"
        return None

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None:
            return event.cancel(status_message="Caster or beast no longer exists")
        effect,_,saved=self.resolve_saving_throw(event,caster=caster,target=target,ability_name="wisdom",
            dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id))
        if not saved and not effect.canceled:
            return self.apply_owned_condition(effect,AnimalFriendshipEffect(source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,caster_faction=caster.faction))
        return effect


class DissonantFearEffect(BaseCondition):
    turn_ends: int | None = 2
    name: str = "Dissonant Whispers Fear"
    description: str = "Cannot move; attacks and ability checks have disadvantage even outside the caster's sight."
    immunity_names: tuple[str,...] = ("Frightened",)
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.PERMANENT))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Fear recipient no longer exists")
        modifiers=[]
        for value in (target.equipment.attack_bonus,
                      *(target.ability_scores.get_ability(ability).check_bonus for ability in ("strength","dexterity","constitution","intelligence","wisdom","charisma")),
                      *(target.skill_set.get_skill(skill).skill_bonus for skill in all_skills)):
            ident=value.self_static.add_advantage_modifier(AdvantageModifier(name=self.name,
                value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
            modifiers.append((value.uuid,ident))
        for value in target.action_economy.speed_values:
            ident=value.self_static.add_max_constraint(NumericalModifier(name=self.name,value=0,
                source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
            modifiers.append((value.uuid,ident))
        handlers=[]
        if self.turn_ends is not None:
            expiry=target_turn_expiry_handler(self,turn_ends=self.turn_ends)
            target.add_event_handler(expiry)
            handlers.append(expiry.uuid)
        return modifiers,handlers,[],[],event.phase_to(EventPhase.EFFECT)


class DissonantWhispers(SpellAction):
    name: str = "Dissonant Whispers"
    description: str = "WIS save for half psychic damage; failure gives two-turn fear."
    spell_level: int = 1
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE,normal=60))
    target_type: TargetType = TargetType.ENTITY
    spell_damage_type: DamageType = DamageType.PSYCHIC
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag,...] = (SavingThrowEffectTag.FEAR,)

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="dissonant_whispers",condition_type=DissonantFearEffect,beneficial=False,
            save_ability='wisdom',fact='selected_target.condition.frightened',)

    def get_outcome_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return self.saving_throw_damage_outcome_profile(actor,dice_count=3+self.get_upcast_bonus(),die_size=6,damage_type=DamageType.PSYCHIC,save_ability="wisdom",half_damage_on_save=True)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None:
            return event.cancel(status_message="Caster or recipient no longer exists")
        effect,_,saved=self.resolve_saving_throw(event,caster=caster,target=target,ability_name="wisdom",
            dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id))
        if effect.canceled:
            return effect
        damage=Damage(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,damage_dice=6,
            dice_numbers=3+max(0,self.cast_at_level-1),damage_bonus=caster.get_spell_damage_bonus(),damage_type=DamageType.PSYCHIC)
        roll=roll_spell_damage(damage, parent_event=event, effect_origin=self.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
        effect=deliver_spell_damage(effect,target,damage,roll,amount=roll.total//2 if saved else roll.total)
        if effect.canceled:
            return effect
        if not saved and target.is_active:
            target.add_condition(DissonantFearEffect(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid),parent_event=effect)
        return effect


class HideousLaughterEffect(BaseCondition):
    name: str = "Hideous Laughter"
    description: str = "Prone and unable to act; WIS saves at turn end and with advantage after damage."
    immunity_names: tuple[str,...] = ("Prone",)
    spell_dc: int = 10
    agency_denial: ConditionAgencyDenial = ConditionAgencyDenial.FULL_TURN
    duration: Duration = Field(default_factory=lambda: Duration(duration=10,duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Laughter recipient no longer exists")
        modifiers=apply_incapacitated_transform(target,name=self.name,effect_source_uuid=self.source_entity_uuid)
        def incoming_advantage(source_uuid: UUID,attacker_uuid: UUID | None=None,context: dict | None=None):
            attacker=Entity.get(attacker_uuid) if attacker_uuid else None
            if attacker is None or target.senses.get_feet_distance(attacker.position)>10:
                return None
            return AdvantageModifier(name=self.name,value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=source_uuid,target_entity_uuid=attacker_uuid)
        value=target.equipment.ac_bonus
        ident=value.to_target_contextual.add_advantage_modifier(ContextualAdvantageModifier(
            name=self.name,source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid,
            callable=incoming_advantage))
        modifiers.append((value.uuid,ident))
        for ability in ("strength","dexterity"):
            value=target.saving_throws.get_saving_throw(ability).bonus
            ident=value.self_static.add_advantage_modifier(AdvantageModifier(name=self.name,
                value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
            modifiers.append((value.uuid,ident))
        def repeat(boundary: Event,_: UUID) -> Optional[Event]:
            caster=Entity.get(self.source_entity_uuid)
            if caster is None:
                target.remove_condition_by_uuid(self.uuid,parent_event=boundary)
                return None
            bonus=target.saving_throws.get_saving_throw("wisdom").bonus
            ident=None
            if boundary.event_type is EventType.DAMAGE_APPLIED:
                ident=bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Laughter damage save",
                    value=AdvantageStatus.ADVANTAGE,source_entity_uuid=target.uuid,target_entity_uuid=caster.uuid))
            try:
                request=caster.create_saving_throw_request(target_entity_uuid=target.uuid,ability_name="wisdom",
                    dc=self.spell_dc,parent_event=boundary.uuid,
                    saving_throw_context=self.saving_throw_context(effect_id="spell.hideous_laughter.repeat"))
                _outcome,_roll,saved=target.saving_throw(request)
            finally:
                if ident is not None: bonus.self_static.remove_modifier(ident)
            if saved: target.remove_condition_by_uuid(self.uuid,parent_event=boundary)
            return None
        handler=EventHandler(name="Laughter recovery",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END,event_phase=EventPhase.EFFECT,event_source_entity_uuid=target.uuid),
                Trigger(event_type=EventType.DAMAGE_APPLIED,event_phase=EventPhase.EFFECT,event_target_entity_uuid=target.uuid)],event_processor=repeat)
        target.add_event_handler(handler)
        return modifiers,[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)


class HideousLaughter(SpellAction):
    name: str = "Hideous Laughter"
    description: str = "WIS save or persistent prone and inability to act; requires Intelligence 5+."
    spell_level: int = 1
    spell_school: str = "enchantment"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE,normal=60))
    concentration: bool = True
    harmful: bool = True

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="hideous_laughter",condition_type=HideousLaughterEffect,beneficial=False,
            save_ability='wisdom',fact='selected_target.condition.incapacitated',)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        target=Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is None or target.ability_scores.intelligence.ability_score.score<5:
            return "Target needs Intelligence 5 or greater"
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None:
            return event.cancel(status_message="Caster or recipient no longer exists")
        dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        effect,_,saved=self.resolve_saving_throw(event,caster=caster,target=target,ability_name="wisdom",dc=dc)
        if saved or effect.canceled:
            return effect
        return self.apply_owned_condition(effect,HideousLaughterEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,spell_dc=dc))


class HeroismEffect(BaseCondition):
    name: str = "Heroism"
    description: str = "Fear immunity and five source-owned temporary HP refreshed each turn."
    duration: Duration = Field(default_factory=lambda: Duration(duration=10,duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    _purge: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Heroism recipient no longer exists")
        self._purge=prepare_control_removals(target,frozenset({"Frightened"}),event)
        if self._purge is None:
            return [],[],[],[],event.cancel(status_message="Existing fear removal was rejected")
        target.add_condition_immunity_source("Frightened",self.uuid)
        def refresh(boundary: Event,_: UUID) -> Optional[Event]:
            self._grant(target,boundary)
            return None
        handler=EventHandler(name="Heroism refresh",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_START,event_phase=EventPhase.EFFECT,event_source_entity_uuid=target.uuid)],event_processor=refresh)
        target.add_event_handler(handler)
        return [],[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)

    def _grant(self,target: Entity,event: Event) -> None:
        target.health.add_temporary_hit_points(5,self.source_entity_uuid,parent_event=event.uuid,source_id=f"condition.heroism.{self.uuid}")

    def _commit_application(self,event: Event) -> None:
        if self._purge is not None: BaseBlock.commit_owned_condition_removals(self._purge)
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None: self._grant(target,event)

    def publish_prepared_application(self) -> None:
        if self._purge is not None and self._purge.committed_result is not None:
            BaseBlock.publish_owned_condition_removals(self._purge)

    def _release_owned_runtime_state(self,*,parent_event: Event | None = None) -> None:
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self._purge is not None and self._purge.committed_result is None:
            BaseBlock.cancel_owned_condition_removals(self._purge,"Heroism was not committed")
        if target is not None:
            target.remove_condition_immunity_source("Frightened",self.uuid)
            grant=target.health.temporary_hit_points_grant
            if grant is not None and grant.source_id==f"condition.heroism.{self.uuid}":
                target.health.clear_temporary_hit_points(parent_event=parent_event.uuid if parent_event else None)
        super()._release_owned_runtime_state(parent_event=parent_event)


class Heroism(SpellAction):
    name: str = "Heroism"
    description: str = "Clear and prevent fear; refresh five temporary HP each turn."
    spell_level: int = 1
    spell_school: str = "enchantment"
    target_type: TargetType = TargetType.MULTI_ENTITY
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH,normal=5))
    valid_target_filter: str = "self_or_allies"
    include_self: bool = True
    concentration: bool = True
    harmful: bool = False

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="heroism",condition_type=HeroismEffect,beneficial=True,
            save_ability=None,fact=None,)

    def get_multi_target_count(self) -> Optional[int]:
        return max(1,self.cast_at_level)

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),HeroismEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=event.target_entity_uuid))


class CalmedEffect(BaseCondition):
    name: str = "Calm Emotions"
    description: str = "Clear and prevent charm, fear and native rage effects."
    duration: Duration = Field(default_factory=lambda: Duration(duration=10,duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    _purge: PreparedConditionRemovals | None = PrivateAttr(default=None)

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Calm recipient no longer exists")
        self._purge=prepare_control_removals(target,frozenset({"Charmed","Frightened","Raging","Frenzied"}),event)
        if self._purge is None:
            return [],[],[],[],event.cancel(status_message="Existing control removal was rejected")
        for name in ("Charmed","Frightened","Raging","Frenzied"):
            target.add_condition_immunity_source(name,self.uuid)
        return [],[],[],[],event.phase_to(EventPhase.EFFECT)

    def _commit_application(self,event: Event) -> None:
        if self._purge is not None: BaseBlock.commit_owned_condition_removals(self._purge)

    def publish_prepared_application(self) -> None:
        if self._purge is not None and self._purge.committed_result is not None:
            BaseBlock.publish_owned_condition_removals(self._purge)

    def _release_owned_runtime_state(self,*,parent_event: Event | None = None) -> None:
        if self._purge is not None and self._purge.committed_result is None:
            BaseBlock.cancel_owned_condition_removals(self._purge,"Calm was not committed")
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            for name in ("Charmed","Frightened","Raging","Frenzied"):
                target.remove_condition_immunity_source(name,self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)


class CalmEmotions(SpellAction):
    name: str = "Calm Emotions"
    description: str = "Humanoids in the area lose charm, fear and rage and cannot regain them."
    spell_level: int = 2
    spell_school: str = "enchantment"
    target_type: TargetType = TargetType.POSITION_AOE
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE,normal=60))
    valid_target_filter: str = "all"
    include_self: bool = True
    concentration: bool = True
    harmful: bool = False

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="calm_emotions",condition_type=CalmedEffect,beneficial=True,
            save_ability=None,fact=None,included=frozenset({CreatureType.HUMANOID.value}),)

    def model_post_init(self,context: Any) -> None:
        super().model_post_init(context)
        if self.aoe_shape is None:
            self.aoe_shape=Sphere(radius_feet=20)

    def _resolve_execution_targets(self):
        return self._resolve_area_targets() if self.effective_target_type is TargetType.POSITION_AOE else super()._resolve_execution_targets()

    def _apply(self,event: SpellEvent) -> Optional[SpellEvent]:
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        effect=event.phase_to(EventPhase.EFFECT)
        if target is None or target.creature_type is not CreatureType.HUMANOID:
            return effect
        return self.apply_owned_condition(effect,CalmedEffect(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid))


class HexQuarry(BaseCondition):
    name: str = "Hex"
    description: str = "Chosen ability checks and their skills have disadvantage; saves are unaffected."
    ability: AbilityName = "strength"
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL,ConditionTag.CURSE})

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"Hex:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Hex"

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Hex recipient is absent")
        values=[target.ability_scores.get_ability(self.ability).check_bonus]
        for skill_name in all_skills:
            skill=target.skill_set.get_skill(skill_name)
            if SKILL_TO_ABILITY[skill_name]==self.ability:
                values.append(skill.skill_bonus)
        modifiers=[]
        for value in values:
            identity=value.self_static.add_advantage_modifier(AdvantageModifier(name="Hex",value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
            modifiers.append((value.uuid,identity))
        return modifiers,[],[],[],event.phase_to(EventPhase.EFFECT)


@srd_action_identity(content_id="action.spell.hex.reapply",display_name="Reapply Hex",
    description="Choose a new quarry after the previous quarry is defeated.",parent_spell_name='Hex',source_page=154,sort_order=3010)
class ReapplyHex(ReapplyQuarry):
    name: str = "Reapply Hex"
    description: str = "Choose a new quarry after the previous quarry is defeated."


class HexEffect(QuarrySustain):
    name: str = "Hex Sustain"
    description: str = "Retains the caster's Hex and free reapplication until rest."
    ability: AbilityName = "strength"

    def create_quarry_condition(self,target: Entity) -> BaseCondition:
        return HexQuarry(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid,ability=self.ability)

    def _apply(self,event: Event):
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(self.quarry_uuid)
        if caster is None or target is None or not self.set_quarry(target,event):
            return [],[],[],[],event.cancel(status_message="Quarry cannot be hexed")
        handler=install_hit_rider(self,dice_count=1,die_size=6,damage_type=DamageType.NECROTIC,weapon_only=False,quarry=lambda:self.quarry_uuid)
        action=ReapplyHex(source_entity_uuid=caster.uuid,sustain_uuid=self.uuid,template=True)
        caster.register_action(action)
        self.action_uuid=action.uuid
        return [],[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)


class Hex(SpellAction):
    name: str = "Hex"
    description: str = "Attack-roll hits add 1d6 necrotic; chosen ability CHECKS have disadvantage."
    spell_level: int = 1
    spell_school: str = "enchantment"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=60))
    concentration: bool = True
    harmful: bool = True
    ability: AbilityName = "strength"
    costs: list[Cost] = Field(default_factory=lambda:[Cost(name="Hex",cost_type="bonus_actions",cost=1,
        evaluator=entity_action_economy_cost_evaluator)])

    def get_variant_facets(self):
        return (*super().get_variant_facets(),ActionVariantFacet(key="ability",value=self.ability,label=self.ability.title()))

    def get_discovery_variants(self,entity: Any):
        return [variant.model_copy(update={"uuid":uuid4(),"ability":ability})
            for variant in super().get_discovery_variants(entity)
            for ability in ("strength","dexterity","constitution","intelligence","wisdom","charisma")]

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent):
        if event.target_entity_uuid is None:
            return event.cancel(status_message="Quarry is absent")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),HexEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.source_entity_uuid,
            quarry_uuid=event.target_entity_uuid,ability=self.ability))


class CharmMonsterEffect(AnimalFriendshipEffect):
    name: str = "Charm Monster"
    duration: Duration = Field(default_factory=lambda: Duration(duration=600, duration_type=DurationType.ROUNDS))

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.name = f"Charm Monster:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Charm Monster"


class CharmMonster(SpellAction):
    name: str = "Charm Monster"
    description: str = "Charm visible creatures; combat grants save advantage and allied damage ends the charm."
    spell_level: int = 4
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    target_type: TargetType = TargetType.MULTI_ENTITY
    harmful: bool = True
    include_self: bool = False
    allow_same_target: bool = False
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = (SavingThrowEffectTag.CHARM,)

    def get_multi_target_count(self) -> int:
        return 1 + self.get_upcast_bonus()

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None: return None
        return spell_condition_profile(self, actor, key="charm_monster",
            condition_type=CharmMonsterEffect, save_ability="wisdom", fact="selected_target.condition.charmed")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None: return event.cancel(status_message="Charm recipient absent")
        bonus = target.saving_throws.get_saving_throw("wisdom").bonus
        advantage = None
        if target.active_encounter_uuid is not None and any(
                ally.active_encounter_uuid == target.active_encounter_uuid and ally.is_encounter_alive
                and target.is_enemy(ally) and (ally.uuid == caster.uuid or caster.is_ally(ally))
                for ally in Entity.get_all_entities()):
            advantage = bonus.self_static.add_advantage_modifier(AdvantageModifier(
                name="Combat charm save", value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=target.uuid, target_entity_uuid=caster.uuid))
        try:
            effect, _, saved = self.resolve_saving_throw(event, caster=caster, target=target,
                ability_name="wisdom", dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id))
        finally:
            if advantage is not None: bonus.self_static.remove_modifier(advantage)
        if saved or effect.canceled: return effect
        return self.apply_owned_condition(effect, CharmMonsterEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid, caster_faction=caster.faction))


class IrresistibleDanceEffect(BaseCondition):
    name: str = "Irresistible Dance"
    description: str = "Cannot use Actions or move; incoming attacks gain advantage, DEX saves suffer disadvantage."
    immunity_names: tuple[str, ...] = ("Charmed",)
    spell_dc: int
    blocked_action_channels: frozenset[str] = frozenset({"actions"})
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.name = f"Irresistible Dance:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Irresistible Dance"

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None: return [], [], [], [], event.cancel(status_message="Dancer absent")
        modifiers = []
        for value in target.action_economy.speed_values:
            ident = value.self_static.add_max_constraint(NumericalModifier(name=self.name, value=0,
                source_entity_uuid=target.uuid, target_entity_uuid=self.source_entity_uuid))
            modifiers.append((value.uuid, ident))
        for value in (target.equipment.attack_bonus, target.saving_throws.get_saving_throw("dexterity").bonus):
            ident = value.self_static.add_advantage_modifier(AdvantageModifier(name=self.name,
                value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=target.uuid))
            modifiers.append((value.uuid, ident))
        value = target.equipment.ac_bonus
        ident = value.to_target_static.add_advantage_modifier(AdvantageModifier(name=self.name,
            value=AdvantageStatus.ADVANTAGE, source_entity_uuid=target.uuid))
        modifiers.append((value.uuid, ident))
        def recover(boundary: Event, _: UUID):
            if condition_save(self, target, boundary, "wisdom", self.spell_dc, "spell.irresistible_dance.recovery", (SavingThrowEffectTag.CHARM,)):
                target.remove_condition_by_uuid(self.uuid, parent_event=boundary)
            return None
        handler = EventHandler(name="Dance recovery", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid)], event_processor=recover)
        target.add_event_handler(handler)
        return modifiers, [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class IrresistibleDance(SpellAction):
    name: str = "Irresistible Dance"
    description: str = "No initial save; dancing blocks Actions/movement until a later Wisdom save."
    spell_level: int = 6
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    target_type: TargetType = TargetType.ENTITY
    concentration: bool = True
    harmful: bool = True
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = (SavingThrowEffectTag.CHARM,)

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None: return None
        return spell_condition_profile(self, actor, key="irresistible_dance", condition_type=IrresistibleDanceEffect,
            fact="selected_target.condition.charmed")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A living creature that passes the relationship filter, seen and within range."""
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None: return event.cancel(status_message="Caster absent")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT), IrresistibleDanceEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=event.target_entity_uuid,
            spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)))


class FeeblemindEffect(BaseCondition):
    name: str = "Feeblemind"
    description: str = "INT and CHA become 1; spellcasting and magic item activation are prevented until cured."
    spell_dc: int
    blocks_spellcasting: bool = True
    blocks_magic_item_activation: bool = True
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.ABILITY_SCORE_REDUCTION})
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None: return [], [], [], [], event.cancel(status_message="Feeblemind recipient absent")
        modifiers = []
        for ability in ("intelligence", "charisma"):
            value = target.ability_scores.get_ability(ability).ability_score
            modifier = NumericalModifier(name=self.name, value=1, source_entity_uuid=target.uuid,
                contribution_owner_uuid=self.uuid)
            value.add_fixed_score(modifier)
            modifiers.append((value.uuid, modifier.uuid))
        def cure(incoming: Event, _: UUID):
            if (isinstance(incoming, ActionApplicationCommittedEvent) and not incoming.canceled
                    and incoming.spell_id == "spell.heal" and self.applied and self.contributions_active()):
                target.remove_condition_by_uuid(self.uuid, parent_event=incoming)
            return None
        handler = EventHandler(name="Feeblemind accepted Heal cure", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ACTION_APPLICATION_COMMITTED,event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid)], event_processor=cure)
        target.add_event_handler(handler)
        return modifiers, [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def recover_after_thirty_days(self, adjudication: Event) -> bool:
        """GM/native time adjudication, deliberately absent from player actions."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None or not self.applied: return False
        if condition_save(self, target, adjudication, "intelligence", self.spell_dc, "spell.feeblemind.recovery"):
            return target.remove_condition_by_uuid(self.uuid, parent_event=adjudication)
        return False


class Feeblemind(SpellAction):
    name: str = "Feeblemind"
    description: str = "4d6 psychic damage; failed INT save reduces INT/CHA to 1 and prevents casting or magic item activation."
    spell_level: int = 8
    spell_school: str = "enchantment"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))
    target_type: TargetType = TargetType.ENTITY
    harmful: bool = True

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self, actor, key="feeblemind", condition_type=FeeblemindEffect,
            save_ability="intelligence")

    def get_outcome_profile(self):
        return ActionOutcomeProfile(resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=[DamageRollProfile(dice_count=4, die_size=6, flat_bonus=0, damage_type=DamageType.PSYCHIC.value)])

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A living creature that passes the relationship filter, seen and within range."""
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None: return event.cancel(status_message="Recipient absent")
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        effect, _, saved = self.resolve_saving_throw(event, caster=caster, target=target, ability_name="intelligence", dc=dc)
        if effect.canceled: return effect
        damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, dice_numbers=4,
            damage_dice=6, damage_type=DamageType.PSYCHIC,
            damage_bonus=ModifiableValue.create(source_entity_uuid=caster.uuid, base_value=0))
        effect = deliver_spell_damage(effect, target, damage, roll_spell_damage(damage, parent_event=event, effect_origin=self.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0))
        if effect.canceled or saved or not target.is_active: return effect
        return self.apply_owned_condition(effect, FeeblemindEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid, spell_dc=dc))
