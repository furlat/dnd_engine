"""Selected furniture profiles composed from ordinary item and terrain owners."""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.materials import Material
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec


@dataclass(frozen=True, slots=True)
class WorldPropProfile:
    name: str
    description: str
    destroyed_name: str
    destroyed_description: str
    footprint_offsets: tuple[tuple[int, int], ...]
    material: Material = Material.WOOD
    hit_points: int = 18
    difficult_debris: bool = False
    vertical_extent_steps: int = 1
    blocks_optics: bool = False
    blocks_propagation: bool = False


WORLD_PROP_PROFILES = MappingProxyType({
    "environment.furniture.bed": WorldPropProfile(
        name="Wooden bed", description="A wooden bed occupying two floor spaces.",
        destroyed_name="Broken wooden bed",
        destroyed_description="Collapsed wood and bedding; passable difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), difficult_debris=True,
    ),
    "environment.furniture.table": WorldPropProfile(
        name="Wooden table", description="A small wooden table occupying one floor space.",
        destroyed_name="Broken wooden table",
        destroyed_description="Collapsed wooden fragments; the space is passable.",
        footprint_offsets=((0, 0),),
    ),
    "environment.furniture.wardrobe": WorldPropProfile(
        name='Wooden wardrobe', description='A tall closed wooden wardrobe with a solid back.',
        destroyed_name='Broken wooden wardrobe',
        destroyed_description='Broken wooden wardrobe; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.bookshelf": WorldPropProfile(
        name='Bookshelf', description='A tall wooden bookcase filled with decorative books.',
        destroyed_name='Broken bookshelf',
        destroyed_description='Broken bookshelf; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=22,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.writing_desk": WorldPropProfile(
        name='Writing desk', description='A wooden writing desk with papers and an inkpot.',
        destroyed_name='Broken writing desk',
        destroyed_description='Broken writing desk; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=18,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.bedside_stand": WorldPropProfile(
        name='Bedside stand', description='A small wooden stand for a bedside.',
        destroyed_name='Broken bedside stand',
        destroyed_description='Broken bedside stand; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=12,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.work_stool": WorldPropProfile(
        name='Work stool', description='A low wooden workshop stool.',
        destroyed_name='Broken work stool',
        destroyed_description='Broken work stool; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=8,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.storage_shelving": WorldPropProfile(
        name='Storage shelving', description='Tall backed wooden shelves for household storage.',
        destroyed_name='Broken storage shelving',
        destroyed_description='Broken storage shelving; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=22,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.ingredient_shelves": WorldPropProfile(
        name='Ingredient shelves', description='A tall wooden shelf holding decorative ingredient jars.',
        destroyed_name='Broken ingredient shelves',
        destroyed_description='Broken ingredient shelves; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=20,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.preparation_counter": WorldPropProfile(
        name='Preparation counter', description='A low wooden preparation counter.',
        destroyed_name='Broken preparation counter',
        destroyed_description='Broken preparation counter; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=20,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.sack_bundles": WorldPropProfile(
        name='Sack bundles', description='A group of tied cloth sacks.',
        destroyed_name='Broken sack bundles',
        destroyed_description='Broken sack bundles; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=8,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.wooden_chair": WorldPropProfile(
        name='Wooden chair', description='A wooden chair with an open back.',
        destroyed_name='Broken wooden chair',
        destroyed_description='Broken wooden chair; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=10,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.wooden_bench": WorldPropProfile(
        name='Wooden bench', description='A low wooden bench.',
        destroyed_name='Broken wooden bench',
        destroyed_description='Broken wooden bench; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=18,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.pottery_jar": WorldPropProfile(
        name='Pottery jar', description='A single earthenware jar.',
        destroyed_name='Broken pottery jar',
        destroyed_description='Broken pottery jar; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=6,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.pottery_group": WorldPropProfile(
        name='Pottery jars', description='A group of earthenware jars.',
        destroyed_name='Broken pottery jars',
        destroyed_description='Broken pottery jars; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=10,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.pottery_cluster": WorldPropProfile(
        name='Pottery stack', description='A tall stack of earthenware jars.',
        destroyed_name='Broken pottery stack',
        destroyed_description='Broken pottery stack; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=18,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.barrel_cluster": WorldPropProfile(
        name='Barrel cluster', description='A group of ordinary wooden barrels.',
        destroyed_name='Broken barrel cluster',
        destroyed_description='Broken barrel cluster; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.crate_stack": WorldPropProfile(
        name='Crate stack', description='A low stack of wooden crates.',
        destroyed_name='Broken crate stack',
        destroyed_description='Broken crate stack; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=20,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.large_crate_stack": WorldPropProfile(
        name='Large crate stack', description='A tall, tightly packed stack of wooden crates.',
        destroyed_name='Broken large crate stack',
        destroyed_description='Broken large crate stack; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=30,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.animal_statue": WorldPropProfile(
        name='Animal statue', description='A stone animal sculpture on a round plinth.',
        destroyed_name='Broken animal statue',
        destroyed_description='Broken animal statue; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=36,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.winged_statue": WorldPropProfile(
        name='Winged statue', description='A winged stone figure on a round plinth.',
        destroyed_name='Broken winged statue',
        destroyed_description='Broken winged statue; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=36,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.stone_pedestal": WorldPropProfile(
        name='Stone pedestal', description='A slender ornamental stone pedestal.',
        destroyed_name='Broken stone pedestal',
        destroyed_description='Broken stone pedestal; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=27,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=False,
    ),
    "environment.furniture.stone_bench": WorldPropProfile(
        name='Stone bench', description='A low stone bench.',
        destroyed_name='Broken stone bench',
        destroyed_description='Broken stone bench; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=27,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
    ),

})

