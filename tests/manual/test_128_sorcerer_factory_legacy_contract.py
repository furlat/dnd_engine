"""Active Sorcerer factory regressions displaced by the July test rework.

``to_archive/examples/test_sorcerer_factory.py`` owns 77 named checks, but its
custom ``__main__`` runner is not collected by pytest.  This module restores
the missing behavioral contracts and records the exact active selector for
every legacy ID.  A selector in another file means that current test already
asserts the same invariant; local selectors cover behavior that had no active
equivalent.

The local cases intentionally use tables for level/configuration progression,
spell slots, metamagic eligibility, and Font of Magic conversions.  Combat
cases remain separate because their failure modes and cleanup boundaries are
different.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import pytest
from pydantic import ValidationError

from dnd.actions import SpellAction
from dnd.actions_functional import get_available_actions
from dnd.classes.sorcerer import SP_TO_SLOT_COST
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.core.base_actions import TargetType, spell_slot_cost_type
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import AbilityName, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import (
    AutoHitModifier,
    AutoHitStatus,
    NumericalModifier,
)
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.utils import (
    force_spell_attack_hit,
    get_hp,
    remove_spell_attack_modifier,
    reset_combat_state,
    set_hp,
)


THIS_FILE = "tests/manual/test_128_sorcerer_factory_legacy_contract.py"
BOOK_FILE = "tests/engine_book/test_chapter_16_class_features.py"
OVERRIDE_FILE = "tests/manual/test_126_action_override_runtime.py"

LEVEL_SELECTOR = f"{THIS_FILE}::test_sorcerer_level_progression"
CONFIG_SELECTOR = f"{THIS_FILE}::test_sorcerer_config_validation"
CUSTOM_SPELL_SELECTOR = (
    f"{THIS_FILE}::test_custom_spell_configuration_replaces_factory_defaults"
)
EQUIPMENT_SELECTOR = (
    f"{THIS_FILE}::test_quarterstaff_preset_equips_the_requested_weapon"
)
IDENTITY_SELECTOR = (
    f"{THIS_FILE}::test_factory_preserves_requested_position_and_faction"
)
METAMAGIC_DISCOVERY_SELECTOR = (
    f"{THIS_FILE}::test_metamagic_discovery_matches_the_level_configuration"
)
METAMAGIC_RESOURCE_SELECTOR = (
    f"{THIS_FILE}::test_metamagic_activation_spends_and_gates_sorcery_points"
)
METAMAGIC_EXCLUSIVITY_SELECTOR = (
    f"{THIS_FILE}::test_only_one_pending_metamagic_can_be_active"
)
TWINNED_FILTER_SELECTOR = (
    f"{THIS_FILE}::test_twinned_does_not_retarget_self_spells"
)
QUICKENED_FILTER_SELECTOR = (
    f"{THIS_FILE}::test_quickened_changes_only_action_cost_spells_and_survives_nonspell_actions"
)
QUICKENED_CAST_SELECTOR = (
    f"{THIS_FILE}::test_quickened_spell_cast_uses_bonus_action_and_deals_damage"
)
QUICKENED_MISS_SELECTOR = (
    f"{THIS_FILE}::test_quickened_cleanup_runs_after_a_committed_spell_miss"
)
QUICKENED_TURN_SELECTOR = (
    f"{THIS_FILE}::test_quickened_and_regular_spell_resolve_in_one_turn"
)
TWINNED_CAST_SELECTOR = (
    f"{THIS_FILE}::test_twinned_hold_person_applies_both_targets_and_cleans_override"
)
DISTANT_CAST_SELECTOR = (
    f"{THIS_FILE}::test_distant_spell_executes_at_close_range_then_restores_templates"
)
FONT_SLOT_TO_SP_SELECTOR = (
    f"{THIS_FILE}::test_font_of_magic_converts_slots_to_sorcery_points"
)
FONT_SP_TO_SLOT_SELECTOR = (
    f"{THIS_FILE}::test_font_of_magic_converts_sorcery_points_to_slots"
)
FONT_GATING_SELECTOR = (
    f"{THIS_FILE}::test_font_of_magic_rejects_unavailable_or_unaffordable_conversion"
)
FONT_COUNT_SELECTOR = (
    f"{THIS_FILE}::test_font_of_magic_registers_only_owned_slot_levels"
)
FONT_COMPOSITION_SELECTOR = (
    f"{THIS_FILE}::test_font_conversion_can_fund_quickened_in_the_same_turn"
)
SHIELD_SELECTOR = (
    f"{THIS_FILE}::test_factory_registers_the_shield_reaction"
)
DEATH_SELECTOR = (
    f"{THIS_FILE}::test_death_does_not_corrupt_sorcerer_feature_state"
)

BOOK_QUICKENED_SELECTOR = (
    f"{BOOK_FILE}::test_eb_16_004_sorcerer_quickened_spell_overrides_and_cleanup"
)
BOOK_METAMAGIC_SELECTOR = (
    f"{BOOK_FILE}::test_eb_16_016_sorcerer_font_of_magic_twinned_and_distant_overrides"
)
BOOK_DRACONIC_SELECTOR = (
    f"{BOOK_FILE}::test_eb_16_017_sorcerer_draconic_resilience_and_elemental_affinity"
)
OVERRIDE_CONCENTRATION_SELECTOR = (
    f"{OVERRIDE_FILE}::test_damage_breaks_multitarget_concentration_and_all_linked_effects"
)


# Every legacy ID is explicit.  Existing selectors are used only where the
# active test asserts the same behavior, avoiding a second copy of that case.
LEGACY_ID_TO_ACTIVE_SELECTOR: dict[str, str] = {
    "SF-A1": LEVEL_SELECTOR,
    "SF-A2": LEVEL_SELECTOR,
    "SF-A3": LEVEL_SELECTOR,
    "SF-A4": CONFIG_SELECTOR,
    "SF-A5": CONFIG_SELECTOR,
    "SF-B1": LEVEL_SELECTOR,
    "SF-B2": LEVEL_SELECTOR,
    "SF-B3": METAMAGIC_RESOURCE_SELECTOR,
    "SF-B4": METAMAGIC_RESOURCE_SELECTOR,
    "SF-C1": METAMAGIC_RESOURCE_SELECTOR,
    "SF-C2": BOOK_QUICKENED_SELECTOR,
    "SF-C3": QUICKENED_CAST_SELECTOR,
    "SF-C4": BOOK_QUICKENED_SELECTOR,
    "SF-D1": BOOK_METAMAGIC_SELECTOR,
    "SF-D2": TWINNED_CAST_SELECTOR,
    "SF-D3": TWINNED_CAST_SELECTOR,
    "SF-E1": BOOK_METAMAGIC_SELECTOR,
    "SF-E2": DISTANT_CAST_SELECTOR,
    "SF-F1": FONT_SLOT_TO_SP_SELECTOR,
    "SF-F2": FONT_SP_TO_SLOT_SELECTOR,
    "SF-F3": FONT_GATING_SELECTOR,
    "SF-G1": BOOK_DRACONIC_SELECTOR,
    "SF-G2": BOOK_DRACONIC_SELECTOR,
    "SF-G3": BOOK_DRACONIC_SELECTOR,
    "SF-H1": QUICKENED_TURN_SELECTOR,
    "SF-H2": QUICKENED_FILTER_SELECTOR,
    "SF-H3": QUICKENED_FILTER_SELECTOR,
    "SF-H4": QUICKENED_TURN_SELECTOR,
    "SF-H5": METAMAGIC_EXCLUSIVITY_SELECTOR,
    "SF-I1": BOOK_METAMAGIC_SELECTOR,
    "SF-I2": BOOK_METAMAGIC_SELECTOR,
    "SF-I3": TWINNED_FILTER_SELECTOR,
    "SF-I4": TWINNED_CAST_SELECTOR,
    "SF-I5": TWINNED_CAST_SELECTOR,
    "SF-I6": METAMAGIC_RESOURCE_SELECTOR,
    "SF-J1": BOOK_METAMAGIC_SELECTOR,
    "SF-J2": BOOK_METAMAGIC_SELECTOR,
    "SF-J3": DISTANT_CAST_SELECTOR,
    "SF-J4": DISTANT_CAST_SELECTOR,
    "SF-J5": BOOK_METAMAGIC_SELECTOR,
    "SF-K1": METAMAGIC_EXCLUSIVITY_SELECTOR,
    "SF-K2": METAMAGIC_EXCLUSIVITY_SELECTOR,
    "SF-K3": QUICKENED_FILTER_SELECTOR,
    "SF-K4": QUICKENED_FILTER_SELECTOR,
    "SF-K5": QUICKENED_MISS_SELECTOR,
    "SF-L1": FONT_SLOT_TO_SP_SELECTOR,
    "SF-L2": BOOK_METAMAGIC_SELECTOR,
    "SF-L3": BOOK_METAMAGIC_SELECTOR,
    "SF-L4": FONT_SP_TO_SLOT_SELECTOR,
    "SF-L5": FONT_SLOT_TO_SP_SELECTOR,
    "SF-L6": FONT_GATING_SELECTOR,
    "SF-M1": LEVEL_SELECTOR,
    "SF-M2": LEVEL_SELECTOR,
    "SF-M3": BOOK_DRACONIC_SELECTOR,
    "SF-M4": BOOK_DRACONIC_SELECTOR,
    "SF-M5": BOOK_DRACONIC_SELECTOR,
    "SF-N1": LEVEL_SELECTOR,
    "SF-N2": CUSTOM_SPELL_SELECTOR,
    "SF-N3": EQUIPMENT_SELECTOR,
    "SF-N4": IDENTITY_SELECTOR,
    "SF-N5": CONFIG_SELECTOR,
    "SF-O1": LEVEL_SELECTOR,
    "SF-O2": LEVEL_SELECTOR,
    "SF-O3": LEVEL_SELECTOR,
    "SF-O4": LEVEL_SELECTOR,
    "SF-P1": METAMAGIC_DISCOVERY_SELECTOR,
    "SF-P2": METAMAGIC_DISCOVERY_SELECTOR,
    "SF-P3": METAMAGIC_DISCOVERY_SELECTOR,
    "SF-P4": FONT_COUNT_SELECTOR,
    "SF-Q1": BOOK_METAMAGIC_SELECTOR,
    "SF-Q2": BOOK_METAMAGIC_SELECTOR,
    "SF-Q3": BOOK_METAMAGIC_SELECTOR,
    "SF-R1": QUICKENED_TURN_SELECTOR,
    "SF-R2": OVERRIDE_CONCENTRATION_SELECTOR,
    "SF-R3": FONT_COMPOSITION_SELECTOR,
    "SF-R4": SHIELD_SELECTOR,
    "SF-R5": DEATH_SELECTOR,
}


@pytest.fixture(autouse=True)
def reset_sorcerer_state() -> None:
    """Give every regression an isolated registry and open combat grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    get_map().create_rectangle(0, 0, 30, 12)


