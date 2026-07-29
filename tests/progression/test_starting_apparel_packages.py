"""Starting apparel is exact persistent character data, not UI inference."""

from __future__ import annotations

from uuid import uuid4

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_appearance import (
    FIGHTER_HUMAN_APPEARANCE,
)
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_PACKAGE_DECLARATIONS,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    ChoiceRequirementKind,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import BodyPart, VisualLoadoutSlot
from server.character_directory_service import CharacterDirectoryService
from server.character_directory_contracts import (
    CharacterBuildDraft,
    CharacterCreationValidationRequest,
    CharacterLoadoutDraft,
    CreateCharacterRequest,
)
from server.content_catalog import (
    build_public_content_catalog,
    safe_content_presentation_ref,
)
from server.game_directory.contracts import PrincipalCreate, PrincipalKind
from server.game_directory.repository import GameDirectoryRepository


_PEPPER = b"starting-apparel-package-tests"


def test_starting_apparel_catalog_is_exact_and_separate_from_class_gear(
    tmp_path,
) -> None:
    content_system = bootstrap_content_system()
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=_PEPPER,
    )
    catalog = CharacterDirectoryService(
        repository,
        content_system,
    ).build_creation_catalog()
    content_catalog = build_public_content_catalog(content_system)
    content_entries = {
        row.ref: row for row in content_catalog.entries
    }
    preset_rows = {
        row.recipe.recipe_digest: row
        for row in content_catalog.presets
    }
    safe_presentation_hashes = {
        row.ref.presentation_contract_hash
        for row in content_catalog.safe_presentations
    }

    assert catalog.schema_version == 7
    assert tuple(plan.plan_id for plan in catalog.creation_plans) == (
        "creation_plan.blank_custom",
        "creation_plan.premade.hero.barbarian_l5_berserker_torch",
        "creation_plan.premade.hero.fighter_2_sorcerer_3_spellblade",
        "creation_plan.premade.hero.fighter_l5_shield_torch",
        "creation_plan.premade.hero.sorcerer_l5_standard_torch",
    )
    for plan in catalog.creation_plans:
        assert type(plan).model_validate(
            plan.model_dump(mode="json"),
        ) == plan
    assert (
        catalog.starting_apparel_requirement.choice_kind
        is ChoiceRequirementKind.STARTING_APPAREL_PACKAGE
    )
    assert catalog.starting_apparel_requirement.minimum_selections == 1
    assert catalog.starting_apparel_requirement.maximum_selections == 1
    assert len(catalog.starting_equipment_packages) == 9
    assert tuple(
        row.ref for row in catalog.starting_apparel_packages
    ) == catalog.starting_apparel_requirement.allowed_refs

    assert len(STARTING_APPAREL_PACKAGE_DECLARATIONS) >= 4
    for row in catalog.starting_apparel_packages:
        assert (
            row.ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        )
        assert "starting_apparel" in row.descriptor.tags
        definition = content_system.registry.resolve_typed_definition(
            row.ref,
            StartingEquipmentPackageDefinition,
        )
        assert content_entries[row.ref].presentation.icon_key is not None
        assert {
            entry.equipped_slot for entry in definition.entries
        } == {BodyPart.BODY, BodyPart.FEET}
        for entry in definition.entries:
            assert entry.recipe.ref in content_entries
            preset = content_system.registry.find_recipe_preset(
                entry.recipe,
            )
            assert preset is not None
            preset_row = preset_rows[entry.recipe.recipe_digest]
            assert preset_row.ref == preset.ref
            assert preset_row.presentation.icon_key is not None
            assert preset_row.presentation.sprite_key is not None
            assert preset_row.presentation.visual_variant_key is not None
            assert preset_row.presentation.tint_rgb is not None
            assert preset_row.presentation.ui_group is not None
            assert preset_row.presentation.equipment_sprites
            assert (
                safe_content_presentation_ref(
                    preset_row.presentation,
                ).presentation_contract_hash
                in safe_presentation_hashes
            )
        StartingApparelPackageChoice(
            choice_id=catalog.starting_apparel_requirement.choice_id,
            selected_ref=row.ref,
        )

    repository.close()


def test_character_build_visual_preview_uses_production_projection_for_custom_and_premade(
    tmp_path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "preview.sqlite3",
        capability_pepper=_PEPPER,
    )
    owner = repository.create_principal(PrincipalCreate(
        principal_kind=PrincipalKind.HUMAN,
        display_name="Owner",
    ))
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    blank_plan = service.build_creation_catalog().creation_plans[0]
    request = CharacterCreationValidationRequest(
        build=_fighter_build(service, with_apparel=True),
        loadout=CharacterLoadoutDraft(),
        creation_plan_id=blank_plan.plan_id,
        creation_plan_digest=blank_plan.plan_digest,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
    )

    custom = service.build_character_visual_preview(
        owner.principal_id,
        request,
    )
    assert custom.schema_version == 1
    assert custom.normalized_build == request.build
    assert custom.normalized_loadout == request.loadout
    assert custom.content_set_digest == request.expected_content_set_digest
    assert custom.ruleset_digest == request.expected_ruleset_digest
    assert custom.entity.uuid == custom.visual_loadout.entity_uuid
    assert custom.entity.content_ref.model_dump(mode="json") == (
        request.build.body_recipe.ref.model_dump(mode="json")
    )
    assert {
        row.slot for row in custom.visual_loadout.layers
    } >= {VisualLoadoutSlot.BODY_ARMOR, VisualLoadoutSlot.BOOTS}

    premade = service.build_creation_catalog().creation_plans[1]
    premade_preview = service.build_character_visual_preview(
        owner.principal_id,
        request.model_copy(update={
            "build": premade.build,
            "loadout": premade.loadout,
            "creation_plan_id": premade.plan_id,
            "creation_plan_digest": premade.plan_digest,
        }),
    )
    assert premade_preview.normalized_build == premade.build
    assert premade_preview.normalized_loadout == premade.loadout
    assert (
        premade_preview.entity.uuid
        == premade_preview.visual_loadout.entity_uuid
    )
    assert premade_preview.visual_loadout.layers
    repository.close()


