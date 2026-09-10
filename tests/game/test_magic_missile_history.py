"""One public cast retains three ordered A/B/A applications and their HP facts."""

from uuid import uuid5

from dnd.actions import SpellEvent
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, TakeDamageEvent
from dnd.core.life_types import LifeState
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.combat import bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage


def test_public_repeated_target_cast_keeps_each_application_while_latest_advances() -> None:
    data = load_animation_data()
    script = iter_combat_demo(magic_missile=True)
    try:
        seed, first_lineage = next(script), next(script)
        assert isinstance(seed, PresentationTarget)
        assert isinstance(first_lineage, CompletedLineage)
        root = first_lineage.root
        assert isinstance(root, SpellEvent)
        a_uuid, b_uuid, repeated_a = root.declared_target_entity_uuids
        assert repeated_a == a_uuid and b_uuid != a_uuid
        caster = Entity.get(seed.observer_uuid)
        assert caster is not None
        assert caster.action_economy.actions.normalized_score == 0
        assert caster.action_economy.spell_slot_1.normalized_score == 1

        applications = [event for event in first_lineage.events if isinstance(event, SpellEvent)
                        and event.parent_lineage == root.lineage_uuid]
        assert [event.application_index for event in applications] == [0, 1, 2]
        assert [event.target_entity_uuid for event in applications] == [a_uuid, b_uuid, a_uuid]
        assert [event.application_id for event in applications] == [
            uuid5(root.lineage_uuid, f"target-application:{index}") for index in range(3)
        ]
        assert root.application_id is None and root.total_targets == 3 and root.total_damage == 12
        assert set(root.children_lineages) == {event.lineage_uuid for event in applications}
        for application, expected_damage, expected_hp in zip(applications, (5, 5, 2), (75, 75, 73), strict=True):
            incoming = next(event for event in first_lineage.events if isinstance(event, TakeDamageEvent)
                            and event.parent_lineage == application.lineage_uuid)
            applied = next(event for event in first_lineage.events if isinstance(event, DamageAppliedEvent)
                           and event.parent_lineage == incoming.lineage_uuid)
            assert applied.target_entity_uuid == incoming.target_entity_uuid == application.target_entity_uuid
            assert (applied.applied_damage, applied.resulting_normal_hp) == (expected_damage, expected_hp)
            assert applied.resulting_temporary_hp == 0
            assert applied.damage_type.value == "Force"
            assert applied.effect_id == "dnd.spells.evocation.MagicMissile.damage"
            assert [roll.total for roll in application.damage_rolls or ()] == [expected_damage]
        for event in first_lineage.events:
            assert event.phase is EventPhase.COMPLETION
            assert set(event.children_lineages) == {
                child.lineage_uuid for child in first_lineage.events if child.parent_lineage == event.lineage_uuid
            }
            original = EventQueue.get_event_by_uuid(event.uuid)
            assert original is not None
            assert event.parent_event == original.parent_event
            assert event.parent_lineage == original.parent_lineage
            assert event.identified_entity_observer_uuids == original.identified_entity_observer_uuids
            assert event.located_entity_observer_uuids == original.located_entity_observer_uuids

        first = bind_cast(seed, first_lineage, data, travel_apex_steps=1.0)
        sources = first.timeline.source.applications
        assert [source.application_id for source in sources] == [str(event.application_id) for event in applications]
        assert [source.target.actor_uuid for source in sources] == [str(a_uuid), str(b_uuid), str(a_uuid)]
        assert [source.target.hp for source in sources] == [80, 80, 80]
        assert [source.resulting_hp for source in sources] == [75, 75, 73]
        assert [source.damage_type for source in sources] == ["Force"] * 3
        assert len(first.appearances) == 3
        assert first.timeline.source.caster.elevation_steps == 0
        assert [source.target.elevation_steps for source in sources] == [2, 2, 2]
        hp_times = tuple(application.hp_ms for application in first.timeline.applications)
        assert all(time is not None for time in hp_times)
        sample_times = (0.0, first.timeline.release_ms,
                        *(time for time in hp_times if time is not None), first.timeline.complete_ms)
        original_samples = tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times)
        assert len(original_samples[0].bodies) == 3 and len(original_samples[0].vitals) == 2
        assert tuple((vital.actor_uuid, vital.hp) for vital in original_samples[2].vitals) == (
            (str(a_uuid), 75), (str(b_uuid), 80),
        )
        assert tuple(vital.hp for vital in original_samples[3].vitals) == (75, 75)
        assert tuple(vital.hp for vital in original_samples[4].vitals) == (73, 75)

        second_lineage = next(script)
        assert isinstance(second_lineage, CompletedLineage)
        assert caster.action_economy.actions.normalized_score == 0
        assert caster.action_economy.spell_slot_1.normalized_score == 0
    finally:
        script.close()

    latest_first = reduce_lineage(seed, first_lineage)
    latest_second = reduce_lineage(latest_first, second_lineage)
    assert tuple(latest_first.actors[identity].normal_hp for identity in (a_uuid, b_uuid)) == (73, 75)
    assert tuple(latest_second.actors[identity].normal_hp for identity in (a_uuid, b_uuid)) == (66, 73)
    assert tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times) == original_samples
    second = bind_cast(first.after, second_lineage, data, travel_apex_steps=1.0)
    assert [source.target.hp for source in second.timeline.source.applications] == [73, 75, 73]
    assert [source.damage_total for source in second.timeline.source.applications] == [3, 2, 4]
    assert [source.resulting_hp for source in second.timeline.source.applications] == [70, 73, 66]
    assert first.after == latest_first and second.after == latest_second
    final_sample = sample_cast(second.timeline, second.timeline.complete_ms)
    assert tuple(vital.hp for vital in final_sample.vitals) == (66, 73)
    assert all(vital.life_state is LifeState.ALIVE for vital in final_sample.vitals)

    reset_engine_runtime()
    replay_first = bind_cast(seed, first_lineage, data, travel_apex_steps=1.0)
    replay_second = bind_cast(replay_first.after, second_lineage, data, travel_apex_steps=1.0)
    assert replay_first == first and replay_second == second
    assert tuple(sample_cast(replay_first.timeline, elapsed) for elapsed in sample_times) == original_samples
    assert sample_cast(replay_second.timeline, replay_second.timeline.complete_ms) == final_sample
