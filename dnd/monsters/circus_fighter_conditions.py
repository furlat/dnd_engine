from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.blocks.equipment import Weapon
from dnd.core.equipment_types import WeaponProperty
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.entity import Entity
from dnd.core.values import Channel, Kind, add_modifier


def elemental_advantage(
    source_uuid: UUID,
    target_uuid: Optional[UUID],
    context: Optional[Dict[str, Any]],
) -> Optional[AdvantageModifier]:
    """Return advantage when the source is wielding an elemental weapon.

    Args:
        source_uuid: Entity UUID for the attacker being evaluated.
        target_uuid: Target UUID passed through the contextual modifier.
        context: Runtime context supplied by the modifier evaluator.

    Returns:
        Advantage modifier when either melee weapon deals elemental damage,
        otherwise None.
    """
    source_entity = Entity.get(source_uuid)
    if not isinstance(source_entity, Entity):
        return None

    elemental_types = {
        DamageType.ACID,
        DamageType.COLD,
        DamageType.FIRE,
        DamageType.LIGHTNING,
        DamageType.POISON,
        DamageType.THUNDER,
    }
    weapons = [
        source_entity.equipment.weapon_melee_main,
        source_entity.equipment.weapon_melee_off,
    ]

    for weapon in weapons:
        if not isinstance(weapon, Weapon):
            continue

        has_elemental = weapon.damage_type in elemental_types or any(
            damage_type in elemental_types for damage_type in weapon.extra_damage_type
        )
        if has_elemental:
            return AdvantageModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=target_uuid,
                name="Elemental Weapon Advantage",
                value=AdvantageStatus.ADVANTAGE,
            )

    return None


def create_elemental_advantage_modifier(
    source_uuid: UUID,
    target_uuid: UUID,
) -> ContextualAdvantageModifier:
    """Create contextual advantage for elemental weapon attacks.

    Args:
        source_uuid: Entity UUID that owns the modifier.
        target_uuid: Target UUID associated with the modifier.

    Returns:
        Contextual advantage modifier for elemental weapon attacks.
    """
    return ContextualAdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Elemental Weapon",
        callable=elemental_advantage,
    )


def dual_wielder_ac_bonus(
    source_uuid: UUID,
    target_uuid: Optional[UUID],
    context: Optional[Dict[str, Any]],
) -> Optional[NumericalModifier]:
    """Return the dual-wielder AC bonus when both melee hands hold weapons.

    Args:
        source_uuid: Entity UUID for the creature being evaluated.
        target_uuid: Target UUID passed through the contextual modifier.
        context: Runtime context supplied by the modifier evaluator.

    Returns:
        A +1 AC modifier when the source has melee weapons in both hands,
        otherwise None.
    """
    source_entity = Entity.get(source_uuid)
    if not isinstance(source_entity, Entity):
        return None

    main_hand = source_entity.equipment.weapon_melee_main
    off_hand = source_entity.equipment.weapon_melee_off

    if not (isinstance(main_hand, Weapon) and isinstance(off_hand, Weapon)):
        return None

    if WeaponProperty.RANGED in main_hand.properties or WeaponProperty.RANGED in off_hand.properties:
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Dual Wielder AC Bonus",
        value=1,
    )


def create_dual_wielder_ac_modifier(
    source_uuid: UUID,
    target_uuid: UUID,
) -> ContextualNumericalModifier:
    """Create contextual AC bonus for dual-wielding melee weapons.

    Args:
        source_uuid: Entity UUID that owns the modifier.
        target_uuid: Target UUID associated with the modifier.

    Returns:
        Contextual numerical modifier for dual-wielder AC.
    """
    return ContextualNumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Dual Wielder",
        callable=dual_wielder_ac_bonus,
    )


class DualWielder(BaseCondition):
    """Contextual AC bonus for wielding separate melee weapons.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
    """

    name: str = Field(default="Dual Wielder", description="Condition registry key.")
    description: str = Field(
        default="You gain a +1 bonus to AC while wielding a separate melee weapon in each hand.",
        description="Player-facing summary for the dual-wielder condition.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the contextual AC modifier.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        if isinstance(target_entity, Entity):
            outs = []
            dual_wielder = create_dual_wielder_ac_modifier(self.target_entity_uuid, self.source_entity_uuid)
            modifier_uuid = add_modifier(target_entity.equipment.ac_bonus, Channel.SELF_CONTEXTUAL, Kind.VALUE, dual_wielder)
            outs.append((target_entity.equipment.ac_bonus.uuid, modifier_uuid))
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Dual Wielder contextual ac modifer condition to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}"
        )


class ElementalWeaponMastery(BaseCondition):
    """Contextual attack advantage for weapons with elemental damage.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
    """

    name: str = Field(default="Elemental Weapon Mastery", description="Condition registry key.")
    description: str = Field(
        default="You have advantage on attack rolls made with weapons that deal acid, cold, fire, lightning, poison, or thunder damage.",
        description="Player-facing summary for elemental weapon mastery.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply the contextual elemental-weapon advantage modifier.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        if isinstance(target_entity, Entity):
            outs = []
            elemental_advantage_modifier = create_elemental_advantage_modifier(self.target_entity_uuid, self.source_entity_uuid)
            modifier_uuid = add_modifier(target_entity.equipment.attack_bonus, Channel.SELF_CONTEXTUAL, Kind.ADVANTAGE, elemental_advantage_modifier)
            outs.append((target_entity.equipment.attack_bonus.uuid, modifier_uuid))
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Elemental Weapon Mastery contextual advantage modifier condition to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}"
        )


