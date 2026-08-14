"""Pure validation and preview derivation for schema-2 character builds.

This module resolves authenticated content data but never executes content
factories and never mutates a runtime entity.  It is the fail-closed seam used
before structural materialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.character_appearance import (
    resolve_player_character_appearance,
)
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_CHOICE_ID,
)
from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    AbilityScorePrerequisite,
    AbilityScoreImprovementChoice,
    AllOfPrerequisite,
    AnyOfPrerequisite,
    BackgroundDefinition,
    BuildChoiceRequirement,
    BuildChoiceSelection,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterLoadoutRevisionV1,
    ChoiceRequirementKind,
    ClassLevelPrerequisite,
    ClassDefinition,
    ClassLevelEntry,
    ClassSkillChoice,
    ElementalAncestryChoice,
    FeatChoice,
    FightingStyleChoice,
    HasFeaturePrerequisite,
    KnowsSpellPrerequisite,
    MetamagicChoice,
    NotPrerequisite,
    OriginTraitChoice,
    PrerequisiteExpression,
    ProficiencySubjectKind,
    ProficiencySubject,
    RitualPreparationPolicy,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellKnownChoice,
    SpellReplacementChoice,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
    StartingProficiencyChoice,
    SpellcastingSourceId,
    SubclassChoice,
    SubclassDefinition,
    TotalCharacterLevelPrerequisite,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_features import OriginStructuralFeatureDefinition
from dnd.core.content.origin_support import OriginRuntimeSupportStatus
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.progression import (
    CasterProgression,
    MulticlassSlotRoundingPolicy,
    SpellcastingClassContribution,
    effective_spellcaster_level,
    full_caster_spell_slots_for_level,
    maximum_spell_rank_for_contribution,
)

_TypedDefinition = TypeVar("_TypedDefinition", bound=BaseModel)


class CharacterBuildIssueCode(str, Enum):
    """Closed machine-readable reasons a durable build cannot be applied."""

    CONTENT_SET_MISMATCH = "content_set_mismatch"
    RULESET_MISMATCH = "ruleset_mismatch"
    LOADOUT_CHARACTER_MISMATCH = "loadout_character_mismatch"
    LOADOUT_DEFINITION_MISMATCH = "loadout_definition_mismatch"
    CONTENT_REF_UNKNOWN = "content_ref_unknown"
    CONTENT_CONTRACT_MISMATCH = "content_contract_mismatch"
    TYPED_DEFINITION_REQUIRED = "typed_definition_required"
    TYPED_DEFINITION_TYPE_MISMATCH = "typed_definition_type_mismatch"
    BODY_FACTORY_REQUIRED = "body_factory_required"
    BODY_NOT_CHARACTER_BODY = "body_not_character_body"
    BODY_PARAMETERS_INVALID = "body_parameters_invalid"
    APPEARANCE_SELECTION_INVALID = "appearance_selection_invalid"
    SPECIES_VARIANT_PARENT_MISMATCH = "species_variant_parent_mismatch"
    ORIGIN_IMPLEMENTATION_BLOCKED = "origin_implementation_blocked"
    SUBCLASS_PARENT_MISMATCH = "subclass_parent_mismatch"
    SUBCLASS_SELECTION_TIMING = "subclass_selection_timing"
    SUBCLASS_SELECTION_MISMATCH = "subclass_selection_mismatch"
    CLASS_LEVEL_DEFINITION_MISSING = "class_level_definition_missing"
    DUPLICATE_CHOICE_REQUIREMENT = "duplicate_choice_requirement"
    MISSING_REQUIRED_CHOICE = "missing_required_choice"
    UNEXPECTED_CHOICE = "unexpected_choice"
    CHOICE_KIND_MISMATCH = "choice_kind_mismatch"
    CHOICE_SELECTION_COUNT = "choice_selection_count"
    CHOICE_REF_NOT_ALLOWED = "choice_ref_not_allowed"
    CHOICE_PROFICIENCY_SUBJECT_NOT_ALLOWED = (
        "choice_proficiency_subject_not_allowed"
    )
    DUPLICATE_FIGHTING_STYLE = "duplicate_fighting_style"
    DUPLICATE_METAMAGIC = "duplicate_metamagic"
    MULTICLASS_PREREQUISITE_UNMET = "multiclass_prerequisite_unmet"
    SPELLCASTING_SOURCE_DUPLICATE = "spellcasting_source_duplicate"
    SPELL_CHOICE_SOURCE_UNKNOWN = "spell_choice_source_unknown"
    SPELL_LEARN_DUPLICATE = "spell_learn_duplicate"
    SPELL_REPLACEMENT_SOURCE_MISMATCH = (
        "spell_replacement_source_mismatch"
    )
    SPELL_REPLACEMENT_DUPLICATE = "spell_replacement_duplicate"
    PREPARED_SPELL_SOURCE_UNKNOWN = "prepared_spell_source_unknown"
    PREPARED_SPELL_SOURCE_INACTIVE = "prepared_spell_source_inactive"
    PREPARED_SPELL_NOT_ENTITLED = "prepared_spell_not_entitled"
    PREPARED_SPELL_RANK_UNAVAILABLE = "prepared_spell_rank_unavailable"


class CharacterGrantScheduleKind(str, Enum):
    """Closed payload kinds in the authored structural grant schedule."""

    AUTOMATIC_CONTENT = "automatic_content"
    SELECTED_CONTENT = "selected_content"
    PROFICIENCY = "proficiency"
    ABILITY_SCORE_INCREASE = "ability_score_increase"
    SPELL_LEARN = "spell_learn"
    SPELL_REPLACEMENT = "spell_replacement"


class CharacterGrantSourceKind(str, Enum):
    """Exact authored owner of one structural grant row."""

    SPECIES = "species"
    SPECIES_VARIANT = "species_variant"
    BACKGROUND = "background"
    FIRST_CLASS_PACKAGE = "first_class_package"
    MULTICLASS_CLASS_PACKAGE = "multiclass_class_package"
    CLASS_LEVEL = "class_level"
    SUBCLASS_LEVEL = "subclass_level"


@dataclass(frozen=True, slots=True)
class CharacterGrantProvenance:
    """Dependency-neutral source coordinates for one ledger-derived grant."""

    source_kind: CharacterGrantSourceKind
    source_ref: ContentRef
    character_level: int | None
    class_level_id: str | None
    class_level: int | None
    choice_id: str | None
    ordinal_path: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CharacterGrantScheduleEntry:
    """One typed authored grant plus its retry-stable materializer token.

    ``grant_token`` is stable for an exact immutable build and is intended to
    be combined with ``CharacterDefinitionRevisionV2.character_id`` by the
    runtime UUID derivation.  It deliberately contains no runtime Entity or
    component identity.
    """

    kind: CharacterGrantScheduleKind
    provenance: CharacterGrantProvenance
    grant_token: str
    content_ref: ContentRef | None = None
    proficiency: ProficiencySubject | None = None
    ability: AbilityScoreName | None = None
    amount: int | None = None
    replaced_content_ref: ContentRef | None = None


@dataclass(frozen=True, slots=True)
class CharacterBuildValidationIssue:
    """One typed build failure with a stable structural path."""

    code: CharacterBuildIssueCode
    path: tuple[str, ...]
    content_refs: tuple[ContentRef, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CasterContributionPreview:
    """One class contribution to the normal shared spell-slot table."""

    class_ref: ContentRef
    class_level: int
    progression: CasterProgression
    spellcasting_feature_class_level: int | None
    spellcasting_source_id: SpellcastingSourceId | None
    spellcasting_ability: AbilityScoreName | None
    maximum_spell_rank: int
    ritual_policy: RitualPreparationPolicy


@dataclass(frozen=True, slots=True)
class KnownSpellGrantPreview:
    """One final known spell with its exact casting-source provenance."""

    spell_ref: ContentRef
    provider_ref: ContentRef
    spellcasting_source_id: SpellcastingSourceId
    grant_token: str


@dataclass(frozen=True, slots=True)
class OriginInnateSpellGrantPreview:
    """One validated origin spell with exact source and usage semantics."""

    grant_id: str
    spell_ref: ContentRef
    provider_ref: ContentRef
    spellcasting_source_id: SpellcastingSourceId
    spellcasting_ability: AbilityScoreName
    provider_level: int
    fixed_cast_rank: int
    uses_per_long_rest: int | None
    grant_token: str


@dataclass(frozen=True, slots=True)
class CharacterBuildPreview:
    """Deterministic derived facts safe to show before materialization."""

    class_level_counts: tuple[tuple[ContentRef, int], ...]
    automatic_grant_refs: tuple[ContentRef, ...]
    grant_schedule: tuple[CharacterGrantScheduleEntry, ...]
    final_known_spell_refs: tuple[ContentRef, ...]
    caster_contributions: tuple[CasterContributionPreview, ...]
    effective_spellcaster_level: int
    normal_spell_slots: tuple[tuple[int, int], ...]
    final_known_spells: tuple[KnownSpellGrantPreview, ...] = ()
    origin_innate_spells: tuple[
        OriginInnateSpellGrantPreview,
        ...,
    ] = ()


@dataclass(frozen=True, slots=True)
class CharacterBuildValidationResult:
    """Validation issues and the preview produced only by a valid build."""

    issues: tuple[CharacterBuildValidationIssue, ...]
    preview: CharacterBuildPreview | None

    @property
    def valid(self) -> bool:
        return not self.issues


class CharacterBuildValidator:
    """Validate one durable build against one exact loaded content system."""

    def __init__(
        self,
        content_system: LoadedContentSystem,
        *,
        expected_ruleset_digest: str,
        multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy = (
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
        permissive_multiclass_prerequisites: bool = True,
    ) -> None:
        self._content_system = content_system
        self._registry = content_system.registry
        self._expected_ruleset_digest = expected_ruleset_digest
        self._multiclass_slot_rounding_policy = (
            multiclass_slot_rounding_policy
        )
        self._permissive_multiclass_prerequisites = (
            permissive_multiclass_prerequisites
        )

    def validate(
        self,
        definition: CharacterDefinitionRevisionV2,
        loadout: CharacterLoadoutRevisionV1,
    ) -> CharacterBuildValidationResult:
        """Return typed failures or one deterministic composition preview."""
        issues: list[CharacterBuildValidationIssue] = []
        selected_fighting_styles: dict[str, ContentRef] = {}
        selected_metamagic: dict[str, ContentRef] = {}

        self._validate_revision_heads(definition, loadout, issues)
        self._validate_body_recipe(definition, issues)

        species = self._resolve_origin_definition(
            definition.species_ref,
            SpeciesDefinition,
            ("species_ref",),
            issues,
        )
        if species is not None:
            try:
                resolve_player_character_appearance(
                    body_ref=definition.body_recipe.ref,
                    species_ref=definition.species_ref,
                    selection=definition.appearance,
                )
            except ValueError as exc:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.APPEARANCE_SELECTION_INVALID,
                    ("appearance",),
                    (definition.body_recipe.ref, definition.species_ref),
                    detail=str(exc),
                )
        variant = None
        if definition.species_variant_ref is not None:
            variant = self._resolve_origin_definition(
                definition.species_variant_ref,
                SpeciesVariantDefinition,
                ("species_variant_ref",),
                issues,
            )
            if (
                variant is not None
                and variant.parent_species_ref != definition.species_ref
            ):
                self._issue(
                    issues,
                    CharacterBuildIssueCode.SPECIES_VARIANT_PARENT_MISMATCH,
                    ("species_variant_ref",),
                    (
                        definition.species_variant_ref,
                        variant.parent_species_ref,
                        definition.species_ref,
                    ),
                )
        background = self._resolve_origin_definition(
            definition.background_ref,
            BackgroundDefinition,
            ("background_ref",),
            issues,
        )

        automatic_grants: list[ContentRef] = []
        origin_requirements: list[BuildChoiceRequirement] = []
        if species is not None:
            self._validate_requirement_proficiency_refs(
                species.choice_requirements,
                ("species_ref", "choice_requirements"),
                issues,
            )
            self._append_origin_grants(
                species,
                definition.earned_character_level,
                ("species_ref",),
                automatic_grants,
                issues,
            )
            self._validate_origin_innate_spell_refs(
                species,
                ("species_ref", "innate_spellcasting"),
                issues,
            )
            origin_requirements.extend(species.choice_requirements)
        if variant is not None:
            self._validate_requirement_proficiency_refs(
                variant.choice_requirements,
                ("species_variant_ref", "choice_requirements"),
                issues,
            )
            self._append_origin_grants(
                variant,
                definition.earned_character_level,
                ("species_variant_ref",),
                automatic_grants,
                issues,
            )
            self._validate_origin_innate_spell_refs(
                variant,
                ("species_variant_ref", "innate_spellcasting"),
                issues,
            )
            origin_requirements.extend(variant.choice_requirements)
        if background is not None:
            self._validate_requirement_proficiency_refs(
                background.choice_requirements,
                ("background_ref", "choice_requirements"),
                issues,
            )
            self._append_resolved_grants(
                background.automatic_grant_refs,
                ("background_ref", "automatic_grant_refs"),
                automatic_grants,
                issues,
            )
            origin_requirements.extend(background.choice_requirements)
        origin_selections = tuple(
            choice
            for choice in definition.immutable_origin_choices
            if not isinstance(choice, StartingApparelPackageChoice)
        )
        apparel_selections = tuple(
            choice
            for choice in definition.immutable_origin_choices
            if isinstance(choice, StartingApparelPackageChoice)
        )
        self._validate_choices(
            requirements=tuple(origin_requirements),
            selections=origin_selections,
            path=("immutable_origin_choices",),
            issues=issues,
        )
        self._validate_choices(
            requirements=(self._starting_apparel_requirement(),),
            selections=apparel_selections,
            path=("immutable_origin_choices",),
            issues=issues,
        )
        self._validate_unique_fighting_styles(
            definition.immutable_origin_choices,
            path=("immutable_origin_choices",),
            selected=selected_fighting_styles,
            issues=issues,
        )

        class_order: list[str] = []
        class_refs: dict[str, ContentRef] = {}
        class_counts: dict[str, int] = {}
        class_definitions: dict[str, ClassDefinition] = {}
        first_subclass_level: dict[str, int] = {}
        effective_abilities = _effective_creation_ability_scores(definition)
        owned_feature_keys = {
            ref.identity_key
            for ref in (
                background.automatic_grant_refs
                if background is not None
                else ()
            )
        }
        owned_feature_keys.update(
            ref.identity_key
            for choice in definition.immutable_origin_choices
            for ref in _choice_all_refs(choice)
        )
        known_spell_keys = {
            ref.identity_key
            for ref in (
                background.automatic_grant_refs
                if background is not None
                else ()
            )
            if ref.definition_kind == ContentDefinitionKind.SPELL
        }
        known_spell_keys.update(
            ref.identity_key
            for choice in definition.immutable_origin_choices
            for ref in _choice_all_refs(choice)
            if ref.definition_kind == ContentDefinitionKind.SPELL
        )
        source_independent_known_spell_keys = set(known_spell_keys)
        known_spells_by_source: dict[str, dict[str, ContentRef]] = {}

        for index, level in enumerate(definition.class_levels):
            level_path = ("class_levels", str(index))
            _add_origin_feature_keys_before_level(
                (species, variant),
                level.character_level,
                owned_feature_keys,
                known_spell_keys,
                source_independent_known_spell_keys,
            )
            class_key = level.class_ref.identity_key
            prior_class_counts = dict(class_counts)
            previous_count = class_counts.get(class_key, 0)
            if class_key not in class_counts:
                class_order.append(class_key)
                class_refs[class_key] = level.class_ref
            class_counts[class_key] = previous_count + 1

            class_definition = class_definitions.get(class_key)
            if class_definition is None:
                class_definition = self._resolve_typed_definition(
                    level.class_ref,
                    ClassDefinition,
                    (*level_path, "class_ref"),
                    issues,
                )
                if class_definition is not None:
                    class_definitions[class_key] = class_definition
                    self._validate_class_definition_refs(
                        level.class_ref,
                        class_definition,
                        (*level_path, "class_ref"),
                        issues,
                    )
            if class_definition is None:
                continue

            expected_requirements: list[BuildChoiceRequirement] = []
            if previous_count == 0:
                if (
                    level.character_level > 1
                    and not self._permissive_multiclass_prerequisites
                ):
                    self._validate_multiclass_prerequisites(
                        target_class_ref=level.class_ref,
                        target_class_definition=class_definition,
                        prior_class_order=class_order[:-1],
                        class_refs=class_refs,
                        class_definitions=class_definitions,
                        class_counts=prior_class_counts,
                        total_character_level=level.character_level - 1,
                        effective_abilities=effective_abilities,
                        owned_feature_keys=owned_feature_keys,
                        known_spell_keys=known_spell_keys,
                        path=(*level_path, "class_ref"),
                        issues=issues,
                    )
                package = (
                    class_definition.first_class_proficiencies
                    if level.character_level == 1
                    else class_definition.multiclass_proficiencies
                )
                expected_requirements.extend(package.choices)

            class_level_definition = _level_definition(
                class_definition,
                level.resulting_class_level,
            )
            if class_level_definition is None:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.CLASS_LEVEL_DEFINITION_MISSING,
                    (*level_path, "resulting_class_level"),
                    (level.class_ref,),
                    detail=str(level.resulting_class_level),
                )
            else:
                self._append_resolved_grants(
                    class_level_definition.automatic_grant_refs,
                    (*level_path, "automatic_grant_refs"),
                    automatic_grants,
                    issues,
                )
                owned_feature_keys.update(
                    ref.identity_key
                    for ref in class_level_definition.automatic_grant_refs
                )
                known_spell_keys.update(
                    ref.identity_key
                    for ref in class_level_definition.automatic_grant_refs
                    if ref.definition_kind == ContentDefinitionKind.SPELL
                )
                self._add_automatic_source_spells(
                    class_definition,
                    class_level_definition.automatic_grant_refs,
                    known_spells_by_source,
                )
                expected_requirements.extend(
                    class_level_definition.choice_requirements,
                )

            subclass_definition = self._validate_subclass(
                level,
                level_path,
                expected_requirements,
                first_subclass_level,
                issues,
            )
            if subclass_definition is not None:
                subclass_level_definition = _level_definition(
                    subclass_definition,
                    level.resulting_class_level,
                )
                if subclass_level_definition is not None:
                    self._append_resolved_grants(
                        subclass_level_definition.automatic_grant_refs,
                        (*level_path, "subclass_automatic_grant_refs"),
                        automatic_grants,
                        issues,
                    )
                    owned_feature_keys.update(
                        ref.identity_key
                        for ref in (
                            subclass_level_definition.automatic_grant_refs
                        )
                    )
                    known_spell_keys.update(
                        ref.identity_key
                        for ref in (
                            subclass_level_definition.automatic_grant_refs
                        )
                        if ref.definition_kind == ContentDefinitionKind.SPELL
                    )
                    self._add_automatic_source_spells(
                        class_definition,
                        subclass_level_definition.automatic_grant_refs,
                        known_spells_by_source,
                    )
                    expected_requirements.extend(
                        subclass_level_definition.choice_requirements,
                    )

            self._validate_choices(
                requirements=tuple(expected_requirements),
                selections=level.choices,
                path=(*level_path, "choices"),
                issues=issues,
            )
            self._validate_unique_fighting_styles(
                level.choices,
                path=(*level_path, "choices"),
                selected=selected_fighting_styles,
                issues=issues,
            )
            self._validate_unique_metamagic(
                level.choices,
                path=(*level_path, "choices"),
                selected=selected_metamagic,
                issues=issues,
            )
            self._validate_subclass_choice_matches_level(
                level,
                level_path,
                issues,
            )
            self._apply_source_spell_choices(
                class_definition=class_definition,
                choices=level.choices,
                path=(*level_path, "choices"),
                known_spells_by_source=known_spells_by_source,
                issues=issues,
            )
            for choice in level.choices:
                owned_feature_keys.update(
                    ref.identity_key for ref in _choice_all_refs(choice)
                )
                if isinstance(choice, (CantripChoice, SpellKnownChoice)):
                    known_spell_keys.update(
                        ref.identity_key for ref in choice.selected_refs
                    )
                elif isinstance(choice, SpellReplacementChoice):
                    known_spell_keys.add(choice.learned_spell_ref.identity_key)
                elif isinstance(choice, AbilityScoreImprovementChoice):
                    for ability, amount in choice.increases:
                        effective_abilities[ability] += amount
            _add_origin_feature_keys_at_level(
                (species, variant),
                level.character_level,
                owned_feature_keys,
                known_spell_keys,
                source_independent_known_spell_keys,
            )
            known_spell_keys = {
                *source_independent_known_spell_keys,
                *(
                    spell_key
                    for source_spells in known_spells_by_source.values()
                    for spell_key in source_spells
                ),
            }

        self._validate_loadout_refs(
            loadout,
            class_order,
            class_refs,
            class_counts,
            class_definitions,
            issues,
        )

        class_level_counts = tuple(
            (class_refs[key], class_counts[key]) for key in class_order
        )
        caster_previews: list[CasterContributionPreview] = []
        caster_rows: list[SpellcastingClassContribution] = []
        for class_key in class_order:
            class_definition = class_definitions.get(class_key)
            if class_definition is None:
                continue
            contribution = SpellcastingClassContribution(
                class_level=class_counts[class_key],
                progression=class_definition.caster_progression,
                spellcasting_feature_class_level=(
                    class_definition.spellcasting_feature_class_level
                ),
            )
            preview = CasterContributionPreview(
                class_ref=class_refs[class_key],
                class_level=class_counts[class_key],
                progression=class_definition.caster_progression,
                spellcasting_feature_class_level=(
                    class_definition.spellcasting_feature_class_level
                ),
                spellcasting_source_id=(
                    class_definition.spellcasting_source_id
                ),
                spellcasting_ability=class_definition.spellcasting_ability,
                maximum_spell_rank=maximum_spell_rank_for_contribution(
                    contribution,
                ),
                ritual_policy=class_definition.ritual_policy,
            )
            caster_previews.append(preview)
            caster_rows.append(contribution)
        effective_level = effective_spellcaster_level(
            caster_rows,
            policy=self._multiclass_slot_rounding_policy,
        )
        normal_slots = (
            tuple(sorted(full_caster_spell_slots_for_level(effective_level).items()))
            if effective_level > 0
            else ()
        )

        if issues:
            return CharacterBuildValidationResult(
                issues=tuple(issues),
                preview=None,
            )
        grant_schedule = self._build_grant_schedule(
            definition=definition,
            species=species,
            variant=variant,
            background=background,
            class_definitions=class_definitions,
        )
        source_by_provenance_ref = _spell_source_by_provenance_ref(
            definition,
            class_definitions,
        )
        final_known_spells = _final_known_spell_grants(
            grant_schedule,
            source_by_provenance_ref,
        )
        origin_innate_spells = _origin_innate_spell_grants(
            definition=definition,
            species=species,
            variant=variant,
            schedule=grant_schedule,
        )
        return CharacterBuildValidationResult(
            issues=(),
            preview=CharacterBuildPreview(
                class_level_counts=class_level_counts,
                automatic_grant_refs=tuple(automatic_grants),
                grant_schedule=grant_schedule,
                final_known_spell_refs=_final_known_spell_refs(
                    grant_schedule,
                    source_by_provenance_ref,
                    final_known_spells,
                ),
                final_known_spells=final_known_spells,
                origin_innate_spells=origin_innate_spells,
                caster_contributions=tuple(caster_previews),
                effective_spellcaster_level=effective_level,
                normal_spell_slots=normal_slots,
            ),
        )

    def _build_grant_schedule(
        self,
        *,
        definition: CharacterDefinitionRevisionV2,
        species: SpeciesDefinition | None,
        variant: SpeciesVariantDefinition | None,
        background: BackgroundDefinition | None,
        class_definitions: dict[str, ClassDefinition],
    ) -> tuple[CharacterGrantScheduleEntry, ...]:
        """Derive authored grants once validation has proven every reference."""
        schedule: list[CharacterGrantScheduleEntry] = []
        origin_choice_sources: dict[
            str,
            tuple[CharacterGrantSourceKind, ContentRef],
        ] = {}

        for source_kind, source_ref, origin in (
            (
                CharacterGrantSourceKind.SPECIES,
                definition.species_ref,
                species,
            ),
            (
                CharacterGrantSourceKind.SPECIES_VARIANT,
                definition.species_variant_ref,
                variant,
            ),
        ):
            if origin is None or source_ref is None:
                continue
            for row_index, row in enumerate(origin.level_grants):
                if row.character_level > definition.earned_character_level:
                    continue
                for grant_index, grant_ref in enumerate(row.grant_refs):
                    schedule.append(
                        _grant_schedule_entry(
                            kind=(
                                CharacterGrantScheduleKind
                                .AUTOMATIC_CONTENT
                            ),
                            provenance=CharacterGrantProvenance(
                                source_kind=source_kind,
                                source_ref=source_ref,
                                character_level=row.character_level,
                                class_level_id=None,
                                class_level=None,
                                choice_id=None,
                                ordinal_path=(row_index, grant_index),
                            ),
                            content_ref=grant_ref,
                        ),
                    )
            for source_index, source in enumerate(
                origin.innate_spellcasting,
            ):
                for grant_index, grant in enumerate(source.grants):
                    if (
                        grant.unlock_character_level
                        > definition.earned_character_level
                        or grant.spell_ref is None
                    ):
                        continue
                    schedule.append(
                        _grant_schedule_entry(
                            kind=(
                                CharacterGrantScheduleKind
                                .AUTOMATIC_CONTENT
                            ),
                            provenance=CharacterGrantProvenance(
                                source_kind=source_kind,
                                source_ref=source_ref,
                                character_level=(
                                    grant.unlock_character_level
                                ),
                                class_level_id=None,
                                class_level=None,
                                choice_id=None,
                                ordinal_path=(
                                    len(origin.level_grants),
                                    source_index,
                                    grant_index,
                                ),
                            ),
                            content_ref=grant.spell_ref,
                        ),
                    )
            for requirement in origin.choice_requirements:
                origin_choice_sources[requirement.choice_id] = (
                    source_kind,
                    source_ref,
                )

        if background is not None:
            for grant_index, grant_ref in enumerate(
                background.automatic_grant_refs,
            ):
                schedule.append(
                    _grant_schedule_entry(
                        kind=(
                            CharacterGrantScheduleKind.AUTOMATIC_CONTENT
                        ),
                        provenance=CharacterGrantProvenance(
                            source_kind=CharacterGrantSourceKind.BACKGROUND,
                            source_ref=definition.background_ref,
                            character_level=None,
                            class_level_id=None,
                            class_level=None,
                            choice_id=None,
                            ordinal_path=(grant_index,),
                        ),
                        content_ref=grant_ref,
                    ),
                )
            for requirement in background.choice_requirements:
                origin_choice_sources[requirement.choice_id] = (
                    CharacterGrantSourceKind.BACKGROUND,
                    definition.background_ref,
                )

        for choice_index, choice in enumerate(
            definition.immutable_origin_choices,
        ):
            if isinstance(choice, StartingApparelPackageChoice):
                continue
            source_kind, source_ref = origin_choice_sources[choice.choice_id]
            _append_choice_schedule(
                schedule,
                choice=choice,
                source_kind=source_kind,
                source_ref=source_ref,
                character_level=None,
                class_level_id=None,
                class_level=None,
                ordinal_prefix=(choice_index,),
            )

        seen_classes: set[str] = set()
        for level_index, level in enumerate(definition.class_levels):
            class_key = level.class_ref.identity_key
            class_definition = class_definitions[class_key]
            first_class_entry = class_key not in seen_classes
            choice_sources: dict[
                str,
                tuple[CharacterGrantSourceKind, ContentRef],
            ] = {}
            if first_class_entry:
                seen_classes.add(class_key)
                source_kind = (
                    CharacterGrantSourceKind.FIRST_CLASS_PACKAGE
                    if level.character_level == 1
                    else (
                        CharacterGrantSourceKind
                        .MULTICLASS_CLASS_PACKAGE
                    )
                )
                package = (
                    class_definition.first_class_proficiencies
                    if level.character_level == 1
                    else class_definition.multiclass_proficiencies
                )
                for subject_index, subject in enumerate(package.automatic):
                    schedule.append(
                        _grant_schedule_entry(
                            kind=CharacterGrantScheduleKind.PROFICIENCY,
                            provenance=CharacterGrantProvenance(
                                source_kind=source_kind,
                                source_ref=level.class_ref,
                                character_level=level.character_level,
                                class_level_id=level.class_level_id.value,
                                class_level=level.resulting_class_level,
                                choice_id=None,
                                ordinal_path=(level_index, subject_index),
                            ),
                            proficiency=subject,
                        ),
                    )
                if level.character_level == 1:
                    for ability_index, ability in enumerate(
                        class_definition.saving_throw_proficiencies,
                    ):
                        schedule.append(
                            _grant_schedule_entry(
                                kind=(
                                    CharacterGrantScheduleKind.PROFICIENCY
                                ),
                                provenance=CharacterGrantProvenance(
                                    source_kind=source_kind,
                                    source_ref=level.class_ref,
                                    character_level=level.character_level,
                                    class_level_id=(
                                        level.class_level_id.value
                                    ),
                                    class_level=level.resulting_class_level,
                                    choice_id=None,
                                    ordinal_path=(
                                        level_index,
                                        len(package.automatic)
                                        + ability_index,
                                    ),
                                ),
                                proficiency=ProficiencySubject(
                                    subject_kind=(
                                        ProficiencySubjectKind.SAVING_THROW
                                    ),
                                    subject_id=(
                                        f"saving_throw.{ability.value}"
                                    ),
                                ),
                            ),
                        )
                for requirement in package.choices:
                    choice_sources[requirement.choice_id] = (
                        source_kind,
                        level.class_ref,
                    )

            class_level_definition = _level_definition(
                class_definition,
                level.resulting_class_level,
            )
            if class_level_definition is not None:
                for grant_index, grant_ref in enumerate(
                    class_level_definition.automatic_grant_refs,
                ):
                    schedule.append(
                        _grant_schedule_entry(
                            kind=(
                                CharacterGrantScheduleKind
                                .AUTOMATIC_CONTENT
                            ),
                            provenance=CharacterGrantProvenance(
                                source_kind=(
                                    CharacterGrantSourceKind.CLASS_LEVEL
                                ),
                                source_ref=level.class_ref,
                                character_level=level.character_level,
                                class_level_id=level.class_level_id.value,
                                class_level=level.resulting_class_level,
                                choice_id=None,
                                ordinal_path=(level_index, grant_index),
                            ),
                            content_ref=grant_ref,
                        ),
                    )
                for requirement in (
                    class_level_definition.choice_requirements
                ):
                    choice_sources[requirement.choice_id] = (
                        CharacterGrantSourceKind.CLASS_LEVEL,
                        level.class_ref,
                    )

            if level.subclass_ref is not None:
                subclass = self._registry.resolve_typed_definition(
                    level.subclass_ref,
                    SubclassDefinition,
                )
                subclass_level_definition = _level_definition(
                    subclass,
                    level.resulting_class_level,
                )
                if subclass_level_definition is not None:
                    for grant_index, grant_ref in enumerate(
                        subclass_level_definition.automatic_grant_refs,
                    ):
                        schedule.append(
                            _grant_schedule_entry(
                                kind=(
                                    CharacterGrantScheduleKind
                                    .AUTOMATIC_CONTENT
                                ),
                                provenance=CharacterGrantProvenance(
                                    source_kind=(
                                        CharacterGrantSourceKind
                                        .SUBCLASS_LEVEL
                                    ),
                                    source_ref=level.subclass_ref,
                                    character_level=level.character_level,
                                    class_level_id=(
                                        level.class_level_id.value
                                    ),
                                    class_level=level.resulting_class_level,
                                    choice_id=None,
                                    ordinal_path=(
                                        level_index,
                                        grant_index,
                                    ),
                                ),
                                content_ref=grant_ref,
                            ),
                        )
                    for requirement in (
                        subclass_level_definition.choice_requirements
                    ):
                        choice_sources[requirement.choice_id] = (
                            CharacterGrantSourceKind.SUBCLASS_LEVEL,
                            level.subclass_ref,
                        )

            for choice_index, choice in enumerate(level.choices):
                source_kind, source_ref = choice_sources[choice.choice_id]
                _append_choice_schedule(
                    schedule,
                    choice=choice,
                    source_kind=source_kind,
                    source_ref=source_ref,
                    character_level=level.character_level,
                    class_level_id=level.class_level_id.value,
                    class_level=level.resulting_class_level,
                    ordinal_prefix=(level_index, choice_index),
                )
        expanded_schedule: list[CharacterGrantScheduleEntry] = []
        origin_source_kinds = {
            CharacterGrantSourceKind.SPECIES,
            CharacterGrantSourceKind.SPECIES_VARIANT,
            CharacterGrantSourceKind.BACKGROUND,
        }
        for entry in schedule:
            expanded_schedule.append(entry)
            if (
                entry.kind is not CharacterGrantScheduleKind.AUTOMATIC_CONTENT
                or entry.content_ref is None
                or entry.provenance.source_kind not in origin_source_kinds
            ):
                continue
            declaration = self._registry.resolve_definition(entry.content_ref)
            feature = declaration.definition_payload
            if not isinstance(feature, OriginStructuralFeatureDefinition):
                continue
            for subject_index, subject in enumerate(
                feature.automatic_proficiencies,
            ):
                expanded_schedule.append(
                    _grant_schedule_entry(
                        kind=CharacterGrantScheduleKind.PROFICIENCY,
                        provenance=CharacterGrantProvenance(
                            source_kind=entry.provenance.source_kind,
                            source_ref=entry.provenance.source_ref,
                            character_level=entry.provenance.character_level,
                            class_level_id=entry.provenance.class_level_id,
                            class_level=entry.provenance.class_level,
                            choice_id=entry.provenance.choice_id,
                            ordinal_path=(
                                *entry.provenance.ordinal_path,
                                subject_index,
                            ),
                        ),
                        content_ref=entry.content_ref,
                        proficiency=subject,
                    ),
                )
        return tuple(expanded_schedule)

    def _starting_apparel_requirement(self) -> BuildChoiceRequirement:
        """Return the installed exact apparel vocabulary without requiring it.

        Generic durable revisions predate this creator choice. New-character
        policy requires the row at the directory boundary; the structural
        validator accepts a missing row so old premades and stored definitions
        remain valid, while validating any supplied row fail-closed.
        """

        allowed_refs = tuple(sorted(
            (
                declaration.ref
                for declaration in self._registry.declarations.values()
                if (
                    declaration.mode
                    is ContentDeclarationMode.TYPED_DEFINITION
                    and isinstance(
                        declaration.definition_payload,
                        StartingEquipmentPackageDefinition,
                    )
                    and declaration.descriptor.visibility
                    is ContentVisibility.PUBLIC
                    and "starting_apparel" in declaration.descriptor.tags
                )
            ),
            key=lambda ref: ref.identity_key,
        ))
        return BuildChoiceRequirement(
            choice_id=STARTING_APPAREL_CHOICE_ID,
            choice_kind=ChoiceRequirementKind.STARTING_APPAREL_PACKAGE,
            minimum_selections=0,
            maximum_selections=1,
            allowed_refs=allowed_refs,
        )

    def _validate_revision_heads(
        self,
        definition: CharacterDefinitionRevisionV2,
        loadout: CharacterLoadoutRevisionV1,
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        if (
            definition.content_set_digest
            != self._content_system.content_set_digest
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.CONTENT_SET_MISMATCH,
                ("content_set_digest",),
            )
        if definition.ruleset_digest != self._expected_ruleset_digest:
            self._issue(
                issues,
                CharacterBuildIssueCode.RULESET_MISMATCH,
                ("ruleset_digest",),
            )
        if loadout.character_id != definition.character_id:
            self._issue(
                issues,
                CharacterBuildIssueCode.LOADOUT_CHARACTER_MISMATCH,
                ("loadout", "character_id"),
            )
        if (
            loadout.based_on_definition_revision
            != definition.definition_revision
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.LOADOUT_DEFINITION_MISMATCH,
                ("loadout", "based_on_definition_revision"),
            )

    def _validate_body_recipe(
        self,
        definition: CharacterDefinitionRevisionV2,
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        declaration = self._resolve_declaration(
            definition.body_recipe.ref,
            ("body_recipe", "ref"),
            issues,
        )
        if declaration is None:
            return
        if (
            declaration.mode != ContentDeclarationMode.FACTORY
            or declaration.construction is None
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.BODY_FACTORY_REQUIRED,
                ("body_recipe", "ref"),
                (definition.body_recipe.ref,),
            )
            return
        required_tags = {"character_body", "player_capable"}
        if not required_tags.issubset(declaration.descriptor.tags):
            self._issue(
                issues,
                CharacterBuildIssueCode.BODY_NOT_CHARACTER_BODY,
                ("body_recipe", "ref"),
                (definition.body_recipe.ref,),
                detail=",".join(sorted(required_tags)),
            )
            return
        try:
            declaration.construction.parameter_model.model_validate(
                definition.body_recipe.parameters,
            )
        except ValidationError as error:
            self._issue(
                issues,
                CharacterBuildIssueCode.BODY_PARAMETERS_INVALID,
                ("body_recipe", "parameters"),
                (definition.body_recipe.ref,),
                detail=str(error),
            )

    def _resolve_declaration(
        self,
        ref: ContentRef,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ):
        try:
            return self._registry.resolve_definition(ref)
        except KeyError:
            self._issue(
                issues,
                CharacterBuildIssueCode.CONTENT_REF_UNKNOWN,
                path,
                (ref,),
            )
        except ValueError as error:
            self._issue(
                issues,
                CharacterBuildIssueCode.CONTENT_CONTRACT_MISMATCH,
                path,
                (ref,),
                detail=str(error),
            )
        return None

    def _resolve_typed_definition(
        self,
        ref: ContentRef,
        expected_type: type[_TypedDefinition],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> _TypedDefinition | None:
        declaration = self._resolve_declaration(ref, path, issues)
        if declaration is None:
            return None
        if (
            declaration.mode != ContentDeclarationMode.TYPED_DEFINITION
            or declaration.definition_payload is None
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.TYPED_DEFINITION_REQUIRED,
                path,
                (ref,),
            )
            return None
        if not isinstance(declaration.definition_payload, expected_type):
            self._issue(
                issues,
                CharacterBuildIssueCode.TYPED_DEFINITION_TYPE_MISMATCH,
                path,
                (ref,),
                detail=expected_type.__name__,
            )
            return None
        return cast(_TypedDefinition, declaration.definition_payload)

    def _resolve_origin_definition(
        self,
        ref: ContentRef,
        expected_type: type[_TypedDefinition],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> _TypedDefinition | None:
        declaration = self._resolve_declaration(ref, path, issues)
        if declaration is None:
            return None
        if (
            declaration.mode != ContentDeclarationMode.TYPED_DEFINITION
            or declaration.definition_payload is None
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.TYPED_DEFINITION_REQUIRED,
                path,
                (ref,),
            )
            return None
        if not isinstance(declaration.definition_payload, expected_type):
            self._issue(
                issues,
                CharacterBuildIssueCode.TYPED_DEFINITION_TYPE_MISMATCH,
                path,
                (ref,),
                detail=expected_type.__name__,
            )
            return None
        payload = cast(
            SpeciesDefinition | SpeciesVariantDefinition | BackgroundDefinition,
            declaration.definition_payload,
        )
        if (
            payload.runtime_support.status
            is OriginRuntimeSupportStatus.BLOCKED
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.ORIGIN_IMPLEMENTATION_BLOCKED,
                path,
                (ref,),
                detail=payload.runtime_support.blocked_reason or "",
            )
            return None
        return cast(_TypedDefinition, payload)

    def _append_origin_grants(
        self,
        definition: SpeciesDefinition | SpeciesVariantDefinition,
        character_level: int,
        path: tuple[str, ...],
        automatic_grants: list[ContentRef],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        for row in definition.level_grants:
            if row.character_level <= character_level:
                self._append_resolved_grants(
                    row.grant_refs,
                    (*path, "level_grants", str(row.character_level)),
                    automatic_grants,
                    issues,
                )

    def _append_resolved_grants(
        self,
        refs: tuple[ContentRef, ...],
        path: tuple[str, ...],
        automatic_grants: list[ContentRef],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        for index, ref in enumerate(refs):
            if self._resolve_declaration(
                ref,
                (*path, str(index)),
                issues,
            ) is not None:
                automatic_grants.append(ref)

    def _validate_origin_innate_spell_refs(
        self,
        definition: SpeciesDefinition | SpeciesVariantDefinition,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        """Authenticate every fixed and selectable innate spell ref."""
        for source_index, source in enumerate(
            definition.innate_spellcasting,
        ):
            for grant_index, grant in enumerate(source.grants):
                refs = (
                    (grant.spell_ref,)
                    if grant.spell_ref is not None
                    else grant.allowed_spell_refs
                )
                for ref_index, ref in enumerate(refs):
                    self._resolve_declaration(
                        ref,
                        (
                            *path,
                            str(source_index),
                            "grants",
                            str(grant_index),
                            "spell_refs",
                            str(ref_index),
                        ),
                        issues,
                    )

    def _validate_class_definition_refs(
        self,
        class_ref: ContentRef,
        definition: ClassDefinition,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        for package_name, package in (
            (
                "first_class_proficiencies",
                definition.first_class_proficiencies,
            ),
            (
                "multiclass_proficiencies",
                definition.multiclass_proficiencies,
            ),
        ):
            self._validate_proficiency_subject_refs(
                package.automatic,
                (*path, package_name, "automatic"),
                issues,
            )
            self._validate_requirement_proficiency_refs(
                package.choices,
                (*path, package_name, "choices"),
                issues,
            )
        for level_index, level in enumerate(definition.level_definitions):
            self._validate_requirement_proficiency_refs(
                level.choice_requirements,
                (
                    *path,
                    "level_definitions",
                    str(level_index),
                    "choice_requirements",
                ),
                issues,
            )
        for index, entitlement in enumerate(definition.spell_entitlements):
            self._resolve_declaration(
                entitlement.spell_ref,
                (*path, "spell_entitlements", str(index), "spell_ref"),
                issues,
            )
        if definition.multiclass_prerequisite is not None:
            self._validate_prerequisite_refs(
                definition.multiclass_prerequisite,
                (*path, "multiclass_prerequisite"),
                issues,
            )
        if (
            definition.caster_progression != CasterProgression.NON_CASTER
            and definition.spellcasting_source_id is None
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.PREPARED_SPELL_SOURCE_UNKNOWN,
                (*path, "spellcasting_source_id"),
                (class_ref,),
            )

    def _validate_requirement_proficiency_refs(
        self,
        requirements: tuple[BuildChoiceRequirement, ...],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        for requirement_index, requirement in enumerate(requirements):
            self._validate_proficiency_subject_refs(
                requirement.allowed_proficiency_subjects,
                (*path, str(requirement_index), "allowed_proficiency_subjects"),
                issues,
            )

    def _validate_proficiency_subject_refs(
        self,
        subjects: tuple[ProficiencySubject, ...],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        for subject_index, subject in enumerate(subjects):
            if subject.content_ref is None:
                continue
            self._resolve_declaration(
                subject.content_ref,
                (*path, str(subject_index), "content_ref"),
                issues,
            )

    def _validate_prerequisite_refs(
        self,
        prerequisite: PrerequisiteExpression,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        if isinstance(prerequisite, (AllOfPrerequisite, AnyOfPrerequisite)):
            for index, child in enumerate(prerequisite.prerequisites):
                self._validate_prerequisite_refs(
                    child,
                    (*path, "prerequisites", str(index)),
                    issues,
                )
            return
        if isinstance(prerequisite, NotPrerequisite):
            self._validate_prerequisite_refs(
                prerequisite.prerequisite,
                (*path, "prerequisite"),
                issues,
            )
            return
        if isinstance(prerequisite, ClassLevelPrerequisite):
            self._resolve_typed_definition(
                prerequisite.class_ref,
                ClassDefinition,
                (*path, "class_ref"),
                issues,
            )
            return
        if isinstance(prerequisite, HasFeaturePrerequisite):
            self._resolve_declaration(
                prerequisite.feature_ref,
                (*path, "feature_ref"),
                issues,
            )
            return
        if isinstance(prerequisite, KnowsSpellPrerequisite):
            self._resolve_declaration(
                prerequisite.spell_ref,
                (*path, "spell_ref"),
                issues,
            )

    def _validate_multiclass_prerequisites(
        self,
        *,
        target_class_ref: ContentRef,
        target_class_definition: ClassDefinition,
        prior_class_order: list[str],
        class_refs: dict[str, ContentRef],
        class_definitions: dict[str, ClassDefinition],
        class_counts: dict[str, int],
        total_character_level: int,
        effective_abilities: dict[AbilityScoreName, int],
        owned_feature_keys: set[str],
        known_spell_keys: set[str],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        rows = [
            (
                class_refs[class_key],
                class_definitions[class_key],
            )
            for class_key in prior_class_order
            if class_key in class_definitions
        ]
        rows.append((target_class_ref, target_class_definition))
        for class_ref, definition in rows:
            prerequisite = definition.multiclass_prerequisite
            if prerequisite is None:
                continue
            if not _prerequisite_satisfied(
                prerequisite,
                class_counts=class_counts,
                total_character_level=total_character_level,
                effective_abilities=effective_abilities,
                owned_feature_keys=owned_feature_keys,
                known_spell_keys=known_spell_keys,
            ):
                self._issue(
                    issues,
                    CharacterBuildIssueCode.MULTICLASS_PREREQUISITE_UNMET,
                    path,
                    (class_ref,),
                )

    def _validate_subclass(
        self,
        level: ClassLevelEntry,
        path: tuple[str, ...],
        expected_requirements: list[BuildChoiceRequirement],
        first_subclass_level: dict[str, int],
        issues: list[CharacterBuildValidationIssue],
    ) -> SubclassDefinition | None:
        subclass_ref = level.subclass_ref
        if subclass_ref is None:
            return None
        subclass = self._resolve_typed_definition(
            subclass_ref,
            SubclassDefinition,
            (*path, "subclass_ref"),
            issues,
        )
        if subclass is None:
            return None
        if subclass.parent_class_ref != level.class_ref:
            self._issue(
                issues,
                CharacterBuildIssueCode.SUBCLASS_PARENT_MISMATCH,
                (*path, "subclass_ref"),
                (
                    subclass_ref,
                    subclass.parent_class_ref,
                    level.class_ref,
                ),
            )
        class_key = level.class_ref.identity_key
        if class_key not in first_subclass_level:
            first_subclass_level[class_key] = level.resulting_class_level
            has_authored_selection = any(
                requirement.choice_kind == ChoiceRequirementKind.SUBCLASS
                for requirement in expected_requirements
            )
            if not has_authored_selection:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.SUBCLASS_SELECTION_TIMING,
                    (*path, "subclass_ref"),
                    (subclass_ref,),
                )
        return subclass

    def _validate_subclass_choice_matches_level(
        self,
        level: ClassLevelEntry,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        choices = tuple(
            choice
            for choice in level.choices
            if isinstance(choice, SubclassChoice)
        )
        for choice in choices:
            if level.subclass_ref != choice.selected_ref:
                refs = (
                    (choice.selected_ref,)
                    if level.subclass_ref is None
                    else (choice.selected_ref, level.subclass_ref)
                )
                self._issue(
                    issues,
                    CharacterBuildIssueCode.SUBCLASS_SELECTION_MISMATCH,
                    (*path, "choices", choice.choice_id),
                    refs,
                )

    def _validate_choices(
        self,
        *,
        requirements: tuple[BuildChoiceRequirement, ...],
        selections: tuple[BuildChoiceSelection, ...],
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        requirements_by_id: dict[str, BuildChoiceRequirement] = {}
        for requirement in requirements:
            existing = requirements_by_id.get(requirement.choice_id)
            if existing is not None:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.DUPLICATE_CHOICE_REQUIREMENT,
                    (*path, requirement.choice_id),
                    tuple(
                        ref
                        for row in (existing, requirement)
                        for ref in row.allowed_refs
                    ),
                )
                continue
            requirements_by_id[requirement.choice_id] = requirement
            for index, allowed_ref in enumerate(requirement.allowed_refs):
                self._resolve_declaration(
                    allowed_ref,
                    (
                        *path,
                        requirement.choice_id,
                        "allowed_refs",
                        str(index),
                    ),
                    issues,
                )

        selections_by_id = {choice.choice_id: choice for choice in selections}
        for choice_id, requirement in requirements_by_id.items():
            selection = selections_by_id.get(choice_id)
            if selection is None:
                if requirement.minimum_selections > 0:
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.MISSING_REQUIRED_CHOICE,
                        (*path, choice_id),
                        requirement.allowed_refs,
                    )
                continue
            self._validate_choice(
                requirement,
                selection,
                (*path, choice_id),
                issues,
            )

        for choice in selections:
            if choice.choice_id not in requirements_by_id:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.UNEXPECTED_CHOICE,
                    (*path, choice.choice_id),
                    _choice_all_refs(choice),
                )
                for index, ref in enumerate(_choice_all_refs(choice)):
                    self._resolve_declaration(
                        ref,
                        (*path, choice.choice_id, "refs", str(index)),
                        issues,
                    )

    def _validate_unique_fighting_styles(
        self,
        selections: tuple[BuildChoiceSelection, ...],
        *,
        path: tuple[str, ...],
        selected: dict[str, ContentRef],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        """Reject selecting one exact Fighting Style from multiple sources."""
        for choice in selections:
            if not isinstance(choice, FightingStyleChoice):
                continue
            key = choice.selected_ref.identity_key
            if key in selected:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.DUPLICATE_FIGHTING_STYLE,
                    (*path, choice.choice_id),
                    (choice.selected_ref,),
                )
                continue
            selected[key] = choice.selected_ref

    def _validate_unique_metamagic(
        self,
        selections: tuple[BuildChoiceSelection, ...],
        *,
        path: tuple[str, ...],
        selected: dict[str, ContentRef],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        """Reject selecting one exact metamagic option at multiple levels."""
        for choice in selections:
            if not isinstance(choice, MetamagicChoice):
                continue
            for ref in choice.selected_refs:
                key = ref.identity_key
                if key in selected:
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.DUPLICATE_METAMAGIC,
                        (*path, choice.choice_id),
                        (ref,),
                    )
                    continue
                selected[key] = ref

    @staticmethod
    def _add_automatic_source_spells(
        class_definition: ClassDefinition,
        refs: tuple[ContentRef, ...],
        known_spells_by_source: dict[str, dict[str, ContentRef]],
    ) -> None:
        """Add class/subclass automatic spells to their exact class source."""
        source = class_definition.spellcasting_source_id
        if source is None:
            return
        known = known_spells_by_source.setdefault(source.value, {})
        for ref in refs:
            if ref.definition_kind == ContentDefinitionKind.SPELL:
                known.setdefault(ref.identity_key, ref)

    def _apply_source_spell_choices(
        self,
        *,
        class_definition: ClassDefinition,
        choices: tuple[BuildChoiceSelection, ...],
        path: tuple[str, ...],
        known_spells_by_source: dict[str, dict[str, ContentRef]],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        """Validate and apply one level's spell choices to one exact source."""
        spell_choices = tuple(
            choice
            for choice in choices
            if isinstance(
                choice,
                (CantripChoice, SpellKnownChoice, SpellReplacementChoice),
            )
        )
        if not spell_choices:
            return
        source = class_definition.spellcasting_source_id
        if source is None:
            for choice in spell_choices:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.SPELL_CHOICE_SOURCE_UNKNOWN,
                    (*path, choice.choice_id),
                    _choice_all_refs(choice),
                )
            return

        known = known_spells_by_source.setdefault(source.value, {})
        prior_keys = set(known)
        replaced_keys: set[str] = set()
        planned_new_keys: set[str] = set()
        valid_choices: set[str] = set()
        for choice in spell_choices:
            choice_path = (*path, choice.choice_id)
            valid = True
            if isinstance(choice, SpellReplacementChoice):
                replaced_key = choice.replaced_spell_ref.identity_key
                learned_key = choice.learned_spell_ref.identity_key
                if (
                    replaced_key not in prior_keys
                    or replaced_key in replaced_keys
                ):
                    self._issue(
                        issues,
                        (
                            CharacterBuildIssueCode
                            .SPELL_REPLACEMENT_SOURCE_MISMATCH
                        ),
                        choice_path,
                        (choice.replaced_spell_ref,),
                        detail=source.value,
                    )
                    valid = False
                if (
                    learned_key in prior_keys
                    or learned_key in planned_new_keys
                ):
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.SPELL_REPLACEMENT_DUPLICATE,
                        choice_path,
                        (choice.learned_spell_ref,),
                        detail=source.value,
                    )
                    valid = False
                replaced_keys.add(replaced_key)
                planned_new_keys.add(learned_key)
            else:
                for ref in choice.selected_refs:
                    key = ref.identity_key
                    if key in prior_keys or key in planned_new_keys:
                        self._issue(
                            issues,
                            CharacterBuildIssueCode.SPELL_LEARN_DUPLICATE,
                            choice_path,
                            (ref,),
                            detail=source.value,
                        )
                        valid = False
                    planned_new_keys.add(key)
            if valid:
                valid_choices.add(choice.choice_id)

        for choice in spell_choices:
            if choice.choice_id not in valid_choices:
                continue
            if isinstance(choice, SpellReplacementChoice):
                known.pop(choice.replaced_spell_ref.identity_key)
                known[choice.learned_spell_ref.identity_key] = (
                    choice.learned_spell_ref
                )
            else:
                for ref in choice.selected_refs:
                    known[ref.identity_key] = ref

    def _validate_choice(
        self,
        requirement: BuildChoiceRequirement,
        selection: BuildChoiceSelection,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        selection_kind = _choice_kind(selection)
        kind_matches = selection_kind == requirement.choice_kind
        if (
            requirement.choice_kind
            == ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT
        ):
            kind_matches = isinstance(
                selection,
                (AbilityScoreImprovementChoice, FeatChoice),
            )
        if not kind_matches:
            self._issue(
                issues,
                CharacterBuildIssueCode.CHOICE_KIND_MISMATCH,
                path,
                _choice_all_refs(selection),
                detail=selection_kind.value,
            )
        selection_count = _choice_selection_count(selection)
        if not (
            requirement.minimum_selections
            <= selection_count
            <= requirement.maximum_selections
        ):
            self._issue(
                issues,
                CharacterBuildIssueCode.CHOICE_SELECTION_COUNT,
                path,
                _choice_all_refs(selection),
                detail=str(selection_count),
            )

        selected_refs = _choice_allowed_refs(selection)
        all_refs = _choice_all_refs(selection)
        for index, ref in enumerate(all_refs):
            self._resolve_declaration(
                ref,
                (*path, "refs", str(index)),
                issues,
            )
        allowed = set(requirement.allowed_refs)
        for selected_ref in selected_refs:
            if allowed and selected_ref not in allowed:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.CHOICE_REF_NOT_ALLOWED,
                    path,
                    (selected_ref, *requirement.allowed_refs),
                )
        self._validate_proficiency_choice(
            requirement,
            selection,
            path,
            issues,
        )

    def _validate_proficiency_choice(
        self,
        requirement: BuildChoiceRequirement,
        selection: BuildChoiceSelection,
        path: tuple[str, ...],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        selected_subjects = (
            selection.proficiencies
            if isinstance(selection, StartingProficiencyChoice)
            else ()
        )
        self._validate_proficiency_subject_refs(
            selected_subjects,
            (*path, "proficiencies"),
            issues,
        )
        allowed = requirement.allowed_proficiency_subjects
        if not allowed:
            return
        if isinstance(selection, ClassSkillChoice):
            for skill in selection.skills:
                subject_id = f"skill.{skill}"
                if not any(
                    row.subject_kind == ProficiencySubjectKind.SKILL
                    and row.subject_id == subject_id
                    for row in allowed
                ):
                    self._issue(
                        issues,
                        (
                            CharacterBuildIssueCode
                            .CHOICE_PROFICIENCY_SUBJECT_NOT_ALLOWED
                        ),
                        path,
                        detail=subject_id,
                    )
            return
        if isinstance(selection, StartingProficiencyChoice):
            for subject in selection.proficiencies:
                if subject not in allowed:
                    self._issue(
                        issues,
                        (
                            CharacterBuildIssueCode
                            .CHOICE_PROFICIENCY_SUBJECT_NOT_ALLOWED
                        ),
                        path,
                        detail=(
                            f"{subject.subject_kind.value}:"
                            f"{subject.identity_key}"
                        ),
                    )

    def _validate_loadout_refs(
        self,
        loadout: CharacterLoadoutRevisionV1,
        class_order: list[str],
        class_refs: dict[str, ContentRef],
        class_counts: dict[str, int],
        class_definitions: dict[str, ClassDefinition],
        issues: list[CharacterBuildValidationIssue],
    ) -> None:
        sources: dict[
            str,
            tuple[ContentRef, ClassDefinition, int],
        ] = {}
        duplicate_sources: set[str] = set()
        for class_key in class_order:
            definition = class_definitions.get(class_key)
            if definition is None or definition.spellcasting_source_id is None:
                continue
            source_key = definition.spellcasting_source_id.value
            existing = sources.get(source_key)
            if existing is not None:
                duplicate_sources.add(source_key)
                self._issue(
                    issues,
                    CharacterBuildIssueCode.SPELLCASTING_SOURCE_DUPLICATE,
                    ("class_levels",),
                    (existing[0], class_refs[class_key]),
                    detail=source_key,
                )
                continue
            sources[source_key] = (
                class_refs[class_key],
                definition,
                class_counts[class_key],
            )

        for row_index, row in enumerate(loadout.prepared_spells):
            path = ("loadout", "prepared_spells", str(row_index))
            source_key = row.spellcasting_source_id.value
            source = sources.get(source_key)
            if source is None or source_key in duplicate_sources:
                self._issue(
                    issues,
                    CharacterBuildIssueCode.PREPARED_SPELL_SOURCE_UNKNOWN,
                    path,
                    row.spell_refs,
                    detail=source_key,
                )
                source_definition = None
                accessible_rank = -1
            else:
                _, source_definition, class_level = source
                feature_level = (
                    source_definition.spellcasting_feature_class_level
                )
                if feature_level is None or class_level < feature_level:
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.PREPARED_SPELL_SOURCE_INACTIVE,
                        path,
                        row.spell_refs,
                        detail=source_key,
                    )
                    accessible_rank = -1
                else:
                    contribution = SpellcastingClassContribution(
                        class_level=class_level,
                        progression=source_definition.caster_progression,
                        spellcasting_feature_class_level=feature_level,
                    )
                    individual_level = effective_spellcaster_level(
                        (contribution,),
                        policy=self._multiclass_slot_rounding_policy,
                    )
                    slots = (
                        full_caster_spell_slots_for_level(individual_level)
                        if individual_level > 0
                        else {}
                    )
                    accessible_rank = max(slots, default=0)
            entitlements = (
                {
                    entitlement.spell_ref.identity_key: entitlement
                    for entitlement in source_definition.spell_entitlements
                }
                if source_definition is not None
                else {}
            )
            for spell_index, spell_ref in enumerate(row.spell_refs):
                self._resolve_declaration(
                    spell_ref,
                    (
                        "loadout",
                        "prepared_spells",
                        str(row_index),
                        "spell_refs",
                        str(spell_index),
                    ),
                    issues,
                )
                entitlement = entitlements.get(spell_ref.identity_key)
                if (
                    entitlement is None
                    or entitlement.spell_ref != spell_ref
                ):
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.PREPARED_SPELL_NOT_ENTITLED,
                        (*path, "spell_refs", str(spell_index)),
                        (spell_ref,),
                        detail=source_key,
                    )
                elif entitlement.spell_rank > accessible_rank:
                    self._issue(
                        issues,
                        CharacterBuildIssueCode.PREPARED_SPELL_RANK_UNAVAILABLE,
                        (*path, "spell_refs", str(spell_index)),
                        (spell_ref,),
                        detail=str(entitlement.spell_rank),
                    )
        for index, toggle in enumerate(loadout.feature_toggles):
            self._resolve_declaration(
                toggle.feature_ref,
                ("loadout", "feature_toggles", str(index)),
                issues,
            )

    @staticmethod
    def _issue(
        issues: list[CharacterBuildValidationIssue],
        code: CharacterBuildIssueCode,
        path: tuple[str, ...],
        content_refs: tuple[ContentRef, ...] = (),
        *,
        detail: str = "",
    ) -> None:
        issues.append(
            CharacterBuildValidationIssue(
                code=code,
                path=path,
                content_refs=content_refs,
                detail=detail,
            ),
        )


