"""Canonical armor, apparel, headgear, and shield content declarations."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from dnd.blocks.equipment import Armor, BodyArmor, Boots, Gauntlets, Helmet, Shield
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
from dnd.core.equipment_types import ArmorType, BodyPart, EquipmentSlot
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ContextualNumericalModifier, NumericalModifier
from dnd.entity import Entity
from dnd.items.authored_presentations import (
    authored_item_factory as item_factory,
)
from dnd.items.visual_variants import ItemVisualVariantParameters


def heavy_armor_strength_penalty(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None,
) -> Optional[NumericalModifier]:
    """Return the heavy-armor movement penalty when Strength is too low.

    Args:
        source_entity_uuid: Entity wearing the armor.
        target_entity_uuid: Unused contextual target UUID.
        context: Unused contextual data.

    Returns:
        A `NumericalModifier` for -10 feet of speed when the wearer does not
        meet the armor Strength requirement; otherwise `None`.
    """
    _ = target_entity_uuid, context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    body_armor = entity.equipment.body_armor
    if body_armor is None or body_armor.strength_requirement is None:
        return None
    strength_score = entity.ability_scores.strength.ability_score.score
    if strength_score >= body_armor.strength_requirement:
        return None
    return NumericalModifier(
        name=f"{body_armor.name} Strength Requirement",
        value=-10,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid,
    )


class StealthDisadvantageBodyArmor(BodyArmor):
    """BodyArmor subclass that applies stealth disadvantage on equip.

    Armors with `stealth_disadvantage=True` use this hook-bearing subclass so
    equip and unequip can add and remove the stealth and heavy-armor movement
    modifiers through the owning entity.
    """
    _stealth_mod_uuid: Optional[UUID] = None
    _stealth_mod_value_uuid: Optional[UUID] = None
    _movement_mod_uuid: Optional[UUID] = None
    _movement_mod_value_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            self._stealth_mod_uuid = entity.skill_set.stealth.skill_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name=f"{self.name} Stealth Disadvantage",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=entity_uuid
                )
            )
            self._stealth_mod_value_uuid = entity.skill_set.stealth.skill_bonus.uuid
            if self.strength_requirement is not None:
                modifier = ContextualNumericalModifier(
                    name=f"{self.name} Strength Requirement",
                    source_entity_uuid=entity_uuid,
                    target_entity_uuid=entity_uuid,
                    callable=heavy_armor_strength_penalty,
                )
                self._movement_mod_uuid = entity.action_economy.movement.self_contextual.add_value_modifier(modifier)
                self._movement_mod_value_uuid = entity.action_economy.movement.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        if self._stealth_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.skill_set.stealth.skill_bonus.self_static.remove_modifier(self._stealth_mod_uuid)
            self._stealth_mod_uuid = None
            self._stealth_mod_value_uuid = None
        if self._movement_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.action_economy.movement.self_contextual.remove_value_modifier(self._movement_mod_uuid)
            self._movement_mod_uuid = None
            self._movement_mod_value_uuid = None


class SpellbladeCrown(Helmet):
    """Authored crown that grants +3 Charisma while equipped."""

    _charisma_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None or self._charisma_modifier_uuid is not None:
            return
        self._charisma_modifier_uuid = (
            entity.ability_scores.charisma.ability_score.self_static
            .add_value_modifier(
                NumericalModifier(
                    name="Spellblade Crown Charisma",
                    value=3,
                    source_entity_uuid=self.uuid,
                    target_entity_uuid=entity_uuid,
                ),
            )
        )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        if self._charisma_modifier_uuid is None:
            return
        entity = Entity.get(entity_uuid)
        if entity is not None:
            entity.ability_scores.charisma.ability_score.self_static.remove_modifier(
                self._charisma_modifier_uuid,
            )
        self._charisma_modifier_uuid = None


class SrdArmorParameters(ItemVisualVariantParameters):
    """Optional authored presentation variant over canonical SRD mechanics."""


_POSSESSION_ITEM_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.POSSESSION,
)


def _armor_descriptor(
    *,
    content_key: str,
    display_name: str,
    description: str,
    armor_group: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    """Build one stable public SRD armor catalog descriptor."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("armor", armor_group, "srd"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_key,
            visual_variant_key=content_key.removeprefix("armor."),
            ui_group=f"armor.{armor_group}",
        ),
        ordering=ContentOrdering(
            sort_group=f"armor.{armor_group}",
            sort_order=sort_order,
        ),
    )


def _armor_provenance(source_name: str) -> ContentProvenance:
    """Build the exact reviewed SRD 5.1 armor-table citation."""
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), pp. 63-64, Armor table: "
            f"{source_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Playable Armor Class and equip mechanics; cost and weight parity "
            "remain source-ledger work."
        ),
    )


