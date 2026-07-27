"""Transport-neutral persistent character composition service."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID, uuid5

from pydantic import ValidationError

from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterBuildValidationResult,
    CharacterBuildValidator,
)
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_premade_build,
    starter_holdings_for_build,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.durable_characters import (
    BackgroundDefinition,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterItemV1,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    StartingEquipmentPackageChoice,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import ContentFidelity
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
    CharacterBuildDraft,
    CharacterBuildPreviewResponse,
    CharacterBuildValidationIssueResponse,
    CharacterBuildValidationRequest,
    CharacterBuildValidationResponse,
    CharacterCreationCatalogResponse,
    CharacterDefinitionHistoryResponse,
    CharacterGrantScheduleEntryResponse,
    CharacterLevelUpRequest,
    CharacterListResponse,
    CharacterLoadoutDraft,
    CharacterLoadoutMutationRequest,
    CharacterMutationIssueCode,
    CharacterOriginImplementation,
    CharacterOriginImplementationStatus,
    CharacterAttachmentSummary,
    CharacterProfileGameSeat,
    CharacterProfileResponse,
    CharacterRespecRequest,
    CharacterSnapshotResponse,
    ClassCatalogEntry,
    CasterContributionPreviewResponse,
    CreateCharacterRequest,
    KnownSpellGrantPreviewResponse,
    SpeciesCatalogEntry,
    SpeciesVariantCatalogEntry,
    StartingEquipmentPackageCatalogEntry,
    SubclassCatalogEntry,
    UpdateCharacterProfileSettingsRequest,
)
from server.game_directory.contracts import (
    CanonicalCharacterRecord,
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    DirectoryMutationReceiptCreate,
    CharacterRevisionBundleCommit,
    CharacterRevisionHeads,
    ProfileSettingsCreate,
    ProfileSettingsRecord,
    ProfileSettingsUpdate,
    SpellPreparationPolicy,
)
from server.game_directory.canonical import canonical_digest
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
_LEVEL_UP_OPERATION = "character.level_up"
_RESPEC_OPERATION = "character.respec"
_LOADOUT_OPERATION = "character.loadout"


def _origin_implementation(
    fidelity: ContentFidelity,
    notes: str,
) -> CharacterOriginImplementation:
    if fidelity is ContentFidelity.COMPLETE:
        return CharacterOriginImplementation(
            status=CharacterOriginImplementationStatus.AVAILABLE,
        )
    reason = notes.strip()
    if not reason:
        raise RuntimeError(
            "Blocked character origins require exact provenance notes",
        )
    return CharacterOriginImplementation(
        status=CharacterOriginImplementationStatus.BLOCKED,
        blocked_reason=reason,
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
                        implementation=_origin_implementation(
                            declaration.provenance.fidelity,
                            declaration.provenance.notes,
                        ),
                    ),
                )
            elif isinstance(payload, SpeciesVariantDefinition):
                variants.append(
                    SpeciesVariantCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                        implementation=_origin_implementation(
                            declaration.provenance.fidelity,
                            declaration.provenance.notes,
                        ),
                    ),
                )
            elif isinstance(payload, BackgroundDefinition):
                backgrounds.append(
                    BackgroundCatalogEntry(
                        ref=declaration.ref,
                        descriptor=declaration.descriptor,
                        definition=payload,
                        implementation=_origin_implementation(
                            declaration.provenance.fidelity,
                            declaration.provenance.notes,
                        ),
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
        premades = tuple(
            compose_builtin_premade_build(build)
            for _, build in sorted(BUILTIN_PREMADE_BUILDS.items())
        )
        return CharacterCreationCatalogResponse(
            content_set_digest=self.content_system.content_set_digest,
            body_recipes=tuple(
                sorted(body_recipes, key=lambda recipe: recipe.ref.identity_key),
            ),
            body_recipe_presets=body_presets,
            species=tuple(sorted(species, key=key)),
            species_variants=tuple(sorted(variants, key=key)),
            backgrounds=tuple(sorted(backgrounds, key=key)),
            classes=tuple(sorted(classes, key=key)),
            subclasses=tuple(sorted(subclasses, key=key)),
            premades=premades,
            starting_equipment_packages=tuple(sorted(
                starting_equipment_packages,
                key=key,
            )),
        )

    def validate_new_character(
        self,
        principal_id: UUID,
        request: CharacterBuildValidationRequest,
    ) -> CharacterBuildValidationResponse:
        """Validate a creation draft under the owner's exact profile policy."""

        settings = self.ensure_profile_settings(principal_id)
        definition = self._normalize_definition(
            request.build,
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
                *self._creation_issues(request.build, request.loadout),
            ],
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
        earned_character_level = len(request.build.class_levels)
        character_id = uuid5(
            _CHARACTER_IDEMPOTENCY_NAMESPACE,
            f"{principal_id}:{request.idempotency_key}",
        )
        definition = self._normalize_definition(
            request.build,
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
                *self._creation_issues(request.build, request.loadout),
            ],
        )
        if not validation.valid:
            raise CharacterDirectoryBuildError(validation)
        holdings = self._starter_holdings(definition)
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
        transition_issues = self._level_up_issues(
            character_id,
            current,
            request.build,
        )
        definition, loadout = self._normalize_mutation(
            character,
            request.build,
            request.loadout,
            settings,
        )
        return self._merge_issues(
            self._validate(definition, loadout, settings),
            [
                *self._identity_issues(request, settings),
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
            request.build,
            request.loadout,
            settings,
        )
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                new_definition=definition,
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
        if not self._same_immutable_origin(current, request.build):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.IMMUTABLE_ORIGIN_CHANGED,
                ),
            )
        definition, loadout = self._normalize_mutation(
            character,
            request.build,
            request.loadout,
            settings,
        )
        return self._merge_issues(
            self._validate(definition, loadout, settings),
            [*self._identity_issues(request, settings), *issues],
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
        character, _, settings = self._mutation_context(
            principal_id,
            character_id,
        )
        definition, loadout = self._normalize_mutation(
            character,
            request.build,
            request.loadout,
            settings,
        )
        self.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=request.expected_row_version,
                expected_heads=request.expected_heads,
                new_definition=definition,
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

    @staticmethod
    def _mutation_request_digest(
        request: (
            CharacterLevelUpRequest
            | CharacterRespecRequest
            | CharacterLoadoutMutationRequest
        ),
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
        request: (
            CharacterLevelUpRequest
            | CharacterRespecRequest
            | CharacterLoadoutMutationRequest
        ),
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
        request: (
            CharacterLevelUpRequest
            | CharacterRespecRequest
            | CharacterLoadoutMutationRequest
        ),
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
        request: (
            CharacterLevelUpRequest
            | CharacterRespecRequest
            | CharacterLoadoutMutationRequest
        ),
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
        request: (
            CharacterLevelUpRequest
            | CharacterRespecRequest
            | CharacterLoadoutMutationRequest
        ),
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
    ) -> CharacterHoldingsRevision:
        """Materialize exact selected creation packages into revision one."""

        if definition.premade_id is not None:
            premade_build = BUILTIN_PREMADE_BUILDS.get(
                definition.premade_id,
            )
            if premade_build is None:
                raise ConflictError("Unknown premade character identity")
            authored_holdings = starter_holdings_for_build(premade_build)
            return CharacterHoldingsRevision.create(
                character_id=definition.character_id,
                holdings_revision=1,
                items=tuple(sorted(
                    (
                        CharacterItemV1.create(
                            character_item_id=uuid5(
                                definition.character_id,
                                (
                                    "dnd-engine:premade-holding:v2:"
                                    f"{index}:"
                                    f"{holding.recipe.recipe_digest}:"
                                    f"{holding.equipped_slot}"
                                ),
                            ),
                            recipe=holding.recipe,
                            quantity=holding.quantity,
                            equipped_slot=holding.equipped_slot,
                        )
                        for index, holding in enumerate(authored_holdings)
                    ),
                    key=lambda item: item.character_item_id.hex,
                )),
            )

        choices = (
            *definition.immutable_origin_choices,
            *(
                choice
                for level in definition.class_levels
                for choice in level.choices
            ),
        )
        items: list[CharacterItemV1] = []
        for choice in choices:
            if not isinstance(choice, StartingEquipmentPackageChoice):
                continue
            package = self.content_system.registry.resolve_typed_definition(
                choice.selected_ref,
                StartingEquipmentPackageDefinition,
            )
            for entry_index, entry in enumerate(package.entries):
                items.append(CharacterItemV1.create(
                    character_item_id=uuid5(
                        definition.character_id,
                        (
                            "dnd-engine:starting-equipment:v1:"
                            f"{choice.choice_id}:"
                            f"{choice.selected_ref.identity_key}:"
                            f"{entry_index}:{entry.recipe.recipe_digest}:"
                            f"{entry.equipped_slot}"
                        ),
                    ),
                    recipe=entry.recipe,
                    quantity=entry.quantity,
                    equipped_slot=entry.equipped_slot,
                ))
        return CharacterHoldingsRevision.create(
            character_id=definition.character_id,
            holdings_revision=1,
            items=tuple(sorted(
                items,
                key=lambda item: item.character_item_id.hex,
            )),
        )

    @staticmethod
    def _creation_issues(
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
    ) -> list[CharacterBuildValidationIssueResponse]:
        if build.premade_id is None:
            if len(build.class_levels) == 1:
                return []
            return [
                CharacterBuildValidationIssueResponse(
                    code=(
                        CharacterMutationIssueCode.INITIAL_LEVEL_MUST_BE_ONE
                    ),
                    path=("build", "class_levels"),
                    detail=(
                        "New custom characters must begin at character level "
                        "one."
                    ),
                ),
            ]

        authored_build = BUILTIN_PREMADE_BUILDS.get(build.premade_id)
        if authored_build is None:
            return [
                CharacterBuildValidationIssueResponse(
                    code=CharacterMutationIssueCode.UNKNOWN_PREMADE_ID,
                    path=("build", "premade_id"),
                    detail="The selected premade identity is not installed.",
                ),
            ]
        premade = compose_builtin_premade_build(authored_build)
        if build == premade.build and loadout == premade.loadout:
            return []
        return [
            CharacterBuildValidationIssueResponse(
                code=CharacterMutationIssueCode.PREMADE_BUILD_MISMATCH,
                path=("build",),
                detail=(
                    "Premade selections must use the exact authenticated "
                    "catalog build and loadout."
                ),
            ),
        ]

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
        current: CharacterDefinitionRevisionV2,
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
        if not self._same_immutable_origin(current, build):
            issues.append(
                self._mutation_issue(
                    CharacterMutationIssueCode.IMMUTABLE_ORIGIN_CHANGED,
                ),
            )
        return issues

    @staticmethod
    def _same_immutable_origin(
        current: CharacterDefinitionRevisionV2,
        draft: CharacterBuildDraft,
    ) -> bool:
        return (
            current.body_recipe == draft.body_recipe
            and current.species_ref == draft.species_ref
            and current.species_variant_ref == draft.species_variant_ref
            and current.background_ref == draft.background_ref
            and current.immutable_origin_choices == draft.immutable_origin_choices
            and current.appearance == draft.appearance
            and current.base_ability_scores == draft.base_ability_scores
            and current.flexible_ability_bonuses
            == draft.flexible_ability_bonuses
            and current.premade_id == draft.premade_id
        )

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
