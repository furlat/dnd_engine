"""Disposition ledger for the archived information-leak regression script.

The old script mixed two engine contracts with a deleted CLI-side filter.  The
subjective server projector is now the privacy authority, so this file restores
the two genuine engine gaps and points every superseded case at its maintained
privacy contract without reviving the unsafe compatibility path.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from dnd.conditions import Hidden
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.core.gridmap import get_map
from dnd.entities.entity import Entity
from tests.engine.support import create_test_monster
from dnd.spells.evocation import Fireball
from tests.engine.support import get_hp, reset_combat_state


CoverageStatus = Literal["active", "strengthened", "retired", "stale", "unresolved"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived case's current disposition."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_legacy_information_privacy_coverage.py"
SENSES_FILE = "tests/engine/test_senses_light_stealth.py"
PROJECTION_FILE = "tests/manual/test_113_subjective_combat_log_projection.py"
OBSERVATION_FILE = "tests/manual/test_28_subjective_observation_stream.py"


INFORMATION_PRIVACY_LEDGER: dict[str, LegacyCoverage] = {
    "test_aoe_preview_hidden_entity": LegacyCoverage(
        "strengthened",
        f"{SENSES_FILE}::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them",
        "The maintained engine test asserts both subjective preview privacy and objective effects.",
    ),
    "test_combat_log_anonymization": LegacyCoverage(
        "retired",
        f"{PROJECTION_FILE}::test_every_entry_type_recursively_scrubs_an_unknown_identity",
        "Deleted CLI string replacement is superseded by typed recursive server projection.",
    ),
    "test_aoe_empty_position": LegacyCoverage(
        "active",
        f"{THIS_FILE}::test_position_aoe_can_resolve_with_zero_affected_entities",
        "Restored as a deterministic action lifecycle and resource-cost contract.",
    ),
    "test_temporal_filtering": LegacyCoverage(
        "retired",
        f"{PROJECTION_FILE}::test_fully_unobserved_log_tree_is_omitted",
        "The deleted CLI kept and anonymized wholly unobserved entries for "
        "compatibility. The canonical typed projector deliberately omits the "
        "entire unobserved causal tree instead.",
    ),
    "test_engine_perceiver_stamping": LegacyCoverage(
        "strengthened",
        f"{OBSERVATION_FILE}::test_child_log_inherits_identity_established_by_its_causal_parent",
        "Maintained coverage follows identity evidence through the causal log tree.",
    ),
    "test_movement_hidden_positions": LegacyCoverage(
        "strengthened",
        f"{OBSERVATION_FILE}::test_known_enemy_movement_log_stops_at_last_perceived_step",
        "Maintained coverage clips typed movement geometry at the last evidenced position.",
    ),
    "test_aoe_reveals_hidden_target": LegacyCoverage(
        "retired",
        f"{PROJECTION_FILE}::test_global_reveal_metadata_does_not_grant_subjective_identity",
        "A global reveal list is intentionally not a universal subjective identity grant.",
    ),
    "test_revealed_filter_unit": LegacyCoverage(
        "retired",
        f"{PROJECTION_FILE}::test_global_reveal_metadata_does_not_grant_subjective_identity",
        "The unsafe CLI reveal override was removed rather than reproduced.",
    ),
    "test_condition_removal_log_data": LegacyCoverage(
        "active",
        f"{THIS_FILE}::test_condition_removal_log_carries_typed_identity_and_reveal_fact",
        "Restored directly against the current condition-removal event contract.",
    ),
    "test_invisible_kill_reveals_sub_events": LegacyCoverage(
        "strengthened",
        f"{OBSERVATION_FILE}::test_lethal_log_retains_identity_known_when_event_started",
        "Maintained end-to-end coverage freezes event-time identity across lethal visibility loss.",
    ),
}


def test_information_privacy_manifest_accounts_for_all_10_cases() -> None:
    """Every archived function has one reviewed maintained disposition."""
    assert len(INFORMATION_PRIVACY_LEDGER) == 10
    assert not any(
        row.status == "unresolved"
        for row in INFORMATION_PRIVACY_LEDGER.values()
    )
    for case, row in INFORMATION_PRIVACY_LEDGER.items():
        assert case.startswith("test_")
        assert row.selector.startswith("tests/") and "::test_" in row.selector
        assert row.rationale


def test_position_aoe_can_resolve_with_zero_affected_entities() -> None:
    """Fireball can spend its action and slot on a legal empty grid position."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 15, 15)
    caster = create_test_monster("monster.generic_caster", 
        name="Wizard",
        position=(2, 2),
        faction="heroes",
        level=5,
    )
    distant_target = create_test_monster("monster.skeleton", 
        name="Distant Target",
        position=(14, 14),
        faction="monsters",
    )
    Entity.materialize_all_navigation(max_distance=15)
    hp_before = get_hp(distant_target)
    action_before = caster.action_economy.actions.normalized_score
    slots_before = caster.action_economy.spell_slot_3.normalized_score

    result = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(7, 2),
        cast_at_level=3,
    ).apply()

    assert isinstance(result, ActionEvent)
    assert not result.canceled
    assert result.total_targets == 0
    assert result.aoe_position == (7, 2)
    assert get_hp(distant_target) == hp_before
    assert caster.action_economy.actions.normalized_score == action_before - 1
    assert caster.action_economy.spell_slot_3.normalized_score == slots_before - 1


def test_condition_removal_log_carries_typed_identity_and_reveal_fact() -> None:
    """Removing an obscuring condition identifies it and marks the reveal fact."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    condition = Hidden(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Rogue",
        target_entity_name="Rogue",
        stealth_result=20,
    )
    event = ConditionRemovalEvent(
        condition=condition,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Rogue",
        target_entity_name="Rogue",
        phase=EventPhase.COMPLETION,
    )

    log = event.generate_combat_log()

    assert log is not None
    assert log.entry_type == CombatLogEntryType.CONDITION_REMOVED
    assert log.source_uuid == str(source_uuid)
    assert log.target_uuid == str(target_uuid)
    assert log.data == {
        "condition_name": "Hidden",
        "condition_content_identity": None,
        "reveals_target": True,
        "application_disposition": None,
    }
