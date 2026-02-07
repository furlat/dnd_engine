"""Enchantment spells - affecting minds and behavior.

Contains: HoldPerson, HoldPersonEffect, CharmPerson, TestBless, Sleep
"""
import random
from typing import Optional, List, Tuple, cast as type_cast
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, RangeType, Range, EventType, EventHandler, Trigger
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, CreatureType, DamageType
from dnd.core.aoe import AoEShape, Sphere

from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent
from dnd.conditions import Paralyzed, Charmed, Unconscious, Stunned, Concentrating
from dnd.spells.evocation import validate_line_of_sight


class CharmPerson(SpellAction):
    """Charm Person - 1st level Enchantment

    You attempt to charm a humanoid you can see within range. It must make a
    Wisdom saving throw, and does so with advantage if you or your companions
    are fighting it. If it fails, it is charmed by you until the spell ends
    or until you or your companions do anything harmful to it. The charmed
    creature regards you as a friendly acquaintance.

    Duration: 1 hour (not tracked in combat - essentially permanent)
    Not concentration.

    At Higher Levels: You can target one additional creature for each slot
    level above 1st. The creatures must be within 30 feet of each other.
    """
    name: str = Field(default="Charm Person")
    description: str = Field(default="WIS save or charmed. Advantage if fighting.")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="enchantment")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)  # Multi-target for upcast
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))

    # Target filtering - humanoids only
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")  # Typically enemies

    # Multi-target configuration
    allow_same_target: bool = Field(default=False)  # Different creatures only
    max_targets: int = Field(default=1)  # Base = 1, +1 per upcast level

    def get_num_targets(self) -> int:
        """1 target base + 1 per upcast level."""
        return 1 + max(0, self.cast_at_level - self.spell_level)

    def get_all_targets(self) -> List[UUID]:
        """Return all targets up to max for cast level."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:self.get_num_targets()]

    def _is_target_fighting_caster(self, target: Entity, caster: Entity) -> bool:
        """Check if target is fighting (in combat with) the caster.

        Returns True if target has attacked the caster this combat,
        or if they're enemies and in close proximity.
        """
        # For now, use a simple check: if they're enemies and visible
        # A more sophisticated check would track combat actions
        if caster.is_enemy(target):
            # If the caster is in target's visible enemies, they're "fighting"
            return caster.uuid in target.get_visible_enemies()
        return False

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, LOS, and creature type (humanoid only)."""

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Charm Person only affects humanoids
        if target_entity.creature_type != CreatureType.HUMANOID:
            return declaration_event.cancel(
                status_message=f"Charm Person only affects humanoids, not {target_entity.creature_type.value}"
            )

        # Validate range
        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        # For multi-target: validate all targets are within 30ft of each other
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

        # Call parent validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Charm Person - WIS save (with advantage if fighting) or charmed."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Check if target gets advantage (fighting the caster)
        is_fighting = self._is_target_fighting_caster(target, caster)

        # 3. Add advantage modifier if fighting
        advantage_mod_uuid: Optional[UUID] = None
        if is_fighting:
            adv_mod = AdvantageModifier(
                name="Charm Person (Fighting)",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            advantage_mod_uuid = target.saving_throws.get_saving_throw("wisdom").bonus.self_static.add_advantage_modifier(adv_mod)

        # 4. Request WIS save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # 5. Remove advantage modifier
        if advantage_mod_uuid:
            target.saving_throws.get_saving_throw("wisdom").bonus.self_static.remove_modifier(advantage_mod_uuid)

        # Get save bonus for combat log
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

        # 6. On successful save: spell has no effect
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - {target.name} resists the charm"
            )

        # 7. On failed save: apply Charmed condition
        charmed = Charmed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(charmed, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is charmed"
        )


