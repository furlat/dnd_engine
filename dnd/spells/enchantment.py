"""Enchantment spells - affecting minds and behavior.

Contains: HoldPerson, HoldPersonEffect, CharmPerson, TestBless, Sleep,
          Bane, BaneEffect, Bless, BlessEffect
"""
import random
from typing import Any, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.base_actions import (
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import (
    BaseCondition,
)
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionRemovalTrigger,
    ConditionTag,
)
from dnd.core.content.origin_features import OriginCapability
from dnd.core.events import (
    Event, EventPhase, RangeType, Range, EventType, EventHandler, Trigger,
    D20RollResultEvent,
)
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.core.aoe import AoEShape, Sphere

from dnd.entity import Entity
from dnd.actions import Move, SpellAction, SpellEvent, validate_line_of_sight
from dnd.conditions import Paralyzed, Charmed, Stunned, Prone
from dnd.creature_transforms import (
    apply_turn_spent_transform,
    apply_unconscious_transform,
)
from dnd.spells.content_metadata import srd_spell_identity


class CharmPerson(SpellAction):
    """Charm one or more humanoids after Wisdom saves.

    Upcasting increases the target count, and targets that are fighting the
    caster receive advantage on the save.
    """
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight, range, target type, and target spacing."""
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        if target_entity.creature_type != CreatureType.HUMANOID:
            return declaration_event.cancel(
                status_message=f"Charm Person only affects humanoids, not {target_entity.creature_type.value}"
            )

        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        all_targets = self.get_all_targets()
        if len(all_targets) > 1:
            for i, t1 in enumerate(all_targets):
                for t2 in all_targets[i+1:]:
                    e1 = Entity.get(t1)
                    e2 = Entity.get(t2)
                    if e1 and e2:
                        dist = e1.senses.get_feet_distance(e2.position)
                        if dist > 30:
                            return declaration_event.cancel(
                                status_message=f"Targets must be within 30ft of each other ({e1.name} and {e2.name} are {dist}ft apart)"
                            )

        parent_result = super()._validate(los_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the Wisdom save and apply Charmed on failure."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

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

        save_bonus = target.saving_throw_bonus(caster.uuid, "wisdom").normalized_score

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

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - {target.name} resists the charm"
            )

        charmed = Charmed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(charmed, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is charmed"
        )


class HoldPersonEffect(BaseCondition):
    """Apply Hold Person's spell-specific parent condition."""
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

        execution_event = declaration_event.with_updates(
            update={"condition": self},
            status_message=f"Applying Paralyzed sub-condition to {target.name}"
        )

        paralyzed = Paralyzed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_condition_event = target.add_condition(paralyzed, parent_event=execution_event)

        if sub_condition_event is not None and sub_condition_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(paralyzed.uuid)

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
                )
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Hold Person's save-based paralysis branch."""
        if not isinstance(actor, Entity):
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight, range, and humanoid targeting."""
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target_entity:
            return declaration_event.cancel(status_message="Target entity not found")

        if target_entity.creature_type != CreatureType.HUMANOID:
            return declaration_event.cancel(
                status_message=f"Hold Person only affects humanoids, not {target_entity.creature_type.value}"
            )

        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and link a failed hold effect to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        concentration = self.ensure_concentration(execution_event)

        effect_event, _, success = self.resolve_saving_throw(
            execution_event,
            caster=caster,
            target=target,
            ability_name="wisdom",
            dc=dc,
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - {target.name} saved"
            )

        hold_effect = HoldPersonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(hold_effect, parent_event=effect_event)

        if hold_effect.applied:
            concentration.add_linked_condition(target.uuid, hold_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        execution_event = declaration_event.with_updates(
            update={"condition": self},
            status_message=f"Applying Paralyzed sub-condition to {target.name}"
        )

        paralyzed = Paralyzed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(paralyzed, parent_event=execution_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(paralyzed.uuid)

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
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Hold Monster's save-based paralysis branch."""
        if not isinstance(actor, Entity):
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight, range, and undead exclusion."""
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target_entity:
            return declaration_event.cancel(status_message="Target entity not found")

        if target_entity.creature_type == CreatureType.UNDEAD:
            return declaration_event.cancel(
                status_message=f"Hold Monster has no effect on undead"
            )

        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and link a failed hold effect to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        concentration_condition = self.ensure_concentration(execution_event)

        effect_event, _, success = self.resolve_saving_throw(
            execution_event,
            caster=caster,
            target=target,
            ability_name="wisdom",
            dc=dc,
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - {target.name} saved"
            )

        hold_effect = HoldMonsterEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(hold_effect, parent_event=effect_event)

        if hold_effect.applied:
            concentration_condition.add_linked_condition(target.uuid, hold_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight and range."""
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply instant death when the target is below the HP threshold."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        current_hp = target.get_hp()

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
                return effect_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"{target.name} is protected from {self.name}"
                )
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} is slain by Power Word Kill!"
            )
        else:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight for all targets."""
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Complete the current target branch of the test spell."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not target:
            return execution_event.cancel(status_message="Target not found")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                Trigger(event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT)
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
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=20
            )

    def get_hp_pool_dice(self) -> Tuple[int, int]:
        """Return the HP-pool dice count and die size."""
        base_dice = 5
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 2
        return (base_dice + upcast_bonus, 8)

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Sleep's automatic agency-denial condition for selected targets."""
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

        if not (self.aoe_shape and self.end_position):
            return []

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return []

        self.aoe_shape.compute_objective(caster.position)

        candidates: List[Tuple[int, UUID]] = []
        for uid in self.aoe_shape.affected_entity_uuids:
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
        """Validate the area origin has line of sight and range."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Sleep effect to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Sleep affecting {target.name} ({target.get_hp()} HP)"
        )

        sleep_effect = SleepEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(sleep_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        stunned = Stunned(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(stunned, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(stunned.uuid)

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

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Power Word Stun", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Power Word Stun", parent_event=event)
            return None

        return EventHandler(
            name=f"Power Word Stun Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class PowerWordStun(SpellAction):
    """Stun a target whose current hit points are at or below the threshold."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight and range."""
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stunned when the target is below the HP threshold."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        current_hp = target.get_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Power Word Stun targeting {target.name} ({current_hp} HP)"
        )

        if current_hp <= self.hp_threshold:
            dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

            stun_effect = PowerWordStunEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc
            )
            target.add_condition(stun_effect, parent_event=effect_event)

            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} is stunned by Power Word Stun!"
            )
        else:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Power Word Stun has no effect - {target.name} has {current_hp} HP (threshold: {self.hp_threshold})"
            )


