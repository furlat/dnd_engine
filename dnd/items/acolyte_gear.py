"""Exact mundane SRD possessions granted by the Acolyte background."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dnd.blocks.base_item import (
    BaseItem,
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
    item_factory,
)


class AcolyteGearParameters(BaseModel):
    """Empty reconstruction vocabulary for fixed mundane Acolyte gear."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_POSSESSION_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.POSSESSION,
)


def _descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=(
            "acolyte",
            "background_equipment",
            "gear",
            "srd",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=f"item.{content_id}",
            visual_variant_key=content_id,
            ui_group="items.adventuring_gear",
        ),
        ordering=ContentOrdering(
            sort_group="items.adventuring_gear",
            sort_order=sort_order,
        ),
    )


def _provenance(display_name: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 Backgrounds: Acolyte — Equipment: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact persistent mundane possession. Currency is intentionally "
            "not encoded as an item because the engine has no canonical "
            "durable currency owner."
        ),
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="gear.holy_symbol",
    version=1,
    parameters=AcolyteGearParameters,
    descriptor=_descriptor(
        content_id="holy-symbol",
        display_name="Holy Symbol",
        description="A devotional symbol used by an acolyte.",
        sort_order=10,
    ),
    provenance=_provenance("Holy Symbol"),
    item_definition=_POSSESSION_DEFINITION,
)
def _build_holy_symbol(
    context: object,
    parameters: AcolyteGearParameters,
) -> BaseItem:
    item_context = ItemBuildContext.model_validate(context)
    return BaseItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Holy Symbol",
        semantic_key="gear.holy_symbol",
        description="A devotional symbol used by an acolyte.",
        visual_item_name="Holy Symbol",
        tags=["acolyte", "holy_symbol", "religious"],
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="gear.prayer_book",
    version=1,
    parameters=AcolyteGearParameters,
    descriptor=_descriptor(
        content_id="prayer-book",
        display_name="Prayer Book",
        description="A book of prayers and devotional rites.",
        sort_order=20,
    ),
    provenance=_provenance("Prayer Book"),
    item_definition=_POSSESSION_DEFINITION,
)
def _build_prayer_book(
    context: object,
    parameters: AcolyteGearParameters,
) -> BaseItem:
    item_context = ItemBuildContext.model_validate(context)
    return BaseItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Prayer Book",
        semantic_key="gear.prayer_book",
        description="A book of prayers and devotional rites.",
        visual_item_name="Prayer Book",
        tags=["acolyte", "book", "religious"],
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="gear.incense",
    version=1,
    parameters=AcolyteGearParameters,
    descriptor=_descriptor(
        content_id="incense",
        display_name="Incense",
        description="A stick of incense used in religious observance.",
        sort_order=30,
    ),
    provenance=_provenance("5 sticks of incense"),
    item_definition=_POSSESSION_DEFINITION,
)
def _build_incense(
    context: object,
    parameters: AcolyteGearParameters,
) -> BaseItem:
    item_context = ItemBuildContext.model_validate(context)
    return BaseItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Incense",
        semantic_key="gear.incense",
        description="A stick of incense used in religious observance.",
        visual_item_name="Incense",
        stack_id="srd_5_1.gear.incense",
        max_stack=20,
        tags=["acolyte", "incense", "religious"],
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="gear.vestments",
    version=1,
    parameters=AcolyteGearParameters,
    descriptor=_descriptor(
        content_id="vestments",
        display_name="Vestments",
        description="Religious ceremonial clothing carried by an acolyte.",
        sort_order=40,
    ),
    provenance=_provenance("Vestments"),
    item_definition=_POSSESSION_DEFINITION,
)
def _build_vestments(
    context: object,
    parameters: AcolyteGearParameters,
) -> BaseItem:
    item_context = ItemBuildContext.model_validate(context)
    return BaseItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Vestments",
        semantic_key="gear.vestments",
        description="Religious ceremonial clothing carried by an acolyte.",
        visual_item_name="Vestments",
        tags=["acolyte", "clothes", "religious", "vestments"],
    )


@item_factory(
    pack_id="content.srd_5_1_cc",
    content_id="gear.common_clothes",
    version=1,
    parameters=AcolyteGearParameters,
    descriptor=_descriptor(
        content_id="common-clothes",
        display_name="Common Clothes",
        description="An ordinary set of common clothing.",
        sort_order=50,
    ),
    provenance=_provenance("Common clothes"),
    item_definition=_POSSESSION_DEFINITION,
)
def _build_common_clothes(
    context: object,
    parameters: AcolyteGearParameters,
) -> BaseItem:
    item_context = ItemBuildContext.model_validate(context)
    return BaseItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Common Clothes",
        semantic_key="gear.common_clothes",
        description="An ordinary set of common clothing.",
        visual_item_name="Common Clothes",
        tags=["acolyte", "clothes", "common"],
    )


def _declaration_and_recipe(
    factory,
) -> tuple[ContentDeclaration, ContentRecipe]:
    declaration = get_content_declaration(factory)
    return (
        declaration,
        ContentRecipe.create(ref=declaration.ref, parameters={}),
    )


HOLY_SYMBOL_DECLARATION, HOLY_SYMBOL_RECIPE = _declaration_and_recipe(
    _build_holy_symbol,
)
HOLY_SYMBOL_REF = HOLY_SYMBOL_DECLARATION.ref
PRAYER_BOOK_DECLARATION, PRAYER_BOOK_RECIPE = _declaration_and_recipe(
    _build_prayer_book,
)
PRAYER_BOOK_REF = PRAYER_BOOK_DECLARATION.ref
INCENSE_DECLARATION, INCENSE_RECIPE = _declaration_and_recipe(
    _build_incense,
)
INCENSE_REF = INCENSE_DECLARATION.ref
VESTMENTS_DECLARATION, VESTMENTS_RECIPE = _declaration_and_recipe(
    _build_vestments,
)
VESTMENTS_REF = VESTMENTS_DECLARATION.ref
COMMON_CLOTHES_DECLARATION, COMMON_CLOTHES_RECIPE = (
    _declaration_and_recipe(_build_common_clothes)
)
COMMON_CLOTHES_REF = COMMON_CLOTHES_DECLARATION.ref

SRD_ACOLYTE_GEAR_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    COMMON_CLOTHES_DECLARATION,
    HOLY_SYMBOL_DECLARATION,
    INCENSE_DECLARATION,
    PRAYER_BOOK_DECLARATION,
    VESTMENTS_DECLARATION,
)


__all__ = [
    "HOLY_SYMBOL_DECLARATION",
    "HOLY_SYMBOL_RECIPE",
    "HOLY_SYMBOL_REF",
    "INCENSE_DECLARATION",
    "INCENSE_RECIPE",
    "INCENSE_REF",
    "COMMON_CLOTHES_DECLARATION",
    "COMMON_CLOTHES_RECIPE",
    "COMMON_CLOTHES_REF",
    "PRAYER_BOOK_DECLARATION",
    "PRAYER_BOOK_RECIPE",
    "PRAYER_BOOK_REF",
    "SRD_ACOLYTE_GEAR_DECLARATIONS",
    "VESTMENTS_DECLARATION",
    "VESTMENTS_RECIPE",
    "VESTMENTS_REF",
]
