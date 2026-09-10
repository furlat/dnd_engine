"""An actual spell miss reuses authored delivery without inventing damage."""

from uuid import UUID

import pytest

from dnd.actions import SpellEvent
from dnd.core.dice import AttackOutcome
from dnd.core.events import AttackD20RollResultEvent, DamageAppliedEvent, TakeDamageEvent
from dnd.core.life_types import LifeState
from dnd.runtime_reset import reset_engine_runtime
from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.combat import bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage


@pytest.mark.parametrize("attack_seed, outcome", [
    (1, AttackOutcome.MISS),
    (31, AttackOutcome.CRIT_MISS),
])
def test_public_miss_keeps_hp_and_authored_delivery_without_hit_feedback(
    attack_seed: int, outcome: AttackOutcome,
) -> None:
    script = iter_combat_demo(second_attack_seed=attack_seed)
    try:
        seed, hit_lineage = next(script), next(script)
        assert isinstance(seed, PresentationTarget)
        assert isinstance(hit_lineage, CompletedLineage)
        data = load_animation_data()
        hit = bind_cast(seed, hit_lineage, data)
        missed_lineage = next(script)
        assert isinstance(missed_lineage, CompletedLineage)
    finally:
        script.close()

    root = missed_lineage.root
    assert isinstance(root, SpellEvent)
    assert root.attack_outcome is outcome
    assert not any(isinstance(event, (DamageAppliedEvent, TakeDamageEvent))
                   for event in missed_lineage.events)
    roll = next(event for event in missed_lineage.events if isinstance(event, AttackD20RollResultEvent))
    assert roll.parent_lineage == root.lineage_uuid
    assert root.combat_log is not None and root.combat_log.success is False
    assert "misses" in root.combat_log.compact

    missed = bind_cast(hit.after, missed_lineage, data)
    recipient = UUID(missed.timeline.source.applications[0].target.actor_uuid)
    assert hit.after.actors[recipient].normal_hp == 73
    assert missed.after.actors[recipient].normal_hp == 73
    assert missed.after.actors[recipient].temporary_hp == 0
    assert missed.after.actors[recipient].life_state is LifeState.ALIVE
    assert missed.after == reduce_lineage(hit.after, missed_lineage)
    assert missed.timeline.source.applications[0].damage_applied is False
    assert missed.timeline.source.applications[0].damage_total is None
    assert missed.timeline.source.applications[0].resulting_hp is None
    assert missed.timeline.source.applications[0].resulting_life_state is None
    assert missed.timeline.recipe == hit.timeline.recipe == data.drafts["spell.fire_bolt"]
    assert missed.timeline.release_ms == hit.timeline.release_ms
    assert missed.timeline.applications[0].projectile_intervals == hit.timeline.applications[0].projectile_intervals
    assert not {"effect", "vitals"}.intersection(anchor.name for anchor in missed.timeline.anchors)
    travel = next(interval for interval in missed.timeline.applications[0].projectile_intervals if interval.name == "travel")
    impact = next(interval for interval in missed.timeline.applications[0].projectile_intervals if interval.name == "impact")
    times = (0, missed.timeline.release_ms, (travel.start_ms + travel.end_ms) / 2,
             impact.start_ms + 100, missed.timeline.complete_ms)
    samples = tuple(sample_cast(missed.timeline, elapsed) for elapsed in times)
    for sample in samples:
        body = next(body for body in sample.bodies if body.actor_uuid == str(recipient))
        assert body.clip == "Idle"
        assert sample.vitals[0].hp == 73 and sample.vitals[0].life_state is LifeState.ALIVE
        assert sample.numbers == () and sample.vitals[0].flash is None

    reset_engine_runtime()
    replay = bind_cast(hit.after, missed_lineage, data)
    assert replay.after == missed.after
    assert tuple(sample_cast(replay.timeline, elapsed) for elapsed in times) == samples