def _build_srd_body_armor(
    context: ItemBuildContext,
    parameters: SrdArmorParameters,
    *,
    name: str,
    description: str,
    armor_type: ArmorType,
    armor_class: int,
    max_dex_bonus: int,
    stealth_disadvantage: bool = False,
    strength_requirement: int | None = None,
) -> BodyArmor:
    """Construct one canonical body-armor instance from immutable facts."""
    armor_model = (
        StealthDisadvantageBodyArmor
        if stealth_disadvantage
        else BodyArmor
    )
    return armor_model(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name or name,
        visual_item_name=(
            name if parameters.visual_variant_id is not None else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description=description,
        type=armor_type,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=armor_class,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=max_dex_bonus,
            value_name="Max Dex Bonus",
        ),
        strength_requirement=strength_requirement,
        stealth_disadvantage=stealth_disadvantage,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.padded",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.padded",
        display_name="Padded Armor",
        description="Quilted layers of cloth and batting.",
        armor_group="light",
        sort_order=10,
    ),
    provenance=_armor_provenance("Padded"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_padded_armor(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD padded armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Padded Armor",
        description="Quilted layers of cloth and batting.",
        armor_type=ArmorType.LIGHT,
        armor_class=11,
        max_dex_bonus=10,
        stealth_disadvantage=True,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.leather",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.leather",
        display_name="Leather Armor",
        description="Basic leather armor providing light protection.",
        armor_group="light",
        sort_order=20,
    ),
    provenance=_armor_provenance("Leather"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_leather_armor(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD leather armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Leather Armor",
        description="Basic leather armor providing light protection.",
        armor_type=ArmorType.LIGHT,
        armor_class=11,
        max_dex_bonus=10,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.studded_leather",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.studded_leather",
        display_name="Studded Leather",
        description="Tough leather reinforced with close-set rivets.",
        armor_group="light",
        sort_order=30,
    ),
    provenance=_armor_provenance("Studded leather"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_studded_leather(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD studded leather armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Studded Leather",
        description="Tough leather reinforced with close-set rivets.",
        armor_type=ArmorType.LIGHT,
        armor_class=12,
        max_dex_bonus=10,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.hide",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.hide",
        display_name="Hide Armor",
        description="Crude armor made from thick animal hides.",
        armor_group="medium",
        sort_order=10,
    ),
    provenance=_armor_provenance("Hide"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_hide_armor(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD hide armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Hide Armor",
        description="Crude armor made from thick animal hides.",
        armor_type=ArmorType.MEDIUM,
        armor_class=12,
        max_dex_bonus=2,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.chain_shirt",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.chain_shirt",
        display_name="Chain Shirt",
        description="Interlocking metal rings forming a shirt.",
        armor_group="medium",
        sort_order=20,
    ),
    provenance=_armor_provenance("Chain shirt"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_chain_shirt(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD chain shirt."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Chain Shirt",
        description="Interlocking metal rings forming a shirt.",
        armor_type=ArmorType.MEDIUM,
        armor_class=13,
        max_dex_bonus=2,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.scale_mail",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.scale_mail",
        display_name="Scale Mail",
        description="Overlapping metal scales sewn to a leather coat.",
        armor_group="medium",
        sort_order=30,
    ),
    provenance=_armor_provenance("Scale mail"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_scale_mail(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD scale mail."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Scale Mail",
        description="Overlapping metal scales sewn to a leather coat.",
        armor_type=ArmorType.MEDIUM,
        armor_class=14,
        max_dex_bonus=2,
        stealth_disadvantage=True,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.breastplate",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.breastplate",
        display_name="Breastplate",
        description="A fitted metal chest piece with leather straps.",
        armor_group="medium",
        sort_order=40,
    ),
    provenance=_armor_provenance("Breastplate"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_breastplate(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD breastplate."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Breastplate",
        description="A fitted metal chest piece with leather straps.",
        armor_type=ArmorType.MEDIUM,
        armor_class=14,
        max_dex_bonus=2,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.half_plate",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.half_plate",
        display_name="Half Plate",
        description="Shaped metal plates covering most of the body.",
        armor_group="medium",
        sort_order=50,
    ),
    provenance=_armor_provenance("Half plate"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_half_plate(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD half plate."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Half Plate",
        description="Shaped metal plates covering most of the body.",
        armor_type=ArmorType.MEDIUM,
        armor_class=15,
        max_dex_bonus=2,
        stealth_disadvantage=True,
    )



@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.ring_mail",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.ring_mail",
        display_name="Ring Mail",
        description="Leather armor with heavy rings sewn into it.",
        armor_group="heavy",
        sort_order=10,
    ),
    provenance=_armor_provenance("Ring mail"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_ring_mail(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD ring mail."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Ring Mail",
        description="Leather armor with heavy rings sewn into it.",
        armor_type=ArmorType.HEAVY,
        armor_class=14,
        max_dex_bonus=0,
        stealth_disadvantage=True,
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.chain_mail",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.chain_mail",
        display_name="Chain Mail",
        description="Interlocking metal rings over quilted fabric.",
        armor_group="heavy",
        sort_order=20,
    ),
    provenance=_armor_provenance("Chain mail"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_chain_mail(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD chain mail."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Chain Mail",
        description="Interlocking metal rings over quilted fabric.",
        armor_type=ArmorType.HEAVY,
        armor_class=16,
        max_dex_bonus=0,
        strength_requirement=13,
        stealth_disadvantage=True,
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.splint",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.splint",
        display_name="Splint Armor",
        description="Narrow vertical strips of metal riveted to leather.",
        armor_group="heavy",
        sort_order=30,
    ),
    provenance=_armor_provenance("Splint"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_splint_armor(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD splint armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Splint Armor",
        description="Narrow vertical strips of metal riveted to leather.",
        armor_type=ArmorType.HEAVY,
        armor_class=17,
        max_dex_bonus=0,
        strength_requirement=15,
        stealth_disadvantage=True,
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="armor.plate",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=_armor_descriptor(
        content_key="armor.plate",
        display_name="Plate Armor",
        description="Full plate armor providing maximum protection.",
        armor_group="heavy",
        sort_order=40,
    ),
    provenance=_armor_provenance("Plate"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_plate_armor(
    context: object,
    parameters: SrdArmorParameters,
) -> BodyArmor:
    """Construct the canonical SRD plate armor."""
    return _build_srd_body_armor(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Plate Armor",
        description="Full plate armor providing maximum protection.",
        armor_type=ArmorType.HEAVY,
        armor_class=18,
        max_dex_bonus=0,
        strength_requirement=15,
        stealth_disadvantage=True,
    )


class NeurodragonStaticItemParameters(BaseModel):
    """A NeuroDragon item definition with no authored variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class WoodenShieldVariantParameters(ItemVisualVariantParameters):
    """Optional authored presentation variant over wooden-shield mechanics."""


class ApparelVariantParameters(BaseModel):
    """Typed visual and RPG-label variant for body apparel or footwear."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visual_variant_id: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)


class HeadgearVariantParameters(BaseModel):
    """Typed renderer variant for fixed-name headgear."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visual_variant_id: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)


def _neurodragon_apparel_descriptor(
    *,
    content_key: str,
    display_name: str,
    description: str,
    group: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    """Build one stable public NeuroDragon apparel descriptor."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("apparel", "neurodragon", group),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_key,
            visual_variant_key=content_key.rsplit(".", 1)[-1],
            ui_group=f"apparel.{group}",
        ),
        ordering=ContentOrdering(
            sort_group=f"apparel.{group}",
            sort_order=sort_order,
        ),
    )


def _neurodragon_apparel_provenance(
    display_name: str,
) -> ContentProvenance:
    """Build reviewed original-content provenance for one apparel root."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Original equipment and renderer-variant behavior preserved "
            "exactly."
        ),
    )


def _build_neurodragon_cloth_outfit(
    context: ItemBuildContext,
    parameters: ApparelVariantParameters,
    *,
    visual_item_name: str,
    description: str,
) -> BodyArmor:
    """Construct one recipe-parameterized cloth body outfit."""
    return BodyArmor(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name or visual_item_name,
        visual_item_name=visual_item_name,
        visual_variant_id=parameters.visual_variant_id,
        description=description,
        type=ArmorType.CLOTH,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=10,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


def _build_neurodragon_footwear(
    context: ItemBuildContext,
    parameters: ApparelVariantParameters,
    *,
    visual_item_name: str,
    description: str,
    armor_type: ArmorType,
) -> Boots:
    """Construct one recipe-parameterized zero-AC footwear item."""
    return Boots(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name or visual_item_name,
        visual_item_name=visual_item_name,
        visual_variant_id=parameters.visual_variant_id,
        description=description,
        type=armor_type,
        body_part=BodyPart.FEET,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


def _build_neurodragon_headgear(
    context: ItemBuildContext,
    parameters: HeadgearVariantParameters,
    *,
    name: str,
    description: str,
    armor_type: ArmorType,
) -> Helmet:
    """Construct one fixed-name, recipe-parameterized headgear item."""
    return Helmet(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name or name,
        visual_item_name=(
            name if parameters.visual_variant_id is not None else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description=description,
        type=armor_type,
        body_part=BodyPart.HEAD,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


def _build_neurodragon_visual_gear(
    context: ItemBuildContext,
    parameters: ApparelVariantParameters,
    *,
    item_model: type[Armor],
    name: str,
    description: str,
    armor_type: ArmorType,
    body_part: BodyPart,
    armor_class: int,
) -> Armor:
    """Construct one zero-effect authored apparel root and its visual variant."""
    return item_model(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name=parameters.display_name or name,
        visual_item_name=name,
        visual_variant_id=parameters.visual_variant_id,
        description=description,
        type=armor_type,
        body_part=body_part,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=armor_class,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


def _declare_neurodragon_visual_gear(
    *,
    content_id: str,
    display_name: str,
    description: str,
    group: str,
    sort_order: int,
    item_model: type[Armor],
    armor_type: ArmorType,
    body_part: BodyPart,
    armor_class: int = 0,
):
    """Declare one mechanical gear root shared by all of its named colors."""
    def factory(
        context: object,
        parameters: ApparelVariantParameters,
    ) -> Armor:
        return _build_neurodragon_visual_gear(
            ItemBuildContext.model_validate(context),
            parameters,
            item_model=item_model,
            name=display_name,
            description=description,
            armor_type=armor_type,
            body_part=body_part,
            armor_class=armor_class,
        )

    factory.__name__ = f"_build_{content_id.rsplit('.', 1)[-1]}"
    factory.__qualname__ = factory.__name__
    return item_factory(
        pack_id="content.neurodragon",
        content_id=content_id,
        version=1,
        parameters=ApparelVariantParameters,
        descriptor=_neurodragon_apparel_descriptor(
            content_key=content_id,
            display_name=display_name,
            description=description,
            group=group,
            sort_order=sort_order,
        ),
        provenance=_neurodragon_apparel_provenance(display_name),
        item_definition=_POSSESSION_ITEM_DEFINITION,
    )(factory)


_build_fine_clothes = _declare_neurodragon_visual_gear(
    content_id="apparel.fine_clothes",
    display_name="Fine Clothes",
    description="Tailored clothes made from quality cloth.",
    group="body",
    sort_order=25,
    item_model=BodyArmor,
    armor_type=ArmorType.CLOTH,
    body_part=BodyPart.BODY,
    armor_class=10,
)
_build_cloth_hood = _declare_neurodragon_visual_gear(
    content_id="apparel.cloth_hood",
    display_name="Cloth Hood",
    description="A simple cloth hood.",
    group="headgear",
    sort_order=40,
    item_model=Helmet,
    armor_type=ArmorType.CLOTH,
    body_part=BodyPart.HEAD,
)
_build_leather_hood = _declare_neurodragon_visual_gear(
    content_id="apparel.leather_hood",
    display_name="Leather Hood",
    description="A fitted hood made from supple leather.",
    group="headgear",
    sort_order=50,
    item_model=Helmet,
    armor_type=ArmorType.LIGHT,
    body_part=BodyPart.HEAD,
)
_build_chain_coif = _declare_neurodragon_visual_gear(
    content_id="apparel.chain_coif",
    display_name="Chain Coif",
    description="A fitted coif of interlocking metal rings.",
    group="headgear",
    sort_order=60,
    item_model=Helmet,
    armor_type=ArmorType.HEAVY,
    body_part=BodyPart.HEAD,
)
_build_horned_helmet = _declare_neurodragon_visual_gear(
    content_id="apparel.horned_helmet",
    display_name="Horned Helmet",
    description="A metal war helmet crowned by prominent horns.",
    group="headgear",
    sort_order=70,
    item_model=Helmet,
    armor_type=ArmorType.HEAVY,
    body_part=BodyPart.HEAD,
)
_build_great_helm = _declare_neurodragon_visual_gear(
    content_id="apparel.great_helm",
    display_name="Great Helm",
    description="A heavy enclosed helmet that covers the face.",
    group="headgear",
    sort_order=80,
    item_model=Helmet,
    armor_type=ArmorType.HEAVY,
    body_part=BodyPart.HEAD,
)
_build_monster_helm = _declare_neurodragon_visual_gear(
    content_id="apparel.monster_helm",
    display_name="Monster Helm",
    description="A fantastical headpiece shaped like a monstrous visage.",
    group="headgear",
    sort_order=90,
    item_model=Helmet,
    armor_type=ArmorType.CLOTH,
    body_part=BodyPart.HEAD,
)
_build_bracers = _declare_neurodragon_visual_gear(
    content_id="apparel.bracers",
    display_name="Bracers",
    description="Protective forearm guards that leave the hands exposed.",
    group="hands",
    sort_order=10,
    item_model=Gauntlets,
    armor_type=ArmorType.LIGHT,
    body_part=BodyPart.HANDS,
)
_build_leather_gloves = _declare_neurodragon_visual_gear(
    content_id="apparel.leather_gloves",
    display_name="Leather Gloves",
    description="Close-fitting gloves made from leather.",
    group="hands",
    sort_order=20,
    item_model=Gauntlets,
    armor_type=ArmorType.LIGHT,
    body_part=BodyPart.HANDS,
)
_build_gauntlets = _declare_neurodragon_visual_gear(
    content_id="apparel.gauntlets",
    display_name="Gauntlets",
    description="Articulated plate protection for the hands.",
    group="hands",
    sort_order=30,
    item_model=Gauntlets,
    armor_type=ArmorType.HEAVY,
    body_part=BodyPart.HANDS,
)
_build_monster_hands = _declare_neurodragon_visual_gear(
    content_id="apparel.monster_hands",
    display_name="Monster Hands",
    description="Fantastical gloves shaped like monstrous appendages.",
    group="hands",
    sort_order=40,
    item_model=Gauntlets,
    armor_type=ArmorType.CLOTH,
    body_part=BodyPart.HANDS,
)


@item_factory(
    pack_id="content.neurodragon",
    content_id="armor.cloth",
    version=1,
    parameters=NeurodragonStaticItemParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="armor.cloth",
        display_name="Cloth Armor",
        description="Simple clothing that provides no protection.",
        group="body",
        sort_order=10,
    ),
    provenance=_neurodragon_apparel_provenance("Cloth Armor"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_cloth_armor(
    context: object,
    parameters: NeurodragonStaticItemParameters,
) -> BodyArmor:
    """Construct canonical NeuroDragon cloth armor."""
    _ = parameters
    item_context = ItemBuildContext.model_validate(context)
    return BodyArmor(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Cloth Armor",
        description="Simple clothing that provides no protection.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=10,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.common_clothes",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.common_clothes",
        display_name="Common Clothes",
        description="Simple everyday clothing suited to work and village life.",
        group="body",
        sort_order=20,
    ),
    provenance=_neurodragon_apparel_provenance("Common Clothes"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_common_clothes(
    context: object,
    parameters: ApparelVariantParameters,
) -> BodyArmor:
    """Construct canonical recipe-parameterized Common Clothes."""
    return _build_neurodragon_cloth_outfit(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Common Clothes",
        description="Simple everyday clothing suited to work and village life.",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.travelers_clothes",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.travelers_clothes",
        display_name="Traveler's Clothes",
        description="Hard-wearing clothes cut for travel and outdoor work.",
        group="body",
        sort_order=30,
    ),
    provenance=_neurodragon_apparel_provenance("Traveler's Clothes"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_travelers_clothes(
    context: object,
    parameters: ApparelVariantParameters,
) -> BodyArmor:
    """Construct canonical recipe-parameterized Traveler's Clothes."""
    return _build_neurodragon_cloth_outfit(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Traveler's Clothes",
        description="Hard-wearing clothes cut for travel and outdoor work.",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.costume",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.costume",
        display_name="Costume",
        description=(
            "Distinctive garb made for performance, ceremony, or the arena."
        ),
        group="body",
        sort_order=40,
    ),
    provenance=_neurodragon_apparel_provenance("Costume"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_costume(
    context: object,
    parameters: ApparelVariantParameters,
) -> BodyArmor:
    """Construct canonical recipe-parameterized Costume."""
    return _build_neurodragon_cloth_outfit(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Costume",
        description=(
            "Distinctive garb made for performance, ceremony, or the arena."
        ),
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.robes",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.robes",
        display_name="Robes",
        description="Cloth robes suitable for an arcane caster.",
        group="body",
        sort_order=50,
    ),
    provenance=_neurodragon_apparel_provenance("Robes"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_robes(
    context: object,
    parameters: ApparelVariantParameters,
) -> BodyArmor:
    """Construct canonical recipe-parameterized Robes."""
    return _build_neurodragon_cloth_outfit(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Robes",
        description="Cloth robes suitable for an arcane caster.",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.cloth_shoes",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.cloth_shoes",
        display_name="Cloth Shoes",
        description="Soft cloth shoes.",
        group="footwear",
        sort_order=10,
    ),
    provenance=_neurodragon_apparel_provenance("Cloth Shoes"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_cloth_shoes(
    context: object,
    parameters: ApparelVariantParameters,
) -> Boots:
    """Construct canonical recipe-parameterized Cloth Shoes."""
    return _build_neurodragon_footwear(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Cloth Shoes",
        description="Soft cloth shoes.",
        armor_type=ArmorType.CLOTH,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.leather_boots",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.leather_boots",
        display_name="Leather Boots",
        description="Sturdy leather adventuring boots.",
        group="footwear",
        sort_order=20,
    ),
    provenance=_neurodragon_apparel_provenance("Leather Boots"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_leather_boots(
    context: object,
    parameters: ApparelVariantParameters,
) -> Boots:
    """Construct canonical recipe-parameterized Leather Boots."""
    return _build_neurodragon_footwear(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Leather Boots",
        description="Sturdy leather adventuring boots.",
        armor_type=ArmorType.LIGHT,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.sandals",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.sandals",
        display_name="Sandals",
        description=(
            "Simple open footwear suited to warm climates and humble dress."
        ),
        group="footwear",
        sort_order=30,
    ),
    provenance=_neurodragon_apparel_provenance("Sandals"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_sandals(
    context: object,
    parameters: ApparelVariantParameters,
) -> Boots:
    """Construct canonical recipe-parameterized Sandals."""
    return _build_neurodragon_footwear(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Sandals",
        description=(
            "Simple open footwear suited to warm climates and humble dress."
        ),
        armor_type=ArmorType.CLOTH,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.leather_shoes",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.leather_shoes",
        display_name="Leather Shoes",
        description="Plain leather shoes for daily wear.",
        group="footwear",
        sort_order=40,
    ),
    provenance=_neurodragon_apparel_provenance("Leather Shoes"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_leather_shoes(
    context: object,
    parameters: ApparelVariantParameters,
) -> Boots:
    """Construct canonical recipe-parameterized Leather Shoes."""
    return _build_neurodragon_footwear(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Leather Shoes",
        description="Plain leather shoes for daily wear.",
        armor_type=ArmorType.LIGHT,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.armored_boots",
    version=1,
    parameters=ApparelVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.armored_boots",
        display_name="Armored Boots",
        description=(
            "Plate-reinforced boots intended to complete a heavy armor "
            "harness."
        ),
        group="footwear",
        sort_order=50,
    ),
    provenance=_neurodragon_apparel_provenance("Armored Boots"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_armored_boots(
    context: object,
    parameters: ApparelVariantParameters,
) -> Boots:
    """Construct canonical recipe-parameterized Armored Boots."""
    return _build_neurodragon_footwear(
        ItemBuildContext.model_validate(context),
        parameters,
        visual_item_name="Armored Boots",
        description=(
            "Plate-reinforced boots intended to complete a heavy armor "
            "harness."
        ),
        armor_type=ArmorType.HEAVY,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.iron_helmet",
    version=1,
    parameters=HeadgearVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.iron_helmet",
        display_name="Iron Helmet",
        description="A sturdy metal helmet.",
        group="headgear",
        sort_order=10,
    ),
    provenance=_neurodragon_apparel_provenance("Iron Helmet"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_iron_helmet(
    context: object,
    parameters: HeadgearVariantParameters,
) -> Helmet:
    """Construct canonical recipe-parameterized Iron Helmet."""
    return _build_neurodragon_headgear(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Iron Helmet",
        description="A sturdy metal helmet.",
        armor_type=ArmorType.HEAVY,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.wizard_hat",
    version=1,
    parameters=HeadgearVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.wizard_hat",
        display_name="Wizard's Hat",
        description="A pointy cloth hat favored by arcane casters.",
        group="headgear",
        sort_order=20,
    ),
    provenance=_neurodragon_apparel_provenance("Wizard's Hat"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_wizard_hat(
    context: object,
    parameters: HeadgearVariantParameters,
) -> Helmet:
    """Construct canonical recipe-parameterized Wizard's Hat."""
    return _build_neurodragon_headgear(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Wizard's Hat",
        description="A pointy cloth hat favored by arcane casters.",
        armor_type=ArmorType.CLOTH,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.crown",
    version=1,
    parameters=HeadgearVariantParameters,
    descriptor=_neurodragon_apparel_descriptor(
        content_key="apparel.crown",
        display_name="Crown",
        description="A decorative crown.",
        group="headgear",
        sort_order=30,
    ),
    provenance=_neurodragon_apparel_provenance("Crown"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_crown(
    context: object,
    parameters: HeadgearVariantParameters,
) -> Helmet:
    """Construct canonical recipe-parameterized Crown."""
    return _build_neurodragon_headgear(
        ItemBuildContext.model_validate(context),
        parameters,
        name="Crown",
        description="A decorative crown.",
        armor_type=ArmorType.CLOTH,
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="shield.shield",
    version=1,
    parameters=SrdArmorParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Shield",
        description="A wooden or metal shield.",
        tags=("armor", "shield", "srd"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="shield.shield",
            visual_variant_key="shield",
            ui_group="armor.shields",
        ),
        ordering=ContentOrdering(
            sort_group="armor.shields",
            sort_order=10,
        ),
    ),
    provenance=_armor_provenance("Shield"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_shield(
    context: object,
    parameters: SrdArmorParameters,
) -> Shield:
    """Construct the canonical SRD shield."""
    item_context = ItemBuildContext.model_validate(context)
    return Shield(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name=parameters.display_name or "Shield",
        visual_item_name=(
            "Shield" if parameters.visual_variant_id is not None else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description="A wooden or metal shield.",
        ac_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=2,
            value_name="Shield AC Bonus",
        ),
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="shield.wooden",
    version=1,
    parameters=WoodenShieldVariantParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Wooden Shield",
        description="A crude wooden shield.",
        tags=("armor", "neurodragon", "shield"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="shield.wooden",
            visual_variant_key="wooden_shield",
            ui_group="armor.shields",
        ),
        ordering=ContentOrdering(
            sort_group="armor.shields",
            sort_order=20,
        ),
    ),
    provenance=_neurodragon_apparel_provenance("Wooden Shield"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_wooden_shield(
    context: object,
    parameters: WoodenShieldVariantParameters,
) -> Shield:
    """Construct the canonical NeuroDragon wooden shield."""
    item_context = ItemBuildContext.model_validate(context)
    return Shield(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name=parameters.display_name or "Wooden Shield",
        visual_item_name=(
            "Wooden Shield"
            if parameters.visual_variant_id is not None
            else None
        ),
        visual_variant_id=parameters.visual_variant_id,
        description="A crude wooden shield.",
        ac_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=2,
            value_name="Shield AC Bonus",
        ),
    )


PADDED_ARMOR_DECLARATION = get_content_declaration(_build_padded_armor)
LEATHER_ARMOR_DECLARATION = get_content_declaration(_build_leather_armor)
STUDDED_LEATHER_DECLARATION = get_content_declaration(_build_studded_leather)
HIDE_ARMOR_DECLARATION = get_content_declaration(_build_hide_armor)
CHAIN_SHIRT_DECLARATION = get_content_declaration(_build_chain_shirt)
SCALE_MAIL_DECLARATION = get_content_declaration(_build_scale_mail)
BREASTPLATE_DECLARATION = get_content_declaration(_build_breastplate)
HALF_PLATE_DECLARATION = get_content_declaration(_build_half_plate)
RING_MAIL_DECLARATION = get_content_declaration(_build_ring_mail)
CHAIN_MAIL_DECLARATION = get_content_declaration(_build_chain_mail)
SPLINT_ARMOR_DECLARATION = get_content_declaration(_build_splint_armor)
PLATE_ARMOR_DECLARATION = get_content_declaration(_build_plate_armor)
SHIELD_DECLARATION = get_content_declaration(_build_shield)

PADDED_ARMOR_REF = PADDED_ARMOR_DECLARATION.ref
LEATHER_ARMOR_REF = LEATHER_ARMOR_DECLARATION.ref
STUDDED_LEATHER_REF = STUDDED_LEATHER_DECLARATION.ref
HIDE_ARMOR_REF = HIDE_ARMOR_DECLARATION.ref
CHAIN_SHIRT_REF = CHAIN_SHIRT_DECLARATION.ref
SCALE_MAIL_REF = SCALE_MAIL_DECLARATION.ref
BREASTPLATE_REF = BREASTPLATE_DECLARATION.ref
HALF_PLATE_REF = HALF_PLATE_DECLARATION.ref
RING_MAIL_REF = RING_MAIL_DECLARATION.ref
CHAIN_MAIL_REF = CHAIN_MAIL_DECLARATION.ref
SPLINT_ARMOR_REF = SPLINT_ARMOR_DECLARATION.ref
PLATE_ARMOR_REF = PLATE_ARMOR_DECLARATION.ref
SHIELD_REF = SHIELD_DECLARATION.ref

PADDED_ARMOR_RECIPE = ContentRecipe.create(
    ref=PADDED_ARMOR_REF,
    parameters={},
)
LEATHER_ARMOR_RECIPE = ContentRecipe.create(
    ref=LEATHER_ARMOR_REF,
    parameters={},
)
STUDDED_LEATHER_RECIPE = ContentRecipe.create(
    ref=STUDDED_LEATHER_REF,
    parameters={},
)
HIDE_ARMOR_RECIPE = ContentRecipe.create(
    ref=HIDE_ARMOR_REF,
    parameters={},
)
CHAIN_SHIRT_RECIPE = ContentRecipe.create(
    ref=CHAIN_SHIRT_REF,
    parameters={},
)
SCALE_MAIL_RECIPE = ContentRecipe.create(
    ref=SCALE_MAIL_REF,
    parameters={},
)
BREASTPLATE_RECIPE = ContentRecipe.create(
    ref=BREASTPLATE_REF,
    parameters={},
)
HALF_PLATE_RECIPE = ContentRecipe.create(
    ref=HALF_PLATE_REF,
    parameters={},
)
RING_MAIL_RECIPE = ContentRecipe.create(
    ref=RING_MAIL_REF,
    parameters={},
)
CHAIN_MAIL_RECIPE = ContentRecipe.create(
    ref=CHAIN_MAIL_REF,
    parameters={},
)
SPLINT_ARMOR_RECIPE = ContentRecipe.create(
    ref=SPLINT_ARMOR_REF,
    parameters={},
)
PLATE_ARMOR_RECIPE = ContentRecipe.create(
    ref=PLATE_ARMOR_REF,
    parameters={},
)
SHIELD_RECIPE = ContentRecipe.create(
    ref=SHIELD_REF,
    parameters={},
)

SRD_ARMOR_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    PADDED_ARMOR_DECLARATION,
    LEATHER_ARMOR_DECLARATION,
    STUDDED_LEATHER_DECLARATION,
    HIDE_ARMOR_DECLARATION,
    CHAIN_SHIRT_DECLARATION,
    SCALE_MAIL_DECLARATION,
    BREASTPLATE_DECLARATION,
    HALF_PLATE_DECLARATION,
    RING_MAIL_DECLARATION,
    CHAIN_MAIL_DECLARATION,
    SPLINT_ARMOR_DECLARATION,
    PLATE_ARMOR_DECLARATION,
    SHIELD_DECLARATION,
)

def _default_recipe(
    definition: object,
) -> tuple[ContentDeclaration, ContentRecipe]:
    """Return one declaration and its empty-parameter default recipe."""
    declaration = get_content_declaration(definition)
    return (
        declaration,
        ContentRecipe.create(ref=declaration.ref, parameters={}),
    )


CLOTH_ARMOR_DECLARATION, CLOTH_ARMOR_RECIPE = _default_recipe(
    _build_cloth_armor,
)
CLOTH_ARMOR_REF = CLOTH_ARMOR_DECLARATION.ref
COMMON_CLOTHES_DECLARATION, COMMON_CLOTHES_RECIPE = _default_recipe(
    _build_common_clothes,
)
COMMON_CLOTHES_REF = COMMON_CLOTHES_DECLARATION.ref
FINE_CLOTHES_DECLARATION, FINE_CLOTHES_RECIPE = _default_recipe(
    _build_fine_clothes,
)
FINE_CLOTHES_REF = FINE_CLOTHES_DECLARATION.ref
TRAVELERS_CLOTHES_DECLARATION, TRAVELERS_CLOTHES_RECIPE = _default_recipe(
    _build_travelers_clothes,
)
TRAVELERS_CLOTHES_REF = TRAVELERS_CLOTHES_DECLARATION.ref
COSTUME_DECLARATION, COSTUME_RECIPE = _default_recipe(_build_costume)
COSTUME_REF = COSTUME_DECLARATION.ref
ROBES_DECLARATION, ROBES_RECIPE = _default_recipe(_build_robes)
ROBES_REF = ROBES_DECLARATION.ref
CLOTH_SHOES_DECLARATION, CLOTH_SHOES_RECIPE = _default_recipe(
    _build_cloth_shoes,
)
CLOTH_SHOES_REF = CLOTH_SHOES_DECLARATION.ref
LEATHER_BOOTS_DECLARATION, LEATHER_BOOTS_RECIPE = _default_recipe(
    _build_leather_boots,
)
LEATHER_BOOTS_REF = LEATHER_BOOTS_DECLARATION.ref
SANDALS_DECLARATION, SANDALS_RECIPE = _default_recipe(_build_sandals)
SANDALS_REF = SANDALS_DECLARATION.ref
LEATHER_SHOES_DECLARATION, LEATHER_SHOES_RECIPE = _default_recipe(
    _build_leather_shoes,
)
LEATHER_SHOES_REF = LEATHER_SHOES_DECLARATION.ref
ARMORED_BOOTS_DECLARATION, ARMORED_BOOTS_RECIPE = _default_recipe(
    _build_armored_boots,
)
ARMORED_BOOTS_REF = ARMORED_BOOTS_DECLARATION.ref
IRON_HELMET_DECLARATION, IRON_HELMET_RECIPE = _default_recipe(
    _build_iron_helmet,
)
IRON_HELMET_REF = IRON_HELMET_DECLARATION.ref
WIZARD_HAT_DECLARATION, WIZARD_HAT_RECIPE = _default_recipe(
    _build_wizard_hat,
)
WIZARD_HAT_REF = WIZARD_HAT_DECLARATION.ref
CROWN_DECLARATION, CROWN_RECIPE = _default_recipe(_build_crown)
CROWN_REF = CROWN_DECLARATION.ref


@item_factory(
    pack_id="content.neurodragon",
    content_id="apparel.spellblade_crown",
    version=1,
    parameters=NeurodragonStaticItemParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Spellblade Crown",
        description=(
            "An arcane crown granting +3 Charisma score while equipped."
        ),
        tags=("apparel", "headgear", "magic", "neurodragon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=CROWN_DECLARATION.descriptor.presentation,
        ordering=ContentOrdering(
            sort_group="apparel.headgear",
            sort_order=31,
        ),
    ),
    provenance=_neurodragon_apparel_provenance("Spellblade Crown"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
)
def _build_spellblade_crown(
    context: object,
    parameters: NeurodragonStaticItemParameters,
) -> SpellbladeCrown:
    """Construct the exact reversible spellblade premade head item."""
    _ = parameters
    item_context = ItemBuildContext.model_validate(context)
    return SpellbladeCrown(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Spellblade Crown",
        visual_item_name="Crown",
        description=(
            "An arcane crown granting +3 Charisma score while equipped."
        ),
        type=ArmorType.CLOTH,
        body_part=BodyPart.HEAD,
        ac=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=0,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=item_context.source_entity_uuid,
            base_value=10,
            value_name="Max Dex Bonus",
        ),
    )


(
    SPELLBLADE_CROWN_DECLARATION,
    SPELLBLADE_CROWN_RECIPE,
) = _default_recipe(_build_spellblade_crown)
SPELLBLADE_CROWN_REF = SPELLBLADE_CROWN_DECLARATION.ref

CLOTH_HOOD_DECLARATION, CLOTH_HOOD_RECIPE = _default_recipe(
    _build_cloth_hood,
)
CLOTH_HOOD_REF = CLOTH_HOOD_DECLARATION.ref
LEATHER_HOOD_DECLARATION, LEATHER_HOOD_RECIPE = _default_recipe(
    _build_leather_hood,
)
LEATHER_HOOD_REF = LEATHER_HOOD_DECLARATION.ref
CHAIN_COIF_DECLARATION, CHAIN_COIF_RECIPE = _default_recipe(
    _build_chain_coif,
)
CHAIN_COIF_REF = CHAIN_COIF_DECLARATION.ref
HORNED_HELMET_DECLARATION, HORNED_HELMET_RECIPE = _default_recipe(
    _build_horned_helmet,
)
HORNED_HELMET_REF = HORNED_HELMET_DECLARATION.ref
GREAT_HELM_DECLARATION, GREAT_HELM_RECIPE = _default_recipe(
    _build_great_helm,
)
GREAT_HELM_REF = GREAT_HELM_DECLARATION.ref
MONSTER_HELM_DECLARATION, MONSTER_HELM_RECIPE = _default_recipe(
    _build_monster_helm,
)
MONSTER_HELM_REF = MONSTER_HELM_DECLARATION.ref
BRACERS_DECLARATION, BRACERS_RECIPE = _default_recipe(_build_bracers)
BRACERS_REF = BRACERS_DECLARATION.ref
LEATHER_GLOVES_DECLARATION, LEATHER_GLOVES_RECIPE = _default_recipe(
    _build_leather_gloves,
)
LEATHER_GLOVES_REF = LEATHER_GLOVES_DECLARATION.ref
GAUNTLETS_DECLARATION, GAUNTLETS_RECIPE = _default_recipe(_build_gauntlets)
GAUNTLETS_REF = GAUNTLETS_DECLARATION.ref
MONSTER_HANDS_DECLARATION, MONSTER_HANDS_RECIPE = _default_recipe(
    _build_monster_hands,
)
MONSTER_HANDS_REF = MONSTER_HANDS_DECLARATION.ref
WOODEN_SHIELD_DECLARATION, WOODEN_SHIELD_RECIPE = _default_recipe(
    _build_wooden_shield,
)
WOODEN_SHIELD_REF = WOODEN_SHIELD_DECLARATION.ref

NEURODRAGON_ARMOR_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    CLOTH_ARMOR_DECLARATION,
    COMMON_CLOTHES_DECLARATION,
    FINE_CLOTHES_DECLARATION,
    TRAVELERS_CLOTHES_DECLARATION,
    COSTUME_DECLARATION,
    ROBES_DECLARATION,
    CLOTH_SHOES_DECLARATION,
    LEATHER_BOOTS_DECLARATION,
    SANDALS_DECLARATION,
    LEATHER_SHOES_DECLARATION,
    ARMORED_BOOTS_DECLARATION,
    IRON_HELMET_DECLARATION,
    WIZARD_HAT_DECLARATION,
    CROWN_DECLARATION,
    SPELLBLADE_CROWN_DECLARATION,
    CLOTH_HOOD_DECLARATION,
    LEATHER_HOOD_DECLARATION,
    CHAIN_COIF_DECLARATION,
    HORNED_HELMET_DECLARATION,
    GREAT_HELM_DECLARATION,
    MONSTER_HELM_DECLARATION,
    BRACERS_DECLARATION,
    LEATHER_GLOVES_DECLARATION,
    GAUNTLETS_DECLARATION,
    MONSTER_HANDS_DECLARATION,
    WOODEN_SHIELD_DECLARATION,
)
