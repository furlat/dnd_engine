"""Focused contract tests for safe local-profile directory ownership."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from server.game_directory import (
    GameDirectoryRepository,
    ImmutableRecordError,
)
from server.game_directory.contracts import PrincipalCreate, PrincipalKind
from server.game_directory.local_profiles import LocalProfileManager


PEPPER = b"local-profile-manager-test-pepper"
RULESET_DIGEST = character_ruleset_digest(
    permissive_multiclass_prerequisites=True,
    multiclass_slot_rounding_policy=(
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    ),
)


def _manager(tmp_path: Path) -> LocalProfileManager:
    return LocalProfileManager(
        runtime_root=tmp_path / ".runtime",
        capability_pepper=PEPPER,
    )


def _repository(database_path: Path) -> GameDirectoryRepository:
    return GameDirectoryRepository(
        database_path,
        capability_pepper=PEPPER,
    )


def test_create_list_and_reopen_profile_owns_exact_safe_layout(
    tmp_path: Path,
) -> None:
    """Creation publishes one complete UUID-owned profile and no caller path."""

    manager = _manager(tmp_path)
    profile_id = uuid4()

    created = manager.create_profile(
        "  Tommaso   Local  ",
        profile_id=profile_id,
    )
    expected_root = tmp_path / ".runtime" / "profiles" / str(profile_id)

    assert created.profile_id == profile_id
    assert created.display_name == "Tommaso Local"
    assert created.profile_root == expected_root.resolve()
    assert created.database_path == expected_root.resolve() / "profile.sqlite3"
    assert created.artifacts_root == expected_root.resolve() / "artifacts"
    assert created.exports_root == expected_root.resolve() / "exports"
    assert created.database_path.is_file()
    assert created.artifacts_root.is_dir()
    assert created.exports_root.is_dir()

    principal = created.repository.get_principal(profile_id)
    settings = created.repository.get_profile_settings(profile_id)
    assert principal.principal_id == profile_id
    assert principal.principal_kind is PrincipalKind.HUMAN
    assert principal.display_name == "Tommaso Local"
    assert settings.owner_principal_id == profile_id
    assert settings.ruleset_digest == RULESET_DIGEST
    assert settings.permissive_multiclass_prerequisites is True
    assert settings.allow_respec is True
    created.close()
    created.close()

    assert manager.list_profiles() == (
        manager.profile_summary(profile_id),
    )

    with manager.open_profile(profile_id) as reopened:
        assert reopened.profile_id == profile_id
        assert reopened.display_name == "Tommaso Local"
        assert reopened.repository.get_profile_settings(profile_id) == settings

    with pytest.raises(RuntimeError, match="database is closed"):
        reopened.repository.get_principal(profile_id)


def test_create_rejects_non_uuid_handles_and_never_accepts_paths(
    tmp_path: Path,
) -> None:
    """Only UUID handles can select filesystem state."""

    manager = _manager(tmp_path)

    with pytest.raises(TypeError, match="profile_id must be a UUID"):
        manager.create_profile("Player", profile_id="../../outside")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="profile_id must be a UUID"):
        manager.open_profile("../../outside")  # type: ignore[arg-type]

    assert tuple(manager.profiles_root.iterdir()) == ()


@pytest.mark.parametrize("case", ["zero", "multiple", "mismatched"])
def test_open_rejects_invalid_human_principal_ownership(
    tmp_path: Path,
    case: str,
) -> None:
    """A local DB must contain one human whose ID equals its UUID directory."""

    manager = _manager(tmp_path)
    profile_id = uuid4()
    profile_root = manager.profiles_root / str(profile_id)
    profile_root.mkdir()
    (profile_root / "artifacts").mkdir()
    (profile_root / "exports").mkdir()
    repository = _repository(profile_root / "profile.sqlite3")

    if case == "multiple":
        repository.create_principal(
            PrincipalCreate(
                principal_id=profile_id,
                principal_kind=PrincipalKind.HUMAN,
                display_name="Owner",
            ),
        )
        repository.create_principal(
            PrincipalCreate(
                principal_kind=PrincipalKind.HUMAN,
                display_name="Other human",
            ),
        )
    elif case == "mismatched":
        repository.create_principal(
            PrincipalCreate(
                principal_kind=PrincipalKind.HUMAN,
                display_name="Wrong owner",
            ),
        )
    repository.close()

    with pytest.raises(
        ImmutableRecordError,
        match="exactly one human principal|does not match",
    ):
        manager.open_profile(profile_id)


@pytest.mark.parametrize("missing", ["identity", "settings"])
def test_open_rejects_missing_player_identity_or_settings(
    tmp_path: Path,
    missing: str,
) -> None:
    """The owning human, local identity, and rules settings form one profile."""

    manager = _manager(tmp_path)
    profile_id = uuid4()
    profile_root = manager.profiles_root / str(profile_id)
    profile_root.mkdir()
    (profile_root / "artifacts").mkdir()
    (profile_root / "exports").mkdir()
    repository = _repository(profile_root / "profile.sqlite3")
    repository.create_principal(
        PrincipalCreate(
            principal_id=profile_id,
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    repository.close()

    if missing == "settings":
        connection = sqlite3.connect(profile_root / "profile.sqlite3")
        try:
            connection.execute(
                """
                INSERT INTO player_identities(
                    identity_key, principal_id, display_name, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "owner",
                    str(profile_id),
                    "Owner",
                    "2026-07-26T00:00:00+00:00",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    expected = (
        "exactly one player identity"
        if missing == "identity"
        else "has no profile settings"
    )
    with pytest.raises(ImmutableRecordError, match=expected):
        manager.open_profile(profile_id)


def test_list_fails_closed_on_noncanonical_profile_directory(
    tmp_path: Path,
) -> None:
    """Dedicated profile storage cannot silently hide malformed directories."""

    manager = _manager(tmp_path)
    (manager.profiles_root / "not-a-profile").mkdir()

    with pytest.raises(ImmutableRecordError, match="not a canonical UUID"):
        manager.list_profiles()


def test_open_rejects_symlinked_profile_storage(
    tmp_path: Path,
) -> None:
    """A UUID handle cannot traverse a symlink to storage outside the root."""

    manager = _manager(tmp_path)
    profile_id = uuid4()
    outside = tmp_path / "outside"
    outside.mkdir()
    (manager.profiles_root / str(profile_id)).symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(ImmutableRecordError, match="symbolic link"):
        manager.open_profile(profile_id)


def test_profile_creation_is_not_published_when_initialization_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed settings write leaves neither a selectable nor partial profile."""

    manager = _manager(tmp_path)
    profile_id = uuid4()

    def fail_settings(*args: object, **kwargs: object) -> object:
        raise RuntimeError("injected settings failure")

    monkeypatch.setattr(
        GameDirectoryRepository,
        "create_profile_settings",
        fail_settings,
    )

    with pytest.raises(RuntimeError, match="injected settings failure"):
        manager.create_profile("Player", profile_id=profile_id)

    assert not (manager.profiles_root / str(profile_id)).exists()
    assert manager.list_profiles() == ()
    assert not any(path.name.startswith(".creating-") for path in manager.profiles_root.iterdir())


def test_open_rejects_identity_bound_to_a_non_owner(
    tmp_path: Path,
) -> None:
    """A player identity cannot authenticate a different local principal."""

    manager = _manager(tmp_path)
    profile_id = uuid4()
    profile_root = manager.profiles_root / str(profile_id)
    profile_root.mkdir()
    (profile_root / "artifacts").mkdir()
    (profile_root / "exports").mkdir()
    repository = _repository(profile_root / "profile.sqlite3")
    repository.create_principal(
        PrincipalCreate(
            principal_id=profile_id,
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    other_id = uuid4()
    repository.resolve_player_identity(
        "other",
        PrincipalCreate(
            principal_id=other_id,
            principal_kind=PrincipalKind.SERVICE,
            display_name="Other",
        ),
    )
    repository.close()

    connection = sqlite3.connect(profile_root / "profile.sqlite3")
    try:
        connection.execute(
            """
            INSERT INTO profile_settings(
                owner_principal_id,
                permissive_multiclass_prerequisites,
                multiclass_slot_rounding_policy,
                allow_respec,
                spell_preparation_policy,
                settings_version,
                ruleset_digest,
                updated_at
            ) VALUES (?, 1, 'srd_5_2_round_up', 1, 'long_rest', 1, ?, ?)
            """,
            (str(profile_id), RULESET_DIGEST, "2026-07-26T00:00:00+00:00"),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ImmutableRecordError, match="does not belong"):
        manager.open_profile(profile_id)
