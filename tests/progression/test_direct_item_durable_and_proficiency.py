"""Public durable-item and exact-weapon-proficiency contracts."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.content.durable_characters import CharacterItemV2
from dnd.core.equipment_types import WeaponProperty
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime


def test_character_item_v2_rejects_tampering_legacy_recipe_and_augmentations_without_partial_state(
) -> None:
    """Durable direct items reject both tampering and retired construction data."""
    item = CharacterItemV2.create(
        character_item_id=UUID(int=1),
        item_id="weapon.longsword",
        quantity=1,
    )
    before = tuple(Entity.get_all_entities())

    tampered = item.model_dump(mode="json")
    tampered["quantity"] = 2
    with pytest.raises(ValidationError, match="does not authenticate"):
        CharacterItemV2.model_validate(tampered)

    for retired_field in ("recipe", "augmentations"):
        retired = item.model_dump(mode="json")
        retired[retired_field] = {}
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CharacterItemV2.model_validate(retired)

    assert tuple(Entity.get_all_entities()) == before


def test_character_item_v2_round_trip_authenticates_direct_state() -> None:
    """The durable record round-trips its direct identity and mutable item state."""
    item = CharacterItemV2.create(
        character_item_id=UUID(int=2),
        item_id="spell_item.wand_magic_missiles",
        quantity=1,
        remaining_charges=4,
        durability_damage=2,
    )

    restored = CharacterItemV2.model_validate_json(item.model_dump_json())

    assert restored == item
    assert restored.item_id == "spell_item.wand_magic_missiles"
    assert restored.remaining_charges == 4
    assert restored.durability_damage == 2
    restored.verify_integrity()


def test_specific_weapon_proficiency_uses_direct_item_ids_in_attacks_sources_and_birth_facts(
) -> None:
    """One direct weapon ID drives training, attack proficiency, and birth state."""
    reset_engine_runtime(grid_size=(3, 3))
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Longsword Specialist",
        config=EntityConfig(
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_weapon_ids=("weapon.longsword",),
            ),
        ),
    )
    longsword = build_authored_item("weapon.longsword", entity.uuid)
    rapier = build_authored_item("weapon.rapier", entity.uuid)

    assert entity.creature_proficiencies.is_weapon_proficient(
        longsword.properties,
        longsword.item_id,
    )
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
        rapier.item_id,
    )

    created = entity.compose_entity()
    assert created.weapon_proficiencies == ("weapon.longsword",)

