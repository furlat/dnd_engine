"""Pydantic contracts for the game-directory control plane."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dnd.analytics.models import GameSummary
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)
from dnd.core.content.encounters import (
    EncounterRecipe,
    EncounterRosterRecipe,
)
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from server.game_directory.canonical import canonical_digest

JsonObject = dict[str, JsonValue]


class DirectoryModel(BaseModel):
    """Strict immutable base model for persisted directory contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PrincipalKind(str, Enum):
    """Kinds of durable identities recognized by the directory."""

    HUMAN = "human"
    CODEX = "codex"
    SERVICE = "service"
    SYSTEM_AI = "system_ai"


class CharacterStatus(str, Enum):
    """Lifecycle states for one player-owned persistent character."""

    ACTIVE = "active"
    RETIRED = "retired"


class CharacterRevisionState(str, Enum):
    """Durable revision readiness for a character row."""

    LEGACY_PENDING = "legacy_pending"
    CANONICAL = "canonical"


class SpellPreparationPolicy(str, Enum):
    """When a profile permits a persistent prepared-spell loadout change."""

    LONG_REST = "long_rest"
    OUT_OF_COMBAT = "out_of_combat"


class CharacterAdvancementSourceKind(str, Enum):
    """Audited sources that may grant persistent character levels."""

    CREATION = "creation"
    GAME_REWARD = "game_reward"
    DEVELOPER = "developer"
    MIGRATION = "migration"


class WorkerState(str, Enum):
    """Lifecycle states for an isolated game worker."""

    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    ENDED = "ended"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    LOST = "lost"


class WorkerTransportKind(str, Enum):
    """Private transports supported between gateway and worker."""

    UNIX_SOCKET = "unix_socket"
    LOOPBACK_TCP = "loopback_tcp"


class GameLifecycleState(str, Enum):
    """Durable hosted-game lifecycle states."""

    RESERVED = "reserved"
    STARTING = "starting"
    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    ARCHIVED = "archived"


class VisibilityPolicy(str, Enum):
    """Discovery policy for a hosted game."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class ObserverPolicy(str, Enum):
    """Policy controlling observer attachment."""

    PUBLIC = "public"
    MEMBERS = "members"
    DISABLED = "disabled"


class ExecutionKind(str, Enum):
    """Origin and execution mode of a game record."""

    HOSTED = "hosted"
    LOCAL = "local"
    IMPORTED = "imported"


class MembershipRole(str, Enum):
    """Durable role of a principal inside a game."""

    OWNER = "owner"
    PLAYER = "player"
    OBSERVER = "observer"
    AGENT = "agent"
    REFEREE = "referee"
    ADMINISTRATOR = "administrator"


class MembershipState(str, Enum):
    """Lifecycle state of a game membership."""

    INVITED = "invited"
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    REVOKED = "revoked"
    LEFT = "left"


class GrantKind(str, Enum):
    """Single-purpose directory capability kinds."""

    INVITE = "invite"
    RECONNECT = "reconnect"
    OBSERVE = "observe"
    AGENT_ATTACH = "agent_attach"
    ADMIN = "admin"


class ClientKind(str, Enum):
    """Client kinds retained in attachment history."""

    NEUROCLIENT = "neuroclient"
    CODEX_CLI = "codex_cli"
    EXTERNAL_AI = "external_ai"
    OBSERVER_TOOL = "observer_tool"


class AttachmentState(str, Enum):
    """Lifecycle state of one concrete runtime attachment."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ArtifactKind(str, Enum):
    """Immutable game evidence artifact kinds."""

    CREATION_MANIFEST = "creation_manifest"
    OBJECTIVE_EVENT_HISTORY = "objective_event_history"
    COMBAT_LOG = "combat_log"
    SUBJECTIVE_TRANSCRIPT = "subjective_transcript"
    AGENT_TELEMETRY = "agent_telemetry"
    TERMINAL_SUMMARY = "terminal_summary"
    REPLAY_BUNDLE = "replay_bundle"
    SUBJECTIVE_REPLAY_BUNDLE = "subjective_replay_bundle"


class ProducerKind(str, Enum):
    """Kinds of processes that may publish immutable artifacts."""

    DIRECTORY = "directory"
    WORKER = "worker"
    IMPORTER = "importer"


class PrincipalCreate(DirectoryModel):
    """Input used to create a durable directory principal."""

    principal_id: UUID = Field(default_factory=uuid4, description="Stable principal identifier.")
    principal_kind: PrincipalKind = Field(description="Kind of identity represented by the principal.")
    display_name: str = Field(min_length=1, description="Human-readable principal name.")
    credential_hash: str | None = Field(default=None, description="Optional pre-hashed external credential.")
    metadata: JsonObject = Field(default_factory=dict, description="Canonical principal metadata.")