@dataclass(frozen=True)
class SorcererLevelCase:
    """Expected factory surfaces for one representative Sorcerer level."""

    case_name: str
    level: int
    metamagic_choices: Optional[list[str]]
    asi_4: Optional[list[tuple[AbilityName, int]]]
    asi_8: Optional[list[tuple[AbilityName, int]]]
    asi_12: Optional[list[tuple[AbilityName, int]]]
    expected_proficiency: int
    expected_slots: dict[int, int]
    expected_sorcery_points: Optional[int]
    expected_hp: Optional[int] = None
    expected_charisma: Optional[int] = None
    expected_constitution: Optional[int] = None


LEVEL_CASES = (
    SorcererLevelCase(
        case_name="level-1-baseline",
        level=1,
        metamagic_choices=None,
        asi_4=None,
        asi_8=None,
        asi_12=None,
        expected_proficiency=2,
        expected_slots={1: 2},
        expected_sorcery_points=None,
        expected_hp=9,
        expected_charisma=17,
        expected_constitution=14,
    ),
    SorcererLevelCase(
        case_name="level-2-font-of-magic",
        level=2,
        metamagic_choices=None,
        asi_4=None,
        asi_8=None,
        asi_12=None,
        expected_proficiency=2,
        expected_slots={1: 3},
        expected_sorcery_points=2,
    ),
    SorcererLevelCase(
        case_name="level-3-slot-progression",
        level=3,
        metamagic_choices=["quickened", "twinned"],
        asi_4=None,
        asi_8=None,
        asi_12=None,
        expected_proficiency=2,
        expected_slots={1: 4, 2: 2},
        expected_sorcery_points=3,
    ),
    SorcererLevelCase(
        case_name="level-5-slot-and-hp-progression",
        level=5,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        asi_8=None,
        asi_12=None,
        expected_proficiency=3,
        expected_slots={1: 4, 2: 3, 3: 2},
        expected_sorcery_points=5,
        expected_hp=37,
    ),
    SorcererLevelCase(
        case_name="level-7-slot-progression",
        level=7,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        asi_8=None,
        asi_12=None,
        expected_proficiency=3,
        expected_slots={1: 4, 2: 3, 3: 3, 4: 1},
        expected_sorcery_points=7,
    ),
    SorcererLevelCase(
        case_name="level-9-slot-progression",
        level=9,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
        asi_12=None,
        expected_proficiency=4,
        expected_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
        expected_sorcery_points=9,
    ),
    SorcererLevelCase(
        case_name="level-10-constitution-asi",
        level=10,
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
        asi_12=None,
        expected_proficiency=4,
        expected_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
        expected_sorcery_points=10,
        expected_hp=82,
        expected_charisma=19,
        expected_constitution=16,
    ),
    SorcererLevelCase(
        case_name="level-10-split-asi",
        level=10,
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("charisma", 1), ("constitution", 1)],
        asi_12=None,
        expected_proficiency=4,
        expected_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
        expected_sorcery_points=10,
        expected_charisma=20,
        expected_constitution=15,
    ),
    SorcererLevelCase(
        case_name="level-15-slot-progression",
        level=15,
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
        asi_12=[("dexterity", 2)],
        expected_proficiency=5,
        expected_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
        expected_sorcery_points=15,
    ),
)


