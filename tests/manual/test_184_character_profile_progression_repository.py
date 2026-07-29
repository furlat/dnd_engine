"""Focused persistence tests for profile settings and three-head characters."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    FlexibleAbilityBonusSelection,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.progression import character_ruleset_digest
from server.game_directory.canonical import canonical_digest, canonical_json
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    CharacterDeploymentLeaseCreate,
    CharacterRevisionBundleCommit,
    CharacterRevisionHeads,
    CharacterSettlementCreate,
    DirectoryMutationReceiptCreate,
    GameCreate,
    GameLifecycleState,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    MulticlassSlotRoundingPolicy,
    PinnedCharacterDeploymentCreate,
    PrincipalCreate,
    PrincipalKind,
    ProfileSettingsCreate,
    ProfileSettingsUpdate,
    SpellPreparationPolicy,
)
from server.game_directory.errors import (
    ConflictError,
    MigrationError,
    NotFoundError,
    StaleVersionError,
)
from server.game_directory.migrations import (
    CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES,
    MIGRATIONS,
    OFFLINE_CHARACTER_LOADOUT_BACKFILL_REQUIRED,
    apply_migrations,
    configure_connection,
)
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
PEPPER = b"character-profile-progression-repository-pepper"
CHARACTER_ID = UUID("10000000-0000-0000-0000-000000000184")


def _open(path: Path) -> GameDirectoryRepository:
    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def _recipe(
    kind: ContentDefinitionKind,
    content_id: str,
    *,
    parameters: dict[str, JsonValue] | None = None,
) -> ContentRecipe:
    return ContentRecipe.create(
        ref=ContentRef(
            pack_id="content.srd_5_1_cc",
            definition_kind=kind,
            content_id=content_id,
            content_version=1,
            definition_contract_hash="a" * 64,
        ),
        parameters=parameters or {},
    )


def _definition(
    revision: int = 1,
    *,
    character_id: UUID = CHARACTER_ID,
) -> CharacterDefinitionRevisionV2:
    return CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=revision,
        body_recipe=_recipe(
            ContentDefinitionKind.CREATURE,
            "creature.player_body",
        ),
        species_ref=_recipe(
            ContentDefinitionKind.SPECIES,
            "species.human",
        ).ref,
        background_ref=_recipe(
            ContentDefinitionKind.BACKGROUND,
            "background.acolyte",
        ).ref,
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
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=_recipe(
                    ContentDefinitionKind.CLASS,
                    "class.fighter",
                ).ref,
                resulting_class_level=1,
            ),
        ),
        premade_id="premade.barbarian",
        earned_character_level=1,
        content_set_digest="b" * 64,
        ruleset_digest="c" * 64,
    )


def _holdings(
    revision: int = 1,
    *,
    character_id: UUID = CHARACTER_ID,
) -> CharacterHoldingsRevision:
    return CharacterHoldingsRevision.create(
        character_id=character_id,
        holdings_revision=revision,
        items=(),
    )


def _loadout(
    revision: int = 1,
    *,
    based_on_definition_revision: int = 1,
    character_id: UUID = CHARACTER_ID,
) -> CharacterLoadoutRevisionV1:
    return CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=revision,
        based_on_definition_revision=based_on_definition_revision,
    )


def _initial_award(
    *,
    character_id: UUID = CHARACTER_ID,
) -> CharacterAdvancementAwardCreate:
    return CharacterAdvancementAwardCreate(
        character_id=character_id,
        level_delta=1,
        source_kind=CharacterAdvancementSourceKind.CREATION,
        source_id=f"character:{character_id}:creation",
    )


def _bootstrap(
    owner_principal_id: UUID,
    *,
    character_id: UUID = CHARACTER_ID,
) -> CharacterBootstrapCreate:
    return CharacterBootstrapCreate(
        character_id=character_id,
        owner_principal_id=owner_principal_id,
        display_name="Stored Hero",
        definition=_definition(character_id=character_id),
        starter_holdings=_holdings(character_id=character_id),
        starter_loadout=_loadout(character_id=character_id),
        initial_advancement_award=_initial_award(character_id=character_id),
    )


def _principal(repository: GameDirectoryRepository):
    return repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Player",
        ),
    )


def _heads(character) -> CharacterRevisionHeads:
    return CharacterRevisionHeads(
        definition_revision=character.current_definition_revision,
        definition_digest=character.current_definition_digest,
        holdings_revision=character.current_holdings_revision,
        holdings_digest=character.current_holdings_digest,
        loadout_revision=character.current_loadout_revision,
        loadout_digest=character.current_loadout_digest,
    )


def _game_membership_and_deployment(
    repository: GameDirectoryRepository,
    owner_principal_id: UUID,
    *,
    end_game: bool = True,
):
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=owner_principal_id,
            scenario_kind="test",
            scenario_id="settlement",
            display_name="Settlement Test",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest="c" * 64,
        ),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=owner_principal_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(may_control_entities=True),
        ),
    )
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )
    character = repository.get_character(CHARACTER_ID)
    deployment = repository.deploy_character_pinned(
        PinnedCharacterDeploymentCreate(
            game_id=game.game_id,
            membership_id=membership.membership_id,
            character_id=CHARACTER_ID,
            entity_uuid=uuid4(),
            lease_id=lease.lease_id,
        ),
        expected_character_row_version=character.row_version,
        expected_heads=_heads(character),
    )
    if end_game:
        game = repository.transition_game(
            game.game_id,
            expected_row_version=game.row_version,
            lifecycle_state=GameLifecycleState.ENDED,
            terminal_reason="completed",
        )
    return game, deployment


def test_character_revision_receipt_replays_one_atomic_success(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    owner = _principal(repository)
    character = repository.create_character_with_revisions(
        _bootstrap(owner.principal_id),
    )
    receipt_key = uuid4()
    receipt = DirectoryMutationReceiptCreate(
        owner_principal_id=owner.principal_id,
        idempotency_key=receipt_key,
        operation_kind="character.loadout",
        scope_id=CHARACTER_ID,
        request_digest="d" * 64,
    )
    bundle = CharacterRevisionBundleCommit(
        character_id=CHARACTER_ID,
        expected_row_version=character.row_version,
        expected_heads=_heads(character),
        new_loadout=_loadout(revision=2),
        mutation_receipt=receipt,
    )

    first = repository.commit_character_revisions(bundle)
    repository.close()
    repository = _open(database_path)
    replay = repository.commit_character_revisions(bundle)
    assert replay == first
    stored = repository.get_directory_mutation_receipt(
        owner.principal_id,
        receipt_key,
    )
    assert stored.operation_kind == "character.loadout"
    result_character = stored.result_payload["character"]
    result_heads = stored.result_payload["heads"]
    assert isinstance(result_character, dict)
    assert isinstance(result_heads, dict)
    assert result_character["row_version"] == 2
    assert result_heads["loadout_revision"] == 2

    with pytest.raises(ConflictError, match="idempotency key"):
        repository.commit_character_revisions(
            bundle.model_copy(
                update={
                    "mutation_receipt": receipt.model_copy(
                        update={"request_digest": "e" * 64},
                    ),
                },
            ),
        )
    repository.close()


def test_fresh_schema_has_profile_progression_tables_and_three_head_columns(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "profile.sqlite3"
    repository = _open(database_path)
    repository.close()
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }
    character_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(characters)").fetchall()
    }
    deployment_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(character_deployments)",
        ).fetchall()
    }
    connection.close()

    assert {
        "profile_settings",
        "character_advancement_awards",
        "character_loadout_revisions",
        "character_settlements",
        "directory_mutation_receipts",
    } <= tables
    assert {"current_loadout_revision", "current_loadout_digest"} <= character_columns
    assert {"loadout_revision", "loadout_digest"} <= deployment_columns


def test_existing_two_head_canonical_database_requires_offline_backfill(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "two-head.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    configure_connection(connection, 5_000)
    apply_migrations(
        connection,
        NOW,
        migrations=MIGRATIONS[: CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES.version],
    )
    timestamp = NOW.isoformat().replace("+00:00", "Z")
    principal_id = str(uuid4())
    character_id = uuid4()
    definition = _definition(character_id=character_id)
    holdings = _holdings(character_id=character_id)
    connection.execute(
        """
        INSERT INTO principals(
            principal_id, principal_kind, display_name, created_at,
            metadata_json, metadata_digest
        ) VALUES (?, 'human', 'Existing Player', ?, '{}', ?)
        """,
        (principal_id, timestamp, canonical_digest({})),
    )
    connection.execute(
        """
        INSERT INTO characters(
            character_id, owner_principal_id, display_name,
            preset_configuration_id, status, created_at, updated_at,
            row_version, revision_state
        ) VALUES (?, ?, 'Existing Hero', 'premade.barbarian', 'active', ?, ?,
                  1, 'legacy_pending')
        """,
        (str(character_id), principal_id, timestamp, timestamp),
    )
    connection.execute(
        """
        INSERT INTO character_definitions(
            character_id, definition_revision, schema_version,
            definition_json, definition_digest, created_at
        ) VALUES (?, 1, 1, ?, ?, ?)
        """,
        (
            str(character_id),
            canonical_json(definition.model_dump(mode="json")),
            definition.definition_digest,
            timestamp,
        ),
    )
    connection.execute(
        """
        INSERT INTO character_holdings_revisions(
            character_id, holdings_revision, schema_version,
            holdings_json, holdings_digest, created_at
        ) VALUES (?, 1, 1, ?, ?, ?)
        """,
        (
            str(character_id),
            canonical_json(holdings.model_dump(mode="json")),
            holdings.holdings_digest,
            timestamp,
        ),
    )
    connection.execute(
        """
        UPDATE characters
        SET revision_state = 'canonical',
            current_definition_revision = 1,
            current_definition_digest = ?,
            current_holdings_revision = 1,
            current_holdings_digest = ?
        WHERE character_id = ?
        """,
        (
            definition.definition_digest,
            holdings.holdings_digest,
            str(character_id),
        ),
    )

    with pytest.raises(
        MigrationError,
        match=OFFLINE_CHARACTER_LOADOUT_BACKFILL_REQUIRED,
    ):
        apply_migrations(connection, NOW, migrations=MIGRATIONS)

    assert (
        connection.execute(
            "SELECT MAX(version) FROM schema_migrations",
        ).fetchone()[0]
        == CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES.version
    )
    assert connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'character_loadout_revisions'
        """,
    ).fetchone() is None
    connection.close()