class HoldPersonEffect(BaseCondition):
    """
    The spell effect condition applied to the target of Hold Person.

    This condition:
    - Has Paralyzed as a sub-condition (same entity, auto-cleanup)
    - Can be targeted by Dispel Magic
    - Allows spell-specific immunity (immune to "Hold Person" but not all paralysis)
    - Is linked to caster's Concentrating via linked_conditions

    When this condition is removed (by breaking concentration, dispel, or repeat save),
    the Paralyzed sub-condition is automatically removed.
    """
    name: str = "Hold Person"
    description: str = "Magically held in place"

    # Track the caster for repeat saves
    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:


        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            update={"condition": self},
            status_message=f"Applying Paralyzed sub-condition to {target.name}"
        )

        # Apply Paralyzed as a sub-condition (same entity = existing mechanism)
        paralyzed = Paralyzed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid  # Links child to parent
        )
        sub_condition_event = target.add_condition(paralyzed, parent_event=execution_event)

        if sub_condition_event is not None and sub_condition_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(paralyzed.uuid)

        # Register handler for repeat saves at end of target's turn
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
        """Create handler for repeat WIS saves at end of target's turn."""

        # Capture values for closure - these are validated before handler creation
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid: UUID = self.target_entity_uuid
        caster_uuid: UUID = self.caster_uuid
        effect_uuid: UUID = self.uuid
        dc: int = self.spell_dc

        def repeat_save_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """At end of target's turn, allow repeat WIS save."""
            _ = source_entity_uuid  # Unused but required by signature

            # Only trigger for target's turn end
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected by this Hold Person
            hold_person = target.active_conditions.get("Hold Person")
            if not hold_person or hold_person.uuid != effect_uuid:
                return None

            # Make repeat WIS save
            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the spell by removing the effect
                target.remove_condition("Hold Person")
                return None

            # Repeat WIS save (child of triggering turn end event)
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                # Remove concentration from caster - this will automatically
                # remove HoldPersonEffect via linked_conditions, which removes Paralyzed via sub_conditions
                if "Concentrating" in caster.active_conditions:
                    conc = caster.active_conditions.get("Concentrating")
                    if conc and isinstance(conc, Concentrating) and conc.spell_name == "Hold Person":
                        caster.remove_condition("Concentrating")

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


class HoldPerson(SpellAction):
    """Hold Person - 2nd level Enchantment (Concentration)

    Choose a humanoid that you can see within range. The target must succeed
    on a Wisdom saving throw or be paralyzed for the duration. At the end of
    each of its turns, the target can make another Wisdom saving throw.
    On a success, the spell ends on the target.

    At Higher Levels: Target one additional humanoid per slot level above 2nd.
    (Note: Multi-target not yet implemented)
    """
    name: str = Field(default="Hold Person")
    description: str = Field(default="Target must succeed on WIS save or be paralyzed")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="enchantment")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, line of sight, and creature type (humanoid only)."""

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        # Validate range
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Hold Person only affects humanoids
        if target_entity.creature_type != CreatureType.HUMANOID:
            return declaration_event.cancel(
                status_message=f"Hold Person only affects humanoids, not {target_entity.creature_type.value}"
            )

        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Hold Person - WIS save or Paralyzed.

        IMPORTANT: Concentration begins when the spell is cast, BEFORE the save.
        This ensures casting a concentration spell always breaks existing concentration,
        even if the target succeeds on their save.

        Structure:
        - Caster: Concentrating(spell_name="Hold Person")
                      │
                      └── linked_conditions ──► Target: HoldPersonEffect
                                                              │
                                                              └── sub_conditions ──► Paralyzed
        """

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Apply Concentrating condition FIRST (breaks existing concentration)
        # This happens regardless of whether the target saves
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Hold Person"
        )
        caster.add_condition(concentration, parent_event=execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"Requesting WIS save DC {dc}"
        )

        # 3. Request WIS save (child of effect event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=effect_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        # 4. On successful save: spell has no effect (but concentration is active)
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - target saved (still concentrating)"
            )

        # 5. On failed save: apply HoldPersonEffect (which applies Paralyzed as sub-condition)
        hold_effect = HoldPersonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(hold_effect, parent_event=effect_event)

        # 6. Link Concentrating → HoldPersonEffect via linked_conditions
        # When concentration breaks, HoldPersonEffect is removed, which removes Paralyzed
        concentration.add_linked_condition(target.uuid, hold_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is held (concentration)"
        )


