"""Canonical transport contracts for persistent character composition.

Clients submit authored selections only.  Stable character identity, immutable
revision numbers, earned-level authority, content/ruleset identities, and every
digest are normalized by :mod:`server.character_directory_service`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
)
from dnd.core.content.descriptors import ContentDescriptor
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    BackgroundDefinition,
    ClassDefinition,
    ProficiencySubject,
    RitualPreparationPolicy,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellcastingSourceId,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.premade_characters import (
    CharacterBuildDraft,
    CharacterLoadoutDraft,
    PremadeCharacterBuild,
)
from dnd.core.content.recipe_presets import ContentRecipePreset
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.progression import CasterProgression
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
)
from server.game_directory.contracts import (
    CanonicalCharacterRecord,
    CharacterAdvancementAwardRecord,
    CharacterDefinitionRecord,
    CharacterHoldingsRecord,
    CharacterLoadoutRecord,
    CharacterRevisionHeads,
    ClientKind,
    MembershipRecord,
    PrincipalRecord,
    ProfileSettingsRecord,
    SpellPreparationPolicy,
)


class CharacterDirectoryModel(BaseModel):
    """Strict public character-directory model."""

    model_config = ConfigDict(extra="forbid")


class CharacterMutationIssueCode(str, Enum):
    """Closed directory-owned reasons a valid build cannot be committed."""

    ACTIVE_DEPLOYMENT = "active_deployment"
    IMMUTABLE_ORIGIN_CHANGED = "immutable_origin_changed"
    LEVEL_UP_MUST_APPEND_ONE_LEVEL = "level_up_must_append_one_level"
    LEVEL_ENTITLEMENT_UNAVAILABLE = "level_entitlement_unavailable"
    RESPEC_DISABLED = "respec_disabled"
    RESPEC_LEVEL_TOTAL_MISMATCH = "respec_level_total_mismatch"
    INITIAL_LEVEL_MUST_BE_ONE = "initial_level_must_be_one"
    UNKNOWN_PREMADE_ID = "unknown_premade_id"
    PREMADE_BUILD_MISMATCH = "premade_build_mismatch"


class CharacterBuildValidationRequest(CharacterDirectoryModel):
    """Validate one complete structural draft and its matching loadout."""

    build: CharacterBuildDraft
    loadout: CharacterLoadoutDraft = Field(default_factory=CharacterLoadoutDraft)
    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateCharacterRequest(CharacterBuildValidationRequest):
    """Create one schema-2 character from exact authored selections."""

    display_name: str = Field(min_length=1, max_length=80)
    idempotency_key: UUID


class CharacterMutationExpectation(CharacterDirectoryModel):
    """Exact three-head compare-and-swap expectation."""

    idempotency_key: UUID
    expected_row_version: int = Field(ge=1)
    expected_heads: CharacterRevisionHeads


class CharacterLevelUpRequest(
    CharacterBuildValidationRequest,
    CharacterMutationExpectation,
):
    """Append exactly one earned class level and replace its loadout."""


class CharacterRespecRequest(
    CharacterBuildValidationRequest,
    CharacterMutationExpectation,
):
    """Replace all class-level selections at the current earned level."""


class CharacterLoadoutMutationRequest(
    CharacterMutationExpectation,
):
    """Replace only the mutable loadout stream."""

    loadout: CharacterLoadoutDraft
    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CharacterGrantProvenanceResponse(CharacterDirectoryModel):
    """Exact authored source coordinates for one derived grant."""

    source_kind: CharacterGrantSourceKind
    source_ref: ContentRef
    character_level: int | None
    class_level_id: str | None
    class_level: int | None
    choice_id: str | None
    ordinal_path: tuple[int, ...]


class CharacterGrantScheduleEntryResponse(CharacterDirectoryModel):
    """One normalized structural grant in deterministic application order."""

    kind: CharacterGrantScheduleKind
    provenance: CharacterGrantProvenanceResponse
    grant_token: str
    content_ref: ContentRef | None = None
    proficiency: ProficiencySubject | None = None
    ability: AbilityScoreName | None = None
    amount: int | None = None
    replaced_content_ref: ContentRef | None = None


class CasterContributionPreviewResponse(CharacterDirectoryModel):
    """One class contribution to the shared normal spell-slot table."""

    class_ref: ContentRef
    class_level: int
    progression: CasterProgression
    spellcasting_feature_class_level: int | None
    spellcasting_source_id: SpellcastingSourceId | None
    spellcasting_ability: AbilityScoreName | None
    maximum_spell_rank: int
    ritual_policy: RitualPreparationPolicy


class KnownSpellGrantPreviewResponse(CharacterDirectoryModel):
    """One final known spell and its exact casting source."""

    spell_ref: ContentRef
    provider_ref: ContentRef
    spellcasting_source_id: SpellcastingSourceId
    grant_token: str


class CharacterBuildPreviewResponse(CharacterDirectoryModel):
    """Deterministic build facts safe for creator and level-up previews."""

    class_level_counts: tuple[tuple[ContentRef, int], ...]
    automatic_grant_refs: tuple[ContentRef, ...]
    grant_schedule: tuple[CharacterGrantScheduleEntryResponse, ...]
    final_known_spell_refs: tuple[ContentRef, ...]
    caster_contributions: tuple[CasterContributionPreviewResponse, ...]
    effective_spellcaster_level: int
    normal_spell_slots: tuple[tuple[int, int], ...]
    final_known_spells: tuple[KnownSpellGrantPreviewResponse, ...] = ()


class CharacterBuildValidationIssueResponse(CharacterDirectoryModel):
    """One closed build failure with a stable structural path."""

    code: CharacterBuildIssueCode | CharacterMutationIssueCode
    path: tuple[str, ...]
    content_refs: tuple[ContentRef, ...] = ()
    detail: str = ""


class CharacterBuildValidationResponse(CharacterDirectoryModel):
    """Exact validation outcome; invalid drafts never receive a preview."""

    valid: bool
    issues: tuple[CharacterBuildValidationIssueResponse, ...]
    preview: CharacterBuildPreviewResponse | None
    normalized_build: CharacterBuildDraft
    normalized_loadout: CharacterLoadoutDraft
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )


class CharacterAdvancementResponse(CharacterDirectoryModel):
    """Immutable advancement authority for one character."""

    character_id: UUID
    earned_character_level: int = Field(ge=0, le=20)
    awards: tuple[CharacterAdvancementAwardRecord, ...]


class AdminCharacterAdvancementAwardRequest(CharacterDirectoryModel):
    """Grant level entitlement without choosing how the character spends it."""

    idempotency_key: UUID
    expected_earned_character_level: int = Field(ge=1, le=20)
    level_delta: int = Field(default=1, ge=1, le=19)


class CharacterSnapshotResponse(CharacterDirectoryModel):
    """Current exact character row and all three immutable heads."""

    character: CanonicalCharacterRecord
    heads: CharacterRevisionHeads
    definition: CharacterDefinitionRecord
    holdings: CharacterHoldingsRecord
    loadout: CharacterLoadoutRecord
    advancement: CharacterAdvancementResponse


class CharacterListResponse(CharacterDirectoryModel):
    """Current persistent-character summaries owned by one profile."""

    characters: tuple[CanonicalCharacterRecord, ...]


class CharacterAttachmentSummary(CharacterDirectoryModel):
    """Non-secret summary of one live profile attachment."""

    attachment_id: UUID
    game_id: UUID
    membership_id: UUID
    client_kind: ClientKind
    client_instance_id: str
    connected_at: datetime
    expires_at: datetime | None = None


class CharacterProfileGameSeat(CharacterDirectoryModel):
    """One current or historical game seat owned by the profile."""

    membership: MembershipRecord
    controlled_entity_uuids: tuple[UUID, ...]
    active_attachments: tuple[CharacterAttachmentSummary, ...]


class CharacterProfileResponse(CharacterDirectoryModel):
    """One profile's settings, characters, and reconnectable game seats."""

    principal: PrincipalRecord
    settings: ProfileSettingsRecord
    characters: tuple[CanonicalCharacterRecord, ...]
    game_seats: tuple[CharacterProfileGameSeat, ...]


