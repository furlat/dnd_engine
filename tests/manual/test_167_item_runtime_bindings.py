"""Runtime item bindings preserve recipes without polluting engine item models."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.blocks.equipment import Weapon
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.items.weapons import CLUB_RECIPE
from dnd.runtime_reset import reset_engine_runtime


def test_item_origin_is_validated_before_factory_materialization() -> None:
    """Possessions cannot masquerade as intrinsic or environment definitions."""
    runtime = ContentSystemRuntime()
    runtime.install(bootstrap_content_system())
    bindings = ItemRuntimeBindingRegistry()
    owner_uuid = uuid4()

    with pytest.raises(ValueError, match="incompatible"):
        materialize_item(
            CLUB_RECIPE,
            owner_uuid,
            origin=ItemRuntimeOrigin.INTRINSIC,
            expected_type=Weapon,
            binding_registry=bindings,
            runtime=runtime,
        )
    assert runtime.materialization_count == 0
    assert bindings.bindings == {}

    with pytest.raises(ValueError, match="requires character_item_id"):
        materialize_item(
            CLUB_RECIPE,
            owner_uuid,
            origin=ItemRuntimeOrigin.PERSISTED,
            expected_type=Weapon,
            binding_registry=bindings,
            runtime=runtime,
        )
    assert runtime.materialization_count == 0


def test_persisted_binding_owns_character_item_and_content_set_identity() -> None:
    """A deployment UUID is linked to, but never substituted for, durable identity."""
    runtime = ContentSystemRuntime()
    runtime.install(bootstrap_content_system())
    bindings = ItemRuntimeBindingRegistry()
    character_item_id = uuid4()

    item = materialize_item(
        CLUB_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.PERSISTED,
        expected_type=Weapon,
        character_item_id=character_item_id,
        binding_registry=bindings,
        runtime=runtime,
    )
    binding = bindings.require(item.uuid)

    assert binding.runtime_item_uuid == item.uuid
    assert binding.recipe == CLUB_RECIPE
    assert binding.character_item_id == character_item_id
    assert binding.content_set_digest == runtime.require().content_set_digest
    assert "character_item_id" not in item.model_dump()
    assert "recipe" not in item.model_dump()


def test_engine_reset_retires_deployment_bindings_but_not_content_registry() -> None:
    """A new game cannot observe stale UUID bindings from the prior generation."""
    reset_engine_runtime()
    item = materialize_item(
        CLUB_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert ITEM_RUNTIME_BINDINGS.require(item.uuid).recipe == CLUB_RECIPE

    reset_engine_runtime()

    with pytest.raises(KeyError, match="not bound"):
        ITEM_RUNTIME_BINDINGS.require(item.uuid)
