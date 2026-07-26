"""Canonical content-backed contracts for the three approved premades."""

from __future__ import annotations

import inspect
from collections import Counter
from types import MappingProxyType
from uuid import uuid4

import pytest

import dnd.content_system.creature_materialization as creature_materialization
import dnd.items.test_items as fixture_items
import dnd.items.torches as torches
import dnd.premade_characters as premade_characters
from dnd.blocks.base_item import EquippableItem
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.premade_characters import (
    PremadeCharacterTemplate,
    StarterHoldingTemplate,
)
from dnd.entity import Entity
from dnd.premade_characters import (
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID,
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID,
    NEURODRAGON_PREMADE_CREATURE_DECLARATIONS,
    PREMADE_CHARACTER_TEMPLATES,
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID,
)
from dnd.runtime_reset import reset_engine_runtime


EXPECTED_PREMADE_IDS = (
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID,
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID,
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID,
)
EXPECTED_TEMPLATE_DIGESTS = {
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID: (
        "8d3fd657f2c947d94f3e785d2e91af1a43712bc2639186548f2839c31525b920"
    ),
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID: (
        "bb7c46c3e28b73dd783e7ab8f09825a70c96a238b4348eda2ba64cc163fa92c7"
    ),
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID: (
        "a4a767c9e157f713d2b0d7cd2a3548592f4a84ebef4fadadc388c6604af59e27"
    ),
}


@pytest.fixture(scope="module", autouse=True)
def _install_frozen_content_system() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _materialize(
    template: PremadeCharacterTemplate,
    possession_mode: CreaturePossessionMode,
) -> Entity:
    return materialize_creature(
        template.creature_recipe,
        runtime_entity_uuid=uuid4(),
        display_name="Stored Character Name",
        faction="player_characters",
        position=(3, 4),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.premade.{template.premade_id}",
        ),
        possession_mode=possession_mode,
    )


def _template_holdings(
    template: PremadeCharacterTemplate,
) -> Counter[tuple[str, str | None]]:
    return Counter({
        (
            holding.recipe.recipe_digest,
            (
                holding.equipped_slot.value
                if holding.equipped_slot is not None
                else None
            ),
        ): holding.quantity
        for holding in template.starter_holdings
    })


def _runtime_holdings(
    entity: Entity,
) -> Counter[tuple[str, str | None]]:
    rows: Counter[tuple[str, str | None]] = Counter()
    for item in entity.equipment.get_all_equipped_items():
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        rows[(binding.recipe.recipe_digest, item.equipped_slot)] += (
            item.stack_count
        )
    for item in entity.inventory.items.values():
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        rows[(binding.recipe.recipe_digest, None)] += item.stack_count
    return rows


def _hydrate_exact_starter_holdings(
    entity: Entity,
    template: PremadeCharacterTemplate,
) -> None:
    """Exercise the persisted-holdings side of the structure-only boundary."""
    for holding in template.starter_holdings:
        item = materialize_item_from_installed_runtime(
            holding.recipe,
            entity.uuid,
            origin=ItemRuntimeOrigin.PERSISTED,
            character_item_id=uuid4(),
        )
        item.stack_count = holding.quantity
        if holding.equipped_slot is None:
            assert entity.loot_item(item)
            continue
        assert isinstance(item, EquippableItem)
        assert entity.equipment.equip(item, holding.equipped_slot)


def test_templates_are_exact_immutable_uuid_free_and_digest_stable() -> None:
    """Cold starter templates authenticate order without minting item IDs."""
    assert isinstance(PREMADE_CHARACTER_TEMPLATES, MappingProxyType)
    assert not hasattr(
        premade_characters,
        "PREMADE_CREATURE_RECIPES_BY_ID",
    )
    assert tuple(PREMADE_CHARACTER_TEMPLATES) == EXPECTED_PREMADE_IDS
    assert len(NEURODRAGON_PREMADE_CREATURE_DECLARATIONS) == 3

    for premade_id, template in PREMADE_CHARACTER_TEMPLATES.items():
        assert template.premade_id == premade_id
        assert template.template_digest == EXPECTED_TEMPLATE_DIGESTS[premade_id]
        assert (
            template.creature_recipe.ref.definition_kind
            == ContentDefinitionKind.CREATURE
        )
        assert set(StarterHoldingTemplate.model_fields) == {
            "recipe",
            "quantity",
            "equipped_slot",
        }
        assert "uuid" not in template.model_dump_json()
        template.verify_integrity()


