"""Field Focus content pack used by extension tutorials."""

from typing import Optional

from pydantic import Field

from dnd.actions import entity_action_economy_cost_applier, entity_action_economy_cost_evaluator
from dnd.blocks.base_item import UsableItem
from dnd.core.base_actions import ActionEvent, AvailableActionInfo, BaseAction, Cost, TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventPhase
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin


class FieldFocus(BaseCondition):
    """Condition that grants a field unit tactical mobility and defense."""

    name: str = Field(default="Field Focus", description="Condition registry key.")
    description: str = Field(
        default="A compact field kit boosts movement and defense.",
        description="Rules summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Public condition category.",
    )
    movement_bonus: int = Field(default=10, description="Bonus feet of movement while focused.")
    armor_bonus: int = Field(default=1, description="Armor Class bonus while focused.")

    def _apply(self, declaration_event: Event):
        """Apply movement and Armor Class modifiers to the target entity.

        Args:
            declaration_event: Condition application event currently being resolved.

        Returns:
            Condition application tuple containing owned modifier UUID pairs and
            the effect event.
        """
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Field Focus target missing")
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], declaration_event.cancel(status_message="Field Focus target not found")

        owned_modifiers = []
        movement_modifier = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            name="Field Focus Movement",
            value=self.movement_bonus,
        )
        movement_uuid = target.action_economy.movement.self_static.add_value_modifier(movement_modifier)
        owned_modifiers.append((target.action_economy.movement.uuid, movement_uuid))

        armor_modifier = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            name="Field Focus Armor",
            value=self.armor_bonus,
        )
        armor_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(armor_modifier)
        owned_modifiers.append((target.equipment.ac_bonus.uuid, armor_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} gains Field Focus",
        )
        return owned_modifiers, [], [], [], effect_event


class DeployFieldFocus(BaseAction):
    """Bonus action that applies Field Focus to the acting entity."""

    name: str = Field(default="Deploy Field Focus", description="Action discovery label.")
    description: str = Field(default="Deploy a field kit for speed and defense.", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="The action targets the acting entity.")
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Deploy Field Focus Cost",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        description="Bonus-action cost required to deploy the focus.",
    )
    charge_cost: int = Field(default=1, description="Charges consumed when provided by an item.")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate that the actor can deploy Field Focus.

        Args:
            declaration_event: Action declaration event.

        Returns:
            Execution event when valid, or a canceled declaration event.
        """
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return declaration_event.cancel(status_message="Field Focus actor not found")
        if "Field Focus" in actor.active_conditions:
            return declaration_event.cancel(status_message="Field Focus is already active")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"{actor.name} can deploy Field Focus",
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply Field Focus to the acting entity.

        Args:
            execution_event: Action execution event.

        Returns:
            Completion event after the condition is applied.
        """
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return execution_event.cancel(status_message="Field Focus actor not found")

        actor.add_condition(
            FieldFocus(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid),
            parent_event=execution_event,
        )
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{actor.name} deploys Field Focus",
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{actor.name} is field-focused",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Spend the action's bonus-action cost.

        Args:
            completion_event: Completed action event.

        Returns:
            Event returned by the action economy cost applier.
        """
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


def find_action_info(actions, template_name: str) -> AvailableActionInfo:
    """Return a discovered action row by template name.

    Args:
        actions: Available-actions result returned by discovery.
        template_name: Template name to find.

    Returns:
        Matching action info row.
    """
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def find_item_action(actions, action_name: str, item_uuid) -> AvailableActionInfo:
    """Return a discovered item-provided action row.

    Args:
        actions: Available-actions result returned by discovery.
        action_name: Base action name before item suffixing.
        item_uuid: Item UUID expected to provide the action.

    Returns:
        Matching item-use action info row.
    """
    return find_action_info(actions, f"{action_name}__item_{item_uuid}")


def inventory_item_named(entity: Entity, name: str) -> UsableItem:
    """Return one usable inventory item by name.

    Args:
        entity: Entity whose inventory should be searched.
        name: Item display name to find.

    Returns:
        Matching usable item.
    """
    for item in entity.inventory.items.values():
        if item.name == name:
            assert isinstance(item, UsableItem)
            return item
    raise AssertionError(f"{entity.name} does not carry {name}")


def create_field_kit(owner_uuid, charges: int = 1) -> UsableItem:
    """Create a usable field kit that provides Deploy Field Focus.

    Args:
        owner_uuid: Entity UUID used as the kit's source owner.
        charges: Number of available item uses.

    Returns:
        Usable Field Kit item.
    """
    return UsableItem(
        source_entity_uuid=owner_uuid,
        name="Field Kit",
        description="A compact kit that deploys tactical focus gear.",
        map_char="kit",
        charges=charges,
        max_charges=charges,
        use_action_templates=[
            DeployFieldFocus(source_entity_uuid=owner_uuid, template=True),
        ],
    )


def create_field_medic(
    name: str = "Field Medic",
    position: tuple[int, int] = (1, 1),
    faction: str = "heroes",
) -> Entity:
    """Create a goblin-based support actor carrying the field content pack.

    Args:
        name: Entity display name.
        position: Starting grid position.
        faction: Faction assigned to the actor.

    Returns:
        Configured support actor.
    """
    medic = create_goblin(name=name, position=position, faction=faction)
    medic.register_action(DeployFieldFocus(source_entity_uuid=medic.uuid, template=True))
    medic.loot_item(create_field_kit(medic.uuid))
    return medic


def create_field_training_scene():
    """Create one custom actor, an ally, and one floor field kit.

    Returns:
        Tuple of the field medic, allied actor, and floor kit.
    """
    medic = create_field_medic()
    ally = create_goblin(name="Field Ally", position=(2, 1), faction="heroes")
    floor_kit = create_field_kit(medic.uuid)
    floor_kit.place_on_grid((1, 2))
    Entity.update_all_entities_senses(max_distance=20)
    return medic, ally, floor_kit
