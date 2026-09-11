"""Previously unseen actors arrive from saved history with their current state."""

from typing import Literal
import json

import pytest

from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from game.animation_data import load_animation_data
from game.attack import bind_attack
from game.motion import bind_motion, sample_motion
from game.presentation import reduce_lineage as reduce_native_lineage
from game.player_projection import lineage_branch, reduce_lineage, stage_lineage
from game.player_facts import SensoryFact, StepFact
from game.replay import decode_sequence, encode_sequence
from game.scene import scene_actors
from tests.game.discovery_scenarios import discovery_history
from tests.game.player_helpers import player_history


def test_initial_archive_excludes_existing_hidden_actor_payloads() -> None:
    history = discovery_history(existing_hidden=True)
    payload = encode_sequence(history.initialization, history.lineages)
    before, (discovery, _) = decode_sequence(payload)
    admission, = discovery.admissions
    identity = admission.actor.uuid
    # The received initializer contains permitted event payloads. Diagnostic
    # objective-row headers remain a separately documented archive limitation.
    initialization = json.loads(payload)["initialization"]
    for field in ("admitted", "conditions", "admissions"):
        assert str(identity) not in json.dumps(initialization[field])
    assert set(before.actors) == {before.observer_uuid}
    revealed = reduce_native_lineage(before, discovery).actors[identity]
    assert revealed.normal_hp == 33
    item_uuid = dict(revealed.equipment)[WeaponSlot.MELEE_MAIN.value]
    assert next(item for item in revealed.items if item.item_uuid == item_uuid).item_id == "weapon.dagger"
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("mode", ("enter_view", "deploy_later"))
def test_saved_discovery_admits_current_actor_without_private_history(mode: Literal["enter_view", "deploy_later"]) -> None:
    history = discovery_history(mode=mode)
    original, lineages = history.before, history.lineages
    payload = encode_sequence(history.initialization, lineages)
    before, (restored, later) = decode_sequence(payload)
    assert before == original and (restored, later) == lineages
    admission, = restored.admissions
    identity = admission.actor.uuid
    assert identity not in before.actors
    assert before.senses is not None and identity not in before.senses.entities
    assert admission.actor.normal_hp == 33
    assert admission.contact is not None and admission.contact.visual
    assert admission.event_uuid in {row.event_uuid for row in restored.objective_rows}
    assert EventQueue.event_cursor() == 0

    before, (restored, later) = player_history(history)
    assert before.senses is not None
    admission, = restored.observations
    data = load_animation_data()
    prepared = stage_lineage(before, restored)
    assert prepared.actors[identity] == admission.actor
    assert prepared.actors[before.observer_uuid] == before.actors[before.observer_uuid]
    assert identity not in before.actors and identity not in before.senses.entities
    actors = scene_actors(prepared, data, {})
    assert str(identity) in {actor.contact.actor_uuid for actor in actors}
    item = next(item for item in prepared.actors[identity].visual_loadout.layers
                if item.slot == WeaponSlot.MELEE_MAIN.value)
    assert item.item_id == "weapon.dagger"
    after = reduce_lineage(before, restored)
    assert after.actors[identity].normal_hp == 33
    attack = bind_attack(after, later, data)
    assert attack is not None and attack.timeline.target.actor_uuid == str(identity)
    assert attack.timeline.target.hp == 33
    assert not later.observations
    assert attack.after == reduce_lineage(after, later)
    assert attack.after.actors[identity].normal_hp < 33
    assert EventQueue.event_cursor() == 0


def test_discovery_is_applied_at_its_actual_movement_step() -> None:
    history = discovery_history()
    before, lineages = history.before, history.lineages
    state, (lineage, _) = decode_sequence(encode_sequence(history.initialization, lineages))
    assert state == before
    state, (lineage, _) = player_history(history)
    restored_before = state
    identity = lineage.observations[0].actor.uuid
    steps = tuple(event for event in lineage.events if isinstance(event.fact, StepFact))
    assert len(steps) > 1
    admitted_at: list[tuple[int, int]] = []
    for step in steps:
        branch = lineage_branch(lineage, step)
        previous = state
        state = reduce_lineage(state, branch)
        sensory = tuple(event.fact for event in branch.events if isinstance(event.fact, SensoryFact))
        if any(identity in event.entity_contacts_changed for event in sensory):
            assert identity not in previous.actors and identity in state.actors
            assert isinstance(step.fact, StepFact)
            admitted_at.append(step.fact.to_position)
        else:
            assert identity not in state.actors
    assert admitted_at == [(4, 3)]

    data = load_animation_data()
    motion = bind_motion(restored_before, lineage, data)
    assert motion is not None and len(motion.legs) == len(steps)
    for leg in motion.legs:
        sampled = sample_motion(motion, data, leg.end_ms - 0.01)
        assert sampled.displayed is not None and identity not in sampled.displayed.actors
    sampled = sample_motion(motion, data, motion.legs[-1].end_ms)
    assert sampled.displayed is not None and sampled.displayed.actors[identity].normal_hp == 33
    assert str(identity) in {actor.contact.actor_uuid for actor in scene_actors(sampled.displayed, data, {})}
    assert EventQueue.event_cursor() == 0
