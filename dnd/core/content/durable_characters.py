"""Dependency-neutral durable character and possession revision contracts."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Self, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
    validate_sha256,
)
from dnd.core.content.origin_support import OriginRuntimeSupport
from dnd.core.content.recipes import ContentRecipe
from dnd.types.equipment import EquipmentSlot
from dnd.types.progression import CasterProgression
from dnd.types import abilities as ability_types
from dnd.types.rolls import HitDieSize
from dnd.core.progression import point_buy_cost


def _canonical_sha256(payload: object) -> str:
    """Return the SHA-256 of one exact canonical JSON payload."""
    return canonical_content_sha256(payload)


def compute_item_augmentation_digest(
    *,
    content_ref: ContentRef,
    parameters: dict[str, JsonValue],
    durable_state: dict[str, JsonValue],
) -> str:
    """Authenticate one permanent item augmentation record."""
    return _canonical_sha256(
        {
            "content_ref": content_ref.model_dump(mode="json"),
            "parameters": parameters,
            "durable_state": durable_state,
        },
    )


class ItemAugmentationRecord(BaseModel):
    """Permanent item behavior rebuilt through its authored content identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_ref: ContentRef
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    durable_state: dict[str, JsonValue] = Field(default_factory=dict)
    augmentation_digest: str

    @classmethod
    def create(
        cls,
        *,
        content_ref: ContentRef,
        parameters: dict[str, JsonValue] | None = None,
        durable_state: dict[str, JsonValue] | None = None,
    ) -> Self:
        """Create one augmentation with its exact canonical digest."""
        validated_parameters = parameters or {}
        validated_state = durable_state or {}
        return cls(
            content_ref=content_ref,
            parameters=validated_parameters,
            durable_state=validated_state,
            augmentation_digest=compute_item_augmentation_digest(
                content_ref=content_ref,
                parameters=validated_parameters,
                durable_state=validated_state,
            ),
        )

    @field_validator("augmentation_digest")
    @classmethod
    def _validate_augmentation_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "augmentation_digest")

    @model_validator(mode="after")
    def _validate_augmentation_digest(self) -> Self:
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject augmentation parameters or state changed after hashing."""
        expected = compute_item_augmentation_digest(
            content_ref=self.content_ref,
            parameters=self.parameters,
            durable_state=self.durable_state,
        )
        if self.augmentation_digest != expected:
            raise ValueError(
                "augmentation_digest does not authenticate the content "
                "reference, parameters, and durable state",
            )


def compute_character_item_digest(
    *,
    schema_version: Literal[1],
    character_item_id: UUID,
    recipe: ContentRecipe,
    quantity: int,
    remaining_charges: int | None,
    durability_damage: int | None,
    durable_augmentations: tuple[ItemAugmentationRecord, ...],
    equipped_slot: EquipmentSlot | None,
) -> str:
    """Authenticate one exact durable possession record."""
    return _canonical_sha256(
        {
            "schema_version": schema_version,
            "character_item_id": str(character_item_id),
            "recipe": recipe.model_dump(mode="json"),
            "quantity": quantity,
            "remaining_charges": remaining_charges,
            "durability_damage": durability_damage,
            "durable_augmentations": [
                augmentation.model_dump(mode="json")
                for augmentation in durable_augmentations
            ],
            "equipped_slot": (
                equipped_slot.value if equipped_slot is not None else None
            ),
        },
    )


class CharacterItemV1(BaseModel):
    """One durable possession, independent from every runtime item instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    character_item_id: UUID
    recipe: ContentRecipe
    quantity: int = Field(default=1, ge=1)
    remaining_charges: int | None = Field(default=None, ge=0)
    durability_damage: int | None = Field(default=None, ge=0)
    durable_augmentations: tuple[ItemAugmentationRecord, ...] = ()
    equipped_slot: EquipmentSlot | None = None
    character_item_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_item_id: UUID,
        recipe: ContentRecipe,
        quantity: int = 1,
        remaining_charges: int | None = None,
        durability_damage: int | None = None,
        durable_augmentations: tuple[ItemAugmentationRecord, ...] = (),
        equipped_slot: EquipmentSlot | None = None,
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one possession with its exact canonical digest."""
        return cls(
            schema_version=schema_version,
            character_item_id=character_item_id,
            recipe=recipe,
            quantity=quantity,
            remaining_charges=remaining_charges,
            durability_damage=durability_damage,
            durable_augmentations=durable_augmentations,
            equipped_slot=equipped_slot,
            character_item_digest=compute_character_item_digest(
                schema_version=schema_version,
                character_item_id=character_item_id,
                recipe=recipe,
                quantity=quantity,
                remaining_charges=remaining_charges,
                durability_damage=durability_damage,
                durable_augmentations=durable_augmentations,
                equipped_slot=equipped_slot,
            ),
        )

    @field_validator("character_item_digest")
    @classmethod
    def _validate_character_item_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "character_item_digest")

    @model_validator(mode="after")
    def _validate_character_item(self) -> Self:
        if self.recipe.ref.definition_kind != ContentDefinitionKind.ITEM:
            raise ValueError(
                "CharacterItemV1 recipe must reference an item definition",
            )
        augmentation_digests = tuple(
            augmentation.augmentation_digest
            for augmentation in self.durable_augmentations
        )
        if len(set(augmentation_digests)) != len(augmentation_digests):
            raise ValueError(
                "durable_augmentations contain duplicate augmentation_digest "
                "values",
            )
        if augmentation_digests != tuple(sorted(augmentation_digests)):
            raise ValueError(
                "durable_augmentations must be ordered by augmentation_digest",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of this durable possession record."""
        self.recipe.verify_integrity()
        for augmentation in self.durable_augmentations:
            augmentation.verify_integrity()
        expected = compute_character_item_digest(
            schema_version=self.schema_version,
            character_item_id=self.character_item_id,
            recipe=self.recipe,
            quantity=self.quantity,
            remaining_charges=self.remaining_charges,
            durability_damage=self.durability_damage,
            durable_augmentations=self.durable_augmentations,
            equipped_slot=self.equipped_slot,
        )
        if self.character_item_digest != expected:
            raise ValueError(
                "character_item_digest does not authenticate the durable item",
            )