class UpdateCharacterProfileSettingsRequest(CharacterDirectoryModel):
    """Replace profile build policy through one exact settings CAS."""

    expected_settings_version: int = Field(ge=1)
    permissive_multiclass_prerequisites: bool = True
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy = (
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    )
    allow_respec: bool = True
    spell_preparation_policy: SpellPreparationPolicy = (
        SpellPreparationPolicy.LONG_REST
    )


class CharacterDefinitionHistoryResponse(CharacterDirectoryModel):
    """Every immutable structural revision in ascending order."""

    character_id: UUID
    definitions: tuple[CharacterDefinitionRecord, ...]


class CharacterOriginImplementationStatus(str, Enum):
    """Whether one authored origin is mechanically selectable."""

    AVAILABLE = "available"
    BLOCKED = "blocked"


class CharacterOriginImplementation(CharacterDirectoryModel):
    """Closed creator availability with an exact reason when unavailable."""

    status: CharacterOriginImplementationStatus
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def _validate_reason(self) -> "CharacterOriginImplementation":
        if (
            self.status is CharacterOriginImplementationStatus.BLOCKED
            and not self.blocked_reason
        ):
            raise ValueError("blocked character origins require a reason")
        if (
            self.status is CharacterOriginImplementationStatus.AVAILABLE
            and self.blocked_reason is not None
        ):
            raise ValueError(
                "available character origins cannot carry a blocked reason",
            )
        return self


class SpeciesCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: SpeciesDefinition
    implementation: CharacterOriginImplementation


class SpeciesVariantCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: SpeciesVariantDefinition
    implementation: CharacterOriginImplementation


class BackgroundCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: BackgroundDefinition
    implementation: CharacterOriginImplementation


class ClassCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: ClassDefinition


class SubclassCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: SubclassDefinition


class StartingEquipmentPackageCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: StartingEquipmentPackageDefinition


class CharacterCreationRulesMetadata(CharacterDirectoryModel):
    """Public constants and supported profile policy choices for the creator."""

    schema_version: Literal[1] = 1
    rules_baseline: Literal[
        "srd_5_1_with_selected_bg3_creation_rules"
    ] = "srd_5_1_with_selected_bg3_creation_rules"
    character_level_cap: Literal[20] = 20
    point_buy_budget: Literal[27] = 27
    minimum_ability_score: Literal[8] = 8
    maximum_pre_bonus_ability_score: Literal[15] = 15
    ordinary_ability_score_cap: Literal[20] = 20
    flexible_plus_two: Literal[2] = 2
    flexible_plus_one: Literal[1] = 1
    flexible_bonuses_must_target_distinct_abilities: Literal[True] = True
    hit_points_after_character_level_one: Literal[
        "fixed_class_average"
    ] = "fixed_class_average"
    supported_multiclass_slot_rounding_policies: tuple[
        MulticlassSlotRoundingPolicy,
        ...,
    ] = tuple(MulticlassSlotRoundingPolicy)
    default_multiclass_slot_rounding_policy: (
        MulticlassSlotRoundingPolicy
    ) = MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    default_permissive_multiclass_prerequisites: bool = True


class CharacterCreationCatalogResponse(CharacterDirectoryModel):
    """Exact typed definitions and curated body recipes usable by creators."""

    schema_version: Literal[1] = 1
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rules: CharacterCreationRulesMetadata = Field(
        default_factory=CharacterCreationRulesMetadata,
    )
    body_recipes: tuple[ContentRecipe, ...]
    body_recipe_presets: tuple[ContentRecipePreset, ...]
    species: tuple[SpeciesCatalogEntry, ...]
    species_variants: tuple[SpeciesVariantCatalogEntry, ...]
    backgrounds: tuple[BackgroundCatalogEntry, ...]
    classes: tuple[ClassCatalogEntry, ...]
    subclasses: tuple[SubclassCatalogEntry, ...]
    premades: tuple[PremadeCharacterBuild, ...]
    starting_equipment_packages: tuple[
        StartingEquipmentPackageCatalogEntry,
        ...,
    ]


class StandaloneLocalProfileResponse(CharacterDirectoryModel):
    """Selected physical profile identity for direct standalone clients."""

    profile_id: UUID
    display_name: str = Field(min_length=1, max_length=80)
    principal_capability: str = Field(min_length=1)
    settings: ProfileSettingsRecord
