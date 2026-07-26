"""Focused objective terminal summary reduction tests."""

from datetime import datetime, timedelta, timezone
from typing import TypedDict
from uuid import UUID, uuid4

import pytest

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, SpellEvent
from dnd.analytics import (
    EntitySnapshotV1,
    GameSummaryEvidenceV1,
    MetricAvailability,
    GameOutcomeResolution,
    TerminalCursorV1,
    canonical_summary_bytes,
    reduce_game_summary,
    summary_digest_is_valid,
)
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.conditions import Prone
from dnd.core.base_actions import ActionEvent, BaseCost
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.runtime import bind_runtime_behavior
from dnd.core.damage import DamageComponentResolution, DamageResolution
from dnd.core.dice import AttackOutcome, DiceRoll, RollType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    AttackD20RollResultEvent,
    Damage,
    DamageAppliedEvent,
    DeathEvent,
    EncounterEndEvent,
    EncounterStartEvent,
    Event,
    EventPhase,
    EventType,
    ForcedMovementEvent,
    HealEvent,
    RoundStartEvent,
    TakeDamageEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from dnd.core.life_types import LifeState
from dnd.core.modifiers import (
    AdvantageStatus,
    AutoHitStatus,
    CriticalStatus,
    DamageType,
    ResistanceStatus,
)


HERO_UUID = UUID("00000000-0000-0000-0000-000000000101")
GOBLIN_UUID = UUID("00000000-0000-0000-0000-000000000202")
ENCOUNTER_UUID = UUID("00000000-0000-0000-0000-000000000303")
ITEM_UUID = UUID("00000000-0000-0000-0000-000000000404")
STARTED_AT = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
PRONE_CONTENT_IDENTITY = "core.rules:condition:condition.prone@1"


class _EventKwargs(TypedDict):
    """Common constructor fields for deterministic terminal events."""

    source_entity_uuid: UUID
    lineage_uuid: UUID
    timestamp: datetime
    phase: EventPhase
    use_register: bool


def test_engine_event_timestamps_are_timezone_aware_utc() -> None:
    """Canonical evidence must never label local wall time as UTC."""
    event = Event(
        source_entity_uuid=HERO_UUID,
        event_type=EventType.BASE_ACTION,
        use_register=False,
    )

    assert event.timestamp.tzinfo is not None
    assert event.timestamp.utcoffset() == timedelta(0)

    completed = event.phase_to(EventPhase.COMPLETION, use_register=False)

    assert completed.timestamp.tzinfo is not None
    assert completed.timestamp.utcoffset() == timedelta(0)


def _snapshots() -> tuple[
    tuple[EntitySnapshotV1, ...],
    tuple[EntitySnapshotV1, ...],
]:
    """Return deterministic initial and terminal combatant states."""
    initial = (
        EntitySnapshotV1(
            entity_uuid=HERO_UUID,
            name="Aria",
            side_id="heroes",
            normal_hit_points=18,
            maximum_hit_points=24,
            temporary_hit_points=0,
            life_state=LifeState.ALIVE,
            is_defeated=False,
            position=(1, 1),
            resources={"spell_slot_1": 2},
        ),
        EntitySnapshotV1(
            entity_uuid=GOBLIN_UUID,
            name="Goblin Captain",
            side_id="monsters",
            normal_hit_points=8,
            maximum_hit_points=16,
            temporary_hit_points=3,
            life_state=LifeState.ALIVE,
            is_defeated=False,
            position=(6, 1),
        ),
    )
    final = (
        EntitySnapshotV1(
            entity_uuid=HERO_UUID,
            name="Aria",
            side_id="heroes",
            normal_hit_points=22,
            maximum_hit_points=24,
            temporary_hit_points=0,
            life_state=LifeState.ALIVE,
            is_defeated=False,
            position=(4, 1),
            resources={"spell_slot_1": 1},
        ),
        EntitySnapshotV1(
            entity_uuid=GOBLIN_UUID,
            name="Goblin Captain",
            side_id="monsters",
            normal_hit_points=0,
            maximum_hit_points=16,
            temporary_hit_points=0,
            life_state=LifeState.DEAD,
            is_defeated=True,
            position=(8, 1),
            condition_semantic_keys=(PRONE_CONTENT_IDENTITY,),
        ),
    )
    return initial, final