def _bane_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Subtract 1d4 from d20 roll (attack or save)."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = random.randint(1, 4)
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

    d4_value = random.randint(1, 4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    return event.replace_roll(new_roll, "Bless", f"+{d4_value} (1d4)")


class BaneEffect(BaseCondition):
    """Register Bane's d20 roll-result handler."""
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Bane's failed-save d20 penalty branch."""
        if not isinstance(actor, Entity):
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

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the Charisma save and apply Bane on failure."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        concentration = self.ensure_concentration(execution_event)

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

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Bane - {target.name} resists",
            )

        bane_effect = BaneEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(bane_effect, parent_event=effect_event)
        if bane_effect.applied:
            concentration.add_linked_condition(target.uuid, bane_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Bless's automatic d20 support branch."""
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

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Bless to the current target in the convolution loop."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = self.ensure_concentration(execution_event)

        bless_effect = BlessEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(bless_effect, parent_event=execution_event)
        if bless_effect.applied:
            concentration.add_linked_condition(target.uuid, bless_effect.uuid)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Bless - {target.name} is blessed",
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                (target.action_economy.movement.normalized_score + 4) // 5,
            )
            target.update_entity_senses(
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

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare the save-based condition applied by the selected command."""
        if not isinstance(actor, Entity):
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight and undead immunity."""
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and target.creature_type == CreatureType.UNDEAD:
            return declaration_event.cancel(status_message="Command has no effect on undead")

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and apply the selected command effect."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        if target.creature_type == CreatureType.UNDEAD:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is commanded to {self.command_word}"
        )