class PrincipalRecord(PrincipalCreate):
    """Persisted principal record."""

    metadata_digest: str = Field(description="SHA-256 digest of canonical metadata.")
    created_at: datetime = Field(description="UTC creation time.")
    last_seen_at: datetime | None = Field(default=None, description="UTC time of the latest authenticated use.")
    disabled_at: datetime | None = Field(default=None, description="UTC time when the principal was disabled.")


class PlayerIdentityRecord(DirectoryModel):
    """Stable name login bound to one durable human principal."""

    identity_key: str = Field(min_length=1, description="Normalized case-insensitive login name.")
    principal_id: UUID = Field(description="Durable principal owning this login name.")
    display_name: str = Field(min_length=1, description="Player-facing spelling of the name.")
    created_at: datetime = Field(description="UTC identity creation time.")


class PrincipalCredentialCreate(DirectoryModel):
    """Register one independently revocable client credential."""

    credential_id: UUID = Field(default_factory=uuid4, description="Stable credential identifier.")
    principal_id: UUID = Field(description="Principal authenticated by this credential.")
    client_instance_id: str = Field(min_length=1, max_length=160, description="Issuing client instance.")
    secret_hash: str = Field(min_length=1, description="HMAC digest of the client secret.")


class PrincipalCredentialRecord(PrincipalCredentialCreate):
    """Persisted client credential metadata without its plaintext secret."""

    issued_at: datetime = Field(description="UTC credential issuance time.")
    last_seen_at: datetime | None = Field(default=None, description="UTC latest authentication time.")
    revoked_at: datetime | None = Field(default=None, description="UTC credential revocation time.")


class ProfileSettingsCreate(DirectoryModel):
    """Create the rules policy owned by one player principal."""

    owner_principal_id: UUID
    permissive_multiclass_prerequisites: bool = True
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy = (
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    )
    allow_respec: bool = True
    spell_preparation_policy: SpellPreparationPolicy = (
        SpellPreparationPolicy.LONG_REST
    )
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_ruleset_digest(self) -> Self:
        expected = character_ruleset_digest(
            permissive_multiclass_prerequisites=(
                self.permissive_multiclass_prerequisites
            ),
            multiclass_slot_rounding_policy=(
                self.multiclass_slot_rounding_policy
            ),
        )
        if self.ruleset_digest != expected:
            raise ValueError(
                "ruleset_digest does not authenticate the selected "
                "character-build policy",
            )
        return self


class ProfileSettingsUpdate(ProfileSettingsCreate):
    """Replace profile rules policy through a settings-version CAS."""

    expected_settings_version: int = Field(ge=1)


class ProfileSettingsRecord(ProfileSettingsCreate):
    """Persisted profile rules policy."""

    settings_version: int = Field(ge=1)
    updated_at: datetime


class CharacterAdvancementAwardCreate(DirectoryModel):
    """Append one idempotent source-owned level entitlement."""

    award_id: UUID = Field(default_factory=uuid4)
    character_id: UUID
    level_delta: int = Field(gt=0)
    source_kind: CharacterAdvancementSourceKind
    source_id: str = Field(min_length=1)


class CharacterAdvancementAwardRecord(CharacterAdvancementAwardCreate):
    """Persisted immutable level entitlement."""

    created_at: datetime


class CharacterRevisionHeads(DirectoryModel):
    """One exact three-stream character CAS expectation."""

    definition_revision: int = Field(ge=1)
    definition_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdings_revision: int = Field(ge=1)
    holdings_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    loadout_revision: int = Field(ge=1)
    loadout_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CharacterRecord(DirectoryModel):
    """Persisted player character and its current revision."""

    character_id: UUID = Field(description="Stable character identifier.")
    owner_principal_id: UUID = Field(
        description="Principal that owns the character.",
    )
    display_name: str = Field(
        min_length=1,
        max_length=80,
        description="Player-facing character name.",
    )
    status: CharacterStatus = Field(
        default=CharacterStatus.ACTIVE,
        description="Character lifecycle state.",
    )
    revision_state: CharacterRevisionState = Field(
        default=CharacterRevisionState.LEGACY_PENDING,
        description="Whether all three exact durable heads are installed.",
    )
    current_definition_revision: int | None = Field(
        default=None,
        ge=1,
        description="Current immutable structural revision, when migrated.",
    )
    current_definition_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Digest of the current immutable structural revision.",
    )
    current_holdings_revision: int | None = Field(
        default=None,
        ge=1,
        description="Current immutable holdings revision, when migrated.",
    )
    current_holdings_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Digest of the current immutable holdings revision.",
    )
    current_loadout_revision: int | None = Field(
        default=None,
        ge=1,
        description="Current immutable prepared-feature loadout revision.",
    )
    current_loadout_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Digest of the current immutable loadout revision.",
    )
    created_at: datetime = Field(description="UTC character creation time.")
    updated_at: datetime = Field(description="UTC time of the latest character update.")
    row_version: int = Field(default=1, ge=1, description="Compare-and-swap character revision.")

    @model_validator(mode="after")
    def _validate_revision_heads(self) -> Self:
        """Require either an explicit legacy gap or six complete current heads."""

        heads = (
            self.current_definition_revision,
            self.current_definition_digest,
            self.current_holdings_revision,
            self.current_holdings_digest,
            self.current_loadout_revision,
            self.current_loadout_digest,
        )
        if self.revision_state is CharacterRevisionState.LEGACY_PENDING:
            if any(value is not None for value in heads):
                raise ValueError(
                    "legacy-pending characters cannot have revision heads",
                )
        elif any(value is None for value in heads):
            raise ValueError("canonical characters require complete revision heads")
        return self