def test_entity_snapshot_life_state_owns_defeated_projection_when_present() -> None:
    """New snapshots retain LifeState while legacy v1 rows remain readable."""
    legacy = EntitySnapshotV1(
        entity_uuid=GOBLIN_UUID,
        name="Legacy Goblin",
        side_id="monsters",
        normal_hit_points=0,
        maximum_hit_points=16,
        is_defeated=True,
    )
    assert legacy.life_state is None

    with pytest.raises(ValueError, match="is_defeated must equal"):
        EntitySnapshotV1(
            entity_uuid=GOBLIN_UUID,
            name="Impossible Goblin",
            side_id="monsters",
            normal_hit_points=0,
            maximum_hit_points=16,
            life_state=LifeState.ALIVE,
            is_defeated=True,
        )


def _completed_event_kwargs(
    *,
    source_uuid: UUID,
    seconds: int,
    lineage_uuid: UUID | None = None,
) -> _EventKwargs:
    """Return common deterministic terminal event fields.

    Args:
        source_uuid: Acting entity identity.
        seconds: Offset from STARTED_AT.
        lineage_uuid: Optional fixed lineage identity.

    Returns:
        Constructor keyword mapping.
    """
    return {
        "source_entity_uuid": source_uuid,
        "lineage_uuid": lineage_uuid or uuid4(),
        "timestamp": STARTED_AT + timedelta(seconds=seconds),
        "phase": EventPhase.COMPLETION,
        "use_register": False,
    }


