"""Canonical content factories for production environment objects.

Positions, linked handler UUIDs, chest contents, and current light state are
encounter state.  The recipes in this module authenticate only authored
construction facts; callers materialize and bind an object before placing or
linking it in the active grid.
"""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.base_actions import BaseAction
from dnd.core.creature_types import DamageType
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
from dnd.core.content.identities import ContentRef
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
    environment_object_factory,
    get_content_declaration,
)
from dnd.items.environment import (
    CloseDirectionalDoorAction,
    DirectionalDoor,
    DirectionalWall,
    OpenDirectionalDoorAction,
)
from dnd.core.events import (
    Event,
    EventPhase,
    SpatialEffectInteractionEvent,
    TakeDamageEvent,
)
from dnd.types.world import WorldEdgeChannel

DIRECTIONS: tuple[str, ...] = ("north", "south", "east", "west")
DIRECTIONAL_CONTENT_CHANNELS: tuple[str, ...] = (
    "movement",
    "vision",
    "light",
    "propagation",
)


def _boundary_channels(
    authored_channels: tuple[str, ...],
) -> tuple[WorldEdgeChannel, ...]:
    """Reduce the frozen legacy recipe vocabulary to structural channels."""
    structural = {
        "movement": WorldEdgeChannel.MOVEMENT,
        "vision": WorldEdgeChannel.OPTICAL,
        "light": WorldEdgeChannel.OPTICAL,
        "propagation": WorldEdgeChannel.PROPAGATION,
    }
    try:
        requested = {structural[channel] for channel in authored_channels}
    except KeyError as error:
        raise ValueError(
            f"Unsupported boundary channel: {error.args[0]}"
        ) from error
    return tuple(
        channel for channel in WorldEdgeChannel if channel in requested
    )
from dnd.items.spell_items import SpellGrantingItem
from dnd.items.environment_interactables import (
    ActivateDeviceAction,
    ArcaneDevice,
    CloseDoorAction,
    CookAction,
    LootAllAction,
    OpenDoorAction,
    PullLeverAction,
    RestAction,
    StorageChest,
    DoorObject,
    TrapLever,
)
from dnd.items.torches import (
    ExtinguishWallTorchAction,
    IgniteWallTorchAction,
    WallTorch,
)
from dnd.spatial.environmental_conditions import OilSurface
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_NAME
from dnd.spells.evocation import Fireball, MagicMissile


_ENVIRONMENT_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.ENVIRONMENT,
)
_MAGIC_MISSILE_DECLARATION = SPELL_CONTENT_DECLARATIONS_BY_NAME[
    "Magic Missile"
]
_FIREBALL_DECLARATION = SPELL_CONTENT_DECLARATIONS_BY_NAME["Fireball"]


class EmptyEnvironmentParameters(BaseModel):
    """Environment roots with no authored construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DirectionalWallParameters(BaseModel):
    """Authored directional channels for one structural wall."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(default="Directional Wall", min_length=1)
    blocked_directions: tuple[str, ...] = Field(
        default_factory=lambda: DIRECTIONS,
    )
    blocked_channels: tuple[str, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CONTENT_CHANNELS,
    )


class DirectionalDoorParameters(DirectionalWallParameters):
    """Authored directional channels and initial state for one door."""

    display_name: str = Field(default="Directional Door", min_length=1)
    is_open: bool = False


class DoorParameters(BaseModel):
    """Initial state for the map-editor's global-blocking door."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_open: bool = False


class TrapLeverParameters(BaseModel):
    """Stable charge budget; linked trap UUIDs remain encounter state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = Field(default=1, ge=-1)


class StorageChestParameters(BaseModel):
    """Authored chest label and action surface, excluding runtime contents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(default="Chest", min_length=1)
    include_loot_all_action: bool = False


class ArcaneDeviceParameters(BaseModel):
    """Authored restoration value for the Arcana-gated device."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    heal_amount: int = Field(default=5, ge=0)


