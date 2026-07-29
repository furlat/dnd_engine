"""Focused SQL foundation tests for durable character revisions and leases."""

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
    CharacterItemV1,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    FlexibleAbilityBonusSelection,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import WeaponSlot
from server.game_directory.canonical import canonical_digest, canonical_json
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    CharacterDeploymentLeaseCreate,
    CharacterRevisionHeads,
    CharacterRevisionState,
    GameCreate,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    MembershipState,
    PinnedCharacterDeploymentCreate,
    PrincipalCreate,
    PrincipalKind,
)
from server.game_directory.errors import ConflictError, StaleVersionError
from server.game_directory.migrations import (
    CHARACTER_PROFILE_PROGRESSION_FOUNDATION,
    CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES,
    MIGRATIONS,
    apply_migrations,
    configure_connection,
)
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
PEPPER = b"character-revision-repository-test-pepper"
CHARACTER_ID = UUID("10000000-0000-0000-0000-000000000001")
ITEM_ID = UUID("20000000-0000-0000-0000-000000000001")


def _open(path: Path) -> GameDirectoryRepository:
    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def _heads(character) -> CharacterRevisionHeads:
    return CharacterRevisionHeads(
        definition_revision=character.current_definition_revision,
        definition_digest=character.current_definition_digest,
        holdings_revision=character.current_holdings_revision,
        holdings_digest=character.current_holdings_digest,
        loadout_revision=character.current_loadout_revision,
        loadout_digest=character.current_loadout_digest,
    )


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
    character_id: UUID = CHARACTER_ID,
) -> CharacterDefinitionRevisionV2:
    return CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
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


def _item(*, quantity: int = 1) -> CharacterItemV1:
    return CharacterItemV1.create(
        character_item_id=ITEM_ID,
        recipe=_recipe(
            ContentDefinitionKind.ITEM,
            "item.club",
            parameters={"material": "oak"},
        ),
        quantity=quantity,
        equipped_slot=WeaponSlot.MELEE_MAIN,
    )


def _holdings(
    revision: int = 1,
    *,
    character_id: UUID = CHARACTER_ID,
    quantity: int = 1,
) -> CharacterHoldingsRevision:
    return CharacterHoldingsRevision.create(
        character_id=character_id,
        holdings_revision=revision,
        items=(_item(quantity=quantity),),
    )


def _loadout(
    *,
    character_id: UUID = CHARACTER_ID,
) -> CharacterLoadoutRevisionV1:
    return CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
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
        definition=_definition(character_id),
        starter_holdings=_holdings(character_id=character_id),
        starter_loadout=_loadout(character_id=character_id),
        initial_advancement_award=CharacterAdvancementAwardCreate(
            character_id=character_id,
            level_delta=1,
            source_kind=CharacterAdvancementSourceKind.CREATION,
            source_id=f"character:{character_id}:creation",
        ),
    )


def _principal(repository: GameDirectoryRepository):
    return repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Player",
        ),
    )


def _game_and_membership(
    repository: GameDirectoryRepository,
    principal_id: UUID,
):
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=principal_id,
            scenario_kind="test",
            scenario_id="character-revisions",
            display_name="Character Revision Test",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest="c" * 64,
        ),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=principal_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(may_control_entities=True),
        ),
    )
    return game, membership


