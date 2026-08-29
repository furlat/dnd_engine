"""Necromancy spells - manipulating life force and death.

Contains: Blight, BlindnessDeafness, FalseLife, ChillTouch, NecroticBless, Eyebite, BestowCurse
"""
from typing import Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.base_actions import (
    ActionOutcomeProfile,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.types.conditions import (
    ConditionAgencyDenial,
    ConditionCategory,
    ConditionRemovalTrigger,
    ConditionTag,
    DurationType,
)
from dnd.types.world import MovementMode
from dnd.types.rolls import AttackOutcome, RollType
from dnd.core.dice import Dice
from dnd.core.events.resolution_events import (
    DamageRollResultEvent,
    RangeType,
    Range,
    Damage,
)
from dnd.core.events.events_registry import (
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
    Event,
    EventQueue,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
)
from dnd.types.abilities import AbilityName, SkillName
from dnd.core.gridmap import get_map
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    NumericalModifier,
    ContextualAdvantageModifier,
)
from dnd.types.rolls import AdvantageStatus
from dnd.core.values import ModifiableValue
from functools import partial
from typing import Any, Dict
from dnd.entities.entity import Entity
from dnd.actions.standard import (
    Dash,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.core.base_actions import (
    Cost,
    BaseAction,
    ActionCategory,
)
from dnd.conditions import Blinded, Deafened, Frightened, Concentrating, ConcentrationActionMarker
from dnd.entities.creature_transforms import apply_unconscious_transform
from dnd.spells.enchantment import BaneEffect, BlessEffect
from dnd.spells.content_metadata import srd_action_identity
from dnd.blocks.skills import SKILL_TO_ABILITY


class FalseLife(SpellAction):
    """Grant temporary hit points through a self-targeted necromancy spell.

    False Life grants 1d4 + 4 temporary hit points, plus 5 additional
    temporary hit points for each slot level above 1st. The engine applies the
    temporary hit points immediately and leaves duration expiry to the HP pool.
    """
    name: str = Field(default="False Life", description="Spell name.")
    description: str = Field(
        default="Gain 1d4+4 temporary hit points (+5 per upcast level)",
        description="Rules-facing summary of the temporary hit point effect.",
    )
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Self-targeting spell.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF, normal=0),
        description="Self range used by action discovery and validation.",
    )

    def get_temp_hp_bonus(self) -> int:
        """Return the flat temporary hit point bonus before the d4 roll."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 5
        return 4 + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate that the caster exists before the self spell executes."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Casting {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Roll and apply False Life's temporary hit points."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        bonus_value = ModifiableValue.create(
            source_entity_uuid=caster.uuid,
            base_value=self.get_temp_hp_bonus(),
            value_name="False Life Bonus"
        )
        dice = Dice(
            count=1,
            value=4,
            bonus=bonus_value,
            roll_type=RollType.CHECK
        )
        temp_hp_roll = dice.roll

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            dice_roll=temp_hp_roll,
            status_message=f"Rolled 1d4+{self.get_temp_hp_bonus()} = {temp_hp_roll.total} temporary HP"
        )
        if effect_event.canceled:
            return effect_event

        caster.grant_temporary_hit_points(
            temp_hp_roll.total,
            caster.uuid,
            source_description=self.name,
            parent_event=effect_event.uuid,
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            temp_hp_gained=temp_hp_roll.total,
            status_message=f"{caster.name} gains {temp_hp_roll.total} temporary hit points"
        )


class NoHealing(BaseCondition):
    """Block healing on the target while the condition is active."""
    name: str = Field(default="No Healing", description="Condition name.")
    description: str = Field(default="Cannot regain hit points", description="Rules-facing condition summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Set the target health block to reject healing."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target.health.healing_blocked = True

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} cannot regain hit points"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Reset the target health block when the condition is removed."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.health.healing_blocked = False

        return super()._remove(event)


class ChillTouchEffect(BaseCondition):
    """Track Chill Touch's duration and target-linked healing block.

    The tracking condition lives on the caster so the "until the start of your
    next turn" duration advances with the caster. It links to the No Healing
    condition applied to the target and optionally adds the undead attack
    penalty.
    """
    name: str = Field(default="Chill Touch Effect", description="Condition name.")
    description: str = Field(
        default=(
            "A creature hit by Chill Touch cannot regain hit points until the "
            "start of the caster's next turn; if it is undead, it also has "
            "disadvantage on attacks against the caster."
        ),
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    affected_target_uuid: Optional[UUID] = Field(default=None, description="Target affected by Chill Touch.")
    target_is_undead: bool = Field(default=False, description="Whether the affected target is undead.")

    @staticmethod
    def undead_attack_disadvantage(
        caster_uuid: UUID,
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[AdvantageModifier]:
        """Return disadvantage when the undead target attacks the caster."""
        _ = context
        if target_entity_uuid and target_entity_uuid == caster_uuid:
            return AdvantageModifier(
                name="Chill Touch (Undead)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid
            )
        return None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the caster-side tracker and undead attack penalty if needed."""
        if not self.affected_target_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Affected target UUID not set")

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Caster UUID not set")

        target = Entity.get(self.affected_target_uuid)
        caster = Entity.get(self.target_entity_uuid)
        if not target or not caster:
            return [], [], [], [], declaration_event.cancel(status_message="Target or caster not found")

        outs: List[Tuple[UUID, UUID]] = []

        if self.target_is_undead:
            callable_func = partial(self.undead_attack_disadvantage, caster.uuid)
            disadv_mod = ContextualAdvantageModifier(
                name="Chill Touch (Undead)",
                source_entity_uuid=target.uuid,
                target_entity_uuid=caster.uuid,
                callable=callable_func
            )
            mod_uuid = target.equipment.attack_bonus.self_contextual.add_advantage_modifier(disadv_mod)
            outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Applied Chill Touch effect tracker"
        )

        if not outs:
            dummy_mod = NumericalModifier(
                name="Chill Touch Tracker",
                value=0,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
            mod_uuid = caster.proficiency_bonus.self_static.add_value_modifier(dummy_mod)
            outs.append((caster.proficiency_bonus.uuid, mod_uuid))

        return outs, [], [], [], effect_event


class ChillTouch(SpellAction):
    """Make a ranged spell attack that deals necrotic damage and blocks healing.

    Damage scales to 2d8 at 5th level, 3d8 at 11th level, and 4d8 at 17th
    level. Undead targets also gain disadvantage on attacks against the caster.
    """
    name: str = Field(default="Chill Touch", description="Spell name.")
    description: str = Field(
        default="1d8 necrotic, target can't heal. Undead: disadvantage vs caster.",
        description="Rules-facing summary of the attack and debuffs.",
    )
    spell_level: int = Field(default=0, description="Cantrip spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Maximum range for the spell attack.",
    )
    projectile_type: Optional[str] = Field(default="orb", description="VFX projectile metadata.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Chill Touch's execution-honest actor-baseline attack model."""
        if not isinstance(actor, Entity):
            return None
        profile = self.spell_attack_outcome_profile(
            actor,
            dice_count=self._get_cantrip_dice_count(self.caster_level),
            die_size=8,
            damage_type=DamageType.NECROTIC,
        )
        return profile

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight for the spell attack."""
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute the spell attack, damage roll, and hit debuffs."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )
        if effect_event.canceled:
            return effect_event

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )

        damage_dice = necrotic_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.NECROTIC,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        is_undead = target.creature_type == CreatureType.UNDEAD

        effect_condition = ChillTouchEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            affected_target_uuid=target.uuid,
            target_is_undead=is_undead,
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
        )
        caster.add_condition(effect_condition, parent_event=effect_event)

        no_healing = NoHealing(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(no_healing, parent_event=effect_event)

        effect_condition.add_linked_condition(target.uuid, no_healing.uuid)

        undead_text = " (undead: disadvantage vs caster)" if is_undead else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} necrotic damage, target can't heal{undead_text}"
        )


class Blight(SpellAction):
    """Drain vitality from a creature with a Constitution saving throw.

    Undead and constructs are rejected during validation. Plant creatures have
    disadvantage on the saving throw and take maximum damage.
    """
    name: str = Field(default="Blight", description="Spell name.")
    description: str = Field(
        default="8d8 necrotic, CON save half. No effect on undead/constructs. Plants: disadvantage + max damage.",
        description="Rules-facing summary of damage and special target handling.",
    )
    spell_level: int = Field(default=4, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the spell target.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="VFX projectile metadata.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")
    include_self: bool = Field(default=False, description="Whether action discovery includes the caster.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    base_damage_dice: int = Field(default=8, description="Base number of d8 damage dice.")

    def get_damage_dice_count(self) -> int:
        """Return the number of d8 damage dice after upcasting."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Blight's save-for-half necrotic damage model."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=8,
            damage_type=DamageType.NECROTIC,
            save_ability="constitution",
            half_damage_on_save=True,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight, range, and invalid creature types."""
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target_entity:
            return declaration_event.cancel(status_message="Target entity not found")

        if target_entity.creature_type == CreatureType.UNDEAD:
            return declaration_event.cancel(
                status_message="Blight has no effect on undead"
            )
        if target_entity.creature_type == CreatureType.CONSTRUCT:
            return declaration_event.cancel(
                status_message="Blight has no effect on constructs"
            )

        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the saving throw and apply necrotic damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        is_plant = target.creature_type == CreatureType.PLANT
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        mod_uuid: Optional[UUID] = None
        if is_plant:
            disadv_mod = AdvantageModifier(
                name="Blight (Plant)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            mod_uuid = target.saving_throws.get_saving_throw(AbilityName.CONSTITUTION).bonus.self_static.add_advantage_modifier(disadv_mod)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        if is_plant and mod_uuid:
            target.saving_throws.get_saving_throw(AbilityName.CONSTITUTION).bonus.self_static.remove_modifier(mod_uuid)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()
        damage_bonus_value = damage_bonus.normalized_score

        if is_plant:
            final_damage = num_dice * 8 + damage_bonus_value
        else:
            necrotic_damage = Damage(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                damage_dice=8,
                dice_numbers=num_dice,
                damage_bonus=damage_bonus,
                damage_type=DamageType.NECROTIC
            )
            damage_dice = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT)
            damage_roll = damage_dice.roll

            final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success and not is_plant else ""
        plant_text = " (maximum damage)" if is_plant else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=final_damage,
            status_message=f"Blight deals {final_damage} necrotic damage to {target.name}{save_text}{plant_text}"
        )


class BlindnessDeafnessEffect(BaseCondition):
    """Apply Blindness/Deafness and manage its repeat save handler."""
    name: str = Field(default="Blindness/Deafness", description="Condition name.")
    description: str = Field(default="Blinded or Deafened by magic", description="Rules-facing condition summary.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the save DC.")
    spell_dc: int = Field(default=10, description="Constitution save DC to end the effect.")
    effect_type: str = Field(default="blinded", description="Effect choice: blinded or deafened.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the chosen sub-condition and register repeat saves."""
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        if self.effect_type == "blinded":
            effect = Blinded(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL}
            )
        else:
            effect = Deafened(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL}
            )

        sub_event = target.add_condition(effect, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(effect.uuid)

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied {self.effect_type.capitalize()} to {target.name}"
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

        def repeat_save_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            bd_effect = target.active_conditions.get("Blindness/Deafness")
            if not bd_effect or bd_effect.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Blindness/Deafness", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.CONSTITUTION,
                dc=dc,
                parent_event=event.uuid
            )
            _roll, _outcome, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Blindness/Deafness", parent_event=event)
            return None

        return EventHandler(
            name=f"Blindness/Deafness Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class BlindnessDeafness(SpellAction):
    """Blind or deafen one or more targets after Constitution saves.

    The spell is not concentration. Upcasting targets one additional creature
    for each slot level above 2nd.
    """
    name: str = Field(default="Blindness/Deafness", description="Spell name.")
    description: str = Field(
        default="CON save or Blinded/Deafened. Repeat save each turn.",
        description="Rules-facing summary of the chosen effect and repeat save.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    effect_type: str = Field(default="blinded", description="Effect choice: blinded or deafened.")

    def get_num_projectiles(self) -> int:
        """Return the number of targets allowed by the slot level."""
        return 1 + self.get_upcast_bonus()

    def get_multi_target_count(self) -> Optional[int]:
        """Return the action discovery multi-target count."""
        return self.get_num_projectiles()

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare the selected blindness/deafness save effect."""
        if not isinstance(actor, Entity):
            return None
        effect_type = self.effect_type.lower()
        condition_keys = (
            frozenset({"dnd.spells.necromancy.BlindnessDeafnessEffect", "dnd.conditions.Deafened"})
            if effect_type == "deafened"
            else frozenset({"dnd.spells.necromancy.BlindnessDeafnessEffect", "dnd.conditions.Blinded"})
        )
        condition_fact = "selected_target.condition.deafened" if effect_type == "deafened" else "selected_target.condition.blinded"
        return ActionTargetEffectProfile(
            semantic_id=f"control.blindness_deafness.{effect_type}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"control.{effect_type}",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="constitution",
                    condition_fact_ids=(condition_fact,),
                    condition_semantic_keys=condition_keys,
                ),
            ),
        )

    def get_all_targets(self) -> List[UUID]:
        """Return the selected targets trimmed to the spell's target count."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets[:self.get_num_projectiles()]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate effect choice, range, and line of sight for all targets."""
        if self.effect_type not in ["blinded", "deafened"]:
            return declaration_event.cancel(status_message="Effect type must be 'blinded' or 'deafened'")

        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and apply the chosen effect on failure."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Blindness/Deafness"
            )

        bd_effect = BlindnessDeafnessEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc,
            effect_type=self.effect_type
        )
        target.add_condition(bd_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is {self.effect_type.capitalize()} by Blindness/Deafness"
        )