def _level_definition(
    definition: ClassDefinition | SubclassDefinition,
    class_level: int,
):
    return next(
        (
            row
            for row in definition.level_definitions
            if row.class_level == class_level
        ),
        None,
    )


def _effective_creation_ability_scores(
    definition: CharacterDefinitionRevisionV2,
) -> dict[AbilityScoreName, int]:
    scores = {
        AbilityScoreName.STRENGTH: definition.base_ability_scores.strength,
        AbilityScoreName.DEXTERITY: definition.base_ability_scores.dexterity,
        AbilityScoreName.CONSTITUTION: definition.base_ability_scores.constitution,
        AbilityScoreName.INTELLIGENCE: (
            definition.base_ability_scores.intelligence
        ),
        AbilityScoreName.WISDOM: definition.base_ability_scores.wisdom,
        AbilityScoreName.CHARISMA: definition.base_ability_scores.charisma,
    }
    scores[definition.flexible_ability_bonuses.plus_two] += 2
    scores[definition.flexible_ability_bonuses.plus_one] += 1
    return scores


def _add_origin_feature_keys_before_level(
    definitions: tuple[
        SpeciesDefinition | SpeciesVariantDefinition | None,
        ...,
    ],
    character_level: int,
    owned_feature_keys: set[str],
    known_spell_keys: set[str],
    source_independent_known_spell_keys: set[str],
) -> None:
    for definition in definitions:
        if definition is None:
            continue
        for row in definition.level_grants:
            if row.character_level < character_level:
                owned_feature_keys.update(
                    ref.identity_key for ref in row.grant_refs
                )
                spell_keys = {
                    ref.identity_key
                    for ref in row.grant_refs
                    if ref.definition_kind == ContentDefinitionKind.SPELL
                }
                known_spell_keys.update(spell_keys)
                source_independent_known_spell_keys.update(spell_keys)


