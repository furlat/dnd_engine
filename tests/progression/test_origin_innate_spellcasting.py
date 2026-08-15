"""Exact origin-owned innate spellcasting contracts and runtime lifecycle."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
    BUILT_IN_RECIPE_PRESET_INVENTORY,
)
from dnd.content_system.character_appearance import FIGHTER_HUMAN_APPEARANCE
from dnd.content_system.character_build_validation import (
    CharacterBuildPreview,
    CharacterBuildValidator,
    OriginInnateSpellGrantPreview,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_origin_definitions import (
    ADVENTURER_BACKGROUND_REF,
    HIGH_ELF_VARIANT_DECLARATION,
    TIEFLING_SPECIES_DECLARATION,
)
from dnd.content_system.fighter_character_grant_appliers import (
    FIGHTING_STYLE_ARCHERY_REF,
)
from dnd.content_system import origin_innate_spellcasting
from dnd.content_system.origin_innate_spellcasting import (
    innate_spell_resource_name,
    install_origin_innate_spellcasting,
)
from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_ID,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    OriginInnateSpellGrant,
    OriginInnateSpellcastingDefinition,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellcastingSourceId,
    StartingEquipmentPackageChoice,
)
from dnd.types.abilities import AbilityName
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.dice import fixed_dice_faces
from dnd.types.damage import DamageType
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.core.modifiers import NumericalModifier
from dnd.actions.standard import (
    SpellAction,
)
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.entity import Entity, EntityConfig
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _spell_ref(content_id: str) -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.SPELL,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def test_origin_innate_spell_contract_closes_fixed_and_chosen_grants() -> None:
    fire_bolt = _spell_ref("spell.fire_bolt")
    definition = OriginInnateSpellcastingDefinition(
        source_id=SpellcastingSourceId(
            value="species_variant.high_elf.innate_spellcasting",
        ),
        ability=AbilityName.INTELLIGENCE,
        grants=(
            OriginInnateSpellGrant(
                grant_id="high_elf.wizard_cantrip",
                unlock_character_level=1,
                choice_id="species_variant.high_elf.wizard_cantrip",
                allowed_spell_refs=(fire_bolt,),
                fixed_cast_rank=0,
                uses_per_long_rest=None,
            ),
        ),
    )

    assert definition.grants[0].choice_id == (
        "species_variant.high_elf.wizard_cantrip"
    )
    assert definition.grants[0].spell_ref is None
    assert definition.grants[0].allowed_spell_refs == (fire_bolt,)

    with pytest.raises(
        ValidationError,
        match="exactly one fixed spell or choice-backed spell set",
    ):
        OriginInnateSpellGrant(
            grant_id="invalid.both",
            unlock_character_level=1,
            spell_ref=fire_bolt,
            choice_id="invalid.choice",
            allowed_spell_refs=(fire_bolt,),
            fixed_cast_rank=0,
            uses_per_long_rest=None,
        )

    with pytest.raises(ValidationError, match="leveled innate spell"):
        OriginInnateSpellGrant(
            grant_id="invalid.unlimited",
            unlock_character_level=1,
            spell_ref=_spell_ref("spell.darkness"),
            fixed_cast_rank=2,
            uses_per_long_rest=None,
        )


def test_origin_innate_spell_runtime_source_is_not_a_class_source() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    source_id = UUID("22222222-2222-2222-2222-222222222222")
    provider_ref = ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.SPECIES,
        content_id="species.tiefling",
        content_version=2,
        definition_contract_hash="b" * 64,
    )

    entity.spellcasting.add_innate_source(
        source_id,
        "charisma",
        provider_ref=provider_ref,
        provider_level=5,
        maximum_spell_rank=2,
    )

    source = entity.spellcasting.sources[source_id]
    assert source.source_kind == "innate"
    assert source.provider_ref == provider_ref
    assert entity.spellcasting.resolve_spellcasting_ability(
        source_id,
    ) == "charisma"
    assert entity.spellcasting.remove_source(source_id)


def _loaded_builtin() -> LoadedContentSystem:
    return LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations={
                declaration.ref.identity_key: declaration
                for declaration in BUILT_IN_DECLARATION_INVENTORY
            },
            recipe_presets={
                preset.ref.identity_key: preset
                for preset in BUILT_IN_RECIPE_PRESET_INVENTORY
            },
            sources={},
        ),
        built_in_artifact_digest="c" * 64,
        content_set_digest="d" * 64,
    )


def _fighter_level_one_definition(
    *,
    character_id: UUID,
    species_ref: ContentRef,
    species_variant_ref: ContentRef | None = None,
    immutable_origin_choices: tuple[CantripChoice, ...] = (),
    earned_character_level: int = 1,
) -> CharacterDefinitionRevisionV2:
    return CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=species_ref,
        species_variant_ref=species_variant_ref,
        background_ref=ADVENTURER_BACKGROUND_REF,
        immutable_origin_choices=immutable_origin_choices,
        appearance=FIGHTER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=8,
            charisma=13,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityName.STRENGTH,
            plus_one=AbilityName.CHARISMA,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=1,
                choices=(
                    StartingEquipmentPackageChoice(
                        choice_id=(
                            "class.fighter.first_class.starting_equipment"
                        ),
                        selected_ref=(
                            STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                                ("fighter", "sword_shield")
                            ].ref
                        ),
                    ),
                    FightingStyleChoice(
                        choice_id="class.fighter.level_1.fighting_style",
                        selected_ref=FIGHTING_STYLE_ARCHERY_REF,
                    ),
                    ClassSkillChoice(
                        choice_id="class.fighter.proficiencies.skills",
                        skills=("athletics", "perception"),
                    ),
                ),
            ),
        ),
        earned_character_level=earned_character_level,
        content_set_digest="d" * 64,
        ruleset_digest="e" * 64,
    )


def test_tiefling_level_one_validates_materializes_and_removes_thaumaturgy(
) -> None:
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    character_id = uuid4()
    definition = _fighter_level_one_definition(
        character_id=character_id,
        species_ref=TIEFLING_SPECIES_DECLARATION.ref,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
    )

    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=definition.ruleset_digest,
    ).validate(definition, loadout)

    assert validation.valid, validation.issues
    assert validation.preview is not None
    assert [
        (
            row.spell_ref.content_id,
            row.fixed_cast_rank,
            row.spellcasting_ability,
            row.uses_per_long_rest,
        )
        for row in validation.preview.origin_innate_spells
    ] == [
        (
            "spell.thaumaturgy",
            0,
            AbilityName.CHARISMA,
            None,
        ),
    ]

    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Tiefling Fighter",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.tiefling.innate_spellcasting",
        ),
        expected_ruleset_digest=definition.ruleset_digest,
        runtime=runtime,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None
    action = entity.get_action_template("Thaumaturgy")
    assert isinstance(action, SpellAction)
    assert action.spellcasting_source_id is not None
    source = entity.spellcasting.sources[action.spellcasting_source_id]
    assert source.source_kind == "innate"
    assert source.provider_ref == TIEFLING_SPECIES_DECLARATION.ref
    assert source.ability == "charisma"

    remove_character_composition(entity, receipt)

    assert entity.get_action_template("Thaumaturgy") is None
    assert entity.spellcasting.sources == {}


def test_tiefling_level_five_installs_fixed_rank_uses_and_recovers_them(
) -> None:
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    entity = Entity.create(
        source_entity_uuid=uuid4(),
    )
    tiefling_definition = TIEFLING_SPECIES_DECLARATION.definition_payload
    assert isinstance(tiefling_definition, SpeciesDefinition)
    source_definition = tiefling_definition.innate_spellcasting[0]
    rows_by_id = {
        row.grant_id: row for row in source_definition.grants
    }
    preview_rows = tuple(
        OriginInnateSpellGrantPreview(
            grant_id=grant.grant_id,
            spell_ref=grant.spell_ref,
            provider_ref=TIEFLING_SPECIES_DECLARATION.ref,
            spellcasting_source_id=source_definition.source_id,
            spellcasting_ability=source_definition.ability,
            provider_level=5,
            fixed_cast_rank=grant.fixed_cast_rank,
            uses_per_long_rest=grant.uses_per_long_rest,
            grant_token=f"tiefling:{grant.grant_id}",
        )
        for grant in source_definition.grants
        if grant.spell_ref is not None
    )
    context = BuiltinCharacterGrantContext(
        entity=entity,
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(),
            grant_schedule=(),
            final_known_spell_refs=tuple(
                row.spell_ref for row in preview_rows
            ),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
            origin_innate_spells=preview_rows,
        ),
        runtime=runtime,
    )
    receipts = install_origin_innate_spellcasting(context)

    darkness = entity.get_action_template("Darkness")
    assert isinstance(darkness, SpellAction)
    assert darkness.cast_at_level == 2
    assert darkness.alt_skip_slot
    assert entity.get_action_template("Thaumaturgy") is not None
    hellish = next(
        row
        for row in preview_rows
        if row.grant_id == "tiefling.infernal_legacy.hellish_rebuke"
    )
    darkness_row = next(
        row
        for row in preview_rows
        if row.grant_id == "tiefling.infernal_legacy.darkness"
    )
    hellish_resource = innate_spell_resource_name(hellish)
    darkness_resource = innate_spell_resource_name(darkness_row)
    assert entity.action_economy.get_resource_current(hellish_resource) == 1
    assert entity.action_economy.get_resource_current(darkness_resource) == 1
    assert (
        SPELL_CATALOG_COMPOSITION_BY_ID["hellish_rebuke"].declaration.ref
        == rows_by_id[
            "tiefling.infernal_legacy.hellish_rebuke"
        ].spell_ref
    )

    assert entity.action_economy.consume_resource(darkness_resource, 1)
    entity.on_long_rest()
    assert entity.action_economy.get_resource_current(darkness_resource) == 1

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=context.character_id,
            grants=receipts,
        ),
    )
    assert entity.get_action_template("Darkness") is None
    assert entity.get_action_template("Thaumaturgy") is None
    assert entity.spellcasting.sources == {}
    assert hellish_resource not in entity.action_economy.resources
    assert darkness_resource not in entity.action_economy.resources


def _tiefling_innate_failure_context() -> tuple[
    BuiltinCharacterGrantContext,
    tuple[OriginInnateSpellGrantPreview, ...],
]:
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    entity = Entity.create(source_entity_uuid=uuid4())
    tiefling_definition = TIEFLING_SPECIES_DECLARATION.definition_payload
    assert isinstance(tiefling_definition, SpeciesDefinition)
    source_definition = tiefling_definition.innate_spellcasting[0]
    preview_rows = tuple(
        OriginInnateSpellGrantPreview(
            grant_id=grant.grant_id,
            spell_ref=grant.spell_ref,
            provider_ref=TIEFLING_SPECIES_DECLARATION.ref,
            spellcasting_source_id=source_definition.source_id,
            spellcasting_ability=source_definition.ability,
            provider_level=5,
            fixed_cast_rank=grant.fixed_cast_rank,
            uses_per_long_rest=grant.uses_per_long_rest,
            grant_token=f"tiefling:{grant.grant_id}",
        )
        for grant in source_definition.grants
        if grant.spell_ref is not None
    )
    context = BuiltinCharacterGrantContext(
        entity=entity,
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(),
            grant_schedule=(),
            final_known_spell_refs=tuple(
                row.spell_ref for row in preview_rows
            ),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
            origin_innate_spells=preview_rows,
        ),
        runtime=runtime,
    )
    return context, preview_rows


def test_origin_innate_install_failure_rolls_back_prior_source_and_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, preview_rows = _tiefling_innate_failure_context()
    entity = context.entity
    thaumaturgy_key = next(
        row.spell_ref.identity_key
        for row in preview_rows
        if row.spell_ref.content_id == "spell.thaumaturgy"
    )
    monkeypatch.setattr(
        origin_innate_spellcasting,
        "_SPELL_ROW_BY_REF_KEY",
        {
            key: row
            for key, row in (
                origin_innate_spellcasting._SPELL_ROW_BY_REF_KEY.items()
            )
            if key != thaumaturgy_key
        },
    )

    with pytest.raises(
        RuntimeError,
        match="Origin innate spell has no exact runtime row",
    ):
        install_origin_innate_spellcasting(context)

    assert entity.spellcasting.sources == {}
    assert entity.registered_actions == []
    assert entity.event_handlers == {}
    assert not any(
        name.startswith("origin_innate_spell:")
        for name in entity.action_economy.resources
    )


@pytest.mark.parametrize(
    "failure_mode",
    ("constructor", "wrong_action", "unsupported_reaction"),
)
def test_origin_innate_current_grant_failure_releases_its_resource(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    context, preview_rows = _tiefling_innate_failure_context()
    darkness = next(
        row
        for row in preview_rows
        if row.spell_ref.content_id == "spell.darkness"
    )
    current_row = origin_innate_spellcasting._SPELL_ROW_BY_REF_KEY[
        darkness.spell_ref.identity_key
    ]

    class ConstructorFailureSpell(SpellAction):
        def __init__(self, **_: object) -> None:
            raise RuntimeError("fixture spell constructor failure")

    class WrongAction(BaseAction):
        pass

    if failure_mode == "constructor":
        replacement = replace(
            current_row,
            spell_type=ConstructorFailureSpell,
        )
        expected_error = RuntimeError
    elif failure_mode == "wrong_action":
        replacement = replace(
            current_row,
            spell_type=cast(type[SpellAction], WrongAction),
        )
        expected_error = TypeError
    else:
        hellish = next(
            row
            for row in origin_innate_spellcasting._SPELL_ROW_BY_REF_KEY.values()
            if row.declaration.ref.content_id == "spell.hellish_rebuke"
        )
        assert hellish.reaction_handler_factory is not None
        replacement = replace(
            current_row,
            spell_type=None,
            reaction_handler_factory=hellish.reaction_handler_factory,
        )
        expected_error = RuntimeError
    monkeypatch.setattr(
        origin_innate_spellcasting,
        "_SPELL_ROW_BY_REF_KEY",
        {
            **origin_innate_spellcasting._SPELL_ROW_BY_REF_KEY,
            darkness.spell_ref.identity_key: replacement,
        },
    )

    with pytest.raises(expected_error):
        install_origin_innate_spellcasting(context)

    assert context.entity.spellcasting.sources == {}
    assert context.entity.registered_actions == []
    assert context.entity.event_handlers == {}
    assert not any(
        name.startswith("origin_innate_spell:")
        for name in context.entity.action_economy.resources
    )


def test_high_elf_selected_wizard_cantrip_installs_with_intelligence_source(
) -> None:
    variant = HIGH_ELF_VARIANT_DECLARATION.definition_payload
    assert isinstance(variant, SpeciesVariantDefinition)
    source = variant.innate_spellcasting[0]
    grant = source.grants[0]
    requirement = next(
        row
        for row in variant.choice_requirements
        if row.choice_id == grant.choice_id
    )
    assert requirement.choice_id == grant.choice_id
    assert requirement.allowed_refs == grant.allowed_spell_refs
    selected_ref = next(
        ref
        for ref in grant.allowed_spell_refs
        if ref.content_id == "spell.fire_bolt"
    )

    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    character_id = uuid4()
    entity = Entity.create(source_entity_uuid=uuid4())
    preview_row = OriginInnateSpellGrantPreview(
        grant_id=grant.grant_id,
        spell_ref=selected_ref,
        provider_ref=HIGH_ELF_VARIANT_DECLARATION.ref,
        spellcasting_source_id=source.source_id,
        spellcasting_ability=source.ability,
        provider_level=1,
        fixed_cast_rank=0,
        uses_per_long_rest=None,
        grant_token="high_elf:selected_fire_bolt",
    )
    context = BuiltinCharacterGrantContext(
        entity=entity,
        character_id=character_id,
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(),
            grant_schedule=(),
            final_known_spell_refs=(selected_ref,),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
            origin_innate_spells=(preview_row,),
        ),
        runtime=runtime,
    )

    receipts = install_origin_innate_spellcasting(context)

    fire_bolt = entity.get_action_template("Fire Bolt")
    assert isinstance(fire_bolt, SpellAction)
    assert fire_bolt.spellcasting_source_id is not None
    runtime_source = entity.spellcasting.sources[
        fire_bolt.spellcasting_source_id
    ]
    assert runtime_source.source_kind == "innate"
    assert runtime_source.provider_ref == HIGH_ELF_VARIANT_DECLARATION.ref
    assert runtime_source.ability == "intelligence"

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=context.character_id,
            grants=receipts,
        ),
    )
    assert entity.get_action_template("Fire Bolt") is None
    assert entity.spellcasting.sources == {}


def test_tiefling_hellish_rebuke_spends_fixed_use_and_deals_rank_two_damage(
) -> None:
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    tiefling = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            position=(2, 2),
            faction="heroes",
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    ),
                ],
            ),
        ),
    )
    attacker = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            position=(3, 2),
            faction="monsters",
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    ),
                ],
            ),
        ),
    )
    save_penalty = NumericalModifier.create(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
        name="Fail Hellish Rebuke save",
        value=-100,
    )
    attacker.saving_throws.get_saving_throw(
        "dexterity",
    ).bonus.self_static.add_value_modifier(save_penalty)
    tiefling_definition = TIEFLING_SPECIES_DECLARATION.definition_payload
    assert isinstance(tiefling_definition, SpeciesDefinition)
    source_definition = tiefling_definition.innate_spellcasting[0]
    grant = next(
        row
        for row in source_definition.grants
        if row.grant_id == "tiefling.infernal_legacy.hellish_rebuke"
    )
    assert grant.spell_ref is not None
    preview_row = OriginInnateSpellGrantPreview(
        grant_id=grant.grant_id,
        spell_ref=grant.spell_ref,
        provider_ref=TIEFLING_SPECIES_DECLARATION.ref,
        spellcasting_source_id=source_definition.source_id,
        spellcasting_ability=source_definition.ability,
        provider_level=5,
        fixed_cast_rank=grant.fixed_cast_rank,
        uses_per_long_rest=grant.uses_per_long_rest,
        grant_token="tiefling:hellish_rebuke",
    )
    context = BuiltinCharacterGrantContext(
        entity=tiefling,
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(),
            grant_schedule=(),
            final_known_spell_refs=(grant.spell_ref,),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
            origin_innate_spells=(preview_row,),
        ),
        runtime=runtime,
    )
    receipts = install_origin_innate_spellcasting(context)
    tiefling.update_entity_senses(max_distance=60)
    resource_name = innate_spell_resource_name(preview_row)
    hp_before = attacker.get_normal_hp()

    with fixed_dice_faces(1, 10, 10, 10):
        tiefling.receive_damage(
            1,
            DamageType.SLASHING,
            attacker.uuid,
        )

    assert attacker.get_normal_hp() == hp_before - 30
    assert tiefling.action_economy.get_resource_current(resource_name) == 0
    assert tiefling.action_economy.reactions.normalized_score == 0

    remove_character_composition(
        tiefling,
        CharacterCompositionReceipt(
            runtime_entity_uuid=tiefling.uuid,
            character_id=context.character_id,
            grants=receipts,
        ),
    )
    assert not tiefling.event_handlers
    assert resource_name not in tiefling.action_economy.resources


def test_hellish_rebuke_declaration_veto_preserves_reaction_and_resource(
) -> None:
    """A rejected reaction action cannot spend resources or damage its target."""
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    tiefling = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            position=(2, 2),
            faction="heroes",
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    ),
                ],
            ),
        ),
    )
    attacker = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            position=(3, 2),
            faction="monsters",
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    ),
                ],
            ),
        ),
    )
    tiefling_definition = TIEFLING_SPECIES_DECLARATION.definition_payload
    assert isinstance(tiefling_definition, SpeciesDefinition)
    source_definition = tiefling_definition.innate_spellcasting[0]
    grant = next(
        row
        for row in source_definition.grants
        if row.grant_id == "tiefling.infernal_legacy.hellish_rebuke"
    )
    assert grant.spell_ref is not None
    preview_row = OriginInnateSpellGrantPreview(
        grant_id=grant.grant_id,
        spell_ref=grant.spell_ref,
        provider_ref=TIEFLING_SPECIES_DECLARATION.ref,
        spellcasting_source_id=source_definition.source_id,
        spellcasting_ability=source_definition.ability,
        provider_level=5,
        fixed_cast_rank=grant.fixed_cast_rank,
        uses_per_long_rest=grant.uses_per_long_rest,
        grant_token="tiefling:hellish_rebuke:veto",
    )
    receipts = install_origin_innate_spellcasting(
        BuiltinCharacterGrantContext(
            entity=tiefling,
            character_id=uuid4(),
            preview=CharacterBuildPreview(
                class_level_counts=(),
                automatic_grant_refs=(),
                grant_schedule=(),
                final_known_spell_refs=(grant.spell_ref,),
                caster_contributions=(),
                effective_spellcaster_level=0,
                normal_spell_slots=(),
                origin_innate_spells=(preview_row,),
            ),
            runtime=runtime,
        )
    )
    resource_name = innate_spell_resource_name(preview_row)

    def veto_reaction_action(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Reaction action vetoed")

    tiefling.add_event_handler(
        EventHandler(
            source_entity_uuid=tiefling.uuid,
            name="Veto Hellish Rebuke action",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.DECLARATION,
                    event_source_entity_uuid=tiefling.uuid,
                ),
            ],
            event_processor=veto_reaction_action,
        )
    )
    tiefling.update_entity_senses(max_distance=60)
    attacker_hp_before = attacker.get_normal_hp()
    reaction_before = tiefling.action_economy.reactions.normalized_score
    resource_before = tiefling.action_economy.get_resource_current(
        resource_name
    )

    tiefling.receive_damage(1, DamageType.SLASHING, attacker.uuid)

    assert attacker.get_normal_hp() == attacker_hp_before
    assert tiefling.action_economy.reactions.normalized_score == reaction_before
    assert (
        tiefling.action_economy.get_resource_current(resource_name)
        == resource_before
    )
    assert receipts
