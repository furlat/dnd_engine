"""Real save-based paralysis on a longsword opportunity hit interrupts walking.

The existing configurable Ghoul rider is used with its CON10 save and actual
paralysis condition. It is not a full Hold Person spell or a new item proc.
"""

from dataclasses import replace
from types import MappingProxyType

import pytest

from dnd.actions import AttackEvent, JumpEvent, MovementEvent
from dnd.core.action_execution import MovementTerminationReason
from dnd.core.dice import AttackOutcome
from dnd.core.events import DamageAppliedEvent, EventPhase, SavingThrowEvent, StepMovementEvent
from dnd.core.life_types import LifeState
from game.animation import body_clip
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.attack import select_attack_profile
from game.choreography import sample_choreography
from game.combat import actor_contact
from game.motion import bind_motion, sample_motion
from game.presentation import PresentationTarget, reduce_lineage
from tests.game.scenarios import movement_with_paralysis


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


def authored_contact_ms(data: AnimationData, before: PresentationTarget, attack: AttackEvent) -> float:
    assert attack.behavior_id is not None
    profile = select_attack_profile(data.attack_recipes[attack.behavior_id], attack)
    assert profile is not None
    source = actor_contact(before, before.actors[attack.source_entity_uuid], data)
    clip = body_clip(data, source, profile.actor.clip)
    frame = next(anchor.frame for name in ("impact", "contact", "effect")
                 for anchor in profile.anchors if anchor.name == name)
    return frame * 1000 / (clip.fps * profile.actor.playbackSpeed)


