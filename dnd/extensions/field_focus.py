"""Field Focus item, action, and condition content."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions import entity_action_economy_cost_applier, entity_action_economy_cost_evaluator
from dnd.blocks.base_item import UsableItem
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    behavior_identity,
    get_content_declaration,
    item_factory,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.events import Event, EventPhase
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity


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


@behavior_identity(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id="content.neurodragon",
    content_id="action.item.field_kit.deploy",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Deploy Field Focus",
        description="Deploy a field kit for speed and defense.",
        tags=("action", "item", "neurodragon", "support"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="action.item.field_kit.deploy",
            visual_variant_key="field_kit_deploy",
            vfx_profile="field_kit_deploy",
            ui_group="actions.action",
        ),
        ordering=ContentOrdering(
            sort_group="actions.action",
            sort_order=40,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: Deploy Field Focus"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Exact existing Field Kit use action.",
    ),
)
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
        return effect_event.with_updates(
            status_message=f"{actor.name} is field-focused",
        )

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Spend the action's bonus-action cost.

        Args:
            execution_event: Validated execution proposal.

        Returns:
            Event returned by the action economy cost applier.
        """
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)
class FieldKitParameters(BaseModel):
    """Durable authored parameters for a finite-use Field Kit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = 1


@item_factory(
    pack_id="content.neurodragon",
    content_id="gear.field_kit",
    version=1,
    parameters=FieldKitParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Field Kit",
        description="A compact kit that deploys tactical focus gear.",
        tags=("gear", "neurodragon", "support", "usable"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="gear.field_kit",
            visual_variant_key="field_kit",
            ui_group="gear.support",
        ),
        ordering=ContentOrdering(
            sort_group="gear.support",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor="Neurodragon original content baseline: Field Kit",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact finite-charge Field Kit and Deploy Field Focus action "
            "template from the extension content."
        ),
    ),
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=get_content_declaration(DeployFieldFocus).ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        ),
    ),
)
def _build_field_kit(
    raw_context: object,
    parameters: FieldKitParameters,
) -> UsableItem:
    """Construct a Field Kit through the canonical item factory."""
    context = ItemBuildContext.model_validate(raw_context)
    return UsableItem(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Field Kit",
        description="A compact kit that deploys tactical focus gear.",
        map_char="kit",
        charges=parameters.charges,
        max_charges=parameters.charges,
        use_action_templates=[
            DeployFieldFocus(
                source_entity_uuid=context.source_entity_uuid,
                template=True,
            ),
        ],
    )


FIELD_KIT_DECLARATION = get_content_declaration(_build_field_kit)
FIELD_KIT_REF = FIELD_KIT_DECLARATION.ref


def field_kit_recipe(*, charges: int = 1) -> ContentRecipe:
    """Return an authenticated Field Kit recipe."""
    return ContentRecipe.create(
        ref=FIELD_KIT_REF,
        parameters={"charges": charges},
    )


FIELD_KIT_RECIPE = field_kit_recipe()
NEURODRAGON_FIELD_FOCUS_ITEM_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    FIELD_KIT_DECLARATION,
)