def _add_origin_feature_keys_at_level(
    definitions: tuple[
        SpeciesDefinition | SpeciesVariantDefinition | None,
        ...,
    ],
    character_level: int,
    owned_feature_keys: set[str],
    known_spell_keys: set[str],
    source_independent_known_spell_keys: set[str],
) -> None:
    for definition in definitions:
        if definition is None:
            continue
        for row in definition.level_grants:
            if row.character_level == character_level:
                owned_feature_keys.update(
                    ref.identity_key for ref in row.grant_refs
                )
                spell_keys = {
                    ref.identity_key
                    for ref in row.grant_refs
                    if ref.definition_kind == ContentDefinitionKind.SPELL
                }
                known_spell_keys.update(spell_keys)
                source_independent_known_spell_keys.update(spell_keys)


def _prerequisite_satisfied(
    prerequisite: PrerequisiteExpression,
    *,
    class_counts: dict[str, int],
    total_character_level: int,
    effective_abilities: dict[AbilityScoreName, int],
    owned_feature_keys: set[str],
    known_spell_keys: set[str],
) -> bool:
    if isinstance(prerequisite, AllOfPrerequisite):
        return all(
            _prerequisite_satisfied(
                child,
                class_counts=class_counts,
                total_character_level=total_character_level,
                effective_abilities=effective_abilities,
                owned_feature_keys=owned_feature_keys,
                known_spell_keys=known_spell_keys,
            )
            for child in prerequisite.prerequisites
        )
    if isinstance(prerequisite, AnyOfPrerequisite):
        return any(
            _prerequisite_satisfied(
                child,
                class_counts=class_counts,
                total_character_level=total_character_level,
                effective_abilities=effective_abilities,
                owned_feature_keys=owned_feature_keys,
                known_spell_keys=known_spell_keys,
            )
            for child in prerequisite.prerequisites
        )
    if isinstance(prerequisite, NotPrerequisite):
        return not _prerequisite_satisfied(
            prerequisite.prerequisite,
            class_counts=class_counts,
            total_character_level=total_character_level,
            effective_abilities=effective_abilities,
            owned_feature_keys=owned_feature_keys,
            known_spell_keys=known_spell_keys,
        )
    if isinstance(prerequisite, ClassLevelPrerequisite):
        return (
            class_counts.get(prerequisite.class_ref.identity_key, 0)
            >= prerequisite.minimum
        )
    if isinstance(prerequisite, TotalCharacterLevelPrerequisite):
        return total_character_level >= prerequisite.minimum
    if isinstance(prerequisite, AbilityScorePrerequisite):
        return (
            effective_abilities.get(prerequisite.ability, 0)
            >= prerequisite.minimum
        )
    if isinstance(prerequisite, HasFeaturePrerequisite):
        return prerequisite.feature_ref.identity_key in owned_feature_keys
    if isinstance(prerequisite, KnowsSpellPrerequisite):
        return prerequisite.spell_ref.identity_key in known_spell_keys
    return False