def create_level_case(case: SorcererLevelCase) -> Entity:
    """Create one Sorcerer using the explicit inputs from a progression row."""
    return create_sorcerer(
        SorcererConfig(
            level=case.level,
            name=f"Level {case.level} Regression Sorcerer",
            position=(1, 1),
            faction="heroes",
            metamagic_choices=case.metamagic_choices,
            asi_4=case.asi_4,
            asi_8=case.asi_8,
            asi_12=case.asi_12,
        )
    )


def create_level_five(
    *,
    name: str = "Sorcerer Regression",
    metamagic_choices: Optional[list[str]] = None,
    spell_names: Optional[list[str]] = None,
) -> Entity:
    """Create the standard level-five fixture used by behavior tests."""
    return create_sorcerer(
        SorcererConfig(
            level=5,
            name=name,
            position=(1, 1),
            faction="heroes",
            metamagic_choices=(
                metamagic_choices
                if metamagic_choices is not None
                else ["quickened", "twinned"]
            ),
            asi_4=[("charisma", 2)],
            spell_names=spell_names,
        )
    )


def action_template(entity: Entity, name: str):
    """Return one exact action template and fail with a useful assertion."""
    template = entity.get_action_template(name)
    assert template is not None, f"Expected registered action {name!r}"
    return template


