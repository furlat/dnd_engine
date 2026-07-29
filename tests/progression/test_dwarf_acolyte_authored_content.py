"""Exact Dwarf training and Acolyte starting-possession closure."""

from typing import cast
from uuid import uuid4

from dnd.blocks.base_item import BaseItem
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.equipment import Weapon
from dnd.content_system.acolyte_starting_holdings import (
    ACOLYTE_STARTING_HOLDINGS_DECLARATION,
)
from dnd.content_system.background_starting_holdings import (
    background_starting_holdings,
)
from dnd.content_system.character_origin_definitions import (
    ACOLYTE_BACKGROUND_DECLARATION,
)
from dnd.content_system.origin_feature_definitions import (
    ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    _install_proficiency,
    remove_character_composition,
)
from dnd.content_system.origin_feature_definitions import (
    DWARF_COMBAT_TRAINING_DECLARATION,
)
from dnd.core.content.durable_characters import (
    BackgroundDefinition,
    ProficiencySubjectKind,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginStructuralFeatureDefinition,
)
from dnd.core.content.origin_support import OriginRuntimeSupportStatus
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import WeaponProperty
from dnd.items.acolyte_gear import (
    COMMON_CLOTHES_RECIPE,
    HOLY_SYMBOL_DECLARATION,
    HOLY_SYMBOL_RECIPE,
    INCENSE_DECLARATION,
    INCENSE_RECIPE,
    PRAYER_BOOK_DECLARATION,
    PRAYER_BOOK_RECIPE,
    VESTMENTS_RECIPE,
)
from dnd.items.weapons import (
    BATTLEAXE_REF,
    HANDAXE_REF,
    LIGHT_HAMMER_DECLARATION,
    LIGHT_HAMMER_REF,
    WARHAMMER_REF,
)
from dnd.entity import Entity, EntityConfig


def test_acolyte_background_authenticates_one_exact_starting_holdings_package(
) -> None:
    payload = ACOLYTE_BACKGROUND_DECLARATION.definition_payload
    assert isinstance(payload, BackgroundDefinition)
    assert (
        payload.starting_holdings_package_ref
        == ACOLYTE_STARTING_HOLDINGS_DECLARATION.ref
    )
    assert payload.runtime_support.status is OriginRuntimeSupportStatus.AVAILABLE
    assert (
        ACOLYTE_STARTING_HOLDINGS_DECLARATION.ref
        in ACOLYTE_BACKGROUND_DECLARATION.descriptor.related_content_refs
    )
    language_requirement = payload.choice_requirements[0]
    assert (
        language_requirement.choice_id
        == "background.acolyte.languages"
    )
    assert language_requirement.minimum_selections == 2
    assert language_requirement.maximum_selections == 2
    assert all(
        row.subject_kind is ProficiencySubjectKind.LANGUAGE
        for row in language_requirement.allowed_proficiency_subjects
    )
    shelter = (
        ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION.definition_payload
    )
    assert isinstance(shelter, OriginStructuralFeatureDefinition)
    assert shelter.capabilities == (
        OriginCapability.SHELTER_OF_THE_FAITHFUL,
    )


def test_acolyte_starting_holdings_are_exact_ordered_srd_possessions() -> None:
    payload = ACOLYTE_STARTING_HOLDINGS_DECLARATION.definition_payload
    assert isinstance(payload, StartingEquipmentPackageDefinition)

    assert tuple(
        (
            entry.recipe.recipe_digest,
            entry.quantity,
            entry.equipped_slot,
        )
        for entry in payload.entries
    ) == (
        (HOLY_SYMBOL_RECIPE.recipe_digest, 1, None),
        (PRAYER_BOOK_RECIPE.recipe_digest, 1, None),
        (INCENSE_RECIPE.recipe_digest, 5, None),
        (VESTMENTS_RECIPE.recipe_digest, 1, None),
        (COMMON_CLOTHES_RECIPE.recipe_digest, 1, None),
    )


