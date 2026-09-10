"""Public casts retain historical animation while subjective state advances.

These cases connect real discovered actions and complete engine lineages to
the existing authored sampler. They do not recreate spell mechanics in fixtures.
"""

from dataclasses import dataclass, replace
import random
from uuid import UUID, uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import get_available_actions, register_spell
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.controller import HumanController
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.dice import AttackOutcome
from dnd.core.events import (
    DamageAppliedEvent, DeathEvent, EntityCreatedEvent, Event, EventPhase, EventQueue, EventType,
    LifeStateChangeEvent, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType,
    TakeDamageEvent,
)
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import FireBolt
from dnd.world_authoring import project_world_tile
from game.animation import body_clip, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import AnimationData
from game.combat import bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_lineage, reduce_lineage, seed_actors,
)


@dataclass(frozen=True)
class PublicCasts:
    seed: PresentationTarget
    first: CompletedLineage
    second: CompletedLineage
    declaration: Event
    recipient: UUID
    authoritative_hp: tuple[int, int, int]


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


@pytest.fixture
def casts() -> PublicCasts:
    """Compose known actors, discover a real spell, and spend two actual turns."""
    grid = reset_engine_runtime(grid_size=(8, 8))
    random_state = random.getstate()
    game = Game()
    actors: list[Entity] = []
    births: list[EntityCreatedEvent] = []
    for name, position, faction in (
        ("Caster", (1, 1), "heroes"),
        ("Recipient", (4, 1), "monsters"),
    ):
        actor = Entity.create(
            uuid4(), name,
            config=EntityConfig(
                position=position, faction=faction,
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums",
                )]),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                appearance=AppearanceConfig(
                    visual_scale=0.5, body_category="NakedBody", has_beard=False,
                ),
            ),
        )
        if name == "Caster":
            register_spell(actor, FireBolt, caster_level=1)
        births.append(actor.compose_entity())
        game.deploy_entity(actor, position)
        actors.append(actor)
    caster, recipient = actors
    Entity.update_all_entities_senses()
    encounter = Encounter(name="Historical cast contract", source_entity_uuid=uuid4())
    for actor in actors:
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
    random.seed(0)
    encounter.start_encounter()
    encounter.start_turn()
    while encounter.get_current_entity() is not caster:
        encounter.next_turn()

    seed = seed_actors(
        PresentationTarget(
            generation=EventQueue.generation_id(), observer_uuid=caster.uuid,
            tiles={position: project_world_tile(tile) for position, tile in grid.get_all_tiles().items()},
            senses=capture_senses_snapshot(caster.senses),
            reducer_cursor=EventQueue.event_cursor(),
        ),
        tuple(births),
        active_weapon_sets={actor.uuid: actor.equipment.active_weapon_set for actor in actors},
    )
    histories: list[CompletedLineage] = []
    hp = [recipient.get_normal_hp()]
    first_declaration: Event | None = None
    for cast_number in (1, 2):
        if cast_number == 2:
            encounter.next_turn()
            while encounter.get_current_entity() is not caster:
                encounter.next_turn()
        action = next(
            row for row in get_available_actions(caster).all_actions
            if row.behavior_id == "spell.fire_bolt"
        )
        target = next(row for row in action.valid_targets if row.target_uuid == recipient.uuid)
        start = EventQueue.event_cursor()
        random.seed(0)
        terminal = encounter.execute_action(caster.uuid, action.template_name, target.index)
        assert terminal is not None and terminal.phase is EventPhase.COMPLETION
        assert caster.action_economy.actions.normalized_score == 0
        if first_declaration is None:
            first_declaration = next(event for _, event in EventQueue.iter_events_since(start))
        histories.append(capture_lineage(terminal, observer_uuid=caster.uuid))
        hp.append(recipient.get_normal_hp())
    random.setstate(random_state)
    assert first_declaration is not None
    return PublicCasts(seed, histories[0], histories[1], first_declaration, recipient.uuid, (hp[0], hp[1], hp[2]))


