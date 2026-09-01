"""Canonical Neurodragon consumables and their definition-owned behavior."""

from types import MappingProxyType
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
)
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.conditions import Concentrating, GreaterInvisibilityEffect
from dnd.core.action_types import ActionPresentationKind
from dnd.core.base_actions import (
    ActionEvent,
    ActionSelfSetupProfile,
    ActionSetupDuration,
    ActionSetupMaintenanceFailure,
    ActionSetupMaintenanceProfile,
    ActionSetupMaintenanceTrigger,
    BaseAction,
    Cost,
    TargetType,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import (
    ConditionCategory,
    ConditionTag,
    DurationType,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.identities import ContentDefinitionKind
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
from dnd.core.content.runtime import (
    RuntimeBehaviorKind,
    bind_runtime_behavior_child,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase
from dnd.core.creature_types import DamageType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.transmutation import HasteEffect


HEALING_POTION_DRINK_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.healing_potion.drink@1"
)
FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.weapon_coat.fire.apply@1"
)
LIGHTNING_WEAPON_COAT_APPLY_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.weapon_coat.lightning.apply@1"
)
CONCENTRATION_FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.weapon_coat.concentration_fire.apply@1"
)
TIMED_FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.weapon_coat.timed_fire.apply@1"
)
GREATER_INVISIBILITY_POTION_DRINK_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.potion_greater_invisibility.drink@1"
)
HASTE_POTION_DRINK_SEMANTIC_KEY = (
    "content.neurodragon:action:"
    "action.consumable.potion_haste.drink@1"
)
FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY = (
    "content.neurodragon:condition:"
    "condition.consumable.weapon_coat.fire@1"
)
LIGHTNING_WEAPON_COAT_CONDITION_SEMANTIC_KEY = (
    "content.neurodragon:condition:"
    "condition.consumable.weapon_coat.lightning@1"
)
CONCENTRATION_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY = (
    "content.neurodragon:condition:"
    "condition.consumable.weapon_coat.concentration_fire@1"
)
TIMED_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY = (
    "content.neurodragon:condition:"
    "condition.consumable.weapon_coat.timed_fire@1"
)


def _provenance(display_name: str) -> ContentProvenance:
    """Return reviewed original-content provenance for one consumable root."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Original consumable mechanics preserved exactly.",
    )


def _consumable_action_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    sort_order: int,
    applied_condition_types: tuple[type[BaseCondition], ...] = (),
):
    """Declare one original action before its providing item factory."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id="content.neurodragon",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("action", "consumable"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id,
                vfx_profile=content_id,
                ui_group="actions.consumable",
            ),
            ordering=ContentOrdering(
                sort_group="actions.consumable",
                sort_order=sort_order,
            ),
        ),
        provenance=_provenance(display_name),
        dependencies=tuple(
            ContentDependency(
                relation=ContentDependencyRelation.APPLIES_CONDITION,
                target_ref=get_content_declaration(condition_type).ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes=(
                    "Applied by this exact consumable action through an "
                    "authenticated runtime behavior binding."
                ),
            )
            for condition_type in applied_condition_types
        ),
    )


def _consumable_condition_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    sort_order: int,
):
    """Declare one exact player-visible consumable condition."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.CONDITION,
        runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
        pack_id="content.neurodragon",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("condition", "consumable", "weapon_coat"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id,
                vfx_profile=content_id,
                ui_group="conditions.condition",
            ),
            ordering=ContentOrdering(
                sort_group="conditions.condition",
                sort_order=sort_order,
            ),
        ),
        provenance=_provenance(display_name),
    )


class _PotionDrinkAction(BaseAction):
    """Shared videogame rule for drinking a potion as a bonus action."""

    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Drink Potion Cost",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        description="One bonus action consumed by every potion-drinking action.",
    )
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DRINK,
        description="Tells presentation clients to render a potion-drinking action.",
    )

    def _apply_costs(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        """Commit the potion's bonus-action cost before execution."""
        return entity_action_economy_cost_applier(
            execution_event,
            self.source_entity_uuid,
        )


