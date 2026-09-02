"""Public outcome proofs for direct character origins."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.conditions import Concentrating
from dnd.content.characters.origin_definitions import (
    ABILITY_ORDER,
    ALL_LANGUAGES,
    ALL_SKILLS,
    BACKGROUND_DEFINITIONS,
    DRACONIC_ANCESTRIES,
    DRAGONBORN_ANCESTRY_DEFINITIONS,
    SPECIES_DEFINITIONS,
    SPECIES_VARIANT_DEFINITIONS,
    resolve_origin,
)
from dnd.content.characters.origin_grants import (
    ORIGIN_STEP_ID,
    apply_origin,
    reconcile_origin_total_level,
    remove_origin,
)
from dnd.content.items.item_loadouts import ACOLYTE_STARTING_LOADOUT
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import RollType, fixed_dice_faces
from dnd.core.events import EventPhase, TakeDamageEvent
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.life_types import LifeState
from dnd.core.modifiers import AdvantageStatus, NumericalModifier, ResistanceStatus
from dnd.core.progression import CasterProgression
from dnd.core.saving_throw_types import (
    SAVING_THROW_CONTEXT_KEY,
    SavingThrowContext,
    SavingThrowEffectTag,
)
from dnd.entity import Entity, EntityConfig
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_RESOURCE,
    DragonbornBreathWeapon,
    DragonbornBreathWeaponEvent,
)
from dnd.origins.half_orc import HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Darkness
from dnd.types.character_progression import (
    AppliedOriginState,
    Background,
    OriginCapability,
    OriginChoiceSelection,
    RitualPreparationPolicy,
    Species,
    SpeciesVariant,
)
from dnd.types.abilities import AbilityName
from dnd.types.senses import SenseMode, SensesType
from tests.engine.support import create_test_entity


_BASE_SCORES: tuple[tuple[AbilityName, int], ...] = tuple(
    (ability, 10) for ability in ABILITY_ORDER
)
_BONUSES: tuple[tuple[AbilityName, int], ...] = (
    ("strength", 2),
    ("dexterity", 1),
)
_ORIGIN_CASES = (
    (Species.DRAGONBORN, None),
    (Species.DWARF, None),
    (Species.DWARF, SpeciesVariant.HILL_DWARF),
    (Species.ELF, None),
    (Species.ELF, SpeciesVariant.HIGH_ELF),
    (Species.GNOME, None),
    (Species.GNOME, SpeciesVariant.ROCK_GNOME),
    (Species.HALF_ELF, None),
    (Species.HALF_ORC, None),
    (Species.HALFLING, None),
    (Species.HALFLING, SpeciesVariant.LIGHTFOOT),
    (Species.HUMAN, None),
    (Species.TIEFLING, None),
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _resolved(
    species: Species,
    variant: SpeciesVariant | None = None,
    background: Background = Background.ADVENTURER,
):
    species_definition = SPECIES_DEFINITIONS[species]
    variant_definition = (
        SPECIES_VARIANT_DEFINITIONS[variant]
        if variant is not None
        else None
    )
    requirements = (
        *species_definition.choices,
        *(variant_definition.choices if variant_definition is not None else ()),
        *BACKGROUND_DEFINITIONS[background].choices,
    )
    used_languages = {
        *species_definition.fixed_languages,
        *(variant_definition.fixed_languages if variant_definition is not None else ()),
    }
    used_skills = {
        *species_definition.fixed_skills,
        *BACKGROUND_DEFINITIONS[background].fixed_skills,
    }
    used_tools: set[str] = set()
    selections: list[OriginChoiceSelection] = []
    for requirement in requirements:
        if "language" in requirement.choice_id:
            unavailable = used_languages
        elif "skill" in requirement.choice_id:
            unavailable = used_skills
        elif "tool" in requirement.choice_id:
            unavailable = used_tools
        else:
            unavailable = set()
        values = tuple(
            value
            for value in requirement.allowed_values
            if value not in unavailable
        )[: requirement.selections]
        selections.append(OriginChoiceSelection(
            choice_id=requirement.choice_id,
            values=values,
        ))
        unavailable.update(values)
    state = AppliedOriginState(
        base_ability_scores=_BASE_SCORES,
        flexible_ability_bonuses=_BONUSES,
        choices=tuple(selections),
    )
    return resolve_origin(
        species=species,
        species_variant=variant,
        background=background,
        state=state,
    )


def _action(entity: Entity, behavior_id: str):
    return next(
        action
        for action in entity.registered_actions
        if action.behavior_binding is not None
        and action.behavior_binding.behavior_id == behavior_id
    )


def _assert_origin_removed(entity: Entity) -> None:
    assert entity.character_species is None
    assert entity.character_species_variant is None
    assert entity.character_background is None
    assert entity.applied_origin_state is None
    assert entity.structural_size_sources == {}
    assert entity.origin_capability_sources == {}
    assert entity.feature_sources == {}
    assert entity.senses.get_sense_range(SensesType.DARKVISION) == -1
    assert entity.creature_proficiencies.language_sources == {}
    assert entity.creature_proficiencies.tool_sources == {}
    assert entity.creature_proficiencies.specific_weapon_sources == {}
    assert entity.event_handlers == {}
    assert entity.registered_actions == []
    assert entity.spellcasting.sources == {}
    with pytest.raises(KeyError):
        entity.character_grant_receipt(ORIGIN_STEP_ID)


def _choice_rows(definition) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
    return tuple(
        (choice.choice_id, choice.selections, choice.allowed_values)
        for choice in definition.choices
    )


def test_cold_species_table_is_the_exact_nine_species_vocabulary() -> None:
    assert tuple(SPECIES_DEFINITIONS) == tuple(Species)
    assert {
        species: (
            definition.size,
            definition.walking_speed_feet,
            definition.fixed_languages,
            definition.variants,
            definition.fixed_skills,
            definition.capabilities,
            definition.feature_ids,
            _choice_rows(definition),
        )
        for species, definition in SPECIES_DEFINITIONS.items()
    } == {
        Species.DRAGONBORN: (
            Size.MEDIUM,
            30,
            ("language.common", "language.draconic"),
            (),
            (),
            (),
            (
                "species.dragonborn.ancestry_resistance",
                "species.dragonborn.breath_weapon",
            ),
            ((
                "species.dragonborn.draconic_ancestry",
                1,
                DRACONIC_ANCESTRIES,
            ),),
        ),
        Species.DWARF: (
            Size.MEDIUM,
            25,
            ("language.common", "language.dwarvish"),
            (SpeciesVariant.HILL_DWARF,),
            (),
            (OriginCapability.STONECUNNING,),
            (
                "sense.darkvision.60",
                "species.dwarf.combat_training",
                "species.dwarf.poison_resilience",
            ),
            ((
                "species.dwarf.artisans_tool",
                1,
                (
                    "tool.artisan.brewers_supplies",
                    "tool.artisan.masons_tools",
                    "tool.artisan.smiths_tools",
                ),
            ),),
        ),
        Species.ELF: (
            Size.MEDIUM,
            30,
            ("language.common", "language.elvish"),
            (SpeciesVariant.HIGH_ELF,),
            ("perception",),
            (
                OriginCapability.MAGICAL_SLEEP_IMMUNITY,
                OriginCapability.TRANCE,
            ),
            ("sense.darkvision.60", "species.elf.fey_ancestry"),
            (),
        ),
        Species.GNOME: (
            Size.SMALL,
            25,
            ("language.common", "language.gnomish"),
            (SpeciesVariant.ROCK_GNOME,),
            (),
            (),
            ("sense.darkvision.60", "species.gnome.cunning"),
            (),
        ),
        Species.HALF_ELF: (
            Size.MEDIUM,
            30,
            ("language.common", "language.elvish"),
            (),
            (),
            (OriginCapability.MAGICAL_SLEEP_IMMUNITY,),
            ("sense.darkvision.60", "species.elf.fey_ancestry"),
            (
                (
                    "species.half_elf.additional_language",
                    1,
                    tuple(
                        value
                        for value in ALL_LANGUAGES
                        if value not in {"language.common", "language.elvish"}
                    ),
                ),
                ("species.half_elf.skill_versatility", 2, ALL_SKILLS),
            ),
        ),
        Species.HALF_ORC: (
            Size.MEDIUM,
            30,
            ("language.common", "language.orc"),
            (),
            ("intimidation",),
            (),
            (
                "sense.darkvision.60",
                "species.half_orc.relentless_endurance",
                "species.half_orc.savage_attacks",
            ),
            (),
        ),
        Species.HALFLING: (
            Size.SMALL,
            25,
            ("language.common", "language.halfling"),
            (SpeciesVariant.LIGHTFOOT,),
            (),
            (OriginCapability.HALFLING_NIMBLENESS,),
            ("species.halfling.brave", "species.halfling.lucky"),
            (),
        ),
        Species.HUMAN: (
            Size.MEDIUM,
            30,
            ("language.common",),
            (),
            (),
            (),
            (),
            ((
                "species.human.additional_language",
                1,
                tuple(
                    value for value in ALL_LANGUAGES
                    if value != "language.common"
                ),
            ),),
        ),
        Species.TIEFLING: (
            Size.MEDIUM,
            30,
            ("language.common", "language.infernal"),
            (),
            (),
            (),
            (
                "sense.darkvision.60",
                "species.tiefling.fire_resistance",
                "species.tiefling.infernal_legacy",
            ),
            (),
        ),
    }


def test_cold_variant_and_background_tables_are_exact() -> None:
    assert tuple(SPECIES_VARIANT_DEFINITIONS) == tuple(SpeciesVariant)
    assert tuple(BACKGROUND_DEFINITIONS) == tuple(Background)
    assert {
        variant: (
            definition.parent_species,
            definition.fixed_languages,
            definition.capabilities,
            definition.feature_ids,
            _choice_rows(definition),
        )
        for variant, definition in SPECIES_VARIANT_DEFINITIONS.items()
    } == {
        SpeciesVariant.HILL_DWARF: (
            Species.DWARF,
            (),
            (),
            ("species_variant.hill_dwarf.dwarven_toughness",),
            (),
        ),
        SpeciesVariant.HIGH_ELF: (
            Species.ELF,
            (),
            (),
            (
                "species_variant.high_elf.weapon_training",
                "species_variant.high_elf.wizard_cantrip",
            ),
            (
                (
                    "species_variant.high_elf.additional_language",
                    1,
                    tuple(
                        value
                        for value in ALL_LANGUAGES
                        if value not in {"language.common", "language.elvish"}
                    ),
                ),
                (
                    "species_variant.high_elf.wizard_cantrip",
                    1,
                    ("spell.fire_bolt",),
                ),
            ),
        ),
        SpeciesVariant.ROCK_GNOME: (
            Species.GNOME,
            (),
            (OriginCapability.ARTIFICERS_LORE, OriginCapability.TINKER),
            ("species_variant.rock_gnome.tinkers_tools",),
            (),
        ),
        SpeciesVariant.LIGHTFOOT: (
            Species.HALFLING,
            (),
            (OriginCapability.NATURALLY_STEALTHY,),
            (),
            (),
        ),
    }
    assert {
        background: (
            definition.fixed_skills,
            definition.capabilities,
            definition.feature_ids,
            _choice_rows(definition),
        )
        for background, definition in BACKGROUND_DEFINITIONS.items()
    } == {
        Background.ACOLYTE: (
            ("insight", "religion"),
            (OriginCapability.SHELTER_OF_THE_FAITHFUL,),
            ("background.acolyte.starting_holdings",),
            (("background.acolyte.languages", 2, ALL_LANGUAGES),),
        ),
        Background.ADVENTURER: ((), (), (), ()),
    }


def test_cold_draconic_ancestry_table_is_exact() -> None:
    assert tuple(DRAGONBORN_ANCESTRY_DEFINITIONS) == DRACONIC_ANCESTRIES
    assert {
        ancestry: (row.damage_type, row.geometry, row.save_ability)
        for ancestry, row in DRAGONBORN_ANCESTRY_DEFINITIONS.items()
    } == {
        "black": (DamageType.ACID, "line", "dexterity"),
        "blue": (DamageType.LIGHTNING, "line", "dexterity"),
        "brass": (DamageType.FIRE, "line", "dexterity"),
        "bronze": (DamageType.LIGHTNING, "line", "dexterity"),
        "copper": (DamageType.ACID, "line", "dexterity"),
        "gold": (DamageType.FIRE, "cone", "dexterity"),
        "green": (DamageType.POISON, "cone", "constitution"),
        "red": (DamageType.FIRE, "cone", "dexterity"),
        "silver": (DamageType.COLD, "cone", "constitution"),
        "white": (DamageType.COLD, "cone", "constitution"),
    }
    assert tuple(entry.item_id for entry in ACOLYTE_STARTING_LOADOUT) == (
        "gear.holy_symbol",
        "gear.prayer_book",
        "gear.incense",
        "gear.vestments",
        "gear.common_clothes",
    )
    assert ACOLYTE_STARTING_LOADOUT[2].quantity == 5


def test_origin_resolution_rejects_a_language_already_known_from_species() -> None:
    state = AppliedOriginState(
        base_ability_scores=_BASE_SCORES,
        flexible_ability_bonuses=_BONUSES,
        choices=(OriginChoiceSelection(
            choice_id="background.acolyte.languages",
            values=("language.common", "language.celestial"),
        ),),
    )

    with pytest.raises(ValueError, match="cannot duplicate known languages"):
        resolve_origin(
            species=Species.ELF,
            species_variant=None,
            background=Background.ACOLYTE,
            state=state,
        )


@pytest.mark.parametrize(
    ("selection", "message"),
    (
        (
            OriginChoiceSelection(
                choice_id="species.human.additional_language",
                values=("language.elvish", "language.gnomish"),
            ),
            "wrong cardinality",
        ),
        (
            OriginChoiceSelection(
                choice_id="species.human.additional_language",
                values=("language.common",),
            ),
            "unsupported values",
        ),
    ),
)
def test_origin_resolution_rejects_wrong_choice_values(
    selection: OriginChoiceSelection,
    message: str,
) -> None:
    state = AppliedOriginState(
        base_ability_scores=_BASE_SCORES,
        flexible_ability_bonuses=_BONUSES,
        choices=(selection,),
    )

    with pytest.raises(ValueError, match=message):
        resolve_origin(
            species=Species.HUMAN,
            species_variant=None,
            background=Background.ADVENTURER,
            state=state,
        )


@pytest.mark.parametrize(("species", "variant"), _ORIGIN_CASES)
@pytest.mark.parametrize("background", tuple(Background))
def test_every_origin_applies_and_removes_exactly(
    species: Species,
    variant: SpeciesVariant | None,
    background: Background,
) -> None:
    entity = Entity.create(uuid4())
    resolved = _resolved(species, variant, background)
    initial_scores = {
        ability: entity.ability_scores.get_ability(ability).ability_score.normalized_score
        for ability in ABILITY_ORDER
    }

    receipt = apply_origin(entity, resolved, character_level=5)

    assert receipt == entity.character_grant_receipt(ORIGIN_STEP_ID)
    assert entity.character_species is species
    assert entity.character_species_variant is variant
    assert entity.character_background is background
    assert entity.applied_origin_state == resolved.state
    assert entity.size is resolved.size
    assert entity.action_economy.current_speed() == resolved.walking_speed_feet
    assert all(
        entity.creature_proficiencies.knows_language(language)
        for language in resolved.languages
    )
    assert all(entity.has_origin_capability(row) for row in resolved.capabilities)
    assert all(entity.has_feature(row) for row in resolved.feature_ids)
    assert entity.ability_scores.strength.ability_score.normalized_score == (
        initial_scores["strength"] + 2
    )
    assert entity.ability_scores.dexterity.ability_score.normalized_score == (
        initial_scores["dexterity"] + 1
    )

    remove_origin(entity)

    _assert_origin_removed(entity)
    assert entity.size is entity.structural_base_size
    assert entity.action_economy.current_speed() == 30
    for ability, score in initial_scores.items():
        assert (
            entity.ability_scores.get_ability(ability).ability_score.normalized_score
            == score
        )
    entity.discard_uncommitted()


@pytest.mark.parametrize(
    ("species", "variant", "background", "message"),
    (
        (
            Species.ELF,
            SpeciesVariant.HILL_DWARF,
            Background.ADVENTURER,
            "does not belong",
        ),
        (
            Species.HUMAN,
            None,
            Background.ADVENTURER,
            "choice order",
        ),
    ),
)
def test_origin_resolution_rejects_invalid_semantics_before_entity_mutation(
    species: Species,
    variant: SpeciesVariant | None,
    background: Background,
    message: str,
) -> None:
    entity = Entity.create(uuid4())
    state = AppliedOriginState(
        base_ability_scores=_BASE_SCORES,
        flexible_ability_bonuses=_BONUSES,
    )

    with pytest.raises(ValueError, match=message):
        resolve_origin(
            species=species,
            species_variant=variant,
            background=background,
            state=state,
        )

    assert entity.character_species is None
    assert entity.applied_origin_state is None
    entity.discard_uncommitted()


def test_natural_owner_failure_cleans_partial_origin_and_preserves_sibling() -> None:
    entity = Entity.create(uuid4())
    sibling_source = uuid4()
    sibling_feature = uuid4()
    entity.add_structural_size_source(sibling_source, Size.MEDIUM)
    entity.add_feature_source("feature.fixture.sibling", sibling_feature)
    initial_strength = entity.ability_scores.strength.ability_score.normalized_score

    with pytest.raises(ValueError, match="structural size contributions disagree"):
        apply_origin(entity, _resolved(Species.GNOME), character_level=1)

    assert entity.structural_size_sources == {sibling_source: Size.MEDIUM}
    assert entity.feature_sources == {"feature.fixture.sibling": {sibling_feature}}
    assert entity.ability_scores.strength.ability_score.normalized_score == initial_strength
    assert entity.character_species is None
    assert entity.applied_origin_state is None
    with pytest.raises(KeyError):
        entity.character_grant_receipt(ORIGIN_STEP_ID)
    entity.discard_uncommitted()


def test_origin_removal_preserves_sibling_feature_and_capability_sources() -> None:
    entity = Entity.create(uuid4())
    feature_source = uuid4()
    capability_source = uuid4()
    entity.add_feature_source("species.elf.fey_ancestry", feature_source)
    entity.add_origin_capability_source(
        OriginCapability.MAGICAL_SLEEP_IMMUNITY,
        capability_source,
    )

    apply_origin(
        entity,
        _resolved(Species.ELF, SpeciesVariant.HIGH_ELF),
        character_level=1,
    )
    remove_origin(entity)

    assert entity.feature_sources == {
        "species.elf.fey_ancestry": {feature_source},
    }
    assert entity.origin_capability_sources == {
        OriginCapability.MAGICAL_SLEEP_IMMUNITY: {capability_source},
    }
    entity.remove_feature_source("species.elf.fey_ancestry", feature_source)
    entity.remove_origin_capability_source(
        OriginCapability.MAGICAL_SLEEP_IMMUNITY,
        capability_source,
    )
    entity.discard_uncommitted()


def test_origin_mechanics_bind_direct_owner_surfaces() -> None:
    acolyte = Entity.create(uuid4())
    resolved_acolyte = _resolved(
        Species.HUMAN,
        background=Background.ACOLYTE,
    )
    apply_origin(acolyte, resolved_acolyte, character_level=1)
    assert acolyte.skill_set.insight.proficiency
    assert acolyte.skill_set.religion.proficiency
    assert acolyte.has_origin_capability(
        OriginCapability.SHELTER_OF_THE_FAITHFUL,
    )
    assert acolyte.has_feature("background.acolyte.starting_holdings")
    assert all(
        acolyte.creature_proficiencies.knows_language(language)
        for language in resolved_acolyte.languages
    )

    dragonborn = Entity.create(uuid4())
    apply_origin(dragonborn, _resolved(Species.DRAGONBORN), character_level=6)
    breath = _action(dragonborn, "action.origin.dragonborn.breath_weapon")
    assert isinstance(breath, DragonbornBreathWeapon)
    assert breath.damage_dice_count == 3
    assert breath.damage_type is DamageType.ACID
    assert breath.breath_geometry == "line"
    assert dragonborn.health.get_resistance(DamageType.ACID) is ResistanceStatus.RESISTANCE
    assert dragonborn.action_economy.resources[DRAGONBORN_BREATH_RESOURCE].maximum == 1

    dwarf = Entity.create(uuid4())
    apply_origin(
        dwarf,
        _resolved(Species.DWARF, SpeciesVariant.HILL_DWARF),
        character_level=5,
    )
    assert dwarf.health.get_resistance(DamageType.POISON) is ResistanceStatus.RESISTANCE
    assert dwarf.health.max_hit_points_bonus.normalized_score == 5
    assert set(dwarf.creature_proficiencies.specific_weapon_sources) == {
        "weapon.battleaxe",
        "weapon.handaxe",
        "weapon.light_hammer",
        "weapon.warhammer",
    }

    high_elf = Entity.create(uuid4())
    apply_origin(
        high_elf,
        _resolved(Species.ELF, SpeciesVariant.HIGH_ELF),
        character_level=5,
    )
    assert _action(high_elf, "spell.fire_bolt").caster_level == 5
    assert set(high_elf.creature_proficiencies.specific_weapon_sources) == {
        "weapon.longbow",
        "weapon.longsword",
        "weapon.shortbow",
        "weapon.shortsword",
    }

    rock_gnome = Entity.create(uuid4())
    apply_origin(
        rock_gnome,
        _resolved(Species.GNOME, SpeciesVariant.ROCK_GNOME),
        character_level=1,
    )
    assert rock_gnome.creature_proficiencies.is_tool_proficient("tool.tinkers_tools")
    assert rock_gnome.has_origin_capability(OriginCapability.ARTIFICERS_LORE)
    assert rock_gnome.has_origin_capability(OriginCapability.TINKER)

    half_orc = Entity.create(uuid4())
    apply_origin(half_orc, _resolved(Species.HALF_ORC), character_level=1)
    assert half_orc.equipment.crit_extra_dice_melee.normalized_score == 1

    tiefling = Entity.create(uuid4())
    apply_origin(tiefling, _resolved(Species.TIEFLING), character_level=1)
    assert tiefling.health.get_resistance(
        DamageType.FIRE,
    ) is ResistanceStatus.RESISTANCE


def test_direct_dragonborn_breath_executes_damage_save_and_rest_use() -> None:
    caster = create_test_entity(
        source_id=uuid4(),
        name="Black Dragonborn",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                constitution=AbilityConfig(ability_score=16),
            ),
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=12,
                hit_dice_count=6,
                mode="maximums",
            )]),
            position=(2, 5),
            faction="heroes",
            proficiency_bonus=3,
        ),
    )
    target = create_test_entity(
        source_id=uuid4(),
        name="Line Target",
        config=EntityConfig(
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=12,
                hit_dice_count=6,
                mode="maximums",
            )]),
            position=(6, 5),
            faction="monsters",
        ),
    )
    save_modifier = NumericalModifier.create(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        name="Fail Breath Weapon save",
        value=-100,
    )
    target.saving_throws.get_saving_throw(
        "dexterity",
    ).bonus.self_static.add_value_modifier(save_modifier)
    apply_origin(caster, _resolved(Species.DRAGONBORN), character_level=6)
    template = _action(caster, "action.origin.dragonborn.breath_weapon")
    hp_before = target.get_hp()

    with fixed_dice_faces(10, 4, 4, 4):
        result = template.instantiate(end_position=(3, 5)).apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    assert result.save_dc == 14
    assert result.total_damage == 12
    assert hp_before - target.get_hp() == 12
    assert caster.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 0
    caster.on_short_rest()
    assert caster.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 1


def test_direct_lightfoot_capability_changes_creature_space_traversal() -> None:
    halfling = create_test_entity(
        source_id=uuid4(),
        name="Lightfoot",
        config=EntityConfig(position=(1, 0), faction="heroes", size=Size.SMALL),
    )
    larger = create_test_entity(
        source_id=uuid4(),
        name="Larger creature",
        config=EntityConfig(position=(2, 0), faction="monsters", size=Size.MEDIUM),
    )
    apply_origin(
        halfling,
        _resolved(Species.HALFLING, SpeciesVariant.LIGHTFOOT),
        character_level=1,
    )

    halfling.update_entity_senses(max_distance=20)

    assert not larger.blocks_walking(halfling.uuid)
    assert halfling.senses.paths[(3, 0)] == [(1, 0), (2, 0), (3, 0)]
    assert halfling.has_origin_capability(OriginCapability.NATURALLY_STEALTHY)


@pytest.mark.parametrize(
    ("species", "effect_tag", "is_magical", "abilities"),
    (
        (Species.DWARF, SavingThrowEffectTag.POISON, False, ABILITY_ORDER),
        (Species.ELF, SavingThrowEffectTag.CHARM, True, ABILITY_ORDER),
        (Species.HALFLING, SavingThrowEffectTag.FEAR, True, ABILITY_ORDER),
        (
            Species.GNOME,
            None,
            True,
            ("intelligence", "wisdom", "charisma"),
        ),
    ),
)
def test_origin_save_rules_consume_exact_cause_context(
    species: Species,
    effect_tag: SavingThrowEffectTag | None,
    is_magical: bool,
    abilities: tuple[str, ...],
) -> None:
    entity = Entity.create(uuid4())
    apply_origin(entity, _resolved(species), character_level=1)
    context = SavingThrowContext(
        cause_id="origin.fixture.save",
        effect_id="origin.fixture.effect",
        is_magical=is_magical,
        effect_tags=(() if effect_tag is None else (effect_tag,)),
    )

    for ability in ABILITY_ORDER:
        bonus = entity.saving_throws.get_saving_throw(ability).bonus
        bonus.set_context({SAVING_THROW_CONTEXT_KEY: context})
        assert bonus.advantage is (
            AdvantageStatus.ADVANTAGE
            if ability in abilities
            else AdvantageStatus.NONE
        )
        bonus.clear_context()


def test_halfling_lucky_and_half_orc_endurance_are_direct_bound_handlers() -> None:
    halfling = Entity.create(uuid4())
    apply_origin(halfling, _resolved(Species.HALFLING), character_level=1)
    lucky = next(iter(halfling.event_handlers.values()))
    assert lucky.behavior_binding is not None
    assert lucky.behavior_binding.behavior_id == "trait.origin.halfling.lucky"
    with fixed_dice_faces(1, 7):
        roll, event = halfling.roll_d20_event(
            halfling.ability_scores.dexterity.ability_score,
            RollType.CHECK,
            skill_name="stealth",
        )
    assert roll.results == [7]
    assert event.original_roll.results == [1]

    half_orc = Entity.create(
        uuid4(),
        config=EntityConfig(health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10,
            hit_dice_count=1,
            mode="maximums",
        )])),
    )
    attacker = Entity.create(uuid4())
    apply_origin(half_orc, _resolved(Species.HALF_ORC), character_level=1)
    endurance = next(iter(half_orc.event_handlers.values()))
    assert endurance.behavior_binding is not None
    assert endurance.behavior_binding.behavior_id == (
        "trait.origin.half_orc.relentless_endurance"
    )
    half_orc.receive_damage(
        half_orc.get_normal_hp(),
        DamageType.SLASHING,
        attacker.uuid,
    )
    assert half_orc.get_normal_hp() == 1
    assert half_orc.health.life_state is LifeState.ALIVE
    assert half_orc.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) == 0


def test_total_level_reconciliation_updates_every_origin_threshold() -> None:
    dragonborn = Entity.create(uuid4())
    apply_origin(dragonborn, _resolved(Species.DRAGONBORN), character_level=1)
    reconcile_origin_total_level(dragonborn, previous_level=1, new_level=16)
    assert _action(
        dragonborn,
        "action.origin.dragonborn.breath_weapon",
    ).damage_dice_count == 5

    hill_dwarf = Entity.create(uuid4())
    apply_origin(
        hill_dwarf,
        _resolved(Species.DWARF, SpeciesVariant.HILL_DWARF),
        character_level=1,
    )
    reconcile_origin_total_level(hill_dwarf, previous_level=1, new_level=9)
    assert hill_dwarf.health.max_hit_points_bonus.normalized_score == 9

    high_elf = Entity.create(uuid4())
    apply_origin(
        high_elf,
        _resolved(Species.ELF, SpeciesVariant.HIGH_ELF),
        character_level=1,
    )
    reconcile_origin_total_level(high_elf, previous_level=1, new_level=7)
    assert _action(high_elf, "spell.fire_bolt").caster_level == 7
    assert next(iter(high_elf.spellcasting.sources.values())).provider_level == 7

    tiefling = Entity.create(uuid4())
    apply_origin(tiefling, _resolved(Species.TIEFLING), character_level=1)
    assert {
        action.behavior_binding.behavior_id
        for action in tiefling.registered_actions
        if action.behavior_binding is not None
    } == {
        "spell.thaumaturgy",
    }
    reconcile_origin_total_level(tiefling, previous_level=1, new_level=3)
    assert tiefling.spellcasting.learned_reaction_spell_source_ids(
        "spell.hellish_rebuke",
    )
    reconcile_origin_total_level(tiefling, previous_level=3, new_level=5)
    assert _action(tiefling, "spell.darkness").caster_level == 5
    reconcile_origin_total_level(tiefling, previous_level=5, new_level=2)
    assert {
        action.behavior_binding.behavior_id
        for action in tiefling.registered_actions
        if action.behavior_binding is not None
    } == {
        "spell.thaumaturgy",
    }
    assert tiefling.spellcasting.learned_reaction_spell_source_ids(
        "spell.hellish_rebuke",
    ) == ()

    jumping_tiefling = Entity.create(uuid4())
    apply_origin(
        jumping_tiefling,
        _resolved(Species.TIEFLING),
        character_level=1,
    )
    reconcile_origin_total_level(
        jumping_tiefling,
        previous_level=1,
        new_level=16,
    )
    jumping_source = next(iter(jumping_tiefling.spellcasting.sources.values()))
    assert jumping_source.provider_level == 16
    assert _action(jumping_tiefling, "spell.darkness").caster_level == 16


def test_tiefling_reaction_cleanup_preserves_a_sibling_spell_source() -> None:
    tiefling = create_test_entity(
        source_id=uuid4(),
        name="Tiefling Sorcerer",
        config=EntityConfig(
            action_economy=ActionEconomyConfig(spell_slots={1: 1}),
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=8,
                hit_dice_count=4,
                mode="maximums",
            )]),
            position=(1, 1),
            faction="heroes",
        ),
    )
    attacker = create_test_entity(
        source_id=uuid4(),
        name="Attacker",
        config=EntityConfig(
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10,
                hit_dice_count=4,
                mode="maximums",
            )]),
            position=(2, 1),
            faction="monsters",
        ),
    )
    receipt = apply_origin(
        tiefling,
        _resolved(Species.TIEFLING),
        character_level=3,
    )
    spell_id, origin_source, handler_uuid = (
        receipt.learned_reaction_spell_sources[0]
    )
    assert handler_uuid not in receipt.handler_uuids
    sibling_source = uuid4()
    tiefling.spellcasting.add_source(
        sibling_source,
        "charisma",
        provider_id="class.sorcerer",
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=1,
        maximum_spell_rank=1,
        ritual_policy=RitualPreparationPolicy.KNOWN,
    )
    tiefling.spellcasting.add_learned_reaction_spell_source(
        spell_id=spell_id,
        source_id=sibling_source,
        handler_uuid=handler_uuid,
    )

    reconcile_origin_total_level(tiefling, previous_level=3, new_level=2)

    assert tiefling.spellcasting.learned_reaction_spell_source_ids(spell_id) == (
        sibling_source,
    )
    assert tiefling.event_handlers[handler_uuid].uuid == handler_uuid
    assert origin_source in tiefling.spellcasting.sources

    remove_origin(tiefling)

    assert tiefling.spellcasting.learned_reaction_spell_source_ids(spell_id) == (
        sibling_source,
    )
    assert tiefling.event_handlers[handler_uuid].uuid == handler_uuid
    assert set(tiefling.spellcasting.sources) == {sibling_source}

    truesight_source = uuid4()
    tiefling.senses.add_sense_mode_source(
        truesight_source,
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60),
    )
    tiefling.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=60)
    contact = tiefling.senses.entities[attacker.uuid]
    assert contact.visual
    attacker_hp = attacker.get_hp()
    damage_event = TakeDamageEvent(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=tiefling.uuid,
        total_damage=1,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    handler = tiefling.event_handlers[handler_uuid]
    assert any(trigger(damage_event) for trigger in handler.trigger_conditions)
    assert tiefling.action_economy.can_afford("reactions", 1)
    assert tiefling.get_lowest_spell_slot(1) == 1
    with fixed_dice_faces(1, 10, 10):
        assert handler(damage_event) is damage_event
    assert attacker.get_hp() == attacker_hp - 20
    assert tiefling.action_economy.spell_slot_value(1).normalized_score == 0

    reapplied = apply_origin(
        tiefling,
        _resolved(Species.TIEFLING),
        character_level=3,
    )
    assert reapplied.learned_reaction_spell_sources == (
        (spell_id, origin_source, handler_uuid),
    )
    assert tiefling.spellcasting.learned_reaction_spell_source_ids(spell_id) == tuple(
        sorted((origin_source, sibling_source), key=str),
    )
    origin_cast = next(
        source
        for source in tiefling.spellcasting.learned_reaction_spell_sources(spell_id)
        if source.source_id == origin_source
    )
    assert origin_cast.fixed_cast_rank == 2
    assert origin_cast.resource_name is not None
    tiefling.action_economy.reset_all_costs()
    innate_damage_event = TakeDamageEvent(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=tiefling.uuid,
        total_damage=1,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    with fixed_dice_faces(1, 10, 10, 10):
        assert handler(innate_damage_event) is innate_damage_event
    assert tiefling.action_economy.get_resource_current(
        origin_cast.resource_name,
    ) == 0
    assert tiefling.action_economy.spell_slot_value(1).normalized_score == 0

    remove_origin(tiefling)

    assert tiefling.spellcasting.learned_reaction_spell_source_ids(spell_id) == (
        sibling_source,
    )
    assert tiefling.event_handlers[handler_uuid].uuid == handler_uuid

    assert tiefling.spellcasting.remove_learned_reaction_spell_source(
        spell_id=spell_id,
        source_id=sibling_source,
        handler_uuid=handler_uuid,
    )
    handler = tiefling.event_handlers[handler_uuid]
    tiefling.remove_event_handler(handler)
    handler.remove_from_register()
    assert tiefling.spellcasting.remove_source(sibling_source)
    tiefling.senses.remove_sense_mode_source(truesight_source)


def _cast_tiefling_darkness(tiefling: Entity, position: tuple[int, int]) -> None:
    Entity.update_all_entities_senses(max_distance=40)
    result = _action(tiefling, "spell.darkness").instantiate(
        end_position=position,
    ).apply()
    assert result is not None
    assert not result.canceled, result.status_message
    assert result.phase is EventPhase.COMPLETION


def test_removing_tiefling_origin_drops_its_owned_darkness_concentration() -> None:
    tiefling = create_test_entity(
        source_id=uuid4(),
        name="Tiefling",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    apply_origin(tiefling, _resolved(Species.TIEFLING), character_level=5)
    _cast_tiefling_darkness(tiefling, (2, 1))
    darkness = _action(tiefling, "spell.darkness")
    assert darkness.active_concentration_slot_uuid is not None
    assert "Concentrating" in tiefling.active_conditions

    remove_origin(tiefling)

    assert "Concentrating" not in tiefling.active_conditions
    _assert_origin_removed(tiefling)


def test_removing_tiefling_origin_preserves_class_darkness_concentration() -> None:
    tiefling = create_test_entity(
        source_id=uuid4(),
        name="Tiefling Sorcerer",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    apply_origin(tiefling, _resolved(Species.TIEFLING), character_level=5)
    _cast_tiefling_darkness(tiefling, (2, 1))
    origin_darkness = _action(tiefling, "spell.darkness")
    origin_slot_uuid = origin_darkness.active_concentration_slot_uuid
    assert origin_slot_uuid is not None
    truesight_source = uuid4()
    tiefling.senses.add_sense_mode_source(
        truesight_source,
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60),
    )

    class_source = uuid4()
    tiefling.spellcasting.add_source(
        class_source,
        "charisma",
        provider_id="class.sorcerer",
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=5,
        maximum_spell_rank=3,
        ritual_policy=RitualPreparationPolicy.NONE,
    )
    tiefling.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=40)
    result = Darkness(
        source_entity_uuid=tiefling.uuid,
        spellcasting_source_id=class_source,
        cast_at_level=2,
        alt_skip_slot=True,
        end_position=(3, 1),
        template=False,
    ).apply()
    assert result is not None
    assert not result.canceled, result.status_message
    assert result.phase is EventPhase.COMPLETION
    concentration = tiefling.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    class_slot_uuid = concentration.get_slot_by_spell_name("Darkness")
    assert class_slot_uuid is not None
    assert class_slot_uuid != origin_slot_uuid

    remove_origin(tiefling)

    concentration = tiefling.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert class_slot_uuid in concentration.concentration_slots
    assert set(tiefling.spellcasting.sources) == {class_source}
    assert tiefling.remove_condition("Concentrating")
    assert tiefling.spellcasting.remove_source(class_source)
    tiefling.senses.remove_sense_mode_source(truesight_source)


def test_origin_removal_rejects_a_modifier_moved_to_a_foreign_channel() -> None:
    entity = create_test_entity(
        source_id=uuid4(),
        name="Human",
        config=EntityConfig(),
    )
    receipt = apply_origin(entity, _resolved(Species.HUMAN), character_level=1)
    ability, modifier_uuid = receipt.ability_score_modifier_ids[0]
    modifier = entity.ability_scores.get_ability(
        ability,
    ).ability_score.self_static.value_modifiers.pop(modifier_uuid)
    entity.health.max_hit_points_bonus.self_static.value_modifiers[
        modifier_uuid
    ] = modifier

    with pytest.raises(RuntimeError, match="modifier ownership changed"):
        remove_origin(entity)

    assert entity.character_grant_receipt(ORIGIN_STEP_ID) is receipt
    assert entity.applied_origin_state is not None
    assert NumericalModifier.get(modifier_uuid) is modifier


def test_tiefling_darkness_rejects_a_same_uuid_foreign_binding_before_cleanup() -> None:
    entity = create_test_entity(
        source_id=uuid4(),
        name="Tiefling",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    receipt = apply_origin(entity, _resolved(Species.TIEFLING), character_level=5)
    _cast_tiefling_darkness(entity, (2, 1))
    darkness_uuid = receipt.darkness_root_owner_action_uuids[0]
    original = next(
        action for action in entity.registered_actions if action.uuid == darkness_uuid
    )
    slot_uuid = original.active_concentration_slot_uuid
    assert slot_uuid is not None
    assert entity.unregister_action_by_uuid(darkness_uuid)
    source_id = receipt.spell_source_ids[0]
    replacement = Darkness(
        uuid=darkness_uuid,
        source_entity_uuid=entity.uuid,
        caster_level=5,
        cast_at_level=2,
        spellcasting_source_id=source_id,
        alt_skip_slot=True,
        template=True,
        semantic_key="spell.darkness",
        behavior_binding=BehaviorBinding(
            behavior_id="spell.darkness",
            provided_by_id="fixture.foreign.darkness",
            origin_root_id="fixture.foreign",
            runtime_owner_uuid=entity.uuid,
        ),
    )
    entity.register_action(replacement)

    with pytest.raises(RuntimeError, match="Darkness root ownership changed"):
        remove_origin(entity)

    assert slot_uuid in entity.active_conditions["Concentrating"].concentration_slots
    assert entity.character_grant_receipt(ORIGIN_STEP_ID) is receipt
