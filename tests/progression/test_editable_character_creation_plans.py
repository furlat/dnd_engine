"""One authenticated editable roster replaces premade/custom split paths."""

from pydantic import ValidationError
import pytest

from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_character_creation_plans,
    starter_holdings_for_build,
    supplemental_holdings_for_build,
)
from dnd.core.content.durable_characters import (
    StartingEquipmentPackageChoice,
)
from dnd.core.content.premade_characters import (
    CharacterCreationPlan,
    CharacterCreationPlanKind,
)
from dnd.items.torches import TORCH_RECIPE
from server.character_directory_contracts import (
    CharacterCreationCatalogResponse,
)


def test_creation_plan_roster_is_one_blank_seed_plus_every_premade() -> None:
    assert "creation_plans" in CharacterCreationCatalogResponse.model_fields
    assert "premades" not in CharacterCreationCatalogResponse.model_fields

    plans = compose_character_creation_plans()

    assert tuple(plan.plan_id for plan in plans) == (
        "creation_plan.blank_custom",
        "creation_plan.premade.hero.barbarian_l5_berserker_torch",
        "creation_plan.premade.hero.fighter_2_sorcerer_3_spellblade",
        "creation_plan.premade.hero.fighter_l5_shield_torch",
        "creation_plan.premade.hero.sorcerer_l5_standard_torch",
    )
    blank = plans[0]
    assert blank.plan_kind is CharacterCreationPlanKind.BLANK_CUSTOM
    assert blank.character_level_entitlement == 1
    assert blank.source_premade_id is None
    assert blank.build.premade_id is None
    assert tuple(
        holding.recipe.recipe_digest
        for holding in blank.supplemental_holdings
    ) == (TORCH_RECIPE.recipe_digest,)
    assert len(blank.build.class_levels) == 1
    assert any(
        choice.choice_id == "character.creation.starting_apparel"
        for choice in blank.build.immutable_origin_choices
    )

    premade_plans = plans[1:]
    assert {
        plan.source_premade_id for plan in premade_plans
    } == set(BUILTIN_PREMADE_BUILDS)
    assert all(
        plan.plan_kind is CharacterCreationPlanKind.PREMADE_TEMPLATE
        and plan.character_level_entitlement == len(plan.build.class_levels)
        == 5
        and plan.build.premade_id == plan.source_premade_id
        for plan in premade_plans
    )


def test_creation_plan_digest_authenticates_level_seed_and_holdings() -> None:
    plan = compose_character_creation_plans()[1]

    with pytest.raises(ValidationError, match="must match its seed build"):
        CharacterCreationPlan.model_validate({
            **plan.model_dump(mode="json"),
            "character_level_entitlement": 4,
        })
    with pytest.raises(ValidationError, match="does not authenticate"):
        CharacterCreationPlan.model_validate({
            **plan.model_dump(mode="json"),
            "build": plan.build.model_copy(update={
                "flexible_ability_bonuses": (
                    plan.build.flexible_ability_bonuses.model_copy(update={
                        "plus_two": (
                            plan.build.flexible_ability_bonuses.plus_one
                        ),
                        "plus_one": (
                            plan.build.flexible_ability_bonuses.plus_two
                        ),
                    })
                ),
            }).model_dump(mode="json"),
        })
    with pytest.raises(ValidationError, match="does not authenticate"):
        CharacterCreationPlan.model_validate({
            **plan.model_dump(mode="json"),
            "supplemental_holdings": [],
        })


def test_editing_premade_clears_identity_without_losing_plan_authority() -> None:
    plan = compose_character_creation_plans()[1]
    source_id = plan.source_premade_id
    assert source_id is not None

    exact = plan.normalize_requested_build(
        build=plan.build,
        loadout=plan.loadout,
    )
    edited = plan.normalize_requested_build(
        build=plan.build.model_copy(update={
            "flexible_ability_bonuses": (
                plan.build.flexible_ability_bonuses.model_copy(update={
                    "plus_two": plan.build.flexible_ability_bonuses.plus_one,
                    "plus_one": plan.build.flexible_ability_bonuses.plus_two,
                })
            ),
        }),
        loadout=plan.loadout,
    )

    assert exact.premade_id == plan.source_premade_id
    assert edited.premade_id is None
    assert plan.supplemental_holdings == supplemental_holdings_for_build(
        BUILTIN_PREMADE_BUILDS[source_id],
    )


def test_premade_plan_separates_selected_class_package_from_supplement() -> None:
    for plan in compose_character_creation_plans()[1:]:
        source_id = plan.source_premade_id
        assert source_id is not None
        build = BUILTIN_PREMADE_BUILDS[source_id]
        full = starter_holdings_for_build(build)
        selected_package_count = sum(
            isinstance(choice, StartingEquipmentPackageChoice)
            for level in plan.build.class_levels
            for choice in level.choices
        )

        assert selected_package_count == 1
        assert len(full) > len(plan.supplemental_holdings)
