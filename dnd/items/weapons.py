"""Weapon factories and hook-bearing weapon test fixtures."""

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.blocks.equipment import Weapon, Range
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    get_content_declaration,
)
from dnd.core.equipment_types import EquipmentSlot, WeaponProperty
from dnd.core.events import (
    RangeType, Event, EventType, EventPhase, EventHandler, Trigger,
    Damage, DamageRollResultEvent,
)
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.items.authored_presentations import (
    authored_item_factory as item_factory,
)
from dnd.items.visual_variants import ItemVisualVariantParameters


class ClubParameters(ItemVisualVariantParameters):
    """Optional authored presentation variant over canonical Club mechanics."""


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="weapon.club",
    version=1,
    parameters=ClubParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Club",
        description="A simple wooden club.",
        tags=("melee", "simple", "srd", "weapon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="weapon.club",
            visual_variant_key="club",
            ui_group="weapons.simple_melee",
        ),
        ordering=ContentOrdering(
            sort_group="weapons.simple_melee",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), pp. 65-66, Weapons table: Club"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Playable mechanics; cost and weight parity remain source-ledger work.",
    ),
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
)
def _build_club(
    context: object,
    parameters: ClubParameters,
) -> Weapon:
    """Construct the one canonical SRD Club definition.

    Args:
        context: Typed runtime owner and exact requested content reference.
        parameters: Empty typed Club parameter contract.

    Returns:
        Simple melee weapon dealing 1d4 bludgeoning damage with Light.
    """
    item_context = ItemBuildContext.model_validate(context)
    return Weapon(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name=parameters.display_name or "Club",
        visual_item_name=(
            "Club" if parameters.visual_variant_id is not None else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description="A simple wooden club.",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


CLUB_DECLARATION = get_content_declaration(_build_club)
CLUB_REF = CLUB_DECLARATION.ref
CLUB_RECIPE = ContentRecipe.create(ref=CLUB_REF, parameters={})


class StandardWeaponParameters(ItemVisualVariantParameters):
    """Optional authored presentation variant over one SRD weapon's mechanics."""


class _StandardWeaponSpec(BaseModel):
    """Cold authored facts used by the canonical mundane weapon factories."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_id: str
    display_name: str
    description: str
    group: str
    order: int
    damage_dice: Literal[4, 6, 8, 10, 12, 20]
    dice_numbers: int
    damage_type: DamageType
    properties: tuple[WeaponProperty, ...]
    range_type: RangeType
    normal_range: int
    long_range: int | None = None
    source_table_name: str | None = None


_POSSESSION_ITEM_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.POSSESSION,
)


def _build_standard_weapon(
    context: object,
    spec: _StandardWeaponSpec,
    parameters: StandardWeaponParameters,
) -> Weapon:
    item_context = ItemBuildContext.model_validate(context)
    return Weapon(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name=parameters.display_name or spec.display_name,
        visual_item_name=(
            spec.display_name
            if parameters.visual_variant_id is not None
            else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description=spec.description,
        damage_dice=spec.damage_dice,
        dice_numbers=spec.dice_numbers,
        damage_type=spec.damage_type,
        properties=list(spec.properties),
        range=Range(
            type=spec.range_type,
            normal=spec.normal_range,
            long=spec.long_range,
        ),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
    )


def _declare_standard_weapon(
    spec: _StandardWeaponSpec,
):
    descriptor = ContentDescriptorSpec(
        display_name=spec.display_name,
        description=spec.description,
        tags=tuple((*spec.group.split("_"), "srd", "weapon")),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=f"weapon.{spec.content_id}",
            visual_variant_key=spec.content_id,
            ui_group=f"weapons.{spec.group}",
        ),
        ordering=ContentOrdering(
            sort_group=f"weapons.{spec.group}",
            sort_order=spec.order,
        ),
    )
    provenance = ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), pp. 65-66, Weapons table: "
            f"{spec.source_table_name or spec.display_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Playable mechanics; cost and weight parity remain source-ledger work.",
    )

    def factory(
        context: object,
        parameters: StandardWeaponParameters,
    ) -> Weapon:
        return _build_standard_weapon(context, spec, parameters)

    factory.__name__ = f"_build_{spec.content_id}"
    factory.__qualname__ = factory.__name__
    return item_factory(
        pack_id="content.srd_5_1_cc",
        content_id=f"weapon.{spec.content_id}",
        version=1,
        parameters=StandardWeaponParameters,
        descriptor=descriptor,
        provenance=provenance,
        item_definition=_POSSESSION_ITEM_DEFINITION,
    )(factory)


_build_dagger = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="dagger",
        display_name="Dagger",
        description="A simple blade for quick strikes.",
        group="simple_melee",
        order=20,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.THROWN,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_handaxe = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="handaxe",
        display_name="Handaxe",
        description="A small axe that can be thrown.",
        group="simple_melee",
        order=30,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.LIGHT, WeaponProperty.THROWN),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_javelin = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="javelin",
        display_name="Javelin",
        description="A light spear designed for throwing.",
        group="simple_melee",
        order=40,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.THROWN,),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_light_hammer = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="light_hammer",
        display_name="Light Hammer",
        description="A compact hammer balanced for melee or throwing.",
        group="simple_melee",
        order=45,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.LIGHT, WeaponProperty.THROWN),
        range_type=RangeType.REACH,
        normal_range=5,
        source_table_name="Hammer, light",
    )
)
_build_mace = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="mace",
        display_name="Mace",
        description="A heavy headed club.",
        group="simple_melee",
        order=50,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=(),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_quarterstaff = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="quarterstaff",
        display_name="Quarterstaff",
        description="A wooden staff used as a weapon.",
        group="simple_melee",
        order=60,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.VERSATILE,),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_sickle = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="sickle",
        display_name="Sickle",
        description="A light, curved harvesting blade.",
        group="simple_melee",
        order=65,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.LIGHT,),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_spear = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="spear",
        display_name="Spear",
        description="A pole weapon with a pointed tip.",
        group="simple_melee",
        order=70,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.THROWN, WeaponProperty.VERSATILE),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_dart = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="dart",
        display_name="Dart",
        description="A balanced throwing dart.",
        group="simple_ranged",
        order=5,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.RANGED,
            WeaponProperty.THROWN,
        ),
        range_type=RangeType.RANGE,
        normal_range=20,
        long_range=60,
    )
)
_build_light_crossbow = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="light_crossbow",
        display_name="Light Crossbow",
        description="A mechanical bow that fires bolts.",
        group="simple_ranged",
        order=10,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED, WeaponProperty.TWO_HANDED),
        range_type=RangeType.RANGE,
        normal_range=80,
        long_range=320,
        source_table_name="Crossbow, light",
    )
)
_build_shortbow = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="shortbow",
        display_name="Shortbow",
        description="A small bow suitable for quick shots.",
        group="simple_ranged",
        order=20,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED, WeaponProperty.TWO_HANDED),
        range_type=RangeType.RANGE,
        normal_range=80,
        long_range=320,
    )
)
_build_sling = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="sling",
        display_name="Sling",
        description="A simple leather sling for hurling stones or bullets.",
        group="simple_ranged",
        order=30,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.RANGED,),
        range_type=RangeType.RANGE,
        normal_range=30,
        long_range=120,
    )
)
_build_battleaxe = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="battleaxe",
        display_name="Battleaxe",
        description="A large axe suitable for battle.",
        group="martial_melee",
        order=10,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_greataxe = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="greataxe",
        display_name="Greataxe",
        description="A massive two-handed axe favored by barbarians.",
        group="martial_melee",
        order=20,
        damage_dice=12,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_greatsword = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="greatsword",
        display_name="Greatsword",
        description="A massive two-handed sword.",
        group="martial_melee",
        order=30,
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_longsword = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="longsword",
        display_name="Longsword",
        description="A versatile one-handed sword.",
        group="martial_melee",
        order=40,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_morningstar = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="morningstar",
        display_name="Morningstar",
        description="A spiked metal head mounted on a sturdy haft.",
        group="martial_melee",
        order=45,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.MARTIAL,),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_rapier = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="rapier",
        display_name="Rapier",
        description="A slender thrusting sword.",
        group="martial_melee",
        order=50,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.FINESSE, WeaponProperty.MARTIAL),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_scimitar = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="scimitar",
        display_name="Scimitar",
        description="A curved slashing sword favored by goblins.",
        group="martial_melee",
        order=60,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_shortsword = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="shortsword",
        display_name="Shortsword",
        description="A short blade suitable for quick strikes.",
        group="martial_melee",
        order=70,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_trident = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="trident",
        display_name="Trident",
        description="A three-pronged martial spear.",
        group="martial_melee",
        order=75,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.THROWN,
            WeaponProperty.VERSATILE,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_warhammer = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="warhammer",
        display_name="Warhammer",
        description="A heavy hammer designed for combat.",
        group="martial_melee",
        order=80,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=(WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        range_type=RangeType.REACH,
        normal_range=5,
    )
)
_build_longbow = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="longbow",
        display_name="Longbow",
        description="A tall bow capable of long-range shots.",
        group="martial_ranged",
        order=10,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.RANGE,
        normal_range=150,
        long_range=600,
    )
)
_build_heavy_crossbow = _declare_standard_weapon(
    _StandardWeaponSpec(
        content_id="heavy_crossbow",
        display_name="Heavy Crossbow",
        description="A powerful mechanical crossbow.",
        group="martial_ranged",
        order=20,
        damage_dice=10,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=(
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
        ),
        range_type=RangeType.RANGE,
        normal_range=100,
        long_range=400,
        source_table_name="Crossbow, heavy",
    )
)


def _declaration_and_recipe(factory):
    declaration = get_content_declaration(factory)
    return declaration, ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )


DAGGER_DECLARATION, DAGGER_RECIPE = _declaration_and_recipe(_build_dagger)
DAGGER_REF = DAGGER_DECLARATION.ref
HANDAXE_DECLARATION, HANDAXE_RECIPE = _declaration_and_recipe(_build_handaxe)
HANDAXE_REF = HANDAXE_DECLARATION.ref
JAVELIN_DECLARATION, JAVELIN_RECIPE = _declaration_and_recipe(_build_javelin)
JAVELIN_REF = JAVELIN_DECLARATION.ref
LIGHT_HAMMER_DECLARATION, LIGHT_HAMMER_RECIPE = _declaration_and_recipe(
    _build_light_hammer,
)
LIGHT_HAMMER_REF = LIGHT_HAMMER_DECLARATION.ref
MACE_DECLARATION, MACE_RECIPE = _declaration_and_recipe(_build_mace)
MACE_REF = MACE_DECLARATION.ref
QUARTERSTAFF_DECLARATION, QUARTERSTAFF_RECIPE = _declaration_and_recipe(
    _build_quarterstaff,
)
QUARTERSTAFF_REF = QUARTERSTAFF_DECLARATION.ref
SICKLE_DECLARATION, SICKLE_RECIPE = _declaration_and_recipe(_build_sickle)
SICKLE_REF = SICKLE_DECLARATION.ref
SPEAR_DECLARATION, SPEAR_RECIPE = _declaration_and_recipe(_build_spear)
SPEAR_REF = SPEAR_DECLARATION.ref
DART_DECLARATION, DART_RECIPE = _declaration_and_recipe(_build_dart)
DART_REF = DART_DECLARATION.ref
LIGHT_CROSSBOW_DECLARATION, LIGHT_CROSSBOW_RECIPE = (
    _declaration_and_recipe(_build_light_crossbow)
)
LIGHT_CROSSBOW_REF = LIGHT_CROSSBOW_DECLARATION.ref
SHORTBOW_DECLARATION, SHORTBOW_RECIPE = _declaration_and_recipe(
    _build_shortbow,
)
SHORTBOW_REF = SHORTBOW_DECLARATION.ref
SLING_DECLARATION, SLING_RECIPE = _declaration_and_recipe(_build_sling)
SLING_REF = SLING_DECLARATION.ref
BATTLEAXE_DECLARATION, BATTLEAXE_RECIPE = _declaration_and_recipe(
    _build_battleaxe,
)
BATTLEAXE_REF = BATTLEAXE_DECLARATION.ref
GREATAXE_DECLARATION, GREATAXE_RECIPE = _declaration_and_recipe(
    _build_greataxe,
)
GREATAXE_REF = GREATAXE_DECLARATION.ref
GREATSWORD_DECLARATION, GREATSWORD_RECIPE = _declaration_and_recipe(
    _build_greatsword,
)
GREATSWORD_REF = GREATSWORD_DECLARATION.ref
LONGSWORD_DECLARATION, LONGSWORD_RECIPE = _declaration_and_recipe(
    _build_longsword,
)
LONGSWORD_REF = LONGSWORD_DECLARATION.ref
MORNINGSTAR_DECLARATION, MORNINGSTAR_RECIPE = _declaration_and_recipe(
    _build_morningstar,
)
MORNINGSTAR_REF = MORNINGSTAR_DECLARATION.ref
RAPIER_DECLARATION, RAPIER_RECIPE = _declaration_and_recipe(_build_rapier)
RAPIER_REF = RAPIER_DECLARATION.ref
SCIMITAR_DECLARATION, SCIMITAR_RECIPE = _declaration_and_recipe(
    _build_scimitar,
)
SCIMITAR_REF = SCIMITAR_DECLARATION.ref
SHORTSWORD_DECLARATION, SHORTSWORD_RECIPE = _declaration_and_recipe(
    _build_shortsword,
)
SHORTSWORD_REF = SHORTSWORD_DECLARATION.ref
TRIDENT_DECLARATION, TRIDENT_RECIPE = _declaration_and_recipe(_build_trident)
TRIDENT_REF = TRIDENT_DECLARATION.ref
WARHAMMER_DECLARATION, WARHAMMER_RECIPE = _declaration_and_recipe(
    _build_warhammer,
)
WARHAMMER_REF = WARHAMMER_DECLARATION.ref
LONGBOW_DECLARATION, LONGBOW_RECIPE = _declaration_and_recipe(_build_longbow)
LONGBOW_REF = LONGBOW_DECLARATION.ref
HEAVY_CROSSBOW_DECLARATION, HEAVY_CROSSBOW_RECIPE = (
    _declaration_and_recipe(_build_heavy_crossbow)
)
HEAVY_CROSSBOW_REF = HEAVY_CROSSBOW_DECLARATION.ref

SRD_WEAPON_DECLARATIONS = (
    CLUB_DECLARATION,
    DAGGER_DECLARATION,
    HANDAXE_DECLARATION,
    JAVELIN_DECLARATION,
    LIGHT_HAMMER_DECLARATION,
    MACE_DECLARATION,
    QUARTERSTAFF_DECLARATION,
    SICKLE_DECLARATION,
    SPEAR_DECLARATION,
    DART_DECLARATION,
    LIGHT_CROSSBOW_DECLARATION,
    SHORTBOW_DECLARATION,
    SLING_DECLARATION,
    BATTLEAXE_DECLARATION,
    GREATAXE_DECLARATION,
    GREATSWORD_DECLARATION,
    LONGSWORD_DECLARATION,
    MORNINGSTAR_DECLARATION,
    RAPIER_DECLARATION,
    SCIMITAR_DECLARATION,
    SHORTSWORD_DECLARATION,
    TRIDENT_DECLARATION,
    WARHAMMER_DECLARATION,
    LONGBOW_DECLARATION,
    HEAVY_CROSSBOW_DECLARATION,
)

_DOUBLE_BLADED_SWORD_SPEC = _StandardWeaponSpec(
    content_id="double_bladed_sword",
    display_name="Double-Bladed Sword",
    description=(
        "An exotic two-handed sword with a blade at each end of its central "
        "grip."
    ),
    group="martial_melee",
    order=5,
    damage_dice=4,
    dice_numbers=2,
    damage_type=DamageType.SLASHING,
    properties=(
        WeaponProperty.TWO_HANDED,
        WeaponProperty.MARTIAL,
    ),
    range_type=RangeType.REACH,
    normal_range=5,
)


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.double_bladed_sword",
    version=1,
    parameters=StandardWeaponParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Double-Bladed Sword",
        description=(
            "An exotic two-handed sword with a blade at each end of its "
            "central grip."
        ),
        tags=(
            "custom",
            "martial",
            "melee",
            "neurodragon",
            "two_handed",
            "weapon",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="weapon.double_bladed_sword",
            visual_variant_key="double_bladed_sword",
            ui_group="weapons.neurodragon",
        ),
        ordering=ContentOrdering(
            sort_group="weapons.neurodragon",
            sort_order=5,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "NeuroDragon authored item catalog: Double-Bladed Sword"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "The project-authored two-bladed weapon owns one shared mechanic; "
            "named color variants remain recipe presets."
        ),
    ),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_double_bladed_sword(
    context: object,
    parameters: StandardWeaponParameters,
) -> Weapon:
    """Construct the canonical NeuroDragon double-bladed sword."""
    return _build_standard_weapon(
        context,
        _DOUBLE_BLADED_SWORD_SPEC,
        parameters,
    )


DOUBLE_BLADED_SWORD_DECLARATION, DOUBLE_BLADED_SWORD_RECIPE = (
    _declaration_and_recipe(_build_double_bladed_sword)
)
DOUBLE_BLADED_SWORD_REF = DOUBLE_BLADED_SWORD_DECLARATION.ref


def _unseen_strike_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Add extra damage when the attacker is unseen by the target.

    Args:
        event: Event currently being processed.
        source_entity_uuid: Entity UUID that owns the unseen-strike handler.

    Returns:
        Modified damage-roll event when the target cannot see the attacker;
        otherwise `None`.
    """
    if not isinstance(event, DamageRollResultEvent):
        return None
    if event.source_entity_uuid != source_entity_uuid:
        return None

    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if not target or not isinstance(target, Entity):
        return None

    contact = target.senses.entities.get(source_entity_uuid)
    if contact is not None and contact.visual:
        return None

    damage_bonus = ModifiableValue.create(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.target_entity_uuid,
        base_value=0,
        value_name="Unseen Strike Damage Bonus",
    )
    damage = Damage(
        name="Unseen Strike",
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.target_entity_uuid,
        damage_dice=6,
        dice_numbers=1,
        damage_bonus=damage_bonus,
        damage_type=DamageType.PIERCING,
    )
    extra_roll = damage.get_dice(event.attack_outcome).roll
    return event.append_damage_roll(
        damage,
        extra_roll,
        "Unseen Strike",
        "1d6 piercing (unseen attacker)",
    )


class _UnseenStrikeDagger(Weapon):
    """Dagger that adds damage through a damage-roll-result handler."""
    _handler_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Register the unseen-strike damage handler.

        Args:
            slot: Equipment slot receiving the dagger.
            entity_uuid: Entity UUID equipping the dagger.
        """
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            handler = EventHandler(
                name="Unseen Strike",
                source_entity_uuid=entity_uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity_uuid
                    )
                ],
                event_processor=_unseen_strike_processor
            )
            entity.add_event_handler(handler)
            self._handler_uuid = handler.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Remove the unseen-strike damage handler.

        Args:
            slot: Equipment slot releasing the dagger.
            entity_uuid: Entity UUID unequipping the dagger.
        """
        if self._handler_uuid:
            handler = EventHandler.get(self._handler_uuid)
            if handler and isinstance(handler, EventHandler):
                entity = Entity.get(entity_uuid)
                if entity and isinstance(entity, Entity):
                    entity.remove_event_handler(handler)
            self._handler_uuid = None


class AssassinDaggerParameters(BaseModel):
    """Assassin's Dagger has no authored construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.assassin_dagger",
    version=1,
    parameters=AssassinDaggerParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Assassin's Dagger",
        description=(
            "A shadowy blade that strikes harder when the target cannot see "
            "its wielder."
        ),
        tags=("custom", "dagger", "melee", "neurodragon", "weapon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="weapon.assassin_dagger",
            visual_variant_key="10000004",
            ui_group="weapons.neurodragon",
        ),
        ordering=ContentOrdering(
            sort_group="weapons.neurodragon",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor="Neurodragon original content baseline: Assassin's Dagger",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Original hook-bearing weapon behavior preserved exactly.",
    ),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_assassin_dagger(
    context: object,
    parameters: AssassinDaggerParameters,
) -> _UnseenStrikeDagger:
    """Construct the canonical hook-bearing Assassin's Dagger."""
    item_context = ItemBuildContext.model_validate(context)
    return _UnseenStrikeDagger(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Assassin's Dagger",
        visual_item_name="Dagger",
        visual_variant_id="10000004",
        description=(
            "A shadowy blade that strikes harder when the target can't see you coming. "
            "+1d6 piercing when unseen."
        ),
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


ASSASSIN_DAGGER_DECLARATION = get_content_declaration(_build_assassin_dagger)
ASSASSIN_DAGGER_REF = ASSASSIN_DAGGER_DECLARATION.ref
ASSASSIN_DAGGER_RECIPE = ContentRecipe.create(
    ref=ASSASSIN_DAGGER_REF,
    parameters={},
)


class _ArcaneStaff(Weapon):
    """Quarterstaff that grants a spell-attack modifier while equipped."""
    _spell_mod_uuid: Optional[UUID] = None
    _spell_mod_value_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Add the staff's spell-attack modifier.

        Args:
            slot: Equipment slot receiving the staff.
            entity_uuid: Entity UUID equipping the staff.
        """
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            modifier = NumericalModifier(
                name="Arcane Staff",
                value=1,
                source_entity_uuid=entity_uuid,
                target_entity_uuid=entity_uuid
            )
            mod_uuid = entity.spellcasting.spell_attack_bonus.self_static.add_value_modifier(modifier)
            self._spell_mod_uuid = mod_uuid
            self._spell_mod_value_uuid = entity.spellcasting.spell_attack_bonus.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Remove the staff's spell-attack modifier.

        Args:
            slot: Equipment slot releasing the staff.
            entity_uuid: Entity UUID unequipping the staff.
        """
        if self._spell_mod_uuid and self._spell_mod_value_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.spellcasting.spell_attack_bonus.self_static.remove_modifier(self._spell_mod_uuid)
            self._spell_mod_uuid = None
            self._spell_mod_value_uuid = None


class ArcaneStaffParameters(BaseModel):
    """Arcane Staff has no authored construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.arcane_staff",
    version=1,
    parameters=ArcaneStaffParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Arcane Staff",
        description=(
            "A staff crackling with arcane energy that improves spell attacks "
            "while equipped."
        ),
        tags=("custom", "melee", "neurodragon", "staff", "weapon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="weapon.arcane_staff",
            visual_variant_key="1000000f",
            ui_group="weapons.neurodragon",
        ),
        ordering=ContentOrdering(
            sort_group="weapons.neurodragon",
            sort_order=20,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor="Neurodragon original content baseline: Arcane Staff",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Original equip-scoped spell-attack modifier preserved exactly.",
    ),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_arcane_staff(
    context: object,
    parameters: ArcaneStaffParameters,
) -> _ArcaneStaff:
    """Construct the canonical equip-scoped Arcane Staff."""
    item_context = ItemBuildContext.model_validate(context)
    return _ArcaneStaff(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Arcane Staff",
        visual_item_name="Quarterstaff",
        visual_variant_id="1000000f",
        description="A staff crackling with arcane energy. +1 to spell attack rolls when equipped.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


ARCANE_STAFF_DECLARATION = get_content_declaration(_build_arcane_staff)
ARCANE_STAFF_REF = ARCANE_STAFF_DECLARATION.ref
ARCANE_STAFF_RECIPE = ContentRecipe.create(
    ref=ARCANE_STAFF_REF,
    parameters={},
)

NEURODRAGON_WEAPON_DECLARATIONS = (
    DOUBLE_BLADED_SWORD_DECLARATION,
    ASSASSIN_DAGGER_DECLARATION,
    ARCANE_STAFF_DECLARATION,
)