def _representative_evidence() -> tuple[list[Event], list[CombatLogEntry]]:
    """Build a representative terminal match from concrete engine events."""
    start = EncounterStartEvent(
        encounter_uuid=ENCOUNTER_UUID,
        combatant_uuids=[HERO_UUID, GOBLIN_UUID],
        initiative_order=[HERO_UUID, GOBLIN_UUID],
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=0),
    )
    round_start = RoundStartEvent(
        encounter_uuid=ENCOUNTER_UUID,
        round_number=1,
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=1),
    )
    hero_turn = TurnStartEvent(
        encounter_uuid=ENCOUNTER_UUID,
        entity_uuid=HERO_UUID,
        round_number=1,
        turn_index=0,
        source_entity_name="Aria",
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=2),
    )
    movement = MovementEvent(
        name="Move",
        source_entity_name="Aria",
        start_position=(1, 1),
        end_position=(3, 1),
        path=[(1, 1), (2, 1), (3, 1)],
        costs=[BaseCost(name="Movement", cost_type="movement", cost=10)],
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=3),
    )
    jump = JumpEvent(
        source_entity_name="Aria",
        start_position=(3, 1),
        end_position=(4, 1),
        jump_distance=15,
        path=[(3, 1), (4, 1)],
        costs=[
            BaseCost(name="Jump", cost_type="bonus_actions", cost=1),
            BaseCost(name="Jump movement", cost_type="movement", cost=15),
        ],
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=4),
    )
    spell_lineage = UUID("00000000-0000-0000-0000-000000000505")
    spell_declaration = SpellEvent(
        name="Magic Missile",
        spell_id="magic_missile",
        spell_level=1,
        cast_at_level=1,
        target_entity_uuid=GOBLIN_UUID,
        source_entity_name="Aria",
        target_entity_name="Goblin Captain",
        costs=[
            BaseCost(name="Cast", cost_type="actions", cost=1),
            BaseCost(name="Slot", cost_type="spell_slot_1", cost=1),
        ],
        source_entity_uuid=HERO_UUID,
        lineage_uuid=spell_lineage,
        timestamp=STARTED_AT + timedelta(seconds=5),
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    spell_execution = spell_declaration.model_copy(
        update={
            "uuid": uuid4(),
            "timestamp": STARTED_AT + timedelta(seconds=5, milliseconds=500),
            "phase": EventPhase.EXECUTION,
        }
    )
    spell_completion = spell_declaration.model_copy(
        update={
            "uuid": uuid4(),
            "timestamp": STARTED_AT + timedelta(seconds=6),
            "phase": EventPhase.COMPLETION,
        }
    )
    per_target_completion = spell_completion.model_copy(
        update={
            "uuid": uuid4(),
            "lineage_uuid": uuid4(),
            "parent_event": spell_execution.uuid,
            "timestamp": STARTED_AT + timedelta(seconds=6, milliseconds=100),
        }
    )
    damage = Damage(
        source_entity_uuid=HERO_UUID,
        target_entity_uuid=GOBLIN_UUID,
        damage_dice=4,
        dice_numbers=4,
        damage_type=DamageType.FORCE,
        use_register=False,
    )
    damage_resolution = DamageResolution(
        declared_damage=16,
        incoming_damage=16,
        event_prevented_damage=0,
        event_amplified_damage=0,
        components=(
            DamageComponentResolution(
                damage_type=DamageType.FORCE,
                incoming_damage=16,
                resistance_status=ResistanceStatus.RESISTANCE,
                multiplier=0.5,
                after_affinity_damage=8,
                affinity_prevented_damage=8,
                vulnerability_bonus_damage=0,
            ),
        ),
        after_affinity_damage=8,
        affinity_prevented_damage=8,
        vulnerability_bonus_damage=0,
        flat_reduction_damage=0,
        mitigated_damage=8,
        temporary_hit_point_damage=3,
        normal_hit_point_damage=5,
        survival_cap_prevented_damage=0,
        effective_normal_hit_point_damage=5,
        overkill_damage=0,
    )
    incoming_damage = TakeDamageEvent(
        target_entity_uuid=GOBLIN_UUID,
        source_entity_name="Aria",
        target_entity_name="Goblin Captain",
        total_damage=16,
        final_damage=8,
        damages=[damage],
        resolution=damage_resolution,
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=7),
    )
    applied_damage = DamageAppliedEvent(
        target_entity_uuid=GOBLIN_UUID,
        source_entity_name="Aria",
        target_entity_name="Goblin Captain",
        applied_damage=8,
        normal_hit_point_damage=5,
        temporary_hit_point_damage=3,
        resulting_normal_hp=3,
        resulting_temporary_hp=0,
        damage_type=DamageType.FORCE,
        damages=[damage],
        resolution=damage_resolution,
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=8),
    )
    prone = Prone(
        source_entity_uuid=HERO_UUID,
        target_entity_uuid=GOBLIN_UUID,
        use_register=False,
    )
    assert bind_runtime_behavior(
        prone,
        runtime_owner_uuid=GOBLIN_UUID,
    ) is not None
    condition = ConditionApplicationEvent(
        target_entity_uuid=GOBLIN_UUID,
        condition=prone,
        source_entity_name="Aria",
        target_entity_name="Goblin Captain",
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=9),
    )
    forced = ForcedMovementEvent(
        target_entity_uuid=GOBLIN_UUID,
        source_entity_name="Aria",
        target_entity_name="Goblin Captain",
        start_position=(6, 1),
        end_position=(8, 1),
        direction=(1, 0),
        intended_distance=10,
        actual_distance=10,
        cause="shove",
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=10),
    )
    item_action = ActionEvent(
        name="Drink Potion",
        target_entity_uuid=HERO_UUID,
        source_entity_name="Aria",
        target_entity_name="Aria",
        source_item_uuid=ITEM_UUID,
        item_charge_cost=1,
        costs=[BaseCost(name="Potion", cost_type="bonus_actions", cost=1)],
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=11),
    )
    item_charge = ItemChargeConsumptionEvent(
        target_entity_uuid=HERO_UUID,
        item_uuid=ITEM_UUID,
        item_semantic_key="item.potion.healing",
        item_name="Potion of Healing",
        amount=1,
        charges_before=1,
        charges_after=0,
        stack_count_before=1,
        stack_count_after=1,
        item_destroyed=True,
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=12),
    )
    healing = HealEvent(
        target_entity_uuid=HERO_UUID,
        source_entity_name="Aria",
        target_entity_name="Aria",
        total_healing=7,
        actual_healing=4,
        source_description="Potion of Healing",
        resulting_normal_hp=22,
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=13),
    )
    goblin_turn = TurnStartEvent(
        encounter_uuid=ENCOUNTER_UUID,
        entity_uuid=GOBLIN_UUID,
        round_number=1,
        turn_index=1,
        source_entity_name="Goblin Captain",
        **_completed_event_kwargs(source_uuid=GOBLIN_UUID, seconds=14),
    )
    opportunity_attack = AttackEvent(
        name="Opportunity Attack",
        target_entity_uuid=HERO_UUID,
        source_entity_name="Goblin Captain",
        target_entity_name="Aria",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Scimitar",
        attack_outcome=AttackOutcome.MISS,
        costs=[BaseCost(name="Reaction", cost_type="reactions", cost=1)],
        **_completed_event_kwargs(source_uuid=GOBLIN_UUID, seconds=15),
    )
    hero_turn_end = TurnEndEvent(
        encounter_uuid=ENCOUNTER_UUID,
        entity_uuid=HERO_UUID,
        round_number=1,
        turn_index=0,
        source_entity_name="Aria",
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=16),
    )
    death = DeathEvent(
        entity_uuid=GOBLIN_UUID,
        entity_name="Goblin Captain",
        killer_uuid=HERO_UUID,
        killer_name="Aria",
        final_hp=0,
        encounter_uuid=ENCOUNTER_UUID,
        target_entity_uuid=GOBLIN_UUID,
        **_completed_event_kwargs(source_uuid=GOBLIN_UUID, seconds=17),
    )
    end = EncounterEndEvent(
        encounter_uuid=ENCOUNTER_UUID,
        combatant_uuids=[HERO_UUID, GOBLIN_UUID],
        reason="one faction remains",
        **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=18),
    )
    events: list[Event] = [
        start,
        round_start,
        hero_turn,
        movement,
        jump,
        spell_declaration,
        spell_execution,
        spell_completion,
        per_target_completion,
        incoming_damage,
        applied_damage,
        condition,
        forced,
        item_action,
        item_charge,
        healing,
        goblin_turn,
        opportunity_attack,
        hero_turn_end,
        death,
        end,
    ]
    return events, [opportunity_attack.generate_combat_log()]