def spell_template(entity: Entity, name: str) -> SpellAction:
    """Return one exact spell template."""
    template = action_template(entity, name)
    assert isinstance(template, SpellAction)
    return template


def force_save_result(
    entity: Entity,
    ability_name: AbilityName,
    *,
    succeeds: bool,
) -> None:
    """Make an ordinary saving throw deterministic without natural extremes."""
    saving_throw = entity.saving_throws.get_saving_throw(ability_name)
    saving_throw.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Sorcerer regression {ability_name} save",
            value=100 if succeeds else -100,
        )
    )


def force_spell_attack_miss(entity: Entity) -> UUID:
    """Install an explicit auto-miss on the spell-attack channel."""
    modifier = AutoHitModifier(
        name="Forced Sorcerer Regression Spell Miss",
        value=AutoHitStatus.AUTOMISS,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return (
        entity.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(
            modifier
        )
    )


def assert_spell_slots(entity: Entity, expected: dict[int, int]) -> None:
    """Assert every owned and unowned slot level, not just one sample."""
    for slot_level in range(1, 10):
        slot = entity.action_economy._get_spell_slot_value(slot_level)
        assert slot.normalized_score == expected.get(slot_level, 0)


def test_legacy_sorcerer_manifest_accounts_for_all_77_cases() -> None:
    """The active coverage map cannot silently omit or rename a legacy ID."""
    section_counts = {
        "A": 5,
        "B": 4,
        "C": 4,
        "D": 3,
        "E": 2,
        "F": 3,
        "G": 3,
        "H": 5,
        "I": 6,
        "J": 5,
        "K": 5,
        "L": 6,
        "M": 5,
        "N": 5,
        "O": 4,
        "P": 4,
        "Q": 3,
        "R": 5,
    }
    expected_ids = {
        f"SF-{section}{number}"
        for section, count in section_counts.items()
        for number in range(1, count + 1)
    }

    assert len(expected_ids) == 77
    assert set(LEGACY_ID_TO_ACTIVE_SELECTOR) == expected_ids
    assert all(
        selector.startswith("tests/") and "::test_" in selector
        for selector in LEGACY_ID_TO_ACTIVE_SELECTOR.values()
    )


@pytest.mark.parametrize(
    "case",
    LEVEL_CASES,
    ids=lambda case: case.case_name,
)
def test_sorcerer_level_progression(case: SorcererLevelCase) -> None:
    """SF-A1-A3/B1-B2/M1-M2/N1/O1-O4: explicit progression table."""
    sorcerer = create_level_case(case)

    assert sorcerer.proficiency_bonus.normalized_score == case.expected_proficiency
    assert_spell_slots(sorcerer, case.expected_slots)

    if case.expected_sorcery_points is None:
        assert not sorcerer.action_economy.has_resource("sorcery_points")
    else:
        assert sorcerer.action_economy.has_resource("sorcery_points")
        assert (
            sorcerer.action_economy.get_resource_current("sorcery_points")
            == case.expected_sorcery_points
        )

    if case.expected_hp is not None:
        assert get_hp(sorcerer) == case.expected_hp
    if case.expected_charisma is not None:
        assert (
            sorcerer.ability_scores.charisma.ability_score.score
            == case.expected_charisma
        )
    if case.expected_constitution is not None:
        assert (
            sorcerer.ability_scores.constitution.ability_score.score
            == case.expected_constitution
        )


INVALID_CONFIG_CASES: tuple[
    tuple[str, Callable[[], SorcererConfig], str],
    ...,
] = (
    (
        "metamagic-before-level-three",
        lambda: SorcererConfig(
            level=1,
            name="Invalid Early Metamagic",
            metamagic_choices=["quickened", "twinned"],
        ),
        "before level 3",
    ),
    (
        "missing-level-three-metamagic",
        lambda: SorcererConfig(level=3, name="Invalid Missing Metamagic"),
        "requires 2 metamagic",
    ),
    (
        "wrong-level-three-metamagic-count",
        lambda: SorcererConfig(
            level=3,
            name="Invalid Metamagic Count",
            metamagic_choices=["quickened"],
        ),
        "requires exactly 2",
    ),
    (
        "missing-level-four-asi",
        lambda: SorcererConfig(
            level=4,
            name="Invalid Missing ASI",
            metamagic_choices=["quickened", "twinned"],
        ),
        "requires asi_4",
    ),
    (
        "same-level-one-ability-bonuses",
        lambda: SorcererConfig(
            level=1,
            name="Invalid Ability Bonuses",
            bonus_plus_2="charisma",
            bonus_plus_1="charisma",
        ),
        "must be different",
    ),
    (
        "duplicate-metamagic",
        lambda: SorcererConfig(
            level=3,
            name="Invalid Duplicate Metamagic",
            metamagic_choices=["quickened", "quickened"],
        ),
        "Duplicate",
    ),
)


@pytest.mark.parametrize(
    ("_case_name", "build_config", "message"),
    INVALID_CONFIG_CASES,
    ids=[case[0] for case in INVALID_CONFIG_CASES],
)
def test_sorcerer_config_validation(
    _case_name: str,
    build_config: Callable[[], SorcererConfig],
    message: str,
) -> None:
    """SF-A4/A5/N5: invalid level configuration is rejected at the boundary."""
    with pytest.raises(ValidationError, match=message):
        build_config()


def test_custom_spell_configuration_replaces_factory_defaults() -> None:
    """SF-N2: an explicit spell list replaces, rather than extends, defaults."""
    sorcerer = create_level_five(
        spell_names=["Fire Bolt", "Lightning Bolt"],
    )

    assert sorcerer.get_action_template("Fire Bolt") is not None
    assert sorcerer.get_action_template("Lightning Bolt") is not None
    assert sorcerer.get_action_template("Magic Missile") is None


def test_quarterstaff_preset_equips_the_requested_weapon() -> None:
    """SF-N3: starter-equipment configuration reaches the public loadout API."""
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=1,
            name="Quarterstaff Sorcerer",
            equipment_preset="quarterstaff",
        )
    )

    weapon = sorcerer.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert weapon is not None
    assert weapon.name == "Quarterstaff"


