"""Canonical schema-2 composition for built-in character fixtures.

The persistent-character API accepts the general schema-2 ledger directly.
This module is only the authored-data adapter used by built-in premades and
engine-owned evaluation scenarios.  It never constructs a class-shaped Entity;
all runtime state is installed by :func:`materialize_character`.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal
from uuid import UUID, uuid5

from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_CLASS_REF,
    BERSERKER_SUBCLASS_REF,
)
from dnd.classes.progression_definitions import (
    CHAMPION_SUBCLASS_DEFINITION,
    CHAMPION_SUBCLASS_REF,
    FIGHTER_CLASS_DEFINITION,
    FIGHTER_CLASS_REF,
)
from dnd.classes.sorcerer_progression_definitions import (
    DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
    DRACONIC_BLOODLINE_SUBCLASS_REF,
    SORCERER_CLASS_DEFINITION,
    SORCERER_CLASS_REF,
)
from dnd.content_system.character_origin_definitions import (
    ADVENTURER_BACKGROUND_REF,
    HUMAN_SPECIES_REF,
)
from dnd.content_system.character_appearance import (
    BARBARIAN_HUMAN_APPEARANCE,
    FIGHTER_HUMAN_APPEARANCE,
    SORCERER_HUMAN_APPEARANCE,
    default_player_character_appearance,
)
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_CHOICE_ID,
    STARTING_APPAREL_PACKAGE_DECLARATIONS_BY_ID,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_NAME,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreImprovementChoice,
    AbilityScoreName,
    BuildChoiceSelection,
    CantripChoice,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterItemV2,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    ElementalAncestryChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    MetamagicChoice,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpellKnownChoice,
    StartingApparelPackageChoice,
    StartingProficiencyChoice,
    StartingEquipmentPackageChoice,
    SubclassChoice,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.premade_characters import (
    CharacterCreationPlan,
    CharacterCreationPlanKind,
    CharacterBuildDraft,
    CharacterLoadoutDraft,
    StarterHoldingTemplate,
)
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.language_types import SrdLanguageId
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE


BuiltinClassId = Literal["barbarian", "fighter", "sorcerer"]
AbilityIncrease = tuple[AbilityScoreName, int]
LevelAbilityIncreases = tuple[tuple[int, tuple[AbilityIncrease, ...]], ...]

DEFAULT_CHARACTER_RULESET_DIGEST = character_ruleset_digest(
    permissive_multiclass_prerequisites=True,
    multiclass_slot_rounding_policy=(
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    ),
)


@dataclass(frozen=True, slots=True)
class BuiltinSingleClassBuild:
    """Authored inputs for one engine-owned schema-2 single-class fixture."""

    class_id: BuiltinClassId
    level: int
    equipment_preset: str
    appearance: CharacterAppearanceSelection | None = None
    asi_by_level: LevelAbilityIncreases = ()
    fighting_style: str | None = None
    metamagic_choices: tuple[str, ...] = ()
    spell_names: tuple[str, ...] = ()
    premade_id: str | None = None
    display_name: str | None = None
    additional_holdings: tuple[StarterHoldingTemplate, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 20:
            raise ValueError("built-in class level must be between 1 and 20")
        asi_levels = tuple(level for level, _ in self.asi_by_level)
        if asi_levels != tuple(sorted(set(asi_levels))):
            raise ValueError("ASI rows must have unique ordered class levels")


@dataclass(frozen=True, slots=True)
class BuiltinMulticlassBuild:
    """Authored inputs for one engine-owned schema-2 multiclass fixture."""

    class_builds: tuple[BuiltinSingleClassBuild, ...]
    base_ability_scores: AbilityScoreAllocation
    flexible_ability_bonuses: FlexibleAbilityBonusSelection
    appearance: CharacterAppearanceSelection
    premade_id: str | None = None
    display_name: str | None = None
    additional_holdings: tuple[StarterHoldingTemplate, ...] = ()

    def __post_init__(self) -> None:
        if len(self.class_builds) < 2:
            raise ValueError(
                "built-in multiclass fixtures require at least two classes",
            )
        class_ids = tuple(row.class_id for row in self.class_builds)
        if class_ids != tuple(dict.fromkeys(class_ids)):
            raise ValueError(
                "built-in multiclass class tracks must be unique",
            )
        if self.level > 20:
            raise ValueError(
                "built-in multiclass total level cannot exceed 20",
            )
        if any(
            (
                row.premade_id is not None
                or row.display_name is not None
                or row.additional_holdings
            )
            for row in self.class_builds
        ):
            raise ValueError(
                "multiclass track rows cannot own premade catalog identity "
                "or holdings",
            )

    @property
    def level(self) -> int:
        """Return total character level across the ordered class ledger."""
        return sum(row.level for row in self.class_builds)


BuiltinCharacterBuild = BuiltinSingleClassBuild | BuiltinMulticlassBuild


@dataclass(frozen=True, slots=True)
class BuiltinCharacterRevisions:
    """The exact durable revision triplet produced from one built-in build."""

    definition: CharacterDefinitionRevisionV2
    holdings: CharacterHoldingsRevision
    loadout: CharacterLoadoutRevisionV1


def _require_choice_ref(
    *,
    class_definition: ClassDefinition | SubclassDefinition,
    class_level: int,
    choice_id: str,
    content_id_suffix: str,
) -> ContentRef:
    level_definition = class_definition.level_definitions[class_level - 1]
    requirement = next(
        (
            row
            for row in level_definition.choice_requirements
            if row.choice_id == choice_id
        ),
        None,
    )
    if requirement is None:
        raise ValueError(f"Missing authored choice requirement {choice_id}")
    matches = tuple(
        ref
        for ref in requirement.allowed_refs
        if ref.content_id.endswith(content_id_suffix)
    )
    if len(matches) != 1:
        raise ValueError(
            f"{choice_id} has no unique {content_id_suffix!r} exact ref",
        )
    return matches[0]


def _asi_choices(
    build: BuiltinSingleClassBuild,
) -> dict[int, AbilityScoreImprovementChoice]:
    choices: dict[int, AbilityScoreImprovementChoice] = {}
    for level, increases in build.asi_by_level:
        choices[level] = AbilityScoreImprovementChoice(
            choice_id=f"class.{build.class_id}.level_{level}.asi_or_feat",
            increases=increases,
        )
    return choices


def _starting_equipment_choice(
    build: BuiltinSingleClassBuild,
) -> StartingEquipmentPackageChoice:
    declaration = STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET.get(
        (build.class_id, build.equipment_preset),
    )
    if declaration is None:
        raise ValueError(
            f"Unknown {build.class_id} equipment preset "
            f"{build.equipment_preset!r}",
        )
    return StartingEquipmentPackageChoice(
        choice_id=(
            f"class.{build.class_id}.first_class.starting_equipment"
        ),
        selected_ref=declaration.ref,
    )


def _fighter_levels(
    build: BuiltinSingleClassBuild,
) -> tuple[ClassLevelEntry, ...]:
    style = build.fighting_style or "defense"
    style_suffix = {
        "archery": "fighting_style.archery",
        "defense": "fighting_style.defense",
        "dueling": "fighting_style.dueling",
        "great_weapon": "fighting_style.great_weapon_fighting",
        "protection": "fighting_style.protection",
        "two_weapon": "fighting_style.two_weapon_fighting",
    }.get(style)
    if style_suffix is None:
        raise ValueError(f"Unknown Fighter fighting style {style!r}")
    first_style_ref = _require_choice_ref(
        class_definition=FIGHTER_CLASS_DEFINITION,
        class_level=1,
        choice_id="class.fighter.level_1.fighting_style",
        content_id_suffix=style_suffix,
    )
    second_style_suffix = (
        "fighting_style.defense"
        if style == "archery"
        else "fighting_style.archery"
    )
    second_style_ref = _require_choice_ref(
        class_definition=CHAMPION_SUBCLASS_DEFINITION,
        class_level=10,
        choice_id=(
            "subclass.fighter.champion.level_10.fighting_style"
        ),
        content_id_suffix=second_style_suffix,
    )
    asi = _asi_choices(build)
    levels: list[ClassLevelEntry] = []
    for level in range(1, build.level + 1):
        choices = []
        if level == 1:
            choices.extend((
                ClassSkillChoice(
                    choice_id="class.fighter.proficiencies.skills",
                    skills=("athletics", "perception"),
                ),
                FightingStyleChoice(
                    choice_id="class.fighter.level_1.fighting_style",
                    selected_ref=first_style_ref,
                ),
                _starting_equipment_choice(build),
            ))
        if level == 3:
            choices.append(SubclassChoice(
                choice_id="class.fighter.level_3.subclass",
                selected_ref=CHAMPION_SUBCLASS_REF,
            ))
        if level == 10:
            choices.append(FightingStyleChoice(
                choice_id=(
                    "subclass.fighter.champion.level_10.fighting_style"
                ),
                selected_ref=second_style_ref,
            ))
        if level in asi:
            choices.append(asi[level])
        levels.append(ClassLevelEntry(
            class_level_id=ClassLevelId(value=f"fighter.level_{level}"),
            character_level=level,
            class_ref=FIGHTER_CLASS_REF,
            resulting_class_level=level,
            subclass_ref=(
                CHAMPION_SUBCLASS_REF if level >= 3 else None
            ),
            choices=tuple(
                sorted(choices, key=lambda choice: choice.choice_id),
            ),
        ))
    return tuple(levels)


def _barbarian_levels(
    build: BuiltinSingleClassBuild,
) -> tuple[ClassLevelEntry, ...]:
    asi = _asi_choices(build)
    levels: list[ClassLevelEntry] = []
    for level in range(1, build.level + 1):
        choices = []
        if level == 1:
            choices.extend((
                ClassSkillChoice(
                    choice_id="class.barbarian.proficiencies.skills",
                    skills=("athletics", "perception"),
                ),
                _starting_equipment_choice(build),
            ))
        if level == 3:
            choices.append(SubclassChoice(
                choice_id="class.barbarian.level_3.subclass",
                selected_ref=BERSERKER_SUBCLASS_REF,
            ))
        if level in asi:
            choices.append(asi[level])
        levels.append(ClassLevelEntry(
            class_level_id=ClassLevelId(value=f"barbarian.level_{level}"),
            character_level=level,
            class_ref=BARBARIAN_CLASS_REF,
            resulting_class_level=level,
            subclass_ref=(
                BERSERKER_SUBCLASS_REF if level >= 3 else None
            ),
            choices=tuple(
                sorted(choices, key=lambda choice: choice.choice_id),
            ),
        ))
    return tuple(levels)


def _sorcerer_spell_choices(
    build: BuiltinSingleClassBuild,
) -> dict[int, tuple[CantripChoice | SpellKnownChoice, ...]]:
    requested_rows = tuple(
        SPELL_CATALOG_COMPOSITION_BY_NAME[name]
        for name in build.spell_names
    )
    entitlement_keys = {
        row.spell_ref.identity_key
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
    }
    if any(
        row.declaration.ref.identity_key not in entitlement_keys
        for row in requested_rows
    ):
        raise ValueError("Built-in Sorcerer names a non-Sorcerer spell")

    entitlement_rows = tuple(
        sorted(
            (
                row
                for row in SPELL_CATALOG_COMPOSITION_BY_NAME.values()
                if row.declaration.ref.identity_key in entitlement_keys
            ),
            key=lambda row: row.declaration.ref.identity_key,
        ),
    )
    requested_cantrips = [
        row.declaration.ref for row in requested_rows if row.level == 0
    ]
    for row in entitlement_rows:
        if row.level == 0 and row.declaration.ref not in requested_cantrips:
            requested_cantrips.append(row.declaration.ref)
    selected_cantrips = list(
        sorted(requested_cantrips[:4], key=lambda ref: ref.identity_key),
    )

    requested_ranked = [
        row for row in requested_rows if row.level > 0
    ]
    selected_ranked_keys: set[str] = set()
    choices: dict[int, tuple[CantripChoice | SpellKnownChoice, ...]] = {}
    learn_counts = {
        1: 2,
        2: 1,
        3: 1,
        4: 1,
        5: 1,
        6: 1,
        7: 1,
        8: 1,
        9: 1,
        10: 1,
        11: 1,
        13: 1,
        15: 1,
        17: 1,
    }
    cantrip_counts = {1: 4, 4: 1, 10: 1}
    for level in range(1, build.level + 1):
        rows: list[CantripChoice | SpellKnownChoice] = []
        if level in cantrip_counts:
            if level == 1:
                selected = tuple(selected_cantrips)
            else:
                available = tuple(
                    row.declaration.ref
                    for row in entitlement_rows
                    if (
                        row.level == 0
                        and row.declaration.ref not in selected_cantrips
                    )
                )
                selected = tuple(sorted(
                    available[:cantrip_counts[level]],
                    key=lambda ref: ref.identity_key,
                ))
                selected_cantrips.extend(selected)
            rows.append(CantripChoice(
                choice_id=f"class.sorcerer.level_{level}.cantrips",
                selected_refs=selected,
            ))
        learn_count = learn_counts.get(level)
        if learn_count is not None:
            maximum_rank = min(9, (level + 1) // 2)
            eligible_requested = [
                row
                for row in requested_ranked
                if (
                    row.level <= maximum_rank
                    and row.declaration.ref.identity_key
                    not in selected_ranked_keys
                )
            ]
            eligible_requested.sort(
                key=lambda row: (
                    -row.level,
                    requested_ranked.index(row),
                ),
            )
            eligible_fallback = [
                row
                for row in entitlement_rows
                if (
                    0 < row.level <= maximum_rank
                    and row.declaration.ref.identity_key
                    not in selected_ranked_keys
                    and row not in eligible_requested
                )
            ]
            selected_rows = (
                eligible_requested + eligible_fallback
            )[:learn_count]
            if len(selected_rows) != learn_count:
                raise ValueError("Insufficient authored Sorcerer spells")
            selected_refs = tuple(sorted(
                (row.declaration.ref for row in selected_rows),
                key=lambda ref: ref.identity_key,
            ))
            selected_ranked_keys.update(
                ref.identity_key for ref in selected_refs
            )
            rows.append(SpellKnownChoice(
                choice_id=f"class.sorcerer.level_{level}.spell_known",
                selected_refs=selected_refs,
            ))
        choices[level] = tuple(
            sorted(rows, key=lambda choice: choice.choice_id),
        )
    return choices


def _sorcerer_levels(
    build: BuiltinSingleClassBuild,
) -> tuple[ClassLevelEntry, ...]:
    asi = _asi_choices(build)
    spell_choices = _sorcerer_spell_choices(build)
    metamagic_by_name = {
        name: _require_choice_ref(
            class_definition=SORCERER_CLASS_DEFINITION,
            class_level=3,
            choice_id="class.sorcerer.level_3.metamagic",
            content_id_suffix=f"metamagic.{name}_spell",
        )
        for name in ("distant", "quickened", "twinned")
    }
    requested_metamagic_names = (
        build.metamagic_choices or ("quickened", "twinned")
    )
    if len(set(requested_metamagic_names)) != len(
        requested_metamagic_names,
    ):
        raise ValueError("Built-in Sorcerer Metamagic choices must be unique")
    unsupported_metamagic_names = (
        set(requested_metamagic_names) - set(metamagic_by_name)
    )
    if unsupported_metamagic_names:
        values = ", ".join(sorted(unsupported_metamagic_names))
        raise ValueError(f"Unknown Sorcerer Metamagic choices: {values}")
    metamagic_names = tuple(requested_metamagic_names) + tuple(
        name
        for name in ("quickened", "twinned", "distant")
        if name not in requested_metamagic_names
    )
    if len(metamagic_names) < 3:
        raise ValueError("Built-in Sorcerer requires three Metamagic choices")
    metamagic_refs = tuple(metamagic_by_name[name] for name in metamagic_names)
    ancestry_ref = _require_choice_ref(
        # Ancestry is authored by the subclass, not the class.
        class_definition=DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
        class_level=1,
        choice_id=(
            "subclass.sorcerer.draconic_bloodline.level_1.ancestry"
        ),
        content_id_suffix="draconic_ancestry.red",
    )
    levels: list[ClassLevelEntry] = []
    for level in range(1, build.level + 1):
        choices: list[BuildChoiceSelection] = list(spell_choices[level])
        if level == 1:
            choices.extend((
                ClassSkillChoice(
                    choice_id="class.sorcerer.proficiencies.skills",
                    skills=("arcana", "deception"),
                ),
                ElementalAncestryChoice(
                    choice_id=(
                        "subclass.sorcerer.draconic_bloodline."
                        "level_1.ancestry"
                    ),
                    selected_ref=ancestry_ref,
                ),
                _starting_equipment_choice(build),
                SubclassChoice(
                    choice_id="class.sorcerer.level_1.subclass",
                    selected_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
                ),
            ))
        if level == 3:
            choices.append(MetamagicChoice(
                choice_id="class.sorcerer.level_3.metamagic",
                selected_refs=tuple(sorted(
                    metamagic_refs[:2],
                    key=lambda ref: ref.identity_key,
                )),
            ))
        if level == 10:
            choices.append(MetamagicChoice(
                choice_id="class.sorcerer.level_10.metamagic",
                selected_refs=(metamagic_refs[2],),
            ))
        if level in asi:
            choices.append(asi[level])
        levels.append(ClassLevelEntry(
            class_level_id=ClassLevelId(value=f"sorcerer.level_{level}"),
            character_level=level,
            class_ref=SORCERER_CLASS_REF,
            resulting_class_level=level,
            subclass_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
            choices=tuple(
                sorted(choices, key=lambda choice: choice.choice_id),
            ),
        ))
    return tuple(levels)


def _single_class_levels(
    build: BuiltinSingleClassBuild,
) -> tuple[ClassLevelEntry, ...]:
    if build.class_id == "fighter":
        return _fighter_levels(build)
    if build.class_id == "barbarian":
        return _barbarian_levels(build)
    return _sorcerer_levels(build)


def _multiclass_levels(
    build: BuiltinMulticlassBuild,
) -> tuple[ClassLevelEntry, ...]:
    levels: list[ClassLevelEntry] = []
    character_level = 0
    for class_index, class_build in enumerate(build.class_builds):
        for entry in _single_class_levels(class_build):
            character_level += 1
            choices = entry.choices
            if class_index > 0 and entry.resulting_class_level == 1:
                choices = tuple(
                    choice
                    for choice in choices
                    if not isinstance(
                        choice,
                        (
                            ClassSkillChoice,
                            StartingEquipmentPackageChoice,
                        ),
                    )
                )
            levels.append(entry.model_copy(update={
                "character_level": character_level,
                "choices": choices,
            }))
    return tuple(levels)


def _build_shape(
    build: BuiltinCharacterBuild,
) -> tuple[
    AbilityScoreAllocation,
    FlexibleAbilityBonusSelection,
    tuple[ClassLevelEntry, ...],
]:
    if isinstance(build, BuiltinMulticlassBuild):
        return (
            build.base_ability_scores,
            build.flexible_ability_bonuses,
            _multiclass_levels(build),
        )
    if build.class_id == "fighter":
        return (
            AbilityScoreAllocation(
                strength=15,
                dexterity=14,
                constitution=13,
                intelligence=10,
                wisdom=12,
                charisma=8,
            ),
            FlexibleAbilityBonusSelection(
                plus_two=AbilityScoreName.STRENGTH,
                plus_one=AbilityScoreName.CONSTITUTION,
            ),
            _fighter_levels(build),
        )
    if build.class_id == "barbarian":
        return (
            AbilityScoreAllocation(
                strength=15,
                dexterity=13,
                constitution=14,
                intelligence=8,
                wisdom=12,
                charisma=10,
            ),
            FlexibleAbilityBonusSelection(
                plus_two=AbilityScoreName.STRENGTH,
                plus_one=AbilityScoreName.CONSTITUTION,
            ),
            _barbarian_levels(build),
        )
    return (
        AbilityScoreAllocation(
            strength=8,
            dexterity=14,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=15,
        ),
        FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.CHARISMA,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        _sorcerer_levels(build),
    )


def _package_holdings(
    build: BuiltinSingleClassBuild,
) -> tuple[StarterHoldingTemplate, ...]:
    declaration = STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET.get(
        (build.class_id, build.equipment_preset),
    )
    if declaration is None or not isinstance(
        declaration.definition_payload,
        StartingEquipmentPackageDefinition,
    ):
        raise ValueError(
            f"Unknown {build.class_id} equipment preset "
            f"{build.equipment_preset!r}",
        )
    return tuple(
        StarterHoldingTemplate(
            item_id=entry.item_id,
            quantity=entry.quantity,
            equipped_slot=entry.equipped_slot,
        )
        for entry in declaration.definition_payload.entries
    )


_COMMON_CURATED_SUPPLEMENT = (
    StarterHoldingTemplate(item_id="consumable.potion_haste"),
    StarterHoldingTemplate(item_id="consumable.healing_potion", quantity=2),
)
_FIGHTER_CURATED_SUPPLEMENT = (
    StarterHoldingTemplate(
        item_id="apparel.leather_boots.brown",
        equipped_slot=BodyPart.FEET,
    ),
    *_COMMON_CURATED_SUPPLEMENT,
    StarterHoldingTemplate(item_id="apparel.cloth_shoes"),
    StarterHoldingTemplate(
        item_id="apparel.iron_helmet.steel",
        equipped_slot=BodyPart.HEAD,
    ),
    StarterHoldingTemplate(item_id="weapon.handaxe"),
    StarterHoldingTemplate(item_id="weapon.javelin"),
    StarterHoldingTemplate(item_id="weapon.dagger"),
    StarterHoldingTemplate(item_id="armor.leather"),
)
_BARBARIAN_CURATED_SUPPLEMENT = (
    *_COMMON_CURATED_SUPPLEMENT,
    StarterHoldingTemplate(item_id="weapon.handaxe"),
    StarterHoldingTemplate(item_id="weapon.javelin"),
    StarterHoldingTemplate(item_id="weapon.dagger"),
    StarterHoldingTemplate(item_id="weapon.longsword"),
    StarterHoldingTemplate(item_id="shield.shield"),
    )


def _first_class_build(
    build: BuiltinCharacterBuild,
) -> BuiltinSingleClassBuild:
    if isinstance(build, BuiltinMulticlassBuild):
        return build.class_builds[0]
    return build


def _curated_supplement_for_build(
    build: BuiltinSingleClassBuild,
) -> tuple[StarterHoldingTemplate, ...]:
    if build.class_id == "fighter":
        return _FIGHTER_CURATED_SUPPLEMENT
    if build.class_id == "barbarian":
        return _BARBARIAN_CURATED_SUPPLEMENT
    spare_item_id = (
        "weapon.quarterstaff"
        if build.equipment_preset == "dagger"
        else "weapon.dagger"
    )
    return (
        StarterHoldingTemplate(
            item_id="apparel.robes.red_mage",
            equipped_slot=BodyPart.BODY,
        ),
        StarterHoldingTemplate(
            item_id="apparel.cloth_shoes.red",
            equipped_slot=BodyPart.FEET,
        ),
        *_COMMON_CURATED_SUPPLEMENT,
        StarterHoldingTemplate(item_id="apparel.robes.wizard"),
        StarterHoldingTemplate(item_id="apparel.cloth_shoes.blue"),
        StarterHoldingTemplate(
            item_id="apparel.wizard_hat.red",
            equipped_slot=BodyPart.HEAD,
        ),
        StarterHoldingTemplate(item_id=spare_item_id),
    )


def starter_holdings_for_build(
    build: BuiltinCharacterBuild,
) -> tuple[StarterHoldingTemplate, ...]:
    """Return exact durable starter possessions for one built-in build."""
    first_class_build = _first_class_build(build)
    inherited = (
        *_package_holdings(first_class_build),
        *_curated_supplement_for_build(first_class_build),
    )
    explicit_slots = {
        holding.equipped_slot
        for holding in build.additional_holdings
        if holding.equipped_slot is not None
    }
    holdings = (
        *(
            holding.model_copy(update={"equipped_slot": None})
            if holding.equipped_slot in explicit_slots
            else holding
            for holding in inherited
        ),
        *build.additional_holdings,
    )
    return holdings


def supplemental_holdings_for_build(
    build: BuiltinCharacterBuild,
) -> tuple[StarterHoldingTemplate, ...]:
    """Return plan-owned holdings beyond selected class/background packages."""

    first_class_build = _first_class_build(build)
    inherited = _curated_supplement_for_build(first_class_build)
    explicit_slots = {
        holding.equipped_slot
        for holding in build.additional_holdings
        if holding.equipped_slot is not None
    }
    return (
        *(
            holding.model_copy(update={"equipped_slot": None})
            if holding.equipped_slot in explicit_slots
            else holding
            for holding in inherited
        ),
        *build.additional_holdings,
    )


def compose_character_creation_plans() -> tuple[
    CharacterCreationPlan,
    ...,
]:
    """Build the one editable Blank + premade creator roster."""

    blank_template = BuiltinSingleClassBuild(
        class_id="fighter",
        level=1,
        equipment_preset="sword_shield",
        appearance=default_player_character_appearance(),
        fighting_style="defense",
    )
    blank_build, blank_loadout = compose_builtin_character_drafts(
        blank_template,
    )
    blank_build = blank_build.model_copy(update={
        "immutable_origin_choices": tuple(sorted(
            (
                *blank_build.immutable_origin_choices,
                StartingApparelPackageChoice(
                    choice_id=STARTING_APPAREL_CHOICE_ID,
                    selected_ref=(
                        STARTING_APPAREL_PACKAGE_DECLARATIONS_BY_ID[
                            "common_clothes"
                        ].ref
                    ),
                ),
            ),
            key=lambda choice: choice.choice_id,
        )),
    })
    plans = [
        CharacterCreationPlan.create(
            plan_id="creation_plan.blank_custom",
            plan_kind=CharacterCreationPlanKind.BLANK_CUSTOM,
            display_name="Blank Custom",
            build=blank_build,
            loadout=blank_loadout,
            character_level_entitlement=1,
            supplemental_holdings=(
                StarterHoldingTemplate(item_id="equipment.portable_torch"),
            ),
        ),
    ]
    plans.extend(
        CharacterCreationPlan.create(
            plan_id=f"creation_plan.premade.{premade_id}",
            plan_kind=CharacterCreationPlanKind.PREMADE_TEMPLATE,
            display_name=build.display_name or premade_id,
            build=compose_builtin_character_drafts(build)[0],
            loadout=compose_builtin_character_drafts(build)[1],
            character_level_entitlement=build.level,
            supplemental_holdings=supplemental_holdings_for_build(build),
            source_premade_id=premade_id,
        )
        for premade_id, build in sorted(BUILTIN_PREMADE_BUILDS.items())
    )
    return tuple(plans)


def compose_builtin_character_revisions(
    *,
    character_id: UUID,
    build: BuiltinCharacterBuild,
    content_system: LoadedContentSystem,
    ruleset_digest: str = DEFAULT_CHARACTER_RULESET_DIGEST,
) -> BuiltinCharacterRevisions:
    """Create exact revision-one schema-2 records for a built-in build."""

    build_draft, loadout_draft = compose_builtin_character_drafts(build)
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=build_draft.body_recipe,
        species_ref=build_draft.species_ref,
        species_variant_ref=build_draft.species_variant_ref,
        background_ref=build_draft.background_ref,
        immutable_origin_choices=build_draft.immutable_origin_choices,
        appearance=build_draft.appearance,
        base_ability_scores=build_draft.base_ability_scores,
        flexible_ability_bonuses=build_draft.flexible_ability_bonuses,
        class_levels=build_draft.class_levels,
        premade_id=build_draft.premade_id,
        earned_character_level=build.level,
        content_set_digest=content_system.content_set_digest,
        ruleset_digest=ruleset_digest,
    )
    holdings = CharacterHoldingsRevision.create(
        character_id=character_id,
        holdings_revision=1,
        items=tuple(
            sorted(
                (
                    CharacterItemV2.create(
                        character_item_id=uuid5(
                            character_id,
                            (
                                "dnd-engine:builtin-character-holding:v2:"
                                f"{index}:{holding.item_id}:"
                                f"{holding.equipped_slot}"
                            ),
                        ),
                        item_id=holding.item_id,
                        quantity=holding.quantity,
                        equipped_slot=holding.equipped_slot,
                    )
                    for index, holding in enumerate(
                        starter_holdings_for_build(build),
                    )
                ),
                key=lambda item: item.character_item_id.hex,
            ),
        ),
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=definition.definition_revision,
        prepared_spells=loadout_draft.prepared_spells,
        feature_toggles=loadout_draft.feature_toggles,
    )
    return BuiltinCharacterRevisions(
        definition=definition,
        holdings=holdings,
        loadout=loadout,
    )


def compose_builtin_character_drafts(
    build: BuiltinCharacterBuild,
) -> tuple[CharacterBuildDraft, CharacterLoadoutDraft]:
    """Compose the exact UUID/revision-free drafts used by every built-in."""

    base_scores, bonuses, levels = _build_shape(build)
    appearance = build.appearance
    if appearance is None:
        raise ValueError(
            "built-in character fixtures require an explicit appearance",
        )
    return (
        CharacterBuildDraft(
            body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
            species_ref=HUMAN_SPECIES_REF,
            background_ref=ADVENTURER_BACKGROUND_REF,
            immutable_origin_choices=(
                StartingProficiencyChoice(
                    choice_id="species.human.additional_language",
                    proficiencies=(
                        ProficiencySubject(
                            subject_kind=ProficiencySubjectKind.LANGUAGE,
                            subject_id=SrdLanguageId.DRACONIC.value,
                        ),
                    ),
                ),
            ),
            appearance=appearance,
            base_ability_scores=base_scores,
            flexible_ability_bonuses=bonuses,
            class_levels=levels,
            premade_id=build.premade_id,
        ),
        CharacterLoadoutDraft(),
    )


BUILTIN_PREMADE_BUILDS = MappingProxyType({
    "hero.barbarian_l5_berserker_torch": BuiltinSingleClassBuild(
        class_id="barbarian",
        level=5,
        equipment_preset="greataxe",
        appearance=BARBARIAN_HUMAN_APPEARANCE,
        asi_by_level=((4, ((AbilityScoreName.STRENGTH, 2),)),),
        premade_id="hero.barbarian_l5_berserker_torch",
        display_name="Berserker",
        additional_holdings=(
            StarterHoldingTemplate(
                item_id="apparel.costume.pit_fighter_wrap",
                equipped_slot=BodyPart.BODY,
            ),
            StarterHoldingTemplate(
                item_id="apparel.leather_boots",
                equipped_slot=BodyPart.FEET,
            ),
            StarterHoldingTemplate(item_id="equipment.portable_torch"),
        ),
    ),
    "hero.fighter_l5_shield_torch": BuiltinSingleClassBuild(
        class_id="fighter",
        level=5,
        equipment_preset="sword_shield",
        appearance=FIGHTER_HUMAN_APPEARANCE,
        fighting_style="dueling",
        asi_by_level=((4, ((AbilityScoreName.STRENGTH, 2),)),),
        premade_id="hero.fighter_l5_shield_torch",
        display_name="Shield Fighter",
        additional_holdings=(
            StarterHoldingTemplate(
                item_id="weapon.longbow",
                equipped_slot=WeaponSlot.RANGED_MAIN,
            ),
            StarterHoldingTemplate(item_id="equipment.portable_torch"),
        ),
    ),
    "hero.sorcerer_l5_standard_torch": BuiltinSingleClassBuild(
        class_id="sorcerer",
        level=5,
        equipment_preset="dagger",
        appearance=SORCERER_HUMAN_APPEARANCE,
        asi_by_level=((4, ((AbilityScoreName.CHARISMA, 2),)),),
        metamagic_choices=("quickened", "twinned"),
        spell_names=(
            "Fire Bolt",
            "Ray of Frost",
            "Magic Missile",
            "Burning Hands",
            "Scorching Ray",
            "Hold Person",
            "Fireball",
            "Lightning Bolt",
        ),
        premade_id="hero.sorcerer_l5_standard_torch",
        display_name="Draconic Sorcerer",
        additional_holdings=(
            StarterHoldingTemplate(item_id="equipment.portable_torch"),
        ),
    ),
    "hero.fighter_2_sorcerer_3_spellblade": BuiltinMulticlassBuild(
        class_builds=(
            BuiltinSingleClassBuild(
                class_id="fighter",
                level=2,
                equipment_preset="sword_shield",
                fighting_style="dueling",
            ),
            BuiltinSingleClassBuild(
                class_id="sorcerer",
                level=3,
                equipment_preset="dagger",
                metamagic_choices=("quickened", "twinned"),
                spell_names=(
                    "Fire Bolt",
                    "Ray of Frost",
                    "Light",
                    "Shocking Grasp",
                    "Magic Missile",
                    "Shield",
                    "Scorching Ray",
                    "Hold Person",
                ),
            ),
        ),
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=13,
            constitution=13,
            intelligence=8,
            wisdom=9,
            charisma=14,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CHARISMA,
        ),
        appearance=FIGHTER_HUMAN_APPEARANCE,
        premade_id="hero.fighter_2_sorcerer_3_spellblade",
        display_name="Draconic Spellblade",
        additional_holdings=(
            StarterHoldingTemplate(
                item_id="apparel.spellblade_crown",
                equipped_slot=BodyPart.HEAD,
            ),
            StarterHoldingTemplate(item_id="equipment.portable_torch"),
        ),
    ),
})


__all__ = [
    "BUILTIN_PREMADE_BUILDS",
    "DEFAULT_CHARACTER_RULESET_DIGEST",
    "BuiltinCharacterRevisions",
    "BuiltinCharacterBuild",
    "BuiltinMulticlassBuild",
    "BuiltinSingleClassBuild",
    "compose_builtin_character_drafts",
    "compose_character_creation_plans",
    "compose_builtin_character_revisions",
    "starter_holdings_for_build",
    "supplemental_holdings_for_build",
]
