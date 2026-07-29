"""SRD 5.1 Dragonborn ancestry runtime mechanics."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from pydantic import Field

from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.core.aoe import Cone, Line
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
    ActionOutcomeProfile,
    BaseAction,
    BaseCost,
    Cost,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    TargetType,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.dragonborn import (
    DragonbornAncestry,
    DragonbornAncestryFeatureDefinition,
    DragonbornBreathGeometry,
    DragonbornSaveAbility,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
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
from dnd.core.dice import AttackOutcome, DiceRoll
from dnd.core.events import Damage, Event, EventPhase
from dnd.core.creature_types import DamageType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity


DRAGONBORN_BREATH_RESOURCE = "dragonborn_breath_weapon"


class DragonbornBreathWeaponEvent(ActionEvent):
    """Cold typed facts produced by one Dragonborn Breath Weapon use."""

    ancestry_ref: ContentRef
    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: DragonbornSaveAbility
    save_dc: int = Field(ge=0)
    save_success: bool | None = None
    save_roll: DiceRoll | None = None
    damage_dice_count: int = Field(ge=1)
    damages: list[Damage] = Field(default_factory=list)
    damage_rolls: list[DiceRoll] = Field(default_factory=list)


@behavior_identity(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id="content.srd_5_1_cc",
    content_id="action.origin.dragonborn.breath_weapon",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Breath Weapon",
        description=(
            "Exhale destructive energy in the shape and damage type granted "
            "by your draconic ancestry."
        ),
        tags=("action", "dragonborn", "origin_feature", "srd_5_1"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="action.dragonborn-breath-weapon",
            visual_variant_key="dragonborn_breath_weapon",
            vfx_profile="dragonborn_breath_weapon",
            ui_group="actions.origin",
        ),
        ordering=ContentOrdering(
            sort_group="actions.origin",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 Races: Dragonborn Traits — Draconic Ancestry and "
            "Breath Weapon"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Uses SRD 5.1 ancestry geometry, save ability, scaling, and "
            "short-or-long-rest use."
        ),
    ),
)
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
    ancestry_ref: ContentRef
    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: DragonbornSaveAbility
    character_level: int = Field(ge=1, le=20)
    costs: list[Cost] = Field(default_factory=list)

    @classmethod
    def from_definition(
        cls,
        *,
        source_entity_uuid: UUID,
        ancestry_ref: ContentRef,
        definition: DragonbornAncestryFeatureDefinition,
        character_level: int,
        template: bool,
    ) -> "DragonbornBreathWeapon":
        """Create an action from one exact typed ancestry definition."""
        return cls(
            source_entity_uuid=source_entity_uuid,
            ancestry_ref=ancestry_ref,
            ancestry=definition.ancestry,
            damage_type=DamageType(definition.damage_type),
            breath_geometry=definition.breath_geometry,
            save_ability=definition.save_ability,
            character_level=character_level,
            aoe_shape=(
                Line(
                    source_entity_uuid=source_entity_uuid,
                    target=(1, 0),
                    length_feet=definition.line_length_feet or 30,
                    width_feet=definition.line_width_feet or 5,
                )
                if definition.breath_geometry
                is DragonbornBreathGeometry.LINE
                else Cone(
                    source_entity_uuid=source_entity_uuid,
                    target=(1, 0),
                    length_feet=definition.cone_length_feet or 15,
                )
            ),
            template=template,
        )

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
            ancestry_ref=self.ancestry_ref,
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

    def _apply_costs(
        self,
        completion_event: DragonbornBreathWeaponEvent,
    ) -> DragonbornBreathWeaponEvent:
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


DRAGONBORN_BREATH_WEAPON_DECLARATION = get_content_declaration(
    DragonbornBreathWeapon,
)
DRAGONBORN_BREATH_WEAPON_REF = (
    DRAGONBORN_BREATH_WEAPON_DECLARATION.ref
)


__all__ = [
    "DRAGONBORN_BREATH_RESOURCE",
    "DRAGONBORN_BREATH_WEAPON_DECLARATION",
    "DRAGONBORN_BREATH_WEAPON_REF",
    "DragonbornBreathWeapon",
    "DragonbornBreathWeaponEvent",
]
