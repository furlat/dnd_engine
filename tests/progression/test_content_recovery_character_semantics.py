"""Rescued in-process character-authoring semantics for the CR-0 freeze."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_CLASS_DEFINITION,
)
from dnd.classes.progression_definitions import FIGHTER_CLASS_DEFINITION
from dnd.classes.sorcerer_progression_definitions import (
    SORCERER_CLASS_DEFINITION,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content.items.authored_item_builders import DIRECT_ITEM_BUILDERS
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_revisions,
    compose_character_creation_plans,
    starter_holdings_for_build,
)
from dnd.content_system.character_appearance import (
    BARBARIAN_HUMAN_APPEARANCE,
    FIGHTER_HUMAN_APPEARANCE,
    PLAYER_CHARACTER_APPEARANCE_OPTIONS,
    SORCERER_HUMAN_APPEARANCE,
    default_player_character_appearance,
    migrate_player_character_appearance,
    resolve_player_character_appearance,
)
from dnd.content_system.character_origin_definitions import HUMAN_SPECIES_REF
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_CHOICE_ID,
    STARTING_APPAREL_PACKAGE_DECLARATIONS,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
)
from dnd.core.content.durable_characters import (
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
    ChoiceRequirementKind,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import BodyPart
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE


EXPECTED_APPEARANCE_DEFAULTS = (
    ("appearance.beard", "appearance.beard.absent"),
    ("appearance.beard_tint", "appearance.beard_tint.follow_hair"),
    ("appearance.body", "appearance.body.humanoid"),
    ("appearance.build", "appearance.build.average"),
    ("appearance.hair_tint", "appearance.color.auburn"),
    ("appearance.head", "appearance.head.hair_09"),
    ("appearance.skin_tint", "appearance.color.light_tan"),
    ("appearance.stature", "appearance.stature.average"),
)
EXPECTED_APPAREL_IDS = (
    "starting_apparel.common_clothes",
    "starting_apparel.travelers_clothes",
    "starting_apparel.fine_clothes",
    "starting_apparel.robes",
)
EXPECTED_EQUIPMENT_IDS = (
    "starting_equipment.fighter.sword_shield",
    "starting_equipment.fighter.greatsword",
    "starting_equipment.fighter.dual_wield",
    "starting_equipment.fighter.archery",
    "starting_equipment.barbarian.greataxe",
    "starting_equipment.barbarian.dual_axes",
    "starting_equipment.barbarian.sword_shield",
    "starting_equipment.sorcerer.dagger",
    "starting_equipment.sorcerer.quarterstaff",
)


def _starting_equipment_requirement(class_definition):
    return next(
        requirement
        for requirement in class_definition.first_class_proficiencies.choices
        if requirement.choice_kind
        is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
    )


def test_character_appearance_options_and_builtin_selections_are_closed() -> None:
    """The exact creator vocabulary validates and resolves every owned fact."""
    option_defaults = tuple(
        (option.option_id, option.default_value_id)
        for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
    )
    value_ids_by_option = {
        option.option_id: tuple(value.value_id for value in option.values)
        for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
    }

    assert option_defaults == EXPECTED_APPEARANCE_DEFAULTS
    assert len(value_ids_by_option["appearance.hair_tint"]) == 20
    assert len(value_ids_by_option["appearance.skin_tint"]) == 20
    assert len(value_ids_by_option["appearance.beard_tint"]) == 21
    assert value_ids_by_option["appearance.beard_tint"] == (
        "appearance.beard_tint.follow_hair",
        *value_ids_by_option["appearance.hair_tint"],
    )
    options_by_id = {
        option.option_id: option
        for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
    }
    follow_hair = options_by_id["appearance.beard_tint"].values[0]
    assert follow_hair.tint_rgb is None
    assert follow_hair.tint_source_option_id == "appearance.hair_tint"
    for value in (
        *options_by_id["appearance.hair_tint"].values,
        *options_by_id["appearance.skin_tint"].values,
        *options_by_id["appearance.beard_tint"].values[1:],
    ):
        assert value.tint_rgb is not None
        assert value.tint_source_option_id is None
    default_selection = default_player_character_appearance()
    assert tuple(
        (row.option_id, row.value_id) for row in default_selection.options
    ) == EXPECTED_APPEARANCE_DEFAULTS

    appearances = (
        default_selection,
        BARBARIAN_HUMAN_APPEARANCE,
        FIGHTER_HUMAN_APPEARANCE,
        SORCERER_HUMAN_APPEARANCE,
        *(build.appearance for build in BUILTIN_PREMADE_BUILDS.values()),
    )
    allowed_values = {
        option_id: set(value_ids)
        for option_id, value_ids in value_ids_by_option.items()
    }
    for selection in appearances:
        assert tuple(row.option_id for row in selection.options) == tuple(
            option_id for option_id, _default in EXPECTED_APPEARANCE_DEFAULTS
        )
        assert all(
            row.value_id in allowed_values[row.option_id]
            for row in selection.options
        )
        resolved = resolve_player_character_appearance(
            body_ref=PLAYER_CHARACTER_BODY_RECIPE.ref,
            species_ref=HUMAN_SPECIES_REF,
            selection=selection,
        )
        assert resolved.body_category == "NakedBody"

    def selection_with(
        replacements: dict[str, str],
    ) -> CharacterAppearanceSelection:
        return CharacterAppearanceSelection(
            options=tuple(
                CharacterAppearanceOptionSelection(
                    option_id=row.option_id,
                    value_id=replacements.get(row.option_id, row.value_id),
                )
                for row in default_selection.options
            ),
        )

    def resolve(selection: CharacterAppearanceSelection):
        return resolve_player_character_appearance(
            body_ref=PLAYER_CHARACTER_BODY_RECIPE.ref,
            species_ref=HUMAN_SPECIES_REF,
            selection=selection,
        )

    following = selection_with({
        "appearance.beard": "appearance.beard.present",
        "appearance.beard_tint": "appearance.beard_tint.follow_hair",
        "appearance.hair_tint": "appearance.color.copper",
    })
    explicit = selection_with({
        "appearance.beard": "appearance.beard.present",
        "appearance.beard_tint": "appearance.color.silver",
        "appearance.hair_tint": "appearance.color.copper",
    })
    assert resolve(following).hair_tint == 0xB65C36
    assert resolve(following).beard_tint == 0xB65C36
    assert resolve(explicit).hair_tint == 0xB65C36
    assert resolve(explicit).beard_tint == 0xB8BCC4

    absent = selection_with({
        "appearance.beard": "appearance.beard.absent",
        "appearance.beard_tint": "appearance.beard_tint.follow_hair",
        "appearance.hair_tint": "appearance.color.copper",
    })
    assert next(
        row.value_id
        for row in absent.options
        if row.option_id == "appearance.beard_tint"
    ) == "appearance.beard_tint.follow_hair"
    assert resolve(absent).has_beard is False
    assert resolve(absent).beard_tint == 0

    for value_id, expected in (
        ("appearance.head.hair_01", "Head1"),
        ("appearance.head.hair_09", "Head9"),
        ("appearance.head.hair_10", "Head10"),
        ("appearance.head.hair_16", "Head16"),
        ("appearance.head.hair_17", "Head17"),
        ("appearance.head.hair_22", "Head22"),
    ):
        assert resolve(selection_with({
            "appearance.head": value_id,
        })).head_category == expected

    for value_id, expected in (
        ("appearance.build.slender", 0.9),
        ("appearance.build.average", 1.0),
        ("appearance.build.broad", 1.1),
    ):
        resolved = resolve(selection_with({"appearance.build": value_id}))
        assert resolved.visual_scale_x == expected
        assert resolved.visual_scale == 1.0

    for value_id, expected in (
        ("appearance.stature.short", 0.9),
        ("appearance.stature.average", 1.0),
        ("appearance.stature.tall", 1.1),
    ):
        resolved = resolve(selection_with({"appearance.stature": value_id}))
        assert resolved.visual_scale == expected
        assert resolved.visual_scale_x == 1.0

    retired = CharacterAppearanceSelection(
        options=tuple(
            row
            for row in default_selection.options
            if row.option_id not in {"appearance.build", "appearance.stature"}
        ),
    )
    with pytest.raises(ValueError, match="exact ordered options"):
        resolve(retired)
    migration = migrate_player_character_appearance(retired)
    assert tuple(
        (row.option_id, row.value_id)
        for row in migration.added_options
    ) == (
        ("appearance.build", "appearance.build.average"),
        ("appearance.stature", "appearance.stature.average"),
    )
    assert resolve(migration.selection).visual_scale == 1.0
    assert resolve(migration.selection).visual_scale_x == 1.0

    partial = CharacterAppearanceSelection(
        options=tuple(
            row
            for row in default_selection.options
            if row.option_id != "appearance.build"
        ),
    )
    with pytest.raises(ValueError, match="exact ordered options"):
        resolve(partial)
    with pytest.raises(ValueError, match="unknown human player appearance value"):
        resolve(selection_with({"appearance.build": "appearance.build.massive"}))


def test_starting_apparel_catalog_is_exact() -> None:
    """Four authored apparel packages resolve to direct body/feet items."""
    loaded = bootstrap_content_system()
    declarations = STARTING_APPAREL_PACKAGE_DECLARATIONS

    assert tuple(row.ref.content_id for row in declarations) == (
        EXPECTED_APPAREL_IDS
    )
    for declaration in declarations:
        assert (
            declaration.ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        )
        assert "starting_apparel" in declaration.descriptor.tags
        definition = loaded.registry.resolve_typed_definition(
            declaration.ref,
            StartingEquipmentPackageDefinition,
        )
        assert definition is declaration.definition_payload
        assert tuple(entry.equipped_slot for entry in definition.entries) == (
            BodyPart.BODY,
            BodyPart.FEET,
        )
        for entry in definition.entries:
            assert entry.item_id in DIRECT_ITEM_BUILDERS

    allowed_refs = {row.ref for row in declarations}
    apparel_choices = tuple(
        tuple(
            choice
            for choice in plan.build.immutable_origin_choices
            if isinstance(choice, StartingApparelPackageChoice)
        )
        for plan in compose_character_creation_plans()
    )
    assert len(apparel_choices[0]) == 1
    assert all(len(choices) <= 1 for choices in apparel_choices)
    assert all(
        choice.choice_id == STARTING_APPAREL_CHOICE_ID
        and choice.selected_ref in allowed_refs
        for choices in apparel_choices
        for choice in choices
    )


def test_starting_equipment_packages_are_exact() -> None:
    """All nine class packages hold direct items and exact choices."""
    loaded = bootstrap_content_system()
    declarations = STARTING_EQUIPMENT_PACKAGE_DECLARATIONS

    assert tuple(row.ref.content_id for row in declarations) == (
        EXPECTED_EQUIPMENT_IDS
    )
    declaration_refs = {row.ref for row in declarations}
    for declaration in declarations:
        definition = loaded.registry.resolve_typed_definition(
            declaration.ref,
            StartingEquipmentPackageDefinition,
        )
        assert definition is declaration.definition_payload
        assert definition.entries
        assert all(
            entry.item_id in DIRECT_ITEM_BUILDERS
            for entry in definition.entries
        )

    expected_classes = (
        (FIGHTER_CLASS_DEFINITION, 4, "fighter"),
        (BARBARIAN_CLASS_DEFINITION, 3, "barbarian"),
        (SORCERER_CLASS_DEFINITION, 2, "sorcerer"),
    )
    selected_refs = set()
    for class_definition, expected_count, class_id in expected_classes:
        requirement = _starting_equipment_requirement(class_definition)
        assert requirement.choice_id == (
            f"class.{class_id}.first_class.starting_equipment"
        )
        assert requirement.minimum_selections == 1
        assert requirement.maximum_selections == 1
        assert len(requirement.allowed_refs) == expected_count
        assert set(requirement.allowed_refs) <= declaration_refs
        assert not any(
            level_requirement.choice_kind
            is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
            for level in class_definition.level_definitions
            for level_requirement in level.choice_requirements
        )
        assert not any(
            multiclass_requirement.choice_kind
            is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
            for multiclass_requirement in (
                class_definition.multiclass_proficiencies.choices
            )
        )
        selected_refs.update(requirement.allowed_refs)
    assert selected_refs == declaration_refs

    for premade_id, build in BUILTIN_PREMADE_BUILDS.items():
        revisions = compose_builtin_character_revisions(
            character_id=uuid4(),
            build=build,
            content_system=loaded,
        )
        first_level = revisions.definition.class_levels[0]
        package_choices = tuple(
            choice
            for choice in first_level.choices
            if isinstance(choice, StartingEquipmentPackageChoice)
        )
        assert len(package_choices) == 1, premade_id
        package = loaded.registry.resolve_typed_definition(
            package_choices[0].selected_ref,
            StartingEquipmentPackageDefinition,
        )
        expected_templates = starter_holdings_for_build(build)
        actual = tuple(sorted(
            (item.item_id, item.quantity, item.equipped_slot)
            for item in revisions.holdings.items
        ))
        expected = tuple(sorted(
            (row.item_id, row.quantity, row.equipped_slot)
            for row in expected_templates
        ))
        assert actual == expected, premade_id
        package_rows = {
            (row.item_id, row.quantity, row.equipped_slot)
            for row in package.entries
        }
        assert package_rows <= set(actual), premade_id