def test_later_public_cast_reduces_without_retiming_or_overwriting_active_history(
    casts: PublicCasts, data: AnimationData,
) -> None:
    assert casts.authoritative_hp == (80, 73, 66)
    damage = next(event for event in casts.first.events if type(event) is DamageAppliedEvent)
    incoming = next(event for event in casts.first.events if type(event) is TakeDamageEvent)
    assert damage.parent_lineage == incoming.lineage_uuid
    assert incoming.parent_lineage == casts.first.root.lineage_uuid
    assert all(event.phase is EventPhase.COMPLETION for event in casts.first.events)
    assert {
        event.lineage_uuid for event in casts.first.events
        if event.parent_lineage == casts.first.root.lineage_uuid
    } == set(casts.first.root.children_lineages)
    assert all(
        event.uuid in {row.event_uuid for row in casts.first.objective_rows}
        for event in casts.first.events
    )
    first = bind_cast(casts.seed, casts.first, data)
    assert first.timeline.source.applications[0].target.hp == 80
    assert first.timeline.source.applications[0].resulting_hp == 73
    assert first.timeline.source.applications[0].application_id is None
    assert first.timeline.source.caster.grid == (1, 1)
    assert first.timeline.source.applications[0].target.grid == (4, 1)
    assert first.timeline.source.applications[0].target.life_state is LifeState.ALIVE
    assert first.timeline.recipe == data.drafts["spell.fire_bolt"]
    hp_anchor = first.timeline.applications[0].hp_ms
    assert hp_anchor is not None and hp_anchor > 0
    sample_times = (0.0, first.timeline.release_ms, hp_anchor - 0.01, hp_anchor, first.timeline.complete_ms)
    original_samples = tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times)
    assert original_samples[2].vitals[0].hp == 80
    assert original_samples[3].vitals[0].hp == 73

    latest_first = reduce_lineage(casts.seed, casts.first)
    latest_second = reduce_lineage(latest_first, casts.second)
    assert casts.seed.actors[casts.recipient].normal_hp == 80
    assert latest_first.actors[casts.recipient].normal_hp == 73
    assert latest_second.actors[casts.recipient].normal_hp == 66
    assert latest_second.actors[casts.recipient].temporary_hp == 0
    second = bind_cast(first.after, casts.second, data)
    assert second.timeline.source.applications[0].target.hp == 73
    assert second.timeline.source.applications[0].resulting_hp == 66
    assert tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times) == original_samples
    assert latest_first == first.after
    assert latest_second == second.after
    assert bind_cast(casts.seed, casts.first, data).timeline == first.timeline

    # The same saved input must still replay after all authoritative owners vanish.
    reset_engine_runtime()
    replay_first = bind_cast(casts.seed, casts.first, data)
    replay_second = bind_cast(replay_first.after, casts.second, data)
    assert replay_first.timeline == first.timeline
    assert replay_second.timeline == second.timeline
    assert replay_second.after == latest_second
    assert tuple(sample_cast(replay_first.timeline, elapsed) for elapsed in sample_times) == original_samples


def test_real_unfinished_declaration_is_not_a_renderable_lineage(casts: PublicCasts) -> None:
    assert casts.declaration.phase is EventPhase.DECLARATION
    with pytest.raises(ValueError, match="complet|terminal"):
        capture_lineage(casts.declaration, observer_uuid=casts.seed.observer_uuid)


def test_missing_historical_recipient_fails_instead_of_using_live_entity(
    casts: PublicCasts, data: AnimationData,
) -> None:
    incomplete = replace(casts.seed, actors={
        actor_uuid: actor for actor_uuid, actor in casts.seed.actors.items()
        if actor_uuid != casts.recipient
    })
    assert Entity.get(casts.recipient) is not None
    with pytest.raises(ValueError, match="actor|target|recipient|baseline"):
        bind_cast(incomplete, casts.first, data)