@_consumable_action_identity(
    content_id="action.item.potion_healing.drink",
    display_name="Drink Healing Potion",
    description="Drink the potion to recover hit points.",
    sort_order=10,
)
class _DrinkHealingPotionAction(_PotionDrinkAction):
    """Drink a potion to heal."""

    name: str = Field(
        default="Drink Potion",
        description="Action name for drinking this potion.",
    )
    description: str = Field(
        default="Drinks a healing potion",
        description="Action description shown for potion use.",
    )
    semantic_key: str = Field(default=HEALING_POTION_DRINK_SEMANTIC_KEY)
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Healing potions target the user.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the potion item this action consumes.",
    )
    heal_amount: int = Field(
        default=7,
        description="Hit points restored by this potion action.",
    )

    def get_fixed_healing(self, actor: Any) -> Optional[int]:
        """Return the potion's deterministic restoration amount."""
        _ = actor
        return self.heal_amount

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.receive_healing(
            self.heal_amount,
            entity.uuid,
            source_description="Potion of Healing",
            parent_event=execution_event.uuid,
        )
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP",
        )
        return effect.with_updates(
            status_message="Drank healing potion",
        )


class _HealingPotion(UsableItem):
    """Potion of Healing. Single use, consumable. Stacks up to 10."""

    name: str = Field(
        default="Potion of Healing",
        description="Display name for the healing potion.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Healing potions can be picked up.",
    )
    map_char: str = Field(
        default="\u03b8",
        description="Map glyph for the healing potion.",
    )
    is_consumable: bool = Field(
        default=True,
        description=(
            "Healing potions are destroyed when their final charge is used."
        ),
    )
    charges: int = Field(
        default=1,
        description="Current charges for the top potion in the stack.",
    )
    max_charges: int = Field(
        default=1,
        description="Maximum charges for each potion in the stack.",
    )
    max_stack: int = Field(
        default=10,
        description="Maximum number of healing potions in one stack.",
    )


