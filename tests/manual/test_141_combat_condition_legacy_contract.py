"""Exact dispositions and restored composition checks for combat conditions."""

from dataclasses import dataclass
from typing import Literal

from dnd.conditions import (
    Blinded,
    Dashing,
    Dodging,
    Grappled,
    Poisoned,
    Prone,
    Restrained,
)
from dnd.core.modifiers import AdvantageStatus
from tests.engine.test_standard_conditions import (
    apply_to_target,
    configured_entity,
    reset_condition_state,
)


CoverageStatus = Literal["active", "strengthened", "stale"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived combat-condition case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_141_combat_condition_legacy_contract.py"
EB08_FILE = "tests/engine/test_standard_conditions.py"
SENSORY_SELECTOR = (
    f"{EB08_FILE}::test_eb_08_001_blinded_and_deafened_apply_sensory_failures"
)
CHARMED_SELECTOR = (
    f"{EB08_FILE}::"
    "test_eb_08_002_charmed_blocks_attacks_and_helps_charmer_social_checks"
)
PRESSURE_SELECTOR = (
    f"{EB08_FILE}::"
    "test_eb_08_003_poisoned_and_frightened_penalize_attacks_and_checks"
)
CONTROL_SELECTOR = (
    f"{EB08_FILE}::"
    "test_eb_08_004_grappled_incapacitated_and_restrained_limit_actions"
)
PRONE_SELECTOR = (
    f"{EB08_FILE}::test_eb_08_005_prone_uses_distance_context_for_incoming_attacks"
)
SEVERE_SELECTOR = (
    f"{EB08_FILE}::test_eb_08_006_severe_conditions_own_direct_denial_transforms"
)
LIFECYCLE_SELECTOR = (
    f"{EB08_FILE}::test_eb_08_012_standard_condition_removal_cleans_owned_state"
)
ACTION_STATE_SELECTOR = (
    f"{THIS_FILE}::test_dashing_and_dodging_apply_and_clean_their_exact_modifiers"
)
COMPOSITION_SELECTOR = (
    f"{THIS_FILE}::"
    "test_condition_modifiers_compose_and_clean_up_by_independent_owner"
)


COMBAT_CONDITION_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_blinded": LegacyCoverage(
        "strengthened",
        SENSORY_SELECTOR,
        "Maintained coverage asserts outgoing attack, incoming attack, skill, and cleanup facts.",
    ),
    "test_charmed": LegacyCoverage(
        "strengthened",
        CHARMED_SELECTOR,
        "Maintained coverage also proves the effect is contextual to the charmer.",
    ),
    "test_dashing": LegacyCoverage(
        "active",
        ACTION_STATE_SELECTOR,
        "The direct condition lifecycle and exact movement delta are restored.",
    ),
    "test_deafened": LegacyCoverage(
        "strengthened",
        SENSORY_SELECTOR,
        "Maintained coverage asserts both hearing-dependent skill families.",
    ),
    "test_dodging": LegacyCoverage(
        "active",
        ACTION_STATE_SELECTOR,
        "The DEX-save and incoming-attack modifiers plus cleanup are restored.",
    ),
    "test_frightened": LegacyCoverage(
        "strengthened",
        PRESSURE_SELECTOR,
        "Maintained coverage proves the penalty is conditional on sensing the source.",
    ),
    "test_grappled": LegacyCoverage(
        "active",
        CONTROL_SELECTOR,
        "Maintained coverage preserves movement denial without denying the action bucket.",
    ),
    "test_incapacitated": LegacyCoverage(
        "strengthened",
        CONTROL_SELECTOR,
        "Maintained coverage asserts every denied action-economy channel.",
    ),
    "test_paralyzed": LegacyCoverage(
        "strengthened",
        SEVERE_SELECTOR,
        "The rule effects remain covered under direct transform ownership.",
    ),
    "test_poisoned": LegacyCoverage(
        "strengthened",
        PRESSURE_SELECTOR,
        "Maintained coverage asserts attacks and multiple ability-check families.",
    ),
    "test_prone": LegacyCoverage(
        "strengthened",
        PRONE_SELECTOR,
        "Maintained coverage distinguishes adjacent and distant incoming attacks.",
    ),
    "test_restrained": LegacyCoverage(
        "strengthened",
        CONTROL_SELECTOR,
        "Maintained coverage asserts movement, attack, save, and incoming pressure.",
    ),
    "test_stunned": LegacyCoverage(
        "strengthened",
        SEVERE_SELECTOR,
        "Direct gates, STR/DEX auto-fail, incoming advantage, absent fabricated child, and exact cleanup are asserted.",
    ),
    "test_unconscious": LegacyCoverage(
        "strengthened",
        SEVERE_SELECTOR,
        "Direct STR/DEX auto-fail, visual/action denial, range-sensitive attack effects, and exact cleanup are asserted.",
    ),
    "test_multiple_disadvantages": LegacyCoverage(
        "active",
        COMPOSITION_SELECTOR,
        "Independent disadvantage owners and partial cleanup are restored.",
    ),
    "test_advantage_disadvantage_cancel": LegacyCoverage(
        "active",
        COMPOSITION_SELECTOR,
        "Cross-entity prone advantage cancels poisoned disadvantage.",
    ),
    "test_incapacitated_chain": LegacyCoverage(
        "strengthened",
        SEVERE_SELECTOR,
        "The old concrete Incapacitated-child assertion is intentionally inverted: severe conditions now own neutral denial directly.",
    ),
    "test_stacking_movement_restrictions": LegacyCoverage(
        "active",
        COMPOSITION_SELECTOR,
        "Independent zero-speed owners survive partial removal.",
    ),
}


