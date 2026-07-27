"""Focused contracts for the canonical persistent-character directory surface."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    starter_holdings_for_build,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassSkillChoice,
    ClassLevelEntry,
    ClassLevelId,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe
from server.character_directory_contracts import (
    AdminCharacterAdvancementAwardRequest,
    CharacterBuildDraft,
    CharacterLevelUpRequest,
    CharacterLoadoutDraft,
    CharacterLoadoutMutationRequest,
    CharacterRespecRequest,
    CreateCharacterRequest,
)
from server.character_directory_service import (
    CharacterDirectoryOwnershipError,
    CharacterDirectoryService,
)
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    CharacterDeploymentLeaseCreate,
    GameCreate,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    PrincipalCreate,
    PrincipalKind,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_directory.errors import ConflictError, StaleVersionError
from server.game_gateway import create_gateway_app
from server.event_server import app as standalone_app


PEPPER = b"character-directory-service-pepper"


def _ref(kind: ContentDefinitionKind, content_id: str) -> ContentRef:
    return ContentRef(
        pack_id="fixture.character_directory",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def _recipe() -> ContentRecipe:
    return ContentRecipe.create(
        ref=_ref(ContentDefinitionKind.CREATURE, "creature.player_body"),
        parameters={},
    )


def _draft() -> CharacterBuildDraft:
    return CharacterBuildDraft(
        body_recipe=_recipe(),
        species_ref=_ref(ContentDefinitionKind.SPECIES, "species.human"),
        background_ref=_ref(
            ContentDefinitionKind.BACKGROUND,
            "background.soldier",
        ),
        appearance=CharacterAppearanceSelection(),
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="level.one"),
                character_level=1,
                class_ref=_ref(
                    ContentDefinitionKind.CLASS,
                    "class.fighter",
                ),
                resulting_class_level=1,
            ),
        ),
    )


def _seed_character(
    repository: GameDirectoryRepository,
    owner_id,
):
    character_id = uuid4()
    draft = _draft()
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=draft.body_recipe,
        species_ref=draft.species_ref,
        species_variant_ref=draft.species_variant_ref,
        background_ref=draft.background_ref,
        immutable_origin_choices=draft.immutable_origin_choices,
        appearance=draft.appearance,
        base_ability_scores=draft.base_ability_scores,
        flexible_ability_bonuses=draft.flexible_ability_bonuses,
        class_levels=draft.class_levels,
        earned_character_level=1,
        content_set_digest="b" * 64,
        premade_id="premade.fixture",
        ruleset_digest="c" * 64,
    )
    return repository.create_character_with_revisions(
        CharacterBootstrapCreate(
            character_id=character_id,
            owner_principal_id=owner_id,
            display_name="Stored Hero",
            definition=definition,
            starter_holdings=CharacterHoldingsRevision.create(
                character_id=character_id,
                holdings_revision=1,
            ),
            starter_loadout=CharacterLoadoutRevisionV1.create(
                character_id=character_id,
                loadout_revision=1,
                based_on_definition_revision=1,
            ),
            initial_advancement_award=CharacterAdvancementAwardCreate(
                character_id=character_id,
                level_delta=1,
                source_kind=CharacterAdvancementSourceKind.CREATION,
                source_id=f"character:{character_id}:creation",
            ),
        ),
    )


def _builtin_fighter_draft(
    service: CharacterDirectoryService,
) -> CharacterBuildDraft:
    catalog = service.build_creation_catalog()
    fighter = next(
        row for row in catalog.classes
        if row.ref.content_id == "class.fighter"
    )
    style_requirement = next(
        row
        for row in fighter.definition.level_definitions[0].choice_requirements
        if row.choice_id.endswith(".fighting_style")
    )
    package_requirement = next(
        row
        for row in fighter.definition.first_class_proficiencies.choices
        if row.choice_id.endswith(".starting_equipment")
    )
    skill_requirement = next(
        row
        for row in fighter.definition.first_class_proficiencies.choices
        if row.choice_id.endswith(".proficiencies.skills")
    )
    return CharacterBuildDraft(
        body_recipe=catalog.body_recipes[0],
        species_ref=next(
            row.ref for row in catalog.species
            if row.ref.content_id == "species.human"
        ),
        background_ref=next(
            row.ref for row in catalog.backgrounds
            if row.ref.content_id == "background.adventurer"
        ),
        appearance=CharacterAppearanceSelection(),
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="level.one"),
                character_level=1,
                class_ref=fighter.ref,
                resulting_class_level=1,
                choices=tuple(sorted(
                    (
                        FightingStyleChoice(
                            choice_id=style_requirement.choice_id,
                            selected_ref=style_requirement.allowed_refs[0],
                        ),
                        StartingEquipmentPackageChoice(
                            choice_id=package_requirement.choice_id,
                            selected_ref=package_requirement.allowed_refs[0],
                        ),
                        ClassSkillChoice(
                            choice_id=skill_requirement.choice_id,
                            skills=("athletics", "perception"),
                        ),
                    ),
                    key=lambda choice: choice.choice_id,
                )),
            ),
        ),
    )


def test_build_draft_is_strict_and_excludes_server_owned_revision_authority() -> None:
    """Clients submit authored selections, never UUID/revision/digest authority."""

    draft = _draft()
    assert draft.class_levels[0].character_level == 1
    for forbidden in (
        "character_id",
        "schema_version",
        "definition_revision",
        "earned_character_level",
        "content_set_digest",
        "ruleset_digest",
        "definition_digest",
    ):
        with pytest.raises(ValidationError):
            CharacterBuildDraft.model_validate(
                {**draft.model_dump(mode="json"), forbidden: "client-owned"},
            )

    with pytest.raises(ValidationError):
        CreateCharacterRequest.model_validate(
            {"display_name": "Legacy", "premade_id": "premade.fixture"},
        )


def test_service_reads_all_heads_and_enforces_owner_before_revision_access(
    tmp_path: Path,
) -> None:
    """One shared service owns character reads; transports provide identity."""

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    stranger = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Stranger",
        ),
    )
    character = _seed_character(repository, owner.principal_id)
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )

    snapshot = service.get_character_snapshot(
        owner.principal_id,
        character.character_id,
    )
    assert snapshot.character == character
    assert snapshot.definition.definition.definition_revision == 1
    assert snapshot.holdings.holdings.holdings_revision == 1
    assert snapshot.loadout.loadout.loadout_revision == 1
    assert snapshot.advancement.earned_character_level == 1

    history = service.get_definition_history(
        owner.principal_id,
        character.character_id,
    )
    assert tuple(
        row.definition.definition_revision for row in history.definitions
    ) == (1,)
    with pytest.raises(CharacterDirectoryOwnershipError):
        service.get_definition_history(
            stranger.principal_id,
            character.character_id,
        )
    repository.close()


def test_gateway_declares_one_unversioned_character_route_family() -> None:
    """OpenAPI contains one canonical route family and no premade/V2 aliases."""

    paths = create_gateway_app().openapi()["paths"]
    expected = {
        "/character-creation/catalog",
        "/character-builds/validate",
        "/directory/characters",
        "/directory/characters/{character_id}",
        "/directory/characters/{character_id}/definition",
        "/directory/characters/{character_id}/definitions",
        "/directory/characters/{character_id}/holdings",
        "/directory/characters/{character_id}/loadout",
        "/directory/players/me",
        "/directory/players/me/settings",
        "/directory/characters/{character_id}/advancement",
        "/directory/characters/{character_id}/level-up/validate",
        "/directory/characters/{character_id}/level-up",
        "/directory/characters/{character_id}/respec/validate",
        "/directory/characters/{character_id}/respec",
        "/directory/characters/{character_id}/loadout/validate",
        "/directory/characters/{character_id}/loadout",
    }
    assert expected <= set(paths)
    assert not any(
        "/v2" in path or "premade" in path
        for path in paths
        if "character" in path
    )


def test_gateway_and_standalone_mount_the_same_character_route_methods() -> None:
    gateway_paths = create_gateway_app().openapi()["paths"]
    standalone_paths = standalone_app.openapi()["paths"]
    character_paths = {
        path
        for path in gateway_paths
        if (
            path.startswith("/character-")
            or path.startswith("/directory/characters")
            or path.startswith("/directory/players/me")
        )
    }
    assert character_paths
    assert character_paths <= set(standalone_paths)
    for path in character_paths:
        assert set(gateway_paths[path]) == set(standalone_paths[path])

    admin_award_path = (
        "/admin/characters/{character_id}/advancement-awards"
    )
    assert admin_award_path in standalone_paths
    assert admin_award_path not in gateway_paths


def test_admin_award_grants_entitlement_without_choosing_the_level_up(
    tmp_path: Path,
) -> None:
    """Local administration grants authority; the player still spends it."""

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    stranger = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Stranger",
        ),
    )
    character = _seed_character(repository, owner.principal_id)
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    request = AdminCharacterAdvancementAwardRequest(
        idempotency_key=uuid4(),
        expected_earned_character_level=1,
        level_delta=1,
    )

    granted = service.grant_admin_advancement_award(
        owner.principal_id,
        character.character_id,
        request,
    )

    assert granted.earned_character_level == 2
    assert granted.awards[-1].source_kind is (
        CharacterAdvancementSourceKind.DEVELOPER
    )
    assert len(
        service.get_character_snapshot(
            owner.principal_id,
            character.character_id,
        ).definition.definition.class_levels,
    ) == 1
    assert (
        service.grant_admin_advancement_award(
            owner.principal_id,
            character.character_id,
            request,
        )
        == granted
    )
    with pytest.raises(StaleVersionError):
        service.grant_admin_advancement_award(
            owner.principal_id,
            character.character_id,
            request.model_copy(update={"idempotency_key": uuid4()}),
        )
    with pytest.raises(CharacterDirectoryOwnershipError):
        service.grant_admin_advancement_award(
            stranger.principal_id,
            character.character_id,
            request.model_copy(
                update={
                    "idempotency_key": uuid4(),
                    "expected_earned_character_level": 2,
                },
            ),
        )
    with pytest.raises(ConflictError, match="level 20"):
        service.grant_admin_advancement_award(
            owner.principal_id,
            character.character_id,
            AdminCharacterAdvancementAwardRequest(
                idempotency_key=uuid4(),
                expected_earned_character_level=2,
                level_delta=19,
            ),
        )
    repository.close()


def test_builtin_creator_catalog_has_exact_schema2_body_and_origin_choices(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    catalog = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    ).build_creation_catalog()
    assert tuple(
        recipe.ref.content_id for recipe in catalog.body_recipes
    ) == ("creature.player.humanoid_body",)
    human = next(
        row for row in catalog.species
        if row.ref.content_id == "species.human"
    )
    adventurer = next(
        row for row in catalog.backgrounds
        if row.ref.content_id == "background.adventurer"
    )
    assert human.implementation.status.value == "available"
    assert human.implementation.blocked_reason is None
    assert "player_capable" in human.descriptor.tags
    assert adventurer.implementation.status.value == "available"
    assert adventurer.implementation.blocked_reason is None
    assert "player_capable" in adventurer.descriptor.tags
    blocked_origins = (
        *(
            row
            for row in catalog.species
            if row.ref.content_id != "species.human"
        ),
        *catalog.species_variants,
        *(
            row
            for row in catalog.backgrounds
            if row.ref.content_id != "background.adventurer"
        ),
    )
    assert blocked_origins
    for row in blocked_origins:
        assert row.implementation.status.value == "blocked"
        assert row.implementation.blocked_reason
        assert "player_capable" not in row.descriptor.tags
    assert {"class.barbarian", "class.fighter", "class.sorcerer"} <= {
        row.ref.content_id for row in catalog.classes
    }
    assert catalog.rules.point_buy_budget == 27
    assert catalog.rules.maximum_pre_bonus_ability_score == 15
    assert catalog.rules.flexible_plus_two == 2
    assert catalog.rules.flexible_plus_one == 1
    assert tuple(row.premade_id for row in catalog.premades) == (
        "hero.barbarian_l5_berserker_torch",
        "hero.fighter_2_sorcerer_3_spellblade",
        "hero.fighter_l5_shield_torch",
        "hero.sorcerer_l5_standard_torch",
    )
    for premade in catalog.premades:
        premade.verify_integrity()
        assert premade.schema_version == 2
        assert premade.build.premade_id == premade.premade_id
        assert len(premade.build.class_levels) == 5
        with pytest.raises(ValidationError, match="does not authenticate"):
            type(premade).model_validate({
                **premade.model_dump(mode="json"),
                "premade_digest": "0" * 64,
            })
    assert (
        catalog.rules.default_multiclass_slot_rounding_policy.value
        == "srd_5_2_round_up"
    )
    repository.close()


def test_blocked_catalog_origins_are_visible_but_rejected_with_exact_path(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "blocked-origins.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    catalog = service.build_creation_catalog()
    settings = service.ensure_profile_settings(owner.principal_id)
    draft = _builtin_fighter_draft(service)
    blocked_rows = (
        (
            "species_ref",
            next(
                row.ref for row in catalog.species
                if row.ref.content_id == "species.dwarf"
            ),
        ),
        (
            "background_ref",
            next(
                row.ref for row in catalog.backgrounds
                if row.ref.content_id == "background.acolyte"
            ),
        ),
    )

    for field_name, blocked_ref in blocked_rows:
        blocked_build = draft.model_copy(
            update={field_name: blocked_ref},
        )
        validation = service.validate_new_character(
            owner.principal_id,
            CreateCharacterRequest(
                display_name="Blocked Origin",
                build=blocked_build,
                loadout=CharacterLoadoutDraft(),
                expected_content_set_digest=(
                    service.content_system.content_set_digest
                ),
                expected_ruleset_digest=settings.ruleset_digest,
                idempotency_key=uuid4(),
            ),
        )
        issue = next(
            issue
            for issue in validation.issues
            if issue.code.value == "origin_implementation_blocked"
        )
        assert issue.path == (field_name,)
        assert issue.content_refs == (blocked_ref,)
        assert issue.detail

    repository.close()


def test_canonical_premade_build_creates_one_level_five_character_with_curated_holdings(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    premade = next(
        row
        for row in service.build_creation_catalog().premades
        if row.premade_id == "hero.fighter_l5_shield_torch"
    )
    request = CreateCharacterRequest(
        display_name="Persistent Premade",
        build=premade.build,
        loadout=premade.loadout,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid, validation.issues
    created = service.create_character(owner.principal_id, request)
    replayed = service.create_character(owner.principal_id, request)

    assert replayed == created
    assert created.definition.definition.premade_id == premade.premade_id
    assert created.advancement.earned_character_level == 5
    expected_holdings = starter_holdings_for_build(
        BUILTIN_PREMADE_BUILDS[premade.premade_id],
    )
    assert {
        (item.recipe.recipe_digest, item.quantity, item.equipped_slot)
        for item in created.holdings.holdings.items
    } == {
        (holding.recipe.recipe_digest, holding.quantity, holding.equipped_slot)
        for holding in expected_holdings
    }

    mismatched_request = request.model_copy(update={
        "idempotency_key": uuid4(),
        "build": premade.build.model_copy(update={
            "premade_id": "hero.barbarian_l5_berserker_torch",
        }),
    })
    mismatch = service.validate_new_character(
        owner.principal_id,
        mismatched_request,
    )
    assert not mismatch.valid
    assert {
        issue.code.value for issue in mismatch.issues
    } >= {"premade_build_mismatch"}
    repository.close()


def test_multiclass_premade_uses_ordinary_creation_validation_and_holdings(
    tmp_path: Path,
) -> None:
    """The release-proof multiclass is catalog data, never a special route."""

    repository = GameDirectoryRepository(
        tmp_path / "multiclass-directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    premade = next(
        row
        for row in service.build_creation_catalog().premades
        if row.premade_id == "hero.fighter_2_sorcerer_3_spellblade"
    )
    assert tuple(
        (
            level.class_ref.content_id,
            level.resulting_class_level,
        )
        for level in premade.build.class_levels
    ) == (
        ("class.fighter", 1),
        ("class.fighter", 2),
        ("class.sorcerer", 1),
        ("class.sorcerer", 2),
        ("class.sorcerer", 3),
    )
    request = CreateCharacterRequest(
        display_name="Persistent Spellblade",
        build=premade.build,
        loadout=premade.loadout,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid, validation.issues
    created = service.create_character(owner.principal_id, request)
    assert created.definition.definition.class_levels == (
        premade.build.class_levels
    )
    assert created.advancement.earned_character_level == 5
    expected_holdings = starter_holdings_for_build(
        BUILTIN_PREMADE_BUILDS[premade.premade_id],
    )
    assert {
        (item.recipe.recipe_digest, item.quantity, item.equipped_slot)
        for item in created.holdings.holdings.items
    } == {
        (holding.recipe.recipe_digest, holding.quantity, holding.equipped_slot)
        for holding in expected_holdings
    }
    assert any(
        item.equipped_slot is not None
        for item in created.holdings.holdings.items
    )
    repository.close()


def test_creation_request_contains_exact_build_and_loadout_drafts() -> None:
    request = CreateCharacterRequest(
        display_name="Canonical",
        build=_draft(),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest="b" * 64,
        expected_ruleset_digest="c" * 64,
        idempotency_key=uuid4(),
    )
    assert request.display_name == "Canonical"
    assert request.loadout.prepared_spells == ()


def test_service_creates_valid_builtin_schema2_fighter_and_returns_heads(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    request = CreateCharacterRequest(
        display_name="  Canonical   Fighter ",
        build=_builtin_fighter_draft(service),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=service.ensure_profile_settings(
            owner.principal_id,
        ).ruleset_digest,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid, validation.issues
    created = service.create_character(owner.principal_id, request)

    assert created.character.display_name == "Canonical Fighter"
    assert created.definition.definition.schema_version == 2
    assert created.heads.definition_revision == 1
    assert created.heads.holdings_revision == 1
    assert created.heads.loadout_revision == 1
    assert created.advancement.earned_character_level == 1
    repository.close()


def test_character_creation_is_idempotent_and_rejects_key_reuse(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    request = CreateCharacterRequest(
        display_name="Idempotent Fighter",
        build=_builtin_fighter_draft(service),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )

    first = service.create_character(owner.principal_id, request)
    second = service.create_character(owner.principal_id, request)
    assert second == first
    assert len(
        repository.list_characters_for_principal(owner.principal_id),
    ) == 1

    with pytest.raises(ConflictError, match="idempotency key"):
        service.create_character(
            owner.principal_id,
            request.model_copy(update={"display_name": "Different"}),
        )
    repository.close()


def test_validation_fails_closed_on_client_content_and_rules_identity(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    request = CreateCharacterRequest(
        display_name="Stale Creator",
        build=_builtin_fighter_draft(service),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest="0" * 64,
        expected_ruleset_digest="1" * 64,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert not validation.valid
    assert tuple(issue.code.value for issue in validation.issues[:2]) == (
        "content_set_mismatch",
        "ruleset_mismatch",
    )
    assert validation.preview is None
    repository.close()


def test_standalone_routes_use_one_selected_physical_profile_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    fixture_repository = GameDirectoryRepository(
        tmp_path / "fixture.sqlite3",
        capability_pepper=PEPPER,
    )
    fixture_service = CharacterDirectoryService(
        fixture_repository,
        bootstrap_content_system(),
    )

    with TestClient(standalone_app) as client:
        local_profile = client.get("/directory/local-profile")
        assert local_profile.status_code == 200, local_profile.text
        profile = local_profile.json()
        creator_catalog = client.get("/character-creation/catalog")
        assert creator_catalog.status_code == 200, creator_catalog.text
        assert [
            row["premade_id"]
            for row in creator_catalog.json()["premades"]
        ] == [
            "hero.barbarian_l5_berserker_torch",
            "hero.fighter_2_sorcerer_3_spellblade",
            "hero.fighter_l5_shield_torch",
            "hero.sorcerer_l5_standard_torch",
        ]
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile["principal_capability"],
        }
        request = CreateCharacterRequest(
            display_name="Standalone Fighter",
            build=_builtin_fighter_draft(fixture_service),
            loadout=CharacterLoadoutDraft(),
            expected_content_set_digest=(
                fixture_service.content_system.content_set_digest
            ),
            expected_ruleset_digest=profile["settings"]["ruleset_digest"],
            idempotency_key=uuid4(),
        )
        created = client.post(
            "/directory/characters",
            headers=headers,
            json=request.model_dump(mode="json"),
        )
        assert created.status_code == 200, created.text
        character_id = created.json()["character"]["character_id"]
        assert client.get(
            f"/directory/characters/{character_id}",
            headers=headers,
        ).status_code == 200
        award_request = AdminCharacterAdvancementAwardRequest(
            idempotency_key=uuid4(),
            expected_earned_character_level=1,
            level_delta=1,
        )
        awarded = client.post(
            f"/admin/characters/{character_id}/advancement-awards",
            headers=headers,
            json=award_request.model_dump(mode="json"),
        )
        assert awarded.status_code == 200, awarded.text
        assert awarded.json()["earned_character_level"] == 2
        assert (
            client.post(
                f"/admin/characters/{character_id}/advancement-awards",
                headers=headers,
                json=award_request.model_dump(mode="json"),
            ).json()
            == awarded.json()
        )
        listed = client.get("/directory/characters", headers=headers)
        assert listed.status_code == 200, listed.text
        assert [
            row["character_id"]
            for row in listed.json()["characters"]
        ] == [character_id]
        profile_response = client.get(
            "/directory/players/me",
            headers=headers,
        )
        assert profile_response.status_code == 200, profile_response.text
        assert profile_response.json()["settings"] == profile["settings"]
        assert [
            row["character_id"]
            for row in profile_response.json()["characters"]
        ] == [character_id]
        updated_settings = client.put(
            "/directory/players/me/settings",
            headers=headers,
            json={
                "expected_settings_version": (
                    profile["settings"]["settings_version"]
                ),
                "permissive_multiclass_prerequisites": False,
                "multiclass_slot_rounding_policy": "srd_5_1_round_down",
                "allow_respec": False,
                "spell_preparation_policy": "out_of_combat",
            },
        )
        assert updated_settings.status_code == 200, updated_settings.text
        assert updated_settings.json()["settings_version"] == 2
        assert (
            client.get(
                "/directory/players/me",
                headers=headers,
            ).json()["settings"]
            == updated_settings.json()
        )

    profile_database = next(
        (tmp_path / "runtime" / "profiles").glob("*/profile.sqlite3"),
    )
    assert profile_database.is_file()
    fixture_repository.close()


def test_level_up_is_active_lease_fenced_and_uses_the_existing_three_head_cas(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    created = service.create_character(
        owner.principal_id,
        CreateCharacterRequest(
            display_name="Fighter",
            build=_builtin_fighter_draft(service),
            loadout=CharacterLoadoutDraft(),
            expected_content_set_digest=(
                service.content_system.content_set_digest
            ),
            expected_ruleset_digest=service.ensure_profile_settings(
                owner.principal_id,
            ).ruleset_digest,
            idempotency_key=uuid4(),
        ),
    )
    repository.create_character_advancement_award(
        CharacterAdvancementAwardCreate(
            character_id=created.character.character_id,
            level_delta=1,
            source_kind=CharacterAdvancementSourceKind.DEVELOPER,
            source_id="developer.level.2",
        ),
    )
    current = created.definition.definition
    assert current.schema_version == 2
    level_two = ClassLevelEntry(
        class_level_id=ClassLevelId(value="level.two"),
        character_level=2,
        class_ref=current.class_levels[0].class_ref,
        resulting_class_level=2,
    )
    build = CharacterBuildDraft(
        body_recipe=current.body_recipe,
        species_ref=current.species_ref,
        species_variant_ref=current.species_variant_ref,
        background_ref=current.background_ref,
        immutable_origin_choices=current.immutable_origin_choices,
        appearance=current.appearance,
        base_ability_scores=current.base_ability_scores,
        flexible_ability_bonuses=current.flexible_ability_bonuses,
        class_levels=(*current.class_levels, level_two),
        premade_id=current.premade_id,
    )
    request = CharacterLevelUpRequest(
        idempotency_key=uuid4(),
        expected_row_version=created.character.row_version,
        expected_heads=created.heads,
        build=build,
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=service.ensure_profile_settings(
            owner.principal_id,
        ).ruleset_digest,
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=owner.principal_id,
            scenario_kind="test",
            scenario_id="lease-fence",
            display_name="Lease Fence",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest=service.content_system.content_set_digest,
        ),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=owner.principal_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(may_control_entities=True),
        ),
    )
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=created.character.character_id,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )

    with pytest.raises(ConflictError, match="active deployment"):
        service.validate_level_up(
            owner.principal_id,
            created.character.character_id,
            request,
        )
    current_build = CharacterBuildDraft(
        body_recipe=current.body_recipe,
        species_ref=current.species_ref,
        species_variant_ref=current.species_variant_ref,
        background_ref=current.background_ref,
        immutable_origin_choices=current.immutable_origin_choices,
        appearance=current.appearance,
        base_ability_scores=current.base_ability_scores,
        flexible_ability_bonuses=current.flexible_ability_bonuses,
        class_levels=current.class_levels,
        premade_id=current.premade_id,
    )
    with pytest.raises(ConflictError, match="active deployment"):
        service.validate_respec(
            owner.principal_id,
            created.character.character_id,
            CharacterRespecRequest(
                idempotency_key=uuid4(),
                expected_row_version=created.character.row_version,
                expected_heads=created.heads,
                build=current_build,
                loadout=CharacterLoadoutDraft(),
                expected_content_set_digest=(
                    service.content_system.content_set_digest
                ),
                expected_ruleset_digest=(
                    service.ensure_profile_settings(
                        owner.principal_id,
                    ).ruleset_digest
                ),
            ),
        )
    with pytest.raises(ConflictError, match="active deployment"):
        service.validate_loadout(
            owner.principal_id,
            created.character.character_id,
            CharacterLoadoutMutationRequest(
                idempotency_key=uuid4(),
                expected_row_version=created.character.row_version,
                expected_heads=created.heads,
                loadout=CharacterLoadoutDraft(),
                expected_content_set_digest=(
                    service.content_system.content_set_digest
                ),
                expected_ruleset_digest=(
                    service.ensure_profile_settings(
                        owner.principal_id,
                    ).ruleset_digest
                ),
            ),
        )

    repository.release_character_deployment_lease(
        lease.lease_id,
        release_reason="test_continue",
    )
    assert service.validate_level_up(
        owner.principal_id,
        created.character.character_id,
        request,
    ).valid
    leveled = service.level_up(
        owner.principal_id,
        created.character.character_id,
        request,
    )
    assert leveled.heads.definition_revision == 2
    leveled_definition = leveled.definition.definition
    assert isinstance(leveled_definition, CharacterDefinitionRevisionV2)
    assert len(leveled_definition.class_levels) == 2
    repository.create_character_advancement_award(
        CharacterAdvancementAwardCreate(
            character_id=created.character.character_id,
            level_delta=1,
            source_kind=CharacterAdvancementSourceKind.DEVELOPER,
            source_id="developer.future.level",
        ),
    )
    assert service.get_advancement(
        owner.principal_id,
        created.character.character_id,
    ).earned_character_level == 3
    assert service.level_up(
        owner.principal_id,
        created.character.character_id,
        request,
    ) == leveled
    with pytest.raises(ConflictError, match="idempotency key"):
        service.level_up(
            owner.principal_id,
            created.character.character_id,
            request.model_copy(
                update={
                    "expected_row_version": request.expected_row_version + 1,
                },
            ),
        )
    repository.close()


def test_loadout_and_respec_each_commit_once_through_three_head_cas(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    created = service.create_character(
        owner.principal_id,
        CreateCharacterRequest(
            display_name="Mutable Fighter",
            build=_builtin_fighter_draft(service),
            loadout=CharacterLoadoutDraft(),
            expected_content_set_digest=(
                service.content_system.content_set_digest
            ),
            expected_ruleset_digest=settings.ruleset_digest,
            idempotency_key=uuid4(),
        ),
    )
    loadout_request = CharacterLoadoutMutationRequest(
        idempotency_key=uuid4(),
        expected_row_version=created.character.row_version,
        expected_heads=created.heads,
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
    )
    assert service.validate_loadout(
        owner.principal_id,
        created.character.character_id,
        loadout_request,
    ).valid
    after_loadout = service.update_loadout(
        owner.principal_id,
        created.character.character_id,
        loadout_request,
    )
    assert after_loadout.heads.definition_revision == 1
    assert after_loadout.heads.loadout_revision == 2
    assert service.update_loadout(
        owner.principal_id,
        created.character.character_id,
        loadout_request,
    ) == after_loadout
    with pytest.raises(ConflictError, match="idempotency key"):
        service.update_loadout(
            owner.principal_id,
            created.character.character_id,
            loadout_request.model_copy(
                update={
                    "expected_row_version": (
                        loadout_request.expected_row_version + 1
                    ),
                },
            ),
        )

    definition = after_loadout.definition.definition
    assert isinstance(definition, CharacterDefinitionRevisionV2)
    respec_request = CharacterRespecRequest(
        idempotency_key=uuid4(),
        expected_row_version=after_loadout.character.row_version,
        expected_heads=after_loadout.heads,
        build=CharacterBuildDraft(
            body_recipe=definition.body_recipe,
            species_ref=definition.species_ref,
            species_variant_ref=definition.species_variant_ref,
            background_ref=definition.background_ref,
            immutable_origin_choices=definition.immutable_origin_choices,
            appearance=definition.appearance,
            base_ability_scores=definition.base_ability_scores,
            flexible_ability_bonuses=definition.flexible_ability_bonuses,
            class_levels=definition.class_levels,
            premade_id=definition.premade_id,
        ),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
    )
    assert service.validate_respec(
        owner.principal_id,
        created.character.character_id,
        respec_request,
    ).valid
    after_respec = service.respec(
        owner.principal_id,
        created.character.character_id,
        respec_request,
    )
    assert after_respec.heads.definition_revision == 2
    assert after_respec.heads.loadout_revision == 3
    assert service.respec(
        owner.principal_id,
        created.character.character_id,
        respec_request,
    ) == after_respec
    with pytest.raises(ConflictError, match="idempotency key"):
        service.respec(
            owner.principal_id,
            created.character.character_id,
            respec_request.model_copy(
                update={
                    "expected_row_version": (
                        respec_request.expected_row_version + 1
                    ),
                },
            ),
        )
    repository.close()
