"""Canonical transport contracts for persistent character composition.

Clients submit authored selections only.  Stable character identity, immutable
revision numbers, earned-level authority, content/ruleset identities, and every
digest are normalized by :mod:`server.character_directory_service`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dnd.blocks.appearance import BodyCategory, HeadCategory
from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
)
from dnd.core.content.descriptors import ContentDescriptor
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    BackgroundDefinition,
    BuildChoiceSelection,
    BuildChoiceRequirement,
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
    ClassDefinition,
    ProficiencySubject,
    RitualPreparationPolicy,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellcastingSourceId,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.encounters import (
    EncounterRecipe,
    EncounterRosterRecipe,
)
from dnd.core.content.premade_characters import (
    CharacterCreationPlan,
    CharacterBuildDraft,
    CharacterLoadoutDraft,
)
from dnd.core.content.recipe_presets import ContentRecipePreset
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import EquipmentSlot
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
    CharacterPresentationPreferencesRecord,
    CharacterRevisionHeads,
    ClientKind,
    MembershipRecord,
    PrincipalRecord,
    ProfileSettingsRecord,
    SavedEncounterRecord,
    SavedEncounterRosterRecord,
    SpellPreparationPolicy,
)
from server.player_replication_contract import EntityVisualLoadout
from server.world_contracts import APIEntitySummary


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
    INITIAL_APPAREL_SELECTION_REQUIRED = (
        "initial_apparel_selection_required"
    )
    CONTENT_REBASE_UNRESOLVABLE = "content_rebase_unresolvable"
    UNKNOWN_CREATION_PLAN = "unknown_creation_plan"
    CREATION_PLAN_DIGEST_MISMATCH = "creation_plan_digest_mismatch"
    CREATION_PLAN_LEVEL_MISMATCH = "creation_plan_level_mismatch"


class CharacterBuildValidationRequest(CharacterDirectoryModel):
    """Validate one complete structural draft and its matching loadout."""

    build: CharacterBuildDraft
    loadout: CharacterLoadoutDraft = Field(default_factory=CharacterLoadoutDraft)
    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CharacterCreationValidationRequest(CharacterBuildValidationRequest):
    """Validate one draft under an exact backend-authored creation plan."""

    creation_plan_id: str = Field(min_length=1)
    creation_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateCharacterRequest(CharacterCreationValidationRequest):
    """Create one schema-2 character from exact authored selections."""

    display_name: str = Field(min_length=1, max_length=80)
    idempotency_key: UUID


class CharacterMutationExpectation(CharacterDirectoryModel):
    """Exact three-head compare-and-swap expectation."""

    idempotency_key: UUID
    expected_row_version: int = Field(ge=1)
    expected_heads: CharacterRevisionHeads


class UpdateCharacterPresentationPreferencesRequest(CharacterDirectoryModel):
    """CAS-replace one flexible non-mechanical presentation document."""

    expected_revision: int = Field(
        ge=0,
        description=(
            "Current presentation revision; zero creates the first "
            "persisted document."
        ),
    )
    preferences: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Frontend-owned experimental art preferences, persisted "
            "separately from character mechanics."
        ),
    )


class CharacterPresentationPreferencesResponse(
    CharacterPresentationPreferencesRecord,
):
    """Public envelope for one character-scoped presentation document."""


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


class CharacterContentRebaseIssueReason(str, Enum):
    """Closed reasons historical content cannot enter a current draft."""

    APPEARANCE_SELECTION_UNSUPPORTED = "appearance_selection_unsupported"
    IDENTITY_NOT_INSTALLED = "identity_not_installed"
    ORIGIN_CHOICE_CONFLICT = "origin_choice_conflict"
    RECIPE_PARAMETERS_INCOMPATIBLE = "recipe_parameters_incompatible"


class CharacterContentRefRebaseChange(CharacterDirectoryModel):
    """One server-authoritative old-contract to current-contract mapping."""

    kind: Literal["content_ref"] = "content_ref"
    path: tuple[str, ...]
    source_ref: ContentRef
    replacement_ref: ContentRef

    @model_validator(mode="after")
    def _validate_identity(self) -> "CharacterContentRefRebaseChange":
        if (
            self.source_ref.pack_id != self.replacement_ref.pack_id
            or self.source_ref.definition_kind
            is not self.replacement_ref.definition_kind
            or self.source_ref.content_id != self.replacement_ref.content_id
        ):
            raise ValueError("content rebase cannot change authored root")
        if self.source_ref == self.replacement_ref:
            raise ValueError("content rebase changes require distinct refs")
        return self


class CharacterAppearanceOptionRebaseChange(CharacterDirectoryModel):
    """One exact retired appearance option added by the rebase service."""

    kind: Literal["appearance_option_added"] = "appearance_option_added"
    path: tuple[str, ...]
    selection: CharacterAppearanceOptionSelection


class CharacterOriginChoiceRebaseChange(CharacterDirectoryModel):
    """One exact origin choice added by an authored content migration."""

    kind: Literal["origin_choice_added"] = "origin_choice_added"
    path: tuple[str, ...]
    selection: BuildChoiceSelection


CharacterRebaseChange = Annotated[
    CharacterContentRefRebaseChange
    | CharacterAppearanceOptionRebaseChange
    | CharacterOriginChoiceRebaseChange,
    Field(discriminator="kind"),
]


class CharacterContentRebaseIssue(CharacterDirectoryModel):
    """One historical identity the installed content set cannot rebase."""

    path: tuple[str, ...]
    reason: CharacterContentRebaseIssueReason
    source_ref: ContentRef
    detail: str = ""


class CharacterRespecSeedSource(CharacterDirectoryModel):
    """Immutable stored provenance from which one editable seed was derived."""

    character_row_version: int = Field(ge=1)
    heads: CharacterRevisionHeads
    definition_revision: int = Field(ge=1)
    definition_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    definition_created_at: datetime
    holdings_created_at: datetime
    loadout_created_at: datetime

    @model_validator(mode="after")
    def _validate_definition_head(self) -> "CharacterRespecSeedSource":
        if (
            self.definition_revision != self.heads.definition_revision
            or self.definition_digest != self.heads.definition_digest
        ):
            raise ValueError("respec source definition must match its heads")
        return self


class CharacterRespecSeedResponse(CharacterDirectoryModel):
    """Current-catalog editable projection of one immutable stored character."""

    schema_version: Literal[1] = 1
    character_id: UUID
    source: CharacterRespecSeedSource
    target_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ready: bool
    editable_build: CharacterBuildDraft | None
    editable_loadout: CharacterLoadoutDraft | None
    changes: tuple[CharacterRebaseChange, ...] = ()
    issues: tuple[CharacterContentRebaseIssue, ...] = ()

    @model_validator(mode="after")
    def _validate_readiness(self) -> "CharacterRespecSeedResponse":
        has_editable = (
            self.editable_build is not None
            and self.editable_loadout is not None
        )
        if self.ready != has_editable:
            raise ValueError("ready must match editable seed availability")
        if self.ready == bool(self.issues):
            raise ValueError("ready seeds cannot have rebase issues")
        change_paths = tuple(change.path for change in self.changes)
        if len(set(change_paths)) != len(change_paths):
            raise ValueError("respec rebase change paths must be unique")
        return self


class CharacterLoadoutMutationRequest(
    CharacterMutationExpectation,
):
    """Replace only the mutable loadout stream."""

    loadout: CharacterLoadoutDraft
    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CharacterEquipOperation(CharacterDirectoryModel):
    """Equip one exact durable possession into one exact runtime-owned slot."""

    operation: Literal["equip"] = "equip"
    character_item_id: UUID
    target_slot: EquipmentSlot


class CharacterUnequipOperation(CharacterDirectoryModel):
    """Unequip one exact durable possession from its authoritative slot."""

    operation: Literal["unequip"] = "unequip"
    character_item_id: UUID


CharacterEquipmentOperation = Annotated[
    CharacterEquipOperation | CharacterUnequipOperation,
    Field(discriminator="operation"),
]


class CharacterEquipmentMutationRequest(
    CharacterMutationExpectation,
):
    """Mutate durable equipment through isolated runtime rule execution."""

    operation: CharacterEquipmentOperation
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


class OriginInnateSpellGrantPreviewResponse(CharacterDirectoryModel):
    """One exact origin-owned innate spell and its usage contract."""

    grant_id: str
    spell_ref: ContentRef
    provider_ref: ContentRef
    spellcasting_source_id: SpellcastingSourceId
    spellcasting_ability: AbilityScoreName
    provider_level: int = Field(ge=1, le=20)
    fixed_cast_rank: int = Field(ge=0, le=9)
    uses_per_long_rest: int | None = Field(default=None, ge=1)
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
    origin_innate_spells: tuple[
        OriginInnateSpellGrantPreviewResponse,
        ...,
    ] = ()


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


class CharacterBuildVisualPreviewResponse(CharacterDirectoryModel):
    """Isolated production visual projection of one validated character draft."""

    schema_version: Literal[1] = 1
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_build: CharacterBuildDraft
    normalized_loadout: CharacterLoadoutDraft
    entity: APIEntitySummary
    visual_loadout: EntityVisualLoadout

    @model_validator(mode="after")
    def _validate_projection_owner(
        self,
    ) -> "CharacterBuildVisualPreviewResponse":
        if self.entity.uuid != self.visual_loadout.entity_uuid:
            raise ValueError(
                "character preview entity and visual loadout must share one UUID",
            )
        return self


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


class SpeciesCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: SpeciesDefinition


class SpeciesVariantCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: SpeciesVariantDefinition


class BackgroundCatalogEntry(CharacterDirectoryModel):
    ref: ContentRef
    descriptor: ContentDescriptor
    definition: BackgroundDefinition


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


class StartingApparelPackageCatalogEntry(CharacterDirectoryModel):
    """One public exact body-and-feet wardrobe package."""

    ref: ContentRef
    descriptor: ContentDescriptor
    definition: StartingEquipmentPackageDefinition


class CharacterAppearanceControlKind(str, Enum):
    """Closed creator control kinds for durable appearance selections."""

    CHOICE = "choice"
    COLOR = "color"


class CharacterAppearanceValueCatalogEntry(CharacterDirectoryModel):
    """One exact semantic value accepted for an appearance option."""

    value_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tint_rgb: int | None = Field(default=None, ge=0, le=0xFFFFFF)
    tint_source_option_id: (
        Literal["appearance.hair_tint"] | None
    )
    body_category: BodyCategory | None = None
    head_category: HeadCategory | None = None
    visual_scale_multiplier: float | None = Field(
        default=None,
        gt=0,
        le=4,
    )
    visual_scale_x_multiplier: float | None = Field(
        default=None,
        gt=0,
        le=4,
    )


class CharacterAppearanceOptionCatalogEntry(CharacterDirectoryModel):
    """One required durable option and its closed selectable values."""

    option_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    control_kind: CharacterAppearanceControlKind
    default_value_id: str = Field(min_length=1)
    values: tuple[CharacterAppearanceValueCatalogEntry, ...]

    @model_validator(mode="after")
    def _validate_values(self) -> "CharacterAppearanceOptionCatalogEntry":
        value_ids = tuple(value.value_id for value in self.values)
        if not value_ids:
            raise ValueError("appearance options require at least one value")
        if len(set(value_ids)) != len(value_ids):
            raise ValueError("appearance option values must be unique")
        if self.default_value_id not in value_ids:
            raise ValueError(
                "appearance option default_value_id must identify one value",
            )
        return self


class CharacterAppearanceConstraintCatalogEntry(CharacterDirectoryModel):
    """One exact conditional compatibility rule between two options."""

    when_option_id: str = Field(min_length=1)
    when_value_id: str = Field(min_length=1)
    required_option_id: str = Field(min_length=1)
    allowed_value_ids: tuple[str, ...] = Field(min_length=1)


class CharacterAppearanceCatalog(CharacterDirectoryModel):
    """Closed appearance vocabulary for the installed player body."""

    schema_version: Literal[4] = 4
    default_selection: CharacterAppearanceSelection
    options: tuple[CharacterAppearanceOptionCatalogEntry, ...]
    constraints: tuple[CharacterAppearanceConstraintCatalogEntry, ...] = ()

    @model_validator(mode="after")
    def _validate_catalog(self) -> "CharacterAppearanceCatalog":
        option_ids = tuple(option.option_id for option in self.options)
        if not option_ids:
            raise ValueError("appearance catalog requires options")
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("appearance catalog option IDs must be unique")
        if option_ids != tuple(sorted(option_ids)):
            raise ValueError("appearance catalog options must be ordered")

        values_by_option = {
            option.option_id: {
                value.value_id for value in option.values
            }
            for option in self.options
        }
        exact_presentation_fields = {
            "appearance.body": "body_category",
            "appearance.build": "visual_scale_x_multiplier",
            "appearance.head": "head_category",
            "appearance.stature": "visual_scale_multiplier",
        }
        for option in self.options:
            if option.control_kind is CharacterAppearanceControlKind.COLOR:
                for value in option.values:
                    if (
                        (value.tint_rgb is None)
                        == (value.tint_source_option_id is None)
                    ):
                        raise ValueError(
                            f"{option.option_id} color values require exactly "
                            "one literal tint or tint source",
                        )
            required_field = exact_presentation_fields.get(option.option_id)
            if required_field is None:
                continue
            if any(
                getattr(value, required_field) is None
                for value in option.values
            ):
                raise ValueError(
                    f"{option.option_id} values require "
                    f"{required_field}",
                )
        defaults = tuple(
            (option.option_id, option.default_value_id)
            for option in self.options
        )
        selected_defaults = tuple(
            (selection.option_id, selection.value_id)
            for selection in self.default_selection.options
        )
        if selected_defaults != defaults:
            raise ValueError(
                "appearance default selection must match option defaults",
            )
        for constraint in self.constraints:
            if (
                constraint.when_option_id not in values_by_option
                or constraint.when_value_id
                not in values_by_option[constraint.when_option_id]
            ):
                raise ValueError(
                    "appearance constraint trigger must identify a value",
                )
            allowed_values = values_by_option.get(
                constraint.required_option_id,
            )
            if (
                allowed_values is None
                or not set(constraint.allowed_value_ids)
                <= allowed_values
            ):
                raise ValueError(
                    "appearance constraint must identify allowed values",
                )
        return self


class CharacterCreationRulesMetadata(CharacterDirectoryModel):
    """Public constants and supported profile policy choices for the creator."""

    schema_version: Literal[2] = 2
    rules_baseline: Literal[
        "srd_5_1_with_selected_bg3_creation_rules"
    ] = "srd_5_1_with_selected_bg3_creation_rules"
    initial_custom_character_level: Literal[1] = 1
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

    schema_version: Literal[7] = 7
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rules: CharacterCreationRulesMetadata = Field(
        default_factory=CharacterCreationRulesMetadata,
    )
    appearance_catalog: CharacterAppearanceCatalog
    body_recipes: tuple[ContentRecipe, ...]
    body_recipe_presets: tuple[ContentRecipePreset, ...]
    species: tuple[SpeciesCatalogEntry, ...]
    species_variants: tuple[SpeciesVariantCatalogEntry, ...]
    backgrounds: tuple[BackgroundCatalogEntry, ...]
    classes: tuple[ClassCatalogEntry, ...]
    subclasses: tuple[SubclassCatalogEntry, ...]
    creation_plans: tuple[CharacterCreationPlan, ...]
    starting_equipment_packages: tuple[
        StartingEquipmentPackageCatalogEntry,
        ...,
    ]
    starting_apparel_requirement: BuildChoiceRequirement
    starting_apparel_packages: tuple[
        StartingApparelPackageCatalogEntry,
        ...,
    ]


class StandaloneLocalProfileResponse(CharacterDirectoryModel):
    """Selected physical profile identity for direct standalone clients."""

    profile_id: UUID
    display_name: str = Field(min_length=1, max_length=80)
    principal_capability: str = Field(min_length=1)
    settings: ProfileSettingsRecord


class SaveEncounterRosterRequest(CharacterDirectoryModel):
    """Persist one exact owner-scoped roster recipe."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRosterRecipe


class ReplaceSavedEncounterRosterRequest(CharacterDirectoryModel):
    """Compare-and-swap one exact owner-scoped roster recipe."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRosterRecipe
    expected_revision: int = Field(ge=1)
    expected_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SavedEncounterRosterListResponse(CharacterDirectoryModel):
    rosters: tuple[SavedEncounterRosterRecord, ...]


class SaveEncounterRequest(CharacterDirectoryModel):
    """Persist one exact owner-scoped encounter recipe."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRecipe


class ReplaceSavedEncounterRequest(CharacterDirectoryModel):
    """Compare-and-swap one exact owner-scoped encounter recipe."""

    title: str = Field(min_length=1, max_length=120)
    recipe: EncounterRecipe
    expected_revision: int = Field(ge=1)
    expected_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SavedEncounterListResponse(CharacterDirectoryModel):
    encounters: tuple[SavedEncounterRecord, ...]
