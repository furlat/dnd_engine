"""Durable characters reconstruct structure and possessions through one path."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
)
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
)
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterItemV1,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.equipment_types import BodyPart
from dnd.core.gridmap import get_map
from dnd.items.torches import Torch
from dnd.runtime_reset import reset_engine_runtime
from server.character_directory_contracts import CreateCharacterRequest
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import PrincipalCreate, PrincipalKind
from server.game_directory.repository import GameDirectoryRepository


PEPPER = b"character-runtime-materialization-pepper"

_RUNTIME_APPEARANCE_BY_PREMADE = {
    "hero.barbarian_l5_berserker_torch": (
        1.1,
        1.1,
        "NakedBody",
        0xD4AA78,
        "Head17",
        0xD0BFA1,
        False,
        0,
    ),
    "hero.fighter_l5_shield_torch": (
        1.0,
        1.0,
        "NakedBody",
        0xE6BC98,
        "Head10",
        0x993F00,
        True,
        0x993F00,
    ),
    "hero.sorcerer_l5_standard_torch": (
        0.9,
        0.9,
        "NakedBody",
        0xE6BC98,
        "Head22",
        0x993F00,
        False,
        0,
    ),
    "hero.fighter_2_sorcerer_3_spellblade": (
        1.0,
        1.0,
        "NakedBody",
        0xE6BC98,
        "Head10",
        0x993F00,
        True,
        0x993F00,
    ),
}


def _persisted_premade(
    database_path: Path,
    *,
    premade_id: str,
    display_name: str,
):
    repository = GameDirectoryRepository(
        database_path,
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Runtime Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )
    plan = next(
        row
        for row in service.build_creation_catalog().creation_plans
        if row.source_premade_id == premade_id
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    snapshot = service.create_character(
        owner.principal_id,
        CreateCharacterRequest(
            display_name=display_name,
            build=plan.build,
            loadout=plan.loadout,
            creation_plan_id=plan.plan_id,
            creation_plan_digest=plan.plan_digest,
            expected_content_set_digest=(
                service.content_system.content_set_digest
            ),
            expected_ruleset_digest=settings.ruleset_digest,
            idempotency_key=uuid4(),
        ),
    )
    return repository, snapshot


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    reset_engine_runtime(grid_size=(15, 15))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("premade_id", tuple(BUILTIN_PREMADE_BUILDS))
def test_premade_deployment_uses_only_persisted_holdings(
    tmp_path: Path,
    premade_id: str,
) -> None:
    """Structural factories cannot regenerate a second starter loadout."""

    repository, snapshot = _persisted_premade(
        tmp_path / f"{premade_id}.sqlite3",
        display_name="Durable Hero",
        premade_id=premade_id,
    )
    result = materialize_character(
        definition=snapshot.definition.definition,
        holdings=snapshot.holdings.holdings,
        loadout=snapshot.loadout.loadout,
        runtime_entity_uuid=uuid4(),
        display_name=snapshot.character.display_name,
        faction="heroes",
        position=(2, 3),
        deployment_role=CreatureDeploymentRole(
            role_id="hosted.side_a.character",
        ),
        expected_ruleset_digest=snapshot.definition.definition.ruleset_digest,
    )

    assert (
        result.entity.content_ref
        == snapshot.definition.definition.body_recipe.ref
    )
    assert result.entity.name == "Durable Hero"
    appearance = result.entity.appearance
    assert (
        appearance.visual_scale,
        appearance.visual_scale_x,
        appearance.body_category,
        appearance.skin_tint,
        appearance.head_category,
        appearance.hair_tint,
        appearance.has_beard,
        appearance.beard_tint,
    ) == _RUNTIME_APPEARANCE_BY_PREMADE[premade_id]
    assert len(result.item_lineage) == len(snapshot.holdings.holdings.items)
    assert {character_item_id for character_item_id, _ in result.item_lineage} == {
        item.character_item_id for item in snapshot.holdings.holdings.items
    }
    assert {
        binding.character_item_id
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
        if binding.character_item_id is not None
    } == {
        item.character_item_id for item in snapshot.holdings.holdings.items
    }
    assert all(
        binding.origin.value == "persisted"
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
    )
    torches = tuple(
        item
        for item in result.entity.inventory.items.values()
        if isinstance(item, Torch)
    )
    assert len(torches) == 1
    assert torches[0].is_lit
    assert torches[0]._light_source_uuid in get_map()._light_sources
    expected_head_name = {
        "hero.barbarian_l5_berserker_torch": None,
        "hero.fighter_l5_shield_torch": "Steel Helmet",
        "hero.sorcerer_l5_standard_torch": "Red Wizard Hat",
        "hero.fighter_2_sorcerer_3_spellblade": "Spellblade Crown",
    }[premade_id]
    helmet = result.entity.equipment.helmet
    assert (helmet.name if helmet is not None else None) == expected_head_name
    if premade_id == "hero.fighter_2_sorcerer_3_spellblade":
        assert helmet is not None
        charisma = result.entity.ability_scores.charisma.ability_score
        assert charisma.score == 18
        removed = result.entity.equipment.unequip(BodyPart.HEAD)
        assert removed is helmet
        assert charisma.score == 15
        assert result.entity.equipment.equip(helmet, BodyPart.HEAD)
        assert charisma.score == 18
    repository.close()


def test_every_persisted_starting_torch_is_lit(tmp_path: Path) -> None:
    """Every torch in the authoritative starting holdings emits light."""

    repository, snapshot = _persisted_premade(
        tmp_path / "multiple-starting-torches.sqlite3",
        display_name="Two Torch Hero",
        premade_id="hero.fighter_l5_shield_torch",
    )
    existing_torch = next(
        item
        for item in snapshot.holdings.holdings.items
        if item.recipe.ref.content_id == "equipment.portable_torch"
    )
    holdings = CharacterHoldingsRevision.create(
        character_id=snapshot.character.character_id,
        holdings_revision=snapshot.holdings.holdings.holdings_revision,
        items=tuple(
            sorted(
                (
                    *snapshot.holdings.holdings.items,
                    CharacterItemV1.create(
                        character_item_id=uuid4(),
                        recipe=existing_torch.recipe,
                    ),
                ),
                key=lambda item: item.character_item_id.hex,
            ),
        ),
    )

    result = materialize_character(
        definition=snapshot.definition.definition,
        holdings=holdings,
        loadout=snapshot.loadout.loadout,
        runtime_entity_uuid=uuid4(),
        display_name=snapshot.character.display_name,
        faction="heroes",
        position=(2, 3),
        deployment_role=CreatureDeploymentRole(
            role_id="hosted.side_a.character",
        ),
        expected_ruleset_digest=snapshot.definition.definition.ruleset_digest,
    )

    torches = tuple(
        item
        for item in result.entity.inventory.items.values()
        if isinstance(item, Torch)
    )
    assert len(torches) == 2
    assert all(torch.is_lit for torch in torches)
    assert all(
        torch._light_source_uuid in get_map()._light_sources
        for torch in torches
    )
    repository.close()


def test_worker_rejects_character_from_another_content_set(
    tmp_path: Path,
) -> None:
    """A stored definition cannot silently resolve under changed installed code."""

    repository, snapshot = _persisted_premade(
        tmp_path / "content-set.sqlite3",
        display_name="Pinned Hero",
        premade_id=next(iter(BUILTIN_PREMADE_BUILDS)),
    )
    original = snapshot.definition.definition
    assert isinstance(original, CharacterDefinitionRevisionV2)
    changed_definition = CharacterDefinitionRevisionV2.create(
        character_id=snapshot.character.character_id,
        definition_revision=1,
        body_recipe=original.body_recipe,
        species_ref=original.species_ref,
        species_variant_ref=original.species_variant_ref,
        background_ref=original.background_ref,
        immutable_origin_choices=original.immutable_origin_choices,
        appearance=original.appearance,
        base_ability_scores=original.base_ability_scores,
        flexible_ability_bonuses=original.flexible_ability_bonuses,
        class_levels=original.class_levels,
        premade_id=original.premade_id,
        earned_character_level=original.earned_character_level,
        content_set_digest="f" * 64,
        ruleset_digest=original.ruleset_digest,
    )

    with pytest.raises(ValueError, match="content set differs"):
        materialize_character(
            definition=changed_definition,
            holdings=snapshot.holdings.holdings,
            loadout=snapshot.loadout.loadout,
            runtime_entity_uuid=uuid4(),
            display_name="Pinned Hero",
            faction="heroes",
            position=(1, 1),
            deployment_role=CreatureDeploymentRole(
                role_id="hosted.side_a.character",
            ),
            expected_ruleset_digest=original.ruleset_digest,
        )
    repository.close()


def test_definition_and_holdings_character_identity_must_match(
    tmp_path: Path,
) -> None:
    """A valid revision from another character cannot be spliced into launch."""

    repository, first = _persisted_premade(
        tmp_path / "identity.sqlite3",
        display_name="First",
        premade_id=next(iter(BUILTIN_PREMADE_BUILDS)),
    )
    mismatched = CharacterHoldingsRevision.create(
        character_id=uuid4(),
        holdings_revision=1,
        items=(),
    )

    with pytest.raises(ValueError, match="different characters"):
        materialize_character(
            definition=first.definition.definition,
            holdings=mismatched,
            loadout=first.loadout.loadout,
            runtime_entity_uuid=uuid4(),
            display_name="First",
            faction="heroes",
            position=(1, 1),
            deployment_role=CreatureDeploymentRole(
                role_id="hosted.side_a.character",
            ),
            expected_ruleset_digest=first.definition.definition.ruleset_digest,
        )
    repository.close()
