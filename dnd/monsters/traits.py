"""Reusable SRD monster traits implemented with engine primitives."""

from __future__ import annotations

from typing import Callable, Literal, Optional, Tuple, List, cast
from uuid import UUID

from pydantic import Field

from dnd.actions import Attack, AttackEvent, Dash, Disengage, Hide, Move, build_weapon_attack_outcome_profile, entity_action_economy_cost_applier, entity_action_economy_cost_evaluator, validate_line_of_sight
from dnd.blocks.equipment import Damage
from dnd.conditions import Paralyzed, Prone
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
    DamageRollProfile,
    ActionOutcomeProfile,
    ActionSelfSetupProfile,
    ActionSetupDuration,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    BaseAction,
    BaseCost,
    Cost,
    CostType,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.content import ContentKind
from dnd.core.dice import AttackOutcome, Dice, RollType
from dnd.core.events import (
    DamageRollResultEvent,
    D20RollResultEvent,
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Range,
    RangeType,
    TakeDamageEvent,
    Trigger,
    WeaponSlot,
)
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ContextualAdvantageModifier, DamageType, NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.classes.barbarian import RecklessAttack
from dnd.core.base_conditions import DurationType


DamageDieValue = Literal[4, 6, 8, 10, 12, 20]


def register_pack_tactics(entity: Entity) -> None:
    """Register SRD Pack Tactics on an entity."""
    _add_feature_once(entity, PackTacticsFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))


def register_sunlight_sensitivity(entity: Entity) -> None:
    """Register SRD Sunlight Sensitivity on an entity."""
    _add_feature_once(entity, SunlightSensitivityFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))


def register_dark_devotion(entity: Entity) -> None:
    """Register SRD Dark Devotion on an entity."""
    _add_feature_once(
        entity,
        ConditionalSaveAdvantageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Dark Devotion",
            condition_contexts=("Charmed", "Frightened", "Charm Person", "Fear"),
        ),
    )


def register_brave(entity: Entity) -> None:
    """Register SRD Brave on an entity."""
    _add_feature_once(
        entity,
        ConditionalSaveAdvantageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Brave",
            condition_contexts=("Frightened", "Fear"),
        ),
    )


def register_keen_perception(entity: Entity, *, name: str, modes: tuple[str, ...]) -> None:
    """Register a keen-senses perception advantage feature."""
    _add_feature_once(
        entity,
        KeenPerceptionFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=name,
            modes=modes,
        ),
    )


def register_cunning_action(entity: Entity) -> None:
    """Register Spy Cunning Action bonus-action options."""
    _register_action_once(entity, Dash(source_entity_uuid=entity.uuid, template=True, name="Cunning Action: Dash", alt_cost_type="bonus_actions"))
    _register_action_once(entity, Disengage(source_entity_uuid=entity.uuid, template=True, name="Cunning Action: Disengage", alt_cost_type="bonus_actions"))
    _register_action_once(entity, Hide(source_entity_uuid=entity.uuid, template=True, name="Cunning Action: Hide", alt_cost_type="bonus_actions"))


def register_aggressive(entity: Entity) -> None:
    """Register Orc Aggressive as bonus-action enemy-closing movement."""
    _register_action_once(entity, AggressiveMoveAction(source_entity_uuid=entity.uuid, template=True))


def register_reckless(entity: Entity) -> None:
    """Register SRD Reckless using the existing engine Reckless Attack action."""
    _register_action_once(entity, RecklessAttack(source_entity_uuid=entity.uuid, template=True, name="Reckless"))


def register_multiattack(entity: Entity, name: str, attacks: tuple[tuple[WeaponSlot, int], ...]) -> None:
    """Register a monster stat-block Multiattack action."""
    _register_action_once(
        entity,
        MultiattackAction(
            source_entity_uuid=entity.uuid,
            template=True,
            name=name,
            attack_sequence=attacks,
        ),
    )


def register_martial_advantage(entity: Entity) -> None:
    """Register Hobgoblin Martial Advantage."""
    _add_feature_once(
        entity,
        BonusDamageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Martial Advantage",
            dice_numbers=2,
            damage_dice=6,
            requires_adjacent_ally=True,
            once_per_turn=True,
            weapon_only=True,
        ),
    )


def register_sneak_attack(entity: Entity) -> None:
    """Register Spy Sneak Attack."""
    _add_feature_once(
        entity,
        BonusDamageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Sneak Attack",
            dice_numbers=2,
            damage_dice=6,
            requires_sneak_condition=True,
            once_per_turn=True,
            weapon_only=True,
        ),
    )


def register_brute(entity: Entity) -> None:
    """Register SRD Brute-style extra melee weapon die."""
    _add_feature_once(
        entity,
        BonusDamageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Brute",
            dice_numbers=1,
            damage_dice=8,
            melee_only=True,
            weapon_only=True,
        ),
    )


def register_surprise_attack(entity: Entity) -> None:
    """Register Bugbear Surprise Attack for unseen opening strikes."""
    _add_feature_once(
        entity,
        BonusDamageFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Surprise Attack",
            dice_numbers=2,
            damage_dice=6,
            requires_unseen_attacker=True,
            once_per_turn=True,
            weapon_only=True,
        ),
    )


def register_bite_prone_rider(entity: Entity, dc: int) -> None:
    """Register wolf-style bite prone rider."""
    _add_feature_once(
        entity,
        HitSaveRiderFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Bite Prone Rider",
            weapon_names=("Bite",),
            save_ability="strength",
            save_dc=dc,
            condition_name="Prone",
        ),
    )


