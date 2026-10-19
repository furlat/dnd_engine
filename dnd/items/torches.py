"""Portable and fixed torch items with canonical portable-item content."""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.blocks.base_item import UsableItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
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
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.events import Event, EventPhase, EventQueue, ExposedFlameEvent
from dnd.types.discovery import ActorScan
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemLocation, ItemPresentationState
from dnd.entity import Entity
from dnd.core.base_object import empty_list


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
        default_factory=empty_list,
        description="No-cost action-economy payload for igniting a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action ignites.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if self.source_item_uuid is None:
            return "No torch linked"
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return "Torch not found"
        if torch.is_lit:
            return "Torch already lit"
        return None

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Ignite torch admitted",
        )
        if effect.canceled:
            return effect
        torch.ignite(
            self.source_entity_uuid,
            parent_event=effect.uuid,
        )
        return effect.with_updates(
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
        default_factory=empty_list,
        description="No-cost action-economy payload for extinguishing a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action extinguishes.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if self.source_item_uuid is None:
            return "No torch linked"
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return "Torch not found"
        if not torch.is_lit:
            return "Torch not lit"
        return None

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Extinguish torch admitted",
        )
        if effect.canceled:
            return effect
        torch.extinguish(parent_event=effect.uuid)
        return effect.with_updates(
            status_message="Torch extinguished",
        )


