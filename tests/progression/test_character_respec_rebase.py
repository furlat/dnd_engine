"""Regression coverage for exact persistent-character content rebasing."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_drafts,
    compose_builtin_character_revisions,
)
from dnd.core.content.durable_characters import (
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    StartingProficiencyChoice,
)
from dnd.core.content.identities import ContentRef
from server.character_directory_contracts import (
    CharacterMutationIssueCode,
    CharacterRespecRequest,
)
from server.character_directory_service import CharacterDirectoryService
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
    CharacterRevisionBundleCommit,
)
from server.game_directory.errors import ConflictError, StaleVersionError
from server.game_directory.repository import GameDirectoryRepository


PEPPER = b"character-respec-rebase-pepper"
SOURCE_PREMADE_ID = "hero.fighter_2_sorcerer_3_spellblade"
TARGET_FIGHTER_PREMADE_ID = "hero.fighter_l5_shield_torch"
MONA_HUMAN_V1_CONTRACT_HASH = (
    "4c1110dce3e2ab688603db91ba767cde7d564c1cc3b4a734b3b33811a6176545"
)
MONA_ADVENTURER_V1_CONTRACT_HASH = (
    "a6c220e89812efc6bcc9d0f9efb316803bfdc9b1c6a78144538425215ed1dc79"
)


def _historical_ref(
    ref: ContentRef,
    *,
    definition_contract_hash: str,
) -> ContentRef:
    return ref.model_copy(
        update={
            "content_version": 1,
            "definition_contract_hash": definition_contract_hash,
        },
    )


def _seed_stale_fighter(
    tmp_path: Path,
    *,
    missing_species: bool = False,
) -> tuple[
    GameDirectoryRepository,
    CharacterDirectoryService,
    UUID,
    UUID,
]:
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
    content_system = bootstrap_content_system()
    service = CharacterDirectoryService(repository, content_system)
    settings = service.ensure_profile_settings(owner.principal_id)
    character_id = UUID("416bd7c2-44ee-5e8e-926b-19c9a433862e")
    current = compose_builtin_character_revisions(
        character_id=character_id,
        build=BUILTIN_PREMADE_BUILDS[SOURCE_PREMADE_ID],
        content_system=content_system,
        ruleset_digest=settings.ruleset_digest,
    )
    definition = current.definition
    stale_species_ref = _historical_ref(
        definition.species_ref,
        definition_contract_hash=MONA_HUMAN_V1_CONTRACT_HASH,
    )
    if missing_species:
        stale_species_ref = stale_species_ref.model_copy(
            update={"content_id": "species.removed_human"},
        )
    retired_appearance = CharacterAppearanceSelection(
        options=tuple(
            (
                CharacterAppearanceOptionSelection(
                    option_id=row.option_id,
                    value_id="appearance.head.hair_09",
                )
                if row.option_id == "appearance.head"
                else row
            )
            for row in definition.appearance.options
            if row.option_id not in {
                "appearance.build",
                "appearance.stature",
            }
        ),
    )
    stale_definition = CharacterDefinitionRevisionV2.create(
        character_id=definition.character_id,
        definition_revision=definition.definition_revision,
        body_recipe=definition.body_recipe,
        species_ref=stale_species_ref,
        species_variant_ref=definition.species_variant_ref,
        background_ref=_historical_ref(
            definition.background_ref,
            definition_contract_hash=(
                MONA_ADVENTURER_V1_CONTRACT_HASH
            ),
        ),
        immutable_origin_choices=(),
        appearance=retired_appearance,
        base_ability_scores=definition.base_ability_scores,
        flexible_ability_bonuses=definition.flexible_ability_bonuses,
        class_levels=definition.class_levels,
        premade_id=definition.premade_id,
        earned_character_level=definition.earned_character_level,
        content_set_digest="1" * 64,
        ruleset_digest="2" * 64,
    )
    repository.create_character_with_revisions(
        CharacterBootstrapCreate(
            character_id=character_id,
            owner_principal_id=owner.principal_id,
            display_name="mona",
            definition=stale_definition,
            starter_holdings=current.holdings,
            starter_loadout=current.loadout,
            initial_advancement_award=CharacterAdvancementAwardCreate(
                character_id=character_id,
                level_delta=5,
                source_kind=CharacterAdvancementSourceKind.CREATION,
                source_id=f"character:{character_id}:creation",
            ),
        ),
    )
    return repository, service, owner.principal_id, character_id


def test_respec_seed_rebases_stale_immutable_origin_refs_without_client_inference(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed_stale_fighter(
        tmp_path,
    )

    seed = service.get_respec_seed(owner_id, character_id)

    assert seed.ready
    assert seed.editable_build is not None
    assert seed.editable_loadout is not None
    assert seed.source.definition_revision == 1
    assert seed.source.content_set_digest == "1" * 64
    assert seed.source.ruleset_digest == "2" * 64
    assert seed.source.heads == service.get_character_snapshot(
        owner_id,
        character_id,
    ).heads
    assert seed.target_content_set_digest == (
        service.content_system.content_set_digest
    )
    assert seed.target_ruleset_digest == (
        service.ensure_profile_settings(owner_id).ruleset_digest
    )
    assert tuple(change.path for change in seed.changes) == (
        (
            "build",
            "appearance",
            "options",
            "appearance.build",
        ),
        (
            "build",
            "appearance",
            "options",
            "appearance.stature",
        ),
        ("build", "background_ref"),
        (
            "build",
            "immutable_origin_choices",
            "species.human.additional_language",
        ),
        ("build", "species_ref"),
    )
    content_changes = tuple(
        change
        for change in seed.changes
        if change.kind == "content_ref"
    )
    assert len(content_changes) == 2
    assert all(
        change.source_ref != change.replacement_ref
        for change in content_changes
    )
    assert seed.editable_build.species_ref == next(
        row.ref
        for row in service.build_creation_catalog().species
        if row.ref.content_id == "species.human"
    )
    assert seed.editable_build.background_ref == next(
        row.ref
        for row in service.build_creation_catalog().backgrounds
        if row.ref.content_id == "background.adventurer"
    )
    stored = service.get_character_snapshot(
        owner_id,
        character_id,
    ).definition.definition
    language_choice = next(
        choice
        for choice in seed.editable_build.immutable_origin_choices
        if choice.choice_id == "species.human.additional_language"
    )
    assert isinstance(language_choice, StartingProficiencyChoice)
    assert tuple(
        subject.subject_id
        for subject in language_choice.proficiencies
    ) == ("language.draconic",)
    assert tuple(
        (row.option_id, row.value_id)
        for row in seed.editable_build.appearance.options
    ) == (
        ("appearance.beard", "appearance.beard.present"),
        ("appearance.beard_tint", "appearance.color.auburn"),
        ("appearance.body", "appearance.body.humanoid"),
        ("appearance.build", "appearance.build.average"),
        ("appearance.hair_tint", "appearance.color.auburn"),
        ("appearance.head", "appearance.head.hair_09"),
        ("appearance.skin_tint", "appearance.color.light_tan"),
        ("appearance.stature", "appearance.stature.average"),
    )
    assert stored.immutable_origin_choices == ()
    assert len(stored.appearance.options) == 6
    assert seed.editable_build.class_levels == stored.class_levels
    repository.close()


def test_rebased_seed_validates_and_respec_commits_under_current_digests(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed_stale_fighter(
        tmp_path,
    )
    before = service.get_character_snapshot(owner_id, character_id)
    seed = service.get_respec_seed(owner_id, character_id)
    assert seed.editable_build is not None
    assert seed.editable_loadout is not None
    fighter_build, fighter_loadout = compose_builtin_character_drafts(
        BUILTIN_PREMADE_BUILDS[TARGET_FIGHTER_PREMADE_ID],
    )
    requested_build = fighter_build.model_copy(update={
        "body_recipe": seed.editable_build.body_recipe,
        "species_ref": seed.editable_build.species_ref,
        "species_variant_ref": seed.editable_build.species_variant_ref,
        "background_ref": seed.editable_build.background_ref,
        "immutable_origin_choices": (
            seed.editable_build.immutable_origin_choices
        ),
        "appearance": seed.editable_build.appearance,
        # This reproduces the frontend's formerly required workaround.
        "premade_id": seed.editable_build.premade_id,
    })
    request = CharacterRespecRequest(
        idempotency_key=uuid4(),
        expected_row_version=before.character.row_version,
        expected_heads=before.heads,
        build=requested_build,
        loadout=fighter_loadout,
        expected_content_set_digest=seed.target_content_set_digest,
        expected_ruleset_digest=seed.target_ruleset_digest,
    )

    validation = service.validate_respec(owner_id, character_id, request)
    assert requested_build.base_ability_scores != (
        seed.editable_build.base_ability_scores
    )
    assert requested_build.flexible_ability_bonuses != (
        seed.editable_build.flexible_ability_bonuses
    )
    assert validation.valid, validation.issues
    assert validation.normalized_build.premade_id is None
    result = service.respec(owner_id, character_id, request)

    assert result.definition.definition.definition_revision == 2
    assert result.definition.definition.content_set_digest == (
        seed.target_content_set_digest
    )
    assert result.definition.definition.ruleset_digest == (
        seed.target_ruleset_digest
    )
    assert result.definition.definition.species_ref == (
        seed.editable_build.species_ref
    )
    assert result.definition.definition.background_ref == (
        seed.editable_build.background_ref
    )
    assert result.definition.definition.class_levels == (
        requested_build.class_levels
    )
    assert result.definition.definition.premade_id is None
    assert service.get_definition_history(
        owner_id,
        character_id,
    ).definitions[0].definition == before.definition.definition
    assert service.respec(owner_id, character_id, request) == result
    with pytest.raises(ConflictError, match="idempotency key"):
        service.respec(
            owner_id,
            character_id,
            request.model_copy(
                update={
                    "expected_row_version": request.expected_row_version + 1,
                },
            ),
        )
    repository.close()


def test_respec_still_rejects_an_actual_immutable_origin_change(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed_stale_fighter(
        tmp_path,
    )
    snapshot = service.get_character_snapshot(owner_id, character_id)
    seed = service.get_respec_seed(owner_id, character_id)
    assert seed.editable_build is not None
    assert seed.editable_loadout is not None
    acolyte_ref = next(
        row.ref
        for row in service.build_creation_catalog().backgrounds
        if row.ref.content_id == "background.acolyte"
    )
    request = CharacterRespecRequest(
        idempotency_key=uuid4(),
        expected_row_version=snapshot.character.row_version,
        expected_heads=snapshot.heads,
        build=seed.editable_build.model_copy(update={
            "background_ref": acolyte_ref,
        }),
        loadout=seed.editable_loadout,
        expected_content_set_digest=seed.target_content_set_digest,
        expected_ruleset_digest=seed.target_ruleset_digest,
    )

    validation = service.validate_respec(owner_id, character_id, request)

    assert not validation.valid
    assert CharacterMutationIssueCode.IMMUTABLE_ORIGIN_CHANGED in {
        issue.code for issue in validation.issues
    }
    repository.close()


def test_respec_seed_and_commit_remain_lease_and_three_head_fenced(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed_stale_fighter(
        tmp_path,
    )
    before = service.get_character_snapshot(owner_id, character_id)
    seed = service.get_respec_seed(owner_id, character_id)
    assert seed.editable_build is not None
    assert seed.editable_loadout is not None
    request = CharacterRespecRequest(
        idempotency_key=uuid4(),
        expected_row_version=before.character.row_version,
        expected_heads=before.heads,
        build=seed.editable_build,
        loadout=seed.editable_loadout,
        expected_content_set_digest=seed.target_content_set_digest,
        expected_ruleset_digest=seed.target_ruleset_digest,
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=owner_id,
            scenario_kind="test",
            scenario_id="respec-rebase-fence",
            display_name="Respec Rebase Fence",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest=service.content_system.content_set_digest,
        ),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=owner_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(may_control_entities=True),
        ),
    )
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=character_id,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )

    with pytest.raises(ConflictError, match="active deployment"):
        service.get_respec_seed(owner_id, character_id)
    with pytest.raises(ConflictError, match="active deployment"):
        service.respec(owner_id, character_id, request)

    repository.release_character_deployment_lease(
        lease.lease_id,
        release_reason="test_continue",
    )
    current_holdings = before.holdings.holdings
    repository.commit_character_revisions(
        CharacterRevisionBundleCommit(
            character_id=character_id,
            expected_row_version=before.character.row_version,
            expected_heads=before.heads,
            new_holdings=CharacterHoldingsRevision.create(
                character_id=character_id,
                holdings_revision=current_holdings.holdings_revision + 1,
                items=current_holdings.items,
            ),
        ),
    )
    changed = service.get_character_snapshot(owner_id, character_id)
    assert changed.character.row_version == before.character.row_version + 1
    with pytest.raises(StaleVersionError, match="revision heads changed"):
        service.respec(owner_id, character_id, request)
    repository.close()


def test_respec_seed_fails_closed_for_removed_content_identity(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed_stale_fighter(
        tmp_path,
        missing_species=True,
    )
    missing_species = service.get_character_snapshot(
        owner_id,
        character_id,
    ).definition.definition.species_ref

    seed = service.get_respec_seed(owner_id, character_id)

    assert not seed.ready
    assert seed.editable_build is None
    assert seed.editable_loadout is None
    assert len(seed.issues) == 1
    assert seed.issues[0].path == ("build", "species_ref")
    assert seed.issues[0].source_ref == missing_species
    assert seed.issues[0].reason == "identity_not_installed"
    repository.close()
