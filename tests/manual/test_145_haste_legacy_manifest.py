"""Exact migration dispositions for archived Haste spell and potion suites."""

from dataclasses import dataclass
from typing import Literal

from dnd.actions_functional import execute_use_action
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.core.condition_types import DurationType
from dnd.items.consumables import HASTE_POTION_RECIPE
from dnd.monsters.bestiary import create_skeleton
from dnd.spells.transmutation import HasteEffect
from tests.engine.test_monster_presets import (
    reset_monster_state,
)


CoverageStatus = Literal["active", "strengthened", "stale"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived Haste case's maintained replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


EB15_HASTE = (
    "tests/engine/test_spell_families.py::"
    "test_eb_15_011_haste_modifier_bundle_and_lethargy_cleanup"
)
HASTE_FILE = "tests/manual/test_125_haste_restricted_action.py"
THIS_FILE = "tests/manual/test_145_haste_legacy_manifest.py"
ORDER_SELECTOR = (
    f"{HASTE_FILE}::test_haste_attack_and_normal_attack_batches_are_order_independent"
)
SURGE_SELECTOR = (
    f"{HASTE_FILE}::"
    "test_haste_and_action_surge_preserve_both_extra_attack_batches"
)
SLOW_SELECTOR = (
    f"{HASTE_FILE}::"
    "test_slow_keeps_haste_and_surge_actions_but_suppresses_extra_attacks"
)
CLEANUP_SELECTOR = (
    f"{HASTE_FILE}::"
    "test_haste_cleanup_paths_remove_the_budget_and_apply_owned_lethargy"
)
POTION_SELECTOR = (
    "tests/manual/test_11_equipment_inventory_and_items.py::"
    "test_magic_condition_potions_preserve_magical_origin_and_haste_lethargy"
)
POTION_EXPIRY_SELECTOR = (
    f"{THIS_FILE}::"
    "test_potion_authored_haste_expires_after_exactly_ten_rounds"
)


HASTE_SPELL_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_1_haste_applies_buffs": LegacyCoverage(
        "strengthened",
        EB15_HASTE,
        "The maintained test asserts the full modifier bundle, typed restricted action grant, concentration link, and cleanup.",
    ),
    "test_2_haste_extra_attack_suppression": LegacyCoverage(
        "strengthened",
        ORDER_SELECTOR,
        "Both legal action orders and one-to-three pending Extra Attacks are asserted.",
    ),
    "test_3_haste_action_surge": LegacyCoverage(
        "strengthened",
        SURGE_SELECTOR,
        "Both surge orderings preserve two ordinary attack batches plus the restricted Haste attack.",
    ),
    "test_4_lethargy_on_concentration_break": LegacyCoverage(
        "strengthened",
        EB15_HASTE,
        "Concentration cleanup applies directly owned Haste Lethargy without a synthetic Incapacitated child.",
    ),
    "test_5_lethargy_on_ally": LegacyCoverage(
        "strengthened",
        EB15_HASTE,
        "The linked ally, rather than the caster, owns both Haste and its cleanup lethargy.",
    ),
    "test_6_haste_slow_interaction": LegacyCoverage(
        "strengthened",
        SLOW_SELECTOR,
        "The maintained parameterized contract preserves Haste actions while Slow suppresses Extra Attack.",
    ),
    "test_7_haste_slow_action_surge": LegacyCoverage(
        "strengthened",
        SLOW_SELECTOR,
        "The Action Surge branch is explicitly parameterized and consumes all three legal actions.",
    ),
    "test_8_lethargy_on_dispel": LegacyCoverage(
        "strengthened",
        CLEANUP_SELECTOR,
        "Direct removal and duration expiry share the exact owned cleanup path.",
    ),
    "test_9_lethargy_on_expiry": LegacyCoverage(
        "strengthened",
        CLEANUP_SELECTOR,
        "Duration expiry removes the grant and applies directly owned lethargy.",
    ),
    "test_10_haste_mid_turn_action_surge": LegacyCoverage(
        "strengthened",
        SURGE_SELECTOR,
        "The maintained inverse-order matrix covers a surge introduced before or after the first attack batch.",
    ),
}


HASTE_POTION_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_1_potion_applies_buffs": LegacyCoverage(
        "strengthened",
        POTION_SELECTOR,
        "The potion asserts speed, AC, DEX-save, and typed restricted-action facts.",
    ),
    "test_2_no_concentration": LegacyCoverage(
        "active",
        POTION_SELECTOR,
        "The item effect is explicitly asserted not to create Concentrating.",
    ),
    "test_3_lethargy_on_expiry": LegacyCoverage(
        "strengthened",
        POTION_EXPIRY_SELECTOR,
        "The actual potion-authored ten-round duration is progressed to natural expiry and owned lethargy.",
    ),
    "test_4_potion_consumed": LegacyCoverage(
        "strengthened",
        POTION_SELECTOR,
        "The maintained test checks both inventory removal and registry destruction.",
    ),
    "test_5_ea_suppression": LegacyCoverage(
        "strengthened",
        ORDER_SELECTOR,
        "Potion and spell create the same HasteEffect; the maintained matrix covers both legal action orders and preserves pending Extra Attack.",
    ),
}


def test_haste_legacy_manifests_account_for_all_15_cases() -> None:
    """Every archived Haste spell and potion case has an exact disposition."""
    assert len(HASTE_SPELL_LEGACY_CASES) == 10
    assert len(HASTE_POTION_LEGACY_CASES) == 5
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for ledger in (HASTE_SPELL_LEGACY_CASES, HASTE_POTION_LEGACY_CASES)
        for case, row in ledger.items()
    )


def test_potion_authored_haste_expires_after_exactly_ten_rounds() -> None:
    """The real potion duration survives nine ticks and expires on the tenth."""
    reset_monster_state(width=10, height=10)
    actor = create_skeleton(
        name="Haste Potion Auditor",
        position=(1, 1),
        faction="heroes",
    )
    potion = materialize_item(
        HASTE_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    potion_uuid = potion.uuid
    assert actor.loot_item(potion)
    base_ac = actor.equipment.ac_bonus.normalized_score
    base_movement = actor.action_economy.movement.normalized_score

    completion = execute_use_action(
        actor,
        potion.uuid,
        "Drink Haste Potion",
    )

    assert completion is not None and not completion.canceled
    haste = actor.active_conditions.get("Haste")
    assert isinstance(haste, HasteEffect)
    assert haste.duration.duration_type is DurationType.ROUNDS
    assert haste.duration.duration == 10
    assert "Concentrating" not in actor.active_conditions
    assert actor.equipment.ac_bonus.normalized_score == base_ac + 2
    assert actor.action_economy.movement.normalized_score == base_movement * 2
    assert actor.action_economy.resources["haste_action"].current == 1
    assert not actor.inventory.has_item(potion_uuid)
    assert BaseBlock.get(potion_uuid) is None

    for expected_remaining in range(9, 0, -1):
        assert not actor.advance_duration_condition(
            "Haste",
            skip_save_throw=True,
        )
        active_haste = actor.active_conditions.get("Haste")
        assert isinstance(active_haste, HasteEffect)
        assert active_haste.duration.duration == expected_remaining
        assert "Haste Lethargy" not in actor.active_conditions

    assert actor.advance_duration_condition(
        "Haste",
        skip_save_throw=True,
    )
    assert "Haste" not in actor.active_conditions
    assert "Haste Lethargy" in actor.active_conditions
    assert "haste_action" not in actor.action_economy.resources
    assert actor.equipment.ac_bonus.normalized_score == base_ac
    assert actor.action_economy.action_permission.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 0