class Torch(UsableItem):
    """A portable torch whose temporary light follows its carrier."""
    creates = (IgniteTorchAction, ExtinguishTorchAction)

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

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add portable-torch light mechanics to the item fact."""
        return super().to_item_presentation_state(
            stack_count=stack_count,
        ).model_copy(update={
            "is_lit": self.is_lit,
            "very_bright_radius_feet": self.very_bright_radius_feet,
            "bright_radius_feet": self.bright_radius_feet,
            "dim_radius_feet": self.dim_radius_feet,
        })

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the ignite or extinguish action according to lit state."""
        if not self.is_lit:
            return [
                self.bind_dynamic_use_action(
                    IgniteTorchAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                        use_register=False,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                ExtinguishTorchAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                    use_register=False,
                ),
            )
        ]

    def ignite(
        self,
        carrier_entity_uuid: UUID,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Create the temporary carrier-anchored light for this torch."""
        if self.is_lit:
            return
        self.is_lit = True
        grid = get_map()
        entity = Entity.get(carrier_entity_uuid)
        if entity is None:
            return
        publish_event = entity.creation_committed
        self._light_source_uuid = grid.add_light_source(
            position=entity.position,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
            appearance="torch",
            anchor_uuid=carrier_entity_uuid,
            parent_event=parent_event,
            publish_event=publish_event,
        )
        if not publish_event:
            return
        flame_event = ExposedFlameEvent(
            source_entity_uuid=carrier_entity_uuid,
            target_entity_uuid=self.uuid,
            item_uuid=self.uuid,
            position=entity.position,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
        )
        effect = flame_event.phase_to(EventPhase.EFFECT)
        self.publish_location_state(
            ItemLocation.INVENTORY, owner_uuid=carrier_entity_uuid,
            container_uuid=self.stored_in_uuid, parent_event=effect,
        )
        effect.phase_to(EventPhase.COMPLETION)

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

        owner = Entity.get(self.owner_uuid) if self.owner_uuid is not None else None
        if owner is not None and owner.creation_committed:
            self.publish_location_state(
                ItemLocation.INVENTORY, owner_uuid=self.owner_uuid,
                container_uuid=self.stored_in_uuid,
                parent_event=(EventQueue.get_event_by_uuid(parent_event)
                    if parent_event is not None else None),
            )

    def is_exposed_flame(self) -> bool:
        """Return whether the torch is currently burning."""
        return self.is_lit

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

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Move a burning torch's exact light contribution to its accepted carrier."""
        if not self.is_lit:
            return
        carrier = Entity.get(entity_uuid)
        if carrier is None:
            self.extinguish()
            return
        if self._light_source_uuid in carrier.get_attached_light_sources():
            return
        grid = get_map()
        if self._light_source_uuid is not None:
            grid.remove_light_source(self._light_source_uuid)
        self._light_source_uuid = grid.add_light_source(
            position=carrier.position,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
            appearance="torch",
            anchor_uuid=entity_uuid,
            publish_event=carrier.creation_committed,
        )

    def _on_drop(
        self,
        entity_uuid: UUID,
        position: Tuple[int, int],
    ) -> None:
        """Auto-extinguish when dropped."""
        self.extinguish()
        super()._on_drop(entity_uuid, position)


def build_torch(source_entity_uuid: UUID) -> Torch:
    """Construct one unlit portable torch directly."""
    return Torch(
        source_entity_uuid=source_entity_uuid,
        item_id="equipment.portable_torch",
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
        default_factory=empty_list,
        description="No-cost action-economy payload for lighting a wall torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the wall torch item being lit.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if self.source_item_uuid is None:
            return "No wall torch linked"
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_active or torch.is_lit:
            return "Cannot light"
        return None

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_active:
            return execution_event.cancel(
                status_message="Wall torch not found",
            )
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Light wall torch admitted",
        )
        if effect.canceled:
            return effect
        torch.light(parent_event=effect.uuid)
        return effect.with_updates(
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
        default_factory=empty_list,
        description=(
            "No-cost action-economy payload for extinguishing a wall torch."
        ),
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the wall torch item being extinguished.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if self.source_item_uuid is None:
            return "No wall torch linked"
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_active or not torch.is_lit:
            return "Cannot extinguish"
        return None

    def _apply(
        self,
        execution_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(
                status_message="No wall torch linked",
            )
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_active:
            return execution_event.cancel(
                status_message="Wall torch not found",
            )
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Extinguish wall torch admitted",
        )
        if effect.canceled:
            return effect
        torch.put_out(parent_event=effect.uuid)
        return effect.with_updates(
            status_message="Wall torch extinguished",
        )


class WallTorch(UsableItem):
    """A fixed wall-mounted torch."""
    creates = (IgniteWallTorchAction, ExtinguishWallTorchAction)

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

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add fixed-torch light mechanics to the item fact."""
        return super().to_item_presentation_state(
            stack_count=stack_count,
        ).model_copy(update={
            "is_lit": self.is_lit,
            "very_bright_radius_feet": self.very_bright_radius_feet,
            "bright_radius_feet": self.bright_radius_feet,
            "dim_radius_feet": self.dim_radius_feet,
        })

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the light or extinguish action according to lit state."""
        if not self.is_active:
            return []
        if not self.is_lit:
            return [
                self.bind_dynamic_use_action(
                    IgniteWallTorchAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                        use_register=False,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                ExtinguishWallTorchAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                    use_register=False,
                ),
            )
        ]

    def light(
        self,
        parent_event: Optional[UUID] = None,
    ) -> Optional[ExposedFlameEvent]:
        """Create this fixture's fixed light source."""
        if not self.is_active or self.is_lit:
            return None
        placement = get_map().get_object_placement(self.uuid)
        if placement is None:
            return None
        position = placement.position
        current = EventQueue.publish_declaration(ExposedFlameEvent(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.uuid,
            item_uuid=self.uuid,
            position=position,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
            use_register=False,
        ))
        if current.canceled:
            return current
        current = current.phase_to(EventPhase.EXECUTION)
        if current.canceled:
            return current
        if not self.is_active:
            return current.cancel(status_message="Torch is destroyed")
        light_source_uuid = get_map().add_light_source(
            position=position,
            very_bright_radius_feet=self.very_bright_radius_feet,
            bright_radius_feet=self.bright_radius_feet,
            dim_radius_feet=self.dim_radius_feet,
            appearance="torch",
            anchor_uuid=self.uuid,
            parent_event=current.uuid,
        )
        self._light_source_uuid = light_source_uuid
        self.is_lit = True
        current = current.phase_to(EventPhase.EFFECT)
        if current.canceled:
            self.put_out(parent_event=current.uuid)
            return current
        self.publish_location_state(
            ItemLocation.FLOOR, world_placement=placement, parent_event=current,
        )
        return current.phase_to(EventPhase.COMPLETION)

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
        self.publish_location_state(
            ItemLocation.FLOOR,
            parent_event=(
                EventQueue.get_event_by_uuid(parent_event)
                if parent_event is not None else None
            ),
        )

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        self.put_out(parent_event=parent_event.uuid if parent_event is not None else None)
        super()._on_destroy(parent_event)

    def is_exposed_flame(self) -> bool:
        """Return whether the wall torch is currently burning."""
        return self.is_lit

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
        self.place_on_grid(position)
        if lit:
            self.light()


class StandingTorch(WallTorch):
    """A fixed freestanding torch using the ordinary fixture lifecycle."""

    name: str = Field(
        default="Standing Torch",
        description="Display name for the freestanding fixed torch.",
    )


__all__ = [
    "ExtinguishTorchAction",
    "ExtinguishWallTorchAction",
    "IgniteTorchAction",
    "IgniteWallTorchAction",
    "StandingTorch",
    "Torch",
    "build_torch",
    "WallTorch",
]