def test_factory_preserves_requested_position_and_faction() -> None:
    """SF-N4: placement and allegiance survive factory composition."""
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=1,
            name="Placed Sorcerer",
            position=(10, 5),
            faction="heroes",
        )
    )

    assert sorcerer.senses.position == (10, 5)
    assert sorcerer.faction == "heroes"


@dataclass(frozen=True)
class MetamagicDiscoveryCase:
    """Expected metamagic buttons for one level/configuration pair."""

    case_name: str
    level: int
    choices: Optional[list[str]]
    asi_4: Optional[list[tuple[AbilityName, int]]]
    asi_8: Optional[list[tuple[AbilityName, int]]]
    expected_actions: frozenset[str]


METAMAGIC_DISCOVERY_CASES = (
    MetamagicDiscoveryCase(
        case_name="level-2-no-metamagic",
        level=2,
        choices=None,
        asi_4=None,
        asi_8=None,
        expected_actions=frozenset(),
    ),
    MetamagicDiscoveryCase(
        case_name="level-3-two-selected-options",
        level=3,
        choices=["quickened", "distant"],
        asi_4=None,
        asi_8=None,
        expected_actions=frozenset({"Quickened Spell", "Distant Spell"}),
    ),
    MetamagicDiscoveryCase(
        case_name="level-10-three-selected-options",
        level=10,
        choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
        expected_actions=frozenset(
            {"Quickened Spell", "Twinned Spell", "Distant Spell"}
        ),
    ),
)


@pytest.mark.parametrize(
    "case",
    METAMAGIC_DISCOVERY_CASES,
    ids=lambda case: case.case_name,
)
def test_metamagic_discovery_matches_the_level_configuration(
    case: MetamagicDiscoveryCase,
) -> None:
    """SF-P1-P3: the factory registers exactly the selected metamagic set."""
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=case.level,
            name=case.case_name,
            metamagic_choices=case.choices,
            asi_4=case.asi_4,
            asi_8=case.asi_8,
        )
    )
    known_names = {"Quickened Spell", "Twinned Spell", "Distant Spell"}
    actual_names = {
        name
        for name in known_names
        if sorcerer.get_action_template(name) is not None
    }

    assert actual_names == case.expected_actions
    if case.level == 2:
        assert sorcerer.action_economy.has_resource("sorcery_points")
        assert sorcerer.action_economy.get_resource_current("sorcery_points") == 2


@pytest.mark.parametrize(
    (
        "action_name",
        "sorcery_points_to_spend_first",
        "expected_cost",
        "expected_valid",
        "expected_remaining",
    ),
    (
        ("Quickened Spell", 0, 2, True, 3),
        ("Quickened Spell", 4, 2, False, 1),
        ("Twinned Spell", 5, 1, False, 0),
    ),
    ids=(
        "quickened-spends-two",
        "quickened-rejects-one-point",
        "twinned-rejects-zero-points",
    ),
)
def test_metamagic_activation_spends_and_gates_sorcery_points(
    action_name: str,
    sorcery_points_to_spend_first: int,
    expected_cost: int,
    expected_valid: bool,
    expected_remaining: int,
) -> None:
    """SF-B3/B4/C1/I6: named-resource costs govern activation."""
    sorcerer = create_level_five()
    if sorcery_points_to_spend_first:
        sorcerer.action_economy.consume_resource(
            "sorcery_points",
            sorcery_points_to_spend_first,
        )

    metamagic = action_template(sorcerer, action_name)
    resource_costs = [
        cost.resource_cost
        for cost in metamagic.costs
        if cost.resource_name == "sorcery_points"
    ]

    assert resource_costs == [expected_cost]
    assert metamagic.pre_validate() is expected_valid

    if expected_valid:
        event = metamagic.instantiate().apply()
        assert event is not None
        assert not event.canceled

    assert (
        sorcerer.action_economy.get_resource_current("sorcery_points")
        == expected_remaining
    )


