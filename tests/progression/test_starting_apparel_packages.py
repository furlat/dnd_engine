"""Starting apparel is exact authored character data, not UI inference."""

from __future__ import annotations

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    compose_character_creation_plans,
)
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_CHOICE_ID,
    STARTING_APPAREL_PACKAGE_DECLARATIONS,
)
from dnd.core.content.durable_characters import StartingApparelPackageChoice
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import BodyPart
from server.content_catalog import build_public_content_catalog


def test_starting_apparel_catalog_is_exact_and_separate_from_class_gear() -> None:
    content_system = bootstrap_content_system()
    public_catalog = build_public_content_catalog(content_system)
    public_refs = {row.ref for row in public_catalog.entries}

    assert len(STARTING_APPAREL_PACKAGE_DECLARATIONS) >= 4
    for declaration in STARTING_APPAREL_PACKAGE_DECLARATIONS:
        assert declaration.ref in public_refs
        assert (
            declaration.ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        )
        assert "starting_apparel" in declaration.descriptor.tags
        definition = content_system.registry.resolve_typed_definition(
            declaration.ref,
            StartingEquipmentPackageDefinition,
        )
        assert {
            entry.equipped_slot for entry in definition.entries
        } == {BodyPart.BODY, BodyPart.FEET}
        assert all(entry.recipe.ref in public_refs for entry in definition.entries)


def test_character_creation_plan_apparel_choices_are_exact() -> None:
    plans = compose_character_creation_plans()
    allowed_refs = {
        row.ref for row in STARTING_APPAREL_PACKAGE_DECLARATIONS
    }
    choices = tuple(
        tuple(
            choice
            for choice in plan.build.immutable_origin_choices
            if isinstance(choice, StartingApparelPackageChoice)
        )
        for plan in plans
    )

    assert len(choices[0]) == 1
    assert all(len(apparel) <= 1 for apparel in choices)
    assert all(
        choice.choice_id == STARTING_APPAREL_CHOICE_ID
        and choice.selected_ref in allowed_refs
        for apparel in choices
        for choice in apparel
    )