class CharacterPresentationPreferencesRecord(DirectoryModel):
    """Character-scoped, non-mechanical frontend presentation preferences."""

    schema_version: Literal[1] = 1
    character_id: UUID
    owner_principal_id: UUID
    revision: int = Field(
        ge=0,
        description=(
            "Independent presentation-document revision; zero is the "
            "synthetic empty document before the first write."
        ),
    )
    preferences: JsonObject = Field(
        default_factory=dict,
        description=(
            "Flexible frontend-owned artistic preferences. This document "
            "does not participate in character mechanics or replication."
        ),
    )
    preferences_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_document(self) -> Self:
        if self.preferences_digest != canonical_digest(self.preferences):
            raise ValueError(
                "preferences_digest must authenticate preferences",
            )
        if self.revision == 0:
            if self.preferences or self.updated_at is not None:
                raise ValueError(
                    "revision-zero presentation preferences must be empty",
                )
        elif self.updated_at is None:
            raise ValueError(
                "persisted presentation preferences require updated_at",
            )
        return self


class SavedEncounterRosterCreate(DirectoryModel):
    """Create one owner-scoped reusable exact roster."""

    saved_roster_id: str = Field(min_length=1)
    owner_principal_id: UUID
    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRosterRecipe


class SavedEncounterRosterRecord(SavedEncounterRosterCreate):
    """Persisted exact roster with optimistic revision identity."""

    schema_version: Literal[1] = 1
    recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _validate_digest(self) -> Self:
        if self.recipe.recipe_digest != self.recipe_digest:
            raise ValueError("Saved roster digest must match its recipe")
        return self


class SavedEncounterRosterReplace(DirectoryModel):
    """Compare-and-swap replacement of one saved roster."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRosterRecipe
    expected_revision: int = Field(ge=1)
    expected_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SavedEncounterCreate(DirectoryModel):
    """Create one owner-scoped exact encounter recipe."""

    saved_encounter_id: str = Field(min_length=1)
    owner_principal_id: UUID
    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRecipe


class SavedEncounterRecord(SavedEncounterCreate):
    """Persisted exact encounter with optimistic revision identity."""

    schema_version: Literal[1] = 1
    recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _validate_digest(self) -> Self:
        if self.recipe.recipe_digest != self.recipe_digest:
            raise ValueError("Saved encounter digest must match its recipe")
        return self


class SavedEncounterReplace(DirectoryModel):
    """Compare-and-swap replacement of one saved encounter."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRecipe
    expected_revision: int = Field(ge=1)
    expected_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanonicalCharacterRecord(CharacterRecord):
    """Character row whose exact durable three-stream heads exist."""

    revision_state: Literal[CharacterRevisionState.CANONICAL] = (
        CharacterRevisionState.CANONICAL
    )
    current_definition_revision: int = Field(default=..., ge=1)
    current_definition_digest: str = Field(
        default=...,
        pattern=r"^[0-9a-f]{64}$",
    )
    current_holdings_revision: int = Field(default=..., ge=1)
    current_holdings_digest: str = Field(
        default=...,
        pattern=r"^[0-9a-f]{64}$",
    )
    current_loadout_revision: int = Field(default=..., ge=1)
    current_loadout_digest: str = Field(
        default=...,
        pattern=r"^[0-9a-f]{64}$",
    )