class FireballCannonParameters(BaseModel):
    """Finite authored charge budget for a Fireball cannon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = Field(default=3, ge=0)


def _descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    group: str,
    visual_variant_key: str,
    sort_order: int,
    tags: tuple[str, ...],
    related_content_refs: tuple[ContentRef, ...] = (),
) -> ContentDescriptorSpec:
    """Build one mechanics-free public environment presentation."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("environment", "neurodragon", *tags),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            sprite_key=visual_variant_key,
            visual_variant_key=visual_variant_key,
            ui_group=f"environment.{group}",
        ),
        ordering=ContentOrdering(
            sort_group=f"environment.{group}",
            sort_order=sort_order,
        ),
        related_content_refs=related_content_refs,
    )


def _provenance(display_name: str) -> ContentProvenance:
    """Return reviewed provenance for the retained environment mechanics."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Existing environment-object mechanics preserved exactly.",
    )


def _grants_spell(
    declaration: ContentDeclaration,
) -> ContentDependency:
    """Describe one runtime spell template granted by an environment object."""
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=declaration.ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
    )


def _grants_action(action_type: type[BaseAction]) -> ContentDependency:
    """Describe one exact action behavior granted by an environment object."""
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[action_type].ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.directional_wall",
    version=1,
    parameters=DirectionalWallParameters,
    descriptor=_descriptor(
        content_id="environment.directional_wall",
        display_name="Directional Wall",
        description="A structural wall that blocks selected spatial channels.",
        group="structures",
        visual_variant_key="directional_wall",
        sort_order=10,
        tags=("structure", "wall"),
    ),
    provenance=_provenance("Directional Wall"),
    item_definition=_ENVIRONMENT_DEFINITION,
)
def _build_directional_wall(
    raw_context: object,
    parameters: DirectionalWallParameters,
) -> DirectionalWall:
    context = ItemBuildContext.model_validate(raw_context)
    return DirectionalWall(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name,
        blocked_channels=_boundary_channels(parameters.blocked_channels),
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.directional_door",
    version=1,
    parameters=DirectionalDoorParameters,
    descriptor=_descriptor(
        content_id="environment.directional_door",
        display_name="Directional Door",
        description="A door that opens selected directional spatial channels.",
        group="structures",
        visual_variant_key="directional_door",
        sort_order=20,
        tags=("door", "structure"),
    ),
    provenance=_provenance("Directional Door"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(
        _grants_action(OpenDirectionalDoorAction),
        _grants_action(CloseDirectionalDoorAction),
    ),
)
def _build_directional_door(
    raw_context: object,
    parameters: DirectionalDoorParameters,
) -> DirectionalDoor:
    context = ItemBuildContext.model_validate(raw_context)
    return DirectionalDoor(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name,
        blocked_channels=_boundary_channels(parameters.blocked_channels),
        is_open=parameters.is_open,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.door",
    version=1,
    parameters=DoorParameters,
    descriptor=_descriptor(
        content_id="environment.door",
        display_name="Door",
        description="A fixed door that blocks movement and sight while closed.",
        group="structures",
        visual_variant_key="door",
        sort_order=30,
        tags=("door", "structure"),
    ),
    provenance=_provenance("Door"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(
        _grants_action(OpenDoorAction),
        _grants_action(CloseDoorAction),
    ),
)
def _build_door(
    raw_context: object,
    parameters: DoorParameters,
) -> DoorObject:
    context = ItemBuildContext.model_validate(raw_context)
    return DoorObject(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        is_open=parameters.is_open,
        blocks_movement=not parameters.is_open,
        blocks_optics_field=not parameters.is_open,
        blocks_propagation_field=not parameters.is_open,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.trap_lever",
    version=1,
    parameters=TrapLeverParameters,
    descriptor=_descriptor(
        content_id="environment.trap_lever",
        display_name="Trap Lever",
        description="A fixed lever that can deactivate a linked trap.",
        group="devices",
        visual_variant_key="trap_lever",
        sort_order=10,
        tags=("device", "lever", "trap"),
    ),
    provenance=_provenance("Trap Lever"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(_grants_action(PullLeverAction),),
)
def _build_trap_lever(
    raw_context: object,
    parameters: TrapLeverParameters,
) -> TrapLever:
    context = ItemBuildContext.model_validate(raw_context)
    return TrapLever(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        charges=parameters.charges,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.storage_chest",
    version=1,
    parameters=StorageChestParameters,
    descriptor=_descriptor(
        content_id="environment.storage_chest",
        display_name="Chest",
        description="A fixed container whose encounter contents can be looted.",
        group="containers",
        visual_variant_key="storage_chest",
        sort_order=10,
        tags=("chest", "container"),
    ),
    provenance=_provenance("Storage Chest"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(_grants_action(LootAllAction),),
)
def _build_storage_chest(
    raw_context: object,
    parameters: StorageChestParameters,
) -> StorageChest:
    context = ItemBuildContext.model_validate(raw_context)
    actions: list[BaseAction] = (
        [
            LootAllAction(
                source_entity_uuid=uuid4(),
                template=True,
            ),
        ]
        if parameters.include_loot_all_action
        else []
    )
    return StorageChest(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name,
        use_action_templates=actions,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.campfire",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.campfire",
        display_name="Campfire",
        description="A fixed camp object that supports resting and cooking.",
        group="camp",
        visual_variant_key="campfire",
        sort_order=10,
        tags=("camp", "fire"),
    ),
    provenance=_provenance("Campfire"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(
        _grants_action(RestAction),
        _grants_action(CookAction),
    ),
)
def _build_campfire(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> UsableItem:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return UsableItem(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Campfire",
        is_pickable=False,
        map_char="*",
        use_action_templates=[
            RestAction(source_entity_uuid=uuid4(), template=True),
            CookAction(source_entity_uuid=uuid4(), template=True),
        ],
    )


def _build_blocker(
    raw_context: object,
    *,
    name: str,
    hit_points: int,
    map_char: str,
    blocks_movement: bool,
    blocks_optics: bool,
    blocks_propagation: bool,
) -> BaseItem:
    context = ItemBuildContext.model_validate(raw_context)
    return BaseItem(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=name,
        is_pickable=False,
        is_targetable=True,
        health=BaseItem.create_item_health(
            context.source_entity_uuid,
            hit_points,
        ),
        map_char=map_char,
        blocks_movement=blocks_movement,
        blocks_optics_field=blocks_optics,
        blocks_propagation_field=blocks_propagation,
    )


class OilBarrel(BaseItem):
    """Destructible authored container that spills oil material."""

    def _on_destroy(self, parent_event: Event | None) -> None:
        """Spill oil and let fire damage ignite it through the live event."""
        spill_position = self.get_position()
        if spill_position is None:
            return
        if parent_event is None:
            raise ValueError("Oil Barrel destruction requires a causal event")

        oil = OilSurface(
            source_entity_uuid=parent_event.source_entity_uuid,
            position=spill_position,
            affected_positions={spill_position},
        )
        activation = oil.activate(parent_event=parent_event)
        if activation is None or activation.canceled or not oil.applied:
            return

        if (
            not isinstance(parent_event, TakeDamageEvent)
            or not any(
                damage.damage_type is DamageType.FIRE
                for damage in parent_event.damages
            )
        ):
            return

        interaction = SpatialEffectInteractionEvent(
            source_entity_uuid=parent_event.source_entity_uuid,
            source_entity_name=parent_event.source_entity_name,
            target_entity_uuid=oil.uuid,
            operation=SpatialEffectInteractionOperation.IGNITE,
            positions=(spill_position,),
            intensity=SpatialEffectInteractionIntensity.STRONG,
            damage_type=DamageType.FIRE,
            source_object_uuid=self.uuid,
            source_content_ref=self.content_ref,
            parent_event=parent_event.uuid,
            phase=EventPhase.DECLARATION,
        )
        interaction = interaction.phase_to(EventPhase.EXECUTION)
        if interaction.canceled:
            return
        interaction = interaction.phase_to(EventPhase.EFFECT)
        if interaction.canceled:
            return
        interaction.phase_to(EventPhase.COMPLETION)


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.blocker.crate",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.blocker.crate",
        display_name="Crate",
        description="A destructible crate.",
        group="breakables",
        visual_variant_key="crate",
        sort_order=10,
        tags=("breakable", "crate"),
    ),
    provenance=_provenance("Crate"),
    item_definition=_ENVIRONMENT_DEFINITION,
)
def _build_crate(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> BaseItem:
    _ = parameters
    return _build_blocker(
        raw_context,
        name="Crate",
        hit_points=20,
        map_char="C",
        blocks_movement=False,
        blocks_optics=False,
        blocks_propagation=False,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.blocker.boulder",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.blocker.boulder",
        display_name="Boulder",
        description="A durable boulder that blocks movement.",
        group="breakables",
        visual_variant_key="boulder",
        sort_order=20,
        tags=("blocker", "boulder"),
    ),
    provenance=_provenance("Boulder"),
    item_definition=_ENVIRONMENT_DEFINITION,
)
def _build_boulder(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> BaseItem:
    _ = parameters
    return _build_blocker(
        raw_context,
        name="Boulder",
        hit_points=30,
        map_char="B",
        blocks_movement=True,
        blocks_optics=False,
        blocks_propagation=False,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.blocker.barricade",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.blocker.barricade",
        display_name="Barricade",
        description="A destructible barricade that blocks movement and sight.",
        group="breakables",
        visual_variant_key="barricade",
        sort_order=30,
        tags=("barricade", "blocker", "breakable"),
    ),
    provenance=_provenance("Barricade"),
    item_definition=_ENVIRONMENT_DEFINITION,
)
def _build_barricade(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> BaseItem:
    _ = parameters
    return _build_blocker(
        raw_context,
        name="Barricade",
        hit_points=20,
        map_char="X",
        blocks_movement=True,
        blocks_optics=True,
        blocks_propagation=True,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.blocker.oil_barrel",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.blocker.oil_barrel",
        display_name="Oil Barrel",
        description="A destructible oil barrel that blocks movement.",
        group="breakables",
        visual_variant_key="oil_barrel",
        sort_order=40,
        tags=("barrel", "blocker", "breakable"),
    ),
    provenance=_provenance("Oil Barrel"),
    item_definition=_ENVIRONMENT_DEFINITION,
)
def _build_oil_barrel(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> OilBarrel:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return OilBarrel(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Oil Barrel",
        is_pickable=False,
        is_targetable=True,
        health=BaseItem.create_item_health(
            context.source_entity_uuid,
            12,
        ),
        map_char="O",
        blocks_movement=True,
        blocks_optics_field=False,
        blocks_propagation_field=False,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.wall_torch",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.wall_torch",
        display_name="Wall Torch",
        description="A fixed wall-mounted light source.",
        group="lights",
        visual_variant_key="wall_torch",
        sort_order=10,
        tags=("fixture", "light", "torch"),
    ),
    provenance=_provenance("Wall Torch"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(
        _grants_action(IgniteWallTorchAction),
        _grants_action(ExtinguishWallTorchAction),
    ),
)
def _build_wall_torch(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> WallTorch:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return WallTorch(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.arcane_device",
    version=1,
    parameters=ArcaneDeviceParameters,
    descriptor=_descriptor(
        content_id="environment.arcane_device",
        display_name="Arcane Device",
        description="An Arcana-gated fixed device that restores health.",
        group="devices",
        visual_variant_key="arcane_device",
        sort_order=20,
        tags=("arcane", "device"),
    ),
    provenance=_provenance("Arcane Device"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(_grants_action(ActivateDeviceAction),),
)
def _build_arcane_device(
    raw_context: object,
    parameters: ArcaneDeviceParameters,
) -> ArcaneDevice:
    context = ItemBuildContext.model_validate(raw_context)
    return ArcaneDevice(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        use_action_templates=[
            ActivateDeviceAction(
                source_entity_uuid=uuid4(),
                source_item_uuid=uuid4(),
                heal_amount=parameters.heal_amount,
                template=True,
            ),
        ],
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.arcane_machine_gun",
    version=1,
    parameters=EmptyEnvironmentParameters,
    descriptor=_descriptor(
        content_id="environment.arcane_machine_gun",
        display_name="Arcane Machine Gun",
        description="A fixed device with unlimited Magic Missile uses.",
        group="devices",
        visual_variant_key="arcane_machine_gun",
        sort_order=30,
        tags=("arcane", "device", "spell"),
        related_content_refs=(_MAGIC_MISSILE_DECLARATION.ref,),
    ),
    provenance=_provenance("Arcane Machine Gun"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(_grants_spell(_MAGIC_MISSILE_DECLARATION),),
)
def _build_arcane_machine_gun(
    raw_context: object,
    parameters: EmptyEnvironmentParameters,
) -> SpellGrantingItem:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return SpellGrantingItem(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Arcane Machine Gun",
        scroll_cast_level=1,
        charges=-1,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[
            MagicMissile(
                source_entity_uuid=uuid4(),
                caster_level=1,
                template=True,
            ),
        ],
    )


@environment_object_factory(
    pack_id="content.neurodragon",
    content_id="environment.fireball_cannon",
    version=1,
    parameters=FireballCannonParameters,
    descriptor=_descriptor(
        content_id="environment.fireball_cannon",
        display_name="Fireball Cannon",
        description="A fixed finite-charge device that casts Fireball.",
        group="devices",
        visual_variant_key="fireball_cannon",
        sort_order=40,
        tags=("arcane", "cannon", "device", "spell"),
        related_content_refs=(_FIREBALL_DECLARATION.ref,),
    ),
    provenance=_provenance("Fireball Cannon"),
    item_definition=_ENVIRONMENT_DEFINITION,
    dependencies=(_grants_spell(_FIREBALL_DECLARATION),),
)
def _build_fireball_cannon(
    raw_context: object,
    parameters: FireballCannonParameters,
) -> SpellGrantingItem:
    context = ItemBuildContext.model_validate(raw_context)
    return SpellGrantingItem(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Fireball Cannon",
        scroll_cast_level=3,
        charges=parameters.charges,
        max_charges=parameters.charges,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[
            Fireball(
                source_entity_uuid=uuid4(),
                caster_level=5,
                template=True,
            ),
        ],
    )


DIRECTIONAL_WALL_DECLARATION = get_content_declaration(
    _build_directional_wall,
)
DIRECTIONAL_DOOR_DECLARATION = get_content_declaration(
    _build_directional_door,
)
DOOR_DECLARATION = get_content_declaration(_build_door)
TRAP_LEVER_DECLARATION = get_content_declaration(_build_trap_lever)
STORAGE_CHEST_DECLARATION = get_content_declaration(_build_storage_chest)
CAMPFIRE_DECLARATION = get_content_declaration(_build_campfire)
CRATE_DECLARATION = get_content_declaration(_build_crate)
BOULDER_DECLARATION = get_content_declaration(_build_boulder)
BARRICADE_DECLARATION = get_content_declaration(_build_barricade)
OIL_BARREL_DECLARATION = get_content_declaration(_build_oil_barrel)
WALL_TORCH_DECLARATION = get_content_declaration(_build_wall_torch)
ARCANE_DEVICE_DECLARATION = get_content_declaration(_build_arcane_device)
ARCANE_MACHINE_GUN_DECLARATION = get_content_declaration(
    _build_arcane_machine_gun,
)
FIREBALL_CANNON_DECLARATION = get_content_declaration(
    _build_fireball_cannon,
)

DIRECTIONAL_WALL_REF = DIRECTIONAL_WALL_DECLARATION.ref
DIRECTIONAL_DOOR_REF = DIRECTIONAL_DOOR_DECLARATION.ref
DOOR_REF = DOOR_DECLARATION.ref
TRAP_LEVER_REF = TRAP_LEVER_DECLARATION.ref
STORAGE_CHEST_REF = STORAGE_CHEST_DECLARATION.ref
CAMPFIRE_REF = CAMPFIRE_DECLARATION.ref
CRATE_REF = CRATE_DECLARATION.ref
BOULDER_REF = BOULDER_DECLARATION.ref
BARRICADE_REF = BARRICADE_DECLARATION.ref
OIL_BARREL_REF = OIL_BARREL_DECLARATION.ref
WALL_TORCH_REF = WALL_TORCH_DECLARATION.ref
ARCANE_DEVICE_REF = ARCANE_DEVICE_DECLARATION.ref
ARCANE_MACHINE_GUN_REF = ARCANE_MACHINE_GUN_DECLARATION.ref
FIREBALL_CANNON_REF = FIREBALL_CANNON_DECLARATION.ref


def directional_wall_recipe(
    *,
    display_name: str = "Directional Wall",
    blocked_directions: tuple[str, ...] = DIRECTIONS,
    blocked_channels: tuple[str, ...] = DIRECTIONAL_CONTENT_CHANNELS,
) -> ContentRecipe:
    parameters = DirectionalWallParameters(
        display_name=display_name,
        blocked_directions=blocked_directions,
        blocked_channels=blocked_channels,
    )
    return ContentRecipe.create(
        ref=DIRECTIONAL_WALL_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def directional_door_recipe(
    *,
    display_name: str = "Directional Door",
    blocked_directions: tuple[str, ...] = DIRECTIONS,
    blocked_channels: tuple[str, ...] = DIRECTIONAL_CONTENT_CHANNELS,
    is_open: bool = False,
) -> ContentRecipe:
    parameters = DirectionalDoorParameters(
        display_name=display_name,
        blocked_directions=blocked_directions,
        blocked_channels=blocked_channels,
        is_open=is_open,
    )
    return ContentRecipe.create(
        ref=DIRECTIONAL_DOOR_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def door_recipe(*, is_open: bool = False) -> ContentRecipe:
    parameters = DoorParameters(is_open=is_open)
    return ContentRecipe.create(
        ref=DOOR_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def trap_lever_recipe(*, charges: int = 1) -> ContentRecipe:
    parameters = TrapLeverParameters(charges=charges)
    return ContentRecipe.create(
        ref=TRAP_LEVER_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def storage_chest_recipe(
    *,
    display_name: str = "Chest",
    include_loot_all_action: bool = False,
) -> ContentRecipe:
    parameters = StorageChestParameters(
        display_name=display_name,
        include_loot_all_action=include_loot_all_action,
    )
    return ContentRecipe.create(
        ref=STORAGE_CHEST_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def arcane_device_recipe(*, heal_amount: int = 5) -> ContentRecipe:
    parameters = ArcaneDeviceParameters(heal_amount=heal_amount)
    return ContentRecipe.create(
        ref=ARCANE_DEVICE_REF,
        parameters=parameters.model_dump(mode="json"),
    )


def fireball_cannon_recipe(*, charges: int = 3) -> ContentRecipe:
    parameters = FireballCannonParameters(charges=charges)
    return ContentRecipe.create(
        ref=FIREBALL_CANNON_REF,
        parameters=parameters.model_dump(mode="json"),
    )


DIRECTIONAL_WALL_RECIPE = directional_wall_recipe()
DIRECTIONAL_DOOR_RECIPE = directional_door_recipe()
DOOR_RECIPE = door_recipe()
TRAP_LEVER_RECIPE = trap_lever_recipe()
STORAGE_CHEST_RECIPE = storage_chest_recipe()
CAMPFIRE_RECIPE = ContentRecipe.create(
    ref=CAMPFIRE_REF,
    parameters={},
)
CRATE_RECIPE = ContentRecipe.create(ref=CRATE_REF, parameters={})
BOULDER_RECIPE = ContentRecipe.create(ref=BOULDER_REF, parameters={})
BARRICADE_RECIPE = ContentRecipe.create(
    ref=BARRICADE_REF,
    parameters={},
)
OIL_BARREL_RECIPE = ContentRecipe.create(
    ref=OIL_BARREL_REF,
    parameters={},
)
WALL_TORCH_RECIPE = ContentRecipe.create(
    ref=WALL_TORCH_REF,
    parameters={},
)
ARCANE_DEVICE_RECIPE = arcane_device_recipe()
ARCANE_MACHINE_GUN_RECIPE = ContentRecipe.create(
    ref=ARCANE_MACHINE_GUN_REF,
    parameters={},
)
FIREBALL_CANNON_RECIPE = fireball_cannon_recipe()

NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (
    DIRECTIONAL_WALL_DECLARATION,
    DIRECTIONAL_DOOR_DECLARATION,
    DOOR_DECLARATION,
    TRAP_LEVER_DECLARATION,
    STORAGE_CHEST_DECLARATION,
    CAMPFIRE_DECLARATION,
    CRATE_DECLARATION,
    BOULDER_DECLARATION,
    BARRICADE_DECLARATION,
    OIL_BARREL_DECLARATION,
    WALL_TORCH_DECLARATION,
    ARCANE_DEVICE_DECLARATION,
    ARCANE_MACHINE_GUN_DECLARATION,
    FIREBALL_CANNON_DECLARATION,
)

MAPEDITOR_ENVIRONMENT_CATALOG_ID_BY_REF = MappingProxyType({
    DIRECTIONAL_WALL_REF.identity_key: "directional_wall",
    DIRECTIONAL_DOOR_REF.identity_key: "directional_door",
    DOOR_REF.identity_key: "door",
    TRAP_LEVER_REF.identity_key: "trap_lever",
    STORAGE_CHEST_REF.identity_key: "storage_chest",
    CAMPFIRE_REF.identity_key: "campfire",
    CRATE_REF.identity_key: "crate",
    BOULDER_REF.identity_key: "boulder",
    BARRICADE_REF.identity_key: "barricade",
    OIL_BARREL_REF.identity_key: "oil_barrel",
    WALL_TORCH_REF.identity_key: "wall_torch",
    ARCANE_DEVICE_REF.identity_key: "arcane_device",
    ARCANE_MACHINE_GUN_REF.identity_key: "arcane_machine_gun",
    FIREBALL_CANNON_REF.identity_key: "fireball_cannon",
})


__all__ = [
    "ARCANE_DEVICE_RECIPE",
    "ARCANE_DEVICE_REF",
    "ARCANE_MACHINE_GUN_RECIPE",
    "ARCANE_MACHINE_GUN_REF",
    "BARRICADE_RECIPE",
    "BARRICADE_REF",
    "BOULDER_RECIPE",
    "BOULDER_REF",
    "CAMPFIRE_RECIPE",
    "CAMPFIRE_REF",
    "CRATE_RECIPE",
    "CRATE_REF",
    "DIRECTIONAL_DOOR_RECIPE",
    "DIRECTIONAL_DOOR_REF",
    "DIRECTIONAL_WALL_RECIPE",
    "DIRECTIONAL_WALL_REF",
    "DOOR_RECIPE",
    "DOOR_REF",
    "FIREBALL_CANNON_RECIPE",
    "FIREBALL_CANNON_REF",
    "MAPEDITOR_ENVIRONMENT_CATALOG_ID_BY_REF",
    "NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS",
    "OIL_BARREL_RECIPE",
    "OIL_BARREL_REF",
    "STORAGE_CHEST_RECIPE",
    "STORAGE_CHEST_REF",
    "TRAP_LEVER_RECIPE",
    "TRAP_LEVER_REF",
    "WALL_TORCH_RECIPE",
    "WALL_TORCH_REF",
    "arcane_device_recipe",
    "directional_door_recipe",
    "directional_wall_recipe",
    "door_recipe",
    "fireball_cannon_recipe",
    "storage_chest_recipe",
    "trap_lever_recipe",
]
