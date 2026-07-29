"""Focused contracts for the canonical persistent-character directory surface."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue, ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    starter_holdings_for_build,
)
from dnd.content_system.character_appearance import (
    FIGHTER_HUMAN_APPEARANCE,
    resolve_player_character_appearance,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassSkillChoice,
    ClassLevelEntry,
    ClassLevelId,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.items.torches import TORCH_RECIPE
from server.character_directory_contracts import (
    AdminCharacterAdvancementAwardRequest,
    CharacterBuildDraft,
    CharacterCreationValidationRequest,
    CharacterLevelUpRequest,
    CharacterLoadoutDraft,
    CharacterLoadoutMutationRequest,
    CharacterRespecRequest,
    CreateCharacterRequest,
    UpdateCharacterPresentationPreferencesRequest,
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
from server.game_directory.canonical import canonical_digest
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
        appearance=FIGHTER_HUMAN_APPEARANCE,
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
        immutable_origin_choices=tuple(sorted(
            (
                *(
                    choice
                    for choice in catalog.creation_plans[
                        0
                    ].build.immutable_origin_choices
                    if not isinstance(
                        choice,
                        StartingApparelPackageChoice,
                    )
                ),
            StartingApparelPackageChoice(
                choice_id=catalog.starting_apparel_requirement.choice_id,
                selected_ref=(
                    catalog.starting_apparel_requirement.allowed_refs[0]
                ),
            ),
            ),
            key=lambda choice: choice.choice_id,
        )),
        appearance=FIGHTER_HUMAN_APPEARANCE,
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


def _blank_creation_plan(service: CharacterDirectoryService):
    plan = service.build_creation_catalog().creation_plans[0]
    assert plan.source_premade_id is None
    return plan


def _creation_request(
    service: CharacterDirectoryService,
    *,
    owner_id,
    display_name: str,
    build: CharacterBuildDraft,
    loadout: CharacterLoadoutDraft | None = None,
    idempotency_key=None,
) -> CreateCharacterRequest:
    plan = _blank_creation_plan(service)
    settings = service.ensure_profile_settings(owner_id)
    return CreateCharacterRequest(
        display_name=display_name,
        build=build,
        loadout=loadout or CharacterLoadoutDraft(),
        creation_plan_id=plan.plan_id,
        creation_plan_digest=plan.plan_digest,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=idempotency_key or uuid4(),
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


def test_character_presentation_preferences_are_owner_scoped_persistent_and_independent(
    tmp_path: Path,
) -> None:
    """Flexible art preferences persist without mutating gameplay revisions."""

    database_path = tmp_path / "directory.sqlite3"
    repository = GameDirectoryRepository(
        database_path,
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
    before = service.get_character_snapshot(
        owner.principal_id,
        character.character_id,
    )

    empty = service.get_character_presentation_preferences(
        owner.principal_id,
        character.character_id,
    )
    assert empty.schema_version == 1
    assert empty.character_id == character.character_id
    assert empty.owner_principal_id == owner.principal_id
    assert empty.revision == 0
    assert empty.preferences == {}
    assert empty.preferences_digest == canonical_digest({})
    assert empty.updated_at is None

    portrait: dict[str, JsonValue] = {
        "neuroclient": {
            "portrait_identity": "gallery.hero.ember.v2",
            "experimental": {
                "palette": ["#112233", "#aabbcc"],
                "layer_opacity": 0.75,
            },
        },
    }
    saved = service.update_character_presentation_preferences(
        owner.principal_id,
        character.character_id,
        UpdateCharacterPresentationPreferencesRequest(
            expected_revision=0,
            preferences=portrait,
        ),
    )
    assert saved.revision == 1
    assert saved.preferences == portrait
    assert saved.preferences_digest == canonical_digest(portrait)
    assert saved.updated_at is not None

    with pytest.raises(StaleVersionError):
        service.update_character_presentation_preferences(
            owner.principal_id,
            character.character_id,
            UpdateCharacterPresentationPreferencesRequest(
                expected_revision=0,
                preferences={"neuroclient": {"portrait_identity": "stale"}},
            ),
        )
    with pytest.raises(CharacterDirectoryOwnershipError):
        service.get_character_presentation_preferences(
            stranger.principal_id,
            character.character_id,
        )
    with pytest.raises(CharacterDirectoryOwnershipError):
        service.update_character_presentation_preferences(
            stranger.principal_id,
            character.character_id,
            UpdateCharacterPresentationPreferencesRequest(
                expected_revision=1,
                preferences={},
            ),
        )

    after = service.get_character_snapshot(
        owner.principal_id,
        character.character_id,
    )
    assert after.character.row_version == before.character.row_version
    assert after.heads == before.heads
    repository.close()

    reopened_repository = GameDirectoryRepository(
        database_path,
        capability_pepper=PEPPER,
    )
    reopened_service = CharacterDirectoryService(
        reopened_repository,
        bootstrap_content_system(),
    )
    assert (
        reopened_service.get_character_presentation_preferences(
            owner.principal_id,
            character.character_id,
        )
        == saved
    )
    reopened_repository.close()


def test_gateway_declares_one_unversioned_character_route_family() -> None:
    """OpenAPI contains one canonical route family and no premade/V2 aliases."""

    paths = create_gateway_app().openapi()["paths"]
    expected = {
        "/character-creation/catalog",
        "/character-builds/validate",
        "/character-builds/visual-preview",
        "/directory/characters",
        "/directory/characters/{character_id}",
        "/directory/characters/{character_id}/definition",
        "/directory/characters/{character_id}/definitions",
        "/directory/characters/{character_id}/holdings",
        "/directory/characters/{character_id}/loadout",
        "/directory/characters/{character_id}/presentation-preferences",
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
    assert set(
        paths[
            "/directory/characters/{character_id}/presentation-preferences"
        ],
    ) == {"get", "put"}
    assert not any(
        "/v2" in path or "premade" in path
        for path in paths
        if "character" in path
    )
    assert "/games/{game_id}/runtime/{worker_path}" not in paths


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
    assert human.definition.runtime_support.status.value == "available"
    assert human.definition.runtime_support.blocked_reason is None
    assert adventurer.definition.runtime_support.status.value == "available"
    assert adventurer.definition.runtime_support.blocked_reason is None
    available_origins = (
        *catalog.species,
        *catalog.species_variants,
        *catalog.backgrounds,
    )
    assert available_origins
    for row in available_origins:
        assert row.definition.runtime_support.status.value == "available"
        assert row.definition.runtime_support.blocked_reason is None
        assert "player_capable" not in row.descriptor.tags
        assert "implementation_blocked" not in row.descriptor.tags
    assert {"class.barbarian", "class.fighter", "class.sorcerer"} <= {
        row.ref.content_id for row in catalog.classes
    }
    sorcerer = next(
        row
        for row in catalog.classes
        if row.ref.content_id == "class.sorcerer"
    ).definition
    spell_rank_by_ref = {
        row.spell_ref: row.spell_rank
        for row in sorcerer.spell_entitlements
    }
    level_one_known = next(
        requirement
        for requirement in sorcerer.level_definitions[0].choice_requirements
        if requirement.choice_id
        == "class.sorcerer.level_1.spell_known"
    )
    level_two_replacement = next(
        requirement
        for requirement in sorcerer.level_definitions[1].choice_requirements
        if requirement.choice_id
        == "class.sorcerer.level_2.spell_replacement"
    )
    assert {
        spell_rank_by_ref[ref] for ref in level_one_known.allowed_refs
    } == {1}
    assert {
        spell_rank_by_ref[ref]
        for ref in level_two_replacement.allowed_refs
    } == {1}
    assert catalog.rules.point_buy_budget == 27
    assert catalog.schema_version == 7
    assert catalog.appearance_catalog.schema_version == 4
    assert catalog.rules.schema_version == 2
    assert catalog.rules.initial_custom_character_level == 1
    assert catalog.rules.maximum_pre_bonus_ability_score == 15
    assert catalog.rules.flexible_plus_two == 2
    assert catalog.rules.flexible_plus_one == 1
    assert tuple(
        option.option_id for option in catalog.appearance_catalog.options
    ) == (
        "appearance.beard",
        "appearance.beard_tint",
        "appearance.body",
        "appearance.build",
        "appearance.hair_tint",
        "appearance.head",
        "appearance.skin_tint",
        "appearance.stature",
    )
    assert tuple(
        (selection.option_id, selection.value_id)
        for selection in catalog.appearance_catalog.default_selection.options
    ) == tuple(
        (option.option_id, option.default_value_id)
        for option in catalog.appearance_catalog.options
    )
    hair_tints = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.hair_tint"
    )
    assert len(hair_tints.values) == 20
    assert all(
        value.tint_rgb is not None
        and value.tint_source_option_id is None
        for value in hair_tints.values
    )
    skin_tints = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.skin_tint"
    )
    assert len(skin_tints.values) == 20
    assert all(
        value.tint_rgb is not None
        and value.tint_source_option_id is None
        for value in skin_tints.values
    )
    beard_tints = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.beard_tint"
    )
    follow_hair = beard_tints.values[0]
    assert follow_hair.value_id == "appearance.beard_tint.follow_hair"
    assert follow_hair.tint_rgb is None
    assert follow_hair.tint_source_option_id == "appearance.hair_tint"
    assert tuple(
        value.value_id for value in beard_tints.values[1:]
    ) == tuple(value.value_id for value in hair_tints.values)
    invalid_sourced_tint = (
        catalog.appearance_catalog.model_dump(mode="json")
    )
    invalid_sourced_tint["options"][1]["values"][0]["tint_rgb"] = 1
    with pytest.raises(
        ValidationError,
        match="exactly one literal tint or tint source",
    ):
        type(catalog.appearance_catalog).model_validate(
            invalid_sourced_tint,
        )
    hair_rigs = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.head"
    )
    assert tuple(value.value_id for value in hair_rigs.values) == (
        "appearance.head.hair_01",
        "appearance.head.hair_09",
        "appearance.head.hair_10",
        "appearance.head.hair_16",
        "appearance.head.hair_17",
        "appearance.head.hair_22",
    )
    assert tuple(
        value.head_category for value in hair_rigs.values
    ) == ("Head1", "Head9", "Head10", "Head16", "Head17", "Head22")
    stature = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.stature"
    )
    assert tuple(
        value.visual_scale_multiplier for value in stature.values
    ) == (0.9, 1.0, 1.1)
    build = next(
        option
        for option in catalog.appearance_catalog.options
        if option.option_id == "appearance.build"
    )
    assert tuple(
        value.visual_scale_x_multiplier for value in build.values
    ) == (0.9, 1.0, 1.1)
    assert tuple(
        (
            constraint.when_option_id,
            constraint.when_value_id,
            constraint.required_option_id,
            constraint.allowed_value_ids,
        )
        for constraint in catalog.appearance_catalog.constraints
    ) == ()
    resolved_default = resolve_player_character_appearance(
        body_ref=catalog.body_recipes[0].ref,
        species_ref=human.ref,
        selection=catalog.appearance_catalog.default_selection,
    )
    assert resolved_default.body_category == "NakedBody"
    assert resolved_default.head_category == "Head9"
    assert resolved_default.visual_scale == 1.0
    assert resolved_default.visual_scale_x == 1.0
    assert resolved_default.hair_tint == 0x993F00
    assert resolved_default.skin_tint == 0xE6BC98
    assert not resolved_default.has_beard
    assert resolved_default.beard_tint == 0
    assert tuple(row.plan_id for row in catalog.creation_plans) == (
        "creation_plan.blank_custom",
        "creation_plan.premade.hero.barbarian_l5_berserker_torch",
        "creation_plan.premade.hero.fighter_2_sorcerer_3_spellblade",
        "creation_plan.premade.hero.fighter_l5_shield_torch",
        "creation_plan.premade.hero.sorcerer_l5_standard_torch",
    )
    for plan in catalog.creation_plans:
        assert plan.schema_version == 1
        assert len(plan.build.class_levels) == (
            plan.character_level_entitlement
        )
        with pytest.raises(ValidationError, match="does not authenticate"):
            type(plan).model_validate({
                **plan.model_dump(mode="json"),
                "plan_digest": "0" * 64,
            })
    assert (
        catalog.rules.default_multiclass_slot_rounding_policy.value
        == "srd_5_2_round_up"
    )
    repository.close()


def test_blank_creation_plan_authorizes_exactly_level_one(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "initial-level-directory.sqlite3",
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
    plan = _blank_creation_plan(service)
    level_one = _builtin_fighter_draft(service)
    level_two = ClassLevelEntry(
        class_level_id=ClassLevelId(value="fighter.level.two"),
        character_level=2,
        class_ref=level_one.class_levels[0].class_ref,
        resulting_class_level=2,
    )
    invalid_build = level_one.model_copy(update={
        "class_levels": (*level_one.class_levels, level_two),
    })
    validation = service.validate_new_character(
        owner.principal_id,
        CreateCharacterRequest(
            display_name="Too Experienced",
            build=invalid_build,
            loadout=CharacterLoadoutDraft(),
            creation_plan_id=plan.plan_id,
            creation_plan_digest=plan.plan_digest,
            expected_content_set_digest=(
                service.content_system.content_set_digest
            ),
            expected_ruleset_digest=settings.ruleset_digest,
            idempotency_key=uuid4(),
        ),
    )

    initial_level_issue = next(
        issue
        for issue in validation.issues
        if issue.code.value == "creation_plan_level_mismatch"
    )
    assert initial_level_issue.path == ("build", "class_levels")
    assert (
        initial_level_issue.detail
        == "The selected creation plan authorizes exactly 1 character levels."
    )
    repository.close()


def test_every_catalog_origin_is_mechanically_available(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "blocked-origins.sqlite3",
        capability_pepper=PEPPER,
    )
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    catalog = service.build_creation_catalog()
    assert all(
        row.definition.runtime_support.status.value == "available"
        for row in (
            *catalog.species,
            *catalog.species_variants,
            *catalog.backgrounds,
        )
    )

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
    plan = next(
        row
        for row in service.build_creation_catalog().creation_plans
        if row.source_premade_id == "hero.fighter_l5_shield_torch"
    )
    request = CreateCharacterRequest(
        display_name="Persistent Premade",
        build=plan.build,
        loadout=plan.loadout,
        creation_plan_id=plan.plan_id,
        creation_plan_digest=plan.plan_digest,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid, validation.issues
    created = service.create_character(owner.principal_id, request)
    replayed = service.create_character(owner.principal_id, request)

    assert replayed == created
    assert (
        created.definition.definition.premade_id
        == plan.source_premade_id
    )
    assert created.advancement.earned_character_level == 5
    assert plan.source_premade_id is not None
    expected_holdings = starter_holdings_for_build(
        BUILTIN_PREMADE_BUILDS[plan.source_premade_id],
    )
    assert {
        (item.recipe.recipe_digest, item.quantity, item.equipped_slot)
        for item in created.holdings.holdings.items
    } == {
        (holding.recipe.recipe_digest, holding.quantity, holding.equipped_slot)
        for holding in expected_holdings
    }

    edited_request = request.model_copy(update={
        "idempotency_key": uuid4(),
        "build": plan.build.model_copy(update={
            "flexible_ability_bonuses": (
                plan.build.flexible_ability_bonuses.model_copy(update={
                    "plus_two": (
                        plan.build.flexible_ability_bonuses.plus_one
                    ),
                    "plus_one": (
                        plan.build.flexible_ability_bonuses.plus_two
                    ),
                })
            ),
        }),
    })
    edited = service.validate_new_character(
        owner.principal_id,
        edited_request,
    )
    assert edited.valid, edited.issues
    assert edited.normalized_build.premade_id is None
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
    plan = next(
        row
        for row in service.build_creation_catalog().creation_plans
        if (
            row.source_premade_id
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
    )
    assert tuple(
        (
            level.class_ref.content_id,
            level.resulting_class_level,
        )
        for level in plan.build.class_levels
    ) == (
        ("class.fighter", 1),
        ("class.fighter", 2),
        ("class.sorcerer", 1),
        ("class.sorcerer", 2),
        ("class.sorcerer", 3),
    )
    request = CreateCharacterRequest(
        display_name="Persistent Spellblade",
        build=plan.build,
        loadout=plan.loadout,
        creation_plan_id=plan.plan_id,
        creation_plan_digest=plan.plan_digest,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )

    validation = service.validate_new_character(owner.principal_id, request)
    assert validation.valid, validation.issues
    created = service.create_character(owner.principal_id, request)
    assert created.definition.definition.class_levels == (
        plan.build.class_levels
    )
    assert created.advancement.earned_character_level == 5
    assert plan.source_premade_id is not None
    expected_holdings = starter_holdings_for_build(
        BUILTIN_PREMADE_BUILDS[plan.source_premade_id],
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
        creation_plan_id="creation_plan.blank_custom",
        creation_plan_digest="a" * 64,
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
    request = _creation_request(
        service,
        owner_id=owner.principal_id,
        display_name="  Canonical   Fighter ",
        build=_builtin_fighter_draft(service),
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
    assert sum(
        item.recipe.recipe_digest == TORCH_RECIPE.recipe_digest
        for item in created.holdings.holdings.items
    ) == 1
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
    request = _creation_request(
        service,
        owner_id=owner.principal_id,
        display_name="Idempotent Fighter",
        build=_builtin_fighter_draft(service),
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
    request = _creation_request(
        service,
        owner_id=owner.principal_id,
        display_name="Stale Creator",
        build=_builtin_fighter_draft(service),
    ).model_copy(update={
        "expected_content_set_digest": "0" * 64,
        "expected_ruleset_digest": "1" * 64,
    })

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
            row["source_premade_id"]
            for row in creator_catalog.json()["creation_plans"]
            if row["source_premade_id"] is not None
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
        blank_plan = _blank_creation_plan(fixture_service)
        request = CreateCharacterRequest(
            display_name="Standalone Fighter",
            build=_builtin_fighter_draft(fixture_service),
            loadout=CharacterLoadoutDraft(),
            creation_plan_id=blank_plan.plan_id,
            creation_plan_digest=blank_plan.plan_digest,
            expected_content_set_digest=(
                fixture_service.content_system.content_set_digest
            ),
            expected_ruleset_digest=profile["settings"]["ruleset_digest"],
            idempotency_key=uuid4(),
        )
        visual_preview = client.post(
            "/character-builds/visual-preview",
            headers=headers,
            json=CharacterCreationValidationRequest(
                build=request.build,
                loadout=request.loadout,
                creation_plan_id=request.creation_plan_id,
                creation_plan_digest=request.creation_plan_digest,
                expected_content_set_digest=(
                    request.expected_content_set_digest
                ),
                expected_ruleset_digest=request.expected_ruleset_digest,
            ).model_dump(mode="json"),
        )
        assert visual_preview.status_code == 200, visual_preview.text
        visual_payload = visual_preview.json()
        assert visual_payload["schema_version"] == 1
        assert (
            visual_payload["entity"]["uuid"]
            == visual_payload["visual_loadout"]["entity_uuid"]
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
        _creation_request(
            service,
            owner_id=owner.principal_id,
            display_name="Fighter",
            build=_builtin_fighter_draft(service),
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
        _creation_request(
            service,
            owner_id=owner.principal_id,
            display_name="Mutable Fighter",
            build=_builtin_fighter_draft(service),
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