class CharacterBootstrapCreate(DirectoryModel):
    """Atomically create one character and all three revision-one streams."""

    character_id: UUID = Field(
        default_factory=uuid4,
        description="Stable character identifier shared by every revision.",
    )
    owner_principal_id: UUID = Field(
        description="Principal that owns the character.",
    )
    display_name: str = Field(
        min_length=1,
        max_length=80,
        description="Player-facing character name.",
    )
    definition: CharacterDefinitionRevisionV2 = Field(
        description="Immutable structural revision one.",
    )
    starter_holdings: CharacterHoldingsRevision = Field(
        description="Immutable starter holdings revision one.",
    )
    starter_loadout: CharacterLoadoutRevisionV1 = Field(
        description="Immutable starter loadout revision one.",
    )
    initial_advancement_award: CharacterAdvancementAwardCreate = Field(
        description="Creation-owned entitlement matching the initial build.",
    )
    status: CharacterStatus = Field(
        default=CharacterStatus.ACTIVE,
        description="Initial character lifecycle state.",
    )

    @model_validator(mode="after")
    def _validate_revision_one(self) -> Self:
        """Keep the atomic bootstrap identity and initial revisions exact."""

        if self.definition.character_id != self.character_id:
            raise ValueError("definition character_id must match character_id")
        if self.starter_holdings.character_id != self.character_id:
            raise ValueError("starter holdings character_id must match character_id")
        if self.starter_loadout.character_id != self.character_id:
            raise ValueError("starter loadout character_id must match character_id")
        if self.initial_advancement_award.character_id != self.character_id:
            raise ValueError(
                "initial advancement award character_id must match character_id",
            )
        if self.definition.definition_revision != 1:
            raise ValueError("character bootstrap requires definition revision 1")
        if self.starter_holdings.holdings_revision != 1:
            raise ValueError("character bootstrap requires holdings revision 1")
        if self.starter_loadout.loadout_revision != 1:
            raise ValueError("character bootstrap requires loadout revision 1")
        if (
            self.starter_loadout.based_on_definition_revision
            != self.definition.definition_revision
        ):
            raise ValueError(
                "starter loadout must be based on definition revision 1",
            )
        if (
            self.initial_advancement_award.source_kind
            is not CharacterAdvancementSourceKind.CREATION
            or self.initial_advancement_award.level_delta
            != self.definition.earned_character_level
        ):
            raise ValueError(
                "character bootstrap creation award must match the initial "
                "definition level",
            )
        return self


class CharacterDefinitionRecord(DirectoryModel):
    """One decoded immutable structural revision row."""

    definition: CharacterDefinitionRevisionV2
    created_at: datetime


class CharacterHoldingsRecord(DirectoryModel):
    """One decoded immutable holdings revision row."""

    holdings: CharacterHoldingsRevision
    created_at: datetime


class CharacterLoadoutRecord(DirectoryModel):
    """One decoded immutable loadout revision row."""

    loadout: CharacterLoadoutRevisionV1
    created_at: datetime


class CharacterSettlementCreate(DirectoryModel):
    """Exactly-once receipt for one deployment's holdings transition."""

    settlement_id: UUID = Field(default_factory=uuid4)
    deployment_id: UUID
    game_id: UUID
    character_id: UUID
    starting_holdings_revision: int = Field(ge=1)
    starting_holdings_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    resulting_holdings_revision: int = Field(ge=1)
    resulting_holdings_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    delta_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_holdings_transition(self) -> Self:
        if self.resulting_holdings_revision != self.starting_holdings_revision + 1:
            raise ValueError(
                "settlement resulting holdings revision must follow its start",
            )
        return self


class CharacterSettlementRecord(CharacterSettlementCreate):
    """Persisted immutable settlement receipt."""

    settled_at: datetime


class DirectoryMutationReceiptCreate(DirectoryModel):
    """Caller-owned idempotency identity for one durable directory mutation."""

    owner_principal_id: UUID
    idempotency_key: UUID
    operation_kind: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    scope_id: UUID
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class DirectoryMutationReceiptRecord(DirectoryMutationReceiptCreate):
    """Immutable successful result replayed for an exact mutation retry."""

    result_payload: JsonObject
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def _validate_result_digest(self) -> Self:
        if self.result_digest != canonical_digest(self.result_payload):
            raise ValueError("result_digest does not authenticate result_payload")
        return self