def register_ghoul_claws_paralysis(entity: Entity) -> None:
    """Register Ghoul claw paralysis rider."""
    _add_feature_once(
        entity,
        HitSaveRiderFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Ghoul Claws Paralysis",
            weapon_names=("Claws",),
            save_ability="constitution",
            save_dc=10,
            condition_name="Ghoul Paralysis",
            excluded_creature_types=("undead",),
        ),
    )


def register_undead_fortitude(entity: Entity) -> None:
    """Register SRD Undead Fortitude."""
    _add_feature_once(entity, UndeadFortitudeFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))


def register_parry(entity: Entity, ac_bonus: int = 2) -> None:
    """Register SRD Parry reaction."""
    _add_feature_once(entity, ParryFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid, ac_bonus=ac_bonus))


def register_divine_eminence(entity: Entity) -> None:
    """Register Priest Divine Eminence."""
    _register_action_once(entity, DivineEminenceAction(source_entity_uuid=entity.uuid, template=True))


def register_leadership(entity: Entity) -> None:
    """Register Knight Leadership."""
    _register_action_once(entity, LeadershipAction(source_entity_uuid=entity.uuid, template=True))


def register_rampage(entity: Entity) -> None:
    """Register Gnoll Rampage trigger."""
    _add_feature_once(entity, RampageFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))


def register_natural_bite(entity: Entity, *, name: str = "Bite") -> None:
    """Register a natural bite attack that does not occupy equipment slots."""
    _register_action_once(
        entity,
        NaturalAttack(
            source_entity_uuid=entity.uuid,
            template=True,
            name=name,
            natural_damage_dice=4,
            natural_dice_numbers=1,
            natural_damage_type=DamageType.PIERCING,
            natural_range=Range(type=RangeType.REACH, normal=5),
        ),
    )


class PackTacticsFeature(BaseCondition):
    """Feature condition that grants contextual attack advantage."""

    name: str = Field(default="Pack Tactics", description="Condition name.")
    description: str = Field(default="Advantage on attacks when an ally is adjacent to the target.", description="Rules summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Pack Tactics owner not found")
        modifier = ContextualAdvantageModifier(
            name="Pack Tactics",
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            callable=pack_tactics_advantage,
        )
        mod_uuid = owner.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has Pack Tactics")
        return [(owner.equipment.attack_bonus.uuid, mod_uuid)], [], [], [], effect_event


def pack_tactics_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID], context: Optional[dict]) -> Optional[AdvantageModifier]:
    """Return attack advantage when an ally is adjacent to the target."""
    _ = context
    if target_entity_uuid is None:
        return None
    source = Entity.get(source_entity_uuid)
    target = Entity.get(target_entity_uuid)
    if not source or not target:
        return None
    for candidate in Entity.get_all_entities():
        if candidate.uuid in {source.uuid, target.uuid}:
            continue
        if not source.is_ally(candidate):
            continue
        if "Incapacitated" in candidate.active_conditions or "Dead" in candidate.active_conditions:
            continue
        if candidate.senses.get_feet_distance(target.position) <= 5:
            return AdvantageModifier(name="Pack Tactics", value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)
    return None


class SunlightSensitivityFeature(BaseCondition):
    """Feature condition for explicit sunlight disadvantage contexts."""

    name: str = Field(default="Sunlight Sensitivity", description="Condition name.")
    description: str = Field(default="Disadvantage on attacks and sight Perception in sunlight.", description="Rules summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Sunlight Sensitivity owner not found")
        attack_mod = ContextualAdvantageModifier(
            name="Sunlight Sensitivity",
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            callable=_sunlight_attack_disadvantage,
        )
        perception_mod = ContextualAdvantageModifier(
            name="Sunlight Sensitivity",
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            callable=_sunlight_perception_disadvantage,
        )
        attack_uuid = owner.equipment.attack_bonus.self_contextual.add_advantage_modifier(attack_mod)
        perception_uuid = owner.skill_set.perception.skill_bonus.self_contextual.add_advantage_modifier(perception_mod)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has Sunlight Sensitivity")
        return [(owner.equipment.attack_bonus.uuid, attack_uuid), (owner.skill_set.perception.skill_bonus.uuid, perception_uuid)], [], [], [], effect_event