def test_every_starter_item_recipe_resolves_as_a_possession() -> None:
    """Starter templates contain exact constructible possession recipes only."""
    registry = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry
    for template in PREMADE_CHARACTER_TEMPLATES.values():
        for holding in template.starter_holdings:
            declaration = registry.resolve_factory(holding.recipe.ref)
            assert declaration.item_definition is not None
            assert (
                declaration.item_definition.persistence_policy
                == ItemPersistencePolicy.POSSESSION
            )
            holding.recipe.verify_integrity()


@pytest.mark.parametrize(
    "premade_id",
    EXPECTED_PREMADE_IDS,
)
@pytest.mark.parametrize(
    "possession_mode",
    tuple(CreaturePossessionMode),
)
def test_all_three_recipes_materialize_both_possession_modes(
    premade_id: str,
    possession_mode: CreaturePossessionMode,
) -> None:
    """Context identity is exact and structure-only retains class mechanics."""
    template = PREMADE_CHARACTER_TEMPLATES[premade_id]
    entity = _materialize(template, possession_mode)
    actions = entity.get_available_actions()
    action_count = sum(
        len(rows)
        for rows in (
            actions.entity_actions,
            actions.position_actions,
            actions.self_actions,
            actions.object_actions,
        )
    )

    assert entity.uuid == entity.source_entity_uuid
    assert entity.name == "Stored Character Name"
    assert entity.faction == "player_characters"
    assert entity.position == (3, 4)
    assert entity.content_ref == template.creature_recipe.ref
    assert action_count > 0
    assert entity.active_conditions

    if (
        possession_mode
        == CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ):
        assert entity.equipment.get_all_equipped_items() == []
        assert entity.inventory.items == {}
    else:
        assert _runtime_holdings(entity) == _template_holdings(template)
        torch = entity.inventory.find_items_by_name("Torch")
        assert len(torch) == 1
        assert isinstance(torch[0], torches.Torch)
        assert torch[0].is_lit is True


@pytest.mark.parametrize("premade_id", EXPECTED_PREMADE_IDS)
def test_repeated_structure_only_deployments_hydrate_holdings_once(
    premade_id: str,
) -> None:
    """Two deployment cycles rebuild structure then hydrate one exact loadout."""
    template = PREMADE_CHARACTER_TEMPLATES[premade_id]
    for _ in range(2):
        entity = _materialize(
            template,
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
        )
        assert _runtime_holdings(entity) == Counter()
        _hydrate_exact_starter_holdings(entity, template)
        assert _runtime_holdings(entity) == _template_holdings(template)
        reset_engine_runtime(grid_size=(12, 12))


def test_portable_torch_has_one_canonical_recipe_and_no_legacy_constructor() -> None:
    """Portable torch creation crosses the canonical materializer only."""
    assert not hasattr(torches, "create_torch")
    assert not hasattr(fixture_items, "create_torch")
    assert not hasattr(fixture_items, "Torch")

    declaration = (
        SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.resolve_factory(
            torches.TORCH_RECIPE.ref,
        )
    )
    assert declaration == torches.TORCH_DECLARATION
    assert declaration.item_definition is not None
    assert declaration.item_definition.may_enter_character_holdings

    torch = materialize_item_from_installed_runtime(
        torches.TORCH_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=torches.Torch,
    )
    assert torch.content_ref == torches.TORCH_RECIPE.ref
    assert torch.is_lit is False


def test_premade_materialization_has_no_legacy_preset_lookup() -> None:
    """Canonical factories never resolve the old combatant catalog."""
    sources = (
        inspect.getsource(premade_characters),
        inspect.getsource(creature_materialization),
    )
    for source in sources:
        assert "combatant_catalog" not in source
        assert "get_combatant_configuration" not in source
        assert "HERO_CONFIGURATIONS" not in source