class NecroticBless(SpellAction):
    """Apply Bless to undead targets or Bane to living targets.

    This homebrew spell targets up to four creatures. Undead targets receive
    BlessEffect without a save. Other targets must pass a Charisma save or
    receive BaneEffect.
    """
    name: str = Field(default="Necrotic Bless", description="Spell name.")
    description: str = Field(
        default="4 targets: undead get +1d4, others CHA save or -1d4",
        description="Rules-facing summary of the undead and non-undead effects.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Multi-creature target mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for each target.",
    )
    allow_same_target: bool = Field(default=False, description="Whether repeated targets are allowed.")
    valid_target_filter: str = Field(default="all", description="Action discovery target filter.")
    include_self: bool = Field(default=True, description="Whether action discovery includes the caster.")

    def get_multi_target_count(self) -> Optional[int]:
        """Return the fixed maximum number of targets."""
        return 4

    def get_target_effect_profile(self, actor: Any) -> ActionTargetEffectProfile:
        """Declare the creature-type branches used for target allocation.

        Args:
            actor: Spellcaster discovering this action.

        Returns:
            Conditional Bless and Bane effects with the actor's current save DC.
        """
        return ActionTargetEffectProfile(
            semantic_id="spell.necrotic_bless",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="support.bless",
                    disposition=TargetEffectDisposition.BENEFICIAL,
                    included_creature_types=frozenset({CreatureType.UNDEAD.value}),
                    resolution=OutcomeResolution.AUTOMATIC,
                    condition_fact_ids=("selected_target.condition.bless",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.enchantment.BlessEffect",
                    }),
                ),
                ActionTargetEffectBranchProfile(
                    effect_id="control.bane",
                    disposition=TargetEffectDisposition.HARMFUL,
                    excluded_creature_types=frozenset({CreatureType.UNDEAD.value}),
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_ability="charisma",
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    condition_fact_ids=("selected_target.condition.bane",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.enchantment.BaneEffect",
                    }),
                ),
            ),
        )

    def get_all_targets(self) -> List[UUID]:
        """Return unique selected targets trimmed to four creatures."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:4]

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve one target during multi-target convolution."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        is_undead = target.creature_type == CreatureType.UNDEAD

        if is_undead:
            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                target_entity_name=target.name,
                status_message=f"Necrotic Bless - {target.name} (undead) is blessed",
            )
            if effect_event.canceled:
                return effect_event

            concentration = self.ensure_concentration(effect_event)
            bless_effect = BlessEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                tags={ConditionTag.MAGICAL},
            )
            target.add_condition(bless_effect, parent_event=effect_event)
            if bless_effect.applied:
                concentration.add_linked_condition(target.uuid, bless_effect.uuid)
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Necrotic Bless - {target.name} (undead) is blessed",
            )
        else:
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.CHARISMA,
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
                return effect_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Necrotic Bless - {target.name} resists",
                )

            concentration = self.ensure_concentration(effect_event)
            bane_effect = BaneEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                tags={ConditionTag.MAGICAL},
            )
            target.add_condition(bane_effect, parent_event=effect_event)
            if bane_effect.applied:
                concentration.add_linked_condition(target.uuid, bane_effect.uuid)

            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Necrotic Bless - {target.name} is baned",
            )


class SickenedCondition(BaseCondition):
    """Apply Eyebite's sickened option and its repeat Wisdom save."""
    name: str = Field(default="Sickened", description="Condition name.")
    description: str = Field(
        default="Disadvantage on attacks and ability checks",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster the target must flee from.")
    spell_dc: int = Field(default=10, description="Wisdom save DC to end the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply attack and ability-check disadvantage to the target."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        mod_uuid = target.equipment.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Sickened (attacks)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=target.uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        for ability_name_str in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability_name_typed = type_cast(AbilityName, ability_name_str)
            ability = target.ability_scores.get_ability(ability_name_typed)
            ab_mod_uuid = ability.ability_score.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Sickened (ability checks)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((ability.ability_score.uuid, ab_mod_uuid))

        handler = self._create_repeat_save_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is sickened"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create the end-of-turn Wisdom save handler."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid or self.source_entity_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            sickened = target.active_conditions.get("Sickened")
            if not sickened or sickened.uuid != effect_uuid:
                return None
            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Sickened", parent_event=event)
                return None
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.WISDOM,
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                target.remove_condition("Sickened", parent_event=event)
            return None

        return EventHandler(
            name=f"Sickened: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class EyebiteAsleepEffect(BaseCondition):
    """Apply Eyebite's asleep option and remove it when damage is taken."""
    name: str = Field(default="Eyebite Asleep", description="Condition name.")
    description: str = Field(
        default="Magically asleep - wakes on damage",
        description="Rules-facing condition summary.",
    )
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
        description="The asleep option removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the unconscious transform and register its wake handler."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs = apply_unconscious_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )

        handler = self._create_wake_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} falls asleep (Eyebite)"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_wake_handler(self) -> EventHandler:
        """Create the damage-triggered wake handler."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            asleep = target.active_conditions.get("Eyebite Asleep")
            if not asleep or asleep.uuid != effect_uuid:
                return None
            target.remove_condition("Eyebite Asleep", parent_event=event)
            return None

        return EventHandler(
            name=f"Eyebite: Wake on Damage ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.DAMAGE_APPLIED,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class EyebitePanickedEffect(BaseCondition):
    """Apply Eyebite's panicked option and forced flee behavior."""
    name: str = Field(default="Eyebite Panicked", description="Condition name.")
    description: str = Field(
        default="Panicked - Frightened, must Dash away from caster",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the repeat-save DC.")
    spell_dc: int = Field(default=10, description="Initial Eyebite save DC retained with the effect.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Frightened and register the forced flee handler."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        frightened = Frightened(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(frightened, parent_event=declaration_event)
        sub_conditions_uuids.append(frightened.uuid)

        handler = self._create_flee_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is panicked (Eyebite)"
        )
        return [], handler_uuids, sub_conditions_uuids, [], effect_event

    @staticmethod
    def _distance_feet(first: Tuple[int, int], second: Tuple[int, int]) -> int:
        """Return the engine's Euclidean-grid distance in feet."""
        return int(((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5) * 5

    @staticmethod
    def _direction(start: Tuple[int, int], end: Tuple[int, int]) -> Tuple[int, int]:
        """Return the unit direction from start to end."""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1
        return dx, dy

    @staticmethod
    def _path_cost_feet(target: Entity, path: List[Tuple[int, int]]) -> int:
        """Return the movement cost of a path in feet."""
        grid = get_map()
        cost_units = 0.0
        for step in path[1:]:
            tile = grid.get_tile(*step)
            step_cost = tile.get_movement_cost(MovementMode.WALKING) if tile else 1.0
            if target.ignore_difficult_terrain:
                step_cost = min(step_cost, 1.0)
            cost_units += step_cost
        return int(cost_units * 5)

    @staticmethod
    def _path_is_hazardous(target: Entity, path: List[Tuple[int, int]]) -> bool:
        """Return whether a path crosses a hazardous position for the target."""
        grid = get_map()
        return any(
            grid.is_position_hazardous_for(step[0], step[1], target.uuid)
            for step in path[1:]
        )

    def _should_end(self, target: Entity, caster: Entity) -> bool:
        """Return whether Panicked ends by distance and loss of sight."""
        target.materialize_navigation(max_distance=80)
        distance = self._distance_feet(target.position, caster.position)
        contact = target.senses.entities.get(caster.uuid)
        return distance >= 60 and (contact is None or not contact.visual)

    def _choose_flee_path(self, target: Entity, caster: Entity, movement_budget: int) -> List[Tuple[int, int]]:
        """Choose the safest farthest path away from the caster within budget."""
        target.materialize_navigation(max_distance=80)
        start_distance = self._distance_feet(target.position, caster.position)
        best_path: List[Tuple[int, int]] = []
        best_score: Optional[Tuple[int, int, int]] = None

        for position, normal_path in target.senses.paths.items():
            if position == target.position:
                continue

            path_options: List[Tuple[int, int, List[Tuple[int, int]]]] = []
            normal_cost = self._path_cost_feet(target, normal_path)
            if normal_cost <= movement_budget:
                normal_hazard_rank = 0 if self._path_is_hazardous(target, normal_path) else 1
                path_options.append((normal_hazard_rank, normal_cost, list(normal_path)))

            safe_path = target.senses.safe_paths.get(position)
            if safe_path:
                safe_cost = self._path_cost_feet(target, safe_path)
                if safe_cost <= movement_budget:
                    path_options.append((1, safe_cost, list(safe_path)))

            for safety_rank, cost, path in path_options:
                distance = self._distance_feet(position, caster.position)
                if distance <= start_distance:
                    continue
                score = (safety_rank, distance, -cost)
                if best_score is None or score > best_score:
                    best_score = score
                    best_path = path

        return best_path

    def _move_along_flee_path(self, target: Entity, caster: Entity, path: List[Tuple[int, int]], parent_event: Event) -> None:
        """Move the target along the selected flee path using forced-movement events."""
        if len(path) <= 1:
            return

        grid = get_map()
        planned_cost = self._path_cost_feet(target, path)
        final_position = path[-1]
        direction = self._direction(target.position, final_position)
        forced_event = ForcedMovementEvent(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            source_entity_name=caster.name,
            target_entity_name=target.name,
            start_position=target.position,
            end_position=final_position,
            direction=direction,
            intended_distance=planned_cost,
            actual_distance=planned_cost,
            blocked_by_obstacle=False,
            cause="eyebite_panicked",
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid,
            use_register=False,
        )

        forced_event = EventQueue.publish_declaration(forced_event)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EXECUTION)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EFFECT)
        if forced_event.canceled:
            return

        moved_cost = 0
        blocked = False
        blocked_by: Optional[str] = None
        current_position = target.position

        for next_position in path[1:]:
            blocked_by = grid.identify_blocker_at(
                next_position,
                target.uuid,
                source_position=current_position,
            )
            if blocked_by is not None:
                blocked = True
                break
            step_cost = self._path_cost_feet(target, [current_position, next_position])
            Entity.update_entity_position(target, next_position, parent_event=forced_event.uuid)
            moved_cost += step_cost
            current_position = next_position

        forced_event.phase_to(
            EventPhase.COMPLETION,
            end_position=target.position,
            actual_distance=moved_cost,
            blocked_by_obstacle=blocked,
            blocked_by=blocked_by,
            status_message=f"Eyebite Panicked movement ended at {target.position}",
        )

    def _create_flee_handler(self) -> EventHandler:
        """Create the turn-start forced flee handler."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid or self.source_entity_uuid
        effect_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            panicked = target.active_conditions.get("Eyebite Panicked")
            if not panicked or panicked.uuid != effect_uuid:
                return None
            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Eyebite Panicked", parent_event=event)
                return None

            if self._should_end(target, caster):
                target.remove_condition("Eyebite Panicked", parent_event=event)
                return None

            dash_event = Dash(source_entity_uuid=target.uuid, template=False).apply(parent_event=event)
            if dash_event is None or dash_event.canceled:
                return None

            movement_budget = target.action_economy.get_base_value("movement") * 2
            flee_path = self._choose_flee_path(target, caster, movement_budget)
            self._move_along_flee_path(target, caster, flee_path, event)

            if self._should_end(target, caster):
                target.remove_condition("Eyebite Panicked", parent_event=event)
            return None

        return EventHandler(
            name=f"Eyebite Panicked: Flee ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class EyebiteCastingState(ConcentrationActionMarker):
    """Track Eyebite's granted action and successful saves for one casting."""
    name: str = Field(default="Eyebite Casting", description="Condition name.")
    description: str = Field(
        default="Tracking Eyebite action and targets that saved",
        description="Rules-facing summary of the casting state.",
    )
    successful_save_target_uuids: Set[UUID] = Field(
        default_factory=set,
        description="Creature UUIDs that succeeded on a save against this Eyebite casting.",
    )


@srd_action_identity(
    content_id="action.spell.eyebite.strike",
    display_name="Eyebite Strike",
    description="Apply another selected gaze effect from an active Eyebite spell.",
    parent_spell_name="Eyebite",
    source_page=141,
    sort_order=950,
)
class EyebiteStrike(BaseAction):
    """Resolve the action granted while concentrating on Eyebite."""
    name: str = Field(default="Eyebite Strike", description="Action name.")
    description: str = Field(
        default="Choose a creature: Asleep, Panicked, or Sickened (WIS save)",
        description="Rules-facing action summary.",
    )
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Eyebite Strike", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy cost paid by repeat uses.")
    spell_dc: int = Field(default=10, description="Wisdom save DC for the selected target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the repeat target.",
    )
    effect_choice: str = Field(default="sickened", description="Effect choice: asleep, panicked, or sickened.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    casting_state_condition_uuid: Optional[UUID] = Field(
        default=None,
        description="Eyebite casting-state condition that tracks successful saves.",
    )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare the selected Eyebite strike condition."""
        if not isinstance(actor, Entity):
            return None
        effect_choice = self.effect_choice.lower()
        condition_fact, condition_keys = {
            "asleep": (
                "selected_target.condition.eyebite_asleep",
                frozenset({"dnd.spells.necromancy.EyebiteAsleepEffect"}),
            ),
            "panicked": (
                "selected_target.condition.eyebite_panicked",
                frozenset({"dnd.spells.necromancy.EyebitePanickedEffect"}),
            ),
        }.get(
            effect_choice,
            (
                "selected_target.condition.sickened",
                frozenset({"dnd.spells.necromancy.SickenedCondition"}),
            ),
        )
        return ActionTargetEffectProfile(
            semantic_id=f"control.eyebite.{effect_choice}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"control.eyebite.{effect_choice}",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=self.spell_dc,
                    save_ability="wisdom",
                    condition_fact_ids=(condition_fact,),
                    condition_semantic_keys=condition_keys,
                ),
            ),
        )

    def _get_casting_state(self, caster: Entity) -> Optional[EyebiteCastingState]:
        """Return the active Eyebite casting state for this strike."""
        if self.casting_state_condition_uuid is not None:
            condition = caster.active_conditions_by_uuid.get(self.casting_state_condition_uuid)
            if isinstance(condition, EyebiteCastingState):
                return condition
        fallback = caster.active_conditions.get("Eyebite Casting")
        return fallback if isinstance(fallback, EyebiteCastingState) else None

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate active Eyebite concentration and target range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if "Concentrating" not in caster.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on Eyebite")

        conc = caster.active_conditions.get("Concentrating")
        if not isinstance(conc, Concentrating) or conc.get_slot_by_spell_name("Eyebite") is None:
            return declaration_event.cancel(status_message="Not concentrating on Eyebite")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="No target specified")

        distance = caster.distance_to_entity(target)
        if distance > 60:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft)")

        contact = caster.senses.entities.get(target.uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message="Target not visible")

        casting_state = self._get_casting_state(caster)
        if casting_state and target.uuid in casting_state.successful_save_target_uuids:
            return declaration_event.cancel(status_message="Target already succeeded against this Eyebite")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        """Resolve the Wisdom save and apply the chosen Eyebite effect."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.WISDOM,
            dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, _, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"WIS save: {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        if success:
            casting_state = self._get_casting_state(caster)
            if casting_state:
                casting_state.successful_save_target_uuids.add(target.uuid)
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Eyebite ({self.effect_choice})"
            )

        conc = caster.active_conditions.get("Concentrating")

        if self.effect_choice == "asleep":
            effect = EyebiteAsleepEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(effect, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect.applied:
                conc.add_linked_condition(target.uuid, effect.uuid)
            result_text = "Asleep"

        elif self.effect_choice == "panicked":
            effect_p = EyebitePanickedEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=self.spell_dc
            )
            target.add_condition(effect_p, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect_p.applied:
                conc.add_linked_condition(target.uuid, effect_p.uuid)
            result_text = "Panicked"

        else:
            effect_s = SickenedCondition(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=self.spell_dc
            )
            target.add_condition(effect_s, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect_s.applied:
                conc.add_linked_condition(target.uuid, effect_s.uuid)
            result_text = "Sickened"

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Eyebite: {target.name} is {result_text}"
        )

class Eyebite(SpellAction):
    """Grant a repeatable gaze action while concentration lasts.

    The first target can be resolved immediately when the spell is cast. The
    caster also receives Eyebite Strike for later turns, and the marker
    condition links that action to concentration cleanup.
    """
    name: str = Field(default="Eyebite", description="Spell name.")
    description: str = Field(
        default="WIS save or Asleep/Panicked/Sickened, repeatable each turn",
        description="Rules-facing summary of the gaze options.",
    )
    spell_level: int = Field(default=6, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Self action that grants a targeting action.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Self range for casting the ongoing gaze effect.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="VFX projectile metadata.")
    effect_choice: str = Field(default="sickened", description="Initial and repeat strike effect choice.")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Register the granted action and optionally resolve the first strike."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Eyebite"
        )
        if effect_event.canceled:
            return effect_event

        concentration = self.ensure_concentration(effect_event)
        marker = EyebiteCastingState(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name="Eyebite Strike",
        )
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        strike = EyebiteStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            effect_choice=self.effect_choice,
            casting_state_condition_uuid=marker.uuid,
            template=True
        )
        caster.register_condition_action(marker, strike)

        if self.target_entity_uuid and self.target_entity_uuid != caster.uuid:
            first_strike = EyebiteStrike(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=self.target_entity_uuid,
                spell_dc=dc,
                effect_choice=self.effect_choice,
                casting_state_condition_uuid=marker.uuid,
                template=False,
                costs=[],
            )
            first_strike.apply()

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} channels Eyebite - can target a creature each turn"
        )


