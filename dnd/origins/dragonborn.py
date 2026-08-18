"""SRD 5.1 Dragonborn ancestry runtime mechanics."""

from __future__ import annotations

from typing import Any, cast

from pydantic import Field

from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.core.base_actions import (
    ActionCategory,
    ActionOutcomeProfile,
    BaseAction,
    Cost,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    TargetType,
)
from dnd.core.events.action_events import BaseCost, DragonbornBreathWeaponEvent
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)
from dnd.types.rolls import AttackOutcome
from dnd.core.events.resolution_events import (
    Damage,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.types.damage import DamageType
from dnd.types.abilities import AbilityName
from dnd.core.values import ModifiableValue
from dnd.entities.entity import Entity


DRAGONBORN_BREATH_RESOURCE = "dragonborn_breath_weapon"


class DragonbornBreathWeapon(BaseAction):
    """One ancestry-configured Dragonborn Breath Weapon action."""

    name: str = Field(default="Breath Weapon")
    description: str = Field(
        default=(
            "Exhale ancestry energy; affected creatures save for half damage."
        ),
    )
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY)
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")
    aoe_require_targets: bool = Field(default=True)
    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: AbilityName
    character_level: int = Field(ge=1, le=20)
    costs: list[Cost] = Field(default_factory=list)

    @property
    def damage_dice_count(self) -> int:
        """Return SRD damage dice at character levels 1, 6, 11, and 16."""
        if self.character_level >= 16:
            return 5
        if self.character_level >= 11:
            return 4
        if self.character_level >= 6:
            return 3
        return 2

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Breath Weapon",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name=DRAGONBORN_BREATH_RESOURCE,
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator,
            ),
        ]

    def get_outcome_profile(
        self,
        actor: Any,
    ) -> ActionOutcomeProfile | None:
        """Expose the actor-known save and damage rule to policy consumers."""
        if not isinstance(actor, Entity):
            return None
        save_dc = (
            8
            + actor.ability_scores.constitution.modifier
            + actor.proficiency_bonus.normalized_score
        )
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            application_scope=(
                OutcomeApplicationScope.EACH_AFFECTED_ENTITY
            ),
            damage_rolls=(
                DamageRollProfile(
                    dice_count=self.damage_dice_count,
                    die_size=6,
                    damage_type=self.damage_type.value,
                ),
            ),
            save_dc=save_dc,
            save_ability=self.save_ability,
            half_damage_on_save=True,
        )

    def _create_declaration_event(
        self,
        parent_event: Event | None = None,
        use_register: bool = True,
    ) -> DragonbornBreathWeaponEvent:
        source = Entity.get(self.source_entity_uuid)
        save_dc = (
            8
            + source.ability_scores.constitution.modifier
            + source.proficiency_bonus.normalized_score
            if isinstance(source, Entity)
            else 8
        )
        event = DragonbornBreathWeaponEvent(
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=source.name if source is not None else None,
            parent_event=parent_event.uuid if parent_event is not None else None,
            use_register=use_register,
            costs=[
                BaseCost.model_validate(cost)
                for cost in self.effective_costs
            ],
            name=self.name,
            description=self.description,
            declared_target_entity_uuids=self._declared_target_entity_uuids(),
            aoe_position=self.end_position,
            ancestry=self.ancestry,
            damage_type=self.damage_type,
            breath_geometry=self.breath_geometry,
            save_ability=self.save_ability,
            save_dc=save_dc,
            damage_dice_count=self.damage_dice_count,
        )
        return event

    def _validate(
        self,
        declaration_event: DragonbornBreathWeaponEvent,
    ) -> DragonbornBreathWeaponEvent:
        source = Entity.get(self.source_entity_uuid)
        if not isinstance(source, Entity):
            return declaration_event.cancel(
                status_message="Dragonborn Breath Weapon source not found",
            )
        if self.end_position is None or self.end_position == source.position:
            return declaration_event.cancel(
                status_message="Dragonborn Breath Weapon requires a direction",
            )
        return cast(
            DragonbornBreathWeaponEvent,
            super()._validate(declaration_event),
        )

    def _apply(
        self,
        execution_event: DragonbornBreathWeaponEvent,
    ) -> DragonbornBreathWeaponEvent:
        source = Entity.get(self.source_entity_uuid)
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(source, Entity) or not isinstance(target, Entity):
            return execution_event.cancel(
                status_message="Dragonborn Breath Weapon target not found",
            )

        save_request = source.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=self.save_ability,
            dc=execution_event.save_dc,
            parent_event=execution_event.uuid,
        )
        _, save_roll, save_success = target.saving_throw(save_request)
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            save_success=save_success,
            save_roll=save_roll,
            target_entity_name=target.name,
            status_message=(
                f"{target.name} {'succeeds' if save_success else 'fails'} "
                f"the {self.save_ability} save"
            ),
        )

        damage = Damage(
            source_entity_uuid=source.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=self.damage_dice_count,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid,
                base_value=0,
                value_name="Dragonborn Breath Weapon damage bonus",
            ),
            damage_type=self.damage_type,
        )
        damage_roll = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll
        final_damage = (
            damage_roll.total // 2 if save_success else damage_roll.total
        )
        target.receive_damage(
            amount=final_damage,
            damage_type=self.damage_type,
            source_entity_uuid=source.uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=effect_event.uuid,
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            damages=[damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=(
                f"Breath Weapon deals {final_damage} "
                f"{self.damage_type.value.lower()} damage to {target.name}"
            ),
        )


__all__ = [
    "DRAGONBORN_BREATH_RESOURCE",
    "DragonbornBreathWeapon",
    "DragonbornBreathWeaponEvent",
]