class _WeaponCoatCondition(BaseCondition):
    """Shared internal mechanic for authored weapon-coat conditions."""

    name: str = Field(
        default="Weapon Coat",
        description="Internal shared condition name.",
    )
    description: str = Field(
        default=(
            "The coated weapon deals an extra 1d6 damage of the coat's type "
            "on a hit."
        ),
        description="Rules-facing summary for the active weapon coat.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="The shared implementation base is never player-visible.",
    )
    coated_weapon_uuid: Optional[UUID] = Field(
        default=None,
        description="Weapon UUID that received the extra damage packet.",
    )
    coat_damage_type: DamageType = Field(
        default=DamageType.FIRE,
        description="Damage type added by the coat.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[
        list[tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Optional[Event],
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="No target",
            )
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found",
            )
        if not self.coated_weapon_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="No weapon specified",
            )
        weapon = BaseBlock.get(self.coated_weapon_uuid)
        if not weapon or not isinstance(weapon, Weapon):
            return [], [], [], [], declaration_event.cancel(
                status_message="Weapon not found",
            )

        bonus_mv = ModifiableValue.create(
            source_entity_uuid=self.target_entity_uuid,
            base_value=0,
            value_name=f"{self.name} Bonus",
        )
        weapon.extra_damage_dices.append(6)
        weapon.extra_damage_dices_numbers.append(1)
        weapon.extra_damage_bonus.append(bonus_mv)
        weapon.extra_damage_type.append(self.coat_damage_type)

        effect = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=(
                f"Weapon coated with {self.coat_damage_type.value}"
            ),
        )
        return [], [], [], [], effect

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up elemental dice from the coated weapon."""
        if self.coated_weapon_uuid:
            weapon = BaseBlock.get(self.coated_weapon_uuid)
            if weapon and isinstance(weapon, Weapon):
                for index in range(len(weapon.extra_damage_type) - 1, -1, -1):
                    if (
                        weapon.extra_damage_type[index]
                        == self.coat_damage_type
                    ):
                        weapon.extra_damage_dices.pop(index)
                        weapon.extra_damage_dices_numbers.pop(index)
                        weapon.extra_damage_bonus.pop(index)
                        weapon.extra_damage_type.pop(index)
                        break
        return super()._remove(event)


@_consumable_condition_identity(
    content_id="condition.consumable.weapon_coat.fire",
    display_name="Flaming Coat",
    description=(
        "The coated weapon deals an extra 1d6 fire damage on a hit."
    ),
    sort_order=10,
)
class _FireWeaponCoatCondition(_WeaponCoatCondition):
    """Permanent fire coating applied by the basic flame coat."""

    name: str = Field(default="Flaming Coat")
    description: str = Field(
        default="The coated weapon deals an extra 1d6 fire damage on a hit.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
    )
    coat_damage_type: DamageType = Field(default=DamageType.FIRE)


@_consumable_condition_identity(
    content_id="condition.consumable.weapon_coat.lightning",
    display_name="Lightning Coat",
    description=(
        "The coated weapon deals an extra 1d6 lightning damage on a hit."
    ),
    sort_order=20,
)
class _LightningWeaponCoatCondition(_WeaponCoatCondition):
    """Permanent lightning coating."""

    name: str = Field(default="Lightning Coat")
    description: str = Field(
        default=(
            "The coated weapon deals an extra 1d6 lightning damage on a hit."
        ),
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
    )
    coat_damage_type: DamageType = Field(default=DamageType.LIGHTNING)


@_consumable_condition_identity(
    content_id="condition.consumable.weapon_coat.concentration_fire",
    display_name="Flaming Coat",
    description=(
        "The coated weapon deals an extra 1d6 fire damage on a hit while "
        "its source maintains concentration."
    ),
    sort_order=30,
)
class _ConcentrationFireWeaponCoatCondition(_WeaponCoatCondition):
    """Fire coating linked to a concentration condition."""

    name: str = Field(default="Flaming Coat")
    description: str = Field(
        default=(
            "The coated weapon deals an extra 1d6 fire damage on a hit while "
            "its source maintains concentration."
        ),
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
    )
    coat_damage_type: DamageType = Field(default=DamageType.FIRE)


@_consumable_condition_identity(
    content_id="condition.consumable.weapon_coat.timed_fire",
    display_name="Flaming Coat",
    description=(
        "The coated weapon deals an extra 1d6 fire damage on a hit until "
        "the coating's authored duration expires."
    ),
    sort_order=40,
)
class _TimedFireWeaponCoatCondition(_WeaponCoatCondition):
    """Round-limited fire coating."""

    name: str = Field(default="Flaming Coat")
    description: str = Field(
        default=(
            "The coated weapon deals an extra 1d6 fire damage on a hit until "
            "the coating's authored duration expires."
        ),
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
    )
    coat_damage_type: DamageType = Field(default=DamageType.FIRE)


_WEAPON_COAT_CONDITION_TYPES_BY_SEMANTIC_KEY = MappingProxyType({
    FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
        _FireWeaponCoatCondition,
    LIGHTNING_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
        _LightningWeaponCoatCondition,
    CONCENTRATION_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
        _ConcentrationFireWeaponCoatCondition,
    TIMED_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
        _TimedFireWeaponCoatCondition,
})
if any(
    get_content_declaration(condition_type).ref.identity_key != semantic_key
    for semantic_key, condition_type
    in _WEAPON_COAT_CONDITION_TYPES_BY_SEMANTIC_KEY.items()
):
    raise ValueError("Weapon-coat condition identity map is inconsistent")


@_consumable_action_identity(
    content_id="action.item.weapon_coat.apply",
    display_name="Coat Main Hand",
    description=(
        "Apply the carried weapon coating to the active main-hand weapon."
    ),
    sort_order=20,
    applied_condition_types=tuple(
        _WEAPON_COAT_CONDITION_TYPES_BY_SEMANTIC_KEY.values()
    ),
)
class _ApplyWeaponCoatAction(BaseAction):
    """Apply weapon coat to a specific weapon slot."""

    name: str = Field(
        default="Coat Main Hand",
        description="Action name for applying a weapon coat.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Weapon coats target the acting entity.",
    )
    costs: list[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for coat application.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the coat item being consumed.",
    )
    weapon_slot: str = Field(
        default="MELEE_MAIN",
        description="Equipment weapon slot to coat.",
    )
    coat_duration: Optional[int] = Field(
        default=None,
        description="Duration in rounds; `None` creates a permanent coat.",
    )
    use_concentration: bool = Field(
        default=False,
        description="Whether applying the coat also creates concentration.",
    )
    coat_damage_type: DamageType = Field(
        default=DamageType.FIRE,
        description="Damage type added to the coated weapon.",
    )
    condition_semantic_key: str = Field(
        default=FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY,
        description="Stable definition identity of the applied coat condition.",
    )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        slot = WeaponSlot(self.weapon_slot)
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if not weapon or not isinstance(weapon, Weapon):
            return declaration_event.cancel(status_message="No weapon in slot")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        slot = WeaponSlot(self.weapon_slot)
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if not weapon or not isinstance(weapon, Weapon):
            return execution_event.cancel(status_message="No weapon in slot")

        if self.coat_duration is not None:
            duration = Duration(
                duration=self.coat_duration,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )
        else:
            duration = Duration(
                duration_type=DurationType.PERMANENT,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )

        condition_type = (
            _WEAPON_COAT_CONDITION_TYPES_BY_SEMANTIC_KEY.get(
                self.condition_semantic_key,
            )
        )
        if condition_type is None:
            return execution_event.cancel(
                status_message="Unknown weapon-coat condition identity",
            )
        coat = condition_type(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            coated_weapon_uuid=weapon.uuid,
            coat_damage_type=self.coat_damage_type,
            duration=duration,
        )
        bind_runtime_behavior_child(
            coat,
            provider_binding=self.behavior_binding,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_condition(coat, parent_event=execution_event)

        if self.use_concentration:
            concentration = Concentrating(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                spell_name=f"{coat.name} Weapon",
            )
            entity.add_condition(
                concentration,
                parent_event=execution_event,
            )
            concentration.add_linked_condition(entity.uuid, coat.uuid)

        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied {coat.name.lower()}",
        )
        return effect.with_updates(
            status_message=(
                f"Weapon coated with {self.coat_damage_type.value}"
            ),
        )


class _WeaponCoat(UsableItem):
    """Single-use weapon coat, stackable by exact recipe."""

    name: str = Field(
        default="Weapon Coat of Flame",
        description="Display name for the weapon coat item.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Weapon coats can be picked up.",
    )
    is_consumable: bool = Field(
        default=True,
        description="Weapon coats are consumed when applied.",
    )
    charges: int = Field(
        default=1,
        description="Current charges for the top coat in the stack.",
    )
    max_charges: int = Field(
        default=1,
        description="Maximum charges for each coat item.",
    )
    max_stack: int = Field(
        default=10,
        description="Maximum number of coats in one stack.",
    )


@_consumable_action_identity(
    content_id="action.item.potion_greater_invisibility.drink",
    display_name="Drink Greater Invisibility Potion",
    description="Drink the potion to gain its greater-invisibility effect.",
    sort_order=30,
)
class _DrinkGreaterInvisibilityPotionAction(_PotionDrinkAction):
    """Drink a potion to gain Greater Invisibility."""

    name: str = Field(
        default="Drink Greater Invisibility Potion",
        description="Action name for drinking this potion.",
    )
    description: str = Field(
        default=(
            "Drink to become invisible "
            "(Stealth check to maintain on attack/cast)"
        ),
        description="Action description shown for greater invisibility potions.",
    )
    semantic_key: str = Field(
        default=GREATER_INVISIBILITY_POTION_DRINK_SEMANTIC_KEY,
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Greater invisibility potions target the user.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the potion item being consumed.",
    )

    def get_self_setup_profile(self, actor: Any) -> ActionSelfSetupProfile:
        """Return the typed combat consequences of greater invisibility."""
        stealth_bonus = actor.skill_bonus(
            target_entity_uuid=None,
            skill_name="stealth",
        )
        return ActionSelfSetupProfile(
            semantic_id="setup.greater_invisibility",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            condition_fact_ids=("actor.condition.invisible",),
            active_condition_semantic_keys=frozenset({
                "dnd.conditions.GreaterInvisibilityEffect",
            }),
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_disadvantage=True,
            grants_invisibility=True,
            maintenance=ActionSetupMaintenanceProfile(
                trigger=ActionSetupMaintenanceTrigger.REVEALING_ACTION,
                skill_name="stealth",
                initial_dc=15,
                dc_increment_per_success=1,
                check_bonus=stealth_bonus.normalized_score,
                check_advantage=stealth_bonus.advantage,
                failure=ActionSetupMaintenanceFailure.REMOVE_SETUP,
            ),
        )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        invis_effect = GreaterInvisibilityEffect(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            tags={ConditionTag.MAGICAL},
        )
        entity.add_condition(invis_effect, parent_event=execution_event)

        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name} becomes invisible",
        )
        return effect.with_updates(
            status_message="Drank Potion of Greater Invisibility",
        )


class _PotionOfGreaterInvisibility(UsableItem):
    """Potion of Greater Invisibility. Single use, consumable."""

    name: str = Field(
        default="Potion of Greater Invisibility",
        description="Display name for the potion.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Greater invisibility potions can be picked up.",
    )
    map_char: str = Field(
        default="\u03b8",
        description="Map glyph for the potion.",
    )
    is_consumable: bool = Field(
        default=True,
        description="The potion is consumed when used.",
    )
    charges: int = Field(
        default=1,
        description="Current charges for the top potion in the stack.",
    )
    max_charges: int = Field(
        default=1,
        description="Maximum charges for each potion.",
    )
    max_stack: int = Field(
        default=5,
        description="Maximum number of potions in one stack.",
    )


@_consumable_action_identity(
    content_id="action.item.potion_haste.drink",
    display_name="Drink Haste Potion",
    description="Drink the potion to gain its haste effect.",
    sort_order=40,
)
class _DrinkHastePotionAction(_PotionDrinkAction):
    """Drink a potion to gain Haste without concentration."""

    name: str = Field(
        default="Drink Haste Potion",
        description="Action name for drinking this potion.",
    )
    description: str = Field(
        default=(
            "Drink to gain doubled speed, +2 AC, DEX advantage, and one "
            "restricted Haste action for 10 rounds; suffer lethargy when it ends"
        ),
        description="Action description shown for haste potions.",
    )
    semantic_key: str = Field(default=HASTE_POTION_DRINK_SEMANTIC_KEY)
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Haste potions target the user.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the potion item being consumed.",
    )

    def get_self_setup_profile(self, actor: Any) -> ActionSelfSetupProfile:
        """Return the typed combat consequences of the current Haste effect."""
        _ = actor
        return ActionSelfSetupProfile(
            semantic_id="setup.haste",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            maximum_duration_rounds=10,
            condition_fact_ids=("actor.condition.haste",),
            active_condition_semantic_keys=frozenset({
                "dnd.spells.transmutation.HasteEffect",
            }),
            armor_class_bonus=2,
            movement_speed_multiplier=2.0,
            extra_actions_per_turn=1,
            incapacitates_on_removal=True,
        )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        haste = HasteEffect(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            caster_uuid=entity.uuid,
            tags={ConditionTag.MAGICAL},
        )
        haste.duration.duration_type = DurationType.ROUNDS
        haste.duration.duration = 10
        entity.add_condition(haste, parent_event=execution_event)

        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name} gains Haste",
        )
        return effect.with_updates(
            status_message="Drank Potion of Haste",
        )


class _PotionOfHaste(UsableItem):
    """Potion of Haste. Single use, consumable."""

    name: str = Field(
        default="Potion of Haste",
        description="Display name for the potion.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Haste potions can be picked up.",
    )
    map_char: str = Field(
        default="\u03b8",
        description="Map glyph for the potion.",
    )
    is_consumable: bool = Field(
        default=True,
        description="The potion is consumed when used.",
    )
    charges: int = Field(
        default=1,
        description="Current charges for the top potion in the stack.",
    )
    max_charges: int = Field(
        default=1,
        description="Maximum charges for each potion.",
    )
    max_stack: int = Field(
        default=5,
        description="Maximum number of potions in one stack.",
    )


def build_healing_potion(
    source_entity_uuid: UUID,
    *,
    stack_count: int = 1,
    heal_amount: int = 7,
) -> UsableItem:
    """Construct a healing-potion stack directly."""
    if heal_amount < 0:
        raise ValueError("healing potion heal_amount cannot be negative")
    return _HealingPotion(
        source_entity_uuid=source_entity_uuid,
        item_id="consumable.healing_potion",
        use_action_templates=[_DrinkHealingPotionAction(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            heal_amount=heal_amount,
            template=True,
        )],
        stack_id=f"healing_potion_{heal_amount}",
        stack_count=stack_count,
    )


def build_haste_potion(source_entity_uuid: UUID) -> UsableItem:
    """Construct one Haste potion directly."""
    return _PotionOfHaste(
        source_entity_uuid=source_entity_uuid,
        item_id="consumable.potion_haste",
        use_action_templates=[_DrinkHastePotionAction(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            template=True,
        )],
        stack_id="potion_of_haste",
    )


def build_greater_invisibility_potion(
    source_entity_uuid: UUID,
) -> UsableItem:
    """Construct one Greater Invisibility potion directly."""
    return _PotionOfGreaterInvisibility(
        source_entity_uuid=source_entity_uuid,
        item_id="consumable.potion_greater_invisibility",
        use_action_templates=[_DrinkGreaterInvisibilityPotionAction(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            template=True,
        )],
        stack_id="potion_of_greater_invisibility",
    )


def _build_direct_weapon_coat(
    source_entity_uuid: UUID,
    *,
    item_id: str,
    display_name: str,
    damage_type: DamageType,
    action_id: str,
    condition_id: str,
    stack_id: str,
    include_off_hand: bool = True,
    duration: Optional[int] = None,
    concentration: bool = False,
) -> UsableItem:
    """Construct one weapon coating from explicit mechanical facts."""
    actions = [_ApplyWeaponCoatAction(
        source_entity_uuid=uuid4(),
        source_item_uuid=uuid4(),
        name="Coat Main Hand",
        semantic_key=action_id,
        condition_semantic_key=condition_id,
        weapon_slot="MELEE_MAIN",
        coat_damage_type=damage_type,
        coat_duration=duration,
        use_concentration=concentration,
        template=True,
    )]
    if include_off_hand:
        actions.append(_ApplyWeaponCoatAction(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            name="Coat Off Hand",
            semantic_key=action_id,
            condition_semantic_key=condition_id,
            weapon_slot="MELEE_OFF",
            coat_damage_type=damage_type,
            coat_duration=duration,
            use_concentration=concentration,
            template=True,
        ))
    return _WeaponCoat(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        name=display_name,
        use_action_templates=actions,
        stack_id=stack_id,
    )


def build_fire_weapon_coat(source_entity_uuid: UUID) -> UsableItem:
    return _build_direct_weapon_coat(
        source_entity_uuid,
        item_id="consumable.weapon_coat.fire",
        display_name="Weapon Coat of Flame",
        damage_type=DamageType.FIRE,
        action_id=FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY,
        condition_id=FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY,
        stack_id="weapon_coat_fire",
    )


def build_lightning_weapon_coat(source_entity_uuid: UUID) -> UsableItem:
    return _build_direct_weapon_coat(
        source_entity_uuid,
        item_id="consumable.weapon_coat.lightning",
        display_name="Weapon Coat of Lightning",
        damage_type=DamageType.LIGHTNING,
        action_id=LIGHTNING_WEAPON_COAT_APPLY_SEMANTIC_KEY,
        condition_id=LIGHTNING_WEAPON_COAT_CONDITION_SEMANTIC_KEY,
        stack_id="weapon_coat_lightning",
    )


def build_concentration_fire_weapon_coat(
    source_entity_uuid: UUID,
) -> UsableItem:
    return _build_direct_weapon_coat(
        source_entity_uuid,
        item_id="consumable.weapon_coat.concentration_fire",
        display_name="Concentrated Weapon Coat of Flame",
        damage_type=DamageType.FIRE,
        action_id=CONCENTRATION_FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY,
        condition_id=CONCENTRATION_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY,
        stack_id="weapon_coat_fire",
        include_off_hand=False,
        concentration=True,
    )


def build_timed_fire_weapon_coat(
    source_entity_uuid: UUID,
    *,
    rounds: int = 3,
) -> UsableItem:
    if rounds < 1:
        raise ValueError("timed fire weapon coat rounds must be positive")
    return _build_direct_weapon_coat(
        source_entity_uuid,
        item_id="consumable.weapon_coat.timed_fire",
        display_name="Timed Weapon Coat of Flame",
        damage_type=DamageType.FIRE,
        action_id=TIMED_FIRE_WEAPON_COAT_APPLY_SEMANTIC_KEY,
        condition_id=TIMED_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY,
        stack_id="weapon_coat_fire",
        include_off_hand=False,
        duration=rounds,
    )