def _summary(*, reverse_events: bool = False, combat_log_complete: bool = True):
    """Reduce the representative fixture with selected completeness flags."""
    initial, final = _snapshots()
    events, logs = _representative_evidence()
    if reverse_events:
        events.reverse()
    return reduce_game_summary(
        game_id="game-summary-test",
        encounter_uuid=ENCOUNTER_UUID,
        initial_entities=initial,
        final_entities=final,
        event_history=events,
        combat_logs=logs if combat_log_complete else [],
        evidence=GameSummaryEvidenceV1(
            terminal_cursor=TerminalCursorV1(event_cursor=19, combat_log_cursor=1),
            combat_log_complete=combat_log_complete,
        ),
    )


def test_representative_terminal_match_reduces_objective_typed_evidence() -> None:
    """The v2 reducer distinguishes factual terminal statistics and outcome."""
    summary = _summary()

    assert summary.schema_name == "dnd.game-summary"
    assert summary.schema_version == 2
    assert summary.provenance.reducer_id == "dnd.analytics.game_summary.v2"
    assert summary.outcome.resolution == GameOutcomeResolution.VICTORY
    assert summary.outcome.winning_side_ids == ("heroes",)
    assert summary.outcome.losing_side_ids == ("monsters",)
    assert summary.outcome.reason == "one faction remains"
    assert summary.duration_seconds == 18.0
    assert summary.rounds_started == 1
    assert summary.terminal_cursor.event_cursor == 19
    assert summary.completeness.status.value == "complete"

    hero = next(entity for entity in summary.entities if entity.entity_uuid == HERO_UUID)
    goblin = next(entity for entity in summary.entities if entity.entity_uuid == GOBLIN_UUID)
    assert hero.statistics.damage_dealt.incoming_raw == 16
    assert hero.statistics.damage_dealt.applied == 8
    assert hero.statistics.damage_dealt.normal_hit_point_damage == 5
    assert hero.statistics.damage_dealt.temporary_hit_point_damage == 3
    assert hero.statistics.damage_dealt.unapplied_remainder == 8
    assert hero.statistics.damage_dealt.prevention.event_prevented == 0
    assert hero.statistics.damage_dealt.prevention.resistance_prevented == 8
    assert hero.statistics.damage_dealt.effective_normal_hit_point_damage == 5
    assert hero.statistics.damage_dealt.applied_by_counterparty == {str(GOBLIN_UUID): 8}
    assert hero.statistics.damage_dealt.applied_by_effect == {"unattributed": 8}
    assert hero.statistics.healing_done.requested == 7
    assert hero.statistics.healing_done.applied == 4
    assert hero.statistics.movement.voluntary_feet == 10
    assert hero.statistics.movement.jump_feet == 15
    assert hero.statistics.spell_usage["magic_missile"].completed == 1
    assert hero.statistics.action_usage["Magic Missile"].attempted == 1
    assert hero.statistics.resources_spent["spell_slot_1"] == 1
    assert hero.statistics.item_action_usage[str(ITEM_UUID)].completed == 1
    assert hero.statistics.item_charges_spent["item.potion.healing"] == 1
    assert hero.statistics.kills == 1

    assert goblin.statistics.damage_taken.applied_by_type == {"Force": 8}
    assert goblin.statistics.movement.forced_events == 1
    assert goblin.statistics.movement.forced_feet == 10
    assert goblin.statistics.conditions_applied == {
        PRONE_CONTENT_IDENTITY: 1,
    }
    assert goblin.statistics.attacks.attempted == 1
    assert goblin.statistics.attacks.misses == 1
    assert goblin.statistics.attacks.opportunity_attacks == 1
    assert goblin.statistics.deaths == 1

    heroes = next(side for side in summary.sides if side.side_id == "heroes")
    monsters = next(side for side in summary.sides if side.side_id == "monsters")
    assert heroes.statistics.damage_dealt.applied == 8
    assert heroes.surviving_combatant_count == 1
    assert monsters.statistics.damage_taken.applied == 8
    assert monsters.surviving_combatant_count == 0