class FingerOfDeath(SpellAction):
    """Resolve Finger of Death's Constitution save and necrotic damage.

    The engine supports one additional d8 per slot level above 7th.
    """
    name: str = Field(default="Finger of Death", description="Spell name.")
    description: str = Field(default="7d8+30 necrotic, CON save half", description="Rules-facing damage summary.")
    spell_level: int = Field(default=7, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="VFX projectile metadata.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")
    include_self: bool = Field(default=False, description="Whether action discovery includes the caster.")
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    base_damage_dice: int = Field(default=7, description="Base number of d8 damage dice.")
    flat_damage: int = Field(default=30, description="Flat necrotic damage added after the dice roll.")

    def get_damage_dice_count(self) -> int:
        """Return the number of d8 damage dice after upcasting."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Finger of Death's upcast save-for-half damage model."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=8,
            flat_bonus=actor.spell_damage_outcome_bonus() + self.flat_damage,
            damage_type=DamageType.NECROTIC,
            save_ability="constitution",
            half_damage_on_save=True,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight and range for the target."""
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and apply necrotic damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=8, dice_numbers=num_dice, damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )
        damage_roll = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        raw_damage = damage_roll.total + self.flat_damage

        final_damage = raw_damage // 2 if success else raw_damage

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Finger of Death deals {final_damage} necrotic damage to {target.name}{save_text}"
        )