def _sunlight_attack_disadvantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID], context: Optional[dict]) -> Optional[AdvantageModifier]:
    """Return disadvantage when roll context explicitly marks sunlight."""
    if context and context.get("sunlight") is True:
        return AdvantageModifier(name="Sunlight Sensitivity", value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


def _sunlight_perception_disadvantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID], context: Optional[dict]) -> Optional[AdvantageModifier]:
    """Return disadvantage for sight Perception in explicit sunlight."""
    if context and context.get("sunlight") is True and context.get("sense") in {None, "sight"}:
        return AdvantageModifier(name="Sunlight Sensitivity", value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


class ConditionalSaveAdvantageFeature(BaseCondition):
    """Contextual saving throw advantage against named condition contexts."""

    name: str = Field(default="Conditional Save Advantage", description="Condition name.")
    description: str = Field(default="Advantage on specific saving throws.", description="Rules summary.")
    condition_contexts: tuple[str, ...] = Field(default_factory=tuple, description="Condition contexts that gain advantage.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message=f"{self.name} owner not found")
        outs: List[Tuple[UUID, UUID]] = []
        for save in (
            owner.saving_throws.strength_saving_throw,
            owner.saving_throws.dexterity_saving_throw,
            owner.saving_throws.constitution_saving_throw,
            owner.saving_throws.intelligence_saving_throw,
            owner.saving_throws.wisdom_saving_throw,
            owner.saving_throws.charisma_saving_throw,
        ):
            modifier = ContextualAdvantageModifier(
                name=self.name,
                source_entity_uuid=owner.uuid,
                target_entity_uuid=owner.uuid,
                callable=_condition_context_save_advantage(self.condition_contexts, self.name),
            )
            mod_uuid = save.bonus.self_contextual.add_advantage_modifier(modifier)
            outs.append((save.bonus.uuid, mod_uuid))
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has {self.name}")
        return outs, [], [], [], effect_event


def _condition_context_save_advantage(condition_contexts: tuple[str, ...], name: str) -> Callable[[UUID, Optional[UUID], Optional[dict]], Optional[AdvantageModifier]]:
    """Build a save-advantage callable for configured condition contexts."""
    configured = set(condition_contexts)

    def evaluate(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID], context: Optional[dict]) -> Optional[AdvantageModifier]:
        roll_context = context or {}
        condition_context = roll_context.get("condition_context")
        if condition_context is not None and condition_context in configured:
            return AdvantageModifier(name=name, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
        return None

    return evaluate


class KeenPerceptionFeature(BaseCondition):
    """Contextual Perception advantage for specific sense modes."""

    name: str = Field(default="Keen Perception", description="Condition name.")
    description: str = Field(default="Advantage on Perception with configured senses.", description="Rules summary.")
    modes: tuple[str, ...] = Field(default_factory=tuple, description="Sense modes that activate the trait.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Keen Perception owner not found")
        modifier = ContextualAdvantageModifier(
            name=self.name,
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            callable=_keen_perception_advantage(self.modes, self.name),
        )
        mod_uuid = owner.skill_set.perception.skill_bonus.self_contextual.add_advantage_modifier(modifier)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has {self.name}")
        return [(owner.skill_set.perception.skill_bonus.uuid, mod_uuid)], [], [], [], effect_event


def _keen_perception_advantage(modes: tuple[str, ...], name: str) -> Callable[[UUID, Optional[UUID], Optional[dict]], Optional[AdvantageModifier]]:
    """Build a Perception advantage callable for configured senses."""
    keen_modes = set(modes)

    def evaluate(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID], context: Optional[dict]) -> Optional[AdvantageModifier]:
        roll_context = context or {}
        requested = roll_context.get("sense")
        if requested is None or requested in keen_modes:
            return AdvantageModifier(name=name, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
        return None

    return evaluate


class AggressiveMoveAction(Move):
    """Bonus-action movement that must move toward a visible enemy."""

    name: str = Field(default="Aggressive", description="Action name.")
    description: str = Field(default="Move up to speed toward a visible hostile as a bonus action.", description="Rules summary.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Aggressive Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="Bonus action cost.")

    def pre_validate(self) -> bool:
        """Return whether a visible hostile exists."""
        actor = Entity.get(self.source_entity_uuid)
        if not actor:
            return False
        return any(
            actor.is_enemy(entity)
            for entity_uuid in actor.senses.entities
            if (entity := Entity.get(entity_uuid)) is not None
        )

    def _validate(self, declaration_event):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None or self.end_position is None:
            return declaration_event.cancel(status_message="Aggressive requires actor and destination")
        enemies = [
            entity
            for entity_uuid in actor.senses.entities
            if (entity := Entity.get(entity_uuid)) is not None and actor.is_enemy(entity)
        ]
        if not enemies:
            return declaration_event.cancel(status_message="No visible enemy for Aggressive")
        before = min(actor.senses.get_feet_distance(enemy.position) for enemy in enemies)
        after = min((abs(self.end_position[0] - enemy.position[0]) + abs(self.end_position[1] - enemy.position[1])) * 5 for enemy in enemies)
        if after >= before:
            return declaration_event.cancel(status_message="Aggressive destination must move closer to a visible enemy")
        return super()._validate(declaration_event)


class MultiattackAction(BaseAction):
    """Monster stat-block action that composes existing weapon attacks."""

    name: str = Field(default="Multiattack", description="Action name.")
    description: str = Field(default="Make multiple stat-block weapon attacks.", description="Rules summary.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Multiattack targets one entity for v1.")
    action_category: ActionCategory = Field(default=ActionCategory.ATTACK, description="Attack category.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Multiattack Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="One action cost.")
    attack_sequence: tuple[tuple[WeaponSlot, int], ...] = Field(default_factory=tuple, description="Weapon slots and counts.")

    def get_outcome_profile(self, actor: object) -> Optional[ActionOutcomeProfile]:
        """Return a repeated-attack profile when every attack shares one shape."""
        if not isinstance(actor, Entity):
            return None
        profiles: list[ActionOutcomeProfile] = []
        for slot, count in self.attack_sequence:
            profile = build_weapon_attack_outcome_profile(actor, slot)
            if profile is None:
                return None
            profiles.extend(profile for _ in range(count))
        if not profiles:
            return None
        first = profiles[0]
        comparable = first.model_copy(update={"effect_id": None, "applications": 1})
        if any(profile.model_copy(update={"effect_id": None, "applications": 1}) != comparable for profile in profiles[1:]):
            return None
        return first.model_copy(update={
            "effect_id": f"multiattack.{_fact_slug(self.name)}",
            "applications": len(profiles),
        })

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        actor = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if actor is None or target is None:
            return declaration_event.cancel(status_message="Multiattack requires actor and target")
        for slot, _count in self.attack_sequence:
            attack = Attack(source_entity_uuid=actor.uuid, target_entity_uuid=target.uuid, weapon_slot=slot, costs=[], use_register=False)
            if attack.pre_validate():
                return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Multiattack validated")
        return declaration_event.cancel(status_message="No legal attacks for Multiattack")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        actor = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if actor is None or target is None:
            return execution_event.cancel(status_message="Multiattack actor or target missing")
        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message=f"{actor.name} uses {self.name}")
        for slot, count in self.attack_sequence:
            for _ in range(count):
                if target.get_hp() <= 0:
                    break
                attack = Attack(
                    name=f"{self.name}: Attack",
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=target.uuid,
                    weapon_slot=slot,
                    costs=[],
                    use_register=False,
                )
                if attack.pre_validate():
                    attack.apply(parent_event=effect_event)
        return effect_event.phase_to(EventPhase.COMPLETION, status_message=f"{self.name} completed")

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class NaturalAttack(Attack):
    """Attack template for natural weapons that are not equipment."""

    name: str = Field(default="Natural Attack", description="Natural attack name.")
    weapon_slot: WeaponSlot = Field(default=WeaponSlot.MELEE_MAIN, description="Proxy slot used by attack plumbing.")
    natural_damage_dice: DamageDieValue = Field(default=4, description="Natural weapon die size.")
    natural_dice_numbers: int = Field(default=1, description="Number of natural weapon dice.")
    natural_damage_type: DamageType = Field(default=DamageType.PIERCING, description="Natural weapon damage type.")
    natural_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Natural weapon range.")

    def get_outcome_profile(self, actor: object) -> Optional[ActionOutcomeProfile]:
        """Return natural-weapon damage instead of the proxy equipped slot."""
        if not isinstance(actor, Entity):
            return None
        old_weapon = actor.equipment.weapon_melee_main
        old_damage_dice = actor.equipment.unarmed_damage_dice
        old_dice_numbers = actor.equipment.unarmed_dice_numbers
        old_damage_type = actor.equipment.unarmed_damage_type
        try:
            actor.equipment.weapon_melee_main = None
            actor.equipment.unarmed_damage_dice = self.natural_damage_dice
            actor.equipment.unarmed_dice_numbers = self.natural_dice_numbers
            actor.equipment.unarmed_damage_type = self.natural_damage_type
            profile = build_weapon_attack_outcome_profile(
                actor,
                self.weapon_slot,
                self.override_ability,
            )
            if profile is None:
                return None
            return profile.model_copy(update={"effect_id": f"natural_attack.{self.name.lower().replace(' ', '_')}"})
        finally:
            actor.equipment.weapon_melee_main = old_weapon
            actor.equipment.unarmed_damage_dice = old_damage_dice
            actor.equipment.unarmed_dice_numbers = old_dice_numbers
            actor.equipment.unarmed_damage_type = old_damage_type

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[AttackEvent]:
        """Create an attack event using natural-weapon metadata."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        return AttackEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_entity.name if source_entity else None,
            target_entity_name=target_entity.name if target_entity else None,
            weapon_name=self.name,
            override_ability=self.override_ability,
            damage_types=[self.natural_damage_type],
            range=self.natural_range,
        )

    def _validate(self, declaration_event: AttackEvent) -> Optional[AttackEvent]:
        """Validate natural attack range, line of sight, and ranged pressure."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(declaration_event.target_entity_uuid) if declaration_event.target_entity_uuid else None
        if source is None or target is None:
            return declaration_event.cancel(status_message=f"{self.name} requires source and target")

        distance_feet = source.senses.get_feet_distance(target.position)
        is_long_range = False
        if self.natural_range.type == RangeType.RANGE:
            if distance_feet <= self.natural_range.normal:
                pass
            elif self.natural_range.long is not None and distance_feet <= self.natural_range.long:
                is_long_range = True
            else:
                return declaration_event.cancel(status_message=f"Target entity not in range for {self.name}")
        elif distance_feet > self.natural_range.normal:
            return declaration_event.cancel(status_message=f"Target entity not in reach for {self.name}")

        range_event = declaration_event.phase_to(
            new_phase=EventPhase.DECLARATION,
            status_message=f"Validated range for {self.name}",
            range=self.natural_range,
            is_long_range=is_long_range,
        )
        los_event = validate_line_of_sight(range_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event
        ranged_event = Attack.check_ranged_conditions(los_event, self.source_entity_uuid)
        if ranged_event is None or ranged_event.canceled:
            return ranged_event
        return ranged_event.phase_to(EventPhase.EXECUTION, status_message=f"Attack validated for {self.name}")

    def _apply(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Resolve natural attack damage through the normal attack pipeline."""
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return execution_event.cancel(status_message=f"Source entity not found for {self.name}")

        old_weapon = source.equipment.weapon_melee_main
        old_damage_dice = source.equipment.unarmed_damage_dice
        old_dice_numbers = source.equipment.unarmed_dice_numbers
        old_damage_type = source.equipment.unarmed_damage_type
        try:
            source.equipment.weapon_melee_main = None
            source.equipment.unarmed_damage_dice = self.natural_damage_dice
            source.equipment.unarmed_dice_numbers = self.natural_dice_numbers
            source.equipment.unarmed_damage_type = self.natural_damage_type
            return Attack.attack_consequences(execution_event, self.source_entity_uuid)
        finally:
            source.equipment.weapon_melee_main = old_weapon
            source.equipment.unarmed_damage_dice = old_damage_dice
            source.equipment.unarmed_dice_numbers = old_dice_numbers
            source.equipment.unarmed_damage_type = old_damage_type


class BonusDamageFeature(BaseCondition):
    """Feature that injects extra damage dice into weapon hits."""

    name: str = Field(default="Bonus Damage", description="Condition name.")
    description: str = Field(default="Adds conditional bonus damage.", description="Rules summary.")
    dice_numbers: int = Field(default=1, description="Extra dice count.")
    damage_dice: DamageDieValue = Field(default=6, description="Extra die size.")
    damage_type: Optional[DamageType] = Field(default=None, description="Override damage type.")
    requires_adjacent_ally: bool = Field(default=False, description="Whether target must be adjacent to an ally.")
    requires_sneak_condition: bool = Field(default=False, description="Whether Sneak Attack conditions are required.")
    requires_unseen_attacker: bool = Field(default=False, description="Whether the attacker must be hidden or unseen.")
    once_per_turn: bool = Field(default=False, description="Whether only one use per turn is allowed.")
    melee_only: bool = Field(default=False, description="Whether only reach attacks qualify.")
    weapon_only: bool = Field(default=True, description="Whether only weapon damage events qualify.")

    def get_action_damage_roll_profiles(self, action: object, actor: object) -> tuple[DamageRollProfile, ...]:
        """Declare actor-known bonus damage when it is not target-dependent."""
        if not isinstance(actor, Entity) or not isinstance(action, Attack):
            return ()
        if self.once_per_turn and f"{self.name} Used" in actor.active_conditions:
            return ()
        if self.requires_adjacent_ally or self.requires_sneak_condition or self.requires_unseen_attacker:
            return ()
        if self.melee_only:
            attack_range = action.natural_range if isinstance(action, NaturalAttack) else actor.get_weapon_range(action.weapon_slot)
            if attack_range.type != RangeType.REACH:
                return ()
        return (
            DamageRollProfile(
                dice_count=self.dice_numbers,
                die_size=self.damage_dice,
                flat_bonus=0,
                damage_type=(self.damage_type or _action_primary_damage_type(actor, action)).value,
            ),
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message=f"{self.name} owner not found")
        handler = EventHandler(
            name=self.name,
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.DAMAGE_ROLL_RESULT, event_phase=EventPhase.EFFECT, event_source_entity_uuid=owner.uuid)],
            event_processor=self._processor,
        )
        reset = EventHandler(
            name=f"{self.name} Reset",
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT, event_source_entity_uuid=owner.uuid)],
            event_processor=self._reset_processor,
        )
        owner.add_event_handler(handler)
        owner.add_event_handler(reset)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has {self.name}")
        return [], [handler.uuid, reset.uuid], [], [], effect_event

    def _reset_processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        owner = Entity.get(source_entity_uuid)
        if owner and f"{self.name} Used" in owner.active_conditions:
            owner.remove_condition(f"{self.name} Used", parent_event=event)
        return event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        if not isinstance(event, DamageRollResultEvent):
            return event
        owner = Entity.get(source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if owner is None or target is None:
            return event
        if self.once_per_turn and f"{self.name} Used" in owner.active_conditions:
            return event
        if event.attack_outcome not in {AttackOutcome.HIT, AttackOutcome.CRIT}:
            return event
        if self.melee_only and owner.get_weapon_range(event.weapon_slot).type != RangeType.REACH:
            return event
        if self.requires_adjacent_ally and not _has_adjacent_ally(owner, target):
            return event
        if self.requires_sneak_condition and not _has_sneak_attack_condition(owner, target, event):
            return event
        if self.requires_unseen_attacker and not _is_unseen_attacker(owner, target):
            return event
        damage_type = self.damage_type or (event.damages[0].damage_type if event.damages else DamageType.PIERCING)
        bonus = ModifiableValue.create(source_entity_uuid=owner.uuid, base_value=0, value_name=f"{self.name} Bonus")
        dice = Dice(count=self.dice_numbers, value=self.damage_dice, bonus=bonus, roll_type=RollType.DAMAGE, attack_outcome=event.attack_outcome)
        roll = dice.roll
        event.final_rolls.append(roll)
        event.original_rolls.append(roll)
        event.damages.append(
            Damage(
                damage_type=damage_type,
                dice_numbers=self.dice_numbers,
                damage_dice=self.damage_dice,
                damage_bonus=bonus,
                source_entity_uuid=owner.uuid,
                target_entity_uuid=target.uuid,
            )
        )
        event.roll_modifications.append((self.name, len(event.final_rolls) - 1, 0, roll.total, f"+{self.dice_numbers}d{self.damage_dice}"))
        if self.once_per_turn:
            owner.add_condition(SimpleMarkerCondition(name=f"{self.name} Used", source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid), parent_event=event)
        return event


class SimpleMarkerCondition(BaseCondition):
    """No-op marker condition."""

    name: str = Field(default="Marker", description="Condition name.")
    description: str = Field(default="Internal marker.", description="Rules summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{self.name} applied")


class HitSaveRiderFeature(BaseCondition):
    """Feature that applies a save-based condition rider after a named hit."""

    name: str = Field(default="Hit Save Rider", description="Condition name.")
    weapon_names: tuple[str, ...] = Field(default_factory=tuple, description="Weapon names that trigger the rider.")
    save_ability: str = Field(default="strength", description="Saving throw ability.")
    save_dc: int = Field(default=10, description="Saving throw DC.")
    condition_name: str = Field(default="Prone", description="Condition to apply.")
    excluded_creature_types: tuple[str, ...] = Field(default_factory=tuple, description="Creature types excluded from the rider.")

    def get_action_target_effect_profile(self, action: object, actor: object) -> Optional[ActionTargetEffectProfile]:
        """Declare the save-based rider carried by matching attack actions."""
        if not isinstance(actor, Entity) or not isinstance(action, Attack):
            return None
        weapon_name = _attack_weapon_name(actor, action)
        if weapon_name not in self.weapon_names:
            return None
        condition_keys = {
            "Prone": frozenset({"dnd.conditions.Prone"}),
            "Ghoul Paralysis": frozenset({"dnd.monsters.traits.GhoulParalysisEffect", "dnd.conditions.Paralyzed"}),
        }.get(self.condition_name, frozenset({f"condition.{_fact_slug(self.condition_name)}"}))
        return ActionTargetEffectProfile(
            semantic_id=f"attack.hit_rider.{_fact_slug(self.condition_name)}",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id=f"control.{_fact_slug(self.condition_name)}",
                    disposition=TargetEffectDisposition.HARMFUL,
                    excluded_creature_types=frozenset(self.excluded_creature_types),
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=self.save_dc,
                    save_ability=self.save_ability,
                    condition_fact_ids=(f"selected_target.condition.{_fact_slug(self.condition_name)}",),
                    condition_semantic_keys=condition_keys,
                ),
            ),
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message=f"{self.name} owner not found")
        handler = EventHandler(
            name=self.name,
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT, event_source_entity_uuid=owner.uuid)],
            event_processor=self._processor,
        )
        owner.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has {self.name}")
        return [], [handler.uuid], [], [], effect_event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        if not isinstance(event, AttackEvent) or event.attack_outcome not in {AttackOutcome.HIT, AttackOutcome.CRIT}:
            return event
        if event.damage_rolls is None:
            return event
        if event.weapon_name not in self.weapon_names:
            return event
        source = Entity.get(source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if source is None or target is None:
            return event
        if target.creature_type.value in self.excluded_creature_types:
            return event
        request = source.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=self.save_ability,  # type: ignore[arg-type]
            dc=self.save_dc,
            parent_event=event.uuid,
            condition_context=self.condition_name,
        )
        _outcome, _roll, success = target.saving_throw(request)
        if success:
            return event
        if self.condition_name == "Prone":
            target.add_condition(Prone(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid), parent_event=event)
        elif self.condition_name == "Ghoul Paralysis":
            effect = GhoulParalysisEffect(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, save_dc=self.save_dc)
            target.add_condition(effect, parent_event=event)
        return event


class GhoulParalysisEffect(BaseCondition):
    """Ghoul paralysis effect with end-of-turn repeat save."""

    name: str = Field(default="Ghoul Paralysis", description="Condition name.")
    description: str = Field(default="Paralyzed by ghoul claws; repeat CON save at end of turn.", description="Rules summary.")
    save_dc: int = Field(default=10, description="Repeat save DC.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Ghoul paralysis target not found")
        paralyzed = Paralyzed(source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid, parent_condition=self.uuid)
        target.add_condition(paralyzed, parent_event=declaration_event)
        handler = EventHandler(
            name="Ghoul Paralysis Repeat Save",
            source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT, event_source_entity_uuid=target.uuid)],
            event_processor=self._repeat_save,
        )
        target.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{target.name} is paralyzed by ghoul claws")
        return [], [handler.uuid], [paralyzed.uuid], [], effect_event

    def _repeat_save(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        target = Entity.get(source_entity_uuid)
        source = Entity.get(self.source_entity_uuid)
        if not target or not source:
            return event
        request = source.create_saving_throw_request(target.uuid, "constitution", self.save_dc, parent_event=event.uuid, condition_context="Ghoul Paralysis")
        _outcome, _roll, success = target.saving_throw(request)
        if success and self.name in target.active_conditions:
            target.remove_condition(self.name, parent_event=event)
        return event


class UndeadFortitudeFeature(BaseCondition):
    """Zombie survival feature that caps qualifying lethal damage at 1 HP."""

    name: str = Field(default="Undead Fortitude", description="Condition name.")
    description: str = Field(default="CON save to survive qualifying lethal damage at 1 HP.", description="Rules summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Undead Fortitude owner not found")
        handler = EventHandler(
            name="Undead Fortitude",
            semantic_key="trait.monster.undead_fortitude",
            content_kind=ContentKind.TRAIT,
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EFFECT, event_target_entity_uuid=owner.uuid)],
            event_processor=self._processor,
        )
        owner.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has Undead Fortitude")
        return [], [handler.uuid], [], [], effect_event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        if not isinstance(event, TakeDamageEvent):
            return event
        target = Entity.get(source_entity_uuid)
        if not target or event.damages and event.damages[0].damage_type == DamageType.RADIANT:
            return event
        current_hp = target.get_hp()
        preview = target.preview_take_damage(event)
        if current_hp - preview.normal_hit_point_damage > 0:
            return event
        dc = 5 + event.get_effective_damage()
        request = target.create_saving_throw_request(target.uuid, "constitution", dc, parent_event=event.uuid, condition_context="Undead Fortitude")
        _outcome, _roll, success = target.saving_throw(request)
        if not success:
            return event
        damage_cap = max(0, current_hp - 1)
        if event.normal_hit_point_damage_cap is not None:
            damage_cap = min(damage_cap, event.normal_hit_point_damage_cap)
        return event.model_copy(update={"normal_hit_point_damage_cap": damage_cap, "status_message": "Undead Fortitude keeps target at 1 HP"})


class ParryFeature(BaseCondition):
    """Reaction feature that grants temporary AC against one melee hit."""

    name: str = Field(default="Parry", description="Condition name.")
    description: str = Field(default="Reaction: +AC against one melee attack that would hit.", description="Rules summary.")
    ac_bonus: int = Field(default=2, description="AC bonus.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Parry owner not found")
        handler = EventHandler(
            name="Parry",
            semantic_key="trait.monster.parry",
            content_kind=ContentKind.REACTION,
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EXECUTION, event_target_entity_uuid=owner.uuid)],
            event_processor=self._processor,
        )
        owner.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} can Parry")
        return [], [handler.uuid], [], [], effect_event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        defender = Entity.get(source_entity_uuid)
        if not defender or not isinstance(event, AttackEvent) or event.range is None or event.range.type != RangeType.REACH:
            return event
        if not defender.action_economy.can_afford("reactions", 1):
            return event
        if event.ac is None:
            return event
        event.ac.self_static.add_value_modifier(
            NumericalModifier(
                name="Parry",
                value=self.ac_bonus,
                source_entity_uuid=defender.uuid,
                target_entity_uuid=defender.uuid,
            )
        )
        defender.action_economy.consume("reactions", 1)
        return event.model_copy(update={
            "modified": True,
            "status_message": f"{defender.name} uses Parry for +{self.ac_bonus} AC",
        })


class DivineEminenceAction(BaseAction):
    """Priest bonus action that empowers melee weapon hits with radiant dice."""

    name: str = Field(default="Divine Eminence", description="Action name.")
    description: str = Field(default="Spend a spell slot to add radiant damage to melee attacks this turn.", description="Rules summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Self action.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Divine Eminence Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="Bonus action cost.")

    def pre_validate(self) -> bool:
        actor = Entity.get(self.source_entity_uuid)
        return bool(actor and actor.get_lowest_spell_slot(1) is not None and actor.action_economy.can_afford("bonus_actions", 1))

    def get_self_setup_profile(self, actor: object) -> Optional[ActionSelfSetupProfile]:
        """Describe the short-lived radiant weapon setup for AI policy."""
        if not isinstance(actor, Entity) or actor.get_lowest_spell_slot(1) is None:
            return None
        return ActionSelfSetupProfile(
            semantic_id="setup.divine_eminence",
            duration=ActionSetupDuration.CURRENT_TURN,
            maximum_duration_rounds=1,
            condition_fact_ids=("actor.condition.divine_eminence_active",),
            active_condition_semantic_keys=frozenset({"dnd.monsters.traits.DivineEminenceActive"}),
            increases_weapon_damage=True,
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return execution_event.cancel(status_message="Actor not found")
        slot = actor.get_lowest_spell_slot(1)
        if slot is None:
            return execution_event.cancel(status_message="No spell slot for Divine Eminence")
        actor.action_economy.consume(cast(CostType, f"spell_slot_{slot}"), 1)
        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message=f"{actor.name} invokes Divine Eminence")
        actor.add_condition(DivineEminenceActive(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, slot_level=slot), parent_event=effect_event)
        return effect_event.phase_to(EventPhase.COMPLETION, status_message="Divine Eminence active")

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class DivineEminenceActive(BonusDamageFeature):
    """Temporary radiant melee damage condition."""

    name: str = Field(default="Divine Eminence Active", description="Condition name.")
    slot_level: int = Field(default=1, description="Slot level spent.")
    damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Radiant damage.")
    melee_only: bool = Field(default=True, description="Only melee attacks qualify.")

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1
        self.dice_numbers = 3 + max(0, self.slot_level - 1)
        self.damage_dice = 6


class LeadershipAction(BaseAction):
    """Knight leadership action that grants nearby allies attack/save d4."""

    name: str = Field(default="Leadership", description="Action name.")
    description: str = Field(default="For 1 minute, nearby allies add 1d4 to attack rolls and saves.", description="Rules summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Self action.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Leadership Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="Action cost.")

    def pre_validate(self) -> bool:
        actor = Entity.get(self.source_entity_uuid)
        return bool(actor and "Leadership Used" not in actor.active_conditions)

    def get_self_setup_profile(self, actor: object) -> Optional[ActionSelfSetupProfile]:
        """Describe the ally-support aura as a typed setup action."""
        if not isinstance(actor, Entity) or "Leadership Used" in actor.active_conditions:
            return None
        return ActionSelfSetupProfile(
            semantic_id="support.leadership",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            maximum_duration_rounds=10,
            condition_fact_ids=("actor.aura.leadership", "actor.condition.leadership_used"),
            active_condition_semantic_keys=frozenset({"dnd.monsters.traits.LeadershipAura"}),
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return execution_event.cancel(status_message="Actor not found")
        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message=f"{actor.name} uses Leadership")
        actor.add_condition(LeadershipAura(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid), parent_event=effect_event)
        actor.add_condition(SimpleMarkerCondition(name="Leadership Used", source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid), parent_event=effect_event)
        return effect_event.phase_to(EventPhase.COMPLETION, status_message="Leadership active")

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class LeadershipAura(BaseCondition):
    """Aura handler that adds 1d4 to nearby allies' attacks and saves."""

    name: str = Field(default="Leadership Aura", description="Condition name.")
    description: str = Field(default="Nearby allies add 1d4 to attacks and saves.", description="Rules summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        leader = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not leader:
            return [], [], [], [], declaration_event.cancel(status_message="Leadership owner not found")
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 10
        handler = EventHandler(
            name="Leadership",
            source_entity_uuid=leader.uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.ATTACK_D20_ROLL_RESULT, event_phase=EventPhase.EFFECT),
                Trigger(event_type=EventType.SAVE_D20_ROLL_RESULT, event_phase=EventPhase.EFFECT),
            ],
            event_processor=self._processor,
        )
        leader.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{leader.name} begins Leadership")
        return [], [handler.uuid], [], [], effect_event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        if not isinstance(event, D20RollResultEvent):
            return event
        leader = Entity.get(source_entity_uuid)
        roller = Entity.get(event.source_entity_uuid)
        if leader is None or roller is None or leader.uuid == roller.uuid or not leader.is_ally(roller):
            return event
        if leader.senses.get_feet_distance(roller.position) > 30:
            return event
        roll = event.get_effective_roll()
        d4 = Dice(count=1, value=4, bonus=ModifiableValue.create(source_entity_uuid=leader.uuid, base_value=0, value_name="Leadership"), roll_type=roll.roll_type).roll
        new_roll = roll.model_copy(update={"total": roll.total + d4.total})
        event.replace_roll(new_roll, "Leadership", f"+{d4.total} (1d4)")
        return event


class RampageFeature(BaseCondition):
    """Gnoll feature that grants a bonus bite after a melee kill."""

    name: str = Field(default="Rampage", description="Condition name.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Rampage owner not found")
        handler = EventHandler(
            name="Rampage",
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT, event_source_entity_uuid=owner.uuid)],
            event_processor=self._processor,
        )
        owner.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{owner.name} has Rampage")
        return [], [handler.uuid], [], [], effect_event

    def _processor(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        owner = Entity.get(source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if owner is None or target is None or not isinstance(event, AttackEvent):
            return event
        if event.damage_rolls is None:
            return event
        if event.range is None or event.range.type != RangeType.REACH or target.get_hp() > 0:
            return event
        if "Rampage Available" not in owner.active_conditions:
            owner.add_condition(RampageAvailable(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid), parent_event=event)
        return event


class RampageAvailable(BaseCondition):
    """Temporary condition that grants Rampage Bite."""

    name: str = Field(default="Rampage Available", description="Condition name.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not owner:
            return [], [], [], [], declaration_event.cancel(status_message="Rampage owner not found")
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1
        action = NaturalAttack(
            name="Rampage Bite",
            source_entity_uuid=owner.uuid,
            template=True,
            natural_damage_dice=4,
            natural_dice_numbers=1,
            natural_damage_type=DamageType.PIERCING,
            natural_range=Range(type=RangeType.REACH, normal=5),
            costs=[Cost(name="Rampage Bite Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        )
        owner.register_action(action)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message="Rampage Bite available")
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if owner:
            owner.unregister_action("Rampage Bite")
        return super()._remove(event)


def _has_adjacent_ally(source: Entity, target: Entity) -> bool:
    """Return whether source has an active ally adjacent to target."""
    for candidate in Entity.get_all_entities():
        if candidate.uuid in {source.uuid, target.uuid}:
            continue
        if not source.is_ally(candidate):
            continue
        if "Dead" in candidate.active_conditions or "Incapacitated" in candidate.active_conditions:
            continue
        if candidate.senses.get_feet_distance(target.position) <= 5:
            return True
    return False


def _has_sneak_attack_condition(source: Entity, target: Entity, event: DamageRollResultEvent) -> bool:
    """Return whether a damage event satisfies SRD Sneak Attack conditions."""
    attack_roll = None
    parent = Event.get(event.parent_event) if event.parent_event else None
    if parent is not None:
        attack_roll = getattr(parent, "dice_roll", None)
    has_advantage = bool(attack_roll and attack_roll.advantage_status == AdvantageStatus.ADVANTAGE)
    has_disadvantage = bool(attack_roll and attack_roll.advantage_status == AdvantageStatus.DISADVANTAGE)
    return not has_disadvantage and (has_advantage or _has_adjacent_ally(source, target))


def _is_unseen_attacker(source: Entity, target: Entity) -> bool:
    """Return whether target currently lacks sight of the source."""
    return "Hidden" in source.active_conditions or "Invisible" in source.active_conditions or source.uuid not in target.senses.entities


def _attack_weapon_name(actor: Entity, action: Attack) -> Optional[str]:
    """Return the weapon name a discovered attack row would use."""
    if isinstance(action, NaturalAttack):
        return action.name
    weapon = actor.equipment._get_weapon_by_slot(action.weapon_slot)
    return weapon.name if weapon is not None else None


def _action_primary_damage_type(actor: Entity, action: Attack) -> DamageType:
    """Return the primary damage type used by a discovered attack row."""
    if isinstance(action, NaturalAttack):
        return action.natural_damage_type
    return actor.equipment.get_main_damage_type(action.weapon_slot)


def _fact_slug(value: str) -> str:
    """Normalize a display condition name into a stable fact suffix."""
    slug = "".join(character if character.isalnum() else "_" for character in value.strip().lower())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _register_action_once(entity: Entity, action: BaseAction) -> None:
    """Register an action template if the entity does not already have it."""
    if entity.get_action_template(action.name or "") is None:
        entity.register_action(action)


def _add_feature_once(entity: Entity, condition: BaseCondition) -> None:
    """Apply a persistent feature condition if not already active."""
    if condition.name not in entity.active_conditions:
        entity.add_condition(condition)