def _choice_kind(selection: BuildChoiceSelection) -> ChoiceRequirementKind:
    return ChoiceRequirementKind(selection.choice_type)


def _choice_selection_count(selection: BuildChoiceSelection) -> int:
    if isinstance(selection, ClassSkillChoice):
        return len(selection.skills)
    if isinstance(selection, StartingProficiencyChoice):
        return len(selection.proficiencies)
    if isinstance(
        selection,
        (CantripChoice, SpellKnownChoice, MetamagicChoice),
    ):
        return len(selection.selected_refs)
    return 1


def _choice_allowed_refs(
    selection: BuildChoiceSelection,
) -> tuple[ContentRef, ...]:
    if isinstance(
        selection,
        (
            FightingStyleChoice,
            SubclassChoice,
            ElementalAncestryChoice,
            OriginTraitChoice,
            FeatChoice,
            StartingApparelPackageChoice,
            StartingEquipmentPackageChoice,
        ),
    ):
        return (selection.selected_ref,)
    if isinstance(
        selection,
        (CantripChoice, SpellKnownChoice, MetamagicChoice),
    ):
        return selection.selected_refs
    if isinstance(selection, SpellReplacementChoice):
        return (selection.learned_spell_ref,)
    return ()


def _choice_all_refs(
    selection: BuildChoiceSelection,
) -> tuple[ContentRef, ...]:
    if isinstance(selection, SpellReplacementChoice):
        return (
            selection.replaced_spell_ref,
            selection.learned_spell_ref,
        )
    if isinstance(
        selection,
        (
            AbilityScoreImprovementChoice,
            ClassSkillChoice,
            StartingApparelPackageChoice,
        ),
    ):
        return ()
    if isinstance(selection, StartingProficiencyChoice):
        return ()
    return _choice_allowed_refs(selection)