class InflictWounds(SpellAction):
    """Make a melee spell attack for necrotic damage."""
    name: str = Field(default="Inflict Wounds", description="Spell name.")
    description: str = Field(default="Melee spell attack, 3d10 necrotic", description="Rules-facing damage summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Reach range for the melee spell attack.",
    )
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    projectile_type: Optional[str] = Field(default="touch", description="VFX projectile metadata.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")

    def _get_damage_dice_count(self) -> int:
        """Return the number of d10 damage dice after upcasting."""
        return 2 + self.cast_at_level

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Inflict Wounds' melee spell attack damage model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=self._get_damage_dice_count(),
            die_size=10,
            damage_type=DamageType.NECROTIC,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line of sight and melee reach."""
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the spell attack and apply necrotic damage on hit."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )
        if effect_event.canceled:
            return effect_event

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        num_dice = self._get_damage_dice_count()
        is_crit = outcome == AttackOutcome.CRIT
        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC,
        )
        damage_dice = necrotic_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.NECROTIC,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid,
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"{self.name} deals {damage_roll.total} necrotic damage to {target.name}"
        )


class Harm(SpellAction):
    """Resolve Harm's Constitution save and minimum-HP damage cap."""
    name: str = Field(default="Harm", description="Spell name.")
    description: str = Field(
        default="CON save, 14d6 necrotic, half on save, min 1 HP",
        description="Rules-facing damage summary.",
    )
    spell_level: int = Field(default=6, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the target.",
    )
    valid_target_filter: str = Field(default="enemies", description="Action discovery target filter.")
    projectile_type: Optional[str] = Field(default="touch", description="VFX projectile metadata.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Harm's save-for-half necrotic damage model."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=14,
            die_size=6,
            flat_bonus=0,
            damage_type=DamageType.NECROTIC,
            save_ability="constitution",
            half_damage_on_save=True,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save, roll damage, and preserve at least 1 HP."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid,
        )
        _, _, success = target.saving_throw(save_request)

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=14,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=0,
                value_name="Harm Damage",
            ),
            damage_type=DamageType.NECROTIC,
        )
        damage_roll = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        raw_damage = damage_roll.total
        final_damage = raw_damage // 2 if success else raw_damage

        current_hp = target.get_hp()
        if final_damage >= current_hp:
            final_damage = max(0, current_hp - 1)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Harm vs {target.name}: {'SAVE' if success else 'FAIL'}"
        )
        if effect_event.canceled:
            return effect_event

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid,
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Harm deals {final_damage} necrotic to {target.name}{save_text} (min 1 HP)"
        )

