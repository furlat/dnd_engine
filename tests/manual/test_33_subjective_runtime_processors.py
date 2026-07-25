"""Post-processor checks for the subjective runtime."""

from typing import Any

from ai.knowledge.deriver import derive_agent_facts
from dnd.ai.contracts.observation import KnowledgeState, ObservationObjectFact, ObservationTileFact
from ai.subjective.hooks import DerivedVariableUpdate, HookContext, HookPoint, HookRegistry, ProcessorOutput
from ai.subjective.processors import default_processors
from ai.subjective.queries import SubjectiveQueries
from ai.subjective.store import SubjectiveStore
from tests.manual.test_28_subjective_observation_stream import create_observation_game


class _OrderProbe:
    """Small test processor that records deterministic execution order."""

    def __init__(self, name: str, order: int) -> None:
        self.name = name
        self.order = order

    def run(self, context: HookContext) -> list[ProcessorOutput]:
        seen = list(context.agent_state.variables.get("seen_order", []))
        seen.append(self.name)
        return [ProcessorOutput(variable_update=DerivedVariableUpdate(name="seen_order", value=seen))]


def _world_with_epoch():
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    world = store.load_snapshot(snapshot)
    assert world.current_epoch is not None
    return store, world


def _effect_episode_log(
    source_uuid: str,
    target_uuid: str,
    effect_id: str,
    *,
    blocked_applications: int,
    successful_applications: int = 0,
) -> dict[str, Any]:
    """Build one already-filtered top-level log with typed effect applications."""
    applications = [
        {
            "entry_type": "damage_taken",
            "source_uuid": source_uuid,
            "target_uuid": target_uuid,
            "data": {
                "damage": 0,
                "damage_type": "force",
                "blocked": True,
                "effect_id": effect_id,
            },
            "sub_entries": [],
        }
        for _ in range(blocked_applications)
    ]
    applications.extend(
        {
            "entry_type": "damage_taken",
            "source_uuid": source_uuid,
            "target_uuid": target_uuid,
            "data": {
                "damage": 4,
                "damage_type": "force",
                "blocked": False,
                "effect_id": effect_id,
            },
            "sub_entries": [],
        }
        for _ in range(successful_applications)
    )
    return {
        "entry_type": "multi_entity_action",
        "source_uuid": source_uuid,
        "target_uuid": None,
        "data": {},
        "sub_entries": applications,
    }


def test_hooks_run_in_deterministic_order() -> None:
    """Processor ordering is by numeric order and then stable name."""
    store, world = _world_with_epoch()
    registry = HookRegistry([
        _OrderProbe("b", 20),
        _OrderProbe("a", 20),
        _OrderProbe("early", 10),
    ])

    state = registry.run(HookContext(
        hook=HookPoint.SNAPSHOT_LOADED,
        world=world,
        agent_state=store.agent_state,
    ))

    assert state.variables["seen_order"] == ["early", "a", "b"]
    assert set(registry.last_timings_ms) == {
        "state_copy",
        "early",
        "a",
        "b",
        "state_trim",
    }
    assert all(elapsed_ms >= 0 for elapsed_ms in registry.last_timings_ms.values())


def test_default_processors_build_one_typed_fact_state_and_brief() -> None:
    """The default stack derives typed facts once and adds presentation only."""
    store, world = _world_with_epoch()
    processors = default_processors()
    registry = HookRegistry(processors)

    state = registry.run(HookContext(
        hook=HookPoint.SNAPSHOT_LOADED,
        world=world,
        agent_state=store.agent_state,
    ))

    assert [processor.name for processor in processors] == ["agent_facts", "turn_brief"]
    assert state.variables == {}
    assert state.facts is not None
    assert state.facts.affordances.by_id
    assert state.facts.actor.economy is not None
    assert state.facts.contacts.visible_hostile_uuids
    assert state.briefs
    assert "Actor:" in state.briefs[-1].text


def test_typed_facts_expose_doors_water_and_hazards() -> None:
    """Typed facts retain first-class terrain and object policy inputs."""
    store, world = _world_with_epoch()
    world.known_objects["door"] = ObservationObjectFact(
        uuid="door",
        name="Stone Door",
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=[],
        position=(3, 1),
        state={"is_open": False},
    )
    world.known_tiles["2,1"] = ObservationTileFact(
        key="2,1",
        position=(2, 1),
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=[],
        walking_cost=10,
        is_hazardous=True,
        directional_blocks_movement={"east": True},
    )
    registry = HookRegistry(default_processors())

    state = registry.run(HookContext(
        hook=HookPoint.SNAPSHOT_LOADED,
        world=world,
        agent_state=store.agent_state,
    ))
    queries = SubjectiveQueries(world, state)

    assert state.variables == {}
    assert state.facts is not None
    assert state.facts.topology.slow_positions == frozenset({(2, 1)})
    assert state.facts.topology.hazardous_positions == frozenset({(2, 1)})
    assert state.facts.objects.closed_door_uuids == ("door",)
    assert queries.known_closed_doors()[0].uuid == "door"
    assert queries.safe_movement_rows()