def _grant_schedule_entry(
    *,
    kind: CharacterGrantScheduleKind,
    provenance: CharacterGrantProvenance,
    content_ref: ContentRef | None = None,
    proficiency: ProficiencySubject | None = None,
    ability: AbilityScoreName | None = None,
    amount: int | None = None,
    replaced_content_ref: ContentRef | None = None,
) -> CharacterGrantScheduleEntry:
    payload = {
        "schedule_version": 2,
        "kind": kind.value,
        "source_kind": provenance.source_kind.value,
        "source_ref": provenance.source_ref.identity_key,
        "character_level": provenance.character_level,
        "class_level_id": provenance.class_level_id,
        "class_level": provenance.class_level,
        "choice_id": provenance.choice_id,
        "ordinal_path": list(provenance.ordinal_path),
        "content_ref": (
            content_ref.identity_key if content_ref is not None else None
        ),
        "proficiency": (
            {
                "kind": proficiency.subject_kind.value,
                "identity": proficiency.identity_key,
            }
            if proficiency is not None
            else None
        ),
        "ability": ability.value if ability is not None else None,
        "amount": amount,
        "replaced_content_ref": (
            replaced_content_ref.identity_key
            if replaced_content_ref is not None
            else None
        ),
    }
    digest = canonical_content_sha256(payload)
    return CharacterGrantScheduleEntry(
        kind=kind,
        provenance=provenance,
        grant_token=f"character-structural-grant:v2:{digest}",
        content_ref=content_ref,
        proficiency=proficiency,
        ability=ability,
        amount=amount,
        replaced_content_ref=replaced_content_ref,
    )