class CharacterRevisionBundleCommit(DirectoryModel):
    """One atomic compare-and-swap across character revision streams."""

    character_id: UUID
    expected_row_version: int = Field(ge=1)
    expected_heads: CharacterRevisionHeads
    require_no_active_deployment: bool = False
    new_definition: CharacterDefinitionRevisionV2 | None = None
    new_holdings: CharacterHoldingsRevision | None = None
    new_loadout: CharacterLoadoutRevisionV1 | None = None
    advancement_award: CharacterAdvancementAwardCreate | None = None
    settlement: CharacterSettlementCreate | None = None
    mutation_receipt: DirectoryMutationReceiptCreate | None = None

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        mutations = (
            self.new_definition,
            self.new_holdings,
            self.new_loadout,
            self.advancement_award,
            self.settlement,
        )
        if all(mutation is None for mutation in mutations):
            raise ValueError("character revision bundle cannot be empty")
        for revision in (
            self.new_definition,
            self.new_holdings,
            self.new_loadout,
        ):
            if revision is not None and revision.character_id != self.character_id:
                raise ValueError("revision character_id must match bundle character_id")
        if (
            self.advancement_award is not None
            and self.advancement_award.character_id != self.character_id
        ):
            raise ValueError(
                "advancement award character_id must match bundle character_id",
            )
        if (
            self.mutation_receipt is not None
            and self.mutation_receipt.scope_id != self.character_id
        ):
            raise ValueError(
                "mutation receipt scope_id must match bundle character_id",
            )
        if self.new_definition is not None:
            if (
                self.new_definition.definition_revision
                != self.expected_heads.definition_revision + 1
            ):
                raise ValueError(
                    "new definition revision must follow the expected head",
                )
            if self.new_loadout is None:
                raise ValueError(
                    "a new definition requires a matching replacement loadout",
                )
        if (
            self.new_holdings is not None
            and self.new_holdings.holdings_revision
            != self.expected_heads.holdings_revision + 1
        ):
            raise ValueError("new holdings revision must follow the expected head")
        if (
            self.new_loadout is not None
            and self.new_loadout.loadout_revision
            != self.expected_heads.loadout_revision + 1
        ):
            raise ValueError("new loadout revision must follow the expected head")
        resolved_definition_revision = (
            self.new_definition.definition_revision
            if self.new_definition is not None
            else self.expected_heads.definition_revision
        )
        if (
            self.new_loadout is not None
            and self.new_loadout.based_on_definition_revision
            != resolved_definition_revision
        ):
            raise ValueError(
                "new loadout must be based on the resulting definition head",
            )
        if self.settlement is not None:
            if self.settlement.character_id != self.character_id:
                raise ValueError(
                    "settlement character_id must match bundle character_id",
                )
            if self.new_holdings is None:
                raise ValueError("settlement requires a new holdings revision")
            if (
                self.settlement.starting_holdings_revision
                != self.expected_heads.holdings_revision
                or self.settlement.starting_holdings_digest
                != self.expected_heads.holdings_digest
                or self.settlement.resulting_holdings_revision
                != self.new_holdings.holdings_revision
                or self.settlement.resulting_holdings_digest
                != self.new_holdings.holdings_digest
            ):
                raise ValueError(
                    "settlement holdings must match the bundle transition",
                )
        return self


class CharacterDeploymentLeaseCreate(DirectoryModel):
    """Acquire exclusive live deployment authority for one character."""

    lease_id: UUID = Field(default_factory=uuid4)
    character_id: UUID
    game_id: UUID
    membership_id: UUID


class CharacterDeploymentLeaseRecord(CharacterDeploymentLeaseCreate):
    """Persisted acquisition and release history for one character lease."""

    acquired_at: datetime
    released_at: datetime | None = None
    release_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_release(self) -> Self:
        """Release timestamp and reason become visible atomically."""

        if (self.released_at is None) != (self.release_reason is None):
            raise ValueError(
                "lease release timestamp and reason must be set together",
            )
        return self


class PinnedCharacterDeploymentCreate(DirectoryModel):
    """Deploy a character under one matching active exclusive lease."""

    deployment_id: UUID = Field(
        default_factory=uuid4,
        description="Stable deployment identifier.",
    )
    game_id: UUID = Field(description="Game receiving the character.")
    membership_id: UUID = Field(
        description="Membership controlling the deployed character.",
    )
    character_id: UUID = Field(
        description="Persistent character entering the game.",
    )
    entity_uuid: UUID = Field(
        description="Runtime entity instantiated for this character.",
    )
    lease_id: UUID


class PinnedCharacterDeploymentRecord(PinnedCharacterDeploymentCreate):
    """Deployment history pinned to exact durable character heads."""

    pin_state: Literal["pinned"] = "pinned"
    definition_revision: int = Field(ge=1)
    definition_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdings_revision: int = Field(ge=1)
    holdings_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    loadout_revision: int = Field(ge=1)
    loadout_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    deployed_at: datetime


class WorkerCreate(DirectoryModel):
    """Input used to register an isolated game worker."""

    worker_id: UUID = Field(default_factory=uuid4, description="Stable worker identifier.")
    worker_generation: int = Field(default=1, ge=1, description="Monotonic generation for this worker identity.")
    state: WorkerState = Field(default=WorkerState.STARTING, description="Initial worker lifecycle state.")
    pid: int | None = Field(default=None, ge=1, description="Operating-system process identifier.")
    process_group_id: int | None = Field(default=None, ge=1, description="Process group used for descendant cleanup.")
    host_id: str = Field(min_length=1, description="Host identity that owns the worker.")
    transport_kind: WorkerTransportKind = Field(description="Private gateway-to-worker transport.")
    private_locator: str = Field(min_length=1, description="Private socket path or loopback endpoint.")
    lease_expires_at: datetime | None = Field(default=None, description="UTC worker lease expiry.")
    protocol_hash: str = Field(min_length=1, description="Hash of the worker protocol contract.")
    engine_version: str = Field(min_length=1, description="Engine version running in the worker.")


