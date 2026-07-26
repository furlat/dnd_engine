"""Scenario item augmentations consume the same canonical recipes as content."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.items.weapons import GREATAXE_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.evaluation.assembler import _grant_equipment, _grant_item
from dnd.scenarios.evaluation.models import EquipmentGrant, ItemGrant


def _actor() -> Entity:
    reset_engine_runtime(grid_size=(5, 5))
    return Entity.create(
        source_entity_uuid=uuid4(),
        name="Recipe Tester",
        config=EntityConfig(position=(1, 1), faction="testers"),
    )


def test_item_grant_rejects_the_retired_closed_item_id_contract() -> None:
    with pytest.raises(ValidationError):
        ItemGrant.model_validate({"item_id": "healing_potion"})


def test_generic_item_grant_materializes_any_installed_possession_recipe() -> None:
    actor = _actor()

    _grant_item(actor, ItemGrant(recipe=GREATAXE_RECIPE))

    granted = actor.inventory.find_items_by_name("Greataxe")
    assert len(granted) == 1
    assert granted[0].content_ref == GREATAXE_RECIPE.ref


def test_generic_equipment_grant_has_no_weapon_specific_dispatch() -> None:
    actor = _actor()

    _grant_equipment(
        actor,
        EquipmentGrant(
            recipe=GREATAXE_RECIPE,
            slot=WeaponSlot.MELEE_MAIN,
        ),
    )

    equipped = actor.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
    assert equipped is not None
    assert equipped.name == "Greataxe"
    assert equipped.content_ref == GREATAXE_RECIPE.ref


def test_torch_activation_is_explicit_typed_post_grant_behavior() -> None:
    actor = _actor()

    _grant_item(
        actor,
        ItemGrant(recipe=TORCH_RECIPE, on_grant="ignite"),
    )

    torches = actor.inventory.find_items_by_name("Torch")
    assert len(torches) == 1
    assert isinstance(torches[0], Torch)
    assert torches[0].is_lit


def test_serialized_grants_carry_exact_recipes_and_no_legacy_switch_keys() -> None:
    item_payload = ItemGrant(recipe=GREATAXE_RECIPE).model_dump(mode="json")
    equipment_payload = EquipmentGrant(
        recipe=GREATAXE_RECIPE,
        slot=WeaponSlot.MELEE_MAIN,
    ).model_dump(mode="json")

    assert item_payload["recipe"] == GREATAXE_RECIPE.model_dump(mode="json")
    assert equipment_payload["recipe"] == GREATAXE_RECIPE.model_dump(mode="json")
    for payload in (item_payload, equipment_payload):
        assert "item_id" not in payload
        assert "charges" not in payload
        assert "heal_amount" not in payload