# Existing passive spatial-condition wire contract; no source or asset audit.
DEBRIS_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.furniture_debris", content_version=1,
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)


class DestructionDebris(BaseCondition):
    """An item's shared behavior owns one ordinary difficult-terrain region."""

    name: str = "Destruction debris"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    requires_intact_item: bool = False

    def on_owner_placement_committed(self, event: Event) -> None:
        if self.target_entity_uuid is None:
            return
        owner = BaseBlock.get(self.target_entity_uuid)
        if not isinstance(owner, BaseItem):
            return
        child = next((condition for _, identity in self.linked_conditions
                      if isinstance(condition := BaseCondition.get(identity), AreaCondition)), None)
        placement = get_map().get_object_placement(owner.uuid)
        if placement is None or owner.integrity is not ItemIntegrity.DESTROYED:
            if child is not None:
                child.deactivate(parent_event=event)
            return
        positions = set(placement.positions)
        # This fixed region's origin is a deterministic covered cell. The item
        # retains its own canonical anchor; this is not another item placement.
        origin = min(positions)
        if child is not None:
            previous_origin = child.position
            child.position = origin
            try:
                child.change_footprint(positions, parent_event=event)
            except BaseException:
                child.position = previous_origin
                raise
            return
        child = AreaCondition(
            source_entity_uuid=owner.uuid, name="Furniture debris",
            description="Broken furniture makes these floor spaces difficult terrain.",
            content_ref=DEBRIS_CONTENT_REF, position=origin, affected_positions=positions,
            layer=SpatialEffectLayer.GROUND_SURFACE,
            occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
            adds_difficult_terrain=True, requires_intact_item=False,
            duration=Duration(duration=None, duration_type=DurationType.PERMANENT),
        )
        result = child.activate(parent_event=event)
        if result is not None and not result.canceled and child.applied:
            self.add_linked_condition(child.uuid, child.uuid)


def settle_world_prop(item: BaseItem, parent_event: Event | None = None) -> None:
    """Install authored behavior and settle its actual committed placement."""
    profile = WORLD_PROP_PROFILES.get(item.item_id)
    if profile is None or not profile.difficult_debris:
        return
    if any(isinstance(condition, DestructionDebris) for condition in item.active_conditions.values()):
        return
    condition = DestructionDebris(
        source_entity_uuid=item.uuid, target_entity_uuid=item.uuid,
        duration=Duration(duration=None, duration_type=DurationType.PERMANENT),
    )
    result = item.add_condition(condition, parent_event=parent_event)
    if result is not None and not result.canceled and condition.applied:
        # Cold worlds already committed placement before publishing their first
        # fact. Settle from the real condition application, without replaying a
        # placement or inventing a previous destruction.
        condition.on_owner_placement_committed(result)


def build_world_prop(
    item_id: str, *, source_entity_uuid: UUID | None = None,
    hit_points: int | None = None, integrity: ItemIntegrity = ItemIntegrity.INTACT,
    defer_behaviors: bool = False,
) -> WorldItem:
    """Compose one selected physical profile, without placing or breaking it."""
    profile = WORLD_PROP_PROFILES[item_id]
    hp = profile.hit_points if hit_points is None else hit_points
    if hp < 1:
        raise ValueError("Furniture hit points must be positive")
    source = source_entity_uuid or uuid4()
    placement = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
        vertical_extent_steps=profile.vertical_extent_steps, footprint_offsets=profile.footprint_offsets)
    aftermath = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=False,
        vertical_extent_steps=1, footprint_offsets=profile.footprint_offsets)
    item = WorldItem(
        source_entity_uuid=source, item_id=item_id, name=profile.name,
        description=profile.description, tags=["furniture", profile.material.value],
        is_pickable=False, is_targetable=True, blocks_movement=True,
        blocks_optics_field=profile.blocks_optics, blocks_propagation_field=profile.blocks_propagation,
        health=BaseItem.create_item_health(source, hp), integrity=integrity,
        world_placement_spec=placement,
        destruction_profile=ItemDestructionProfile(
            name=profile.destroyed_name, description=profile.destroyed_description,
            placement_spec=aftermath,
        ),
    )
    if not defer_behaviors:
        settle_world_prop(item)
    return item
