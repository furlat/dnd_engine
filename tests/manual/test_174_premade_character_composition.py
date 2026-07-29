"""Approved premades become exact durable character and holdings revisions."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    starter_holdings_for_build,
)
from dnd.core.content.durable_characters import (
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from server.character_directory_contracts import CreateCharacterRequest
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import (
    PrincipalCreate,
    PrincipalKind,
    PrincipalRecord,
)
from server.game_directory.repository import GameDirectoryRepository


PEPPER = b"premade-composition-test-pepper"

_APPEARANCE_BY_PREMADE = {
    "hero.barbarian_l5_berserker_torch": CharacterAppearanceSelection(
        options=(
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard",
                value_id="appearance.beard.absent",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard_tint",
                value_id="appearance.color.none",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.body",
                value_id="appearance.body.humanoid",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.build",
                value_id="appearance.build.broad",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.hair_tint",
                value_id="appearance.color.sand",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.head",
                value_id="appearance.head.hair_17",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.skin_tint",
                value_id="appearance.color.warm_tan",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.stature",
                value_id="appearance.stature.tall",
            ),
        ),
    ),
    "hero.fighter_l5_shield_torch": CharacterAppearanceSelection(
        options=(
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard",
                value_id="appearance.beard.present",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard_tint",
                value_id="appearance.color.auburn",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.body",
                value_id="appearance.body.humanoid",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.build",
                value_id="appearance.build.average",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.hair_tint",
                value_id="appearance.color.auburn",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.head",
                value_id="appearance.head.hair_10",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.skin_tint",
                value_id="appearance.color.light_tan",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.stature",
                value_id="appearance.stature.average",
            ),
        ),
    ),
    "hero.sorcerer_l5_standard_torch": CharacterAppearanceSelection(
        options=(
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard",
                value_id="appearance.beard.absent",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard_tint",
                value_id="appearance.color.none",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.body",
                value_id="appearance.body.humanoid",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.build",
                value_id="appearance.build.slender",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.hair_tint",
                value_id="appearance.color.auburn",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.head",
                value_id="appearance.head.hair_22",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.skin_tint",
                value_id="appearance.color.light_tan",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.stature",
                value_id="appearance.stature.short",
            ),
        ),
    ),
}
_APPEARANCE_BY_PREMADE[
    "hero.fighter_2_sorcerer_3_spellblade"
] = _APPEARANCE_BY_PREMADE["hero.fighter_l5_shield_torch"]

_EQUIPPED_HEAD_ITEM_BY_PREMADE = {
    "hero.barbarian_l5_berserker_torch": None,
    "hero.fighter_l5_shield_torch": "Iron Helmet",
    "hero.sorcerer_l5_standard_torch": "Wizard's Hat",
    "hero.fighter_2_sorcerer_3_spellblade": "Spellblade Crown",
}


def _directory(
    database_path: Path,
) -> tuple[
    GameDirectoryRepository,
    CharacterDirectoryService,
    PrincipalRecord,
]:
    repository = GameDirectoryRepository(
        database_path,
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Premade Owner",
        ),
    )
    return (
        repository,
        CharacterDirectoryService(
            repository,
            bootstrap_content_system(),
        ),
        owner,
    )


def _request_for_premade(
    service: CharacterDirectoryService,
    *,
    owner_id: UUID,
    premade_id: str,
    display_name: str,
) -> CreateCharacterRequest:
    plan = next(
        row
        for row in service.build_creation_catalog().creation_plans
        if row.source_premade_id == premade_id
    )
    settings = service.ensure_profile_settings(owner_id)
    return CreateCharacterRequest(
        display_name=display_name,
        build=plan.build,
        loadout=plan.loadout,
        creation_plan_id=plan.plan_id,
        creation_plan_digest=plan.plan_digest,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )


@pytest.mark.parametrize("premade_id", tuple(BUILTIN_PREMADE_BUILDS))
def test_every_approved_premade_composes_exact_schema2_revision_one(
    tmp_path: Path,
    premade_id: str,
) -> None:
    """All starter rows are exact durable possession recipes, never live state."""

    repository, service, owner = _directory(
        tmp_path / f"{premade_id}.sqlite3",
    )
    request = _request_for_premade(
        service,
        owner_id=owner.principal_id,
        premade_id=premade_id,
        display_name="Persistent Hero",
    )
    first = service.create_character(owner.principal_id, request)
    second = service.create_character(owner.principal_id, request)

    build = BUILTIN_PREMADE_BUILDS[premade_id]
    definition = first.definition.definition
    holdings = first.holdings.holdings
    loadout = first.loadout.loadout
    assert first == second
    assert definition.schema_version == 2
    assert definition.body_recipe == PLAYER_CHARACTER_BODY_RECIPE
    assert definition.premade_id == premade_id
    assert (
        definition.content_set_digest
        == service.content_system.content_set_digest
    )
    assert definition.definition_revision == 1
    assert definition.earned_character_level == build.level
    assert definition.appearance == _APPEARANCE_BY_PREMADE[premade_id]
    assert len(definition.class_levels) == build.level
    assert holdings.holdings_revision == 1
    assert len(holdings.items) == len(
        starter_holdings_for_build(build),
    )
    assert loadout.based_on_definition_revision == 1
    assert tuple(
        award.level_delta for award in first.advancement.awards
    ) == (build.level,)
    assert tuple(
        item.character_item_id for item in holdings.items
    ) == tuple(
        sorted(
            (
                item.character_item_id
                for item in holdings.items
            ),
            key=lambda item_id: item_id.hex,
        ),
    )
    assert len({
        item.character_item_id
        for item in holdings.items
    }) == len(holdings.items)
    equipped_head = tuple(
        item
        for item in holdings.items
        if item.equipped_slot == "Head"
    )
    expected_head_name = _EQUIPPED_HEAD_ITEM_BY_PREMADE[premade_id]
    if expected_head_name is None:
        assert equipped_head == ()
    else:
        assert len(equipped_head) == 1
        head_declaration = service.content_system.registry.resolve_factory(
            equipped_head[0].recipe.ref,
        )
        assert head_declaration.descriptor.display_name == expected_head_name
    for item in holdings.items:
        declaration = service.content_system.registry.resolve_factory(
            item.recipe.ref,
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )
    repository.close()


def test_character_identity_namespaces_deterministic_starter_item_ids(
    tmp_path: Path,
) -> None:
    """Two characters of one premade never share persistent item identities."""

    repository, service, owner = _directory(tmp_path / "identities.sqlite3")
    premade_id = next(iter(BUILTIN_PREMADE_BUILDS))
    first = service.create_character(
        owner.principal_id,
        _request_for_premade(
            service,
            owner_id=owner.principal_id,
            premade_id=premade_id,
            display_name="First",
        ),
    )
    second = service.create_character(
        owner.principal_id,
        _request_for_premade(
            service,
            owner_id=owner.principal_id,
            premade_id=premade_id,
            display_name="Second",
        ),
    )

    assert {
        item.character_item_id
        for item in first.holdings.holdings.items
    }.isdisjoint({
        item.character_item_id
        for item in second.holdings.holdings.items
    })
    repository.close()


def test_client_cannot_forge_premade_provenance(
    tmp_path: Path,
) -> None:
    """The authenticated creation plan, not a client field, owns provenance."""

    repository, service, owner = _directory(tmp_path / "unknown.sqlite3")
    known_id = next(iter(BUILTIN_PREMADE_BUILDS))
    known = _request_for_premade(
        service,
        owner_id=owner.principal_id,
        premade_id=known_id,
        display_name="Unknown",
    )
    request = known.model_copy(update={
        "build": known.build.model_copy(update={
            "premade_id": "hero.unknown",
        }),
    })

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid
    assert validation.normalized_build.premade_id == known_id
    created = service.create_character(owner.principal_id, request)
    assert created.definition.definition.premade_id == known_id
    repository.close()


def test_public_character_creation_is_schema2_draft_only() -> None:
    """The premade composer is not a second public character-creation API."""

    assert set(CreateCharacterRequest.model_fields) == {
        "display_name",
        "build",
        "loadout",
        "expected_content_set_digest",
        "expected_ruleset_digest",
        "creation_plan_id",
        "creation_plan_digest",
        "idempotency_key",
    }
    with pytest.raises(ValidationError):
        CreateCharacterRequest.model_validate(
            {
                "display_name": "Legacy",
                "premade_id": "hero.fighter_l5_shield_torch",
            },
        )
