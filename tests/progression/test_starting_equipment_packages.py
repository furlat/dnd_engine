"""Starting equipment is exact authored character content, not a primitive tag."""

from __future__ import annotations

from uuid import uuid4

from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_CLASS_DEFINITION,
)
from dnd.classes.progression_definitions import FIGHTER_CLASS_DEFINITION
from dnd.classes.sorcerer_progression_definitions import (
    SORCERER_CLASS_DEFINITION,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_revisions,
    starter_holdings_for_build,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
)
from dnd.core.content.durable_characters import (
    ChoiceRequirementKind,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)


def _package_requirement(class_definition):
    return next(
        requirement
        for requirement in class_definition.first_class_proficiencies.choices
        if requirement.choice_id.endswith(".starting_equipment")
    )


def _package_for_ref(content_system, package_ref):
    return content_system.registry.resolve_typed_definition(
        package_ref,
        StartingEquipmentPackageDefinition,
    )


def test_builtin_starting_equipment_packages_are_exact_typed_item_recipes() -> None:
    content_system = bootstrap_content_system()

    assert len(STARTING_EQUIPMENT_PACKAGE_DECLARATIONS) == 9
    for declaration in STARTING_EQUIPMENT_PACKAGE_DECLARATIONS:
        assert (
            declaration.ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        )
        package = _package_for_ref(content_system, declaration.ref)
        assert package.entries
        assert all(
            entry.recipe.ref.definition_kind is ContentDefinitionKind.ITEM
            for entry in package.entries
        )


def test_existing_classes_require_one_first_class_creation_package_only() -> None:
    expected_counts = (
        ("fighter", FIGHTER_CLASS_DEFINITION, 4),
        ("barbarian", BARBARIAN_CLASS_DEFINITION, 3),
        ("sorcerer", SORCERER_CLASS_DEFINITION, 2),
    )
    for class_id, class_definition, package_count in expected_counts:
        requirement = _package_requirement(class_definition)
        assert requirement.choice_id == (
            f"class.{class_id}.first_class.starting_equipment"
        )
        assert requirement.minimum_selections == 1
        assert requirement.maximum_selections == 1
        assert len(requirement.allowed_refs) == package_count
        assert all(
            ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
            for ref in requirement.allowed_refs
        )
        assert not any(
            requirement.choice_kind
            is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
            for level in class_definition.level_definitions
            for requirement in level.choice_requirements
        )
        assert not any(
            requirement.choice_kind
            is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
            for requirement in (
                class_definition.multiclass_proficiencies.choices
            )
        )


def test_builtin_premades_select_a_package_without_losing_curated_holdings() -> None:
    content_system = bootstrap_content_system()

    for premade_id, build in BUILTIN_PREMADE_BUILDS.items():
        character_id = uuid4()
        revisions = compose_builtin_character_revisions(
            character_id=character_id,
            build=build,
            content_system=content_system,
        )
        first_level = revisions.definition.class_levels[0]
        package_choice = next(
            choice
            for choice in first_level.choices
            if isinstance(choice, StartingEquipmentPackageChoice)
        )
        package = _package_for_ref(content_system, package_choice.selected_ref)
        expected_templates = starter_holdings_for_build(build)
        actual = tuple(
            sorted(
                (
                    item.recipe.recipe_digest,
                    item.quantity,
                    item.equipped_slot,
                )
                for item in revisions.holdings.items
            )
        )
        expected = tuple(
            sorted(
                (
                    row.recipe.recipe_digest,
                    row.quantity,
                    row.equipped_slot,
                )
                for row in expected_templates
            )
        )
        assert actual == expected, premade_id
        package_rows = {
            (row.recipe.recipe_digest, row.quantity, row.equipped_slot)
            for row in package.entries
        }
        assert package_rows <= set(actual)
