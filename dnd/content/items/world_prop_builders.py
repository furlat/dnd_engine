"""Selected furniture profiles composed from ordinary item and terrain owners."""

from dataclasses import dataclass
from typing import Literal
from types import MappingProxyType
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.content.items.object_defenses import OBJECT_ARMOR_CLASS_BY_MATERIAL
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.items.environment_interactables import LootAllAction, StorageChest
from dnd.items.searchables import install_search_gate
from dnd.items.shoving import SHOVEABLE_TAG
from dnd.items.visual_variants import ItemVisualVariantParameters
from dnd.spells.evocation import ContinualFlameCondition
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
    blocks_movement: bool = True
    occupies_bands: bool = True
    armor_class: int | None = None
    visual_variants: tuple[str, ...] = ()
    continual_flame: bool = False
    shoveable: bool = True


WORLD_PROP_PROFILES = MappingProxyType({
    "environment.furniture.bed": WorldPropProfile(
        name="Wooden bed", description="A wooden bed occupying two floor spaces.",
        destroyed_name="Broken wooden bed",
        destroyed_description="Collapsed wood and bedding; passable difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), difficult_debris=True,
        visual_variants=('green_bedding', 'red_white_striped_bedding', 'blue_white_diamond_bedding'),
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
        visual_variants=('knife_slashed',),
    ),
    "environment.furniture.bookshelf": WorldPropProfile(
        name='Bookshelf', description='A tall wooden bookcase filled with decorative books.',
        destroyed_name='Broken bookshelf',
        destroyed_description='Broken bookshelf; the remains leave difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=22,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
        visual_variants=('small', 'large', 'execution_logs'),
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
        visual_variants=('woodworking_bench',),
    ),
    "environment.furniture.sack_bundles": WorldPropProfile(
        name='Sack bundles', description='A group of tied cloth sacks.',
        destroyed_name='Broken sack bundles',
        destroyed_description='Broken sack bundles; the remains leave passable floor.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=8,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        visual_variants=('salt_sacks', 'spilled_sugar_sack'),
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

    'environment.furniture.clay_oven': WorldPropProfile(
        name='Unlit clay oven', description='Unlit clay oven; it gives off no light.',
        destroyed_name='Broken unlit clay oven',
        destroyed_description='Broken unlit clay oven; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=18,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.clay_stove': WorldPropProfile(
        name='Unlit clay stove', description='Unlit clay stove; it gives off no light.',
        destroyed_name='Broken unlit clay stove',
        destroyed_description='Broken unlit clay stove; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=15,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.lidded_vessel': WorldPropProfile(
        name='Lidded pottery vessel', description='Lidded pottery vessel.',
        destroyed_name='Broken lidded pottery vessel',
        destroyed_description='Broken lidded pottery vessel; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=6,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.parked_cart': WorldPropProfile(
        name='Parked wooden cart', description='Parked wooden cart.',
        destroyed_name='Broken parked wooden cart',
        destroyed_description='Broken parked wooden cart; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0), (1, 0)), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.loaded_wagon': WorldPropProfile(
        name='Parked loaded wagon', description='Parked loaded wagon.',
        destroyed_name='Broken parked loaded wagon',
        destroyed_description='Broken parked loaded wagon; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0), (1, 0)), material=Material.WOOD, hit_points=30,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.timber_pile': WorldPropProfile(
        name='Timber pile', description='Timber pile.',
        destroyed_name='Broken timber pile',
        destroyed_description='Broken timber pile; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=22,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.wheelbarrow': WorldPropProfile(
        name='Parked wheelbarrow', description='Parked wheelbarrow.',
        destroyed_name='Broken parked wheelbarrow',
        destroyed_description='Broken parked wheelbarrow; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.covered_market_counter': WorldPropProfile(
        name='Covered market counter', description='Covered market counter.',
        destroyed_name='Broken covered market counter',
        destroyed_description='Broken covered market counter; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.covered_handcart': WorldPropProfile(
        name='Parked covered handcart', description='Parked covered handcart.',
        destroyed_name='Broken parked covered handcart',
        destroyed_description='Broken parked covered handcart; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.pale_market_stall': WorldPropProfile(
        name='Pale market stall', description='Pale market stall.',
        destroyed_name='Broken pale market stall',
        destroyed_description='Broken pale market stall; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.training_dummy': WorldPropProfile(
        name='Training dummy', description='Training dummy.',
        destroyed_name='Broken training dummy',
        destroyed_description='Broken training dummy; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.grindstone': WorldPropProfile(
        name='Grindstone', description='Grindstone.',
        destroyed_name='Broken grindstone',
        destroyed_description='Broken grindstone; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.red_produce_stall': WorldPropProfile(
        name='Red produce stall', description='Red produce stall.',
        destroyed_name='Broken red produce stall',
        destroyed_description='Broken red produce stall; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.rough_market_stall': WorldPropProfile(
        name='Rough market stall', description='Rough market stall.',
        destroyed_name='Broken rough market stall',
        destroyed_description='Broken rough market stall; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.green_market_stall': WorldPropProfile(
        name='Green market stall', description='Green market stall.',
        destroyed_name='Broken green market stall',
        destroyed_description='Broken green market stall; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.produce_tub': WorldPropProfile(
        name='Produce tub', description='Produce tub.',
        destroyed_name='Broken produce tub',
        destroyed_description='Broken produce tub; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=10,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.hide_drying_rack': WorldPropProfile(
        name='Hide drying rack', description='Hide drying rack.',
        destroyed_name='Broken hide drying rack',
        destroyed_description='Broken hide drying rack; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=12,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.feed_trough': WorldPropProfile(
        name='Feed trough', description='Feed trough.',
        destroyed_name='Broken feed trough',
        destroyed_description='Broken feed trough; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.notice_board': WorldPropProfile(
        name='Notice board', description='Notice board.',
        destroyed_name='Broken notice board',
        destroyed_description='Broken notice board; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=12,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.wooden_crib': WorldPropProfile(
        name='Wooden crib', description='Wooden crib.',
        destroyed_name='Broken wooden crib',
        destroyed_description='Broken wooden crib; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.small_wooden_table': WorldPropProfile(
        name='Small wooden table', description='Small wooden table.',
        destroyed_name='Broken small wooden table',
        destroyed_description='Broken small wooden table; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=12,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.red_covered_table': WorldPropProfile(
        name='Red covered table', description='Red covered table.',
        destroyed_name='Broken red covered table',
        destroyed_description='Broken red covered table; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.pale_covered_table': WorldPropProfile(
        name='Pale covered table', description='Pale covered table.',
        destroyed_name='Broken pale covered table',
        destroyed_description='Broken pale covered table; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.short_red_banner': WorldPropProfile(
        name='Short freestanding red banner', description='Short freestanding red banner.',
        destroyed_name='Broken short freestanding red banner',
        destroyed_description='Broken short freestanding red banner; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=8,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.tall_red_banner': WorldPropProfile(
        name='Tall freestanding red banner', description='Tall freestanding red banner.',
        destroyed_name='Broken tall freestanding red banner',
        destroyed_description='Broken tall freestanding red banner; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=8,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
        visual_variants=('tattered_captured',),
    ),
    'environment.furniture.wooden_signpost': WorldPropProfile(
        name='Wooden signpost', description='Wooden signpost.',
        destroyed_name='Broken wooden signpost',
        destroyed_description='Broken wooden signpost; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=12,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.framed_notice_board': WorldPropProfile(
        name='Framed notice board', description='Framed notice board.',
        destroyed_name='Broken framed notice board',
        destroyed_description='Broken framed notice board; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.archery_target': WorldPropProfile(
        name='Archery target', description='Archery target.',
        destroyed_name='Broken archery target',
        destroyed_description='Broken archery target; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=15,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.felled_log': WorldPropProfile(
        name='Felled log', description='Felled log.',
        destroyed_name='Broken felled log',
        destroyed_description='Broken felled log; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0), (1, 0)), material=Material.WOOD, hit_points=18,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.workshop_apparatus': WorldPropProfile(
        name='Workshop apparatus', description='Workshop apparatus.',
        destroyed_name='Broken workshop apparatus',
        destroyed_description='Broken workshop apparatus; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=18,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
        visual_variants=('metal_tools', 'carpentry_tools'),
    ),
    'environment.furniture.alchemy_bench': WorldPropProfile(
        name='Alchemy bench', description='Alchemy bench.',
        destroyed_name='Broken alchemy bench',
        destroyed_description='Broken alchemy bench; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=18,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.anvil': WorldPropProfile(
        name='Anvil', description='Anvil.',
        destroyed_name='Broken anvil',
        destroyed_description='Broken anvil; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=30,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.cannonball_pile': WorldPropProfile(
        name='Cannonball pile', description='Cannonball pile.',
        destroyed_name='Broken cannonball pile',
        destroyed_description='Broken cannonball pile; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=24,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.unlit_crucible': WorldPropProfile(
        name='Unlit stone crucible', description='Unlit stone crucible; it gives off no light.',
        destroyed_name='Broken unlit stone crucible',
        destroyed_description='Broken unlit stone crucible; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=30,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.grave_marker': WorldPropProfile(
        name='Stone grave marker', description='Stone grave marker.',
        destroyed_name='Broken stone grave marker',
        destroyed_description='Broken stone grave marker; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=18,
        difficult_debris=True, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.slender_monument': WorldPropProfile(
        name='Slender stone monument', description='Slender stone monument.',
        destroyed_name='Broken slender stone monument',
        destroyed_description='Broken slender stone monument; the remains make the floor difficult terrain.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=30,
        difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.hay_bale': WorldPropProfile(
        name='Hay bale', description='Hay bale.',
        destroyed_name='Broken hay bale',
        destroyed_description='Broken hay bale; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=8,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.hay_bales_stacked': WorldPropProfile(
        name='Stacked hay bales', description='Stacked hay bales.',
        destroyed_name='Broken stacked hay bales',
        destroyed_description='Broken stacked hay bales; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=12,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.hay_bales_upright': WorldPropProfile(
        name='Upright hay bales', description='Upright hay bales.',
        destroyed_name='Broken upright hay bales',
        destroyed_description='Broken upright hay bales; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=12,
        difficult_debris=False, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.hay_bales_leaning': WorldPropProfile(
        name='Leaning hay bales', description='Leaning hay bales.',
        destroyed_name='Broken leaning hay bales',
        destroyed_description='Broken leaning hay bales; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=12,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
    ),
    'environment.furniture.unlit_candlesticks': WorldPropProfile(
        name='Unlit candlesticks', description='Unlit candlesticks; it gives off no light.',
        destroyed_name='Broken unlit candlesticks',
        destroyed_description='Broken unlit candlesticks; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=6,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=True,
        blocks_movement=True, occupies_bands=True,
        visual_variants=('large_candelabrum', 'black_shrine_candles'),
    ),
    'environment.furniture.spent_ashes': WorldPropProfile(
        name='Spent fire remains', description='Spent fire remains. A flat floor covering.',
        destroyed_name='Broken spent fire remains',
        destroyed_description='Broken spent fire remains; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.EARTH, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
        visual_variants=('burned_furniture',),
    ),
    'environment.furniture.red_rug': WorldPropProfile(
        name='Red rug', description='Red rug. A flat floor covering.',
        destroyed_name='Broken red rug',
        destroyed_description='Broken red rug; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=6,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.pale_rug': WorldPropProfile(
        name='Pale rug', description='Pale rug. A flat floor covering.',
        destroyed_name='Broken pale rug',
        destroyed_description='Broken pale rug; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=6,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_1': WorldPropProfile(
        name='Loose straw 1', description='Loose straw 1. A flat floor covering.',
        destroyed_name='Broken loose straw 1',
        destroyed_description='Broken loose straw 1; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_2': WorldPropProfile(
        name='Loose straw 2', description='Loose straw 2. A flat floor covering.',
        destroyed_name='Broken loose straw 2',
        destroyed_description='Broken loose straw 2; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_3': WorldPropProfile(
        name='Loose straw 3', description='Loose straw 3. A flat floor covering.',
        destroyed_name='Broken loose straw 3',
        destroyed_description='Broken loose straw 3; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_4': WorldPropProfile(
        name='Loose straw 4', description='Loose straw 4. A flat floor covering.',
        destroyed_name='Broken loose straw 4',
        destroyed_description='Broken loose straw 4; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_5': WorldPropProfile(
        name='Loose straw 5', description='Loose straw 5. A flat floor covering.',
        destroyed_name='Broken loose straw 5',
        destroyed_description='Broken loose straw 5; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_6': WorldPropProfile(
        name='Loose straw 6', description='Loose straw 6. A flat floor covering.',
        destroyed_name='Broken loose straw 6',
        destroyed_description='Broken loose straw 6; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_straw_7': WorldPropProfile(
        name='Loose straw 7', description='Loose straw 7. A flat floor covering.',
        destroyed_name='Broken loose straw 7',
        destroyed_description='Broken loose straw 7; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.VEGETATION, hit_points=4,
        difficult_debris=False, vertical_extent_steps=1,
        blocks_optics=False, blocks_propagation=False,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.cold_fire_pit': WorldPropProfile(
        name='Cold fire pit', description='A low ring of stones surrounding cold embers.',
        destroyed_name='Broken cold fire pit',
        destroyed_description='Broken cold fire pit; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.STONE, hit_points=12,
        blocks_movement=False, occupies_bands=False,
    ),
    'environment.furniture.loose_floorboards': WorldPropProfile(
        name='Loose floorboards', description='Wooden boards lying flat on the floor.',
        destroyed_name='Broken loose floorboards',
        destroyed_description='Broken loose floorboards; the remains leave the floor passable.',
        footprint_offsets=((0, 0),), material=Material.WOOD, hit_points=8,
        blocks_movement=False, occupies_bands=False,
    ),
    # Triskelion Outer Ward bodies (content push plan §4.A); fixtures built in place are not shoveable. Hit points use the DMG object table's
    # resilient values (small 10, medium 18, large 27); cloth, paper, glass and stuffed bodies get less,
    # and carved stone more, as the file's earlier statues do. Wall-side decor is nonblocking and
    # stands in the cell beside its wall, as the wall torch does. Colour, bedding and subject
    # differences are visual variants of one body. The vocabulary has no ceramic or hide: porcelain
    # uses GLASS and taxidermy FABRIC, the closest object defences.
    "environment.furniture.long_dining_table": WorldPropProfile(
        name="Long dining table", description="A long, firm wooden table for a crowded hall.",
        destroyed_name="Broken long table", destroyed_description="Split boards and trestles; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (2, 0)), hit_points=27, difficult_debris=True,
    ),
    "environment.furniture.long_bench": WorldPropProfile(
        name="Long bench", description="A long wooden bench beside a dining table.",
        destroyed_name="Broken long bench", destroyed_description="Split bench planks; the space is passable.",
        footprint_offsets=((0, 0), (1, 0), (2, 0)),
    ),
    "environment.furniture.card_table": WorldPropProfile(
        name="Card table", description="A small green-felt card table.",
        destroyed_name="Broken card table", destroyed_description="Torn felt and splinters; the space is passable.",
        footprint_offsets=((0, 0),), hit_points=10,
    ),
    "environment.furniture.card_table_stack": WorldPropProfile(
        name="Stack of card tables", description="Green-felt card tables piled on top of each other.",
        destroyed_name="Collapsed card tables", destroyed_description="Fallen tables and felt; difficult terrain.",
        footprint_offsets=((0, 0),), hit_points=27, difficult_debris=True, vertical_extent_steps=2,
    ),
    "environment.furniture.coffee_table": WorldPropProfile(
        name="Coffee table", description="A short, low table.",
        destroyed_name="Broken coffee table", destroyed_description="Splintered wood; the space is passable.",
        footprint_offsets=((0, 0),), hit_points=10,
    ),
    "environment.furniture.worktable": WorldPropProfile(
        name="Worktable", description="A heavy work surface for tools and oils.",
        destroyed_name="Broken worktable", destroyed_description="Split planks and scattered tools; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), hit_points=27, difficult_debris=True,
    ),
    "environment.furniture.bar_counter": WorldPropProfile(
        name="Bar counter", description="A section of a heavy wooden tavern bar.",
        destroyed_name="Smashed bar counter", destroyed_description="Splintered counter; difficult terrain.",
        footprint_offsets=((0, 0),), hit_points=27, difficult_debris=True,
        visual_variants=("straight", "end"),
        shoveable=False,
    ),
    "environment.furniture.large_desk": WorldPropProfile(
        name="Large desk", description="A huge wooden desk.",
        destroyed_name="Broken large desk", destroyed_description="Split desk and drawers; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), hit_points=27, difficult_debris=True,
    ),
    "environment.furniture.overturned_desk": WorldPropProfile(
        name="Overturned desk", description="A desk turned on its side, one leg torn off.",
        destroyed_name="Broken desk", destroyed_description="Splintered desk; difficult terrain.",
        footprint_offsets=((0, 0),), hit_points=10, difficult_debris=True,
    ),
    "environment.furniture.massive_chair": WorldPropProfile(
        name="Massive wooden chair", description="A heavy, high-backed wooden chair.",
        destroyed_name="Broken massive chair", destroyed_description="Split wood; the space is passable.",
        footprint_offsets=((0, 0),),
    ),
    "environment.furniture.restraint_chair": WorldPropProfile(
        name="Restraint chair", description="A sturdy wooden chair with guards for the neck and wrists.",
        destroyed_name="Broken restraint chair", destroyed_description="Split wood and bent guards; passable.",
        footprint_offsets=((0, 0),),
    ),
    "environment.furniture.padded_chair": WorldPropProfile(
        name="Padded chair", description="An upholstered chair.",
        destroyed_name="Broken padded chair", destroyed_description="Torn padding and wood; passable.",
        footprint_offsets=((0, 0),), hit_points=10,
    ),
    "environment.furniture.couch": WorldPropProfile(
        name="Couch", description="An upholstered couch.",
        destroyed_name="Broken couch", destroyed_description="Torn upholstery and frame; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), difficult_debris=True,
        visual_variants=("black_white_striped", "dark_green", "pink_light_blue_striped", "red_gray", "lounge"),
    ),
    "environment.furniture.cot": WorldPropProfile(
        name="Cot", description="A narrow, foul cot.",
        destroyed_name="Broken cot", destroyed_description="Torn canvas and sticks; passable.",
        footprint_offsets=((0, 0), (1, 0)), hit_points=5,
    ),
    "environment.furniture.four_poster_bed": WorldPropProfile(
        name="Four-poster bed", description="A large bed with tall corner posts.",
        destroyed_name="Collapsed four-poster bed", destroyed_description="Fallen posts and bedding; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), hit_points=27, difficult_debris=True,
        vertical_extent_steps=2, visual_variants=("red_neat", "stained_ripped", "large_comfortable"),
    ),
    "environment.furniture.dresser": WorldPropProfile(
        name="Dresser", description="A wooden chest of drawers.",
        destroyed_name="Broken dresser", destroyed_description="Split drawers; difficult terrain.",
        footprint_offsets=((0, 0),), difficult_debris=True,
    ),
    "environment.furniture.mirrored_dresser": WorldPropProfile(
        name="Dresser with mirror", description="A dresser with an attached mirror.",
        destroyed_name="Broken mirrored dresser", destroyed_description="Split wood and mirror shards; difficult terrain.",
        footprint_offsets=((0, 0),), difficult_debris=True, vertical_extent_steps=2,
        visual_variants=("mirror_smashed",),
    ),
    "environment.furniture.armoire": WorldPropProfile(
        name="Armoire", description="A tall closed armoire with a solid back.",
        destroyed_name="Broken armoire", destroyed_description="Broken armoire; the remains leave difficult terrain.",
        footprint_offsets=((0, 0),), hit_points=24, difficult_debris=True, vertical_extent_steps=2,
        blocks_optics=True, blocks_propagation=True,
    ),
    "environment.furniture.cabinet": WorldPropProfile(
        name="Cabinet", description="A closed wooden cabinet with shelves.",
        destroyed_name="Broken cabinet", destroyed_description="Split shelves; difficult terrain.",
        footprint_offsets=((0, 0),), difficult_debris=True, vertical_extent_steps=2,
        visual_variants=("white_mermaid", "white_bath"),
    ),
    "environment.furniture.hat_rack": WorldPropProfile(
        name="Hat rack", description="An ornate standing hat rack.",
        destroyed_name="Broken hat rack", destroyed_description="Snapped pole; passable.",
        footprint_offsets=((0, 0),), hit_points=5, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.surplus_furniture": WorldPropProfile(
        name="Surplus furniture", description="Musty odd pieces of furniture piled together.",
        destroyed_name="Broken surplus furniture", destroyed_description="Splintered junk; difficult terrain.",
        footprint_offsets=((0, 0),), difficult_debris=True,
    ),
    "environment.furniture.unfinished_coffin": WorldPropProfile(
        name="Unfinished coffin", description="A partly assembled pine coffin frame.",
        destroyed_name="Broken coffin frame", destroyed_description="Loose pine boards; passable.",
        footprint_offsets=((0, 0), (1, 0)), hit_points=5,
    ),
    "environment.furniture.dog_hutch": WorldPropProfile(
        name="Dog hutch", description="A wooden kennel hutch.",
        destroyed_name="Broken dog hutch", destroyed_description="Splintered planks; passable.",
        footprint_offsets=((0, 0),), hit_points=10,
    ),
    "environment.furniture.bucket": WorldPropProfile(
        name="Bucket", description="A wooden bucket.",
        destroyed_name="Broken bucket", destroyed_description="Split staves; passable.",
        footprint_offsets=((0, 0),), hit_points=3, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.teapot": WorldPropProfile(
        name="Teapot", description="A porcelain teapot catching drips.",
        destroyed_name="Shattered teapot", destroyed_description="Porcelain shards; passable.",
        footprint_offsets=((0, 0),), material=Material.GLASS, hit_points=2,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.metal_vat": WorldPropProfile(
        name="Metal vat", description="A large metal vat once used to hold water.",
        destroyed_name="Crumpled vat", destroyed_description="Bent metal; difficult terrain.",
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=27, difficult_debris=True,
    ),
    "environment.furniture.hand_pump": WorldPropProfile(
        name="Hand pump", description="A free-standing iron hand pump.",
        destroyed_name="Broken hand pump", destroyed_description="Bent iron; passable.",
        footprint_offsets=((0, 0),), material=Material.METAL,
        shoveable=False,
    ),
    "environment.furniture.wall_pump": WorldPropProfile(
        name="Wall pump", description="A broken iron pump on the wall, still dripping.",
        destroyed_name="Broken wall pump", destroyed_description="Bent pipe against the wall.",
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=10,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.pump_faucet": WorldPropProfile(
        name="Pump faucet", description="A painted pump faucet on the wall.",
        destroyed_name="Broken faucet", destroyed_description="A twisted faucet against the wall.",
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=5,
        blocks_movement=False, occupies_bands=False, visual_variants=("blue_cold", "red_hot"),
    ),
    "environment.furniture.privy_seat": WorldPropProfile(
        name="Privy seat", description="An alcove with a board with a hole.",
        destroyed_name="Broken privy seat", destroyed_description="Split board; passable.",
        footprint_offsets=((0, 0),), hit_points=5,
        shoveable=False,
    ),
    "environment.furniture.porcelain_toilet": WorldPropProfile(
        name="Porcelain toilet", description="A white and blue porcelain toilet.",
        destroyed_name="Shattered toilet", destroyed_description="Porcelain shards; passable.",
        footprint_offsets=((0, 0),), material=Material.GLASS, hit_points=5,
        shoveable=False,
    ),
    "environment.furniture.brass_bathtub": WorldPropProfile(
        name="Brass bathtub", description="A large ornamental brass bathtub.",
        destroyed_name="Dented bathtub", destroyed_description="Crumpled brass; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), material=Material.METAL, hit_points=27, difficult_debris=True,
        visual_variants=("huge",),
        shoveable=False,
    ),
    "environment.furniture.nymph_fountain": WorldPropProfile(
        name="Nymph fountain", description="A black marble nymph pouring a foul trickle into a blood-red stone basin.",
        destroyed_name="Shattered fountain", destroyed_description="Broken marble and basin; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), material=Material.STONE, hit_points=54,
        difficult_debris=True, vertical_extent_steps=2,
        shoveable=False,
    ),
    "environment.furniture.headsman_block": WorldPropProfile(
        name="Headsman's block", description="A gore-besmirched wooden block.",
        destroyed_name="Split block", destroyed_description="Split wood; passable.",
        footprint_offsets=((0, 0),),
    ),
    "environment.furniture.triskelion_statue": WorldPropProfile(
        name="Triskelion statue",
        description="A three-faced, three-armed marble statue holding a staff, a sword and a whip.",
        destroyed_name="Shattered statue", destroyed_description="Marble rubble; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), material=Material.STONE, hit_points=54,
        difficult_debris=True, vertical_extent_steps=2,
        shoveable=False,
    ),
    "environment.furniture.shrine_platform": WorldPropProfile(
        name="Shrine platform", description="A marble platform crowded with black candles.",
        destroyed_name="Broken shrine", destroyed_description="Cracked marble; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), material=Material.STONE, hit_points=27, difficult_debris=True,
        shoveable=False,
    ),
    "environment.furniture.armor_stand": WorldPropProfile(
        name="Armor stand", description="A stand for a full suit of armor.",
        destroyed_name="Toppled armor stand", destroyed_description="Bent frame; passable.",
        footprint_offsets=((0, 0),), material=Material.METAL,
        visual_variants=("gilded_plate", "gilded_plate_without_helm"),
    ),
    "environment.furniture.manikin": WorldPropProfile(
        name="Wooden manikin", description="A featureless wooden manikin for hanging clothes.",
        destroyed_name="Broken manikin", destroyed_description="Split wood; passable.",
        footprint_offsets=((0, 0),), hit_points=10,
    ),
    "environment.furniture.taxidermy_large": WorldPropProfile(
        name="Stuffed animal", description="A large mounted animal.",
        destroyed_name="Torn taxidermy", destroyed_description="Hide, stuffing and frame; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), material=Material.FABRIC, hit_points=10,
        difficult_debris=True, vertical_extent_steps=2,
        visual_variants=("bear", "bear_partly_eaten", "elk", "hippogriff"),
    ),
    "environment.furniture.taxidermy_long": WorldPropProfile(
        name="Stuffed lion", description="A mounted lion.",
        destroyed_name="Torn taxidermy", destroyed_description="Hide and stuffing; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), material=Material.FABRIC, hit_points=10, difficult_debris=True,
    ),
    "environment.furniture.taxidermy_small": WorldPropProfile(
        name="Stuffed animal", description="A small mounted animal.",
        destroyed_name="Torn taxidermy", destroyed_description="Hide and stuffing; passable.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=5,
        visual_variants=("wolf", "giant_skunk", "small_cluster"),
    ),
    "environment.furniture.eagle_perch": WorldPropProfile(
        name="Mounted eagle", description="A stuffed eagle on a wooden perch shaped like a tree limb.",
        destroyed_name="Broken perch", destroyed_description="Snapped perch and feathers; passable.",
        footprint_offsets=((0, 0),), hit_points=5,
    ),
    "environment.furniture.dragon_skeleton": WorldPropProfile(
        name="Dragon skeleton", description="An eighteen-foot dragon skeleton hung on wires from the ceiling.",
        destroyed_name="Fallen dragon bones", destroyed_description="Scattered bones; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1)),
        material=Material.BONE, hit_points=27, difficult_debris=True, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.bronze_chandelier": WorldPropProfile(
        name="Bronze chandelier", description="A large unlit bronze chandelier hanging from the ceiling.",
        destroyed_name="Fallen chandelier", destroyed_description="Bent bronze; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), material=Material.METAL, hit_points=18,
        difficult_debris=True, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.crystal_chandelier": WorldPropProfile(
        name="Red crystal chandelier", description="An unlit red crystal chandelier hanging from the ceiling.",
        destroyed_name="Fallen chandelier", destroyed_description="Red crystal shards; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0), (0, 1), (1, 1)), material=Material.GLASS, hit_points=4,
        difficult_debris=True, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.wall_rack": WorldPropProfile(
        name="Wall rack", description="A rack against the wall.",
        destroyed_name="Broken wall rack", destroyed_description="Splintered rack against the wall.",
        footprint_offsets=((0, 0),), hit_points=10, blocks_movement=False, occupies_bands=False,
        visual_variants=("bardiches", "polearms", "swords", "weapons_and_armor", "practice_weapons", "tools"),
    ),
    "environment.furniture.tapestry": WorldPropProfile(
        name="Hanging tapestry", description="A large hunting-scene tapestry hanging on the wall.",
        destroyed_name="Shredded tapestry", destroyed_description="Torn cloth against the wall.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=5,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.rolled_tapestry": WorldPropProfile(
        name="Rolled tapestry", description="A bulky, moldy rolled tapestry.",
        destroyed_name="Shredded tapestry", destroyed_description="Torn cloth; passable.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=5,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.curtains": WorldPropProfile(
        name="Curtains", description="Curtains hanging along the wall.",
        destroyed_name="Torn curtains", destroyed_description="Shredded cloth against the wall.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=3,
        blocks_movement=False, occupies_bands=False, visual_variants=("red_frayed", "green", "red_white_striped"),
    ),
    "environment.furniture.tavern_sign": WorldPropProfile(
        name="Tavern sign", description="A sign showing a pale yellow bear skull on blue.",
        destroyed_name="Broken sign", destroyed_description="Splintered sign against the wall.",
        footprint_offsets=((0, 0),), hit_points=5, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.mounted_shield": WorldPropProfile(
        name="Mounted kite shield", description="A kite shield bearing the Triskelion insignia, hung on the wall.",
        destroyed_name="Broken shield", destroyed_description="A split shield against the wall.",
        footprint_offsets=((0, 0),), hit_points=10, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.dartboard": WorldPropProfile(
        name="Dartboard", description="A dartboard on the wall.",
        destroyed_name="Broken dartboard", destroyed_description="Split cork and wood against the wall.",
        footprint_offsets=((0, 0),), hit_points=3, blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.mounted_antlers": WorldPropProfile(
        name="Mounted antlers", description="Antlers and deer heads lining the wall.",
        destroyed_name="Broken trophies", destroyed_description="Fallen antlers against the wall.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=5,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.framed_painting": WorldPropProfile(
        name="Framed painting", description="A framed painting on the wall.",
        destroyed_name="Slashed painting", destroyed_description="A slashed canvas in its frame.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=3,
        blocks_movement=False, occupies_bands=False,
        visual_variants=("santiago", "alfonsina", "vittorino", "sergi", "luciana_and_salvatrice", "the_hunt"),
    ),
    "environment.furniture.slashed_paintings": WorldPropProfile(
        name="Slashed paintings", description="Slashed and discarded paintings on the floor.",
        destroyed_name="Shredded canvas", destroyed_description="Scraps of canvas; passable.",
        footprint_offsets=((0, 0),), material=Material.FABRIC, hit_points=3,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.cresset": WorldPropProfile(
        name="Iron cresset", description="An empty wrought-iron holder for a torch.",
        destroyed_name="Bent cresset", destroyed_description="Bent iron against the wall.",
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=10,
        blocks_movement=False, occupies_bands=False,
    ),
    "environment.furniture.continual_light_rod": WorldPropProfile(
        name="Continual-light rod", description="A torch-sized metal rod set in the wall, shining with a heatless flame.",
        destroyed_name="Bent wall rod", destroyed_description="A bent, dark rod against the wall.",
        footprint_offsets=((0, 0),), material=Material.METAL, hit_points=5,
        blocks_movement=False, occupies_bands=False, continual_flame=True,
    ),
    "environment.furniture.fireplace": WorldPropProfile(
        name="Fireplace", description="A masonry fireplace with a lintel and mantle.",
        destroyed_name="Collapsed fireplace", destroyed_description="Fallen masonry; difficult terrain.",
        footprint_offsets=((0, 0), (1, 0)), material=Material.STONE, hit_points=27,
        difficult_debris=True, vertical_extent_steps=2, visual_variants=("large", "huge", "ornate", "grand"),
        shoveable=False,
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
    creates = (AreaCondition,)

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
    if profile is None:
        return
    if profile.continual_flame and not any(
            isinstance(condition, ContinualFlameCondition) for condition in item.active_conditions.values()):
        flame = ContinualFlameCondition(source_entity_uuid=item.uuid, target_entity_uuid=item.uuid)
        lit = item.add_condition(flame, parent_event=parent_event)
        if lit is None or lit.canceled or not flame.applied:
            raise RuntimeError(f"{item.item_id} could not carry its authored Continual Flame")
    if not profile.difficult_debris or any(
            isinstance(condition, DestructionDebris) for condition in item.active_conditions.values()):
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


def _profile_tags(profile: WorldPropProfile) -> list[str]:
    return ["furniture", profile.material.value, *((SHOVEABLE_TAG,) if profile.shoveable else ())]


def _checked_variant(item_id: str, profile: WorldPropProfile,
                     variant: ItemVisualVariantParameters | None) -> ItemVisualVariantParameters:
    variant = variant or ItemVisualVariantParameters()
    if variant.visual_variant_id is not None and variant.visual_variant_id not in profile.visual_variants:
        raise ValueError(f"{item_id} has no visual variant {variant.visual_variant_id!r}")
    return variant


def build_searchable_prop(item_id: str, *, dc: int = 13,
                          skill: Literal["perception", "investigation"] = "perception",
                          source_entity_uuid: UUID | None = None,
                          variant: ItemVisualVariantParameters | None = None) -> StorageChest:
    """One profiled body (a desk, a false-backed wardrobe, loose boards) holding contents a Search frees.

    It keeps the prop's name, footprint, blocking, material and debris, plus a lid; the caller
    puts the contents in its inventory. Its art is the prop's.
    """
    profile = WORLD_PROP_PROFILES[item_id]
    variant = _checked_variant(item_id, profile, variant)
    placement = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=profile.occupies_bands,
        vertical_extent_steps=profile.vertical_extent_steps, footprint_offsets=profile.footprint_offsets)
    aftermath = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=False,
        vertical_extent_steps=1, footprint_offsets=profile.footprint_offsets)
    body = StorageChest(source_entity_uuid=source_entity_uuid or uuid4(), item_id=item_id,
        name=variant.display_name or profile.name, description=profile.description,
        visual_item_name=profile.name, visual_variant_id=variant.visual_variant_id,
        tags=[*_profile_tags(profile), "container"], is_targetable=True,
        blocks_movement=profile.blocks_movement, blocks_optics_field=profile.blocks_optics,
        blocks_propagation_field=profile.blocks_propagation,
        armor_class=(profile.armor_class if profile.armor_class is not None
                     else OBJECT_ARMOR_CLASS_BY_MATERIAL[profile.material]),
        world_placement_spec=placement, use_action_templates=[],
        destruction_profile=ItemDestructionProfile(name=profile.destroyed_name,
            description=profile.destroyed_description, placement_spec=aftermath))
    body.use_action_templates.append(LootAllAction(source_entity_uuid=body.uuid, source_item_uuid=body.uuid,
        template=True, semantic_key="action.environment.storage_chest.loot_all"))
    body.health = body.create_item_health(body.uuid, profile.hit_points)
    install_search_gate(body, dc=dc, skill=skill)
    settle_world_prop(body)
    return body


def build_world_prop(
    item_id: str, *, source_entity_uuid: UUID | None = None,
    hit_points: int | None = None, integrity: ItemIntegrity = ItemIntegrity.INTACT,
    defer_behaviors: bool = False, variant: ItemVisualVariantParameters | None = None,
) -> WorldItem:
    """Compose one selected physical profile, without placing or breaking it."""
    profile = WORLD_PROP_PROFILES[item_id]
    hp = profile.hit_points if hit_points is None else hit_points
    if hp < 1:
        raise ValueError("Furniture hit points must be positive")
    variant = _checked_variant(item_id, profile, variant)
    source = source_entity_uuid or uuid4()
    placement = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=profile.occupies_bands,
        vertical_extent_steps=profile.vertical_extent_steps, footprint_offsets=profile.footprint_offsets)
    aftermath = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=False,
        vertical_extent_steps=1, footprint_offsets=profile.footprint_offsets)
    item = WorldItem(
        source_entity_uuid=source, item_id=item_id, name=variant.display_name or profile.name,
        visual_item_name=profile.name, visual_variant_id=variant.visual_variant_id,
        description=profile.description, tags=_profile_tags(profile),
        is_pickable=False, is_targetable=True, blocks_movement=profile.blocks_movement,
        blocks_optics_field=profile.blocks_optics, blocks_propagation_field=profile.blocks_propagation,
        health=BaseItem.create_item_health(source, hp), integrity=integrity,
        armor_class=(profile.armor_class if profile.armor_class is not None
                     else OBJECT_ARMOR_CLASS_BY_MATERIAL[profile.material]),
        world_placement_spec=placement,
        destruction_profile=ItemDestructionProfile(
            name=profile.destroyed_name, description=profile.destroyed_description,
            placement_spec=aftermath,
        ),
    )
    if not defer_behaviors:
        settle_world_prop(item)
    return item