def test_combat_condition_manifest_accounts_for_all_18_cases() -> None:
    """Every archived combat-condition case has a reviewed live disposition."""
    assert len(COMBAT_CONDITION_LEGACY_CASES) == 18
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in COMBAT_CONDITION_LEGACY_CASES.items()
    )


def test_dashing_and_dodging_apply_and_clean_their_exact_modifiers() -> None:
    """Dashing and Dodging keep independent, reversible rule ownership."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")
    attacker = configured_entity("Attacker", (3, 1), "heroes")
    base_speed = target.action_economy.current_speed()

    apply_to_target(Dashing, source, target)
    assert target.action_economy.movement.normalized_score == base_speed * 2
    target.remove_condition("Dashing")
    assert target.action_economy.movement.normalized_score == base_speed

    apply_to_target(Dodging, source, target)
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert (
        target.equipment.ac_bonus.outgoing_advantage
        is AdvantageStatus.DISADVANTAGE
    )
    target.remove_condition("Dodging")
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        is AdvantageStatus.NONE
    )
    assert target.equipment.ac_bonus.outgoing_advantage is AdvantageStatus.NONE


def test_condition_modifiers_compose_and_clean_up_by_independent_owner() -> None:
    """Stacked conditions cancel or persist according to their own lifecycles."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    attacker = configured_entity("Attacker", (2, 1), "heroes")
    target = configured_entity("Target", (3, 1), "monsters")

    apply_to_target(Poisoned, source, attacker)
    apply_to_target(Blinded, source, attacker)
    assert attacker.equipment.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    attacker.remove_condition("Poisoned")
    assert attacker.equipment.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    attacker.remove_condition("Blinded")
    assert attacker.equipment.attack_bonus.advantage is AdvantageStatus.NONE

    apply_to_target(Poisoned, source, attacker)
    apply_to_target(Prone, source, target)
    attack_bonus = attacker.attack_bonus(target_entity_uuid=target.uuid)
    attack_bonus.set_from_target(target.ac_bonus(attacker.uuid))
    assert attack_bonus.advantage is AdvantageStatus.NONE
    attack_bonus.reset_from_target()

    apply_to_target(Grappled, attacker, target)
    apply_to_target(Restrained, attacker, target)
    assert target.action_economy.movement.normalized_score == 0
    target.remove_condition("Grappled")
    assert target.action_economy.movement.normalized_score == 0
    target.remove_condition("Restrained")
    assert target.action_economy.movement.normalized_score == 30