def test_profile_settings_are_principal_owned_versioned_and_restart_safe(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "profile.sqlite3"
    repository = _open(database_path)
    principal = _principal(repository)

    created = repository.create_profile_settings(
        ProfileSettingsCreate(
            owner_principal_id=principal.principal_id,
            ruleset_digest=character_ruleset_digest(
                permissive_multiclass_prerequisites=True,
                multiclass_slot_rounding_policy=(
                    MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
                ),
            ),
        ),
    )
    assert created.permissive_multiclass_prerequisites is True
    assert (
        created.multiclass_slot_rounding_policy
        is MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    )
    assert created.allow_respec is True
    assert created.spell_preparation_policy is SpellPreparationPolicy.LONG_REST
    assert created.settings_version == 1

    updated = repository.update_profile_settings(
        ProfileSettingsUpdate(
            owner_principal_id=principal.principal_id,
            expected_settings_version=1,
            permissive_multiclass_prerequisites=False,
            multiclass_slot_rounding_policy=(
                MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN
            ),
            allow_respec=False,
            spell_preparation_policy=SpellPreparationPolicy.OUT_OF_COMBAT,
            ruleset_digest=character_ruleset_digest(
                permissive_multiclass_prerequisites=False,
                multiclass_slot_rounding_policy=(
                    MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN
                ),
            ),
        ),
    )
    assert updated.settings_version == 2
    assert updated.permissive_multiclass_prerequisites is False

    with pytest.raises(StaleVersionError):
        repository.update_profile_settings(
            ProfileSettingsUpdate(
                owner_principal_id=principal.principal_id,
                expected_settings_version=1,
                ruleset_digest=character_ruleset_digest(
                    permissive_multiclass_prerequisites=True,
                    multiclass_slot_rounding_policy=(
                        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
                    ),
                ),
            ),
        )

    reopened = _open(database_path)
    assert reopened.get_profile_settings(principal.principal_id) == updated


def test_bootstrap_persists_all_three_heads_and_idempotent_level_authority(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "profile.sqlite3")
    principal = _principal(repository)

    character = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )

    assert character.current_definition_revision == 1
    assert character.current_holdings_revision == 1
    assert character.current_loadout_revision == 1
    assert repository.get_character_earned_level(CHARACTER_ID) == 1
    assert (
        repository.get_character_loadout_revision(
            CHARACTER_ID,
            loadout_revision=1,
        ).loadout
        == _loadout()
    )
    assert tuple(
        row.definition.definition_revision
        for row in repository.list_character_definition_revisions(CHARACTER_ID)
    ) == (1,)
    assert tuple(
        row.holdings.holdings_revision
        for row in repository.list_character_holdings_revisions(CHARACTER_ID)
    ) == (1,)
    assert tuple(
        row.loadout.loadout_revision
        for row in repository.list_character_loadout_revisions(CHARACTER_ID)
    ) == (1,)

    award = CharacterAdvancementAwardCreate(
        character_id=CHARACTER_ID,
        level_delta=1,
        source_kind=CharacterAdvancementSourceKind.DEVELOPER,
        source_id="developer.level.2",
    )
    first = repository.create_character_advancement_award(award)
    retry = repository.create_character_advancement_award(award)
    assert retry == first
    assert repository.get_character_earned_level(CHARACTER_ID) == 2

    with pytest.raises(ConflictError):
        repository.create_character_advancement_award(
            award.model_copy(update={"level_delta": 2}),
        )
    assert repository.get_character_earned_level(CHARACTER_ID) == 2


