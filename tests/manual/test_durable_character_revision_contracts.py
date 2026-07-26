"""Durable character and item revisions contain no encounter-runtime state."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import JsonValue, ValidationError

from dnd.core.content.durable_characters import (
    CharacterDefinitionRevision,
    CharacterHoldingsRevision,
    CharacterItemV1,
    ItemAugmentationRecord,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import WeaponSlot


_CHARACTER_ID = UUID("10000000-0000-0000-0000-000000000001")
_FIRST_ITEM_ID = UUID("20000000-0000-0000-0000-000000000001")
_SECOND_ITEM_ID = UUID("20000000-0000-0000-0000-000000000002")


def _ref(
    kind: ContentDefinitionKind,
    content_id: str,
    *,
    contract_hash: str = "a" * 64,
) -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=contract_hash,
    )


def _recipe(
    kind: ContentDefinitionKind,
    content_id: str,
    parameters: dict[str, JsonValue] | None = None,
) -> ContentRecipe:
    return ContentRecipe.create(
        ref=_ref(kind, content_id),
        parameters=parameters or {},
    )


def _augmentation() -> ItemAugmentationRecord:
    return ItemAugmentationRecord.create(
        content_ref=_ref(
            ContentDefinitionKind.TRAIT,
            "trait.permanent_keen_edge",
            contract_hash="b" * 64,
        ),
        parameters={"critical_threshold": 19},
        durable_state={"times_improved": 1},
    )


def _item(
    character_item_id: UUID,
    *,
    quantity: int = 1,
    equipped_slot: WeaponSlot | None = None,
) -> CharacterItemV1:
    return CharacterItemV1.create(
        character_item_id=character_item_id,
        recipe=_recipe(
            ContentDefinitionKind.ITEM,
            "item.club",
            {"material": "oak"},
        ),
        quantity=quantity,
        remaining_charges=3,
        durability_damage=2,
        durable_augmentations=(_augmentation(),),
        equipped_slot=equipped_slot,
    )


def _definition() -> CharacterDefinitionRevision:
    return CharacterDefinitionRevision.create(
        character_id=_CHARACTER_ID,
        schema_version=1,
        definition_revision=1,
        creature_recipe=_recipe(
            ContentDefinitionKind.CREATURE,
            "creature.premade_barbarian",
            {"level": 5, "ability_choices": ["strength", "constitution"]},
        ),
        premade_id="premade.barbarian",
        content_set_digest="c" * 64,
    )


def _holdings(
    items: tuple[CharacterItemV1, ...],
) -> CharacterHoldingsRevision:
    return CharacterHoldingsRevision.create(
        character_id=_CHARACTER_ID,
        schema_version=1,
        holdings_revision=1,
        items=items,
    )


def test_durable_contracts_round_trip_with_exact_canonical_digests() -> None:
    """Every durable layer is immutable, JSON-safe, and self-authenticating."""
    augmentation = _augmentation()
    item = _item(_FIRST_ITEM_ID, equipped_slot=WeaponSlot.MELEE_MAIN)
    definition = _definition()
    holdings = _holdings((item,))

    expected_digests = (
        (
            augmentation,
            "augmentation_digest",
            "e5c80c23c9eba7b6b9e6e604d4cb0d0eedf50abcd232aacd4cae95798b61089d",
        ),
        (
            item,
            "character_item_digest",
            "36b24fe4073c7b24cbba20ec1a3ca29a4ff899b1f9045fc4c3be9b6f74eab05f",
        ),
        (
            definition,
            "definition_digest",
            "3de01ea80d34d1a36728f6a156ca1420d2da3a250966f1701dac7e916b7dc94c",
        ),
        (
            holdings,
            "holdings_digest",
            "b0a2af2b238cf9e96b6374147e24d2d69a363a6bad0cf5b073afb49eb9b8a41e",
        ),
    )
    for model, digest_field, expected_digest in expected_digests:
        dumped = model.model_dump(mode="json")
        restored = type(model).model_validate(dumped)
        assert restored == model
        assert dumped[digest_field] == expected_digest

    with pytest.raises(ValidationError, match="frozen"):
        item.quantity = 2


@pytest.mark.parametrize(
    ("factory", "field", "replacement", "digest_name"),
    (
        (_augmentation, "durable_state", {"times_improved": 2}, "augmentation_digest"),
        (
            lambda: _item(_FIRST_ITEM_ID),
            "quantity",
            2,
            "character_item_digest",
        ),
        (_definition, "premade_id", "premade.fighter", "definition_digest"),
        (
            lambda: _holdings((_item(_FIRST_ITEM_ID),)),
            "items",
            [],
            "holdings_digest",
        ),
    ),
)
def test_each_durable_digest_rejects_tampering(
    factory,
    field: str,
    replacement: object,
    digest_name: str,
) -> None:
    """Changing authenticated durable data without its digest fails closed."""
    payload = factory().model_dump(mode="json")
    payload[field] = replacement

    with pytest.raises(ValidationError, match=digest_name):
        factory().__class__.model_validate(payload)


def test_holdings_require_unique_items_in_canonical_persistent_id_order() -> None:
    """Callers cannot make semantically equal holdings hash differently."""
    first = _item(_FIRST_ITEM_ID)
    second = _item(_SECOND_ITEM_ID)

    with pytest.raises(ValidationError, match="ordered"):
        _holdings((second, first))
    with pytest.raises(ValidationError, match="duplicate"):
        _holdings((first, first))


def test_item_augmentations_are_unique_and_canonically_ordered() -> None:
    """Equivalent permanent augmentations cannot produce different item hashes."""
    first = _augmentation()
    second = ItemAugmentationRecord.create(
        content_ref=_ref(
            ContentDefinitionKind.CONDITION,
            "condition.permanent_silvered",
            contract_hash="d" * 64,
        ),
        parameters={"applies_to": "weapon"},
        durable_state={},
    )
    ordered = tuple(
        sorted((first, second), key=lambda row: row.augmentation_digest),
    )
    recipe = _recipe(ContentDefinitionKind.ITEM, "item.club")

    CharacterItemV1.create(
        character_item_id=_FIRST_ITEM_ID,
        recipe=recipe,
        durable_augmentations=ordered,
    )
    with pytest.raises(ValidationError, match="ordered"):
        CharacterItemV1.create(
            character_item_id=_FIRST_ITEM_ID,
            recipe=recipe,
            durable_augmentations=tuple(reversed(ordered)),
        )
    with pytest.raises(ValidationError, match="duplicate"):
        CharacterItemV1.create(
            character_item_id=_FIRST_ITEM_ID,
            recipe=recipe,
            durable_augmentations=(first, first),
        )


def test_outer_digests_authenticate_valid_replacements_of_nested_records() -> None:
    """Re-hashing a child cannot make a stale parent digest authenticate it."""
    original_item = _item(_FIRST_ITEM_ID)
    changed_augmentation = ItemAugmentationRecord.create(
        content_ref=original_item.durable_augmentations[0].content_ref,
        parameters={"critical_threshold": 18},
        durable_state={"times_improved": 2},
    )
    changed_item = CharacterItemV1.create(
        character_item_id=original_item.character_item_id,
        recipe=original_item.recipe,
        quantity=original_item.quantity,
        remaining_charges=original_item.remaining_charges,
        durability_damage=original_item.durability_damage,
        durable_augmentations=(changed_augmentation,),
        equipped_slot=original_item.equipped_slot,
    )

    item_payload = original_item.model_dump(mode="json")
    item_payload["durable_augmentations"] = [
        changed_augmentation.model_dump(mode="json"),
    ]
    with pytest.raises(ValidationError, match="character_item_digest"):
        CharacterItemV1.model_validate(item_payload)

    holdings = _holdings((original_item,))
    holdings_payload = holdings.model_dump(mode="json")
    holdings_payload["items"] = [changed_item.model_dump(mode="json")]
    with pytest.raises(ValidationError, match="holdings_digest"):
        CharacterHoldingsRevision.model_validate(holdings_payload)


def test_item_state_validates_durable_bounds_and_one_selected_slot() -> None:
    """Quantities and mutable counters are bounded without storing footprints."""
    with pytest.raises(ValidationError):
        _item(_FIRST_ITEM_ID, quantity=0)

    payload = _item(_FIRST_ITEM_ID).model_dump(mode="json")
    payload["remaining_charges"] = -1
    with pytest.raises(ValidationError):
        CharacterItemV1.model_validate(payload)

    payload = _item(_FIRST_ITEM_ID).model_dump(mode="json")
    payload["durability_damage"] = -1
    with pytest.raises(ValidationError):
        CharacterItemV1.model_validate(payload)

    payload = _item(_FIRST_ITEM_ID).model_dump(mode="json")
    payload["equipped_slot"] = [
        WeaponSlot.MELEE_MAIN.value,
        WeaponSlot.MELEE_OFF.value,
    ]
    with pytest.raises(ValidationError):
        CharacterItemV1.model_validate(payload)


def test_recipes_are_restricted_to_their_durable_definition_family() -> None:
    """Structural definitions and possessions cannot exchange recipe kinds."""
    with pytest.raises(ValidationError, match="creature"):
        CharacterDefinitionRevision.create(
            character_id=_CHARACTER_ID,
            schema_version=1,
            definition_revision=1,
            creature_recipe=_recipe(
                ContentDefinitionKind.ITEM,
                "item.club",
            ),
            premade_id="premade.invalid",
            content_set_digest="c" * 64,
        )

    with pytest.raises(ValidationError, match="item"):
        CharacterItemV1.create(
            character_item_id=_FIRST_ITEM_ID,
            recipe=_recipe(
                ContentDefinitionKind.CREATURE,
                "creature.premade_barbarian",
            ),
        )


@pytest.mark.parametrize(
    ("factory", "ephemeral_field", "value"),
    (
        (_item, "runtime_item_uuid", "30000000-0000-0000-0000-000000000001"),
        (_item, "position", [4, 7]),
        (_item, "conditions", ["Poisoned"]),
        (_definition, "current_hp", 12),
        (_definition, "action_economy", {"actions": 0}),
        (
            lambda: _holdings((_item(_FIRST_ITEM_ID),)),
            "runtime_entity_uuid",
            "40000000-0000-0000-0000-000000000001",
        ),
    ),
)
def test_ephemeral_runtime_fields_are_rejected(
    factory,
    ephemeral_field: str,
    value: object,
) -> None:
    """No runtime UUID, position, condition, HP, or economy state can persist."""
    model = factory(_FIRST_ITEM_ID) if factory is _item else factory()
    payload = model.model_dump(mode="json")
    payload[ephemeral_field] = value

    with pytest.raises(ValidationError, match=ephemeral_field):
        type(model).model_validate(payload)
