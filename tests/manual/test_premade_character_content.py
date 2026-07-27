"""Canonical content-backed contracts for the approved schema-2 premades."""

from __future__ import annotations

import inspect
from collections import Counter
from collections.abc import Iterator
from types import MappingProxyType
from uuid import uuid4

import pytest

import dnd.content_system.creature_materialization as creature_materialization
import dnd.premade_characters as premade_characters
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    starter_holdings_for_build,
)
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.entity import Entity
from dnd.premade_characters import (
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID,
    BARBARIAN_L5_BERSERKER_TORCH_RECIPE,
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID,
    FIGHTER_L5_SHIELD_TORCH_RECIPE,
    FIGHTER_2_SORCERER_3_SPELLBLADE_PREMADE_ID,
    NEURODRAGON_PREMADE_CREATURE_DECLARATIONS,
    PREMADE_CHARACTER_BUILDS,
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID,
    SORCERER_L5_STANDARD_TORCH_RECIPE,
)
from dnd.runtime_reset import reset_engine_runtime


EXPECTED_PREMADE_IDS = (
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID,
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID,
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID,
    FIGHTER_2_SORCERER_3_SPELLBLADE_PREMADE_ID,
)
EXPECTED_CREATURE_ROOT_PREMADE_IDS = EXPECTED_PREMADE_IDS[:3]
_RECIPE_BY_PREMADE_ID = MappingProxyType({
    BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID: (
        BARBARIAN_L5_BERSERKER_TORCH_RECIPE
    ),
    FIGHTER_L5_SHIELD_TORCH_PREMADE_ID: (
        FIGHTER_L5_SHIELD_TORCH_RECIPE
    ),
    SORCERER_L5_STANDARD_TORCH_PREMADE_ID: (
        SORCERER_L5_STANDARD_TORCH_RECIPE
    ),
})


@pytest.fixture(scope="module", autouse=True)
def _install_frozen_content_system() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())


@pytest.fixture(autouse=True)
def _reset_runtime_state() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _runtime_holdings(
    entity: Entity,
) -> Counter[tuple[str, str | None, int]]:
    rows: Counter[tuple[str, str | None, int]] = Counter()
    for item in entity.equipment.get_all_equipped_items():
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        rows[(
            binding.recipe.recipe_digest,
            item.equipped_slot,
            item.stack_count,
        )] += 1
    for item in entity.inventory.items.values():
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        rows[(binding.recipe.recipe_digest, None, item.stack_count)] += 1
    return rows


def _authored_holdings(
    premade_id: str,
) -> Counter[tuple[str, str | None, int]]:
    return Counter(
        (
            holding.recipe.recipe_digest,
            (
                holding.equipped_slot.value
                if holding.equipped_slot is not None
                else None
            ),
            holding.quantity,
        )
        for holding in starter_holdings_for_build(
            PREMADE_CHARACTER_BUILDS[premade_id],
        )
    )


def _materialize(
    premade_id: str,
    possession_mode: CreaturePossessionMode,
) -> Entity:
    return materialize_creature(
        _RECIPE_BY_PREMADE_ID[premade_id],
        runtime_entity_uuid=uuid4(),
        display_name="Stored Character Name",
        faction="player_characters",
        position=(3, 4),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.premade.{premade_id}",
        ),
        possession_mode=possession_mode,
    )


def test_premade_catalog_roots_are_exact_schema2_build_aliases() -> None:
    """Public premade roots keep identity without owning another class path."""

    assert isinstance(PREMADE_CHARACTER_BUILDS, MappingProxyType)
    assert tuple(PREMADE_CHARACTER_BUILDS) == EXPECTED_PREMADE_IDS
    assert len(NEURODRAGON_PREMADE_CREATURE_DECLARATIONS) == 3
    for premade_id, declaration in zip(
        EXPECTED_CREATURE_ROOT_PREMADE_IDS,
        NEURODRAGON_PREMADE_CREATURE_DECLARATIONS,
        strict=True,
    ):
        build = PREMADE_CHARACTER_BUILDS[premade_id]
        assert build.premade_id == premade_id
        assert build.level == 5
        assert declaration.ref.definition_kind is ContentDefinitionKind.CREATURE
        assert declaration.descriptor.visibility.value == "public"
        assert "premade" in declaration.descriptor.tags
    assert all(
        build.level == 5
        for build in PREMADE_CHARACTER_BUILDS.values()
    )


@pytest.mark.parametrize(
    "premade_id",
    EXPECTED_CREATURE_ROOT_PREMADE_IDS,
)
@pytest.mark.parametrize(
    "possession_mode",
    tuple(CreaturePossessionMode),
)
def test_all_premades_use_one_schema2_materializer_and_exact_possessions(
    premade_id: str,
    possession_mode: CreaturePossessionMode,
) -> None:
    """Catalog aliases retain mechanics while possession mode remains exact."""

    entity = _materialize(premade_id, possession_mode)

    assert entity.uuid == entity.source_entity_uuid
    assert entity.name == "Stored Character Name"
    assert entity.faction == "player_characters"
    assert entity.position == (3, 4)
    assert entity.content_ref == _RECIPE_BY_PREMADE_ID[premade_id].ref
    assert entity.registered_actions
    if (
        possession_mode
        is CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ):
        assert _runtime_holdings(entity) == Counter()
    else:
        assert _runtime_holdings(entity) == _authored_holdings(premade_id)


def test_premade_materialization_has_no_legacy_preset_or_factory_lookup() -> None:
    """The alias layer delegates to schema 2 and never enters retired systems."""

    sources = (
        inspect.getsource(premade_characters),
        inspect.getsource(creature_materialization),
    )
    forbidden = (
        "PREMADE_CHARACTER_TEMPLATES",
        "combatant_catalog",
        "get_combatant_configuration",
        "HERO_CONFIGURATIONS",
        "barbarian_factory",
        "fighter_factory",
        "sorcerer_factory",
    )
    for source in sources:
        assert all(token not in source for token in forbidden)