class HoldMonsterEffect(BaseCondition):
    """
    The spell effect condition applied to the target of Hold Monster.

    Identical to HoldPersonEffect but with different name for spell-specific immunity.
    """
    name: str = "Hold Monster"
    description: str = "Magically held in place"

    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Paralyzed sub-condition and register repeat save handler."""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            update={"condition": self},
            status_message=f"Applying Paralyzed sub-condition to {target.name}"
        )

        # Apply Paralyzed as sub-condition
        paralyzed = Paralyzed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(paralyzed, parent_event=execution_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(paralyzed.uuid)

        # Register repeat save handler
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
        """Create handler for repeat WIS saves at end of target's turn."""
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

            # Check if still affected
            hold_monster = target.active_conditions.get("Hold Monster")
            if not hold_monster or hold_monster.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Hold Monster")
                return None

            # Repeat WIS save (child of triggering turn end event)
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                # Remove concentration (auto-cleans up via linked_conditions)
                if "Concentrating" in caster.active_conditions:
                    conc = caster.active_conditions.get("Concentrating")
                    if conc and isinstance(conc, Concentrating) and conc.spell_name == "Hold Monster":
                        caster.remove_condition("Concentrating")
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
    """Hold Monster - 5th level Enchantment (Concentration)

    Choose a creature that you can see within range. The target must succeed
    on a WIS save or be paralyzed. Has no effect on undead.
    Repeat save at end of each turn.

    At Higher Levels: +1 target per slot level above 5th.
    """
    name: str = Field(default="Hold Monster")
    description: str = Field(default="Target must succeed on WIS save or be paralyzed (not undead)")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="enchantment")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)  # Multi-target for upcast
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=90))

    # Targeting
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    # Multi-target configuration
    allow_same_target: bool = Field(default=False)  # Different creatures only
    max_targets: int = Field(default=1)  # Base = 1, increases with upcast

    def get_max_targets_for_level(self) -> int:
        """1 target at level 5, +1 per level above 5th."""
        return 1 + max(0, self.cast_at_level - self.spell_level)

    def get_all_targets(self) -> List[UUID]:
        """Return targets up to max for cast level."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:self.get_max_targets_for_level()]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, LOS, and creature type (not undead)."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Check creature type - NOT undead
        if target_entity.creature_type == CreatureType.UNDEAD:
            return declaration_event.cancel(
                status_message=f"Hold Monster has no effect on undead"
            )

        # Validate range
        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(new_phase=EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Hold Monster - WIS save or Paralyzed."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # Apply Concentrating ONCE (check if already concentrating on this spell)
        existing_conc = caster.active_conditions.get("Concentrating")
        if not existing_conc or getattr(existing_conc, 'spell_name', '') != "Hold Monster":
            concentration = Concentrating(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid,
                spell_name="Hold Monster"
            )
            caster.add_condition(concentration, parent_event=execution_event)
            concentration_condition = concentration
        else:
            concentration_condition = existing_conc

        # Request WIS save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - {target.name} saved"
            )

        # On failed save: apply HoldMonsterEffect
        hold_effect = HoldMonsterEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(hold_effect, parent_event=effect_event)

        # Link to concentration
        if isinstance(concentration_condition, Concentrating):
            concentration_condition.add_linked_condition(target.uuid, hold_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is held"
        )


class PowerWordKill(SpellAction):
    """Power Word Kill - 9th level Enchantment

    You utter a word of power that can compel one creature you can see within
    range to die instantly. If the creature you choose has 100 hit points or
    fewer, it dies. Otherwise, the spell has no effect.

    No saving throw - just HP threshold check.
    """
    name: str = Field(default="Power Word Kill")
    description: str = Field(default="If target has ≤100 HP, it dies instantly. No save.")
    spell_level: int = Field(default=9)
    spell_school: str = Field(default="enchantment")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))

    # Target filtering
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    # HP threshold
    hp_threshold: int = Field(default=100)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and LOS."""

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Validate range
        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Power Word Kill - instant death if HP ≤ 100."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Get current HP
        current_hp = target.get_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Power Word Kill targeting {target.name} ({current_hp} HP)"
        )

        if current_hp <= self.hp_threshold:
            # Instant death - deal massive damage to ensure death
            # Using 99999 to guarantee death even with resistances
            target.receive_damage(
                amount=99999,
                damage_type=DamageType.FORCE,  # Force damage can't be resisted
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} is slain by Power Word Kill!"
            )
        else:
            # Spell has no effect
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Power Word Kill has no effect - {target.name} has {current_hp} HP (threshold: {self.hp_threshold})"
            )