def _fighter_build(
    service: CharacterDirectoryService,
    *,
    with_apparel: bool,
) -> CharacterBuildDraft:
    catalog = service.build_creation_catalog()
    fighter = next(
        row
        for row in catalog.classes
        if row.ref.content_id == "class.fighter"
    )
    package_requirement = next(
        row
        for row in fighter.definition.first_class_proficiencies.choices
        if row.choice_kind
        is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
    )
    skill_requirement = next(
        row
        for row in fighter.definition.first_class_proficiencies.choices
        if row.choice_kind is ChoiceRequirementKind.CLASS_SKILL
    )
    style_requirement = next(
        row
        for row in fighter.definition.level_definitions[0].choice_requirements
        if row.choice_kind is ChoiceRequirementKind.FIGHTING_STYLE
    )
    fixed_origin_choices = tuple(
        choice
        for choice in catalog.creation_plans[0].build.immutable_origin_choices
        if not isinstance(choice, StartingApparelPackageChoice)
    )
    apparel_choices = (
        (
            StartingApparelPackageChoice(
                choice_id=catalog.starting_apparel_requirement.choice_id,
                selected_ref=next(
                    row.ref
                    for row in catalog.starting_apparel_packages
                    if row.ref.content_id
                    == "starting_apparel.common_clothes"
                ),
            ),
        )
        if with_apparel
        else ()
    )
    return CharacterBuildDraft(
        body_recipe=catalog.body_recipes[0],
        species_ref=next(
            row.ref
            for row in catalog.species
            if row.ref.content_id == "species.human"
        ),
        background_ref=next(
            row.ref
            for row in catalog.backgrounds
            if row.ref.content_id == "background.adventurer"
        ),
        immutable_origin_choices=tuple(sorted(
            (*fixed_origin_choices, *apparel_choices),
            key=lambda choice: choice.choice_id,
        )),
        appearance=FIGHTER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=fighter.ref,
                resulting_class_level=1,
                choices=tuple(sorted(
                    (
                        ClassSkillChoice(
                            choice_id=skill_requirement.choice_id,
                            skills=("athletics", "perception"),
                        ),
                        FightingStyleChoice(
                            choice_id=style_requirement.choice_id,
                            selected_ref=style_requirement.allowed_refs[0],
                        ),
                        StartingEquipmentPackageChoice(
                            choice_id=package_requirement.choice_id,
                            selected_ref=next(
                                ref
                                for ref in package_requirement.allowed_refs
                                if ref.content_id
                                == "starting_equipment.fighter.sword_shield"
                            ),
                        ),
                    ),
                    key=lambda choice: choice.choice_id,
                )),
            ),
        ),
    )


def test_custom_creation_requires_and_persists_exact_apparel_without_replacing_armor(
    tmp_path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "creation.sqlite3",
        capability_pepper=_PEPPER,
    )
    owner = repository.create_principal(PrincipalCreate(
        principal_kind=PrincipalKind.HUMAN,
        display_name="Owner",
    ))
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    settings = service.ensure_profile_settings(owner.principal_id)
    blank_plan = service.build_creation_catalog().creation_plans[0]

    missing = service.validate_new_character(
        owner.principal_id,
        CreateCharacterRequest(
            display_name="Missing Clothes",
            build=_fighter_build(service, with_apparel=False),
            loadout=CharacterLoadoutDraft(),
            expected_content_set_digest=(
                service.content_system.content_set_digest
            ),
            expected_ruleset_digest=settings.ruleset_digest,
            creation_plan_id=blank_plan.plan_id,
            creation_plan_digest=blank_plan.plan_digest,
            idempotency_key=uuid4(),
        ),
    )
    assert "initial_apparel_selection_required" in {
        issue.code.value for issue in missing.issues
    }

    request = CreateCharacterRequest(
        display_name="Dressed Fighter",
        build=_fighter_build(service, with_apparel=True),
        loadout=CharacterLoadoutDraft(),
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        creation_plan_id=blank_plan.plan_id,
        creation_plan_digest=blank_plan.plan_digest,
        idempotency_key=uuid4(),
    )
    validated = service.validate_new_character(owner.principal_id, request)
    assert validated.valid, validated.issues
    created = service.create_character(owner.principal_id, request)

    stored_choice = next(
        choice
        for choice in created.definition.definition.immutable_origin_choices
        if isinstance(choice, StartingApparelPackageChoice)
    )
    assert (
        stored_choice.selected_ref.content_id
        == "starting_apparel.common_clothes"
    )
    body_items = tuple(
        item
        for item in created.holdings.holdings.items
        if item.recipe.ref.content_id
        in {"armor.chain_mail", "apparel.common_clothes"}
    )
    assert len(body_items) == 2
    assert {
        item.recipe.ref.content_id: item.equipped_slot
        for item in body_items
    } == {
        "armor.chain_mail": BodyPart.BODY,
        "apparel.common_clothes": None,
    }
    shoes = next(
        item
        for item in created.holdings.holdings.items
        if item.recipe.ref.content_id == "apparel.leather_shoes"
    )
    assert shoes.equipped_slot is BodyPart.FEET
    repository.close()