def test_only_one_pending_metamagic_can_be_active() -> None:
    """SF-H5/K1/K2: pending metamagic persists and blocks every second option."""
    sorcerer = create_level_five()
    quickened = action_template(sorcerer, "Quickened Spell")
    event = quickened.instantiate().apply()

    assert event is not None
    assert not event.canceled
    assert "MetamagicActive" in sorcerer.active_conditions
    assert not action_template(sorcerer, "Quickened Spell").pre_validate()
    assert not action_template(sorcerer, "Twinned Spell").pre_validate()
    assert "MetamagicActive" in sorcerer.active_conditions


def test_twinned_does_not_retarget_self_spells() -> None:
    """SF-I3: Twinned leaves SELF spells alone.

    EB-16-016 already covers eligible entity spells and rejects AoE/multi-target
    spells; this case restores the distinct SELF-target exclusion.
    """
    sorcerer = create_level_five(
        spell_names=["Fire Bolt", "Hold Person", "False Life"],
    )
    false_life = spell_template(sorcerer, "False Life")
    assert false_life.target_type is TargetType.SELF

    action_template(sorcerer, "Twinned Spell").instantiate().apply()

    assert false_life.alt_target_type is None
    assert false_life.alt_target_count is None
    assert false_life.alt_extra_costs == []


def test_quickened_changes_only_action_cost_spells_and_survives_nonspell_actions() -> None:
    """SF-H2/H3/K3/K4: filter, discovery cost, and pending lifecycle agree.

    EB-16-004 already checks the underlying Fire Bolt template override.  This
    regression adds the public discovery row and the non-spell execution edge.
    """
    sorcerer = create_level_five(
        spell_names=["Fire Bolt", "Misty Step"],
    )
    create_skeleton(name="Discovery Target", position=(2, 1))
    Entity.update_all_entities_senses()
    quickened = action_template(sorcerer, "Quickened Spell")
    quickened.instantiate().apply()

    fire_bolt = spell_template(sorcerer, "Fire Bolt")
    misty_step = spell_template(sorcerer, "Misty Step")
    dash = action_template(sorcerer, "Dash")
    dodge = action_template(sorcerer, "Dodge")

    assert fire_bolt.alt_cost_type == "bonus_actions"
    assert misty_step.alt_cost_type is None
    assert dash.alt_cost_type is None
    assert dodge.alt_cost_type is None

    fire_bolt_rows = [
        row
        for row in get_available_actions(sorcerer).all_actions
        if row.base_template_name == "Fire Bolt"
        or row.template_name == "Fire Bolt"
    ]
    assert fire_bolt_rows
    assert {row.cost_type for row in fire_bolt_rows} == {"bonus_actions"}

    dash_event = dash.instantiate().apply()
    assert dash_event is not None
    assert not dash_event.canceled
    assert "MetamagicActive" in sorcerer.active_conditions


def test_quickened_spell_cast_uses_bonus_action_and_deals_damage() -> None:
    """SF-C3: the factory's Quickened path reaches executable spell combat."""
    sorcerer = create_level_five(spell_names=["Fire Bolt"])
    target = create_skeleton(name="Quickened Target", position=(2, 1))
    set_hp(target, 100)
    Entity.update_all_entities_senses()

    action_template(sorcerer, "Quickened Spell").instantiate().apply()
    hit_modifier = force_spell_attack_hit(sorcerer)
    hp_before = get_hp(target)

    with fixed_dice_faces(*([2] * 20)):
        event = spell_template(sorcerer, "Fire Bolt").instantiate(
            target_entity_uuid=target.uuid
        ).apply()
    remove_spell_attack_modifier(sorcerer, hit_modifier)

    assert event is not None
    assert not event.canceled
    assert get_hp(target) < hp_before
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.actions.normalized_score == 1


def test_quickened_cleanup_runs_after_a_committed_spell_miss() -> None:
    """SF-K5: a completed miss consumes and removes pending metamagic."""
    sorcerer = create_level_five(spell_names=["Fire Bolt"])
    target = create_skeleton(name="Miss Target", position=(2, 1))
    set_hp(target, 100)
    Entity.update_all_entities_senses()

    action_template(sorcerer, "Quickened Spell").instantiate().apply()
    fire_bolt = spell_template(sorcerer, "Fire Bolt")
    miss_modifier = force_spell_attack_miss(sorcerer)
    hp_before = get_hp(target)

    with fixed_dice_faces(*([2] * 20)):
        event = fire_bolt.instantiate(target_entity_uuid=target.uuid).apply()
    remove_spell_attack_modifier(sorcerer, miss_modifier)

    assert event is not None
    assert not event.canceled
    assert get_hp(target) == hp_before
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert fire_bolt.alt_cost_type is None