class TestBless(SpellAction):
    """TestBless - Test spell for MULTI_ENTITY with different targets required + allies filter.

    Targets up to 3 creatures (self or allies). Each gets a simple buff marker.
    This is a test spell to verify MULTI_ENTITY functionality with:
    - allow_same_target=False (must target different creatures)
    - valid_target_filter="self_or_allies" (can only target self and allies)
    """
    name: str = Field(default="Test Bless")
    description: str = Field(default="Bless up to 3 allies (each target only once)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="enchantment")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)  # Multi-target!
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30)
    )

    # Multi-entity configuration
    allow_same_target: bool = Field(default=False)  # Must target different creatures
    valid_target_filter: str = Field(default="self_or_allies")  # Self or allies only
    max_targets: int = Field(default=3)

    def get_all_targets(self) -> List[UUID]:
        """Override: Return primary + extra targets (no repeats allowed)."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:  # Enforce uniqueness
                targets.append(extra)
        return targets[:self.max_targets]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight for all targets."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Source entity not found")

        # Validate all unique targets are in range and LOS (except self)
        all_targets = self.get_all_targets()

        for target_uuid in all_targets:
            # Skip LOS check for self
            if target_uuid == self.source_entity_uuid:
                continue

            target_entity = Entity.get(target_uuid)
            if not target_entity:
                return declaration_event.cancel(status_message=f"Target entity not found")

            # Check LOS
            if target_uuid not in source_entity.senses.entities.keys():
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            # Check range
            distance = source_entity.senses.get_feet_distance(target_entity.position)
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.spell_range.normal}ft)"
                )

        # Call parent validation for MULTI_ENTITY checks (same-target, target filter)
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply buff to current target (self.target_entity_uuid).

        Called once per target by the convolution loop in BaseAction.apply().
        In a real implementation, this would apply an actual Bless condition.
        """
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not target:
            return execution_event.cancel(status_message="Target not found")

        # In a real implementation, we'd add a BlessCondition here.
        # For testing purposes, we just log the blessing.

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is blessed"
        )