@pytest.mark.parametrize(
    ("second_attack_seed", "expected_outcome", "expected_hp", "expected_life"),
    (
        pytest.param(1, AttackOutcome.MISS, 3, LifeState.ALIVE, id="miss"),
        pytest.param(17, AttackOutcome.HIT, -4, LifeState.DEAD, id="lethal"),
    ),
)
def test_canonical_goblin_marker_and_cast_history_survive_turns_and_runtime_reset(
    second_attack_seed: int, expected_outcome: AttackOutcome,
    expected_hp: int, expected_life: LifeState,
) -> None:
    data = load_animation_data(rig_files=(DATA_ROOT.parent / "rigs/goblin01.json",))
    script = iter_combat_demo(goblin_recipient=True, second_attack_seed=second_attack_seed)
    seed = next(script)
    assert isinstance(seed, PresentationTarget)
    recipient = next(
        actor for actor in seed.actors.values()
        if actor.creature_content_ref == "content.neurodragon:creature:creature.goblin@1"
    )
    assert recipient.normal_hp == 10

    hit = next(script)
    assert isinstance(hit, CompletedLineage)
    damage = next(event for event in hit.events if isinstance(event, DamageAppliedEvent))
    marker = next(event for event in hit.events if event.event_type is EventType.CONDITION_APPLICATION)
    marker_fact = next(fact for fact in hit.conditions if fact.event_uuid == marker.uuid)
    assert type(marker) is Event
    assert marker_fact.name == "HasTakenDamage" and marker_fact.category is ConditionCategory.INTERNAL
    assert marker.parent_lineage == damage.lineage_uuid
    assert marker.lineage_uuid in damage.children_lineages
    assert marker.parent_event is not None
    parent = EventQueue.get_event_by_uuid(marker.parent_event)
    assert isinstance(parent, DamageAppliedEvent) and parent.phase is EventPhase.EFFECT
    assert parent.lineage_uuid == damage.lineage_uuid
    live_marker = EventQueue.get_event_by_uuid(marker.uuid)
    assert isinstance(live_marker, ConditionApplicationEvent)
    assert marker.lineage_uuid == live_marker.lineage_uuid
    assert marker.parent_event == live_marker.parent_event
    assert marker_fact.condition_uuid == live_marker.condition.uuid
    assert marker_fact.name == live_marker.condition.name

    first = bind_cast(seed, hit, data)
    latest_first = reduce_lineage(seed, hit)
    hp_anchor = first.timeline.applications[0].hp_ms
    assert hp_anchor is not None
    first_times = (0.0, hp_anchor - 0.01, hp_anchor, first.timeline.complete_ms)
    first_samples = tuple(sample_cast(first.timeline, elapsed) for elapsed in first_times)
    assert tuple(sample.vitals[0].hp for sample in first_samples) == (10, 10, 3, 3)
    assert latest_first == first.after

    # Requesting the second operation advances actual Encounter turns, including
    # the Goblin's condition duration; retained presentation keeps its passive facts.
    second_lineage = next(script)
    script.close()
    assert isinstance(second_lineage, CompletedLineage)
    assert isinstance(second_lineage.root, SpellEvent)
    assert second_lineage.root.attack_outcome is expected_outcome
    for event in second_lineage.events:
        assert event.phase is EventPhase.COMPLETION
        assert set(event.children_lineages) == {
            child.lineage_uuid for child in second_lineage.events
            if child.parent_lineage == event.lineage_uuid
        }
    assert next(fact for fact in hit.conditions if fact.event_uuid == marker.uuid) == marker_fact
    second = bind_cast(first.after, second_lineage, data)
    latest_second = reduce_lineage(latest_first, second_lineage)
    assert tuple(
        state.actors[recipient.uuid].normal_hp for state in (seed, latest_first, latest_second)
    ) == (10, 3, expected_hp)
    assert latest_second.actors[recipient.uuid].life_state is expected_life
    assert second.timeline.source.applications[0].target.hp == 3
    assert second.after == latest_second
    final_sample = sample_cast(second.timeline, second.timeline.complete_ms)
    assert final_sample.vitals[0].hp == expected_hp
    assert final_sample.vitals[0].life_state is expected_life
    assert tuple(sample_cast(first.timeline, elapsed) for elapsed in first_times) == first_samples

    if expected_life is LifeState.DEAD:
        incoming = next(event for event in second_lineage.events if isinstance(event, TakeDamageEvent))
        death = next(event for event in second_lineage.events if isinstance(event, DeathEvent))
        life = next(event for event in second_lineage.events if isinstance(event, LifeStateChangeEvent))
        spatial = next(event for event in second_lineage.events if isinstance(event, SpatialChangeEvent))
        senses = next(
            event for event in second_lineage.events
            if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == seed.observer_uuid
        )
        assert death.parent_lineage == incoming.lineage_uuid
        assert life.parent_lineage == spatial.parent_lineage == death.lineage_uuid
        assert life.parent_event == spatial.parent_event
        assert any(
            row.event_uuid == spatial.parent_event and row.phase == EventPhase.EXECUTION.value
            and row.lineage_uuid == death.lineage_uuid for row in second_lineage.objective_rows
        )
        assert spatial.change_type is SpatialChangeType.PERCEIVABILITY_CHANGED
        assert spatial.entity_uuid == life.entity_uuid == death.entity_uuid == recipient.uuid
        assert spatial.position == first.timeline.source.applications[0].target.grid
        assert senses.parent_lineage == spatial.lineage_uuid
        assert senses.entity_contacts_removed == {recipient.uuid}
        assert latest_first.senses is not None and recipient.uuid in latest_first.senses.entities
        assert latest_second.senses is not None and recipient.uuid not in latest_second.senses.entities
        assert latest_second.actors[recipient.uuid].last_visual_position == first.timeline.source.applications[0].target.grid
        assert life.previous_state is LifeState.ALIVE and life.new_state is LifeState.DEAD
        assert life.normal_hit_points == death.final_hp == expected_hp

        # Identity survives the causal history; contact loss must remain recorded
        # on the terminal versions instead of becoming a fabricated location grant.
        observer, recipient_key = str(seed.observer_uuid), str(recipient.uuid)
        assert observer in second_lineage.root.identified_entity_observer_uuids[recipient_key]
        assert observer not in second_lineage.root.located_entity_observer_uuids[recipient_key]
        for event in second_lineage.events:
            original = EventQueue.get_event_by_uuid(event.uuid)
            assert original is not None
            assert event.parent_event == original.parent_event
            assert event.parent_lineage == original.parent_lineage
            assert event.identified_entity_observer_uuids == original.identified_entity_observer_uuids
            assert event.located_entity_observer_uuids == original.located_entity_observer_uuids

        effect = second.timeline.applications[0].damage_start_ms
        assert effect is not None and second.timeline.applications[0].hp_ms == effect
        before = sample_cast(second.timeline, effect - 0.01)
        at_effect = sample_cast(second.timeline, effect)
        assert (before.vitals[0].hp, before.vitals[0].life_state) == (3, LifeState.ALIVE)
        assert (at_effect.vitals[0].hp, at_effect.vitals[0].life_state) == (-4, LifeState.DEAD)
        assert at_effect.bodies[1].clip == data.death_context.bodyClip
        assert at_effect.bodies[1].frame == 0
        death_clip = body_clip(data, second.timeline.source.applications[0].target, data.death_context.bodyClip)
        assert final_sample.bodies[1].clip == data.death_context.bodyClip
        assert final_sample.bodies[1].frame == death_clip.frames - 1
        assert sample_cast(second.timeline, second.timeline.complete_ms + 1000).bodies[1] == final_sample.bodies[1]
    else:
        assert not any(isinstance(event, DamageAppliedEvent) for event in second_lineage.events)
        assert not second.timeline.source.applications[0].damage_applied

    reset_engine_runtime()
    replay_first = bind_cast(seed, hit, data)
    replay_second = bind_cast(replay_first.after, second_lineage, data)
    assert replay_first.timeline == first.timeline
    assert replay_second.timeline == second.timeline
    assert replay_second.after == latest_second
    assert tuple(sample_cast(replay_first.timeline, elapsed) for elapsed in first_times) == first_samples
    assert sample_cast(replay_second.timeline, replay_second.timeline.complete_ms) == final_sample
    assert next(fact for fact in hit.conditions if fact.event_uuid == marker.uuid) == marker_fact