@pytest.mark.parametrize(
    ("quickened_spell_name", "regular_spell_name"),
    (
        ("Fire Bolt", "Magic Missile"),
        ("Magic Missile", "Fire Bolt"),
    ),
    ids=("quickened-cantrip-then-action-spell", "quickened-slot-then-action-spell"),
)
def test_quickened_and_regular_spell_resolve_in_one_turn(
    quickened_spell_name: str,
    regular_spell_name: str,
) -> None:
    """SF-H1/H4/R1: bonus-action and ordinary spell costs remain independent."""
    sorcerer = create_level_five(
        spell_names=["Fire Bolt", "Magic Missile"],
    )
    target = create_skeleton(name="Full Turn Target", position=(2, 1))
    set_hp(target, 200)
    Entity.update_all_entities_senses()
    hit_modifier = force_spell_attack_hit(sorcerer)
    action_template(sorcerer, "Quickened Spell").instantiate().apply()

    hp_before = get_hp(target)
    quickened = spell_template(sorcerer, quickened_spell_name)
    with fixed_dice_faces(*([2] * 40)):
        first_event = quickened.instantiate(
            target_entity_uuid=target.uuid
        ).apply()

    assert first_event is not None
    assert not first_event.canceled
    assert get_hp(target) < hp_before
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.actions.normalized_score == 1

    hp_after_quickened = get_hp(target)
    regular = spell_template(sorcerer, regular_spell_name)
    with fixed_dice_faces(*([2] * 40)):
        if regular.effective_target_type is TargetType.POSITION_AOE:
            second_event = regular.instantiate(
                target_position=target.senses.position
            ).apply()
        else:
            second_event = regular.instantiate(
                target_entity_uuid=target.uuid
            ).apply()
    remove_spell_attack_modifier(sorcerer, hit_modifier)

    assert second_event is not None
    assert not second_event.canceled
    assert get_hp(target) < hp_after_quickened
    assert sorcerer.action_economy.actions.normalized_score == 0


def test_twinned_hold_person_applies_both_targets_and_cleans_override() -> None:
    """SF-D2/D3/I4/I5: factory metamagic reaches two spell applications."""
    sorcerer = create_level_five(spell_names=["Hold Person"])
    first = create_goblin(name="Twinned Target One", position=(2, 1))
    second = create_goblin(name="Twinned Target Two", position=(3, 1))
    Entity.update_all_entities_senses()
    force_save_result(first, "wisdom", succeeds=False)
    force_save_result(second, "wisdom", succeeds=False)

    action_template(sorcerer, "Twinned Spell").instantiate().apply()
    hold_person = spell_template(sorcerer, "Hold Person")

    assert hold_person.alt_target_type is TargetType.MULTI_ENTITY
    assert hold_person.alt_target_count == 2

    with fixed_dice_faces(2, 2):
        event = hold_person.instantiate(
            target_entity_uuid=first.uuid,
            extra_target_entity_uuids=[second.uuid],
        ).apply()

    assert event is not None
    assert not event.canceled
    assert "Hold Person" in first.active_conditions
    assert "Paralyzed" in first.active_conditions
    assert "Hold Person" in second.active_conditions
    assert "Paralyzed" in second.active_conditions
    assert "Concentrating" in sorcerer.active_conditions
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert hold_person.alt_target_type is None
    assert hold_person.alt_target_count is None


def test_distant_spell_executes_at_close_range_then_restores_templates() -> None:
    """SF-E2/J3/J4: Distant is permissive, spell-only, and self-cleaning."""
    sorcerer = create_level_five(
        metamagic_choices=["quickened", "distant"],
        spell_names=["Fire Bolt"],
    )
    target = create_skeleton(name="Distant Target", position=(2, 1))
    set_hp(target, 100)
    Entity.update_all_entities_senses()
    fire_bolt = spell_template(sorcerer, "Fire Bolt")
    dash = action_template(sorcerer, "Dash")
    dash_before = dash.model_dump()

    action_template(sorcerer, "Distant Spell").instantiate().apply()

    assert fire_bolt.alt_range == 240
    assert dash.model_dump() == dash_before
    hit_modifier = force_spell_attack_hit(sorcerer)
    with fixed_dice_faces(*([2] * 20)):
        event = fire_bolt.instantiate(target_entity_uuid=target.uuid).apply()
    remove_spell_attack_modifier(sorcerer, hit_modifier)

    assert event is not None
    assert not event.canceled
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert fire_bolt.alt_range is None


@pytest.mark.parametrize(
    (
        "slot_level",
        "sorcery_points_spent_first",
        "expected_sorcery_points",
        "expected_slots",
    ),
    (
        (1, 3, 3, 3),
        (2, 3, 4, 2),
        (3, 5, 3, 1),
        (1, 0, 5, 3),
    ),
    ids=(
        "level-1-slot-gains-1-sp",
        "level-2-slot-gains-2-sp",
        "level-3-slot-gains-3-sp",
        "gain-is-capped-at-maximum",
    ),
)
def test_font_of_magic_converts_slots_to_sorcery_points(
    slot_level: int,
    sorcery_points_spent_first: int,
    expected_sorcery_points: int,
    expected_slots: int,
) -> None:
    """SF-F1/L1/L2/L5: each slot value and the SP cap are explicit.

    EB-16-016 already samples the level-three conversion; the table retains
    the level-one/level-two boundaries and makes the cap behavior executable.
    """
    sorcerer = create_level_five()
    if sorcery_points_spent_first:
        sorcerer.action_economy.consume_resource(
            "sorcery_points",
            sorcery_points_spent_first,
        )
    conversion = action_template(sorcerer, f"Slot\u2192SP L{slot_level}")

    event = conversion.instantiate().apply()

    assert event is not None
    assert not event.canceled
    assert (
        sorcerer.action_economy.get_resource_current("sorcery_points")
        == expected_sorcery_points
    )
    slot = sorcerer.action_economy._get_spell_slot_value(slot_level)
    assert slot.normalized_score == expected_slots
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0


