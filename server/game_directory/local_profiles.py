"""Safe filesystem ownership for standalone local player profiles."""

from __future__ import annotations

import shutil
import sqlite3
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from server.game_directory.security import utc_now
from server.game_directory.contracts import (
    PrincipalCreate,
    PrincipalKind,
    ProfileSettingsCreate,
    SpellPreparationPolicy,
)
from server.game_directory.errors import (
    ConflictError,
    ImmutableRecordError,
    NotFoundError,
)
from server.game_directory.repository import GameDirectoryRepository


@dataclass(frozen=True, slots=True)
class LocalProfileSummary:
    """Path-free launcher metadata for one valid local profile."""

    profile_id: UUID
    display_name: str


@dataclass(slots=True)
class LocalProfileHandle:
    """One validated profile and its owned open directory repository."""

    profile_id: UUID
    display_name: str
    profile_root: Path
    database_path: Path
    artifacts_root: Path
    exports_root: Path
    repository: GameDirectoryRepository
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Close the profile database idempotently."""

        if not self._closed:
            self.repository.close()
            self._closed = True

    def __enter__(self) -> LocalProfileHandle:
        """Return this already-open profile handle."""

        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        """Always close the owned database connection."""

        self.close()


class LocalProfileManager:
    """Allocate and open server-owned standalone profile databases.

    Callers select profiles only by UUID. The configured ``runtime_root`` is
    server deployment state and is never accepted by a profile operation.
    """

    def __init__(
        self,
        *,
        capability_pepper: bytes,
        runtime_root: str | Path = ".runtime",
        busy_timeout_ms: int = 2_000,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """Create a local-only profile manager rooted below runtime storage."""

        if not capability_pepper:
            raise ValueError("capability_pepper cannot be empty")
        self._capability_pepper = bytes(capability_pepper)
        self._busy_timeout_ms = busy_timeout_ms
        self._clock = clock
        self.profiles_root = (Path(runtime_root) / "profiles").resolve()
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        if self.profiles_root.is_symlink():
            raise ImmutableRecordError(
                "Local profile storage root cannot be a symbolic link",
            )

    def create_profile(
        self,
        display_name: str,
        *,
        profile_id: UUID | None = None,
        permissive_multiclass_prerequisites: bool = True,
        multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy = (
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
        allow_respec: bool = True,
        spell_preparation_policy: SpellPreparationPolicy = (
            SpellPreparationPolicy.LONG_REST
        ),
    ) -> LocalProfileHandle:
        """Create and atomically publish one complete local profile."""

        selected_profile_id = uuid4() if profile_id is None else profile_id
        self._require_uuid(selected_profile_id)
        normalized_display_name = " ".join(display_name.split())
        if not normalized_display_name:
            raise ValueError("display_name cannot be blank")

        profile_root = self._profile_path(selected_profile_id)
        if profile_root.exists() or profile_root.is_symlink():
            raise ConflictError(
                f"Local profile {selected_profile_id} already exists",
            )

        staging_root = self.profiles_root / (
            f".creating-{selected_profile_id}-{uuid4()}"
        )
        repository: GameDirectoryRepository | None = None
        try:
            staging_root.mkdir(mode=0o700)
            artifacts_root = staging_root / "artifacts"
            exports_root = staging_root / "exports"
            artifacts_root.mkdir(mode=0o700)
            exports_root.mkdir(mode=0o700)
            database_path = staging_root / "profile.sqlite3"
            repository = self._open_repository(database_path)
            identity_key = unicodedata.normalize(
                "NFKC",
                normalized_display_name,
            ).casefold()
            principal, identity = repository.resolve_player_identity(
                identity_key,
                PrincipalCreate(
                    principal_id=selected_profile_id,
                    principal_kind=PrincipalKind.HUMAN,
                    display_name=normalized_display_name,
                    metadata={
                        "authentication_kind": "local_profile",
                        "profile_id": str(selected_profile_id),
                    },
                ),
            )
            if (
                principal.principal_id != selected_profile_id
                or identity.principal_id != selected_profile_id
            ):
                raise ImmutableRecordError(
                    "New local profile identity does not match its profile ID",
                )
            repository.create_profile_settings(
                ProfileSettingsCreate(
                    owner_principal_id=selected_profile_id,
                    permissive_multiclass_prerequisites=(
                        permissive_multiclass_prerequisites
                    ),
                    multiclass_slot_rounding_policy=(
                        multiclass_slot_rounding_policy
                    ),
                    allow_respec=allow_respec,
                    spell_preparation_policy=spell_preparation_policy,
                    ruleset_digest=character_ruleset_digest(
                        permissive_multiclass_prerequisites=(
                            permissive_multiclass_prerequisites
                        ),
                        multiclass_slot_rounding_policy=(
                            multiclass_slot_rounding_policy
                        ),
                    ),
                ),
            )
            repository.close()
            repository = None
            self._audit_profile_database(
                selected_profile_id,
                database_path,
            )
            try:
                staging_root.rename(profile_root)
            except FileExistsError as exc:
                raise ConflictError(
                    f"Local profile {selected_profile_id} already exists",
                ) from exc
        except Exception:
            if repository is not None:
                repository.close()
            self._discard_staging_directory(staging_root)
            raise

        return self.open_profile(selected_profile_id)

    def open_profile(self, profile_id: UUID) -> LocalProfileHandle:
        """Open one validated profile selected only by UUID."""

        self._require_uuid(profile_id)
        profile_root = self._profile_path(profile_id)
        self._validate_profile_layout(profile_id, profile_root)
        database_path = profile_root / "profile.sqlite3"
        repository = self._open_repository(database_path)
        try:
            display_name = self._audit_profile_database(
                profile_id,
                database_path,
            )
            principal = repository.get_principal(profile_id)
            if principal.principal_kind is not PrincipalKind.HUMAN:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} owner is not human",
                )
            try:
                settings = repository.get_profile_settings(profile_id)
            except NotFoundError as exc:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} has no profile settings",
                ) from exc
            if settings.owner_principal_id != profile_id:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} settings owner does not match",
                )
        except Exception:
            repository.close()
            raise

        return LocalProfileHandle(
            profile_id=profile_id,
            display_name=display_name,
            profile_root=profile_root,
            database_path=database_path,
            artifacts_root=profile_root / "artifacts",
            exports_root=profile_root / "exports",
            repository=repository,
        )

    def list_profiles(self) -> tuple[LocalProfileSummary, ...]:
        """List every complete profile after validating its physical owner."""

        profile_ids: list[UUID] = []
        for child in sorted(self.profiles_root.iterdir(), key=lambda path: path.name):
            if child.name.startswith(".creating-"):
                continue
            if not child.is_dir() and not child.is_symlink():
                continue
            profile_ids.append(self._profile_id_from_directory(child))
        return tuple(self.profile_summary(profile_id) for profile_id in profile_ids)

    def profile_summary(self, profile_id: UUID) -> LocalProfileSummary:
        """Read path-free launcher metadata for one profile."""

        with self.open_profile(profile_id) as profile:
            return LocalProfileSummary(
                profile_id=profile.profile_id,
                display_name=profile.display_name,
            )

    def _open_repository(self, database_path: Path) -> GameDirectoryRepository:
        """Open the existing typed repository with deployment-owned settings."""

        return GameDirectoryRepository(
            database_path,
            capability_pepper=self._capability_pepper,
            busy_timeout_ms=self._busy_timeout_ms,
            clock=self._clock,
        )

    def _profile_path(self, profile_id: UUID) -> Path:
        """Return the canonical child path for one already-validated UUID."""

        profile_root = self.profiles_root / str(profile_id)
        if profile_root.parent != self.profiles_root:
            raise ImmutableRecordError("Local profile path escaped its storage root")
        return profile_root

    def _validate_profile_layout(
        self,
        profile_id: UUID,
        profile_root: Path,
    ) -> None:
        """Reject missing, linked, or incomplete profile storage."""

        if profile_root.is_symlink():
            raise ImmutableRecordError(
                f"Local profile {profile_id} cannot be a symbolic link",
            )
        if not profile_root.exists():
            raise NotFoundError(f"Local profile {profile_id} does not exist")
        if not profile_root.is_dir():
            raise ImmutableRecordError(
                f"Local profile {profile_id} storage is not a directory",
            )
        if profile_root.name != str(profile_id):
            raise ImmutableRecordError(
                f"Local profile directory {profile_root.name!r} does not match its UUID",
            )
        for name, expected_kind in (
            ("profile.sqlite3", "file"),
            ("artifacts", "directory"),
            ("exports", "directory"),
        ):
            path = profile_root / name
            if path.is_symlink():
                raise ImmutableRecordError(
                    f"Local profile {profile_id} {name} cannot be a symbolic link",
                )
            valid = path.is_file() if expected_kind == "file" else path.is_dir()
            if not valid:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} requires {name} as a {expected_kind}",
                )

    def _audit_profile_database(
        self,
        profile_id: UUID,
        database_path: Path,
    ) -> str:
        """Read-only audit identity cardinality not exposed by the repository."""

        connection = sqlite3.connect(
            f"{database_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            human_rows = connection.execute(
                """
                SELECT principal_id, display_name
                FROM principals
                WHERE principal_kind = ?
                ORDER BY principal_id
                """,
                (PrincipalKind.HUMAN.value,),
            ).fetchall()
            if len(human_rows) != 1:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} requires exactly one human principal",
                )
            human_row = human_rows[0]
            if human_row["principal_id"] != str(profile_id):
                raise ImmutableRecordError(
                    f"Local profile human principal {human_row['principal_id']} "
                    f"does not match directory {profile_id}",
                )

            identity_rows = connection.execute(
                """
                SELECT identity_key, principal_id, display_name
                FROM player_identities
                ORDER BY identity_key
                """,
            ).fetchall()
            if len(identity_rows) != 1:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} requires exactly one player identity",
                )
            identity_row = identity_rows[0]
            if identity_row["principal_id"] != str(profile_id):
                raise ImmutableRecordError(
                    f"Local profile player identity does not belong to owner {profile_id}",
                )
            if identity_row["display_name"] != human_row["display_name"]:
                raise ImmutableRecordError(
                    f"Local profile {profile_id} identity display name does not match",
                )
            return str(human_row["display_name"])
        finally:
            connection.close()

    def _profile_id_from_directory(self, profile_root: Path) -> UUID:
        """Parse one canonical UUID directory name without following links."""

        if profile_root.is_symlink():
            raise ImmutableRecordError(
                f"Local profile directory {profile_root.name!r} is a symbolic link",
            )
        try:
            profile_id = UUID(profile_root.name)
        except ValueError as exc:
            raise ImmutableRecordError(
                f"Local profile directory {profile_root.name!r} is not a canonical UUID",
            ) from exc
        if str(profile_id) != profile_root.name:
            raise ImmutableRecordError(
                f"Local profile directory {profile_root.name!r} is not a canonical UUID",
            )
        return profile_id

    def _discard_staging_directory(self, staging_root: Path) -> None:
        """Remove only this manager's unpublished, exact staging directory."""

        if (
            staging_root.parent == self.profiles_root
            and staging_root.name.startswith(".creating-")
            and staging_root.exists()
            and not staging_root.is_symlink()
        ):
            shutil.rmtree(staging_root)

    @staticmethod
    def _require_uuid(profile_id: object) -> None:
        """Reject path-like or string selectors at the filesystem boundary."""

        if not isinstance(profile_id, UUID):
            raise TypeError("profile_id must be a UUID")