def test_canonical_digest_is_idempotent_and_event_order_independent() -> None:
    """Equivalent typed evidence produces byte-identical canonical summaries."""
    chronological = _summary()
    reversed_input = _summary(reverse_events=True)

    assert chronological.canonical_sha256 == reversed_input.canonical_sha256
    assert canonical_summary_bytes(chronological) == canonical_summary_bytes(reversed_input)
    assert summary_digest_is_valid(chronological)
    assert summary_digest_is_valid(reversed_input)
    assert not summary_digest_is_valid(
        chronological.model_copy(update={"game_id": "tampered-game"})
    )


def test_d20_luck_uses_advantage_conditioned_expectation() -> None:
    """Luck compares the selected result with the max-of-two distribution."""
    initial, final = _snapshots()
    events, logs = _representative_evidence()
    roll = DiceRoll(
        dice_uuid=uuid4(),
        die_size=20,
        effective_dice_count=1,
        random_faces_rolled=2,
        roll_type=RollType.ATTACK,
        results=[3, 17],
        total=22,
        bonus=5,
        advantage_status=AdvantageStatus.ADVANTAGE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=HERO_UUID,
        target_entity_uuid=GOBLIN_UUID,
    )
    events.append(
        AttackD20RollResultEvent(
            roll=roll,
            original_roll=roll,
            dc=14,
            result=True,
            target_entity_uuid=GOBLIN_UUID,
            **_completed_event_kwargs(source_uuid=HERO_UUID, seconds=5),
        )
    )

    summary = reduce_game_summary(
        game_id="dice-luck-test",
        encounter_uuid=ENCOUNTER_UUID,
        initial_entities=initial,
        final_entities=final,
        event_history=events,
        combat_logs=logs,
        evidence=GameSummaryEvidenceV1(
            terminal_cursor=TerminalCursorV1(event_cursor=len(events), combat_log_cursor=1),
        ),
    )
    hero = next(entity for entity in summary.entities if entity.entity_uuid == HERO_UUID)
    luck = hero.statistics.dice.attack_d20

    assert luck.roll_events == 1
    assert luck.random_faces_rolled == 2
    assert luck.average_observed == 17
    assert luck.average_expected == 13.825
    assert luck.luck_delta == 3.175
    assert luck.advantage_events == 1


def test_unavailable_metrics_and_incomplete_logs_remain_explicit() -> None:
    """The reducer reports metrics independently of unrelated missing logs."""
    summary = _summary(combat_log_complete=False)
    goblin = next(entity for entity in summary.entities if entity.entity_uuid == GOBLIN_UUID)
    provenance = {
        metric.metric: metric
        for metric in summary.provenance.metric_provenance
    }

    assert summary.completeness.status.value == "partial"
    assert summary.completeness.issues == ("combat_log_incomplete",)
    assert goblin.statistics.attacks.opportunity_attacks is None
    assert provenance["opportunity_attacks"].availability == MetricAvailability.UNAVAILABLE
    assert provenance["damage_prevention_decomposition"].availability == MetricAvailability.AVAILABLE
    assert provenance["overkill_damage"].availability == MetricAvailability.AVAILABLE