def _append_choice_schedule(
    schedule: list[CharacterGrantScheduleEntry],
    *,
    choice: BuildChoiceSelection,
    source_kind: CharacterGrantSourceKind,
    source_ref: ContentRef,
    character_level: int | None,
    class_level_id: str | None,
    class_level: int | None,
    ordinal_prefix: tuple[int, ...],
) -> None:
    def provenance(nested_index: int) -> CharacterGrantProvenance:
        return CharacterGrantProvenance(
            source_kind=source_kind,
            source_ref=source_ref,
            character_level=character_level,
            class_level_id=class_level_id,
            class_level=class_level,
            choice_id=choice.choice_id,
            ordinal_path=(*ordinal_prefix, nested_index),
        )

    if isinstance(choice, ClassSkillChoice):
        for index, skill in enumerate(choice.skills):
            schedule.append(
                _grant_schedule_entry(
                    kind=CharacterGrantScheduleKind.PROFICIENCY,
                    provenance=provenance(index),
                    proficiency=ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.SKILL,
                        subject_id=f"skill.{skill}",
                    ),
                ),
            )
        return
    if isinstance(choice, StartingProficiencyChoice):
        for index, subject in enumerate(choice.proficiencies):
            schedule.append(
                _grant_schedule_entry(
                    kind=CharacterGrantScheduleKind.PROFICIENCY,
                    provenance=provenance(index),
                    proficiency=subject,
                ),
            )
        return
    if isinstance(choice, AbilityScoreImprovementChoice):
        for index, (ability, amount) in enumerate(choice.increases):
            schedule.append(
                _grant_schedule_entry(
                    kind=(
                        CharacterGrantScheduleKind.ABILITY_SCORE_INCREASE
                    ),
                    provenance=provenance(index),
                    ability=ability,
                    amount=amount,
                ),
            )
        return
    if isinstance(choice, (CantripChoice, SpellKnownChoice)):
        for index, spell_ref in enumerate(choice.selected_refs):
            schedule.append(
                _grant_schedule_entry(
                    kind=CharacterGrantScheduleKind.SPELL_LEARN,
                    provenance=provenance(index),
                    content_ref=spell_ref,
                ),
            )
        return
    if isinstance(choice, SpellReplacementChoice):
        schedule.append(
            _grant_schedule_entry(
                kind=CharacterGrantScheduleKind.SPELL_REPLACEMENT,
                provenance=provenance(0),
                content_ref=choice.learned_spell_ref,
                replaced_content_ref=choice.replaced_spell_ref,
            ),
        )
        return
    for index, selected_ref in enumerate(_choice_allowed_refs(choice)):
        schedule.append(
            _grant_schedule_entry(
                kind=CharacterGrantScheduleKind.SELECTED_CONTENT,
                provenance=provenance(index),
                content_ref=selected_ref,
            ),
        )