def test_processor_hook_filters_avoid_reducing_the_same_frame_repeatedly() -> None:
    """Action and epoch hooks reuse facts produced by the frame hook."""
    store, world = _world_with_epoch()
    registry = HookRegistry(default_processors())

    frame_state = registry.run(HookContext(
        hook=HookPoint.FRAME_APPLIED,
        world=world,
        agent_state=store.agent_state,
    ))
    frame_facts = frame_state.facts
    assert frame_facts is not None
    assert set(registry.last_timings_ms) == {"state_copy", "agent_facts", "state_trim"}

    action_state = registry.run(HookContext(
        hook=HookPoint.ACTION_COMPLETED,
        world=world,
        agent_state=frame_state,
    ))
    assert action_state.facts is frame_facts
    assert set(registry.last_timings_ms) == {"state_copy", "state_trim"}

    epoch_state = registry.run(HookContext(
        hook=HookPoint.EPOCH_STARTED,
        world=world,
        agent_state=action_state,
    ))
    assert epoch_state.facts is frame_facts
    assert set(registry.last_timings_ms) == {"state_copy", "turn_brief", "state_trim"}
def test_combat_memory_groups_multi_application_blocker_episode_idempotently() -> None:
    """Six blocked darts are one observed blocker episode, not six trials."""
    store, world = _world_with_epoch()
    assert world.current_epoch is not None
    source_uuid = world.current_epoch.actor_uuid
    target_uuid = next(
        entity_uuid
        for entity_uuid in world.known_entities
        if entity_uuid not in world.session.controlled_entity_uuids
    )
    world.combat_logs = [
        _effect_episode_log(
            source_uuid,
            target_uuid,
            "spell.magic_missile",
            blocked_applications=6,
        )
    ]
    registry = HookRegistry(default_processors())

    first = registry.run(HookContext(
        hook=HookPoint.SNAPSHOT_LOADED,
        world=world,
        agent_state=store.agent_state,
    ))
    second = registry.run(HookContext(
        hook=HookPoint.SNAPSHOT_LOADED,
        world=world,
        agent_state=first,
    ))

    assert first.facts is not None
    assert second.facts is not None
    hypothesis = first.facts.combat_memory.hypothesis_for(
        target_uuid,
        "spell.magic_missile",
    )
    assert hypothesis is not None
    assert hypothesis.blocked_episodes == 1
    assert hypothesis.total_episodes == 1
    assert hypothesis.blocked_applications == 6
    assert hypothesis.total_applications == 6
    assert hypothesis.block_probability == 2 / 3
    assert second.facts.combat_memory == first.facts.combat_memory


def test_combat_memory_incremental_reduction_equals_resync_rebuild() -> None:
    """Incremental hooks and a fresh snapshot derive identical hypotheses."""
    _store, world = _world_with_epoch()
    assert world.current_epoch is not None
    source_uuid = world.current_epoch.actor_uuid
    target_uuid = next(
        entity_uuid
        for entity_uuid in world.known_entities
        if entity_uuid not in world.session.controlled_entity_uuids
    )
    first_log = _effect_episode_log(
        source_uuid,
        target_uuid,
        "spell.magic_missile",
        blocked_applications=6,
    )
    world = world.model_copy(update={"combat_logs": [first_log]})
    previous = derive_agent_facts(world).facts
    next_world = world.model_copy(update={
        "combat_logs": [
            first_log,
            _effect_episode_log(
                source_uuid,
                target_uuid,
                "spell.magic_missile",
                blocked_applications=0,
                successful_applications=3,
            ),
        ]
    })

    incremental = derive_agent_facts(
        next_world,
        previous_world=world,
        previous_facts=previous,
    ).facts.combat_memory
    rebuilt = derive_agent_facts(next_world).facts.combat_memory

    assert incremental == rebuilt
    hypothesis = rebuilt.hypothesis_for(target_uuid, "spell.magic_missile")
    assert hypothesis is not None
    assert hypothesis.blocked_episodes == 1
    assert hypothesis.total_episodes == 2
    assert hypothesis.block_probability == 0.5


def test_combat_memory_has_deterministic_episode_and_hypothesis_bounds() -> None:
    """Subjective combat evidence remains finite under a long encounter."""
    _store, world = _world_with_epoch()
    assert world.current_epoch is not None
    source_uuid = world.current_epoch.actor_uuid
    target_uuid = "bounded-target"
    repeated = [
        _effect_episode_log(
            source_uuid,
            target_uuid,
            "spell.magic_missile",
            blocked_applications=1,
        )
        for _ in range(6)
    ]
    repeated_world = world.model_copy(update={"combat_logs": repeated})
    repeated_memory = derive_agent_facts(repeated_world).facts.combat_memory
    repeated_hypothesis = repeated_memory.hypothesis_for(
        target_uuid,
        "spell.magic_missile",
    )
    assert repeated_hypothesis is not None
    assert repeated_hypothesis.blocked_episodes == 4
    assert repeated_hypothesis.total_episodes == 4
    assert repeated_hypothesis.episode_log_indices == (2, 3, 4, 5)

    distinct = [
        _effect_episode_log(
            source_uuid,
            f"target-{index}",
            f"effect-{index}",
            blocked_applications=1,
        )
        for index in range(33)
    ]
    world = world.model_copy(update={"combat_logs": [*repeated, *distinct]})

    memory = derive_agent_facts(world).facts.combat_memory

    assert len(memory.hypotheses) == 32
    assert memory.hypothesis_for(target_uuid, "spell.magic_missile") is None
    assert memory.hypothesis_for("target-0", "effect-0") is None
    newest = memory.hypothesis_for("target-32", "effect-32")
    assert newest is not None
    assert len(newest.episode_log_indices) <= 4