def _materialize(declaration) -> BaseItem:
    construction = declaration.construction
    assert construction is not None
    return cast(
        BaseItem,
        construction.factory(
            ItemBuildContext(
                source_entity_uuid=uuid4(),
                requested_ref=declaration.ref,
            ),
            construction.parameter_model(),
        ),
    )


def test_new_srd_items_materialize_through_ordinary_registered_factories(
) -> None:
    light_hammer = _materialize(LIGHT_HAMMER_DECLARATION)
    assert isinstance(light_hammer, Weapon)
    assert light_hammer.content_ref == LIGHT_HAMMER_REF
    assert light_hammer.damage_dice == 4
    assert light_hammer.damage_type.value == "Bludgeoning"
    assert set(light_hammer.properties) == {
        WeaponProperty.LIGHT,
        WeaponProperty.THROWN,
    }

    holy_symbol = _materialize(HOLY_SYMBOL_DECLARATION)
    prayer_book = _materialize(PRAYER_BOOK_DECLARATION)
    incense = _materialize(INCENSE_DECLARATION)
    assert holy_symbol.content_ref == HOLY_SYMBOL_RECIPE.ref
    assert prayer_book.content_ref == PRAYER_BOOK_RECIPE.ref
    assert incense.content_ref == INCENSE_RECIPE.ref
    assert incense.stack_id == "srd_5_1.gear.incense"
    assert incense.max_stack == 20


def test_dwarf_weapon_training_materializes_and_reverses_all_exact_refs(
) -> None:
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
        ),
    )
    character_id = uuid4()
    payload = DWARF_COMBAT_TRAINING_DECLARATION.definition_payload
    assert isinstance(payload, OriginStructuralFeatureDefinition)
    receipts = tuple(
        _install_proficiency(
            entity=entity,
            character_id=character_id,
            token=f"dwarf.combat_training:{index}",
            subject=subject,
            definition_ref=DWARF_COMBAT_TRAINING_DECLARATION.ref,
        )
        for index, subject in enumerate(payload.automatic_proficiencies)
    )
    expected_refs = (
        BATTLEAXE_REF,
        HANDAXE_REF,
        LIGHT_HAMMER_REF,
        WARHAMMER_REF,
    )
    assert all(
        entity.creature_proficiencies.is_weapon_proficient((), ref)
        for ref in expected_refs
    )

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=character_id,
            grants=receipts,
            automatic_grant_refs=(
                DWARF_COMBAT_TRAINING_DECLARATION.ref,
            ),
        ),
    )
    assert all(
        not entity.creature_proficiencies.is_weapon_proficient((), ref)
        for ref in expected_refs
    )


class _AcolyteRegistry:
    def resolve_typed_definition(self, ref, expected_type):
        if ref == ACOLYTE_BACKGROUND_DECLARATION.ref:
            payload = ACOLYTE_BACKGROUND_DECLARATION.definition_payload
        elif ref == ACOLYTE_STARTING_HOLDINGS_DECLARATION.ref:
            payload = ACOLYTE_STARTING_HOLDINGS_DECLARATION.definition_payload
        else:
            raise AssertionError(ref)
        assert isinstance(payload, expected_type)
        return payload


def test_acolyte_background_package_materializes_into_durable_holdings() -> None:
    character_id = uuid4()
    holdings = background_starting_holdings(
        character_id=character_id,
        background_ref=ACOLYTE_BACKGROUND_DECLARATION.ref,
        registry=cast(FrozenContentRegistry, _AcolyteRegistry()),
    )

    assert {
        (
            row.recipe.recipe_digest,
            row.quantity,
            row.equipped_slot,
        )
        for row in holdings
    } == {
        (
            entry.recipe.recipe_digest,
            entry.quantity,
            entry.equipped_slot,
        )
        for entry in _acolyte_package().entries
    }


def _acolyte_package() -> StartingEquipmentPackageDefinition:
    payload = ACOLYTE_STARTING_HOLDINGS_DECLARATION.definition_payload
    assert isinstance(payload, StartingEquipmentPackageDefinition)
    return payload