def test_migration_marks_legacy_rows_pending_and_adds_immutable_revision_tables(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    configure_connection(connection, 5_000)
    character_revision_index = MIGRATIONS.index(
        CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES,
    )
    apply_migrations(
        connection,
        NOW,
        migrations=MIGRATIONS[:character_revision_index],
    )
    timestamp = NOW.isoformat().replace("+00:00", "Z")
    principal_id = str(uuid4())
    character_id = str(uuid4())
    game_id = str(uuid4())
    membership_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO principals(
            principal_id, principal_kind, display_name, created_at,
            metadata_json, metadata_digest
        ) VALUES (?, 'human', 'Legacy Player', ?, '{}', ?)
        """,
        (principal_id, timestamp, canonical_digest({})),
    )
    connection.execute(
        """
        INSERT INTO characters(
            character_id, owner_principal_id, display_name,
            preset_configuration_id, status, created_at, updated_at
        ) VALUES (?, ?, 'Legacy Hero', 'barbarian', 'active', ?, ?)
        """,
        (character_id, principal_id, timestamp, timestamp),
    )
    connection.execute(
        """
        INSERT INTO games(
            game_id, created_by_principal_id, lifecycle_state,
            visibility_policy, observer_policy, execution_kind,
            scenario_kind, scenario_id, display_name, creation_manifest_json,
            creation_manifest_digest, ruleset_version, engine_version,
            content_digest, created_at
        ) VALUES (
            ?, ?, 'ended', 'private', 'disabled', 'hosted',
            'legacy', 'legacy', 'Legacy Game', '{}', ?,
            'legacy', 'legacy', 'legacy', ?
        )
        """,
        (game_id, principal_id, canonical_digest({}), timestamp),
    )
    connection.execute(
        """
        INSERT INTO game_memberships(
            membership_id, game_id, principal_id, role, membership_state,
            may_connect, may_observe_public_state,
            may_observe_subjective_state, may_control_entities,
            may_view_agent_telemetry, may_manage_members, may_manage_game,
            may_view_objective_replay, authority_epoch, joined_at
        ) VALUES (
            ?, ?, ?, 'player', 'active',
            1, 0, 0, 1, 0, 0, 0, 0, 1, ?
        )
        """,
        (membership_id, game_id, principal_id, timestamp),
    )
    connection.execute(
        """
        INSERT INTO character_deployments(
            deployment_id, game_id, membership_id, character_id,
            entity_uuid, deployed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            game_id,
            membership_id,
            character_id,
            str(uuid4()),
            timestamp,
        ),
    )

    profile_progression_index = MIGRATIONS.index(
        CHARACTER_PROFILE_PROGRESSION_FOUNDATION,
    )
    apply_migrations(
        connection,
        NOW,
        migrations=MIGRATIONS[: profile_progression_index + 1],
    )
    with pytest.raises(sqlite3.IntegrityError, match="complete revision heads"):
        connection.execute(
            """
            INSERT INTO characters(
                character_id, owner_principal_id, display_name,
                preset_configuration_id, status, created_at, updated_at,
                revision_state
            ) VALUES (?, ?, 'Incomplete Hero', 'legacy', 'active', ?, ?,
                      'canonical')
            """,
            (str(uuid4()), principal_id, timestamp, timestamp),
        )
    row = connection.execute(
        """
        SELECT revision_state, current_definition_revision,
               current_definition_digest, current_holdings_revision,
               current_holdings_digest
        FROM characters WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()
    deployment_row = connection.execute(
        """
        SELECT pin_state, lease_id, definition_revision, definition_digest,
               holdings_revision, holdings_digest
        FROM character_deployments WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()
    tables = {
        value[0]
        for value in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }
    stored_migration = connection.execute(
        "SELECT name, checksum FROM schema_migrations WHERE version = ?",
        (CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES.version,),
    ).fetchone()
    connection.close()

    assert tuple(row) == (
        CharacterRevisionState.LEGACY_PENDING.value,
        None,
        None,
        None,
        None,
    )
    assert tuple(deployment_row) == (
        "legacy_pending",
        None,
        None,
        None,
        None,
        None,
    )
    assert {
        "character_definitions",
        "character_holdings_revisions",
        "character_loadout_revisions",
        "character_deployment_leases",
    }.issubset(tables)
    assert stored_migration[0] == "character_revisions_and_deployment_leases"
    assert stored_migration[1] == CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES.checksum


def test_atomic_bootstrap_stores_definition_and_starter_holdings_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    principal = _principal(repository)
    request = _bootstrap(principal.principal_id)

    character = repository.create_character_with_revisions(request)
    definition_row = repository.get_character_definition_revision(
        CHARACTER_ID,
        definition_revision=1,
    )
    holdings_row = repository.get_character_holdings_revision(
        CHARACTER_ID,
        holdings_revision=1,
    )
    loadout_row = repository.get_character_loadout_revision(
        CHARACTER_ID,
        loadout_revision=1,
    )
    with pytest.raises(ConflictError):
        repository.create_character_with_revisions(request)

    raw = sqlite3.connect(database_path)
    definition_json = raw.execute(
        """
        SELECT definition_json FROM character_definitions
        WHERE character_id = ? AND definition_revision = 1
        """,
        (str(CHARACTER_ID),),
    ).fetchone()[0]
    holdings_json = raw.execute(
        """
        SELECT holdings_json FROM character_holdings_revisions
        WHERE character_id = ? AND holdings_revision = 1
        """,
        (str(CHARACTER_ID),),
    ).fetchone()[0]
    loadout_json = raw.execute(
        """
        SELECT loadout_json FROM character_loadout_revisions
        WHERE character_id = ? AND loadout_revision = 1
        """,
        (str(CHARACTER_ID),),
    ).fetchone()[0]
    counts = raw.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM characters WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_definitions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_holdings_revisions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_loadout_revisions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_advancement_awards WHERE character_id = ?)
        """,
        (
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
        ),
    ).fetchone()
    raw.close()
    repository.close()

    assert character.revision_state is CharacterRevisionState.CANONICAL
    assert character.current_definition_revision == 1
    assert character.current_definition_digest == request.definition.definition_digest
    assert character.current_holdings_revision == 1
    assert character.current_holdings_digest == request.starter_holdings.holdings_digest
    assert character.current_loadout_revision == 1
    assert character.current_loadout_digest == request.starter_loadout.loadout_digest
    assert definition_row.definition == request.definition
    assert holdings_row.holdings == request.starter_holdings
    assert loadout_row.loadout == request.starter_loadout
    assert len(holdings_row.holdings.items) == 1
    assert definition_json == canonical_json(request.definition.model_dump(mode="json"))
    assert holdings_json == canonical_json(
        request.starter_holdings.model_dump(mode="json"),
    )
    assert loadout_json == canonical_json(
        request.starter_loadout.model_dump(mode="json"),
    )
    assert tuple(counts) == (1, 1, 1, 1, 1)


def test_holdings_append_is_immutable_and_rejects_a_stale_cas(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    principal = _principal(repository)
    created = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    revision_two = _holdings(revision=2, quantity=2)

    advanced = repository.append_character_holdings_revision(
        revision_two,
        expected_holdings_revision=created.current_holdings_revision,
        expected_holdings_digest=created.current_holdings_digest,
        expected_row_version=created.row_version,
    )
    with pytest.raises(StaleVersionError):
        repository.append_character_holdings_revision(
            _holdings(revision=3, quantity=3),
            expected_holdings_revision=advanced.current_holdings_revision,
            expected_holdings_digest=advanced.current_holdings_digest,
            expected_row_version=created.row_version,
        )

    revision_one_row = repository.get_character_holdings_revision(
        CHARACTER_ID,
        holdings_revision=1,
    )
    revision_two_row = repository.get_character_holdings_revision(
        CHARACTER_ID,
        holdings_revision=2,
    )
    raw = sqlite3.connect(database_path)
    holdings_count = raw.execute(
        """
        SELECT COUNT(*) FROM character_holdings_revisions
        WHERE character_id = ?
        """,
        (str(CHARACTER_ID),),
    ).fetchone()[0]
    revision_three_count = raw.execute(
        """
        SELECT COUNT(*) FROM character_holdings_revisions
        WHERE character_id = ? AND holdings_revision = 3
        """,
        (str(CHARACTER_ID),),
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        raw.execute(
            """
            UPDATE character_definitions SET definition_digest = ?
            WHERE character_id = ? AND definition_revision = 1
            """,
            ("d" * 64, str(CHARACTER_ID)),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        raw.execute(
            """
            UPDATE character_holdings_revisions SET holdings_digest = ?
            WHERE character_id = ? AND holdings_revision = 1
            """,
            ("d" * 64, str(CHARACTER_ID)),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        raw.execute(
            """
            UPDATE character_loadout_revisions SET loadout_digest = ?
            WHERE character_id = ? AND loadout_revision = 1
            """,
            ("d" * 64, str(CHARACTER_ID)),
        )
    raw.close()
    repository.close()

    assert advanced.current_holdings_revision == 2
    assert advanced.current_holdings_digest == revision_two.holdings_digest
    assert advanced.row_version == created.row_version + 1
    assert revision_one_row.holdings == _holdings()
    assert revision_two_row.holdings == revision_two
    assert holdings_count == 2
    assert revision_three_count == 0


def test_exclusive_lease_release_reacquire_and_pinned_deployment(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "directory.sqlite3")
    principal = _principal(repository)
    created = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    advanced = repository.append_character_holdings_revision(
        _holdings(revision=2, quantity=2),
        expected_holdings_revision=1,
        expected_holdings_digest=created.current_holdings_digest,
        expected_row_version=created.row_version,
    )
    first_game, first_membership = _game_and_membership(
        repository,
        principal.principal_id,
    )
    second_game, second_membership = _game_and_membership(
        repository,
        principal.principal_id,
    )
    first_lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=first_game.game_id,
            membership_id=first_membership.membership_id,
        ),
    )
    with pytest.raises(ConflictError, match="active deployment lease"):
        repository.acquire_character_deployment_lease(
            CharacterDeploymentLeaseCreate(
                character_id=CHARACTER_ID,
                game_id=second_game.game_id,
                membership_id=second_membership.membership_id,
            ),
        )

    released = repository.release_character_deployment_lease(
        first_lease.lease_id,
        release_reason="interrupted",
    )
    second_lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=second_game.game_id,
            membership_id=second_membership.membership_id,
        ),
    )
    deployment = repository.deploy_character_pinned(
        PinnedCharacterDeploymentCreate(
            lease_id=second_lease.lease_id,
            game_id=second_game.game_id,
            membership_id=second_membership.membership_id,
            character_id=CHARACTER_ID,
            entity_uuid=uuid4(),
        ),
        expected_character_row_version=advanced.row_version,
        expected_heads=_heads(advanced),
    )
    repository.close()

    assert released.released_at == NOW
    assert released.release_reason == "interrupted"
    assert second_lease.released_at is None
    assert deployment.lease_id == second_lease.lease_id
    assert deployment.definition_revision == advanced.current_definition_revision
    assert deployment.definition_digest == advanced.current_definition_digest
    assert deployment.holdings_revision == advanced.current_holdings_revision
    assert deployment.holdings_digest == advanced.current_holdings_digest
    assert deployment.loadout_revision == advanced.current_loadout_revision
    assert deployment.loadout_digest == advanced.current_loadout_digest


def test_lease_requires_the_active_controlling_membership_of_the_character_owner(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "directory.sqlite3")
    owner = _principal(repository)
    other_principal = _principal(repository)
    repository.create_character_with_revisions(
        _bootstrap(owner.principal_id),
    )

    other_game, other_membership = _game_and_membership(
        repository,
        other_principal.principal_id,
    )
    with pytest.raises(ConflictError, match="character owner"):
        repository.acquire_character_deployment_lease(
            CharacterDeploymentLeaseCreate(
                character_id=CHARACTER_ID,
                game_id=other_game.game_id,
                membership_id=other_membership.membership_id,
            ),
        )

    no_control_game = repository.create_game(
        GameCreate(
            created_by_principal_id=owner.principal_id,
            scenario_kind="test",
            scenario_id="no-control-membership",
            display_name="No Control Membership",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest="c" * 64,
        ),
    )
    no_control_membership = repository.create_membership(
        MembershipCreate(
            game_id=no_control_game.game_id,
            principal_id=owner.principal_id,
            role=MembershipRole.OBSERVER,
            capabilities=MembershipCapabilities(may_control_entities=False),
        ),
    )
    with pytest.raises(ConflictError, match="entity-control authority"):
        repository.acquire_character_deployment_lease(
            CharacterDeploymentLeaseCreate(
                character_id=CHARACTER_ID,
                game_id=no_control_game.game_id,
                membership_id=no_control_membership.membership_id,
            ),
        )

    revoked_game, revoked_membership = _game_and_membership(
        repository,
        owner.principal_id,
    )
    repository.update_membership_authority(
        revoked_membership.membership_id,
        expected_authority_epoch=revoked_membership.authority_epoch,
        membership_state=MembershipState.REVOKED,
        capabilities=MembershipCapabilities(),
    )
    with pytest.raises(ConflictError, match="active membership"):
        repository.acquire_character_deployment_lease(
            CharacterDeploymentLeaseCreate(
                character_id=CHARACTER_ID,
                game_id=revoked_game.game_id,
                membership_id=revoked_membership.membership_id,
            ),
        )
    repository.close()


def test_released_lease_is_idempotent_but_cannot_authorize_a_deployment(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "directory.sqlite3")
    principal = _principal(repository)
    created = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    game, membership = _game_and_membership(repository, principal.principal_id)
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )

    released = repository.release_character_deployment_lease(
        lease.lease_id,
        release_reason="interrupted",
    )
    exact_retry = repository.release_character_deployment_lease(
        lease.lease_id,
        release_reason="interrupted",
    )
    with pytest.raises(ConflictError, match="different reason"):
        repository.release_character_deployment_lease(
            lease.lease_id,
            release_reason="settled",
        )
    with pytest.raises(ConflictError, match="active lease"):
        repository.deploy_character_pinned(
            PinnedCharacterDeploymentCreate(
                lease_id=lease.lease_id,
                game_id=game.game_id,
                membership_id=membership.membership_id,
                character_id=CHARACTER_ID,
                entity_uuid=uuid4(),
            ),
            expected_character_row_version=created.row_version,
            expected_heads=_heads(created),
        )
    repository.close()

    assert exact_retry == released


def test_pinned_deployment_rejects_a_lease_tuple_mismatch(
    tmp_path: Path,
) -> None:
    repository = _open(tmp_path / "directory.sqlite3")
    principal = _principal(repository)
    created = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    game, membership = _game_and_membership(repository, principal.principal_id)
    other_game, other_membership = _game_and_membership(
        repository,
        principal.principal_id,
    )
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )

    mismatches = (
        {
            "game_id": other_game.game_id,
            "membership_id": membership.membership_id,
            "character_id": CHARACTER_ID,
        },
        {
            "game_id": game.game_id,
            "membership_id": other_membership.membership_id,
            "character_id": CHARACTER_ID,
        },
        {
            "game_id": game.game_id,
            "membership_id": membership.membership_id,
            "character_id": uuid4(),
        },
    )
    for mismatch in mismatches:
        with pytest.raises(ConflictError, match="does not match its lease"):
            repository.deploy_character_pinned(
                PinnedCharacterDeploymentCreate(
                    lease_id=lease.lease_id,
                    entity_uuid=uuid4(),
                    **mismatch,
                ),
                expected_character_row_version=created.row_version,
                expected_heads=_heads(created),
            )
    repository.close()


def test_canonical_heads_and_all_pinned_deployment_lineage_are_immutable(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    principal = _principal(repository)
    created = repository.create_character_with_revisions(
        _bootstrap(principal.principal_id),
    )
    game, membership = _game_and_membership(repository, principal.principal_id)
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=CHARACTER_ID,
            game_id=game.game_id,
            membership_id=membership.membership_id,
        ),
    )
    deployment = repository.deploy_character_pinned(
        PinnedCharacterDeploymentCreate(
            lease_id=lease.lease_id,
            game_id=game.game_id,
            membership_id=membership.membership_id,
            character_id=CHARACTER_ID,
            entity_uuid=uuid4(),
        ),
        expected_character_row_version=created.row_version,
        expected_heads=_heads(created),
    )

    raw = sqlite3.connect(database_path)
    raw.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError, match="cannot become legacy"):
        raw.execute(
            """
            UPDATE characters
            SET revision_state = 'legacy_pending',
                current_definition_revision = NULL,
                current_definition_digest = NULL,
                current_holdings_revision = NULL,
                current_holdings_digest = NULL,
                current_loadout_revision = NULL,
                current_loadout_digest = NULL
            WHERE character_id = ?
            """,
            (str(CHARACTER_ID),),
        )

    immutable_columns = (
        "deployment_id",
        "game_id",
        "membership_id",
        "character_id",
        "entity_uuid",
        "deployed_at",
        "lease_id",
        "pin_state",
        "definition_revision",
        "definition_digest",
        "holdings_revision",
        "holdings_digest",
        "loadout_revision",
        "loadout_digest",
    )
    for column in immutable_columns:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            raw.execute(
                f"""
                UPDATE character_deployments SET {column} = {column}
                WHERE deployment_id = ?
                """,
                (str(deployment.deployment_id),),
            )

    immutable_deletes = (
        (
            "character_definitions",
            "character_id = ? AND definition_revision = 1",
            (str(CHARACTER_ID),),
        ),
        (
            "character_holdings_revisions",
            "character_id = ? AND holdings_revision = 1",
            (str(CHARACTER_ID),),
        ),
        (
            "character_loadout_revisions",
            "character_id = ? AND loadout_revision = 1",
            (str(CHARACTER_ID),),
        ),
        (
            "character_deployment_leases",
            "lease_id = ?",
            (str(lease.lease_id),),
        ),
        (
            "character_deployments",
            "deployment_id = ?",
            (str(deployment.deployment_id),),
        ),
    )
    for table, predicate, parameters in immutable_deletes:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            raw.execute(f"DELETE FROM {table} WHERE {predicate}", parameters)
    raw.close()
    repository.close()


def test_injected_mid_transaction_failure_leaves_no_partial_character_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    principal = _principal(repository)
    raw = sqlite3.connect(database_path)
    raw.execute(
        """
        CREATE TRIGGER inject_character_holdings_failure
        BEFORE INSERT ON character_holdings_revisions
        BEGIN
            SELECT RAISE(ABORT, 'injected character transaction failure');
        END
        """,
    )
    raw.commit()
    raw.close()

    with pytest.raises(ConflictError, match="injected character transaction failure"):
        repository.create_character_with_revisions(
            _bootstrap(principal.principal_id),
        )

    raw = sqlite3.connect(database_path)
    counts = raw.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM characters WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_definitions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_holdings_revisions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_loadout_revisions WHERE character_id = ?),
          (SELECT COUNT(*) FROM character_advancement_awards WHERE character_id = ?)
        """,
        (
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
            str(CHARACTER_ID),
        ),
    ).fetchone()
    raw.close()
    repository.close()

    assert tuple(counts) == (0, 0, 0, 0, 0)