class ElementalAffinity(BaseCondition):
    """Fire resistance and cold vulnerability from elemental training.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
    """

    name: str = Field(default="Elemental Affinity", description="Condition registry key.")
    description: str = Field(
        default="Years of performing with enchanted weapons have attuned you to fire, but left you vulnerable to cold. You have resistance to fire damage but vulnerability to cold damage.",
        description="Player-facing summary for elemental affinity.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply fire resistance and cold vulnerability.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        if isinstance(target_entity, Entity):
            fire_resistance = ResistanceModifier(
                name="Elemental Affinity",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                damage_type=DamageType.FIRE,
                value=ResistanceStatus.RESISTANCE,
            )
            cold_vulnerability = ResistanceModifier(
                name="Elemental Affinity",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                damage_type=DamageType.COLD,
                value=ResistanceStatus.VULNERABILITY,
            )
            fire_resistance_uuid = add_modifier(target_entity.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, fire_resistance)
            cold_vulnerability_uuid = add_modifier(target_entity.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, cold_vulnerability)
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Elemental Affinity resistance modifier condition to {target_entity.name}",
            )
            return [
                (target_entity.health.damage_reduction.uuid, fire_resistance_uuid),
                (target_entity.health.damage_reduction.uuid, cold_vulnerability_uuid),
            ], [], [], [], effect_event
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}"
        )


class CircusPerformer(BaseCondition):
    """Bundle of circus-training bonuses and penalties.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
    """

    name: str = Field(default="Circus Performer", description="Condition registry key.")
    description: str = Field(
        default="Your past in the circus has granted you exceptional acrobatic abilities and combat training.",
        description="Player-facing summary for the circus performer condition.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply circus-training modifiers.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        if isinstance(target_entity, Entity):
            outs = []

            acrobatics = target_entity.skill_set.get_skill("acrobatics")
            acro_mod_uuid = add_modifier(acrobatics.skill_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=7,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((acrobatics.skill_bonus.uuid, acro_mod_uuid))

            history = target_entity.skill_set.get_skill("history")
            hist_mod_uuid = add_modifier(history.skill_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=-2,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((history.skill_bonus.uuid, hist_mod_uuid))

            strength_save = target_entity.saving_throws.get_saving_throw("strength")
            strength_mod_uuid = add_modifier(strength_save.bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((strength_save.bonus.uuid, strength_mod_uuid))

            intelligence_save = target_entity.saving_throws.get_saving_throw("intelligence")
            intelligence_mod_uuid = add_modifier(intelligence_save.bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((intelligence_save.bonus.uuid, intelligence_mod_uuid))

            reactions_mod_uuid = add_modifier(target_entity.action_economy.reactions, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=2,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.action_economy.reactions.uuid, reactions_mod_uuid))

            extra_actions_mod_uuid = add_modifier(target_entity.action_economy.actions, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=99,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.action_economy.actions.uuid, extra_actions_mod_uuid))

            for speed in target_entity.action_economy.speed_values:
                movement_mod_uuid = add_modifier(speed, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                        name="Circus Training",
                        value=-5,
                        source_entity_uuid=self.target_entity_uuid,
                        target_entity_uuid=self.source_entity_uuid,
                    ))
                outs.append((speed.uuid, movement_mod_uuid))

            ac_mod_uuid = add_modifier(target_entity.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.equipment.ac_bonus.uuid, ac_mod_uuid))

            unarmed_mod_uuid = add_modifier(target_entity.equipment.unarmed_damage_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.equipment.unarmed_damage_bonus.uuid, unarmed_mod_uuid))

            proficiency_mod_uuid = add_modifier(target_entity.proficiency_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Circus Training",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.proficiency_bonus.uuid, proficiency_mod_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Circus Performer condition to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}"
        )


class Tired(BaseCondition):
    """Movement, reaction, and save penalties from fatigue.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
    """

    name: str = Field(default="Tired", description="Condition registry key.")
    description: str = Field(
        default="You are exhausted from combat or travel, reducing your movement speed and reactions.",
        description="Player-facing summary for the tired condition.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply fatigue penalties.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        if isinstance(target_entity, Entity):
            outs = []

            for speed in target_entity.action_economy.speed_values:
                movement_mod_uuid = add_modifier(speed, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                        name="Tired",
                        value=-10,
                        source_entity_uuid=self.target_entity_uuid,
                        target_entity_uuid=self.source_entity_uuid,
                    ))
                outs.append((speed.uuid, movement_mod_uuid))

            reactions_mod_uuid = add_modifier(target_entity.action_economy.reactions, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
                    name="Tired",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((target_entity.action_economy.reactions.uuid, reactions_mod_uuid))

            strength_save = target_entity.saving_throws.get_saving_throw("strength")
            strength_advantage_uuid = add_modifier(strength_save.bonus, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                    name="Tired",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((strength_save.bonus.uuid, strength_advantage_uuid))

            dexterity_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dexterity_advantage_uuid = add_modifier(dexterity_save.bonus, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                    name="Tired",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                ))
            outs.append((dexterity_save.bonus.uuid, dexterity_advantage_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Tired condition to {target_entity.name}",
            )
            return outs, [], [], [], effect_event
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}"
        )