def _spell_source_by_provenance_ref(
    definition: CharacterDefinitionRevisionV2,
    class_definitions: dict[str, ClassDefinition],
) -> dict[str, tuple[ContentRef, SpellcastingSourceId]]:
    """Map class and subclass grant owners to their exact casting source."""
    sources: dict[str, tuple[ContentRef, SpellcastingSourceId]] = {}
    for level in definition.class_levels:
        class_definition = class_definitions.get(level.class_ref.identity_key)
        if (
            class_definition is None
            or class_definition.spellcasting_source_id is None
        ):
            continue
        row = (
            level.class_ref,
            class_definition.spellcasting_source_id,
        )
        sources[level.class_ref.identity_key] = row
        if level.subclass_ref is not None:
            sources[level.subclass_ref.identity_key] = row
    return sources


def _final_known_spell_grants(
    schedule: tuple[CharacterGrantScheduleEntry, ...],
    source_by_provenance_ref: dict[
        str,
        tuple[ContentRef, SpellcastingSourceId],
    ],
) -> tuple[KnownSpellGrantPreview, ...]:
    """Reduce spell choices once per source without materializing intermediates."""
    known_by_source: dict[str, dict[str, KnownSpellGrantPreview]] = {}
    for row in schedule:
        source = source_by_provenance_ref.get(
            row.provenance.source_ref.identity_key,
        )
        if source is None:
            continue
        provider_ref, source_id = source
        known = known_by_source.setdefault(source_id.value, {})
        if row.kind == CharacterGrantScheduleKind.SPELL_REPLACEMENT:
            replaced = row.replaced_content_ref
            learned = row.content_ref
            if replaced is None or learned is None:
                raise RuntimeError(
                    "validated spell replacement has incomplete payload",
                )
            if known.pop(replaced.identity_key, None) is None:
                raise RuntimeError(
                    "validated spell replacement does not own its replaced "
                    "spell",
                )
            if learned.identity_key in known:
                raise RuntimeError(
                    "validated spell replacement creates a source duplicate",
                )
            known[learned.identity_key] = KnownSpellGrantPreview(
                spell_ref=learned,
                provider_ref=provider_ref,
                spellcasting_source_id=source_id,
                grant_token=row.grant_token,
            )
            continue
        if row.kind not in {
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantScheduleKind.SELECTED_CONTENT,
            CharacterGrantScheduleKind.SPELL_LEARN,
        }:
            continue
        content_ref = row.content_ref
        if (
            content_ref is not None
            and content_ref.definition_kind == ContentDefinitionKind.SPELL
        ):
            known.setdefault(
                content_ref.identity_key,
                KnownSpellGrantPreview(
                    spell_ref=content_ref,
                    provider_ref=provider_ref,
                    spellcasting_source_id=source_id,
                    grant_token=row.grant_token,
                ),
            )
    return tuple(
        spell
        for source_spells in known_by_source.values()
        for spell in source_spells.values()
    )