class SleepEffect(BaseCondition):
    """Effect from Sleep spell.

    Target is Unconscious and wakes on taking damage.
    Uses Unconscious as sub-condition for incapacitation effects.
    """
    name: str = "Sleep"
    description: str = "Magically asleep"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        # Apply Unconscious as sub-condition (handles incapacitation, auto-fail saves, etc.)
        unconscious = Unconscious(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(unconscious, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(unconscious.uuid)

        # Register handler to wake on damage
        handler = self._create_wake_on_damage_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Sleep effect to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_wake_on_damage_handler(self) -> EventHandler:
        """Wake target when they take damage."""
        assert self.target_entity_uuid is not None

        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def wake_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected by THIS sleep effect
            sleep_effect = target.active_conditions.get("Sleep")
            if not sleep_effect or sleep_effect.uuid != effect_uuid:
                return None

            # Wake up - remove Sleep condition (removes Unconscious sub-condition automatically)
            target.remove_condition("Sleep")
            return None

        return EventHandler(
            name=f"Sleep Wake Handler ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EFFECT)
            ],
            event_processor=wake_processor
        )


class Sleep(SpellAction):
    """Sleep - 1st level Enchantment

    Roll 5d8 HP pool. Creatures in 20ft sphere fall Unconscious
    in order of lowest HP until pool exhausted.

    Immune: Undead, creatures immune to being charmed
    Duration: 1 minute (or until damage/action to wake)
    Upcast: +2d8 per slot level above 1st.
    """
    name: str = Field(default="Sleep")
    description: str = Field(default="Roll 5d8 HP pool. Affects creatures in order of lowest HP.")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="enchantment")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=90))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - but we override get_all_targets for HP-pool logic
    include_self: bool = Field(default=False)  # Caster can be affected
    valid_target_filter: str = Field(default="all")  # Affects everyone

    # HP pool tracking (set during get_all_targets)
    hp_pool_rolled: int = Field(default=0)
    hp_pool_remaining: int = Field(default=0)

    def __init__(self, **kwargs):

        if 'aoe_shape' not in kwargs or kwargs['aoe_shape'] is None:
            source_uuid = kwargs.get('source_entity_uuid') or uuid4()
            kwargs['aoe_shape'] = Sphere(
                source_entity_uuid=source_uuid,
                target=kwargs.get('end_position', (0, 0)),
                radius_feet=20
            )
        super().__init__(**kwargs)

    def get_range(self) -> Range:
        return self.spell_range

    def get_hp_pool_dice(self) -> Tuple[int, int]:
        """Returns (dice_count, dice_value). 5d8 base + 2d8 per upcast."""
        base_dice = 5
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 2
        return (base_dice + upcast_bonus, 8)

    def get_all_targets(self) -> List[UUID]:
        """Override: Select targets by HP pool instead of all AoE targets.

        1. Get AoE candidates using parent logic
        2. Filter by immunity (undead, charm-immune)
        3. Sort by current HP (ascending)
        4. Select targets until HP pool exhausted
        """
        # 1. Get AoE candidates
        if not (self.aoe_shape and self.end_position):
            return []

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return []

        self.aoe_shape.compute_objective(caster.position)

        # 2. Filter candidates: alive, not immune
        candidates: List[Tuple[int, UUID]] = []
        for uid in self.aoe_shape.affected_entity_uuids:
            # Skip caster if include_self is False
            if not self.include_self and uid == self.source_entity_uuid:
                continue

            entity = Entity.get(uid)
            if not entity or entity.get_hp() <= 0:
                continue

            # Sleep immunity: undead
            if entity.creature_type == CreatureType.UNDEAD:
                continue

            # Skip charm-immune creatures (Sleep targets creatures that can be charmed)
            if entity.check_condition_immunity("Charmed"):
                continue

            candidates.append((entity.get_hp(), uid))

        # 3. Sort by HP ascending (lowest first)
        # Tie-breaker: UUID for deterministic ordering
        candidates.sort(key=lambda x: (x[0], str(x[1])))

        # 4. Roll HP pool if not already rolled
        if self.hp_pool_rolled == 0:
            dice_count, dice_value = self.get_hp_pool_dice()
            # Simple roll without full Dice machinery for efficiency
            roll_results = [random.randint(1, dice_value) for _ in range(dice_count)]
            total = sum(roll_results)
            self.hp_pool_rolled = total
            self.hp_pool_remaining = total

        # 5. Select targets until pool exhausted
        targets: List[UUID] = []
        remaining = self.hp_pool_remaining
        for hp, uid in candidates:
            if hp <= remaining:
                targets.append(uid)
                remaining -= hp

        self.hp_pool_remaining = remaining
        return targets

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        # Check LOS to target position
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        # Check range
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

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

        # Apply SleepEffect condition (has Unconscious as sub-condition + wake handler)
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
    """
    Effect from Power Word Stun spell.

    Target is Stunned. At end of each turn, CON save to end.
    Uses Stunned as sub-condition.
    """
    name: str = "Power Word Stun"
    description: str = "Stunned by power word"

    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        # Apply Stunned as sub-condition
        stunned = Stunned(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(stunned, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(stunned.uuid)

        # Register repeat save handler
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
        """CON save at end of turn to end stun."""
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

            # Check if still affected
            pw_stun = target.active_conditions.get("Power Word Stun")
            if not pw_stun or pw_stun.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the effect
                target.remove_condition("Power Word Stun")
                return None

            # Repeat CON save (child of triggering turn end event)
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Power Word Stun")
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
    """Power Word Stun - 8th level Enchantment

    You speak a word of power that can overwhelm the mind of one creature you
    can see within range, leaving it dumbfounded. If the target has 150 hit
    points or fewer, it is stunned. Otherwise, the spell has no effect.

    The stunned target must make a CON save at the end of each of its turns.
    On a successful save, this stunning effect ends.

    No saving throw to resist initially - just HP threshold check.
    """
    name: str = Field(default="Power Word Stun")
    description: str = Field(default="If target has ≤150 HP, it is stunned. CON save each turn to end.")
    spell_level: int = Field(default=8)
    spell_school: str = Field(default="enchantment")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))

    # HP threshold
    hp_threshold: int = Field(default=150)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and LOS."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Validate range
        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Power Word Stun - stun if HP ≤ 150."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Get current HP
        current_hp = target.get_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Power Word Stun targeting {target.name} ({current_hp} HP)"
        )

        if current_hp <= self.hp_threshold:
            # Stun the target
            dc = caster.spell_save_dc()

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
            # Spell has no effect
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Power Word Stun has no effect - {target.name} has {current_hp} HP (threshold: {self.hp_threshold})"
            )
