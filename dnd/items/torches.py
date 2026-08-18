"""Portable and fixed torch items with canonical portable-item content."""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_actions import (
    BaseAction,
    Cost,
    TargetType,
)
from dnd.core.base_block import BaseBlock
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
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
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
from dnd.types.behaviors import RuntimeBehaviorKind
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
)
from dnd.core.events.world_events import (
    SpatialEffectInteractionEvent,
)
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.core.gridmap import get_map
from dnd.types.items import ItemLightSourceState
from dnd.entities.entity import Entity


def _torch_action_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    sort_order: int,
):
    """Declare one exact portable-torch action beside its providing item."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id="content.neurodragon",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("action", "item", "torch"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id,
                vfx_profile=content_id,
                ui_group="actions.item",
            ),
            ordering=ContentOrdering(
                sort_group="actions.item",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=(
                "Neurodragon original content baseline: "
                f"{display_name}"
            ),
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Existing portable-torch action preserved exactly.",
        ),
    )


@_torch_action_identity(
    content_id="action.item.torch.ignite",
    display_name="Ignite Torch",
    description="Ignite a carried torch.",
    sort_order=10,
)
class IgniteTorchAction(BaseAction):
    """Ignite a portable torch and anchor its light to the carrier."""

    name: str = Field(
        default="Ignite Torch",
        description="Action name for lighting a torch.",
    )
    description: str = Field(
        default="Light the torch",
        description="Action description shown for torch ignition.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description=(
            "Torch actions target the source user and resolve through "
            "source_item_uuid."
        ),
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for igniting a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action ignites.",
    )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return declaration_event.cancel(status_message="Torch not found")
        if torch.is_lit:
            return declaration_event.cancel(
                status_message="Torch already lit",
            )
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")
        torch.ignite(
            self.source_entity_uuid,
            parent_event=execution_event.uuid,
        )
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Torch ignited",
        )
        return effect.phase_to(
            EventPhase.COMPLETION,
            status_message="Torch ignited",
        )


@_torch_action_identity(
    content_id="action.item.torch.extinguish",
    display_name="Extinguish Torch",
    description="Extinguish a carried torch.",
    sort_order=20,
)
class ExtinguishTorchAction(BaseAction):
    """Extinguish a portable torch and remove its anchored light."""

    name: str = Field(
        default="Extinguish Torch",
        description="Action name for putting out a torch.",
    )
    description: str = Field(
        default="Put out the torch",
        description="Action description shown for torch extinguishing.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description=(
            "Torch actions target the source user and resolve through "
            "source_item_uuid."
        ),
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for extinguishing a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action extinguishes.",
    )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return declaration_event.cancel(status_message="Torch not found")
        if not torch.is_lit:
            return declaration_event.cancel(status_message="Torch not lit")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")
        torch.extinguish(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Torch extinguished",
        )
        return effect.phase_to(
            EventPhase.COMPLETION,
            status_message="Torch extinguished",
        )


class Torch(UsableItem):
    """A portable torch whose temporary light follows its carrier."""

    name: str = Field(
        default="Torch",
        description="Display name for the torch.",
    )
    description: str = Field(
        default=(
            "A torch that provides very bright light in 10ft, bright light "
            "in 10ft, and dim light in 20ft"
        ),
        description="Item description shown for the torch.",
    )
    is_equippable: bool = Field(
        default=False,
        description="Portable torches are carried and used, not equipped.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Portable torches can be picked up.",
    )
    map_char: str = Field(
        default="\u2666",
        description="Map glyph for the torch.",
    )

    very_bright_radius_feet: int = Field(
        default=10,
        description="Very-bright light radius emitted while lit.",
    )
    bright_radius_feet: int = Field(
        default=20,
        description="Bright light radius emitted while lit.",
    )
    dim_radius_feet: int = Field(
        default=20,
        description="Dim light radius emitted while lit.",
    )
    is_lit: bool = Field(
        default=False,
        description="Whether the torch currently has an attached light source.",
    )
    _light_source_uuid: Optional[UUID] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the ignite or extinguish action according to lit state."""
        if not self.is_lit:
            return [
                self.bind_dynamic_use_action(
                    IgniteTorchAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                ExtinguishTorchAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                ),
            )
        ]

    def get_light_source_state(self) -> ItemLightSourceState:
        """Return the torch's exact visible emitter state."""
        return ItemLightSourceState(
            is_lit=self.is_lit,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
        )

    def ignite(
        self,
        carrier_entity_uuid: UUID,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Create the temporary carrier-anchored light for this torch."""
        if self.is_lit:
            return
        entity = Entity.get(carrier_entity_uuid)
        if entity is None:
            return
        self.is_lit = True
        grid = get_map()
        self._light_source_uuid = grid.add_light_source(
            position=entity.position,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
            anchor_uuid=carrier_entity_uuid,
            parent_event=parent_event,
        )
        flame_event = SpatialEffectInteractionEvent(
            source_entity_uuid=carrier_entity_uuid,
            target_entity_uuid=self.uuid,
            operation=SpatialEffectInteractionOperation.IGNITE,
            positions=(entity.position,),
            source_object_uuid=self.uuid,
            source_content_ref=self.content_ref,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        EventQueue.publish_lifecycle(flame_event)

    def extinguish(self, parent_event: Optional[UUID] = None) -> None:
        """Remove this torch's temporary light."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid is not None:
            get_map().remove_light_source(
                self._light_source_uuid,
                parent_event=parent_event,
            )
            self._light_source_uuid = None

    def douse_exposed_flame(
        self,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Douse this torch through the shared exposed-flame surface."""
        if not self.is_lit:
            return False
        self.extinguish(parent_event=parent_event)
        return True

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        """Extinguish before destruction."""
        self.extinguish(
            parent_event=parent_event.uuid if parent_event is not None else None,
        )

    def _on_drop(
        self,
        entity_uuid: UUID,
        position: Tuple[int, int],
    ) -> None:
        """Auto-extinguish when dropped."""
        self.extinguish()
        super()._on_drop(entity_uuid, position)


class TorchParameters(BaseModel):
    """Portable torches have no authored construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _grants_torch_action(action_type: type[BaseAction]) -> ContentDependency:
    """Build one exact portable-torch provider-to-action dependency."""
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=get_content_declaration(action_type).ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        notes="Provided through the portable torch's state-dependent actions.",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="equipment.portable_torch",
    version=1,
    parameters=TorchParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Torch",
        description=(
            "A portable light source that can be ignited or extinguished."
        ),
        tags=("equipment", "light", "neurodragon", "utility"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="item.torch",
            visual_variant_key="portable_torch",
            ui_group="equipment.utility",
        ),
        ordering=ContentOrdering(
            sort_group="equipment.utility",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: portable torch"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Portable torch item and temporary light behavior preserved "
            "exactly."
        ),
    ),
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
    dependencies=(
        _grants_torch_action(IgniteTorchAction),
        _grants_torch_action(ExtinguishTorchAction),
    ),
)
def _build_torch(
    raw_context: object,
    parameters: TorchParameters,
) -> Torch:
    """Build one unlit portable torch; light state is encounter-only."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return Torch(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
    )


TORCH_DECLARATION = get_content_declaration(_build_torch)
TORCH_REF = TORCH_DECLARATION.ref
TORCH_RECIPE = ContentRecipe.create(ref=TORCH_REF, parameters={})
NEURODRAGON_TORCH_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    TORCH_DECLARATION,
)


def build_torch(source_entity_uuid: UUID) -> Torch:
    """Construct one unlit portable torch without a content recipe/runtime."""
    return Torch(
        source_entity_uuid=source_entity_uuid,
        semantic_key="equipment.portable_torch",
    )


class IgniteWallTorchAction(BaseAction):
    """Light a fixed wall torch."""

    name: str = Field(
        default="Light Wall Torch",
        description="Action name for lighting a wall torch.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Wall torch actions target the user.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for lighting a wall torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the wall torch item being lit.",
    )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or torch.is_lit:
            return declaration_event.cancel(status_message="Cannot light")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch):
            return execution_event.cancel(
                status_message="Wall torch not found",
            )
        torch.light(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Wall torch lit",
        )
        return effect.phase_to(
            EventPhase.COMPLETION,
            status_message="Wall torch lit",
        )


class ExtinguishWallTorchAction(BaseAction):
    """Put out a fixed wall torch."""

    name: str = Field(
        default="Extinguish Wall Torch",
        description="Action name for putting out a wall torch.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Wall torch actions target the user.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description=(
            "No-cost action-economy payload for extinguishing a wall torch."
        ),
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the wall torch item being extinguished.",
    )

    def _validate(
        self,
        declaration_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_lit:
            return declaration_event.cancel(
                status_message="Cannot extinguish",
            )
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated",
        )

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch):
            return execution_event.cancel(
                status_message="Wall torch not found",
            )
        torch.put_out(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Wall torch extinguished",
        )
        return effect.phase_to(
            EventPhase.COMPLETION,
            status_message="Wall torch extinguished",
        )


class WallTorch(UsableItem):
    """A fixed wall-mounted torch."""

    name: str = Field(
        default="Wall Torch",
        description="Display name for the wall torch.",
    )
    is_pickable: bool = Field(
        default=False,
        description="Wall torches are fixed environment objects.",
    )
    is_equippable: bool = Field(
        default=False,
        description="Wall torches cannot be equipped.",
    )
    map_char: str = Field(
        default="\u2666",
        description="Map glyph for the wall torch.",
    )

    very_bright_radius_feet: int = Field(
        default=5,
        description="Very-bright light radius emitted while lit.",
    )
    bright_radius_feet: int = Field(
        default=10,
        description="Bright light radius emitted while lit.",
    )
    dim_radius_feet: int = Field(
        default=10,
        description="Dim light radius emitted while lit.",
    )
    is_lit: bool = Field(
        default=False,
        description="Whether the wall torch currently has a light source.",
    )
    _light_source_uuid: Optional[UUID] = None
    _wall_torch_position: Optional[Tuple[int, int]] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the light or extinguish action according to lit state."""
        if not self.is_lit:
            return [
                self.bind_dynamic_use_action(
                    IgniteWallTorchAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                ExtinguishWallTorchAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                ),
            )
        ]

    def get_light_source_state(self) -> ItemLightSourceState:
        """Return the wall torch's exact visible emitter state."""
        return ItemLightSourceState(
            is_lit=self.is_lit,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
        )

    def light(self, parent_event: Optional[UUID] = None) -> None:
        """Create this fixture's fixed light source."""
        if self.is_lit:
            return
        if self._wall_torch_position is None:
            return
        self.is_lit = True
        self._light_source_uuid = get_map().add_light_source(
            position=self._wall_torch_position,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
            parent_event=parent_event,
        )
        flame_event = SpatialEffectInteractionEvent(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.uuid,
            operation=SpatialEffectInteractionOperation.IGNITE,
            positions=(self._wall_torch_position,),
            source_object_uuid=self.uuid,
            source_content_ref=self.content_ref,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        EventQueue.publish_lifecycle(flame_event)

    def put_out(self, parent_event: Optional[UUID] = None) -> None:
        """Remove this fixture's fixed light source."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid is not None:
            get_map().remove_light_source(
                self._light_source_uuid,
                parent_event=parent_event,
            )
            self._light_source_uuid = None

    def douse_exposed_flame(
        self,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Douse this wall torch through the exposed-flame surface."""
        if not self.is_lit:
            return False
        self.put_out(parent_event=parent_event)
        return True

    def mount(
        self,
        position: Tuple[int, int],
        *,
        lit: bool = True,
    ) -> None:
        """Place an already identity-bound fixture and apply its light state."""
        self._wall_torch_position = position
        self.place_on_grid(position)
        if lit:
            self.light()


__all__ = [
    "ExtinguishTorchAction",
    "ExtinguishWallTorchAction",
    "IgniteTorchAction",
    "IgniteWallTorchAction",
    "NEURODRAGON_TORCH_DECLARATIONS",
    "TORCH_DECLARATION",
    "TORCH_RECIPE",
    "TORCH_REF",
    "Torch",
    "TorchParameters",
    "build_torch",
    "WallTorch",
]
