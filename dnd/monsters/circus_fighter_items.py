"""Canonical possession recipes authored for the circus fighter content."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.blocks.equipment import BodyArmor, Range, Weapon
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
    get_content_declaration,
)
from dnd.core.equipment_types import (
    ArmorType,
    BodyPart,
    WeaponProperty,
)
from dnd.core.events import RangeType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    DamageType,
)
from dnd.core.values import ModifiableValue
from dnd.items.authored_presentations import (
    authored_item_factory as item_factory,
)


class CircusPossessionParameters(BaseModel):
    """Circus possessions have one exact authored construction each."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_POSSESSION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.POSSESSION,
)


def _original_provenance(display_name: str) -> ContentProvenance:
    """Describe one existing project-authored circus possession."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: circus fighter "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Exact mechanics from the pre-registry circus fighter factory.",
    )


def _descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    tags: tuple[str, ...],
    order: int,
    visual_variant_key: str | None = None,
) -> ContentDescriptorSpec:
    """Build stable public metadata for one circus possession."""
    family = content_id.split(".", 1)[0]
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=tuple(sorted({"circus", "neurodragon", *tags})),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            visual_variant_key=visual_variant_key,
            ui_group=f"{family}.circus",
        ),
        ordering=ContentOrdering(
            sort_group=f"{family}.circus",
            sort_order=order,
        ),
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.circus.rusty_dagger",
    version=1,
    parameters=CircusPossessionParameters,
    descriptor=_descriptor(
        content_id="weapon.circus.rusty_dagger",
        display_name="Rusty Dagger",
        description=(
            "A poorly maintained dagger whose rusty blade makes accurate "
            "strikes difficult."
        ),
        tags=("dagger", "melee", "weapon"),
        order=10,
    ),
    provenance=_original_provenance("Rusty Dagger"),
    item_definition=_POSSESSION,
)
def _build_rusty_dagger(
    raw_context: object,
    parameters: CircusPossessionParameters,
) -> Weapon:
    """Construct the exact disadvantage-bearing legacy dagger."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    dagger = Weapon(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Rusty Dagger",
        description=(
            "A poorly maintained dagger with a rusty blade. The ornate hilt "
            "is still beautiful, but the blade has seen better days, making "
            "it harder to strike accurately."
        ),
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.THROWN,
        ],
        range=Range(type=RangeType.REACH, normal=5),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
    )
    dagger.attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=context.source_entity_uuid,
            target_entity_uuid=None,
            name="Rusty Blade",
            value=AdvantageStatus.DISADVANTAGE,
        ),
    )
    return dagger


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.circus.flaming_scimitar",
    version=1,
    parameters=CircusPossessionParameters,
    descriptor=_descriptor(
        content_id="weapon.circus.flaming_scimitar",
        display_name="Flaming Scimitar",
        description=(
            "An elegant curved blade enchanted with magical flames for a "
            "circus performer's acrobatic fighting style."
        ),
        tags=("fire", "melee", "scimitar", "weapon"),
        order=20,
        visual_variant_key="30000017",
    ),
    provenance=_original_provenance("Flaming Scimitar"),
    item_definition=_POSSESSION,
)
def _build_flaming_scimitar(
    raw_context: object,
    parameters: CircusPossessionParameters,
) -> Weapon:
    """Construct the exact legacy scimitar with one extra fire die."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return Weapon(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Flaming Scimitar",
        visual_item_name="Scimitar",
        visual_variant_id="30000017",
        description=(
            "An elegant curved blade enchanted with magical flames. The "
            "blade dances with fire during performances, leaving trails of "
            "light in its wake. The flames intensify when the wielder "
            "performs acrobatic maneuvers."
        ),
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[6],
        extra_damage_dices_numbers=[1],
        extra_damage_bonus=[
            ModifiableValue.create(
                source_entity_uuid=context.source_entity_uuid,
                base_value=0,
                value_name="Fire Damage Bonus",
            ),
        ],
        extra_damage_type=[DamageType.FIRE],
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="armor.circus.performer_leather",
    version=1,
    parameters=CircusPossessionParameters,
    descriptor=_descriptor(
        content_id="armor.circus.performer_leather",
        display_name="Performer's Leather Armor",
        description=(
            "Flexible leather armor decorated for an acrobatic circus "
            "performer."
        ),
        tags=("armor", "light_armor"),
        order=30,
    ),
    provenance=_original_provenance("Performer's Leather Armor"),
    item_definition=_POSSESSION,
)
def _build_performer_leather(
    raw_context: object,
    parameters: CircusPossessionParameters,
) -> BodyArmor:
    """Construct the exact AC 11, maximum-Dex-five legacy armor."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return BodyArmor(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Performer's Leather Armor",
        description=(
            "A masterfully crafted set of leather armor adorned with "
            "intricate circus motifs. The armor is specially designed to "
            "allow maximum flexibility for acrobatic performances while "
            "providing protection. Gold and silver thread accents catch the "
            "light during movement."
        ),
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=11,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=5,
            value_name="Max Dex Bonus",
        ),
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.circus.longsword_plus_one",
    version=1,
    parameters=CircusPossessionParameters,
    descriptor=_descriptor(
        content_id="weapon.circus.longsword_plus_one",
        display_name="Longsword +1",
        description=(
            "A magical longsword granting +1 to attack and damage rolls."
        ),
        tags=("magic", "melee", "weapon"),
        order=40,
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 250, Magic Items A-Z: "
            "Weapon, +1, +2, or +3"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact +1 Longsword specialization retained from the legacy "
            "circus module; the generic +2/+3 family remains separate work."
        ),
    ),
    item_definition=_POSSESSION,
)
def _build_longsword_plus_one(
    raw_context: object,
    parameters: CircusPossessionParameters,
) -> Weapon:
    """Construct the exact +1 attack and +1 damage legacy longsword."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return Weapon(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Longsword +1",
        description=(
            "A finely crafted magical longsword that grants a +1 bonus to "
            "attack and damage rolls."
        ),
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=1,
            value_name="Attack Bonus",
        ),
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=1,
            value_name="Damage Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="weapon.circus.soul_draining_morningstar",
    version=1,
    parameters=CircusPossessionParameters,
    descriptor=_descriptor(
        content_id="weapon.circus.soul_draining_morningstar",
        display_name="Soul-Draining Morningstar",
        description=(
            "A wicked morningstar carrying an additional pulse of necrotic "
            "damage."
        ),
        tags=("melee", "necrotic", "weapon"),
        order=50,
    ),
    provenance=_original_provenance("Soul-Draining Morningstar"),
    item_definition=_POSSESSION,
)
def _build_soul_draining_morningstar(
    raw_context: object,
    parameters: CircusPossessionParameters,
) -> Weapon:
    """Construct the exact legacy morningstar with one necrotic d4."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return Weapon(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Soul-Draining Morningstar",
        description=(
            "A wicked morningstar imbued with necrotic energy that drains "
            "the life force of its victims."
        ),
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[4],
        extra_damage_dices_numbers=[1],
        extra_damage_bonus=[
            ModifiableValue.create(
                source_entity_uuid=context.source_entity_uuid,
                base_value=0,
                value_name="Necrotic Damage",
            ),
        ],
        extra_damage_type=[DamageType.NECROTIC],
    )