@pytest.mark.parametrize(
    ("slot_level", "expected_sorcery_points", "expected_slots"),
    (
        (1, 3, 4),
        (3, 0, 2),
    ),
    ids=("two-sp-creates-level-1-slot", "five-sp-creates-level-3-slot"),
)
def test_font_of_magic_converts_sorcery_points_to_slots(
    slot_level: int,
    expected_sorcery_points: int,
    expected_slots: int,
) -> None:
    """SF-F2/L4: affordable SP creates exactly one missing spell slot.

    EB-16-016 owns the equivalent level-two conversion (legacy SF-L3).
    """
    sorcerer = create_level_five()
    slot = sorcerer.action_economy._get_spell_slot_value(slot_level)
    original_slots = slot.normalized_score
    sorcerer.action_economy.consume(
        spell_slot_cost_type(slot_level),
        1,
        "sorcerer_regression_slot_use",
    )
    assert slot.normalized_score == original_slots - 1

    cost = SP_TO_SLOT_COST[slot_level]
    conversion = action_template(
        sorcerer,
        f"{cost}SP\u2192Slot L{slot_level}",
    )
    event = conversion.instantiate().apply()

    assert event is not None
    assert not event.canceled
    assert slot.normalized_score == expected_slots
    assert (
        sorcerer.action_economy.get_resource_current("sorcery_points")
        == expected_sorcery_points
    )
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0


def test_font_of_magic_rejects_unavailable_or_unaffordable_conversion() -> None:
    """SF-F3/L6: conversion is gated by both SP and owned slot levels."""
    sorcerer = create_level_five()
    sorcerer.action_economy.consume_resource("sorcery_points", 5)

    level_one = action_template(sorcerer, "2SP\u2192Slot L1")
    assert not level_one.pre_validate()
    assert sorcerer.get_action_template("6SP\u2192Slot L4") is None
    assert sorcerer.get_action_template("Slot\u2192SP L4") is None


def test_font_of_magic_registers_only_owned_slot_levels() -> None:
    """SF-P4: level-five Font of Magic owns exactly L1-L3 conversion pairs."""
    sorcerer = create_level_five()

    for slot_level in range(1, 4):
        sp_cost = SP_TO_SLOT_COST[slot_level]
        assert sorcerer.get_action_template(f"Slot\u2192SP L{slot_level}") is not None
        assert (
            sorcerer.get_action_template(f"{sp_cost}SP\u2192Slot L{slot_level}")
            is not None
        )

    for slot_level in range(4, 6):
        sp_cost = SP_TO_SLOT_COST[slot_level]
        assert sorcerer.get_action_template(f"Slot\u2192SP L{slot_level}") is None
        assert (
            sorcerer.get_action_template(f"{sp_cost}SP\u2192Slot L{slot_level}")
            is None
        )


def test_font_conversion_can_fund_quickened_in_the_same_turn() -> None:
    """SF-R3: a converted slot immediately funds a zero-action activation."""
    sorcerer = create_level_five()
    sorcerer.action_economy.consume_resource("sorcery_points", 4)
    quickened = action_template(sorcerer, "Quickened Spell")

    assert not quickened.pre_validate()

    conversion = action_template(sorcerer, "Slot\u2192SP L1")
    conversion_event = conversion.instantiate().apply()

    assert conversion_event is not None
    assert not conversion_event.canceled
    assert sorcerer.action_economy.get_resource_current("sorcery_points") == 2
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert quickened.pre_validate()

    quickened_event = quickened.instantiate().apply()

    assert quickened_event is not None
    assert not quickened_event.canceled
    assert sorcerer.action_economy.get_resource_current("sorcery_points") == 0
    assert "MetamagicActive" in sorcerer.active_conditions


def test_factory_registers_the_shield_reaction() -> None:
    """SF-R4: the completed factory actor owns Shield's reaction handler."""
    sorcerer = create_level_five()

    assert sorcerer.get_event_handler_by_name("Shield") is not None


def test_death_does_not_corrupt_sorcerer_feature_state() -> None:
    """SF-R5: death succeeds while persistent factory features remain coherent."""
    sorcerer = create_level_five()
    action_template(sorcerer, "Quickened Spell").instantiate().apply()

    assert {
        "Draconic Resilience",
        "Sorcery Points Feature",
        "MetamagicActive",
    } <= set(sorcerer.active_conditions)

    set_hp(sorcerer, 0)

    assert not sorcerer.has_hp
    assert {
        "Draconic Resilience",
        "Sorcery Points Feature",
        "MetamagicActive",
    } <= set(sorcerer.active_conditions)