@pytest.mark.parametrize("movement_behavior", ["action.move", "action.jump"])
@pytest.mark.parametrize(("seed", "maximum_hp", "outcome", "saved", "termination", "hp", "life"), [
    pytest.param(0, 80, AttackOutcome.HIT, False, MovementTerminationReason.INCAPACITATED,
                 73, LifeState.ALIVE, id="failed-CON10-stops-alive"),
    pytest.param(17, 80, AttackOutcome.HIT, True, MovementTerminationReason.COMPLETED,
                 73, LifeState.ALIVE, id="saved-CON10-continues"),
    pytest.param(1, 80, AttackOutcome.MISS, None, MovementTerminationReason.COMPLETED,
                 80, LifeState.ALIVE, id="miss-continues-without-save"),
    pytest.param(5, 4, AttackOutcome.CRIT, True, MovementTerminationReason.DEAD,
                 -7, LifeState.DEAD, id="lethal-hit-stops"),
])
def test_real_opportunity_rider_joins_before_the_step_commits_or_stops(
    data: AnimationData, movement_behavior: str, seed: int, maximum_hp: int, outcome: AttackOutcome,
    saved: bool | None, termination: MovementTerminationReason, hp: int, life: LifeState,
) -> None:
    before, lineage = movement_with_paralysis(seed, maximum_hp, movement_behavior=movement_behavior)
    # The public helper has reset the entire engine. Everything below replays
    # retained facts and authored data, including the condition identities.
    root = lineage.root
    assert isinstance(root, (MovementEvent, JumpEvent))
    mover_uuid = root.source_entity_uuid
    if isinstance(root, MovementEvent):
        assert root.termination_reason is termination
    else:
        assert root.objective_end_position == root.end_position
    committed = termination is MovementTerminationReason.COMPLETED
    assert root.end_position == ((2, 3) if committed else (3, 3))
    step, = (event for event in lineage.events if isinstance(event, StepMovementEvent))
    attack, = (event for event in lineage.events if isinstance(event, AttackEvent))
    assert step.parent_lineage == root.lineage_uuid and step.committed is committed
    assert attack.parent_lineage == step.lineage_uuid
    assert attack.behavior_id == "reaction.opportunity_attack" and attack.attack_outcome is outcome
    assert attack.target_entity_uuid == mover_uuid
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    assert all(event.phase is EventPhase.COMPLETION for event in lineage.events)
    assert all(event.parent_lineage in by_lineage for event in lineage.events if event is not root)
    assert all(child in by_lineage for event in lineage.events for child in event.children_lineages)
    saves = [event for event in lineage.events if isinstance(event, SavingThrowEvent)]
    if saved is None:
        assert not saves
    else:
        save, = saves
        assert save.parent_lineage == attack.lineage_uuid
        assert save.ability_name == "constitution" and save.get_dc() == 10
        assert save.result is saved
    conditions = {fact.name: fact for fact in lineage.conditions}
    disabling = {"Ghoul Paralysis", "Paralyzed"} if saved is False else set()
    assert set(conditions) & {"Ghoul Paralysis", "Paralyzed"} == disabling
    if disabling:
        by_uuid = {event.uuid: event for event in lineage.events}
        rider = by_uuid[conditions["Ghoul Paralysis"].event_uuid]
        paralyzed = by_uuid[conditions["Paralyzed"].event_uuid]
        assert rider.parent_lineage == attack.lineage_uuid
        assert paralyzed.parent_lineage == rider.lineage_uuid

    latest = reduce_lineage(before, lineage)
    assert latest.actors[mover_uuid].normal_hp == hp
    assert latest.actors[mover_uuid].life_state is life
    assert {fact.name for fact in latest.actors[mover_uuid].conditions} == disabling
    assert actor_contact(latest, latest.actors[mover_uuid], data).grid == root.end_position
    assert before.actors[mover_uuid].normal_hp == maximum_hp
    assert not before.actors[mover_uuid].conditions

    motion = bind_motion(before, lineage, data)
    assert motion is not None and len(motion.reactions) == 1
    reaction, = motion.reactions
    # The original Attack recipe/body owns contact, regardless of how the
    # compositor represents this Attack, its save and the two conditions.
    contact_ms = authored_contact_ms(data, before, attack)
    prior = sample_choreography(reaction.choreography, contact_ms - .001)
    impact = sample_choreography(reaction.choreography, contact_ms)
    assert prior.displayed.actors[mover_uuid].normal_hp == maximum_hp
    assert prior.displayed.actors[mover_uuid].life_state is LifeState.ALIVE
    assert not prior.displayed.actors[mover_uuid].conditions
    assert impact.displayed.actors[mover_uuid].normal_hp == hp
    assert impact.displayed.actors[mover_uuid].life_state is life
    assert {fact.name for fact in impact.displayed.actors[mover_uuid].conditions} == disabling
    applied = [event for event in lineage.events if isinstance(event, DamageAppliedEvent)]
    assert [event.resulting_normal_hp for event in applied] == ([] if saved is None else [hp])

    held = sample_motion(motion, data, reaction.start_ms)
    before_join = sample_motion(motion, data, reaction.end_ms - .001)
    assert held.reaction is reaction.choreography
    assert held.reaction_elapsed_ms == 0
    motion_impact = sample_motion(motion, data, reaction.start_ms + contact_ms)
    assert motion_impact.displayed is not None
    assert {fact.name for fact in motion_impact.displayed.actors[mover_uuid].conditions} == disabling
    assert before_join.reaction is reaction.choreography
    assert before_join.contact.grid == held.contact.grid
    assert before_join.lift_px == held.lift_px
    assert not before_join.complete
    assert reaction.end_ms - reaction.start_ms == pytest.approx(reaction.choreography.complete_ms)
    final = sample_motion(motion, data, motion.complete_ms)
    assert final.complete and final.reaction is None
    assert final.contact.grid == (root.end_position if committed else held.contact.grid)
    assert final.contact.hp == hp and final.contact.life_state is life
    assert final.lift_px == (0 if committed else held.lift_px)
    assert final.displayed is not None
    assert {fact.name for fact in final.displayed.actors[mover_uuid].conditions} == disabling
    if committed:
        resumed = sample_motion(motion, data, reaction.end_ms)
        assert resumed.reaction is None and not resumed.complete
        assert resumed.contact.grid == held.contact.grid
        assert resumed.lift_px == held.lift_px
        assert motion.complete_ms > reaction.end_ms
    else:
        assert motion.complete_ms == reaction.end_ms
    if isinstance(root, JumpEvent):
        context = data.movement_context
        duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
            context.jumpBaseDurationMs + context.jumpPerCellDurationMs))
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + context.jumpArcPerCellPx)
        fraction = min(.35, max(.12, data.movement_reaction_context.movementLeadInMs / duration))
        assert reaction.start_ms == pytest.approx(duration * fraction)
        assert held.contact.grid == pytest.approx((3 - fraction, 3))
        assert held.lift_px == pytest.approx(4 * arc * fraction * (1 - fraction))
        if committed:
            middle = sample_motion(motion, data, reaction.end_ms + duration * (.5 - fraction))
            assert middle.contact.grid == pytest.approx((2.5, 3))
            assert middle.lift_px == pytest.approx(arc)
            assert motion.complete_ms == pytest.approx(duration + reaction.choreography.complete_ms)
    assert sample_choreography(reaction.choreography, contact_ms - .001) == prior
    assert sample_motion(motion, data, reaction.start_ms) == held
    assert reduce_lineage(before, lineage) == latest