class WorkerRecord(WorkerCreate):
    """Persisted worker placement and lifecycle evidence."""

    started_at: datetime = Field(description="UTC registration/start time.")
    last_heartbeat_at: datetime | None = Field(default=None, description="UTC time of the latest heartbeat.")
    stopped_at: datetime | None = Field(default=None, description="UTC terminal process time.")
    failure_code: str | None = Field(default=None, description="Typed worker failure code.")
    failure_detail: JsonObject = Field(default_factory=dict, description="Canonical structured failure detail.")


class GameCreate(DirectoryModel):
    """Input used to reserve a hosted game in the directory."""

    game_id: UUID = Field(default_factory=uuid4, description="Directory-owned stable game identifier.")
    engine_game_id: UUID | None = Field(default=None, description="Worker engine game identifier once created.")
    worker_id: UUID | None = Field(default=None, description="Worker currently hosting the game.")
    worker_generation: int | None = Field(default=None, ge=1, description="Generation of the hosting worker.")
    created_by_principal_id: UUID = Field(description="Principal that requested game creation.")
    lifecycle_state: GameLifecycleState = Field(default=GameLifecycleState.RESERVED, description="Initial lifecycle state.")
    visibility_policy: VisibilityPolicy = Field(default=VisibilityPolicy.PRIVATE, description="Directory discovery policy.")
    observer_policy: ObserverPolicy = Field(default=ObserverPolicy.DISABLED, description="Observer attachment policy.")
    execution_kind: ExecutionKind = Field(default=ExecutionKind.HOSTED, description="Execution origin of the game.")
    scenario_kind: str = Field(min_length=1, description="Scenario source category.")
    scenario_id: str = Field(min_length=1, description="Stable scenario identifier.")
    display_name: str = Field(min_length=1, description="Human-readable game name.")
    creation_manifest: JsonObject = Field(description="Exact canonical launch request and resolved setup.")
    seed: int | None = Field(default=None, description="Deterministic game seed when supplied.")
    ruleset_version: str = Field(min_length=1, description="Ruleset identity used by the worker.")
    engine_version: str = Field(min_length=1, description="Engine version used by the worker.")
    content_digest: str = Field(min_length=1, description="Digest identifying content available to the game.")


class GameRecord(GameCreate):
    """Persisted game-directory record."""

    creation_manifest_digest: str = Field(description="SHA-256 digest of the canonical creation manifest.")
    created_at: datetime = Field(description="UTC reservation time.")
    started_at: datetime | None = Field(default=None, description="UTC time when the game became active.")
    ended_at: datetime | None = Field(default=None, description="UTC terminal encounter time.")
    archived_at: datetime | None = Field(default=None, description="UTC archival time.")
    terminal_reason: str | None = Field(default=None, description="Stable terminal reason code.")
    winner_side_id: str | None = Field(default=None, description="Winning side identity, if any.")
    final_event_cursor: int | None = Field(default=None, ge=0, description="Terminal objective-event cursor.")
    final_combat_log_cursor: int | None = Field(default=None, ge=0, description="Terminal combat-log cursor.")
    current_summary_digest: str | None = Field(default=None, description="Digest of the current immutable summary revision.")
    row_version: int = Field(default=1, ge=1, description="Compare-and-swap lifecycle version.")


class MembershipCapabilities(DirectoryModel):
    """Explicit durable authority granted to one game membership."""

    may_connect: bool = Field(default=True, description="Whether the member may establish runtime attachments.")
    may_observe_public_state: bool = Field(default=False, description="Whether public game state may be observed.")
    may_observe_subjective_state: bool = Field(default=False, description="Whether a subjective participant view may be observed.")
    may_control_entities: bool = Field(default=False, description="Whether the member may control assigned entities.")
    may_view_agent_telemetry: bool = Field(default=False, description="Whether agent telemetry may be observed.")
    may_manage_members: bool = Field(default=False, description="Whether memberships may be administered.")
    may_manage_game: bool = Field(default=False, description="Whether game lifecycle may be administered.")
    may_view_objective_replay: bool = Field(default=False, description="Whether objective replay evidence may be read.")


class MembershipCreate(DirectoryModel):
    """Input used to create durable authority inside one game."""

    membership_id: UUID = Field(default_factory=uuid4, description="Stable membership identifier.")
    game_id: UUID = Field(description="Game receiving the membership.")
    principal_id: UUID = Field(description="Principal receiving the membership.")
    role: MembershipRole = Field(description="Role of the principal in the game.")
    side_id: str | None = Field(default=None, description="Controlled or observed side identity.")
    controller_kind: str | None = Field(default=None, description="Controller implementation associated with the member.")
    membership_state: MembershipState = Field(default=MembershipState.ACTIVE, description="Initial membership lifecycle state.")
    capabilities: MembershipCapabilities = Field(description="Explicit authority flags.")
    subjective_source_membership_id: UUID | None = Field(default=None, description="Membership whose subjective view is followed.")
    authority_epoch: int = Field(default=1, ge=1, description="Monotonic authority version installed in workers.")


