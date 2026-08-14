"""Transport-neutral persistent character composition service."""

from __future__ import annotations

from dataclasses import asdict
from typing import TypeAlias, cast
from uuid import UUID, uuid4, uuid5

from pydantic import ValidationError

from dnd.blocks.appearance import BodyCategory, HeadCategory
from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterBuildValidationResult,
    CharacterBuildValidator,
)
from dnd.content_system.background_starting_holdings import (
    background_starting_holdings,
)
from dnd.content_system.character_appearance import (
    PLAYER_CHARACTER_APPEARANCE_CONSTRAINTS,
    PLAYER_CHARACTER_APPEARANCE_OPTIONS,
    default_player_character_appearance,
)
from dnd.content_system.builtin_character_builds import (
    compose_character_creation_plans,
)
from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_CHOICE_ID,
)
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.durable_characters import (
    BackgroundDefinition,
    BuildChoiceRequirement,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterItemV1,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
    ChoiceRequirementKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.premade_characters import (
    CharacterCreationPlan,
    CharacterCreationPlanKind,
    StarterHoldingTemplate,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from server.character_directory_contracts import (
    AdminCharacterAdvancementAwardRequest,
    BackgroundCatalogEntry,
    CharacterAdvancementResponse,
    CharacterAppearanceCatalog,
    CharacterAppearanceConstraintCatalogEntry,
    CharacterAppearanceControlKind,
    CharacterAppearanceOptionCatalogEntry,
    CharacterAppearanceValueCatalogEntry,
    CharacterBuildDraft,
    CharacterBuildPreviewResponse,
    CharacterBuildValidationIssueResponse,
    CharacterBuildValidationRequest,
    CharacterBuildValidationResponse,
    CharacterBuildVisualPreviewResponse,
    CharacterCreationCatalogResponse,
    CharacterCreationValidationRequest,
    CharacterDefinitionHistoryResponse,
    CharacterEquipmentMutationRequest,
    CharacterGrantScheduleEntryResponse,
    CharacterLevelUpRequest,
    CharacterListResponse,
    CharacterLoadoutDraft,
    CharacterLoadoutMutationRequest,
    CharacterMutationIssueCode,
    CharacterAttachmentSummary,
    CharacterProfileGameSeat,
    CharacterProfileResponse,
    UpdateCharacterPresentationPreferencesRequest,
    CharacterRespecRequest,
    CharacterRespecSeedResponse,
    CharacterRespecSeedSource,
    CharacterSnapshotResponse,
    ClassCatalogEntry,
    CasterContributionPreviewResponse,
    CreateCharacterRequest,
    KnownSpellGrantPreviewResponse,
    OriginInnateSpellGrantPreviewResponse,
    ReplaceSavedEncounterRequest,
    ReplaceSavedEncounterRosterRequest,
    SaveEncounterRequest,
    SaveEncounterRosterRequest,
    SavedEncounterListResponse,
    SavedEncounterRosterListResponse,
    SpeciesCatalogEntry,
    SpeciesVariantCatalogEntry,
    StartingApparelPackageCatalogEntry,
    StartingEquipmentPackageCatalogEntry,
    SubclassCatalogEntry,
    UpdateCharacterProfileSettingsRequest,
)
from server.character_build_preview import build_character_visual_preview
from server.character_content_rebase import (
    CharacterContentRebaseResult,
    rebase_character_content,
)
from server.character_equipment_mutation import mutate_character_equipment
from server.game_directory.contracts import (
    CanonicalCharacterRecord,
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    DirectoryMutationReceiptCreate,
    CharacterRevisionBundleCommit,
    CharacterRevisionHeads,
    CharacterPresentationPreferencesRecord,
    ProfileSettingsCreate,
    ProfileSettingsRecord,
    ProfileSettingsUpdate,
    SavedEncounterCreate,
    SavedEncounterRecord,
    SavedEncounterReplace,
    SavedEncounterRosterCreate,
    SavedEncounterRosterRecord,
    SavedEncounterRosterReplace,
    SpellPreparationPolicy,
)
from server.canonical_json import canonical_json_sha256 as canonical_digest
from server.game_directory.errors import (
    CapabilityError,
    ConflictError,
    NotFoundError,
    StaleVersionError,
)
from server.game_directory.repository import GameDirectoryRepository

_CHARACTER_IDEMPOTENCY_NAMESPACE = UUID(
    "860bd55e-9655-4a13-bcdb-6802d9d3b670",
)
_CHARACTER_PREVIEW_NAMESPACE = UUID(
    "09fd8bc2-8f2b-4b1d-a3d9-f4b72232ba8b",
)
_LEVEL_UP_OPERATION = "character.level_up"
_RESPEC_OPERATION = "character.respec"
_LOADOUT_OPERATION = "character.loadout"
_EQUIPMENT_OPERATION = "character.equipment"

_CharacterMutationRequest: TypeAlias = (
    CharacterLevelUpRequest
    | CharacterRespecRequest
    | CharacterLoadoutMutationRequest
    | CharacterEquipmentMutationRequest
)


def _character_appearance_catalog() -> CharacterAppearanceCatalog:
    """Project the exact resolver-owned appearance vocabulary."""

    return CharacterAppearanceCatalog(
        default_selection=default_player_character_appearance(),
        options=tuple(
            CharacterAppearanceOptionCatalogEntry(
                option_id=option.option_id,
                display_name=option.display_name,
                control_kind=CharacterAppearanceControlKind(
                    option.control_kind,
                ),
                default_value_id=option.default_value_id,
                values=tuple(
                    CharacterAppearanceValueCatalogEntry(
                        value_id=value.value_id,
                        display_name=value.display_name,
                        tint_rgb=value.tint_rgb,
                        tint_source_option_id=(
                            value.tint_source_option_id
                        ),
                        body_category=(
                            cast(BodyCategory, value.runtime_value)
                            if option.option_id == "appearance.body"
                            else None
                        ),
                        head_category=(
                            cast(HeadCategory, value.runtime_value)
                            if option.option_id == "appearance.head"
                            else None
                        ),
                        visual_scale_multiplier=(
                            cast(float, value.runtime_value)
                            if option.option_id == "appearance.stature"
                            else None
                        ),
                        visual_scale_x_multiplier=(
                            cast(float, value.runtime_value)
                            if option.option_id == "appearance.build"
                            else None
                        ),
                    )
                    for value in option.values
                ),
            )
            for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
        ),
        constraints=tuple(
            CharacterAppearanceConstraintCatalogEntry(
                when_option_id=constraint.when_option_id,
                when_value_id=constraint.when_value_id,
                required_option_id=constraint.required_option_id,
                allowed_value_ids=constraint.allowed_value_ids,
            )
            for constraint in PLAYER_CHARACTER_APPEARANCE_CONSTRAINTS
        ),
    )


class CharacterDirectoryOwnershipError(CapabilityError):
    """Raised when a principal addresses another principal's character."""


class CharacterDirectoryBuildError(ConflictError):
    """Raised when a mutation tries to commit an invalid build."""

    def __init__(self, validation: CharacterBuildValidationResponse) -> None:
        super().__init__("Character build validation failed")
        self.validation = validation


class CharacterDirectoryService:
    """Own canonical profile policy and persistent-character composition."""

    def __init__(
        self,
        repository: GameDirectoryRepository,
        content_system: LoadedContentSystem,
    ) -> None:
        self.repository = repository
        self.content_system = content_system

    def ensure_profile_settings(
        self,
        principal_id: UUID,
    ) -> ProfileSettingsRecord:
        """Return one profile policy, creating its canonical default once."""

        try:
            return self.repository.get_profile_settings(principal_id)
        except NotFoundError:
            try:
                return self.repository.create_profile_settings(
                    ProfileSettingsCreate(
                        owner_principal_id=principal_id,
                        ruleset_digest=character_ruleset_digest(
                            permissive_multiclass_prerequisites=True,
                            multiclass_slot_rounding_policy=(
                                MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
                            ),
                        ),
                    ),
                )
            except ConflictError:
                return self.repository.get_profile_settings(principal_id)

    def update_profile_settings(
        self,
        principal_id: UUID,
        *,
        expected_settings_version: int,
        permissive_multiclass_prerequisites: bool,
        multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy,
        allow_respec: bool,
        spell_preparation_policy: SpellPreparationPolicy,
    ) -> ProfileSettingsRecord:
        """Replace profile policy through the repository's one settings CAS."""

        return self.repository.update_profile_settings(
            ProfileSettingsUpdate(
                owner_principal_id=principal_id,
                expected_settings_version=expected_settings_version,
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

    def build_creation_catalog(self) -> CharacterCreationCatalogResponse:
        """Project typed public creator definitions without executable code."""

        species: list[SpeciesCatalogEntry] = []
        variants: list[SpeciesVariantCatalogEntry] = []
        backgrounds: list[BackgroundCatalogEntry] = []
        classes: list[ClassCatalogEntry] = []
        subclasses: list[SubclassCatalogEntry] = []
        starting_equipment_packages: list[
            StartingEquipmentPackageCatalogEntry
        ] = []
        starting_apparel_packages: list[
            StartingApparelPackageCatalogEntry
        ] = []
        body_recipes: list[ContentRecipe] = []
        for declaration in self.content_system.registry.declarations.values():
            if (
                declaration.mode is ContentDeclarationMode.FACTORY
                and declaration.construction is not None
                and declaration.ref.definition_kind
                is ContentDefinitionKind.CREATURE
                and {"character_body", "player_capable"}
                <= set(declaration.descriptor.tags)
            ):
                try:
                    parameters = (
                        declaration.construction.parameter_model.model_validate(
                            {},
                        )
                    )
                except ValidationError:
                    parameters = None
                if parameters is not None:
                    body_recipes.append(
                        ContentRecipe.create(
                            ref=declaration.ref,
                            parameters=parameters.model_dump(mode="json"),
                        ),
                    )
            if (
                declaration.mode is not ContentDeclarationMode.TYPED_DEFINITION
                or declaration.definition_payload is None
                or declaration.descriptor.visibility
                is not ContentVisibility.PUBLIC
            ):
                continue
            payload = declaration.definition_payload
            if isinstance(payload, SpeciesDefinition):
                species.append(
                    SpeciesCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                    ),
                )
            elif isinstance(payload, SpeciesVariantDefinition):
                variants.append(
                    SpeciesVariantCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                    ),
                )
            elif isinstance(payload, BackgroundDefinition):
                backgrounds.append(
                    BackgroundCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                    ),
                )
            elif isinstance(payload, ClassDefinition):
                classes.append(
                    ClassCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                    ),
                )
            elif isinstance(payload, SubclassDefinition):
                subclasses.append(
                    SubclassCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                    ),
                )
            elif isinstance(payload, StartingEquipmentPackageDefinition):
                if "starting_apparel" in declaration.descriptor.tags:
                    starting_apparel_packages.append(
                        StartingApparelPackageCatalogEntry(
                            ref=declaration.ref,
                            descriptor=declaration.descriptor,
                            definition=payload,
                        ),
                    )
                elif "starting_holdings" not in declaration.descriptor.tags:
                    starting_equipment_packages.append(
                        StartingEquipmentPackageCatalogEntry(
                            ref=declaration.ref,
                            descriptor=declaration.descriptor,
                            definition=payload,
                        ),
                    )
        key = lambda row: row.ref.identity_key
        body_presets = tuple(
            sorted(
                (
                    preset
                    for preset in self.content_system.registry.recipe_presets.values()
                    if (
                        preset.recipe.ref.definition_kind
                        is ContentDefinitionKind.CREATURE
                        and "player_capable" in preset.descriptor.tags
                    )
                ),
                key=lambda preset: preset.ref.identity_key,
            ),
        )
        return CharacterCreationCatalogResponse(
            content_set_digest=self.content_system.content_set_digest,
            appearance_catalog=_character_appearance_catalog(),
            body_recipes=tuple(
                sorted(body_recipes, key=lambda recipe: recipe.ref.identity_key),
            ),
            body_recipe_presets=body_presets,
            species=tuple(sorted(species, key=key)),
            species_variants=tuple(sorted(variants, key=key)),
            backgrounds=tuple(sorted(backgrounds, key=key)),
            classes=tuple(sorted(classes, key=key)),
            subclasses=tuple(sorted(subclasses, key=key)),
            creation_plans=compose_character_creation_plans(),
            starting_equipment_packages=tuple(sorted(
                starting_equipment_packages,
                key=key,
            )),
            starting_apparel_requirement=BuildChoiceRequirement(
                choice_id=STARTING_APPAREL_CHOICE_ID,
                choice_kind=(
                    ChoiceRequirementKind.STARTING_APPAREL_PACKAGE
                ),
                minimum_selections=1,
                maximum_selections=1,
                allowed_refs=tuple(
                    row.ref
                    for row in sorted(starting_apparel_packages, key=key)
                ),
            ),
            starting_apparel_packages=tuple(sorted(
                starting_apparel_packages,
                key=key,
            )),
        )

    def validate_new_character(
        self,
        principal_id: UUID,
        request: CharacterCreationValidationRequest,
    ) -> CharacterBuildValidationResponse:
        """Validate a creation draft under the owner's exact profile policy."""

        settings = self.ensure_profile_settings(principal_id)
        plan, plan_issues = self._resolve_creation_plan(request)
        normalized_build = (
            plan.normalize_requested_build(
                build=request.build,
                loadout=request.loadout,
            )
            if plan is not None
            else request.build.model_copy(update={"premade_id": None})
        )
        definition = self._normalize_definition(
            normalized_build,
            character_id=UUID(int=0),
            definition_revision=1,
            earned_character_level=len(request.build.class_levels),
            settings=settings,
        )
        loadout = self._normalize_loadout(
            request.loadout,
            character_id=definition.character_id,
            loadout_revision=1,
            based_on_definition_revision=definition.definition_revision,
        )
        return self._merge_issues(
            self._validate(definition, loadout, settings),
            [
                *self._identity_issues(request, settings),
                *plan_issues,
                *self._creation_issues(
                    normalized_build,
                    request.loadout,
                    plan,
                ),
            ],
        )

    def build_character_visual_preview(
        self,
        principal_id: UUID,
        request: CharacterCreationValidationRequest,
    ) -> CharacterBuildVisualPreviewResponse:
        """Materialize one valid draft in a disposable production runtime."""

        validation = self.validate_new_character(principal_id, request)
        if not validation.valid or validation.preview_digest is None:
            raise CharacterDirectoryBuildError(validation)
        settings = self.ensure_profile_settings(principal_id)
        preview_character_id = uuid5(
            _CHARACTER_PREVIEW_NAMESPACE,
            (
                f"{validation.preview_digest}:"
                f"{validation.content_set_digest}:"
                f"{validation.ruleset_digest}"
            ),
        )
        definition = self._normalize_definition(
            validation.normalized_build,
            character_id=preview_character_id,
            definition_revision=1,
            earned_character_level=len(
                validation.normalized_build.class_levels,
            ),
            settings=settings,
        )
        loadout = self._normalize_loadout(
            validation.normalized_loadout,
            character_id=preview_character_id,
            loadout_revision=1,
            based_on_definition_revision=1,
        )
        plan, _ = self._resolve_creation_plan(request)
        if plan is None:
            raise CharacterDirectoryBuildError(validation)
        return build_character_visual_preview(
            definition=definition,
            holdings=self._starter_holdings(
                definition,
                supplemental_holdings=plan.supplemental_holdings,
            ),
            loadout=loadout,
            normalized_build=validation.normalized_build,
            normalized_loadout=validation.normalized_loadout,
            preview_digest=validation.preview_digest,
            permissive_multiclass_prerequisites=(
                settings.permissive_multiclass_prerequisites
            ),
            multiclass_slot_rounding_policy=(
                settings.multiclass_slot_rounding_policy
            ),
        )

    def create_character(
        self,
        principal_id: UUID,
        request: CreateCharacterRequest,
    ) -> CharacterSnapshotResponse:
        """Atomically create one schema-2 character and three revision heads."""

        display_name = " ".join(request.display_name.split())
        if not display_name:
            raise ValueError("Character name cannot be blank")
        settings = self.ensure_profile_settings(principal_id)
        plan, plan_issues = self._resolve_creation_plan(request)
        normalized_build = (
            plan.normalize_requested_build(
                build=request.build,
                loadout=request.loadout,
            )
            if plan is not None
            else request.build.model_copy(update={"premade_id": None})
        )
        earned_character_level = len(normalized_build.class_levels)
        character_id = uuid5(
            _CHARACTER_IDEMPOTENCY_NAMESPACE,
            f"{principal_id}:{request.idempotency_key}",
        )
        definition = self._normalize_definition(
            normalized_build,
            character_id=character_id,
            definition_revision=1,
            earned_character_level=earned_character_level,
            settings=settings,
        )
        loadout = self._normalize_loadout(
            request.loadout,
            character_id=character_id,
            loadout_revision=1,
            based_on_definition_revision=1,
        )
        validation = self._merge_issues(
            self._validate(definition, loadout, settings),
            [
                *self._identity_issues(request, settings),
                *plan_issues,
                *self._creation_issues(
                    normalized_build,
                    request.loadout,
                    plan,
                ),
            ],
        )
        if not validation.valid:
            raise CharacterDirectoryBuildError(validation)
        if plan is None:
            raise CharacterDirectoryBuildError(validation)
        holdings = self._starter_holdings(
            definition,
            supplemental_holdings=plan.supplemental_holdings,
        )
        bootstrap = CharacterBootstrapCreate(
            character_id=character_id,
            owner_principal_id=principal_id,
            display_name=display_name,
            definition=definition,
            starter_holdings=holdings,
            starter_loadout=loadout,
            initial_advancement_award=CharacterAdvancementAwardCreate(
                award_id=uuid5(character_id, "creation-award"),
                character_id=character_id,
                level_delta=earned_character_level,
                source_kind=CharacterAdvancementSourceKind.CREATION,
                source_id=f"character:{character_id}:creation",
            ),
        )
        try:
            existing = self.get_character_snapshot(
                principal_id,
                character_id,
            )
        except NotFoundError:
            existing = None
        if existing is not None:
            self._require_exact_creation_retry(
                existing,
                display_name=display_name,
                definition=definition,
                holdings=holdings,
                loadout=loadout,
            )
            return existing
        try:
            self.repository.create_character_with_revisions(bootstrap)
        except ConflictError as conflict:
            try:
                concurrent = self.get_character_snapshot(
                    principal_id,
                    character_id,
                )
            except NotFoundError:
                raise conflict
            self._require_exact_creation_retry(
                concurrent,
                display_name=display_name,
                definition=definition,
                holdings=holdings,
                loadout=loadout,
            )
            return concurrent
        return self.get_character_snapshot(principal_id, character_id)

    def get_character(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CanonicalCharacterRecord:
        """Return an owned character with complete canonical heads."""

        character = self.repository.get_character(character_id)
        if character.owner_principal_id != principal_id:
            raise CharacterDirectoryOwnershipError(
                "Character belongs to another player",
            )
        return CanonicalCharacterRecord.model_validate(character.model_dump())

    def list_characters(
        self,
        principal_id: UUID,
    ) -> CharacterListResponse:
        """Return current summaries for exactly the authenticated owner."""

        self.repository.get_principal(principal_id)
        return CharacterListResponse(
            characters=tuple(
                CanonicalCharacterRecord.model_validate(
                    character.model_dump(),
                )
                for character in (
                    self.repository.list_characters_for_principal(
                        principal_id,
                    )
                )
            ),
        )

    def get_character_presentation_preferences(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterPresentationPreferencesRecord:
        """Return one owned character's non-mechanical art document."""

        self.get_character(principal_id, character_id)
        return self.repository.get_character_presentation_preferences(
            character_id,
        )

    def update_character_presentation_preferences(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: UpdateCharacterPresentationPreferencesRequest,
    ) -> CharacterPresentationPreferencesRecord:
        """CAS-replace one owned character's independent art document."""

        self.get_character(principal_id, character_id)
        return self.repository.update_character_presentation_preferences(
            character_id=character_id,
            expected_revision=request.expected_revision,
            preferences=request.preferences,
        )

    def create_saved_encounter_roster(
        self,
        principal_id: UUID,
        request: SaveEncounterRosterRequest,
    ) -> SavedEncounterRosterRecord:
        self.repository.get_principal(principal_id)
        return self.repository.create_saved_encounter_roster(
            SavedEncounterRosterCreate(
                saved_roster_id=f"saved.roster.{uuid4().hex}",
                owner_principal_id=principal_id,
                title=request.title,
                recipe=request.recipe,
            ),
        )

    def get_saved_encounter_roster(
        self,
        principal_id: UUID,
        saved_roster_id: str,
    ) -> SavedEncounterRosterRecord:
        return self.repository.get_saved_encounter_roster(
            principal_id,
            saved_roster_id,
        )

    def list_saved_encounter_rosters(
        self,
        principal_id: UUID,
    ) -> SavedEncounterRosterListResponse:
        return SavedEncounterRosterListResponse(
            rosters=self.repository.list_saved_encounter_rosters(
                principal_id,
            ),
        )

    def replace_saved_encounter_roster(
        self,
        principal_id: UUID,
        saved_roster_id: str,
        request: ReplaceSavedEncounterRosterRequest,
    ) -> SavedEncounterRosterRecord:
        return self.repository.replace_saved_encounter_roster(
            principal_id,
            saved_roster_id,
            SavedEncounterRosterReplace.model_validate(
                request.model_dump(),
            ),
        )

    def delete_saved_encounter_roster(
        self,
        principal_id: UUID,
        saved_roster_id: str,
        *,
        expected_revision: int,
        expected_recipe_digest: str,
    ) -> SavedEncounterRosterRecord:
        return self.repository.delete_saved_encounter_roster(
            principal_id,
            saved_roster_id,
            expected_revision=expected_revision,
            expected_recipe_digest=expected_recipe_digest,
        )

    def create_saved_encounter(
        self,
        principal_id: UUID,
        request: SaveEncounterRequest,
    ) -> SavedEncounterRecord:
        self.repository.get_principal(principal_id)
        return self.repository.create_saved_encounter(
            SavedEncounterCreate(
                saved_encounter_id=f"saved.encounter.{uuid4().hex}",
                owner_principal_id=principal_id,
                title=request.title,
                recipe=request.recipe,
            ),
        )

    def get_saved_encounter(
        self,
        principal_id: UUID,
        saved_encounter_id: str,
    ) -> SavedEncounterRecord:
        return self.repository.get_saved_encounter(
            principal_id,
            saved_encounter_id,
        )

    def list_saved_encounters(
        self,
        principal_id: UUID,
    ) -> SavedEncounterListResponse:
        return SavedEncounterListResponse(
            encounters=self.repository.list_saved_encounters(principal_id),
        )

    def replace_saved_encounter(
        self,
        principal_id: UUID,
        saved_encounter_id: str,
        request: ReplaceSavedEncounterRequest,
    ) -> SavedEncounterRecord:
        return self.repository.replace_saved_encounter(
            principal_id,
            saved_encounter_id,
            SavedEncounterReplace.model_validate(request.model_dump()),
        )

    def delete_saved_encounter(
        self,
        principal_id: UUID,
        saved_encounter_id: str,
        *,
        expected_revision: int,
        expected_recipe_digest: str,
    ) -> SavedEncounterRecord:
        return self.repository.delete_saved_encounter(
            principal_id,
            saved_encounter_id,
            expected_revision=expected_revision,
            expected_recipe_digest=expected_recipe_digest,
        )

    def get_profile(
        self,
        principal_id: UUID,
    ) -> CharacterProfileResponse:
        """Return profile policy, characters, and reconnectable game seats."""

        principal = self.repository.get_principal(principal_id)
        seats: list[CharacterProfileGameSeat] = []
        for membership in self.repository.list_memberships_for_principal(
            principal_id,
        ):
            controlled = tuple(
                assignment.entity_uuid
                for assignment in self.repository.list_entity_assignments(
                    membership.game_id,
                    active_only=False,
                )
                if assignment.membership_id == membership.membership_id
                and assignment.released_at is None
            )
            attachments = tuple(
                CharacterAttachmentSummary(
                    attachment_id=attachment.attachment_id,
                    game_id=attachment.game_id,
                    membership_id=attachment.membership_id,
                    client_kind=attachment.client_kind,
                    client_instance_id=attachment.client_instance_id,
                    connected_at=attachment.connected_at,
                    expires_at=attachment.expires_at,
                )
                for attachment in (
                    self.repository.list_attachments_for_membership(
                        membership.membership_id,
                        connected_only=True,
                    )
                )
            )
            seats.append(
                CharacterProfileGameSeat(
                    membership=membership,
                    controlled_entity_uuids=controlled,
                    active_attachments=attachments,
                ),
            )
        return CharacterProfileResponse(
            principal=principal,
            settings=self.ensure_profile_settings(principal_id),
            characters=tuple(
                CanonicalCharacterRecord.model_validate(
                    character.model_dump(),
                )
                for character in (
                    self.repository.list_characters_for_principal(
                        principal_id,
                    )
                )
            ),
            game_seats=tuple(seats),
        )

    def update_profile_settings_request(
        self,
        principal_id: UUID,
        request: UpdateCharacterProfileSettingsRequest,
    ) -> ProfileSettingsRecord:
        """Replace one profile policy through its public strict request."""

        return self.update_profile_settings(
            principal_id,
            expected_settings_version=request.expected_settings_version,
            permissive_multiclass_prerequisites=(
                request.permissive_multiclass_prerequisites
            ),
            multiclass_slot_rounding_policy=(
                request.multiclass_slot_rounding_policy
            ),
            allow_respec=request.allow_respec,
            spell_preparation_policy=request.spell_preparation_policy,
        )

    def get_character_snapshot(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterSnapshotResponse:
        character = self.get_character(principal_id, character_id)
        return CharacterSnapshotResponse(
            character=character,
            heads=CharacterRevisionHeads(
                definition_revision=character.current_definition_revision,
                definition_digest=character.current_definition_digest,
                holdings_revision=character.current_holdings_revision,
                holdings_digest=character.current_holdings_digest,
                loadout_revision=character.current_loadout_revision,
                loadout_digest=character.current_loadout_digest,
            ),
            definition=self.repository.get_character_definition_revision(
                character_id,
                definition_revision=character.current_definition_revision,
            ),
            holdings=self.repository.get_character_holdings_revision(
                character_id,
                holdings_revision=character.current_holdings_revision,
            ),
            loadout=self.repository.get_character_loadout_revision(
                character_id,
                loadout_revision=character.current_loadout_revision,
            ),
            advancement=self.get_advancement(principal_id, character_id),
        )

    def prepare_character_for_deployment(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterSnapshotResponse:
        """Rebase one stale content snapshot before its deployment is pinned.

        Content-set digests authenticate the complete authored registry, so a
        population-only catalog correction can advance the digest without
        invalidating the exact refs selected by an existing character.  The
        directory resolves every persisted ref through the canonical rebaser,
        validates the resulting build against the installed rules, and commits
        a new immutable definition/loadout head before gameplay sees it.
        """

        for attempt in range(2):
            snapshot = self.get_character_snapshot(
                principal_id,
                character_id,
            )
            definition = snapshot.definition.definition
            if not isinstance(definition, CharacterDefinitionRevisionV2):
                raise ConflictError(
                    "Character must be migrated to schema 2 before deployment",
                )
            settings = self.ensure_profile_settings(principal_id)
            if definition.ruleset_digest != settings.ruleset_digest:
                raise ConflictError(
                    "Character ruleset differs from the selected profile "
                    "settings",
                )
            if (
                definition.content_set_digest
                == self.content_system.content_set_digest
            ):
                return snapshot
            if (
                self.repository.get_active_character_deployment_lease(
                    character_id,
                )
                is not None
            ):
                raise ConflictError(
                    "Character cannot be rebased during an active deployment",
                )

            rebased = self._rebase_snapshot(snapshot)
            if not rebased.ready:
                details = "; ".join(
                    (
                        f"{'.'.join(issue.path)}: "
                        f"{issue.reason.value}: {issue.detail}"
                    )
                    for issue in rebased.issues
                )
                raise ConflictError(
                    "Character content cannot be rebased for deployment"
                    + (f": {details}" if details else ""),
                )
            rebased_definition = self._normalize_definition(
                rebased.build,
                character_id=character_id,
                definition_revision=definition.definition_revision + 1,
                earned_character_level=definition.earned_character_level,
                settings=settings,
            )
            rebased_loadout = self._normalize_loadout(
                rebased.loadout,
                character_id=character_id,
                loadout_revision=(
                    snapshot.loadout.loadout.loadout_revision + 1
                ),
                based_on_definition_revision=(
                    rebased_definition.definition_revision
                ),
            )
            validation = self._validate(
                rebased_definition,
                rebased_loadout,
                settings,
            )
            if not validation.valid:
                details = "; ".join(
                    (
                        f"{issue.code.value}@{'.'.join(issue.path)}"
                        + (f": {issue.detail}" if issue.detail else "")
                    )
                    for issue in validation.issues
                )
                raise ConflictError(
                    "Rebased character is not legal under installed content"
                    + (f": {details}" if details else ""),
                )
            try:
                self.repository.commit_character_revisions(
                    CharacterRevisionBundleCommit(
                        character_id=character_id,
                        expected_row_version=snapshot.character.row_version,
                        expected_heads=snapshot.heads,
                        require_no_active_deployment=True,
                        new_definition=rebased_definition,
                        new_holdings=(
                            rebased.holdings
                            if rebased.holdings_changed
                            else None
                        ),
                        new_loadout=rebased_loadout,
                    ),
                )
            except StaleVersionError:
                if attempt == 0:
                    continue
                raise
            return self.get_character_snapshot(principal_id, character_id)
        raise RuntimeError("unreachable character deployment rebase state")

    def get_definition_history(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterDefinitionHistoryResponse:
        self.get_character(principal_id, character_id)
        return CharacterDefinitionHistoryResponse(
            character_id=character_id,
            definitions=self.repository.list_character_definition_revisions(
                character_id,
            ),
        )

    def get_respec_seed(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterRespecSeedResponse:
        """Project one immutable character onto the installed content contracts."""

        self._mutation_context(principal_id, character_id)
        snapshot = self.get_character_snapshot(principal_id, character_id)
        definition = snapshot.definition.definition
        if not isinstance(definition, CharacterDefinitionRevisionV2):
            raise ConflictError(
                "Character must be migrated to schema 2 before progression",
            )
        rebased = self._rebase_snapshot(snapshot)
        settings = self.ensure_profile_settings(principal_id)
        return CharacterRespecSeedResponse(
            character_id=character_id,
            source=CharacterRespecSeedSource(
                character_row_version=snapshot.character.row_version,
                heads=snapshot.heads,
                definition_revision=definition.definition_revision,
                definition_digest=definition.definition_digest,
                content_set_digest=definition.content_set_digest,
                ruleset_digest=definition.ruleset_digest,
                definition_created_at=snapshot.definition.created_at,
                holdings_created_at=snapshot.holdings.created_at,
                loadout_created_at=snapshot.loadout.created_at,
            ),
            target_content_set_digest=self.content_system.content_set_digest,
            target_ruleset_digest=settings.ruleset_digest,
            ready=rebased.ready,
            editable_build=rebased.build if rebased.ready else None,
            editable_loadout=rebased.loadout if rebased.ready else None,
            changes=rebased.changes,
            issues=rebased.issues,
        )

    def get_advancement(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> CharacterAdvancementResponse:
        self.get_character(principal_id, character_id)
        return CharacterAdvancementResponse(
            character_id=character_id,
            earned_character_level=(
                self.repository.get_character_earned_level(character_id)
            ),
            awards=self.repository.list_character_advancement_awards(
                character_id,
            ),
        )

    def grant_admin_advancement_award(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: AdminCharacterAdvancementAwardRequest,
    ) -> CharacterAdvancementResponse:
        """Grant entitlement while leaving class and choice selection untouched."""

        self.get_character(principal_id, character_id)
        self.repository.create_character_advancement_award_if_expected_level(
            CharacterAdvancementAwardCreate(
                award_id=request.idempotency_key,
                character_id=character_id,
                level_delta=request.level_delta,
                source_kind=CharacterAdvancementSourceKind.DEVELOPER,
                source_id=f"admin:{request.idempotency_key}",
            ),
            expected_earned_character_level=(
                request.expected_earned_character_level
            ),
        )
        return self.get_advancement(principal_id, character_id)

    def validate_level_up(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterLevelUpRequest,
    ) -> CharacterBuildValidationResponse:
        character, current, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        self._assert_expected(character, request)
        rebased = self._rebase_current(character, current)
        requested_build = (
            self._normalize_premade_provenance(
                current=rebased.build,
                current_loadout=rebased.loadout,
                requested=request.build,
                requested_loadout=request.loadout,
            )
            if rebased.ready
            else request.build.model_copy(update={"premade_id": None})
        )
        transition_issues = self._level_up_issues(
            character_id,
            rebased.build,
            requested_build,
        ) if rebased.ready else []
        definition, loadout = self._normalize_mutation(
            character,
            requested_build,
            request.loadout,
            settings,
        )
        return self._merge_issues(
            self._validate(definition, loadout, settings),
            [
                *self._identity_issues(request, settings),
                *self._rebase_validation_issues(rebased),
                *transition_issues,
            ],
        )

    def level_up(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterLevelUpRequest,
    ) -> CharacterSnapshotResponse:
        replay = self._mutation_replay(
            principal_id,
            character_id,
            _LEVEL_UP_OPERATION,
            request,
        )
        if replay is not None:
            return replay
        validation = self.validate_level_up(
            principal_id,
            character_id,
            request,
        )
        if not validation.valid:
            raise CharacterDirectoryBuildError(validation)
        character, _, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        definition, loadout = self._normalize_mutation(
            character,
            validation.normalized_build,
            validation.normalized_loadout,
            settings,
        )
        current = self.repository.get_character_definition_revision(
            character_id,
            definition_revision=character.current_definition_revision,
        ).definition
        if not isinstance(current, CharacterDefinitionRevisionV2):
            raise ConflictError(
                "Character must be migrated to schema 2 before progression",
            )
        rebased = self._rebase_current(character, current)
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                require_no_active_deployment=True,
                new_definition=definition,
                new_holdings=(
                    rebased.holdings if rebased.holdings_changed else None
                ),
                new_loadout=loadout,
                mutation_receipt=self._mutation_receipt(
                    principal_id,
                    character_id,
                    _LEVEL_UP_OPERATION,
                    request,
                ),
            ),
        )
        return self._require_mutation_result(
            principal_id,
            character_id,
            _LEVEL_UP_OPERATION,
            request,
        )

    def validate_respec(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterRespecRequest,
    ) -> CharacterBuildValidationResponse:
        character, current, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        self._assert_expected(character, request)
        rebased = self._rebase_current(character, current)
        requested_build = (
            self._normalize_premade_provenance(
                current=rebased.build,
                current_loadout=rebased.loadout,
                requested=request.build,
                requested_loadout=request.loadout,
            )
            if rebased.ready
            else request.build.model_copy(update={"premade_id": None})
        )
        issues: list[CharacterBuildValidationIssueResponse] = []
        if not settings.allow_respec:
            issues.append(self._mutation_issue(CharacterMutationIssueCode.RESPEC_DISABLED))
        if (
            len(request.build.class_levels)
            != self.repository.get_character_earned_level(character_id)
        ):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.RESPEC_LEVEL_TOTAL_MISMATCH,
                    path=("class_levels",),
                ),
            )
        if (
            rebased.ready
            and not self._same_respec_origin(
                rebased.build,
                requested_build,
            )
        ):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.IMMUTABLE_ORIGIN_CHANGED,
                ),
            )
        definition, loadout = self._normalize_mutation(
            character,
            requested_build,
            request.loadout,
            settings,
        )
        return self._merge_issues(
            self._validate(definition, loadout, settings),
            [
                *self._identity_issues(request, settings),
                *self._rebase_validation_issues(rebased),
                *issues,
            ],
        )

    def respec(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterRespecRequest,
    ) -> CharacterSnapshotResponse:
        replay = self._mutation_replay(
            principal_id,
            character_id,
            _RESPEC_OPERATION,
            request,
        )
        if replay is not None:
            return replay
        validation = self.validate_respec(
            principal_id,
            character_id,
            request,
        )
        if not validation.valid:
            raise CharacterDirectoryBuildError(validation)
        character, current, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        definition, loadout = self._normalize_mutation(
            character,
            validation.normalized_build,
            validation.normalized_loadout,
            settings,
        )
        rebased = self._rebase_current(character, current)
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                require_no_active_deployment=True,
                new_definition=definition,
                new_holdings=(
                    rebased.holdings if rebased.holdings_changed else None
                ),
                new_loadout=loadout,
                mutation_receipt=self._mutation_receipt(
                    principal_id,
                    character_id,
                    _RESPEC_OPERATION,
                    request,
                ),
            ),
        )
        return self._require_mutation_result(
            principal_id,
            character_id,
            _RESPEC_OPERATION,
            request,
        )

    def validate_loadout(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterLoadoutMutationRequest,
    ) -> CharacterBuildValidationResponse:
        character, current, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        self._assert_expected(character, request)
        loadout = self._normalize_loadout(
            request.loadout,
            character_id=character_id,
            loadout_revision=character.current_loadout_revision + 1,
            based_on_definition_revision=(
                character.current_definition_revision
            ),
        )
        return self._merge_issues(
            self._validate(current, loadout, settings),
            self._identity_issues(request, settings),
        )

    def update_loadout(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterLoadoutMutationRequest,
    ) -> CharacterSnapshotResponse:
        replay = self._mutation_replay(
            principal_id,
            character_id,
            _LOADOUT_OPERATION,
            request,
        )
        if replay is not None:
            return replay
        validation = self.validate_loadout(
            principal_id,
            character_id,
            request,
        )
        if not validation.valid:
            raise CharacterDirectoryBuildError(validation)
        character = self.get_character(principal_id, character_id)
        loadout = self._normalize_loadout(
            request.loadout,
            character_id=character_id,
            loadout_revision=character.current_loadout_revision + 1,
            based_on_definition_revision=(
                character.current_definition_revision
            ),
        )
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                require_no_active_deployment=True,
                new_loadout=loadout,
                mutation_receipt=self._mutation_receipt(
                    principal_id,
                    character_id,
                    _LOADOUT_OPERATION,
                    request,
                ),
            ),
        )
        return self._require_mutation_result(
            principal_id,
            character_id,
            _LOADOUT_OPERATION,
            request,
        )

    def update_character_equipment(
        self,
        principal_id: UUID,
        character_id: UUID,
        request: CharacterEquipmentMutationRequest,
    ) -> CharacterSnapshotResponse:
        """Apply one durable gear change through isolated engine authority."""

        replay = self._mutation_replay(
            principal_id,
            character_id,
            _EQUIPMENT_OPERATION,
            request,
        )
        if replay is not None:
            return replay
        character, definition, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        self._assert_expected(character, request)
        if (
            request.expected_content_set_digest
            != self.content_system.content_set_digest
        ):
            raise ConflictError(
                "Character equipment content set expectation is stale",
            )
        if (
            definition.content_set_digest
            != request.expected_content_set_digest
        ):
            raise ConflictError(
                "Character equipment content identity is not current",
            )
        if request.expected_ruleset_digest != settings.ruleset_digest:
            raise ConflictError(
                "Character equipment ruleset expectation is stale",
            )
        if definition.ruleset_digest != request.expected_ruleset_digest:
            raise ConflictError(
                "Character equipment ruleset identity is not current",
            )
        holdings = self.repository.get_character_holdings_revision(
            character_id,
            holdings_revision=character.current_holdings_revision,
        ).holdings
        if not any(
            item.character_item_id == request.operation.character_item_id
            for item in holdings.items
        ):
            raise ConflictError(
                "Character equipment character_item_id is not in holdings",
            )
        loadout = self.repository.get_character_loadout_revision(
            character_id,
            loadout_revision=character.current_loadout_revision,
        ).loadout
        resulting_holdings = mutate_character_equipment(
            definition=definition,
            holdings=holdings,
            loadout=loadout,
            operation=request.operation,
            expected_content_set_digest=request.expected_content_set_digest,
            expected_ruleset_digest=request.expected_ruleset_digest,
            permissive_multiclass_prerequisites=(
                settings.permissive_multiclass_prerequisites
            ),
            multiclass_slot_rounding_policy=(
                settings.multiclass_slot_rounding_policy
            ),
        )
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                require_no_active_deployment=True,
                new_holdings=resulting_holdings,
                mutation_receipt=self._mutation_receipt(
                    principal_id,
                    character_id,
                    _EQUIPMENT_OPERATION,
                    request,
                ),
            ),
        )
        return self._require_mutation_result(
            principal_id,
            character_id,
            _EQUIPMENT_OPERATION,
            request,
        )

    @staticmethod
    def _mutation_request_digest(
        request: _CharacterMutationRequest,
    ) -> str:
        return canonical_digest(
            request.model_dump(
                mode="json",
                exclude={"idempotency_key"},
            ),
        )

    def _mutation_receipt(
        self,
        principal_id: UUID,
        character_id: UUID,
        operation_kind: str,
        request: _CharacterMutationRequest,
    ) -> DirectoryMutationReceiptCreate:
        return DirectoryMutationReceiptCreate(
            owner_principal_id=principal_id,
            idempotency_key=request.idempotency_key,
            operation_kind=operation_kind,
            scope_id=character_id,
            request_digest=self._mutation_request_digest(request),
        )

    def _mutation_replay(
        self,
        principal_id: UUID,
        character_id: UUID,
        operation_kind: str,
        request: _CharacterMutationRequest,
    ) -> CharacterSnapshotResponse | None:
        self.get_character(principal_id, character_id)
        try:
            receipt = self.repository.get_directory_mutation_receipt(
                principal_id,
                request.idempotency_key,
            )
        except NotFoundError:
            return None
        if (
            receipt.operation_kind != operation_kind
            or receipt.scope_id != character_id
            or receipt.request_digest
            != self._mutation_request_digest(request)
        ):
            raise ConflictError(
                "Directory mutation idempotency key was reused with "
                "a different request",
            )
        return CharacterSnapshotResponse.model_validate(
            receipt.result_payload,
        )

    def _require_mutation_result(
        self,
        principal_id: UUID,
        character_id: UUID,
        operation_kind: str,
        request: _CharacterMutationRequest,
    ) -> CharacterSnapshotResponse:
        result = self._mutation_replay(
            principal_id,
            character_id,
            operation_kind,
            request,
        )
        if result is None:
            raise RuntimeError(
                "Committed character mutation has no durable receipt",
            )
        return result

    def _mutation_context(
        self,
        principal_id: UUID,
        character_id: UUID,
    ) -> tuple[
        CanonicalCharacterRecord,
        CharacterDefinitionRevisionV2,
        ProfileSettingsRecord,
    ]:
        character = self.get_character(principal_id, character_id)
        active_lease = self.repository.get_active_character_deployment_lease(
            character_id,
        )
        if active_lease is not None:
            raise ConflictError(
                "Character cannot be changed during an active deployment",
            )
        record = self.repository.get_character_definition_revision(
            character_id,
            definition_revision=character.current_definition_revision,
        )
        if not isinstance(record.definition, CharacterDefinitionRevisionV2):
            raise ConflictError(
                "Character must be migrated to schema 2 before progression",
            )
        return (
            character,
            record.definition,
            self.ensure_profile_settings(principal_id),
        )

    @staticmethod
    def _assert_expected(
        character: CanonicalCharacterRecord,
        request: _CharacterMutationRequest,
    ) -> None:
        expected = request.expected_heads
        if (
            character.row_version != request.expected_row_version
            or character.current_definition_revision
            != expected.definition_revision
            or character.current_definition_digest != expected.definition_digest
            or character.current_holdings_revision
            != expected.holdings_revision
            or character.current_holdings_digest != expected.holdings_digest
            or character.current_loadout_revision != expected.loadout_revision
            or character.current_loadout_digest != expected.loadout_digest
        ):
            raise StaleVersionError(
                f"Character {character.character_id} revision heads changed",
            )

    def _normalize_mutation(
        self,
        character: CanonicalCharacterRecord,
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
        settings: ProfileSettingsRecord,
    ) -> tuple[CharacterDefinitionRevisionV2, CharacterLoadoutRevisionV1]:
        definition = self._normalize_definition(
            build,
            character_id=character.character_id,
            definition_revision=character.current_definition_revision + 1,
            earned_character_level=len(build.class_levels),
            settings=settings,
        )
        return (
            definition,
            self._normalize_loadout(
                loadout,
                character_id=character.character_id,
                loadout_revision=character.current_loadout_revision + 1,
                based_on_definition_revision=definition.definition_revision,
            ),
        )

    def _normalize_definition(
        self,
        build: CharacterBuildDraft,
        *,
        character_id: UUID,
        definition_revision: int,
        earned_character_level: int,
        settings: ProfileSettingsRecord,
    ) -> CharacterDefinitionRevisionV2:
        return CharacterDefinitionRevisionV2.create(
            character_id=character_id,
            definition_revision=definition_revision,
            body_recipe=build.body_recipe,
            species_ref=build.species_ref,
            species_variant_ref=build.species_variant_ref,
            background_ref=build.background_ref,
            immutable_origin_choices=build.immutable_origin_choices,
            appearance=build.appearance,
            base_ability_scores=build.base_ability_scores,
            flexible_ability_bonuses=build.flexible_ability_bonuses,
            class_levels=build.class_levels,
            premade_id=build.premade_id,
            earned_character_level=earned_character_level,
            content_set_digest=self.content_system.content_set_digest,
            ruleset_digest=settings.ruleset_digest,
        )

    @staticmethod
    def _normalize_loadout(
        draft: CharacterLoadoutDraft,
        *,
        character_id: UUID,
        loadout_revision: int,
        based_on_definition_revision: int,
    ) -> CharacterLoadoutRevisionV1:
        return CharacterLoadoutRevisionV1.create(
            character_id=character_id,
            loadout_revision=loadout_revision,
            based_on_definition_revision=based_on_definition_revision,
            prepared_spells=draft.prepared_spells,
            feature_toggles=draft.feature_toggles,
        )

    def _starter_holdings(
        self,
        definition: CharacterDefinitionRevisionV2,
        *,
        supplemental_holdings: tuple[StarterHoldingTemplate, ...] = (),
    ) -> CharacterHoldingsRevision:
        """Materialize exact selected creation packages into revision one."""

        choices = (
            *definition.immutable_origin_choices,
            *(
                choice
                for level in definition.class_levels
                for choice in level.choices
            ),
        )
        items: list[CharacterItemV1] = []
        occupied_slots = set()
        package_choices = tuple(
            choice
            for choice in choices
            if isinstance(choice, StartingEquipmentPackageChoice)
        )
        apparel_choices = tuple(
            choice
            for choice in choices
            if isinstance(choice, StartingApparelPackageChoice)
        )
        for choice in (*package_choices, *apparel_choices):
            package = self.content_system.registry.resolve_typed_definition(
                choice.selected_ref,
                StartingEquipmentPackageDefinition,
            )
            for entry_index, entry in enumerate(package.entries):
                equipped_slot = entry.equipped_slot
                if isinstance(choice, StartingApparelPackageChoice):
                    if equipped_slot in occupied_slots:
                        equipped_slot = None
                if equipped_slot is not None:
                    occupied_slots.add(equipped_slot)
                items.append(CharacterItemV1.create(
                    character_item_id=uuid5(
                        definition.character_id,
                        (
                            "dnd-engine:starting-possession:v2:"
                            f"{choice.choice_type}:"
                            f"{choice.choice_id}:"
                            f"{choice.selected_ref.identity_key}:"
                            f"{entry_index}:{entry.recipe.recipe_digest}:"
                            f"{equipped_slot}"
                        ),
                    ),
                    recipe=entry.recipe,
                    quantity=entry.quantity,
                    equipped_slot=equipped_slot,
                ))
        items.extend(background_starting_holdings(
            character_id=definition.character_id,
            background_ref=definition.background_ref,
            registry=self.content_system.registry,
            occupied_slots=occupied_slots,
        ))
        for index, holding in enumerate(supplemental_holdings):
            equipped_slot = holding.equipped_slot
            if equipped_slot is not None:
                items = [
                    item.model_copy(update={"equipped_slot": None})
                    if item.equipped_slot == equipped_slot
                    else item
                    for item in items
                ]
                occupied_slots.add(equipped_slot)
            items.append(CharacterItemV1.create(
                character_item_id=uuid5(
                    definition.character_id,
                    (
                        "dnd-engine:creation-plan-supplement:v1:"
                        f"{index}:{holding.recipe.recipe_digest}:"
                        f"{equipped_slot}"
                    ),
                ),
                recipe=holding.recipe,
                quantity=holding.quantity,
                equipped_slot=equipped_slot,
            ))
        return CharacterHoldingsRevision.create(
            character_id=definition.character_id,
            holdings_revision=1,
            items=tuple(sorted(
                items,
                key=lambda item: item.character_item_id.hex,
            )),
        )

    def _resolve_creation_plan(
        self,
        request: CharacterCreationValidationRequest,
    ) -> tuple[
        CharacterCreationPlan | None,
        list[CharacterBuildValidationIssueResponse],
    ]:
        plans = {
            plan.plan_id: plan
            for plan in compose_character_creation_plans()
        }
        plan = plans.get(request.creation_plan_id)
        if plan is None:
            return None, [
                self._mutation_issue(
                    CharacterMutationIssueCode.UNKNOWN_CREATION_PLAN,
                    path=("creation_plan_id",),
                ),
            ]
        if plan.plan_digest != request.creation_plan_digest:
            return None, [
                self._mutation_issue(
                    CharacterMutationIssueCode.CREATION_PLAN_DIGEST_MISMATCH,
                    path=("creation_plan_digest",),
                ),
            ]
        return plan, []

    @staticmethod
    def _creation_issues(
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
        plan: CharacterCreationPlan | None,
    ) -> list[CharacterBuildValidationIssueResponse]:
        _ = loadout
        if plan is None:
            return []
        issues: list[CharacterBuildValidationIssueResponse] = []
        if len(build.class_levels) != plan.character_level_entitlement:
            issues.append(CharacterBuildValidationIssueResponse(
                code=(
                    CharacterMutationIssueCode
                    .CREATION_PLAN_LEVEL_MISMATCH
                ),
                path=("build", "class_levels"),
                detail=(
                    "The selected creation plan authorizes exactly "
                    f"{plan.character_level_entitlement} character levels."
                ),
            ))
        if plan.plan_kind is CharacterCreationPlanKind.BLANK_CUSTOM:
            apparel_choices = tuple(
                choice
                for choice in build.immutable_origin_choices
                if isinstance(choice, StartingApparelPackageChoice)
            )
            if len(apparel_choices) != 1:
                issues.append(CharacterBuildValidationIssueResponse(
                    code=(
                        CharacterMutationIssueCode
                        .INITIAL_APPAREL_SELECTION_REQUIRED
                    ),
                    path=("build", "immutable_origin_choices"),
                    detail=(
                        "New custom characters require exactly one exact "
                        "starting-apparel package."
                    ),
                ))
        return issues

    def _validate(
        self,
        definition: CharacterDefinitionRevisionV2,
        loadout: CharacterLoadoutRevisionV1,
        settings: ProfileSettingsRecord,
    ) -> CharacterBuildValidationResponse:
        result = CharacterBuildValidator(
            self.content_system,
            expected_ruleset_digest=settings.ruleset_digest,
            multiclass_slot_rounding_policy=(
                settings.multiclass_slot_rounding_policy
            ),
            permissive_multiclass_prerequisites=(
                settings.permissive_multiclass_prerequisites
            ),
        ).validate(definition, loadout)
        return _validation_response(result, definition, loadout)

    def _level_up_issues(
        self,
        character_id: UUID,
        current: CharacterBuildDraft,
        build: CharacterBuildDraft,
    ) -> list[CharacterBuildValidationIssueResponse]:
        issues: list[CharacterBuildValidationIssueResponse] = []
        if (
            len(build.class_levels) != len(current.class_levels) + 1
            or build.class_levels[:-1] != current.class_levels
        ):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.LEVEL_UP_MUST_APPEND_ONE_LEVEL,
                    path=("class_levels",),
                ),
            )
        if (
            len(build.class_levels)
            > self.repository.get_character_earned_level(character_id)
        ):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.LEVEL_ENTITLEMENT_UNAVAILABLE,
                    path=("class_levels",),
                ),
            )
        if not self._same_level_up_foundation(current, build):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.IMMUTABLE_ORIGIN_CHANGED,
                ),
            )
        return issues

    @staticmethod
    def _same_respec_origin(
        current: CharacterBuildDraft,
        draft: CharacterBuildDraft,
    ) -> bool:
        return (
            current.body_recipe == draft.body_recipe
            and current.species_ref == draft.species_ref
            and current.species_variant_ref == draft.species_variant_ref
            and current.background_ref == draft.background_ref
            and current.immutable_origin_choices == draft.immutable_origin_choices
        )

    @classmethod
    def _same_level_up_foundation(
        cls,
        current: CharacterBuildDraft,
        draft: CharacterBuildDraft,
    ) -> bool:
        return (
            cls._same_respec_origin(current, draft)
            and current.appearance == draft.appearance
            and current.base_ability_scores == draft.base_ability_scores
            and current.flexible_ability_bonuses
            == draft.flexible_ability_bonuses
        )

    @staticmethod
    def _normalize_premade_provenance(
        *,
        current: CharacterBuildDraft,
        current_loadout: CharacterLoadoutDraft,
        requested: CharacterBuildDraft,
        requested_loadout: CharacterLoadoutDraft,
    ) -> CharacterBuildDraft:
        """Retain a premade identity only for an otherwise exact snapshot.

        ``premade_id`` is server-owned provenance, not a client authority or
        an immutable-origin field.  A respec or level-up that diverges from
        the exact premade structure clears it deterministically.
        """

        without_premade = {"premade_id": None}
        retains_premade = (
            current.model_copy(update=without_premade)
            == requested.model_copy(update=without_premade)
            and current_loadout == requested_loadout
        )
        return requested.model_copy(update={
            "premade_id": current.premade_id if retains_premade else None,
        })

    def _rebase_snapshot(
        self,
        snapshot: CharacterSnapshotResponse,
    ) -> CharacterContentRebaseResult:
        definition = snapshot.definition.definition
        if not isinstance(definition, CharacterDefinitionRevisionV2):
            raise ConflictError(
                "Character must be migrated to schema 2 before progression",
            )
        return rebase_character_content(
            registry=self.content_system.registry,
            build=_draft_from_definition(definition),
            loadout=_draft_from_loadout(snapshot.loadout.loadout),
            holdings=snapshot.holdings.holdings,
        )

    def _rebase_current(
        self,
        character: CanonicalCharacterRecord,
        definition: CharacterDefinitionRevisionV2,
    ) -> CharacterContentRebaseResult:
        holdings = self.repository.get_character_holdings_revision(
            character.character_id,
            holdings_revision=character.current_holdings_revision,
        )
        loadout = self.repository.get_character_loadout_revision(
            character.character_id,
            loadout_revision=character.current_loadout_revision,
        )
        return rebase_character_content(
            registry=self.content_system.registry,
            build=_draft_from_definition(definition),
            loadout=_draft_from_loadout(loadout.loadout),
            holdings=holdings.holdings,
        )

    @staticmethod
    def _rebase_validation_issues(
        rebased: CharacterContentRebaseResult,
    ) -> list[CharacterBuildValidationIssueResponse]:
        return [
            CharacterBuildValidationIssueResponse(
                code=(
                    CharacterMutationIssueCode.CONTENT_REBASE_UNRESOLVABLE
                ),
                path=issue.path,
                content_refs=(issue.source_ref,),
                detail=f"{issue.reason.value}: {issue.detail}",
            )
            for issue in rebased.issues
        ]

    @staticmethod
    def _mutation_issue(
        code: CharacterMutationIssueCode,
        *,
        path: tuple[str, ...] = (),
    ) -> CharacterBuildValidationIssueResponse:
        return CharacterBuildValidationIssueResponse(
            code=code,
            path=path,
        )

    @staticmethod
    def _merge_issues(
        result: CharacterBuildValidationResponse,
        additional: list[CharacterBuildValidationIssueResponse],
    ) -> CharacterBuildValidationResponse:
        if not additional:
            return result
        return CharacterBuildValidationResponse(
            valid=False,
            issues=(*additional, *result.issues),
            preview=None,
            normalized_build=result.normalized_build,
            normalized_loadout=result.normalized_loadout,
            content_set_digest=result.content_set_digest,
            ruleset_digest=result.ruleset_digest,
            preview_digest=None,
        )

    def _identity_issues(
        self,
        request: (
            CharacterBuildValidationRequest
            | CharacterLoadoutMutationRequest
        ),
        settings: ProfileSettingsRecord,
    ) -> list[CharacterBuildValidationIssueResponse]:
        issues: list[CharacterBuildValidationIssueResponse] = []
        if (
            request.expected_content_set_digest
            != self.content_system.content_set_digest
        ):
            issues.append(
                CharacterBuildValidationIssueResponse(
                    code=CharacterBuildIssueCode.CONTENT_SET_MISMATCH,
                    path=("expected_content_set_digest",),
                    detail="Loaded content set changed; refresh the creator catalog",
                ),
            )
        if request.expected_ruleset_digest != settings.ruleset_digest:
            issues.append(
                CharacterBuildValidationIssueResponse(
                    code=CharacterBuildIssueCode.RULESET_MISMATCH,
                    path=("expected_ruleset_digest",),
                    detail="Profile build rules changed; refresh profile settings",
                ),
            )
        return issues

    @staticmethod
    def _require_exact_creation_retry(
        existing: CharacterSnapshotResponse,
        *,
        display_name: str,
        definition: CharacterDefinitionRevisionV2,
        holdings: CharacterHoldingsRevision,
        loadout: CharacterLoadoutRevisionV1,
    ) -> None:
        if (
            existing.character.display_name != display_name
            or existing.definition.definition != definition
            or existing.holdings.holdings != holdings
            or existing.loadout.loadout != loadout
        ):
            raise ConflictError(
                "Character creation idempotency key was reused with "
                "different selections",
            )