def compute_character_holdings_digest(
    *,
    character_id: UUID,
    schema_version: Literal[1],
    holdings_revision: int,
    items: tuple[CharacterItemV1, ...],
) -> str:
    """Authenticate one immutable, deterministically ordered holdings revision."""
    return _canonical_sha256(
        {
            "character_id": str(character_id),
            "schema_version": schema_version,
            "holdings_revision": holdings_revision,
            "items": [item.model_dump(mode="json") for item in items],
        },
    )


class CharacterHoldingsRevision(BaseModel):
    """Immutable possessions independently revisioned for one character."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    character_id: UUID
    schema_version: Literal[1] = 1
    holdings_revision: int = Field(ge=1)
    items: tuple[CharacterItemV1, ...] = ()
    holdings_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_id: UUID,
        holdings_revision: int,
        items: tuple[CharacterItemV1, ...] = (),
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one holdings revision with its canonical digest."""
        return cls(
            character_id=character_id,
            schema_version=schema_version,
            holdings_revision=holdings_revision,
            items=items,
            holdings_digest=compute_character_holdings_digest(
                character_id=character_id,
                schema_version=schema_version,
                holdings_revision=holdings_revision,
                items=items,
            ),
        )

    @field_validator("holdings_digest")
    @classmethod
    def _validate_holdings_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "holdings_digest")

    @model_validator(mode="after")
    def _validate_holdings(self) -> Self:
        item_ids = tuple(item.character_item_id for item in self.items)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError(
                "items contain duplicate character_item_id values",
            )
        if item_ids != tuple(sorted(item_ids, key=lambda item_id: item_id.hex)):
            raise ValueError(
                "items must be ordered by character_item_id",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of the base identity or durable possessions."""
        for item in self.items:
            item.verify_integrity()
        expected = compute_character_holdings_digest(
            character_id=self.character_id,
            schema_version=self.schema_version,
            holdings_revision=self.holdings_revision,
            items=self.items,
        )
        if self.holdings_digest != expected:
            raise ValueError(
                "holdings_digest does not authenticate the character "
                "holdings revision",
            )


class _StableProgressionId(BaseModel):
    """One typed, durable identity within a character build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        return validate_namespaced_id(value, cls.__name__)


class ClassLevelId(_StableProgressionId):
    """Identity of one entry in the ordered class-level ledger."""


class SpellcastingSourceId(_StableProgressionId):
    """Identity of one class-owned or origin-owned spellcasting source."""


_SKILL_NAMES = frozenset(skill.value for skill in ability_types.SkillName)


class AbilityScoreAllocation(BaseModel):
    """Exact 27-point-buy scores before flexible ancestry bonuses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strength: int = Field(ge=8, le=15)
    dexterity: int = Field(ge=8, le=15)
    constitution: int = Field(ge=8, le=15)
    intelligence: int = Field(ge=8, le=15)
    wisdom: int = Field(ge=8, le=15)
    charisma: int = Field(ge=8, le=15)

    def score(self, ability: ability_types.AbilityName) -> int:
        """Return one explicitly selected ability score."""
        match ability:
            case ability_types.AbilityName.STRENGTH:
                return self.strength
            case ability_types.AbilityName.DEXTERITY:
                return self.dexterity
            case ability_types.AbilityName.CONSTITUTION:
                return self.constitution
            case ability_types.AbilityName.INTELLIGENCE:
                return self.intelligence
            case ability_types.AbilityName.WISDOM:
                return self.wisdom
            case ability_types.AbilityName.CHARISMA:
                return self.charisma

    @property
    def points_spent(self) -> int:
        """Return the canonical point-buy cost of this allocation."""
        return sum(
            point_buy_cost(score)
            for score in (
                self.strength,
                self.dexterity,
                self.constitution,
                self.intelligence,
                self.wisdom,
                self.charisma,
            )
        )

    @model_validator(mode="after")
    def _validate_budget(self) -> Self:
        if self.points_spent != 27:
            raise ValueError("ability score allocation must spend exactly 27 points")
        return self


class FlexibleAbilityBonusSelection(BaseModel):
    """BG3-style flexible +2/+1 bonuses assigned to distinct abilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plus_two: ability_types.AbilityName
    plus_one: ability_types.AbilityName

    @model_validator(mode="after")
    def _validate_distinct(self) -> Self:
        if self.plus_two == self.plus_one:
            raise ValueError("+2 and +1 must apply to different abilities")
        return self


class CharacterAppearanceOptionSelection(BaseModel):
    """One authored appearance option/value pair.

    These stable tokens are validated against the selected body definition by
    the creator service.  They are not renderer filenames or display labels.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    value_id: str

    @field_validator("option_id", "value_id")
    @classmethod
    def _validate_identity(cls, value: str, info) -> str:
        return validate_namespaced_id(value, info.field_name)


class CharacterAppearanceSelection(BaseModel):
    """Deterministically ordered authored body-appearance selections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    options: tuple[CharacterAppearanceOptionSelection, ...] = ()

    @model_validator(mode="after")
    def _validate_options(self) -> Self:
        option_ids = tuple(row.option_id for row in self.options)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("appearance options contain duplicate option_id")
        if option_ids != tuple(sorted(option_ids)):
            raise ValueError("appearance options must be ordered by option_id")
        return self


class ClassSkillChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_type: Literal["class_skill"] = "class_skill"
    choice_id: str
    skills: tuple[str, ...]

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @field_validator("skills")
    @classmethod
    def _validate_skills(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(skill not in _SKILL_NAMES for skill in value):
            raise ValueError("skills must contain known skill identities")
        if len(set(value)) != len(value) or value != tuple(sorted(value)):
            raise ValueError("skills must be unique and ordered")
        return value


class StartingProficiencyChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_type: Literal["starting_proficiency"] = "starting_proficiency"
    choice_id: str
    proficiencies: tuple["ProficiencySubject", ...]

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @field_validator("proficiencies")
    @classmethod
    def _validate_proficiencies(
        cls,
        value: tuple["ProficiencySubject", ...],
    ) -> tuple["ProficiencySubject", ...]:
        identities = tuple(
            (row.subject_kind.value, row.identity_key) for row in value
        )
        if not value or identities != tuple(sorted(set(identities))):
            raise ValueError(
                "proficiencies must be non-empty, unique, and ordered",
            )
        return value


class _SingleRefChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str
    selected_ref: ContentRef

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")


class FightingStyleChoice(_SingleRefChoice):
    choice_type: Literal["fighting_style"] = "fighting_style"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if (
            self.selected_ref.definition_kind
            != ContentDefinitionKind.CLASS_FEATURE
        ):
            raise ValueError("fighting style must reference a class feature")
        return self


class SubclassChoice(_SingleRefChoice):
    choice_type: Literal["subclass"] = "subclass"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if self.selected_ref.definition_kind != ContentDefinitionKind.SUBCLASS:
            raise ValueError("subclass choice must reference a subclass")
        return self


class ElementalAncestryChoice(_SingleRefChoice):
    choice_type: Literal["elemental_ancestry"] = "elemental_ancestry"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if (
            self.selected_ref.definition_kind
            != ContentDefinitionKind.CLASS_FEATURE
        ):
            raise ValueError(
                "elemental ancestry must reference a class feature",
            )
        return self


class OriginTraitChoice(_SingleRefChoice):
    """One exact trait selected by an immutable character-origin choice."""

    choice_type: Literal["origin_trait"] = "origin_trait"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if self.selected_ref.definition_kind != ContentDefinitionKind.TRAIT:
            raise ValueError("origin trait choice must reference a trait")
        return self


class FeatChoice(_SingleRefChoice):
    choice_type: Literal["feat"] = "feat"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if self.selected_ref.definition_kind != ContentDefinitionKind.FEAT:
            raise ValueError("feat choice must reference a feat")
        return self


class StartingEquipmentPackageChoice(_SingleRefChoice):
    choice_type: Literal["starting_equipment_package"] = (
        "starting_equipment_package"
    )

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if (
            self.selected_ref.definition_kind
            != ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        ):
            raise ValueError(
                "starting equipment package must reference a typed starting "
                "equipment package",
            )
        return self


class StartingApparelPackageChoice(_SingleRefChoice):
    """One exact, persistent wardrobe selected independently of class gear."""

    choice_type: Literal["starting_apparel_package"] = (
        "starting_apparel_package"
    )

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if (
            self.selected_ref.definition_kind
            != ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        ):
            raise ValueError(
                "starting apparel package must reference a typed starting "
                "equipment package",
            )
        return self


class _MultiRefChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str
    selected_refs: tuple[ContentRef, ...]

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @field_validator("selected_refs")
    @classmethod
    def _validate_refs(cls, value: tuple[ContentRef, ...]) -> tuple[ContentRef, ...]:
        identities = tuple(ref.identity_key for ref in value)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("selected_refs must be non-empty and unique")
        if identities != tuple(sorted(identities)):
            raise ValueError("selected_refs must be ordered by identity")
        return value


class CantripChoice(_MultiRefChoice):
    choice_type: Literal["cantrip"] = "cantrip"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if any(
            ref.definition_kind != ContentDefinitionKind.SPELL
            for ref in self.selected_refs
        ):
            raise ValueError("cantrip choice may reference only spells")
        return self


class SpellKnownChoice(_MultiRefChoice):
    choice_type: Literal["spell_known"] = "spell_known"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if any(
            ref.definition_kind != ContentDefinitionKind.SPELL
            for ref in self.selected_refs
        ):
            raise ValueError("known spell choice may reference only spells")
        return self


class MetamagicChoice(_MultiRefChoice):
    choice_type: Literal["metamagic"] = "metamagic"

    @model_validator(mode="after")
    def _validate_kind(self) -> Self:
        if any(
            ref.definition_kind != ContentDefinitionKind.CLASS_FEATURE
            for ref in self.selected_refs
        ):
            raise ValueError("metamagic choice may reference only class features")
        return self


class SpellReplacementChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_type: Literal["spell_replacement"] = "spell_replacement"
    choice_id: str
    replaced_spell_ref: ContentRef
    learned_spell_ref: ContentRef

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @model_validator(mode="after")
    def _validate_spells(self) -> Self:
        for ref in (self.replaced_spell_ref, self.learned_spell_ref):
            if ref.definition_kind != ContentDefinitionKind.SPELL:
                raise ValueError("spell replacement must reference spells")
        if self.replaced_spell_ref.identity_key == self.learned_spell_ref.identity_key:
            raise ValueError("replacement must learn a different spell")
        return self


class AbilityScoreImprovementChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_type: Literal["ability_score_improvement"] = (
        "ability_score_improvement"
    )
    choice_id: str
    increases: tuple[tuple[ability_types.AbilityName, int], ...]

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @model_validator(mode="after")
    def _validate_increases(self) -> Self:
        abilities = tuple(ability for ability, _ in self.increases)
        if len(set(abilities)) != len(abilities):
            raise ValueError("ASI abilities must be unique")
        if sum(amount for _, amount in self.increases) != 2:
            raise ValueError("ASI must grant exactly two total points")
        if any(amount not in {1, 2} for _, amount in self.increases):
            raise ValueError("ASI increases must be one or two points")
        return self


BuildChoiceSelection: TypeAlias = Annotated[
    ClassSkillChoice
    | StartingProficiencyChoice
    | FightingStyleChoice
    | SubclassChoice
    | CantripChoice
    | SpellKnownChoice
    | SpellReplacementChoice
    | MetamagicChoice
    | ElementalAncestryChoice
    | OriginTraitChoice
    | AbilityScoreImprovementChoice
    | FeatChoice
    | StartingEquipmentPackageChoice
    | StartingApparelPackageChoice,
    Field(discriminator="choice_type"),
]


class ClassLevelEntry(BaseModel):
    """One immutable step in the additive class-level ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    class_level_id: ClassLevelId
    character_level: int = Field(ge=1, le=20)
    class_ref: ContentRef
    resulting_class_level: int = Field(ge=1, le=20)
    subclass_ref: ContentRef | None = None
    choices: tuple[BuildChoiceSelection, ...] = ()

    @model_validator(mode="after")
    def _validate_refs_and_choices(self) -> Self:
        if self.class_ref.definition_kind != ContentDefinitionKind.CLASS:
            raise ValueError("class_ref must reference a class definition")
        if (
            self.subclass_ref is not None
            and self.subclass_ref.definition_kind
            != ContentDefinitionKind.SUBCLASS
        ):
            raise ValueError("subclass_ref must reference a subclass definition")
        choice_ids = tuple(choice.choice_id for choice in self.choices)
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("level choices contain duplicate choice_id")
        if choice_ids != tuple(sorted(choice_ids)):
            raise ValueError("level choices must be ordered by choice_id")
        return self


class ChoiceRequirementKind(str, Enum):
    CLASS_SKILL = "class_skill"
    STARTING_PROFICIENCY = "starting_proficiency"
    FIGHTING_STYLE = "fighting_style"
    SUBCLASS = "subclass"
    CANTRIP = "cantrip"
    SPELL_KNOWN = "spell_known"
    SPELL_REPLACEMENT = "spell_replacement"
    METAMAGIC = "metamagic"
    ELEMENTAL_ANCESTRY = "elemental_ancestry"
    ORIGIN_TRAIT = "origin_trait"
    ABILITY_SCORE_IMPROVEMENT = "ability_score_improvement"
    ABILITY_SCORE_IMPROVEMENT_OR_FEAT = (
        "ability_score_improvement_or_feat"
    )
    FEAT = "feat"
    STARTING_EQUIPMENT_PACKAGE = "starting_equipment_package"
    STARTING_APPAREL_PACKAGE = "starting_apparel_package"


class BuildChoiceRequirement(BaseModel):
    """One authored choice slot offered by an origin or class level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str
    choice_kind: ChoiceRequirementKind
    minimum_selections: int = Field(default=1, ge=0)
    maximum_selections: int = Field(default=1, ge=1)
    allowed_refs: tuple[ContentRef, ...] = ()
    allowed_proficiency_subjects: "tuple[ProficiencySubject, ...]" = ()

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "choice_id")

    @model_validator(mode="after")
    def _validate_requirement(self) -> Self:
        if self.minimum_selections > self.maximum_selections:
            raise ValueError("minimum selections cannot exceed maximum")
        identities = tuple(ref.identity_key for ref in self.allowed_refs)
        if len(set(identities)) != len(identities):
            raise ValueError("allowed_refs must be unique")
        if identities != tuple(sorted(identities)):
            raise ValueError("allowed_refs must be ordered by identity")
        proficiency_choice = self.choice_kind in {
            ChoiceRequirementKind.CLASS_SKILL,
            ChoiceRequirementKind.STARTING_PROFICIENCY,
        }
        if proficiency_choice and self.allowed_refs:
            raise ValueError(
                "proficiency choice requirements cannot use allowed_refs",
            )
        if not proficiency_choice and self.allowed_proficiency_subjects:
            raise ValueError(
                "allowed_proficiency_subjects are reserved for proficiency "
                "choice requirements",
            )
        subject_keys = tuple(
            (row.subject_kind.value, row.identity_key)
            for row in self.allowed_proficiency_subjects
        )
        if subject_keys != tuple(sorted(set(subject_keys))):
            raise ValueError(
                "allowed proficiency subjects must be unique and ordered",
            )
        if (
            self.choice_kind == ChoiceRequirementKind.CLASS_SKILL
            and any(
                row.subject_kind != ProficiencySubjectKind.SKILL
                for row in self.allowed_proficiency_subjects
            )
        ):
            raise ValueError(
                "class skill requirements may allow only skill subjects",
            )
        return self


class ClassLevelDefinition(BaseModel):
    """Authored automatic grants and choices at one class level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    class_level: int = Field(ge=1, le=20)
    automatic_grant_refs: tuple[ContentRef, ...] = ()
    choice_requirements: tuple[BuildChoiceRequirement, ...] = ()

    @model_validator(mode="after")
    def _validate_rows(self) -> Self:
        grant_keys = tuple(ref.identity_key for ref in self.automatic_grant_refs)
        if grant_keys != tuple(sorted(set(grant_keys))):
            raise ValueError("automatic grants must be unique and ordered")
        choice_ids = tuple(
            requirement.choice_id for requirement in self.choice_requirements
        )
        if choice_ids != tuple(sorted(set(choice_ids))):
            raise ValueError("choice requirements must be unique and ordered")
        return self


class ProficiencySubjectKind(str, Enum):
    """Closed first-release proficiency subjects."""

    ABILITY_CHECK = "ability_check"
    SKILL = "skill"
    SAVING_THROW = "saving_throw"
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    TOOL = "tool"
    LANGUAGE = "language"


class ProficiencySubject(BaseModel):
    """Exact non-display identity of one proficiency subject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_kind: ProficiencySubjectKind
    subject_id: str | None = None
    content_ref: ContentRef | None = None

    @field_validator("subject_id")
    @classmethod
    def _validate_subject_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "subject_id")

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        if (self.subject_id is None) == (self.content_ref is None):
            raise ValueError(
                "proficiency subject requires exactly one of subject_id or "
                "content_ref",
            )
        if self.content_ref is not None:
            if self.subject_kind != ProficiencySubjectKind.WEAPON:
                raise ValueError(
                    "exact content_ref proficiency is supported only for "
                    "weapons",
                )
            if self.content_ref.definition_kind != ContentDefinitionKind.ITEM:
                raise ValueError(
                    "exact weapon proficiency must reference an item "
                    "definition",
                )
        return self

    @property
    def identity_key(self) -> str:
        """Return one stable ordering/ownership key for this subject."""
        if self.content_ref is not None:
            return self.content_ref.identity_key
        if self.subject_id is None:
            raise RuntimeError("validated proficiency subject has no identity")
        return self.subject_id