def _origin_innate_spell_grants(
    *,
    definition: CharacterDefinitionRevisionV2,
    species: SpeciesDefinition | None,
    variant: SpeciesVariantDefinition | None,
    schedule: tuple[CharacterGrantScheduleEntry, ...],
) -> tuple[OriginInnateSpellGrantPreview, ...]:
    """Resolve fixed and selected origin spells without class-source inference."""
    previews: list[OriginInnateSpellGrantPreview] = []
    schedule_by_source = {
        source_ref.identity_key: tuple(
            row
            for row in schedule
            if row.provenance.source_ref == source_ref
        )
        for source_ref in (
            definition.species_ref,
            definition.species_variant_ref,
        )
        if source_ref is not None
    }
    for provider_ref, origin in (
        (definition.species_ref, species),
        (definition.species_variant_ref, variant),
    ):
        if provider_ref is None or origin is None:
            continue
        provider_rows = schedule_by_source.get(
            provider_ref.identity_key,
            (),
        )
        for source in origin.innate_spellcasting:
            for grant in source.grants:
                if (
                    grant.unlock_character_level
                    > definition.earned_character_level
                ):
                    continue
                matching = tuple(
                    row
                    for row in provider_rows
                    if (
                        row.content_ref is not None
                        and row.content_ref.definition_kind
                        is ContentDefinitionKind.SPELL
                        and (
                            (
                                grant.spell_ref is not None
                                and row.content_ref == grant.spell_ref
                                and row.provenance.character_level
                                == grant.unlock_character_level
                            )
                            or (
                                grant.choice_id is not None
                                and row.provenance.choice_id
                                == grant.choice_id
                                and row.content_ref
                                in grant.allowed_spell_refs
                            )
                        )
                    )
                )
                if len(matching) != 1:
                    raise RuntimeError(
                        "validated innate spell grant has no unique schedule "
                        f"row: {provider_ref.identity_key} {grant.grant_id}",
                    )
                row = matching[0]
                assert row.content_ref is not None
                previews.append(
                    OriginInnateSpellGrantPreview(
                        grant_id=grant.grant_id,
                        spell_ref=row.content_ref,
                        provider_ref=provider_ref,
                        spellcasting_source_id=source.source_id,
                        spellcasting_ability=source.ability,
                        provider_level=definition.earned_character_level,
                        fixed_cast_rank=grant.fixed_cast_rank,
                        uses_per_long_rest=grant.uses_per_long_rest,
                        grant_token=row.grant_token,
                    ),
                )
    return tuple(previews)


def _final_known_spell_refs(
    schedule: tuple[CharacterGrantScheduleEntry, ...],
    source_by_provenance_ref: dict[
        str,
        tuple[ContentRef, SpellcastingSourceId],
    ],
    final_known_spells: tuple[KnownSpellGrantPreview, ...],
) -> tuple[ContentRef, ...]:
    """Project the exact per-source state into a distinct global spell list."""
    final_by_key = {
        row.spell_ref.identity_key: row.spell_ref
        for row in final_known_spells
    }
    sourceless: dict[str, ContentRef] = {}
    for row in schedule:
        if (
            row.provenance.source_ref.identity_key
            in source_by_provenance_ref
        ):
            continue
        if row.kind == CharacterGrantScheduleKind.SPELL_REPLACEMENT:
            if row.replaced_content_ref is not None:
                sourceless.pop(
                    row.replaced_content_ref.identity_key,
                    None,
                )
            if row.content_ref is not None:
                sourceless[row.content_ref.identity_key] = row.content_ref
            continue
        if row.kind not in {
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantScheduleKind.SELECTED_CONTENT,
            CharacterGrantScheduleKind.SPELL_LEARN,
        }:
            continue
        ref = row.content_ref
        if (
            ref is not None
            and ref.definition_kind == ContentDefinitionKind.SPELL
        ):
            sourceless.setdefault(ref.identity_key, ref)

    final_by_key.update(sourceless)
    ordered: dict[str, ContentRef] = {}
    for row in schedule:
        for ref in (row.replaced_content_ref, row.content_ref):
            if ref is None or ref.identity_key not in final_by_key:
                continue
            ordered.setdefault(ref.identity_key, final_by_key[ref.identity_key])
    for key, ref in final_by_key.items():
        ordered.setdefault(key, ref)
    return tuple(ordered.values())


__all__ = [
    "CasterContributionPreview",
    "CharacterBuildIssueCode",
    "CharacterBuildPreview",
    "CharacterBuildValidationIssue",
    "CharacterBuildValidationResult",
    "CharacterBuildValidator",
    "CharacterGrantProvenance",
    "CharacterGrantScheduleEntry",
    "CharacterGrantScheduleKind",
    "CharacterGrantSourceKind",
    "KnownSpellGrantPreview",
    "OriginInnateSpellGrantPreview",
]