def test_one_bundle_cas_advances_definition_and_matching_loadout_atomically(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "profile.sqlite3")
    principal = _principal(repository)
    character = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    definition_two = _definition(2)
    loadout_two = _loadout(2, based_on_definition_revision=2)
    request = CharacterRevisionBundleCommit(
        character_id=CHARACTER_ID,
        expected_row_version=character.row_version,
        expected_heads=_heads(character),
        new_definition=definition_two,
        new_loadout=loadout_two,
    )

    updated = repository.commit_character_revisions(request)

    assert updated.row_version == character.row_version + 1
    assert updated.current_definition_digest == definition_two.definition_digest
    assert updated.current_holdings_digest == character.current_holdings_digest
    assert updated.current_loadout_digest == loadout_two.loadout_digest

    with pytest.raises(StaleVersionError):
        repository.commit_character_revisions(request)
    assert (
        repository.get_character_definition_revision(
            CHARACTER_ID,
            definition_revision=2,
        ).definition
        == definition_two
    )
    assert (
        repository.get_character_loadout_revision(
            CHARACTER_ID,
            loadout_revision=2,
        ).loadout
        == loadout_two
    )


def test_pinned_deployment_carries_all_three_exact_character_heads(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "profile.sqlite3")
    principal = _principal(repository)
    character = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )

    _game, deployment = _game_membership_and_deployment(
        repository,
        principal.principal_id,
    )

    assert deployment.definition_digest == character.current_definition_digest
    assert deployment.holdings_digest == character.current_holdings_digest
    assert deployment.loadout_digest == character.current_loadout_digest
    active_lease = repository.get_active_character_deployment_lease(
        CHARACTER_ID,
    )
    assert active_lease is not None
    assert active_lease.lease_id == deployment.lease_id
    repository.release_character_deployment_lease(
        active_lease.lease_id,
        release_reason="test_complete",
    )
    assert (
        repository.get_active_character_deployment_lease(CHARACTER_ID) is None
    )