_ABILITY_TO_SKILLS: Dict[AbilityName, List[SkillName]] = {}
for _skill, _ability in SKILL_TO_ABILITY.items():
    _ABILITY_TO_SKILLS.setdefault(_ability, []).append(_skill)


class AbilityCurseEffect(BaseCondition):
    """Apply disadvantage to one ability's saving throw and linked skills."""
    name: str = Field(default="Bestow Curse", description="Condition name.")
    description: str = Field(
        default="Cursed - disadvantage on checks and saves with one ability",
        description="Rules-facing condition summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Condition category used by condition filtering.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE},
        description="Condition tags used by cleanup and spell interactions.",
    )
    cursed_ability: AbilityName = Field(default=AbilityName.STRENGTH, description="Ability affected by the curse.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the ability-save and linked-skill disadvantage modifiers."""
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        save = target.saving_throws.get_saving_throw(self.cursed_ability)
        mod_uuid = save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Bestow Curse (save)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((save.bonus.uuid, mod_uuid))

        for skill_name in _ABILITY_TO_SKILLS.get(self.cursed_ability, []):
            skill = target.skill_set.get_skill(skill_name)
            mod_uuid = skill.skill_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Bestow Curse (skill)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=self.target_entity_uuid
                )
            )
            outs.append((skill.skill_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Bestow Curse: disadvantage on {self.cursed_ability} checks and saves"
        )
        return outs, [], [], [], effect_event


class AttackCurseEffect(BaseCondition):
    """Apply disadvantage when the cursed target attacks the caster."""
    name: str = Field(default="Bestow Curse", description="Condition name.")
    description: str = Field(
        default="Cursed - disadvantage on attacks against the caster",
        description="Rules-facing condition summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Condition category used by condition filtering.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster protected by the attack curse.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the contextual attack disadvantage modifier."""
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        caster_uuid = self.caster_uuid

        def attack_curse_check(
            source_entity_uuid: UUID,
            target_entity_uuid: Optional[UUID],
            context: Optional[Dict[str, Any]]
        ) -> Optional[AdvantageModifier]:
            """Disadvantage when attacking the caster."""
            _ = context
            if target_entity_uuid == caster_uuid:
                return AdvantageModifier(
                    name="Bestow Curse (attack)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=source_entity_uuid,
                    target_entity_uuid=target_entity_uuid if target_entity_uuid else source_entity_uuid
                )
            return None

        mod_uuid = target.equipment.attack_bonus.self_contextual.add_advantage_modifier(
            ContextualAdvantageModifier(
                name="Bestow Curse (attack)",
                callable=attack_curse_check,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: disadvantage on attacks against caster"
        )
        return outs, [], [], [], effect_event


class InactionCurseEffect(BaseCondition):
    """Apply turn-start action denial with turn-end cleanup."""
    name: str = Field(default="Bestow Curse", description="Condition name.")
    description: str = Field(
        default="Cursed - WIS save at turn start or waste action",
        description="Rules-facing condition summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Condition category used by condition filtering.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster that owns the turn-start save DC.")
    spell_dc: int = Field(default=10, description="Wisdom save DC for the turn-start check.")
    _action_constraint_uuid: Optional[UUID] = PrivateAttr(default=None)
    _action_value_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Register the turn-start and turn-end handlers."""
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        turn_start_handler = self._create_turn_start_handler()
        target.add_event_handler(turn_start_handler)
        handler_uuids.append(turn_start_handler.uuid)

        turn_end_handler = self._create_turn_end_handler()
        target.add_event_handler(turn_end_handler)
        handler_uuids.append(turn_end_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: WIS save at turn start or lose action"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_turn_start_handler(self) -> EventHandler:
        """Create the handler that can spend the target's action."""
        assert self.target_entity_uuid is not None
        target_uuid: UUID = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        dc = self.spell_dc
        curse_condition = self

        def turn_start_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            curse = target.active_conditions.get("Bestow Curse")
            if not curse or curse.uuid != curse_condition.uuid:
                return None

            caster = Entity.get(caster_uuid) if caster_uuid else None
            if not caster:
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.WISDOM,
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if not success:
                constraint_uuid = target.action_economy.actions.self_static.add_max_constraint(
                    constraint=NumericalModifier(
                        name="Bestow Curse (inaction)",
                        value=0,
                        source_entity_uuid=target_uuid,
                        target_entity_uuid=target_uuid
                    )
                )
                curse_condition._action_constraint_uuid = constraint_uuid
                curse_condition._action_value_uuid = target.action_economy.actions.uuid

            return None

        return EventHandler(
            name=f"Bestow Curse Turn Start ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=turn_start_processor
        )

    def _create_turn_end_handler(self) -> EventHandler:
        """Create the handler that clears one-turn action denial."""
        assert self.target_entity_uuid is not None
        target_uuid: UUID = self.target_entity_uuid
        curse_condition = self

        def turn_end_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if event.source_entity_uuid != target_uuid:
                return None

            if curse_condition._action_constraint_uuid and curse_condition._action_value_uuid:
                value = ModifiableValue.get(curse_condition._action_value_uuid)
                if value and isinstance(value, ModifiableValue):
                    value.self_static.remove_max_constraint(curse_condition._action_constraint_uuid)
                curse_condition._action_constraint_uuid = None
                curse_condition._action_value_uuid = None

            return None

        return EventHandler(
            name=f"Bestow Curse Turn End ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=turn_end_processor
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up a lingering action constraint when the curse is removed."""
        if self._action_constraint_uuid and self._action_value_uuid:
            value = ModifiableValue.get(self._action_value_uuid)
            if value and isinstance(value, ModifiableValue):
                value.self_static.remove_max_constraint(self._action_constraint_uuid)
            self._action_constraint_uuid = None
            self._action_value_uuid = None
        return super()._remove(event)


class DamageCurseEffect(BaseCondition):
    """Add necrotic damage to the caster's attacks against the cursed target."""
    name: str = Field(default="Bestow Curse", description="Condition name.")
    description: str = Field(
        default="Cursed - caster deals extra 1d8 necrotic on hit",
        description="Rules-facing condition summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Condition category used by condition filtering.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE},
        description="Condition tags used by cleanup and spell interactions.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster whose attacks gain bonus damage.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Register the attack-damage handler on the caster."""
        if not self.caster_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No caster UUID")

        caster = Entity.get(self.caster_uuid)
        if not caster or not isinstance(caster, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Caster not found")

        handler_uuids: List[UUID] = []

        handler = self._create_damage_handler()
        caster.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: caster deals +1d8 necrotic on attack"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_damage_handler(self) -> EventHandler:
        """Create the handler that adds necrotic damage after a hit."""
        assert self.caster_uuid is not None
        assert self.target_entity_uuid is not None
        caster_uuid: UUID = self.caster_uuid
        cursed_uuid: UUID = self.target_entity_uuid
        curse_condition = self

        def damage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, DamageRollResultEvent):
                return None
            if source_entity_uuid != caster_uuid:
                return None
            if event.source_entity_uuid != caster_uuid:
                return None
            if event.target_entity_uuid != cursed_uuid:
                return None
            if event.attack_outcome not in {
                AttackOutcome.HIT,
                AttackOutcome.CRIT,
            }:
                return None

            target = Entity.get(cursed_uuid)
            if not target:
                return None
            curse = target.active_conditions.get("Bestow Curse")
            if not curse or curse.uuid != curse_condition.uuid:
                return None

            bonus = ModifiableValue.create(
                source_entity_uuid=caster_uuid,
                base_value=0,
                value_name="Bestow Curse Damage Bonus",
            )
            damage = Damage(
                name="Bestow Curse",
                source_entity_uuid=caster_uuid,
                target_entity_uuid=cursed_uuid,
                damage_dice=8,
                dice_numbers=1,
                damage_bonus=bonus,
                damage_type=DamageType.NECROTIC,
            )
            roll = damage.get_dice(
                attack_outcome=event.attack_outcome,
                crit_extra_dice=0,
            ).roll
            return event.append_damage_roll(
                damage,
                roll,
                "Bestow Curse",
                "+1d8 necrotic damage",
            )

        return EventHandler(
            name=f"Bestow Curse Damage ({cursed_uuid})",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster_uuid
                )
            ],
            event_processor=damage_processor
        )


class BestowCurse(SpellAction):
    """Apply one of four curse effects after a failed Wisdom save.

    The supported options are ability disadvantage, attack disadvantage against
    the caster, turn-start action denial, and bonus necrotic damage from the
    caster's attacks.
    """
    name: str = Field(default="Bestow Curse", description="Spell name.")
    description: str = Field(
        default="Touch: WIS save or be cursed (concentration)",
        description="Rules-facing curse summary.",
    )
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="necromancy", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Single creature target.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Reach range for the touch spell.",
    )
    projectile_type: Optional[str] = Field(default="touch", description="VFX projectile metadata.")
    curse_option: int = Field(default=1, description="Selected curse option from 1 through 4.")
    cursed_ability: AbilityName = Field(default=AbilityName.STRENGTH, description="Ability affected when option 1 is used.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare the selected Bestow Curse branch."""
        if not isinstance(actor, Entity):
            return None
        option = max(1, min(4, self.curse_option))
        condition_fact, condition_keys = {
            1: (
                f"selected_target.condition.bestow_curse.{self.cursed_ability}",
                frozenset({"dnd.spells.necromancy.AbilityCurseEffect"}),
            ),
            2: (
                "selected_target.condition.bestow_curse.attack",
                frozenset({"dnd.spells.necromancy.AttackCurseEffect"}),
            ),
            3: (
                "selected_target.condition.bestow_curse.inaction",
                frozenset({"dnd.spells.necromancy.InactionCurseEffect"}),
            ),
            4: (
                "selected_target.condition.bestow_curse.damage",
                frozenset({"dnd.spells.necromancy.DamageCurseEffect"}),
            ),
        }[option]
        return ActionTargetEffectProfile(
            semantic_id=f"control.bestow_curse.option_{option}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"control.bestow_curse.option_{option}",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=(condition_fact,),
                    condition_semantic_keys=condition_keys,
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target visibility, touch range, and curse option."""
        if self.curse_option < 1 or self.curse_option > 4:
            return declaration_event.cancel(status_message=f"Invalid curse option: {self.curse_option}")

        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve the save and attach the selected curse to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"Requesting WIS save DC {dc}"
        )
        if effect_event.canceled:
            return effect_event

        concentration = self.ensure_concentration(effect_event)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.WISDOM,
            dc=dc,
            parent_event=effect_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.with_updates(
            save_success=success,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            self._close_concentration(effect_event)
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Bestow Curse — {target.name} saved"
            )

        curse: BaseCondition
        if self.curse_option == 1:
            curse = AbilityCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                cursed_ability=self.cursed_ability
            )
        elif self.curse_option == 2:
            curse = AttackCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid
            )
        elif self.curse_option == 3:
            curse = InactionCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc
            )
        else:
            curse = DamageCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid
            )

        target.add_condition(curse, parent_event=effect_event)

        if curse.applied:
            concentration.add_linked_condition(target.uuid, curse.uuid)

        self._close_concentration(effect_event)

        option_desc = {
            1: f"disadvantage on {self.cursed_ability} checks/saves",
            2: "disadvantage on attacks vs caster",
            3: "WIS save or lose action each turn",
            4: "+1d8 necrotic on caster's attacks"
        }
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Bestow Curse on {target.name}: {option_desc[self.curse_option]}"
        )