BuildChoiceRequirement.model_rebuild()
StartingProficiencyChoice.model_rebuild()


class ClassProficiencyPackage(BaseModel):
    """Automatic and selectable proficiencies for one entry mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    automatic: tuple[ProficiencySubject, ...] = ()
    choices: tuple[BuildChoiceRequirement, ...] = ()

    @model_validator(mode="after")
    def _validate_rows(self) -> Self:
        subject_keys = tuple(
            (row.subject_kind.value, row.identity_key)
            for row in self.automatic
        )
        if subject_keys != tuple(sorted(set(subject_keys))):
            raise ValueError(
                "automatic proficiencies must be unique and ordered",
            )
        choice_ids = tuple(choice.choice_id for choice in self.choices)
        if choice_ids != tuple(sorted(set(choice_ids))):
            raise ValueError(
                "proficiency choices must be unique and ordered",
            )
        return self


class RitualPreparationPolicy(str, Enum):
    """How one spellcasting source proves ritual entitlement."""

    NONE = "none"
    KNOWN = "known"
    PREPARED = "prepared"
    SPELLBOOK = "spellbook"


class ClassSpellEntitlement(BaseModel):
    """One exact spell-list row owned by a class definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    spell_ref: ContentRef
    spell_rank: int = Field(ge=0, le=9)

    @model_validator(mode="after")
    def _validate_spell(self) -> Self:
        if self.spell_ref.definition_kind != ContentDefinitionKind.SPELL:
            raise ValueError("spell_ref must reference a spell definition")
        return self


