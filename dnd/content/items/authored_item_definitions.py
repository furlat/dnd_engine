"""Cold renderer-independent definitions for directly authored items."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

from dnd.types.damage import DamageType
from dnd.types.equipment import ArmorType, BodyPart, WeaponProperty
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec


@dataclass(frozen=True, slots=True)
class AuthoredItemDefinition:
    """Static gameplay identity and descriptive facts for one item."""

    item_id: str
    name: str
    description: str
    tags: tuple[str, ...]
    stack_id: Optional[str] = None
    max_stack: int = 1

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id cannot be empty")
        if not self.name:
            raise ValueError("item name cannot be empty")
        if self.max_stack < 1:
            raise ValueError("max_stack must be positive")
        if self.max_stack > 1 and self.stack_id is None:
            raise ValueError("stackable items require a stack_id")


@dataclass(frozen=True, slots=True)
class WeaponDefinition(AuthoredItemDefinition):
    """Cold mechanical facts for one mundane weapon identity."""

    damage_die: int = 4
    damage_dice_count: int = 1
    damage_type: DamageType = DamageType.BLUDGEONING
    properties: tuple[WeaponProperty, ...] = ()
    range_kind: str = "reach"
    normal_range_feet: int = 5
    long_range_feet: Optional[int] = None
    attack_bonus: int = 0
    damage_bonus: int = 0
    attack_disadvantage: bool = False
    extra_damage_die: Optional[int] = None
    extra_damage_dice_count: int = 0
    extra_damage_type: Optional[DamageType] = None


@dataclass(frozen=True, slots=True)
class WearableDefinition(AuthoredItemDefinition):
    """Cold armor/apparel facts with no renderer asset vocabulary."""

    wearable_kind: str = "body_armor"
    armor_type: ArmorType = ArmorType.CLOTH
    body_part: BodyPart = BodyPart.BODY
    armor_class: int = 0
    maximum_dexterity_bonus: int = 10
    shield_armor_class_bonus: int = 0
    strength_requirement: Optional[int] = None
    stealth_disadvantage: bool = False


@dataclass(frozen=True, slots=True)
class StaticBlockerDefinition(AuthoredItemDefinition):
    """Cold mechanical facts for one behavior-free world blocker."""

    hit_points: int = 1
    map_character: str = "?"
    blocks_movement: bool = False
    blocks_optics: bool = False
    blocks_propagation: bool = False
    placement_spec: WorldPlacementSpec = field(kw_only=True)

    def __post_init__(self) -> None:
        AuthoredItemDefinition.__post_init__(self)
        if self.hit_points < 1:
            raise ValueError("static blocker hit_points must be positive")
        if len(self.map_character) != 1:
            raise ValueError("static blocker map_character must be one character")
        if not isinstance(self.placement_spec, WorldPlacementSpec):
            raise ValueError(
                "static blocker placement must be a WorldPlacementSpec",
            )
        if self.placement_spec.kind is not WorldPlacementKind.CENTER:
            raise ValueError("static blocker placement must be CENTER")


_ACOLYTE_GEAR = (
    AuthoredItemDefinition(
        item_id="gear.holy_symbol",
        name="Holy Symbol",
        description="A devotional symbol used by an acolyte.",
        tags=("acolyte", "holy_symbol", "religious"),
    ),
    AuthoredItemDefinition(
        item_id="gear.prayer_book",
        name="Prayer Book",
        description="A book of prayers and devotional rites.",
        tags=("acolyte", "book", "religious"),
    ),
    AuthoredItemDefinition(
        item_id="gear.incense",
        name="Incense",
        description="A stick of incense used in religious observance.",
        tags=("acolyte", "incense", "religious"),
        stack_id="srd_5_1.gear.incense",
        max_stack=20,
    ),
    AuthoredItemDefinition(
        item_id="gear.vestments",
        name="Vestments",
        description="Religious ceremonial clothing carried by an acolyte.",
        tags=("acolyte", "clothes", "religious", "vestments"),
    ),
    AuthoredItemDefinition(
        item_id="gear.common_clothes",
        name="Common Clothes",
        description="An ordinary set of common clothing.",
        tags=("acolyte", "clothes", "common"),
    ),
)

ACOLYTE_GEAR_DEFINITIONS: Mapping[str, AuthoredItemDefinition] = MappingProxyType({
    definition.item_id: definition
    for definition in _ACOLYTE_GEAR
})


_STATIC_BLOCKERS = (
    StaticBlockerDefinition(
        "environment.blocker.crate",
        "Crate",
        "A destructible crate.",
        ("breakable", "crate", "environment"),
        hit_points=20,
        map_character="C",
        placement_spec=WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            vertical_extent_steps=1,
        ),
    ),
    StaticBlockerDefinition(
        "environment.blocker.boulder",
        "Boulder",
        "A durable boulder that blocks movement.",
        ("blocker", "boulder", "environment"),
        hit_points=30,
        map_character="B",
        blocks_movement=True,
        blocks_propagation=True,
        placement_spec=WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=True,
            vertical_extent_steps=1,
        ),
    ),
    StaticBlockerDefinition(
        "environment.blocker.barricade",
        "Barricade",
        "A destructible barricade that blocks movement and sight.",
        ("barricade", "blocker", "breakable", "environment"),
        hit_points=20,
        map_character="X",
        blocks_movement=True,
        blocks_optics=True,
        blocks_propagation=True,
        placement_spec=WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=True,
            vertical_extent_steps=1,
        ),
    ),
)

STATIC_BLOCKER_DEFINITIONS: Mapping[
    str,
    StaticBlockerDefinition,
] = MappingProxyType({
    definition.item_id: definition
    for definition in _STATIC_BLOCKERS
})


_AUTHORED_WEAPONS = (
    WeaponDefinition(
        "weapon.club", "Club", "A simple wooden club.",
        ("melee", "simple", "weapon"), damage_die=4,
        properties=(WeaponProperty.LIGHT,),
    ),
    WeaponDefinition(
        "weapon.spear", "Spear",
        "A versatile spear suitable for thrusting or throwing.",
        ("melee", "simple", "thrown", "weapon"), damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.SIMPLE,
            WeaponProperty.THROWN,
            WeaponProperty.VERSATILE,
        ),
    ),
    WeaponDefinition(
        "weapon.mace", "Mace", "A heavy-headed simple melee weapon.",
        ("melee", "simple", "weapon"), damage_die=6,
        properties=(WeaponProperty.SIMPLE,),
    ),
    WeaponDefinition(
        "weapon.dagger", "Dagger", "A simple blade for quick strikes.",
        ("melee", "simple", "weapon"), damage_die=4,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.THROWN,
        ),
    ),
    WeaponDefinition(
        "weapon.handaxe", "Handaxe", "A small axe that can be thrown.",
        ("melee", "simple", "weapon"), damage_die=6,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.LIGHT, WeaponProperty.THROWN),
    ),
    WeaponDefinition(
        "weapon.javelin", "Javelin", "A light spear designed for throwing.",
        ("melee", "simple", "weapon"), damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.THROWN,),
    ),
    WeaponDefinition(
        "weapon.light_hammer", "Light Hammer",
        "A compact hammer balanced for melee or throwing.",
        ("light", "melee", "simple", "thrown", "weapon"),
        damage_die=4,
        properties=(WeaponProperty.LIGHT, WeaponProperty.THROWN),
    ),
    WeaponDefinition(
        "weapon.quarterstaff", "Quarterstaff", "A wooden staff used as a weapon.",
        ("melee", "simple", "weapon"), damage_die=6,
        properties=(WeaponProperty.VERSATILE,),
    ),
    WeaponDefinition(
        "weapon.sickle", "Sickle", "A light, curved harvesting blade.",
        ("light", "melee", "simple", "weapon"), damage_die=4,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.LIGHT,),
    ),
    WeaponDefinition(
        "weapon.dart", "Dart", "A balanced throwing dart.",
        ("finesse", "ranged", "simple", "thrown", "weapon"),
        damage_die=4,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.RANGED,
            WeaponProperty.THROWN,
        ),
        range_kind="range", normal_range_feet=20, long_range_feet=60,
    ),
    WeaponDefinition(
        "weapon.sling", "Sling",
        "A simple leather sling for hurling stones or bullets.",
        ("ranged", "simple", "weapon"), damage_die=4,
        properties=(WeaponProperty.RANGED,),
        range_kind="range", normal_range_feet=30, long_range_feet=120,
    ),
    WeaponDefinition(
        "weapon.battleaxe", "Battleaxe",
        "A large axe suitable for battle.",
        ("martial", "melee", "weapon"), damage_die=8,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
    ),
    WeaponDefinition(
        "weapon.greataxe", "Greataxe",
        "A massive two-handed axe favored by barbarians.",
        ("heavy", "martial", "melee", "weapon"), damage_die=12,
        damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
    ),
    WeaponDefinition(
        "weapon.greatsword", "Greatsword", "A massive two-handed sword.",
        ("heavy", "martial", "melee", "weapon"), damage_die=6,
        damage_dice_count=2, damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
    ),
    WeaponDefinition(
        "weapon.double_bladed_sword",
        "Double-Bladed Sword",
        "An exotic two-handed sword with a blade at each end of its grip.",
        ("custom", "martial", "melee", "two_handed", "weapon"),
        damage_die=4,
        damage_dice_count=2,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL),
    ),
    WeaponDefinition(
        "weapon.longsword", "Longsword", "A versatile one-handed sword.",
        ("martial", "melee", "weapon"), damage_die=8,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
    ),
    WeaponDefinition(
        "weapon.morningstar", "Morningstar",
        "A spiked metal head mounted on a sturdy haft.",
        ("martial", "melee", "weapon"), damage_die=8,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.MARTIAL,),
    ),
    WeaponDefinition(
        "weapon.rapier", "Rapier", "A slender thrusting sword.",
        ("finesse", "martial", "melee", "weapon"), damage_die=8,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.FINESSE, WeaponProperty.MARTIAL),
    ),
    WeaponDefinition(
        "weapon.longbow", "Longbow", "A tall bow capable of long-range shots.",
        ("heavy", "martial", "ranged", "weapon"), damage_die=8,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
        ),
        range_kind="range",
        normal_range_feet=150,
        long_range_feet=600,
    ),
    WeaponDefinition(
        "weapon.shortsword", "Shortsword",
        "A short blade suitable for quick strikes.",
        ("light", "martial", "melee", "weapon"), damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
    ),
    WeaponDefinition(
        "weapon.scimitar", "Scimitar",
        "A light curved sword made for quick slashing attacks.",
        ("finesse", "light", "martial", "melee", "weapon"),
        damage_die=6,
        damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
    ),
    WeaponDefinition(
        "weapon.trident", "Trident", "A three-pronged martial spear.",
        ("martial", "melee", "thrown", "weapon"), damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.THROWN,
            WeaponProperty.VERSATILE,
            WeaponProperty.MARTIAL,
        ),
    ),
    WeaponDefinition(
        "weapon.warhammer", "Warhammer",
        "A heavy hammer designed for combat.",
        ("martial", "melee", "weapon"), damage_die=8,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
    ),
    WeaponDefinition(
        "weapon.shortbow", "Shortbow",
        "A compact bow effective at short and medium range.",
        ("ranged", "simple", "two_handed", "weapon"),
        damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
        ),
        range_kind="range",
        normal_range_feet=80,
        long_range_feet=320,
    ),
    WeaponDefinition(
        "weapon.light_crossbow", "Light Crossbow",
        "A two-handed crossbow effective at long range.",
        ("ranged", "simple", "two_handed", "weapon"),
        damage_die=8,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.RANGED,
            WeaponProperty.SIMPLE,
            WeaponProperty.TWO_HANDED,
        ),
        range_kind="range",
        normal_range_feet=80,
        long_range_feet=320,
    ),
    WeaponDefinition(
        "weapon.heavy_crossbow", "Heavy Crossbow",
        "A powerful martial crossbow built for long-range attacks.",
        ("heavy", "martial", "ranged", "two_handed", "weapon"),
        damage_die=10,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
        ),
        range_kind="range",
        normal_range_feet=100,
        long_range_feet=400,
    ),
    WeaponDefinition(
        "weapon.arcane_staff", "Arcane Staff",
        "A staff crackling with arcane energy that improves spell attacks while equipped.",
        ("arcane", "melee", "staff", "weapon"),
        damage_die=6,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.VERSATILE,),
    ),
    WeaponDefinition(
        "weapon.circus.rusty_dagger", "Rusty Dagger",
        "A poorly maintained dagger whose rusty blade makes accurate strikes difficult.",
        ("circus", "dagger", "melee", "weapon"),
        damage_die=4,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.THROWN,
        ),
        attack_disadvantage=True,
    ),
    WeaponDefinition(
        "weapon.circus.flaming_scimitar", "Flaming Scimitar",
        "An elegant curved blade whose magical flames intensify during acrobatic maneuvers.",
        ("circus", "fire", "melee", "scimitar", "weapon"),
        damage_die=6,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.FINESSE, WeaponProperty.LIGHT),
        extra_damage_die=6,
        extra_damage_dice_count=1,
        extra_damage_type=DamageType.FIRE,
    ),
    WeaponDefinition(
        "weapon.circus.longsword_plus_one", "Longsword +1",
        "A magical longsword granting +1 to attack and damage rolls.",
        ("circus", "magic", "melee", "weapon"),
        damage_die=8,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.VERSATILE,),
        attack_bonus=1,
        damage_bonus=1,
    ),
    WeaponDefinition(
        "weapon.circus.soul_draining_morningstar", "Soul-Draining Morningstar",
        "A wicked morningstar carrying an additional pulse of necrotic damage.",
        ("circus", "melee", "necrotic", "weapon"),
        damage_die=8,
        damage_type=DamageType.PIERCING,
        extra_damage_die=4,
        extra_damage_dice_count=1,
        extra_damage_type=DamageType.NECROTIC,
    ),
    WeaponDefinition(
        "weapon.creature.kobold_sling", "Sling",
        "A sling used by an SRD kobold.",
        ("creature_possession", "ranged", "srd", "weapon"),
        damage_die=4,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.RANGED,),
        range_kind="range",
        normal_range_feet=30,
        long_range_feet=120,
    ),
    WeaponDefinition(
        "weapon.creature.spy_hand_crossbow", "Hand Crossbow",
        "A compact crossbow carried by an SRD spy.",
        ("creature_possession", "ranged", "srd", "weapon"),
        damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED,),
        range_kind="range",
        normal_range_feet=30,
        long_range_feet=120,
    ),
    WeaponDefinition(
        "weapon.creature.bandit_captain_thrown_dagger", "Thrown Dagger",
        "A dagger profile used at range by an SRD bandit captain.",
        ("creature_possession", "ranged", "srd", "weapon"),
        damage_die=4,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED,),
        range_kind="range",
        normal_range_feet=20,
        long_range_feet=60,
    ),
    WeaponDefinition(
        "weapon.creature.thrown_javelin", "Thrown Javelin",
        "A javelin profile used at range by an SRD creature.",
        ("creature_possession", "ranged", "srd", "weapon"),
        damage_die=6,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED,),
        range_kind="range",
        normal_range_feet=30,
        long_range_feet=120,
    ),
    WeaponDefinition(
        "weapon.creature.bugbear_morningstar", "Morningstar",
        "The piercing morningstar profile of an SRD bugbear.",
        ("creature_possession", "melee", "srd", "weapon"),
        damage_die=8,
        damage_type=DamageType.PIERCING,
    ),
    WeaponDefinition(
        "weapon.creature.ogre_greatclub", "Greatclub",
        "The massive greatclub profile of an SRD ogre.",
        ("creature_possession", "melee", "srd", "weapon"),
        damage_die=8,
        damage_dice_count=2,
    ),
    WeaponDefinition(
        "weapon.creature.ogre_thrown_javelin", "Thrown Javelin",
        "The oversized ranged javelin profile of an SRD ogre.",
        ("creature_possession", "ranged", "srd", "weapon"),
        damage_die=6,
        damage_dice_count=2,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED,),
        range_kind="range",
        normal_range_feet=30,
        long_range_feet=120,
    ),
    WeaponDefinition(
        "weapon.creature.wolf_bite", "Bite",
        "The intrinsic bite of an SRD wolf.",
        ("creature_possession", "intrinsic", "natural", "srd", "weapon"),
        damage_die=4,
        damage_dice_count=2,
        damage_type=DamageType.PIERCING,
    ),
    WeaponDefinition(
        "weapon.creature.dire_wolf_bite", "Bite",
        "The intrinsic bite of an SRD dire wolf.",
        ("creature_possession", "intrinsic", "natural", "srd", "weapon"),
        damage_die=6,
        damage_dice_count=2,
        damage_type=DamageType.PIERCING,
    ),
    WeaponDefinition(
        "weapon.creature.zombie_slam", "Slam",
        "The intrinsic slam of an SRD zombie.",
        ("creature_possession", "intrinsic", "natural", "srd", "weapon"),
        damage_die=6,
    ),
    WeaponDefinition(
        "weapon.creature.ogre_zombie_morningstar", "Morningstar",
        "The oversized morningstar profile of an SRD ogre zombie.",
        ("creature_possession", "melee", "srd", "weapon"),
        damage_die=8,
        damage_dice_count=2,
    ),
    WeaponDefinition(
        "weapon.creature.ghoul_claws", "Claws",
        "The intrinsic claws of an SRD ghoul.",
        ("creature_possession", "intrinsic", "natural", "srd", "weapon"),
        damage_die=4,
        damage_dice_count=2,
        damage_type=DamageType.SLASHING,
    ),
    WeaponDefinition(
        "weapon.creature.ghoul_bite", "Bite",
        "The intrinsic bite of an SRD ghoul.",
        ("creature_possession", "intrinsic", "natural", "srd", "weapon"),
        damage_die=6,
        damage_dice_count=2,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.LIGHT,),
    ),
)

AUTHORED_WEAPON_DEFINITIONS: Mapping[str, WeaponDefinition] = MappingProxyType({
    definition.item_id: definition
    for definition in _AUTHORED_WEAPONS
})


_AUTHORED_WEARABLES = (
    WearableDefinition(
        "armor.padded", "Padded Armor",
        "Quilted layers of cloth and batting.",
        ("armor", "light"), armor_type=ArmorType.LIGHT,
        armor_class=11, stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.scale_mail", "Scale Mail",
        "Overlapping metal scales sewn to a leather coat.",
        ("armor", "medium"), armor_type=ArmorType.MEDIUM,
        armor_class=14, maximum_dexterity_bonus=2,
        stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.breastplate", "Breastplate",
        "A fitted metal chest piece with leather straps.",
        ("armor", "medium"), armor_type=ArmorType.MEDIUM,
        armor_class=14, maximum_dexterity_bonus=2,
    ),
    WearableDefinition(
        "armor.half_plate", "Half Plate",
        "Shaped metal plates covering most of the body.",
        ("armor", "medium"), armor_type=ArmorType.MEDIUM,
        armor_class=15, maximum_dexterity_bonus=2,
        stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.ring_mail", "Ring Mail",
        "Leather armor with heavy rings sewn into it.",
        ("armor", "heavy"), armor_type=ArmorType.HEAVY,
        armor_class=14, maximum_dexterity_bonus=0,
        stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.cloth", "Cloth Armor",
        "Simple clothing that provides no protection.",
        ("apparel", "armor", "cloth"), armor_class=10,
    ),
    WearableDefinition(
        "shield.wooden", "Wooden Shield", "A crude wooden shield.",
        ("armor", "shield", "wood"), wearable_kind="shield",
        body_part=BodyPart.HANDS, shield_armor_class_bonus=2,
    ),
    WearableDefinition(
        "apparel.fine_clothes", "Fine Clothes",
        "Tailored clothes made from quality cloth.",
        ("apparel", "body", "cloth"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.cloth_hood", "Cloth Hood", "A simple cloth hood.",
        ("apparel", "cloth", "headgear"), wearable_kind="helmet",
        body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.leather_hood", "Leather Hood",
        "A fitted hood made from supple leather.",
        ("apparel", "headgear", "leather"), wearable_kind="helmet",
        armor_type=ArmorType.LIGHT, body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.chain_coif", "Chain Coif",
        "A fitted coif of interlocking metal rings.",
        ("apparel", "headgear", "metal"), wearable_kind="helmet",
        armor_type=ArmorType.HEAVY, body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.horned_helmet", "Horned Helmet",
        "A metal war helmet crowned by prominent horns.",
        ("apparel", "headgear", "metal"), wearable_kind="helmet",
        armor_type=ArmorType.HEAVY, body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.great_helm", "Great Helm",
        "A heavy enclosed helmet that covers the face.",
        ("apparel", "headgear", "metal"), wearable_kind="helmet",
        armor_type=ArmorType.HEAVY, body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.monster_helm", "Monster Helm",
        "A fantastical headpiece shaped like a monstrous visage.",
        ("apparel", "headgear", "monster"), wearable_kind="helmet",
        body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.bracers", "Bracers",
        "Protective forearm guards that leave the hands exposed.",
        ("apparel", "hands", "leather"), wearable_kind="gauntlets",
        armor_type=ArmorType.LIGHT, body_part=BodyPart.HANDS,
    ),
    WearableDefinition(
        "apparel.leather_gloves", "Leather Gloves",
        "Close-fitting gloves made from leather.",
        ("apparel", "hands", "leather"), wearable_kind="gauntlets",
        armor_type=ArmorType.LIGHT, body_part=BodyPart.HANDS,
    ),
    WearableDefinition(
        "apparel.gauntlets", "Gauntlets",
        "Articulated plate protection for the hands.",
        ("apparel", "hands", "metal"), wearable_kind="gauntlets",
        armor_type=ArmorType.HEAVY, body_part=BodyPart.HANDS,
    ),
    WearableDefinition(
        "apparel.monster_hands", "Monster Hands",
        "Fantastical gloves shaped like monstrous appendages.",
        ("apparel", "hands", "monster"), wearable_kind="gauntlets",
        body_part=BodyPart.HANDS,
    ),
    WearableDefinition(
        "apparel.common_clothes", "Common Clothes",
        "Simple everyday clothing suited to work and village life.",
        ("apparel", "body", "clothes"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.travelers_clothes", "Traveler's Clothes",
        "Hard-wearing clothes cut for travel and outdoor work.",
        ("apparel", "body", "clothes"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.costume", "Costume",
        "Distinctive garb made for performance, ceremony, or the arena.",
        ("apparel", "body", "costume"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes", "Robes",
        "Cloth robes suitable for an arcane caster.",
        ("apparel", "body", "robes"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.sandals", "Sandals",
        "Simple open footwear suited to warm climates and humble dress.",
        ("apparel", "footwear"), wearable_kind="boots",
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.leather_shoes", "Leather Shoes",
        "Plain leather shoes for daily wear.",
        ("apparel", "footwear", "leather"), wearable_kind="boots",
        armor_type=ArmorType.LIGHT, body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.iron_helmet", "Iron Helmet", "A sturdy metal helmet.",
        ("apparel", "headgear", "metal"), wearable_kind="helmet",
        armor_type=ArmorType.HEAVY, body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.wizard_hat", "Wizard's Hat",
        "A pointy cloth hat favored by arcane casters.",
        ("apparel", "cloth", "headgear"), wearable_kind="helmet",
        body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "armor.chain_shirt", "Chain Shirt",
        "A shirt of interlocking metal rings worn beneath clothing.",
        ("armor", "medium"), armor_type=ArmorType.MEDIUM,
        armor_class=13, maximum_dexterity_bonus=2,
    ),
    WearableDefinition(
        "armor.hide", "Hide Armor",
        "Crude medium armor made from thick hides and furs.",
        ("armor", "medium"), armor_type=ArmorType.MEDIUM,
        armor_class=12, maximum_dexterity_bonus=2,
    ),
    WearableDefinition(
        "armor.plate", "Plate Armor",
        "Interlocking shaped metal plates covering the entire body.",
        ("armor", "heavy"), armor_type=ArmorType.HEAVY,
        armor_class=18, maximum_dexterity_bonus=0,
        strength_requirement=15, stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.splint", "Splint Armor",
        "Narrow metal strips riveted to a backing of leather and cloth.",
        ("armor", "heavy"), armor_type=ArmorType.HEAVY,
        armor_class=17, maximum_dexterity_bonus=0,
        strength_requirement=15, stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.chain_mail", "Chain Mail",
        "Interlocking metal rings over quilted fabric.",
        ("armor", "heavy"), armor_type=ArmorType.HEAVY,
        armor_class=16, maximum_dexterity_bonus=0,
        strength_requirement=13, stealth_disadvantage=True,
    ),
    WearableDefinition(
        "armor.leather", "Leather Armor",
        "Basic leather armor providing light protection.",
        ("armor", "light"), armor_type=ArmorType.LIGHT,
        armor_class=11,
    ),
    WearableDefinition(
        "armor.studded_leather", "Studded Leather",
        "Tough leather reinforced with close-set rivets.",
        ("armor", "light"), armor_type=ArmorType.LIGHT,
        armor_class=12,
    ),
    WearableDefinition(
        "shield.shield", "Shield", "A wooden or metal shield.",
        ("armor", "shield"), wearable_kind="shield",
        body_part=BodyPart.HANDS, shield_armor_class_bonus=2,
    ),
    WearableDefinition(
        "apparel.leather_boots", "Leather Boots",
        "Sturdy leather adventuring boots.",
        ("apparel", "footwear", "leather"), wearable_kind="boots",
        armor_type=ArmorType.LIGHT, body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.leather_boots.brown", "Brown Leather Boots",
        "Sturdy brown leather adventuring boots.",
        ("apparel", "footwear", "leather", "palette.brown"),
        wearable_kind="boots", armor_type=ArmorType.LIGHT,
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.leather_shoes.brown", "Brown Leather Shoes",
        "Low brown leather shoes suited to ordinary work clothing.",
        ("apparel", "footwear", "leather", "palette.brown"),
        wearable_kind="boots", armor_type=ArmorType.LIGHT,
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.armored_boots", "Armored Boots",
        "Metal-reinforced boots worn with heavy armor.",
        ("apparel", "armor", "footwear", "metal"),
        wearable_kind="boots", armor_type=ArmorType.HEAVY,
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.cloth_shoes", "Cloth Shoes", "Soft cloth shoes.",
        ("apparel", "footwear", "cloth"), wearable_kind="boots",
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.cloth_shoes.red", "Red Cloth Shoes", "Soft red cloth shoes.",
        ("apparel", "footwear", "cloth", "palette.red"),
        wearable_kind="boots", body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.cloth_shoes.blue", "Blue Cloth Shoes", "Soft blue cloth shoes.",
        ("apparel", "footwear", "cloth", "palette.blue"),
        wearable_kind="boots", body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.iron_helmet.steel", "Steel Helmet", "A sturdy steel helmet.",
        ("apparel", "headgear", "metal", "palette.steel"),
        wearable_kind="helmet", armor_type=ArmorType.HEAVY,
        body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.wizard_hat.red", "Red Wizard's Hat",
        "A red pointy cloth hat favored by arcane casters.",
        ("apparel", "headgear", "cloth", "palette.red"),
        wearable_kind="helmet", body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.costume.pit_fighter_wrap", "Pit Fighter Wrap",
        "Distinctive arena garb made for a pit fighter.",
        ("apparel", "body", "costume", "pit_fighter"),
    ),
    WearableDefinition(
        "apparel.robes.red_mage", "Red Mage Robes",
        "Red cloth robes suitable for an arcane caster.",
        ("apparel", "body", "robes", "palette.red"),
        armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes.wizard", "Wizard Robes",
        "Cloth robes suitable for an arcane caster.",
        ("apparel", "body", "robes"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes.acolyte_vestments", "Acolyte Vestments",
        "Simple ceremonial robes worn by a junior religious attendant.",
        ("apparel", "body", "robes", "role.divine"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.common_clothes.farmhand_tunic", "Farmhand Tunic",
        "Plain work clothing suited to a farmhand or common laborer.",
        ("apparel", "body", "clothes", "role.commoner"),
    ),
    WearableDefinition(
        "apparel.common_clothes.peasant_rags", "Peasant Rags",
        "Rough patched clothing assembled from simple cloth.",
        ("apparel", "body", "clothes", "worn"),
    ),
    WearableDefinition(
        "apparel.travelers_clothes.thief_garb", "Thief Garb",
        "Dark close-fitting travel clothes suited to covert movement.",
        ("apparel", "body", "clothes", "palette.dark", "role.thief"),
    ),
    WearableDefinition(
        "apparel.robes.hedge_wizard", "Hedge-Wizard Robes",
        "Practical robes worn by a self-taught arcane caster.",
        ("apparel", "body", "robes", "role.arcane"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes.dark_cultist", "Dark Cultist Robes",
        "Dark ceremonial robes associated with forbidden rites.",
        ("apparel", "body", "robes", "palette.dark", "role.occult"),
        armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes.priest_vestments", "Priest Vestments",
        "Ceremonial vestments worn by an ordained priest.",
        ("apparel", "body", "robes", "role.divine"), armor_class=10,
    ),
    WearableDefinition(
        "apparel.robes.necromancer", "Necromancer Robes",
        "Funereal robes marked by necromantic study.",
        ("apparel", "body", "robes", "palette.dark", "role.necromancy"),
        armor_class=10,
    ),
    WearableDefinition(
        "apparel.cloth_shoes.dark", "Dark Cloth Shoes",
        "Soft dark cloth shoes.",
        ("apparel", "footwear", "cloth", "palette.dark"),
        wearable_kind="boots", body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.sandals.rope", "Rope Sandals",
        "Simple sandals bound with rope.",
        ("apparel", "footwear", "rope"),
        wearable_kind="boots", body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "apparel.spellblade_crown", "Spellblade Crown",
        "An arcane crown granting +3 Charisma while equipped.",
        ("apparel", "headgear", "arcane", "crown"),
        wearable_kind="spellblade_crown", body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "armor.armor_scraps", "Armor Scraps",
        "Rusted pieces of armor barely held together on bone.",
        ("armor", "bestiary", "creature_possession", "light"),
        armor_type=ArmorType.LIGHT,
        armor_class=13,
        maximum_dexterity_bonus=0,
    ),
    WearableDefinition(
        "apparel.crown", "Crown",
        "A simple metal crown worn as a sign of rank or occult authority.",
        ("apparel", "crown", "headgear", "metal"),
        wearable_kind="helmet",
        body_part=BodyPart.HEAD,
    ),
    WearableDefinition(
        "apparel.leather_boots.dark", "Dark Leather Boots",
        "Sturdy dark leather boots suited to quiet movement.",
        ("apparel", "footwear", "leather", "palette.dark"),
        wearable_kind="boots",
        armor_type=ArmorType.LIGHT,
        body_part=BodyPart.FEET,
    ),
    WearableDefinition(
        "armor.circus.performer_leather", "Performer's Leather Armor",
        "Flexible leather armor decorated for an acrobatic circus performer.",
        ("armor", "circus", "light", "performer"),
        armor_type=ArmorType.LIGHT,
        armor_class=11,
        maximum_dexterity_bonus=5,
    ),
    WearableDefinition(
        "armor.creature.wolf_natural", "Natural Armor",
        "The wolf's intrinsic hide provides fixed Armor Class 13.",
        ("armor", "creature_possession", "intrinsic", "natural", "srd"),
        armor_type=ArmorType.LIGHT,
        armor_class=13,
        maximum_dexterity_bonus=0,
    ),
    WearableDefinition(
        "armor.creature.dire_wolf_natural", "Natural Armor",
        "The dire wolf's intrinsic hide provides fixed Armor Class 14.",
        ("armor", "creature_possession", "intrinsic", "natural", "srd"),
        armor_type=ArmorType.LIGHT,
        armor_class=14,
        maximum_dexterity_bonus=0,
    ),
)

AUTHORED_WEARABLE_DEFINITIONS: Mapping[str, WearableDefinition] = MappingProxyType({
    definition.item_id: definition
    for definition in _AUTHORED_WEARABLES
})


__all__ = [
    "ACOLYTE_GEAR_DEFINITIONS",
    "AUTHORED_WEAPON_DEFINITIONS",
    "AUTHORED_WEARABLE_DEFINITIONS",
    "STATIC_BLOCKER_DEFINITIONS",
    "AuthoredItemDefinition",
    "StaticBlockerDefinition",
    "WeaponDefinition",
    "WearableDefinition",
]