class MembershipRecord(MembershipCreate):
    """Persisted game membership and authority state."""

    joined_at: datetime = Field(description="UTC membership creation time.")
    disconnected_at: datetime | None = Field(default=None, description="UTC time the member disconnected.")
    revoked_at: datetime | None = Field(default=None, description="UTC authority revocation time.")
    left_at: datetime | None = Field(default=None, description="UTC voluntary departure time.")


class EntityAssignmentCreate(DirectoryModel):
    """Input used to bind one engine entity to a membership."""

    assignment_id: UUID = Field(default_factory=uuid4, description="Stable assignment identifier.")
    game_id: UUID = Field(description="Game containing the entity.")
    membership_id: UUID = Field(description="Membership receiving entity authority.")
    entity_uuid: UUID = Field(description="Worker entity identifier.")
    entity_name: str = Field(min_length=1, description="Entity display name retained for history.")
    faction: str | None = Field(default=None, description="Entity faction identity.")
    side_id: str | None = Field(default=None, description="Entity side identity.")
    controller_kind: str = Field(min_length=1, description="Controller kind installed for the entity.")
    authority_epoch: int = Field(default=1, ge=1, description="Authority epoch of this assignment.")


class EntityAssignmentRecord(EntityAssignmentCreate):
    """Persisted entity assignment history."""

    assigned_at: datetime = Field(description="UTC assignment time.")
    released_at: datetime | None = Field(default=None, description="UTC release time.")


class AccessGrantCreate(DirectoryModel):
    """Input used to issue a single-purpose directory capability."""

    grant_id: UUID = Field(default_factory=uuid4, description="Stable grant identifier.")
    game_id: UUID = Field(description="Game to which the capability is scoped.")
    membership_id: UUID | None = Field(default=None, description="Optional membership receiving the capability.")
    issued_to_principal_id: UUID | None = Field(default=None, description="Optional principal receiving the capability.")
    grant_kind: GrantKind = Field(description="Purpose of the capability.")
    scope: JsonObject = Field(default_factory=dict, description="Canonical capability scope.")
    expires_at: datetime | None = Field(default=None, description="UTC capability expiry.")
    max_uses: int | None = Field(default=None, ge=1, description="Maximum successful validations, if bounded.")
    issued_by_principal_id: UUID = Field(description="Principal that issued the capability.")


class AccessGrantRecord(AccessGrantCreate):
    """Persisted access grant containing only a secret digest."""

    secret_hash: str = Field(description="HMAC digest of the plaintext capability.")
    scope_digest: str = Field(description="SHA-256 digest of canonical scope.")
    issued_at: datetime = Field(description="UTC issuance time.")
    revoked_at: datetime | None = Field(default=None, description="UTC revocation time.")
    uses: int = Field(default=0, ge=0, description="Successful validations consumed.")


class IssuedAccessGrant(DirectoryModel):
    """One-time capability response returned by grant issuance."""

    grant: AccessGrantRecord = Field(description="Persisted grant metadata.")
    capability: str = Field(min_length=1, description="Plaintext capability returned exactly once.")


class AttachmentCreate(DirectoryModel):
    """Input used to retain one concrete runtime connection."""

    attachment_id: UUID = Field(default_factory=uuid4, description="Stable attachment identifier.")
    runtime_session_id: UUID = Field(description="Stable worker-side session identifier reused by reconnects.")
    game_id: UUID = Field(description="Game being attached to.")
    membership_id: UUID = Field(description="Membership authorizing the attachment.")
    worker_id: UUID = Field(description="Worker receiving the runtime attachment.")
    worker_generation: int = Field(ge=1, description="Worker generation receiving the attachment.")
    client_kind: ClientKind = Field(description="Kind of attaching client.")
    client_instance_id: str = Field(min_length=1, description="Client-generated instance identity.")
    expires_at: datetime | None = Field(default=None, description="UTC runtime token expiry.")
    authority_epoch: int = Field(ge=1, description="Authority epoch installed in the worker.")


class AttachmentRecord(AttachmentCreate):
    """Persisted attachment history containing only a token digest."""

    state: AttachmentState = Field(default=AttachmentState.CONNECTED, description="Attachment lifecycle state.")
    runtime_token_hash: str = Field(description="HMAC digest of the runtime token.")
    connected_at: datetime = Field(description="UTC connection time.")
    last_seen_at: datetime | None = Field(default=None, description="UTC latest observed activity.")
    disconnected_at: datetime | None = Field(default=None, description="UTC disconnection time.")
    disconnect_reason: str | None = Field(default=None, description="Stable disconnection reason code.")
    last_event_cursor: int | None = Field(default=None, ge=0, description="Latest acknowledged objective-event cursor.")
    last_combat_log_cursor: int | None = Field(default=None, ge=0, description="Latest acknowledged combat-log cursor.")