class ClassDefinition(BaseModel):
    """Dependency-neutral authored class progression definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hit_die: HitDieSize
    caster_progression: CasterProgression
    spellcasting_feature_class_level: int | None = Field(
        default=None,
        ge=1,
        le=20,
    )
    spellcasting_source_id: SpellcastingSourceId | None = None
    spellcasting_ability: ability_types.AbilityName | None = None
    ritual_policy: RitualPreparationPolicy = RitualPreparationPolicy.NONE
    spell_entitlements: tuple[ClassSpellEntitlement, ...] = ()
    multiclass_prerequisite: "PrerequisiteExpression | None" = None
    first_class_proficiencies: ClassProficiencyPackage = Field(
        default_factory=ClassProficiencyPackage,
    )
    multiclass_proficiencies: ClassProficiencyPackage = Field(
        default_factory=ClassProficiencyPackage,
    )
    saving_throw_proficiencies: tuple[ability_types.AbilityName, ...] = ()
    level_definitions: tuple[ClassLevelDefinition, ...] = ()

    @model_validator(mode="after")
    def _validate_progression(self) -> Self:
        if (
            self.caster_progression == CasterProgression.NON_CASTER
            and (
                self.spellcasting_feature_class_level is not None
                or self.spellcasting_source_id is not None
                or self.spellcasting_ability is not None
                or self.ritual_policy != RitualPreparationPolicy.NONE
                or self.spell_entitlements
            )
        ):
            raise ValueError(
                "non-caster cannot declare spellcasting source, ability, "
                "ritual policy, or spell entitlements",
            )
        if (
            self.caster_progression != CasterProgression.NON_CASTER
            and (
                self.spellcasting_feature_class_level is None
                or self.spellcasting_source_id is None
                or self.spellcasting_ability is None
            )
        ):
            raise ValueError(
                "caster class must declare its Spellcasting level, exact "
                "spellcasting source, and spellcasting ability",
            )
        entitlement_keys = tuple(
            row.spell_ref.identity_key for row in self.spell_entitlements
        )
        if entitlement_keys != tuple(sorted(set(entitlement_keys))):
            raise ValueError("spell entitlements must be unique and ordered")
        levels = tuple(row.class_level for row in self.level_definitions)
        if levels != tuple(sorted(set(levels))):
            raise ValueError("class level definitions must be unique and ordered")
        if self.saving_throw_proficiencies != tuple(
            sorted(set(self.saving_throw_proficiencies), key=lambda row: row.value),
        ):
            raise ValueError(
                "saving throw proficiencies must be unique and ordered",
            )
        return self


class SubclassDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_class_ref: ContentRef
    level_definitions: tuple[ClassLevelDefinition, ...] = ()

    @model_validator(mode="after")
    def _validate_parent(self) -> Self:
        if self.parent_class_ref.definition_kind != ContentDefinitionKind.CLASS:
            raise ValueError("subclass parent must reference a class")
        return self


class OriginLevelGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    character_level: int = Field(ge=1, le=20)
    grant_refs: tuple[ContentRef, ...] = ()

    @model_validator(mode="after")
    def _validate_grants(self) -> Self:
        identities = tuple(ref.identity_key for ref in self.grant_refs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("origin grants must be unique and ordered")
        return self


class OriginInnateSpellGrant(BaseModel):
    """One fixed or creator-selected spell owned by an origin source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: str
    unlock_character_level: int = Field(ge=1, le=20)
    spell_ref: ContentRef | None = None
    choice_id: str | None = None
    allowed_spell_refs: tuple[ContentRef, ...] = ()
    fixed_cast_rank: int = Field(ge=0, le=9)
    uses_per_long_rest: int | None = Field(default=None, ge=1)

    @field_validator("grant_id")
    @classmethod
    def _validate_grant_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "grant_id")

    @field_validator("choice_id")
    @classmethod
    def _validate_choice_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "choice_id")

    @model_validator(mode="after")
    def _validate_spell_source(self) -> Self:
        fixed = self.spell_ref is not None
        chosen = self.choice_id is not None or bool(self.allowed_spell_refs)
        if fixed == chosen:
            raise ValueError(
                "innate spell grant requires exactly one fixed spell or "
                "choice-backed spell set",
            )
        refs = (
            (self.spell_ref,)
            if self.spell_ref is not None
            else self.allowed_spell_refs
        )
        if (
            not refs
            or any(
                ref.definition_kind != ContentDefinitionKind.SPELL
                for ref in refs
            )
        ):
            raise ValueError("innate spell grants may reference only spells")
        identities = tuple(ref.identity_key for ref in refs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError(
                "innate spell references must be unique and ordered",
            )
        if self.choice_id is None and self.allowed_spell_refs:
            raise ValueError("chosen innate spells require a choice_id")
        if self.choice_id is not None and not self.allowed_spell_refs:
            raise ValueError(
                "chosen innate spells require allowed_spell_refs",
            )
        if self.fixed_cast_rank > 0 and self.uses_per_long_rest is None:
            raise ValueError(
                "leveled innate spell requires explicit long-rest uses",
            )
        return self


class OriginInnateSpellcastingDefinition(BaseModel):
    """One origin-owned casting source independent of class spellcasting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: SpellcastingSourceId
    ability: ability_types.AbilityName
    grants: tuple[OriginInnateSpellGrant, ...]

    @model_validator(mode="after")
    def _validate_grants(self) -> Self:
        grant_ids = tuple(grant.grant_id for grant in self.grants)
        if not grant_ids or grant_ids != tuple(sorted(set(grant_ids))):
            raise ValueError(
                "innate spell grants must be non-empty, unique, and ordered",
            )
        choice_ids = tuple(
            grant.choice_id
            for grant in self.grants
            if grant.choice_id is not None
        )
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("innate spell choice_id values must be unique")
        return self


def _validate_origin_rows(
    level_grants: tuple[OriginLevelGrant, ...],
    choice_requirements: tuple[BuildChoiceRequirement, ...],
    innate_spellcasting: tuple[OriginInnateSpellcastingDefinition, ...],
) -> None:
    levels = tuple(row.character_level for row in level_grants)
    if levels != tuple(sorted(set(levels))):
        raise ValueError("origin level grants must be unique and ordered")
    choice_ids = tuple(row.choice_id for row in choice_requirements)
    if choice_ids != tuple(sorted(set(choice_ids))):
        raise ValueError("origin choice requirements must be unique and ordered")
    source_ids = tuple(row.source_id.value for row in innate_spellcasting)
    if source_ids != tuple(sorted(set(source_ids))):
        raise ValueError(
            "origin innate spellcasting sources must be unique and ordered",
        )
    requirement_by_id = {
        requirement.choice_id: requirement
        for requirement in choice_requirements
    }
    for source in innate_spellcasting:
        for grant in source.grants:
            if grant.choice_id is None:
                continue
            requirement = requirement_by_id.get(grant.choice_id)
            if (
                requirement is None
                or requirement.choice_kind is not ChoiceRequirementKind.CANTRIP
                or requirement.allowed_refs != grant.allowed_spell_refs
                or requirement.minimum_selections != 1
                or requirement.maximum_selections != 1
            ):
                raise ValueError(
                    "chosen innate spell must match one exact required "
                    "cantrip choice",
                )


class SpeciesDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_support: OriginRuntimeSupport
    level_grants: tuple[OriginLevelGrant, ...] = ()
    choice_requirements: tuple[BuildChoiceRequirement, ...] = ()
    innate_spellcasting: tuple[
        OriginInnateSpellcastingDefinition,
        ...,
    ] = ()

    @model_validator(mode="after")
    def _validate_rows(self) -> Self:
        _validate_origin_rows(
            self.level_grants,
            self.choice_requirements,
            self.innate_spellcasting,
        )
        return self


class SpeciesVariantDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_species_ref: ContentRef
    runtime_support: OriginRuntimeSupport
    level_grants: tuple[OriginLevelGrant, ...] = ()
    choice_requirements: tuple[BuildChoiceRequirement, ...] = ()
    innate_spellcasting: tuple[
        OriginInnateSpellcastingDefinition,
        ...,
    ] = ()

    @model_validator(mode="after")
    def _validate_parent(self) -> Self:
        if self.parent_species_ref.definition_kind != ContentDefinitionKind.SPECIES:
            raise ValueError("species variant parent must reference a species")
        _validate_origin_rows(
            self.level_grants,
            self.choice_requirements,
            self.innate_spellcasting,
        )
        return self


class BackgroundDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_support: OriginRuntimeSupport
    automatic_grant_refs: tuple[ContentRef, ...] = ()
    starting_holdings_package_ref: ContentRef | None = None
    choice_requirements: tuple[BuildChoiceRequirement, ...] = ()

    @model_validator(mode="after")
    def _validate_rows(self) -> Self:
        grant_keys = tuple(
            ref.identity_key for ref in self.automatic_grant_refs
        )
        if grant_keys != tuple(sorted(set(grant_keys))):
            raise ValueError(
                "background automatic grants must be unique and ordered",
            )
        if (
            self.starting_holdings_package_ref is not None
            and self.starting_holdings_package_ref.definition_kind
            is not ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        ):
            raise ValueError(
                "background starting holdings must reference one starting "
                "equipment package",
            )
        choice_ids = tuple(
            row.choice_id for row in self.choice_requirements
        )
        if choice_ids != tuple(sorted(set(choice_ids))):
            raise ValueError(
                "background choice requirements must be unique and ordered",
            )
        return self


class AllOfPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["all_of"] = "all_of"
    prerequisites: tuple["PrerequisiteExpression", ...]


class AnyOfPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["any_of"] = "any_of"
    prerequisites: tuple["PrerequisiteExpression", ...]


class NotPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["not"] = "not"
    prerequisite: "PrerequisiteExpression"


class ClassLevelPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["class_level"] = "class_level"
    class_ref: ContentRef
    minimum: int = Field(ge=1, le=20)


class TotalCharacterLevelPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["total_character_level"] = "total_character_level"
    minimum: int = Field(ge=1, le=20)


class AbilityScorePrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["ability_score"] = "ability_score"
    ability: ability_types.AbilityName
    minimum: int = Field(ge=1, le=30)


class HasFeaturePrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["has_feature"] = "has_feature"
    feature_ref: ContentRef


class KnowsSpellPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prerequisite_type: Literal["knows_spell"] = "knows_spell"
    spell_ref: ContentRef


PrerequisiteExpression: TypeAlias = Annotated[
    AllOfPrerequisite
    | AnyOfPrerequisite
    | NotPrerequisite
    | ClassLevelPrerequisite
    | TotalCharacterLevelPrerequisite
    | AbilityScorePrerequisite
    | HasFeaturePrerequisite
    | KnowsSpellPrerequisite,
    Field(discriminator="prerequisite_type"),
]

AllOfPrerequisite.model_rebuild()
AnyOfPrerequisite.model_rebuild()
NotPrerequisite.model_rebuild()
ClassDefinition.model_rebuild()


def compute_character_definition_v2_digest(
    *,
    character_id: UUID,
    schema_version: Literal[2],
    definition_revision: int,
    body_recipe: ContentRecipe,
    species_ref: ContentRef,
    species_variant_ref: ContentRef | None,
    background_ref: ContentRef,
    immutable_origin_choices: tuple[BuildChoiceSelection, ...],
    appearance: CharacterAppearanceSelection,
    base_ability_scores: AbilityScoreAllocation,
    flexible_ability_bonuses: FlexibleAbilityBonusSelection,
    class_levels: tuple[ClassLevelEntry, ...],
    premade_id: str | None,
    earned_character_level: int,
    content_set_digest: str,
    ruleset_digest: str,
) -> str:
    """Authenticate every structural field in a schema-2 character build."""
    return _canonical_sha256({
        "character_id": str(character_id),
        "schema_version": schema_version,
        "definition_revision": definition_revision,
        "body_recipe": body_recipe.model_dump(mode="json"),
        "species_ref": species_ref.model_dump(mode="json"),
        "species_variant_ref": (
            species_variant_ref.model_dump(mode="json")
            if species_variant_ref is not None
            else None
        ),
        "background_ref": background_ref.model_dump(mode="json"),
        "immutable_origin_choices": [
            choice.model_dump(mode="json")
            for choice in immutable_origin_choices
        ],
        "appearance": appearance.model_dump(mode="json"),
        "base_ability_scores": base_ability_scores.model_dump(mode="json"),
        "flexible_ability_bonuses": flexible_ability_bonuses.model_dump(
            mode="json",
        ),
        "class_levels": [
            level.model_dump(mode="json") for level in class_levels
        ],
        "premade_id": premade_id,
        "earned_character_level": earned_character_level,
        "content_set_digest": content_set_digest,
        "ruleset_digest": ruleset_digest,
    })


class CharacterDefinitionRevisionV2(BaseModel):
    """Immutable additive build ledger for a persistent character."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    character_id: UUID
    schema_version: Literal[2] = 2
    definition_revision: int = Field(ge=1)
    body_recipe: ContentRecipe
    species_ref: ContentRef
    species_variant_ref: ContentRef | None = None
    background_ref: ContentRef
    immutable_origin_choices: tuple[BuildChoiceSelection, ...] = ()
    appearance: CharacterAppearanceSelection
    base_ability_scores: AbilityScoreAllocation
    flexible_ability_bonuses: FlexibleAbilityBonusSelection
    class_levels: tuple[ClassLevelEntry, ...]
    premade_id: str | None = None
    earned_character_level: int = Field(ge=1, le=20)
    content_set_digest: str
    ruleset_digest: str
    definition_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_id: UUID,
        definition_revision: int,
        body_recipe: ContentRecipe,
        species_ref: ContentRef,
        background_ref: ContentRef,
        appearance: CharacterAppearanceSelection,
        base_ability_scores: AbilityScoreAllocation,
        flexible_ability_bonuses: FlexibleAbilityBonusSelection,
        class_levels: tuple[ClassLevelEntry, ...],
        earned_character_level: int,
        content_set_digest: str,
        ruleset_digest: str,
        species_variant_ref: ContentRef | None = None,
        immutable_origin_choices: tuple[BuildChoiceSelection, ...] = (),
        premade_id: str | None = None,
        schema_version: Literal[2] = 2,
    ) -> Self:
        """Create a schema-2 revision with its canonical digest."""
        return cls(
            character_id=character_id,
            schema_version=schema_version,
            definition_revision=definition_revision,
            body_recipe=body_recipe,
            species_ref=species_ref,
            species_variant_ref=species_variant_ref,
            background_ref=background_ref,
            immutable_origin_choices=immutable_origin_choices,
            appearance=appearance,
            base_ability_scores=base_ability_scores,
            flexible_ability_bonuses=flexible_ability_bonuses,
            class_levels=class_levels,
            premade_id=premade_id,
            earned_character_level=earned_character_level,
            content_set_digest=content_set_digest,
            ruleset_digest=ruleset_digest,
            definition_digest=compute_character_definition_v2_digest(
                character_id=character_id,
                schema_version=schema_version,
                definition_revision=definition_revision,
                body_recipe=body_recipe,
                species_ref=species_ref,
                species_variant_ref=species_variant_ref,
                background_ref=background_ref,
                immutable_origin_choices=immutable_origin_choices,
                appearance=appearance,
                base_ability_scores=base_ability_scores,
                flexible_ability_bonuses=flexible_ability_bonuses,
                class_levels=class_levels,
                premade_id=premade_id,
                earned_character_level=earned_character_level,
                content_set_digest=content_set_digest,
                ruleset_digest=ruleset_digest,
            ),
        )

    @field_validator("premade_id")
    @classmethod
    def _validate_premade_id(cls, value: str | None) -> str | None:
        return (
            None
            if value is None
            else validate_namespaced_id(value, "premade_id")
        )

    @field_validator("content_set_digest", "ruleset_digest", "definition_digest")
    @classmethod
    def _validate_digest(cls, value: str, info) -> str:
        return validate_sha256(value, info.field_name)

    @model_validator(mode="after")
    def _validate_definition(self) -> Self:
        if self.body_recipe.ref.definition_kind != ContentDefinitionKind.CREATURE:
            raise ValueError("body_recipe must reference a creature definition")
        if self.species_ref.definition_kind != ContentDefinitionKind.SPECIES:
            raise ValueError("species_ref must reference a species definition")
        if (
            self.species_variant_ref is not None
            and self.species_variant_ref.definition_kind
            != ContentDefinitionKind.SPECIES_VARIANT
        ):
            raise ValueError(
                "species_variant_ref must reference a species variant",
            )
        if self.background_ref.definition_kind != ContentDefinitionKind.BACKGROUND:
            raise ValueError("background_ref must reference a background")
        if len(self.class_levels) != self.earned_character_level:
            raise ValueError(
                "class level ledger length must equal earned character level",
            )
        expected_character_levels = tuple(
            range(1, self.earned_character_level + 1),
        )
        if (
            tuple(level.character_level for level in self.class_levels)
            != expected_character_levels
        ):
            raise ValueError("class level ledger must be contiguous and ordered")
        counts: dict[str, int] = {}
        subclasses: dict[str, str] = {}
        for level in self.class_levels:
            class_key = level.class_ref.identity_key
            counts[class_key] = counts.get(class_key, 0) + 1
            if level.resulting_class_level != counts[class_key]:
                raise ValueError(
                    "resulting_class_level must count prior levels in that class",
                )
            if level.subclass_ref is not None:
                subclass_key = level.subclass_ref.identity_key
                previous = subclasses.setdefault(class_key, subclass_key)
                if previous != subclass_key:
                    raise ValueError("a class cannot change subclass in one ledger")
            elif class_key in subclasses:
                raise ValueError("subclass_ref cannot disappear after selection")
        level_ids = tuple(level.class_level_id.value for level in self.class_levels)
        if len(set(level_ids)) != len(level_ids):
            raise ValueError("class level ledger IDs must be unique")
        origin_ids = tuple(
            choice.choice_id for choice in self.immutable_origin_choices
        )
        if origin_ids != tuple(sorted(set(origin_ids))):
            raise ValueError("origin choices must be unique and ordered")
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        self.body_recipe.verify_integrity()
        expected = compute_character_definition_v2_digest(
            character_id=self.character_id,
            schema_version=self.schema_version,
            definition_revision=self.definition_revision,
            body_recipe=self.body_recipe,
            species_ref=self.species_ref,
            species_variant_ref=self.species_variant_ref,
            background_ref=self.background_ref,
            immutable_origin_choices=self.immutable_origin_choices,
            appearance=self.appearance,
            base_ability_scores=self.base_ability_scores,
            flexible_ability_bonuses=self.flexible_ability_bonuses,
            class_levels=self.class_levels,
            premade_id=self.premade_id,
            earned_character_level=self.earned_character_level,
            content_set_digest=self.content_set_digest,
            ruleset_digest=self.ruleset_digest,
        )
        if expected != self.definition_digest:
            raise ValueError(
                "definition_digest does not authenticate schema-2 definition",
            )


