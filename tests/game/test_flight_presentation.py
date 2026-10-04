"""Native ground-to-ground flight retains its path and one continuous lift."""

from pathlib import Path

import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_motion, sample_motion, MotionLeg, motion_leg_contact
from game.player_facts import MovementFact
from game.player_reduction import reduce_lineage
from tests.game.movement_scenarios import movement_history
from tests.game.player_helpers import player_history
from tests.game.scenarios import movement_with_paralysis
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH
from devtools.animation_review.summoning_cases import summoning_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(Path("game/data/rigs").glob("*.json")))


@pytest.mark.parametrize("route,battlefield", (
    (((3, 3), (4, 3)), "battlefield.open_floor_bright"),
    (((3, 3), (7, 5)), "battlefield.open_floor_bright"),
    (((8, 5), (8, 4)), "battlefield.elevation_proving_ground"),
    (((8, 4), (8, 5)), "battlefield.elevation_proving_ground"),
))
def test_spell_granted_flight_keeps_ground_endpoints_height_and_continuous_intermediate_lift(data, route, battlefield):
    state, roots = player_history(movement_history(route=route, battlefield_id=battlefield, flight=True))
    seen = 0
    for root in roots:
        if isinstance(root.root.fact, MovementFact):
            motion = bind_motion(state, root, data)
            assert motion is not None and motion.legs
            assert motion.clip == "AttackRun" and not motion.body_loops
            start = sample_motion(motion, data, 0)
            final = sample_motion(motion, data, motion.complete_ms)
            assert start.contact is not None and final.contact is not None
            assert start.contact.grid == route[0] and final.contact.grid == route[-1]
            assert start.lift_px == final.lift_px == 0
            assert final.contact.elevation_steps == state.tiles[route[-1]].elevation_steps
            for leg in motion.legs:
                middle = sample_motion(motion, data, (leg.start_ms + leg.end_ms) / 2)
                assert middle.contact is not None and middle.lift_px > 0
                assert middle.body is not None and middle.body.clip == "AttackRun"
                assert middle.body.frame == 7
            for left, right in zip(motion.legs, motion.legs[1:]):
                before = sample_motion(motion, data, left.end_ms - .0001)
                after = sample_motion(motion, data, right.start_ms)
                assert before.lift_px == pytest.approx(after.lift_px, abs=.001)
                assert after.lift_px > 0
            assert sample_motion(motion, data, motion.complete_ms / 2) == sample_motion(motion, data, motion.complete_ms / 2)
            seen += 1
        state = reduce_lineage(state, root)
    assert seen == 1


@pytest.mark.parametrize("form,slot,clip", (("huntsman_wing_devil", 5, "Jump"), ("fellwing_devil", 6, "Flight")))
def test_innate_wings_use_same_lift_without_a_ground_run(data, form, slot, clip):
    state, roots = player_history(summoning_history(form=form, family="fiend", slot=slot, flight=True), role="caster")
    seen = 0
    for root in roots:
        if isinstance(root.root.fact, MovementFact):
            motion = bind_motion(state, root, data)
            assert motion is not None and motion.clip == clip and not motion.body_loops
            assert sample_motion(motion, data, motion.complete_ms / 2).lift_px > 0
            assert sample_motion(motion, data, motion.complete_ms).lift_px == 0
            seen += 1
        state = reduce_lineage(state, root)
    assert seen


@pytest.mark.parametrize("seed", (0, 1, 17))
def test_native_flight_reaction_holds_source_pose_and_respects_speed_or_stop(data, seed):
    state, roots = player_history(movement_with_paralysis(seed, flight=True), role="mover")
    motion = bind_motion(state, roots[0], data)
    assert motion is not None and motion.reactions
    if motion.legs:
        travel = sum(leg.end_ms-leg.start_ms for leg in motion.legs)
        assert travel == pytest.approx(data.movement_context.walkStepDurationMs/2)
        reaction = motion.reactions[0]
        just_before = sample_motion(motion, data, reaction.start_ms-.00001)
        held = sample_motion(motion, data, reaction.start_ms)
        assert held.contact is not None and held.body is not None
        assert held.lift_px == held.contact.body_lift_px == pytest.approx(just_before.lift_px)
        assert held.body.clip == just_before.body.clip == "AttackRun"
        assert held.body.frame == just_before.body.frame == 7
    else:
        assert motion.settled_contact is not None and motion.settled_contact.grid == (3, 3)
        assert all(reaction.lift_px == 0 for reaction in motion.reactions)


@pytest.mark.parametrize("rising", (True, False))
def test_late_rise_and_early_descent_clear_known_tile_boundary(data, rising):
    # Exercise the pure path sampler with a two-level authored support edge.
    # Native admission/endpoints are covered separately by real elevated moves.
    state, roots = player_history(movement_history(route=((3, 3), (4, 3)), flight=True))
    motion = bind_motion(state, next(row for row in roots if isinstance(row.root.fact, MovementFact)), data)
    assert motion is not None
    height = 2 * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
    leg = MotionLeg((3, 3), (4, 3), 0 if rising else 2, 2 if rising else 0,
        0, 100, arc_height_px=height, curve_from=.9 if rising else 0,
        curve_to=1 if rising else .1, lift_phase_edges=(.2, .8), support_riser=(height, 0, 1))
    contact = motion_leg_contact(motion.actor, leg, data, 50)
    assert contact.elevation_steps + contact.body_lift_px / (HEIGHT_STEP_PIXELS*data.rig.TILE_W/TILE_WIDTH) >= 2
    assert motion_leg_contact(motion.actor, leg, data, 0).body_lift_px == 0 if not rising else True
    assert motion_leg_contact(motion.actor, leg, data, 100).body_lift_px == 0 if rising else True