def test_authored_condition_transition_holds_the_real_reaction_beyond_its_attack(data: AnimationData) -> None:
    before, lineage = movement_with_paralysis(0, movement_behavior="action.jump")
    original = bind_motion(before, lineage, data)
    assert original is not None
    recipe = data.condition_recipes["condition.paralyzed"]
    alpha, duration_ms = .4, 2500.0
    changed_recipe = recipe.model_copy(update={
        "persistent": recipe.persistent.model_copy(update={"alphaMultiplier": alpha}),
        "application": recipe.application.model_copy(update={"durationMs": duration_ms}),
    })
    authored = replace(data, condition_recipes=MappingProxyType({
        **data.condition_recipes, "condition.paralyzed": changed_recipe,
    }))
    extended = bind_motion(before, lineage, authored)
    assert extended is not None
    original_reaction, = original.reactions
    reaction, = extended.reactions
    # Only the source-format presentation values changed. Real event identity,
    # authoritative HP/conditions and the failed Step remain exactly the same.
    assert reaction.choreography.after == original_reaction.choreography.after
    assert reaction.start_ms == original_reaction.start_ms
    assert reaction.end_ms > original_reaction.end_ms
    attack, = (event for event in lineage.events if isinstance(event, AttackEvent))
    contact_ms = authored_contact_ms(data, before, attack)
    assert reaction.choreography.complete_ms == pytest.approx(contact_ms + duration_ms)
    held = sample_motion(extended, authored, original_reaction.end_ms)
    assert held.reaction is reaction.choreography and not held.complete
    assert held.contact.grid == original_reaction.contact.grid
    assert held.lift_px == original_reaction.lift_px
    transitions = sample_choreography(reaction.choreography, original_reaction.choreography.complete_ms)
    fact = next(row for row in lineage.conditions if row.behavior_id == "condition.paralyzed")
    paralyzed = next(sample for transition, sample in zip(reaction.choreography.conditions, transitions.conditions)
                     if transition.event_uuid == fact.event_uuid)
    assert alpha < paralyzed.appearance.alpha < 1
    final = sample_motion(extended, authored, extended.complete_ms)
    assert final.complete and final.reaction is None and final.lift_px == held.lift_px
    assert final.contact.grid == held.contact.grid and final.contact.hp == 73
    assert final.displayed is not None
    mover_uuid = lineage.root.source_entity_uuid
    assert {fact.name for fact in final.displayed.actors[mover_uuid].conditions} == {"Paralyzed", "Ghoul Paralysis"}
    assert sample_motion(extended, authored, original_reaction.end_ms) == held