class PreparedSpellSourceLoadout(BaseModel):
    """Prepared spells owned by one exact casting source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    spellcasting_source_id: SpellcastingSourceId
    spell_refs: tuple[ContentRef, ...] = ()

    @model_validator(mode="after")
    def _validate_spells(self) -> Self:
        if any(
            ref.definition_kind != ContentDefinitionKind.SPELL
            for ref in self.spell_refs
        ):
            raise ValueError("prepared spell rows may reference only spells")
        identities = tuple(ref.identity_key for ref in self.spell_refs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("prepared spells must be unique and ordered")
        return self


class FeatureToggleSelection(BaseModel):
    """One persisted opt-in/out for an exact toggleable feature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_ref: ContentRef
    enabled: bool


def compute_character_loadout_digest(
    *,
    character_id: UUID,
    schema_version: Literal[1],
    loadout_revision: int,
    based_on_definition_revision: int,
    prepared_spells: tuple[PreparedSpellSourceLoadout, ...],
    feature_toggles: tuple[FeatureToggleSelection, ...],
) -> str:
    return _canonical_sha256({
        "character_id": str(character_id),
        "schema_version": schema_version,
        "loadout_revision": loadout_revision,
        "based_on_definition_revision": based_on_definition_revision,
        "prepared_spells": [
            row.model_dump(mode="json") for row in prepared_spells
        ],
        "feature_toggles": [
            row.model_dump(mode="json") for row in feature_toggles
        ],
    })