def test_settlement_advances_holdings_once_and_exact_retry_is_a_noop(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "profile.sqlite3")
    principal = _principal(repository)
    character = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    game, deployment = _game_membership_and_deployment(
        repository,
        principal.principal_id,
    )
    resulting_holdings = _holdings(2)
    settlement = CharacterSettlementCreate(
        deployment_id=deployment.deployment_id,
        game_id=game.game_id,
        character_id=CHARACTER_ID,
        starting_holdings_revision=deployment.holdings_revision,
        starting_holdings_digest=deployment.holdings_digest,
        resulting_holdings_revision=resulting_holdings.holdings_revision,
        resulting_holdings_digest=resulting_holdings.holdings_digest,
        delta_digest=canonical_digest({"loot": []}),
    )
    request = CharacterRevisionBundleCommit(
        character_id=CHARACTER_ID,
        expected_row_version=character.row_version,
        expected_heads=_heads(character),
        new_holdings=resulting_holdings,
        settlement=settlement,
    )

    settled = repository.commit_character_revisions(request)
    retry = repository.commit_character_revisions(request)

    assert settled == retry
    assert settled.current_holdings_revision == 2
    assert (
        repository.get_character_settlement_by_deployment(
            deployment.deployment_id,
        ).resulting_holdings_digest
        == resulting_holdings.holdings_digest
    )

    with pytest.raises(ConflictError):
        repository.commit_character_revisions(
            request.model_copy(
                update={
                    "settlement": settlement.model_copy(
                        update={"delta_digest": "f" * 64},
                    ),
                },
            ),
        )
    assert repository.get_character(CHARACTER_ID).current_holdings_revision == 2


def test_failed_settlement_rolls_back_new_holdings_and_character_head(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "profile.sqlite3")
    principal = _principal(repository)
    character = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    game, deployment = _game_membership_and_deployment(
        repository,
        principal.principal_id,
        end_game=False,
    )
    resulting_holdings = _holdings(2)
    settlement = CharacterSettlementCreate(
        deployment_id=deployment.deployment_id,
        game_id=game.game_id,
        character_id=CHARACTER_ID,
        starting_holdings_revision=deployment.holdings_revision,
        starting_holdings_digest=deployment.holdings_digest,
        resulting_holdings_revision=resulting_holdings.holdings_revision,
        resulting_holdings_digest=resulting_holdings.holdings_digest,
        delta_digest=canonical_digest({"loot": []}),
    )

    with pytest.raises(ConflictError, match="ended game"):
        repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=CHARACTER_ID,
                expected_row_version=character.row_version,
                expected_heads=_heads(character),
                new_holdings=resulting_holdings,
                settlement=settlement,
            ),
        )

    unchanged = repository.get_character(CHARACTER_ID)
    assert unchanged.current_holdings_revision == 1
    with pytest.raises(NotFoundError, match="does not exist"):
        repository.get_character_holdings_revision(
            CHARACTER_ID,
            holdings_revision=2,
        )