RUSTY_DAGGER_DECLARATION = get_content_declaration(_build_rusty_dagger)
RUSTY_DAGGER_REF = RUSTY_DAGGER_DECLARATION.ref
RUSTY_DAGGER_RECIPE = ContentRecipe.create(
    ref=RUSTY_DAGGER_REF,
    parameters={},
)
FLAMING_SCIMITAR_DECLARATION = get_content_declaration(
    _build_flaming_scimitar,
)
FLAMING_SCIMITAR_REF = FLAMING_SCIMITAR_DECLARATION.ref
FLAMING_SCIMITAR_RECIPE = ContentRecipe.create(
    ref=FLAMING_SCIMITAR_REF,
    parameters={},
)
PERFORMER_LEATHER_DECLARATION = get_content_declaration(
    _build_performer_leather,
)
PERFORMER_LEATHER_REF = PERFORMER_LEATHER_DECLARATION.ref
PERFORMER_LEATHER_RECIPE = ContentRecipe.create(
    ref=PERFORMER_LEATHER_REF,
    parameters={},
)
LONGSWORD_PLUS_ONE_DECLARATION = get_content_declaration(
    _build_longsword_plus_one,
)
LONGSWORD_PLUS_ONE_REF = LONGSWORD_PLUS_ONE_DECLARATION.ref
LONGSWORD_PLUS_ONE_RECIPE = ContentRecipe.create(
    ref=LONGSWORD_PLUS_ONE_REF,
    parameters={},
)
SOUL_DRAINING_MORNINGSTAR_DECLARATION = get_content_declaration(
    _build_soul_draining_morningstar,
)
SOUL_DRAINING_MORNINGSTAR_REF = (
    SOUL_DRAINING_MORNINGSTAR_DECLARATION.ref
)
SOUL_DRAINING_MORNINGSTAR_RECIPE = ContentRecipe.create(
    ref=SOUL_DRAINING_MORNINGSTAR_REF,
    parameters={},
)


NEURODRAGON_CIRCUS_ITEM_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    RUSTY_DAGGER_DECLARATION,
    FLAMING_SCIMITAR_DECLARATION,
    PERFORMER_LEATHER_DECLARATION,
    LONGSWORD_PLUS_ONE_DECLARATION,
    SOUL_DRAINING_MORNINGSTAR_DECLARATION,
)
NEURODRAGON_CIRCUS_ITEM_RECIPES_BY_LEGACY_ID = MappingProxyType(
    {
        "flaming_scimitar": FLAMING_SCIMITAR_RECIPE,
        "longsword_plus_one": LONGSWORD_PLUS_ONE_RECIPE,
        "performer_armor": PERFORMER_LEATHER_RECIPE,
        "rusty_dagger": RUSTY_DAGGER_RECIPE,
        "soul_draining_morningstar": SOUL_DRAINING_MORNINGSTAR_RECIPE,
    },
)