class CharacterLoadoutRevisionV1(BaseModel):
    """Mutable-between-games selections revisioned apart from structure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    character_id: UUID
    schema_version: Literal[1] = 1
    loadout_revision: int = Field(ge=1)
    based_on_definition_revision: int = Field(ge=1)
    prepared_spells: tuple[PreparedSpellSourceLoadout, ...] = ()
    feature_toggles: tuple[FeatureToggleSelection, ...] = ()
    loadout_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_id: UUID,
        loadout_revision: int,
        based_on_definition_revision: int,
        prepared_spells: tuple[PreparedSpellSourceLoadout, ...] = (),
        feature_toggles: tuple[FeatureToggleSelection, ...] = (),
        schema_version: Literal[1] = 1,
    ) -> Self:
        return cls(
            character_id=character_id,
            schema_version=schema_version,
            loadout_revision=loadout_revision,
            based_on_definition_revision=based_on_definition_revision,
            prepared_spells=prepared_spells,
            feature_toggles=feature_toggles,
            loadout_digest=compute_character_loadout_digest(
                character_id=character_id,
                schema_version=schema_version,
                loadout_revision=loadout_revision,
                based_on_definition_revision=based_on_definition_revision,
                prepared_spells=prepared_spells,
                feature_toggles=feature_toggles,
            ),
        )

    @field_validator("loadout_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return validate_sha256(value, "loadout_digest")

    @model_validator(mode="after")
    def _validate_loadout(self) -> Self:
        source_ids = tuple(
            row.spellcasting_source_id.value for row in self.prepared_spells
        )
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError(
                "prepared spell sources must be unique and ordered",
            )
        feature_ids = tuple(
            row.feature_ref.identity_key for row in self.feature_toggles
        )
        if feature_ids != tuple(sorted(set(feature_ids))):
            raise ValueError("feature toggles must be unique and ordered")
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        expected = compute_character_loadout_digest(
            character_id=self.character_id,
            schema_version=self.schema_version,
            loadout_revision=self.loadout_revision,
            based_on_definition_revision=self.based_on_definition_revision,
            prepared_spells=self.prepared_spells,
            feature_toggles=self.feature_toggles,
        )
        if expected != self.loadout_digest:
            raise ValueError(
                "loadout_digest does not authenticate character loadout",
            )