class IssuedAttachment(DirectoryModel):
    """One-time runtime-token response returned when an attachment opens."""

    attachment: AttachmentRecord = Field(description="Persisted attachment history record.")
    runtime_token: str = Field(min_length=1, description="Plaintext runtime token returned exactly once.")


class DirectoryEventRecord(DirectoryModel):
    """Append-only typed lifecycle event retained by the directory."""

    cursor: int = Field(ge=1, description="Global monotonic directory-event cursor.")
    event_id: UUID = Field(description="Stable event identifier.")
    game_id: UUID | None = Field(default=None, description="Related game, if the event is game-scoped.")
    event_type: str = Field(min_length=1, description="Stable lifecycle event type.")
    payload: JsonObject = Field(default_factory=dict, description="Canonical structured event payload.")
    payload_digest: str = Field(description="SHA-256 digest of canonical payload.")
    created_at: datetime = Field(description="UTC event creation time.")


class ArtifactCreate(DirectoryModel):
    """Input used to publish immutable external evidence metadata."""

    artifact_id: UUID = Field(default_factory=uuid4, description="Stable artifact identifier.")
    game_id: UUID | None = Field(default=None, description="Related game, if game-scoped.")
    artifact_kind: ArtifactKind = Field(description="Kind of evidence retained by the artifact.")
    schema_version: str = Field(min_length=1, description="Artifact schema identity.")
    media_type: str = Field(min_length=1, description="Artifact media type.")
    uri: str = Field(min_length=1, description="Location of immutable artifact bytes.")
    byte_size: int = Field(ge=0, description="Exact artifact size in bytes.")
    content_digest: str = Field(min_length=1, description="SHA-256 digest of immutable artifact bytes.")
    producer_kind: ProducerKind = Field(description="Kind of process that produced the artifact.")
    producer_version: str = Field(min_length=1, description="Producer implementation version.")


class ArtifactRecord(ArtifactCreate):
    """Persisted immutable artifact descriptor."""

    created_at: datetime = Field(description="UTC publication time.")


class WorkerTerminalReadyManifestCreate(DirectoryModel):
    """Generation-fenced terminal evidence staged before hosted adoption."""

    game_id: UUID
    worker_id: UUID
    worker_generation: int = Field(ge=1)
    objective_artifact: ArtifactCreate
    subjective_artifact: ArtifactCreate
    summary_evidence: JsonObject
    settlement_evidence: JsonObject | None = None
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ready_at: datetime

    @model_validator(mode="after")
    def _validate_artifact_ownership(self) -> Self:
        if (
            self.objective_artifact.game_id != self.game_id
            or self.subjective_artifact.game_id != self.game_id
        ):
            raise ValueError(
                "worker terminal artifacts must belong to the manifest game",
            )
        return self


class WorkerTerminalReadyManifestRecord(
    WorkerTerminalReadyManifestCreate,
):
    """Persisted immutable ready manifest with one-way adoption state."""

    staged_at: datetime
    adopted_at: datetime | None = None


class FinalSummaryRecord(DirectoryModel):
    """Persisted immutable summary revision and indexed fields."""

    summary_id: UUID = Field(description="Stable summary revision identifier.")
    game_id: UUID = Field(description="Game summarized by this revision.")
    schema_version: str = Field(description="Summary payload schema.")
    summary_revision: int = Field(ge=1, description="Monotonic revision number for the game.")
    summary: GameSummary = Field(description="Canonical typed objective summary produced by the engine reducer.")
    summary_digest: str = Field(description="SHA-256 digest of canonical summary JSON.")
    winner_side_id: str | None = Field(default=None, description="Indexed winner identity.")
    terminal_reason: str = Field(description="Indexed terminal reason.")
    round_count: int = Field(ge=0, description="Indexed round count.")
    turn_count: int = Field(ge=0, description="Indexed turn count.")
    duration_ms: int = Field(ge=0, description="Indexed duration in milliseconds.")
    source_event_digest: str = Field(description="Digest of objective event evidence.")
    source_combat_log_digest: str = Field(description="Digest of combat-log evidence.")
    created_at: datetime = Field(description="UTC publication time.")
    supersedes_summary_id: UUID | None = Field(default=None, description="Prior current revision replaced by this one.")
    is_current: bool = Field(description="Whether this is the current summary revision.")


class RepositoryMetrics(DirectoryModel):
    """Database-operation instrumentation for hot-path exclusion proofs."""

    total_operations: int = Field(ge=0, description="Repository operations attempted outside migration bootstrap.")
    successful_operations: int = Field(ge=0, description="Repository operations completed successfully.")
    failed_operations: int = Field(ge=0, description="Repository operations that raised.")
    blocked_hot_path_operations: int = Field(ge=0, description="Operations rejected before touching SQLite in a hot-path guard.")
    injected_failures: int = Field(ge=0, description="Operations rejected by fail injection before touching SQLite.")
    by_operation: dict[str, int] = Field(default_factory=dict, description="Attempt counts grouped by repository operation name.")