def _validation_response(
    result: CharacterBuildValidationResult,
    definition: CharacterDefinitionRevisionV2,
    loadout: CharacterLoadoutRevisionV1,
) -> CharacterBuildValidationResponse:
    issues = tuple(
        CharacterBuildValidationIssueResponse.model_validate(asdict(issue))
        for issue in result.issues
    )
    if result.preview is None:
        preview = None
    else:
        source = result.preview
        preview = CharacterBuildPreviewResponse(
            class_level_counts=source.class_level_counts,
            automatic_grant_refs=source.automatic_grant_refs,
            grant_schedule=tuple(
                CharacterGrantScheduleEntryResponse.model_validate(
                    asdict(entry),
                )
                for entry in source.grant_schedule
            ),
            final_known_spell_refs=source.final_known_spell_refs,
            caster_contributions=tuple(
                CasterContributionPreviewResponse.model_validate(
                    asdict(contribution),
                )
                for contribution in source.caster_contributions
            ),
            effective_spellcaster_level=source.effective_spellcaster_level,
            normal_spell_slots=source.normal_spell_slots,
            final_known_spells=tuple(
                KnownSpellGrantPreviewResponse.model_validate(asdict(spell))
                for spell in source.final_known_spells
            ),
            origin_innate_spells=tuple(
                OriginInnateSpellGrantPreviewResponse.model_validate(
                    asdict(spell),
                )
                for spell in source.origin_innate_spells
            ),
        )
    return CharacterBuildValidationResponse(
        valid=result.valid,
        issues=issues,
        preview=preview,
        normalized_build=_draft_from_definition(definition),
        normalized_loadout=_draft_from_loadout(loadout),
        content_set_digest=definition.content_set_digest,
        ruleset_digest=definition.ruleset_digest,
        preview_digest=(
            None
            if preview is None
            else canonical_digest(preview.model_dump(mode="json"))
        ),
    )


def _draft_from_definition(
    definition: CharacterDefinitionRevisionV2,
) -> CharacterBuildDraft:
    return CharacterBuildDraft(
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
    )


def _draft_from_loadout(
    loadout: CharacterLoadoutRevisionV1,
) -> CharacterLoadoutDraft:
    return CharacterLoadoutDraft(
        prepared_spells=loadout.prepared_spells,
        feature_toggles=loadout.feature_toggles,
    )
