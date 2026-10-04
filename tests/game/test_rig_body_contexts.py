"""Portable rig body data controls existing cues, without changing native facts."""

from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pygame
import pytest
from pydantic import ValidationError

from dnd.core.events import MovementTrajectory
from dnd.core.life_types import LifeState
from dnd.types.world import MovementMode
from game.animation import (
    ActorContact, BodySample, CastApplication, CastInput, body_context, compile_cast, compile_equipment,
    resolve_body_context, sample_cast, sample_equipment,
)
from game.animation_data import load_animation_data, validate_rig_body_contexts, resolve_player_layers
from game.animation_draw import LoadedBodyRows, actor_draw_commands
from game.animation_types import (
    ActionFrameAnchor, AnimationData, BodyRig, ContentBodyQualifier,
    MovementBodyQualifier, RigBodyContextBinding, RoleDefault,
)
from game.attack import bind_attack, sample_attack, select_attack_profile
from game.body_action import join_body_action, sample_body_action
from game.body_hop import sample_body_hop
from game.choreography import (BoundChoreography, bind_choreography, bind_motion, sample_choreography,
                               sample_motion, walk_bound_timelines)
from game.choreography_draw import load_choreography_media, load_motion_media
from game.condition_animation import (
    bind_condition_body, compile_condition, condition_body_pose, resolve_condition_appearance,
    sample_condition_body,
)
from game.forced_movement import sample_forced_body, sample_shove
from game.player_facts import AttackFact, MovementFact, SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from tests.game.concealment_scenarios import concealment_history
from tests.game.forced_movement_scenarios import forced_movement_history
from tests.game.movement_scenarios import movement_history
from tests.game.player_helpers import player_history
from tests.game.scenarios import attack_history, healing_history
from tests.game.trap_expansion_scenarios import trap_expansion_history
from tests.game.test_condition_animation import condition_fact, header


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))


def required_body(body: BodySample | None) -> BodySample:
    assert body is not None
    return body


@pytest.fixture
def graphics():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def authored(data, *rows):
    """Use real imported pixels with deliberately distinct, admitted clip clocks."""
    document = data.rigs[data.root_rig].model_dump(mode="json")
    document["clips"]["Alternate"] = {**document["clips"]["TakeDamage"], "frames": 6, "fps": 20}
    document["clips"]["Recovery"] = {**document["clips"]["Run"], "frames": 9, "fps": 10}
    document["body_contexts"] = [row.model_dump(mode="json") for row in rows]
    rig = BodyRig.model_validate_json(json.dumps(document))
    result = replace(data, rigs={**data.rigs, data.root_rig: rig})
    validate_rig_body_contexts(result)
    return result


def binding(role, *, clip="Alternate", marker=None, frame=2, speed=1., qualifier=None,
            reverse=False, loop=False, enabled=True, rest=None, keys=()):
    body = body_context(clip, speed, enabled=enabled, reversed=reverse, loop=loop,
        anchors=(ActionFrameAnchor(name=marker, frame=frame),) if marker else ())
    payload = body.model_dump(mode="json")
    payload["frameKeys"] = keys
    if rest is not None:
        payload.update(playback="final_rest", restFrame=rest)
    return RigBodyContextBinding.model_validate_json(json.dumps({"role": role,
        "qualifier": (qualifier or RoleDefault()).model_dump(mode="json"), "body": payload}))


def contact(data):
    return ActorContact(str(uuid4()), (3, 3), "S", 1, rig_id=data.root_rig)


def test_alternate_death_never_replays_upright_after_a_volley_downing(data):
    caster = contact(data)
    target = ActorContact("target", (6, 3), "S", 1, hp=1, rig_id="smallscale.goblin01")
    source = CastInput("volley", caster, (
        CastApplication("down", target, True, 1, 0, LifeState.DYING),
        CastApplication("dead", target, True, 1, 0, LifeState.DEAD),
    ))
    timeline = compile_cast(data, "spell.magic_missile", source)
    down, dead = timeline.applications
    assert down.hp_ms is not None and dead.damage_start_ms is not None
    assert down.life_body is not None
    assert dead.damage_start_ms < down.hp_ms + down.life_body.frames * 1000 / down.life_body.fps
    def victim(at):
        return next(body for body in sample_cast(timeline, at).bodies if body.actor_uuid == "target")
    assert victim(down.hp_ms).clip == "Die"
    beginning = victim(dead.damage_start_ms)
    assert (beginning.clip, beginning.frame) == ("Death", 14)
    assert victim(dead.damage_start_ms + 250) == beginning
    assert (victim(timeline.complete_ms).clip, victim(timeline.complete_ms).frame) == ("Death", 14)
    assert victim(dead.damage_start_ms) == beginning
    # An already dead recipient holds the source's final frame, without a replay.
    corpse = replace(target, life_state=LifeState.DEAD, hp=0)
    repeated = compile_cast(data, "spell.magic_missile", CastInput("later", caster, (
        CastApplication("corpse", corpse, True, 1, 0, LifeState.DEAD),)))
    assert all((body.clip, body.frame) == ("Death", 14)
               for at in (0, repeated.release_ms, repeated.complete_ms)
               for body in sample_cast(repeated, at).bodies if body.actor_uuid == "target")


def test_json_roundtrip_and_exact_then_default_then_shared_are_order_independent(data):
    recipe = data.drafts["spell.invisibility"]
    exact = ContentBodyQualifier(contentRef=recipe.definitionRef)
    default = binding("body_action", clip="Recovery", marker="effect")
    specific = binding("body_action", qualifier=exact, marker="effect")
    actor = contact(data)
    shared = body_context("Special1")
    for rows in ((default, specific), (specific, default)):
        adapted = authored(data, *rows)
        restored = BodyRig.model_validate_json(adapted.rigs[data.root_rig].model_dump_json())
        assert restored == adapted.rigs[data.root_rig]
        assert resolve_body_context(adapted, actor, "body_action", exact, shared) == specific.body
        other = ContentBodyQualifier(contentRef=data.drafts["spell.true_seeing"].definitionRef)
        assert resolve_body_context(adapted, actor, "body_action", other, shared) == default.body
        assert resolve_body_context(adapted, actor, "healing", RoleDefault(), shared) is shared
    # Rig selection depends on retained rig identity, never actor UUID/origin.
    assert resolve_body_context(adapted, replace(actor, actor_uuid=str(uuid4())), "body_action", exact, shared) == specific.body
    assert resolve_body_context(data, actor, "body_action", exact, shared) is shared


@pytest.mark.parametrize("mode,trajectory,connector", [
    (MovementMode.WALKING, MovementTrajectory.PATH, None),
    (MovementMode.FLYING, MovementTrajectory.PATH, None),
    (MovementMode.WALKING, MovementTrajectory.DIRECT_ARC, None),
    (MovementMode.WALKING, MovementTrajectory.CONNECTOR_TRANSFER, "window"),
    (None, MovementTrajectory.PATH, None),
])
def test_complete_movement_signature_has_no_independent_wildcards(data, mode, trajectory, connector):
    query = MovementBodyQualifier(movement_mode=mode, trajectory=trajectory,
                                  connector_presentation_key=connector)
    adapted = authored(data, binding("movement", qualifier=query), binding("movement", clip="Run", loop=True))
    assert resolve_body_context(adapted, contact(data), "movement", query, body_context("Idle")).actor.clip == "Alternate"
    other = query.model_copy(update={"connector_presentation_key": "another-window"})
    assert resolve_body_context(adapted, contact(data), "movement", other, body_context("Idle")).actor.clip == "Run"
    missing = query.model_dump(mode="json")
    del missing["movement_mode"]
    with pytest.raises(ValidationError):
        MovementBodyQualifier.model_validate_json(json.dumps(missing))


@pytest.mark.parametrize("mutation", ["duplicate", "unknown-role", "unknown-mode", "unknown-reference", "missing-clip",
    "missing-marker", "extra-marker", "unreachable-marker", "unreachable-key", "unreachable-rest",
    "hidden-slots", "disabled-travel", "loop-equipment", "unordered-keys", "unusable-qualifier"])
def test_bad_bindings_fail_at_data_admission(data, mutation):
    row = binding("body_action", marker="effect").model_dump(mode="json")
    document = data.rigs[data.root_rig].model_dump(mode="json")
    document["clips"]["Alternate"] = {**document["clips"]["TakeDamage"], "frames": 6}
    if mutation == "unknown-role": row["role"] = "new-runner"
    elif mutation == "unknown-mode":
        row.update(role="movement", qualifier={"kind": "movement", "movement_mode": "telepathy", "trajectory": "path", "connector_presentation_key": None})
    elif mutation == "unknown-reference":
        ref = data.drafts["spell.invisibility"].definitionRef.model_dump(mode="json")
        row["qualifier"] = {"kind": "content", "contentRef": {**ref, "content_id": "spell.unregistered"}}
    elif mutation == "missing-clip": row["body"]["actor"]["clip"] = "Missing"
    elif mutation == "missing-marker": row["body"]["anchors"] = []
    elif mutation == "extra-marker": row["body"]["anchors"].append({"name": "invented", "frame": 1})
    elif mutation == "unreachable-marker": row["body"]["anchors"][0]["frame"] = 6
    elif mutation == "unreachable-key": row = binding("movement", keys=((0., 0), (1., 6))).model_dump(mode="json")
    elif mutation == "unreachable-rest": row = binding("condition_hold", rest=6).model_dump(mode="json")
    elif mutation == "hidden-slots": row["body"]["actor"]["hiddenSlots"] = ["weapon"]
    elif mutation == "disabled-travel": row.update(role="movement"); row["body"]["actor"]["enabled"] = False
    elif mutation == "loop-equipment": row.update(role="equipment"); row["body"].update(playback="loop", anchors=[{"name": "commit", "frame": 1}])
    elif mutation == "unordered-keys": row.update(role="movement"); row["body"].update(anchors=[], frameKeys=[[0, 0], [.8, 2], [.4, 3], [1, 5]])
    elif mutation == "unusable-qualifier": row.update(role="healing", qualifier=ContentBodyQualifier(contentRef=data.drafts["spell.invisibility"].definitionRef).model_dump(mode="json")); row["body"]["anchors"] = []
    document["body_contexts"] = [row, row] if mutation == "duplicate" else [row]
    with pytest.raises(ValueError):
        rig = BodyRig.model_validate_json(json.dumps(document))
        validate_rig_body_contexts(replace(data, rigs={**data.rigs, data.root_rig: rig}))


@pytest.fixture(scope="module")
def invisibility():
    before, roots = player_history(concealment_history(reveal="none"), role="subject")
    for root in roots:
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.invisibility":
            return before, root
        before = reduce_lineage(before, root)
    raise AssertionError("Native Invisibility cast absent")


def test_body_action_effect_join_recovery_and_disabled_gesture_keep_native_children(data, invisibility):
    before, root = invisibility
    exact = ContentBodyQualifier(contentRef=data.drafts["spell.invisibility"].definitionRef)
    adapted = authored(data, binding("body_action", qualifier=exact, marker="effect", speed=2.),
                      binding("body_action_recovery", qualifier=exact, clip="Recovery", reverse=True))
    bound = bind_choreography(before, root, adapted)
    cue, = bound.body_actions
    assert cue.effect_ms == pytest.approx(50)
    assert cue.body_end_ms == pytest.approx(125)
    assert all(row.start_ms >= cue.effect_ms for row in bound.conditions)
    assert cue.complete_ms == pytest.approx(cue.join_ms + 800)
    joined = join_body_action(cue, adapted, 1200)
    assert joined.join_ms == 1200 and joined.complete_ms == 2000
    assert required_body(sample_body_action(joined, adapted, 1199)).clip == "Idle"
    assert (required_body(sample_body_action(joined, adapted, 1200)).clip, required_body(sample_body_action(joined, adapted, 1200)).frame) == ("Recovery", 8)
    # Sampling takes the retained selection even when the rig table later differs.
    changed = authored(data)
    assert sample_body_action(joined, changed, 1500) == sample_body_action(joined, adapted, 1500)
    disabled = authored(data, binding("body_action", qualifier=exact, clip="NotLoaded", enabled=False),
                         binding("body_action_recovery", qualifier=exact, clip="Recovery"))
    quiet = bind_choreography(before, root, disabled)
    gesture, = quiet.body_actions
    assert gesture.effect_ms == gesture.body_end_ms == 0
    assert quiet.after == bound.after and quiet.conditions
    assert required_body(sample_body_action(gesture, disabled, gesture.join_ms)).clip == "Recovery"
    assert sample_choreography(bound, cue.effect_ms) == sample_choreography(bound, cue.effect_ms)


@pytest.mark.parametrize("behavior", ["action.move", "action.jump"])
def test_real_motion_keeps_path_airtime_and_selects_body_and_recovery_once(data, behavior, graphics):
    before, roots = player_history(movement_history(route=((3, 3), (5, 3)), behavior=behavior))
    root = next(row for row in roots if isinstance(row.root.fact, MovementFact))
    fact = root.root.fact
    assert isinstance(fact, MovementFact)
    qualifier = MovementBodyQualifier(movement_mode=fact.movement_mode, trajectory=fact.trajectory,
                                      connector_presentation_key=fact.connector_presentation_key)
    adapted = authored(data, binding("movement", qualifier=qualifier, reverse=True),
                      binding("movement_recovery", qualifier=qualifier, clip="Recovery"))
    baseline, selected = bind_motion(before, root, data), bind_motion(before, root, adapted)
    assert baseline is not None and selected is not None
    assert selected.legs == baseline.legs and selected.states == baseline.states
    assert selected.recovery_start_ms == baseline.complete_ms
    assert selected.complete_ms == pytest.approx(baseline.complete_ms + 800)
    leg = selected.legs[0]
    for progress, frame in ((0., 5), (.5, 2), (.999, 0)):
        at = leg.start_ms + (leg.end_ms-leg.start_ms) * progress
        sample = sample_motion(selected, adapted, at)
        assert sample.body is not None and (sample.body.clip, sample.body.frame) == ("Alternate", frame)
        assert sample.contact == sample_motion(baseline, data, at).contact
    assert selected.recovery_start_ms is not None
    recovery = sample_motion(selected, adapted, selected.recovery_start_ms + 100)
    assert recovery.body is not None and (recovery.body.clip, recovery.body.frame) == ("Recovery", 1)
    assert sample_motion(selected, adapted, selected.complete_ms).complete
    rows: LoadedBodyRows = {}
    load_motion_media(selected, adapted, body_rows=rows)
    assert {key[3] for key in rows if key[1] == "Recovery"} == set(range(8))
    assert {key[3] for key in rows if key[1] == "Alternate"} == set(range(8))
    assert sample_motion(selected, adapted, leg.start_ms) == sample_motion(selected, adapted, leg.start_ms)


def test_real_shove_brace_release_recovery_use_selected_clock_without_changing_travel(data):
    before, (root,) = player_history(forced_movement_history())
    adapted = authored(data, binding("shove", marker="contact"),
        binding("forced_movement", marker="brace", reverse=True),
        binding("forced_movement_recovery", clip="Recovery"))
    baseline, selected = bind_choreography(before, root, data), bind_choreography(before, root, adapted)
    shove, = selected.shoves
    force, = selected.forced_movement
    old, = baseline.forced_movement
    assert shove.contact_ms == 100 and sample_shove(shove, adapted, 100).frame == 2
    assert force.start_ms == shove.contact_ms
    assert force.travel_start_ms-force.start_ms == 150  # reverse frame 5 -> brace 2
    assert force.travel_end_ms-force.travel_start_ms == pytest.approx(old.travel_end_ms-old.travel_start_ms)
    assert force.points == old.points and selected.after == baseline.after
    assert sample_forced_body(force, adapted, force.start_ms).frame == 5
    assert sample_forced_body(force, adapted, force.travel_start_ms + 100).frame == 2
    assert sample_forced_body(force, adapted, force.travel_end_ms + 51).frame == 1
    assert sample_forced_body(force, adapted, force.body_end_ms).clip == "Recovery"
    assert force.complete_ms == pytest.approx(force.body_end_ms + 800)


def test_condition_entry_rest_and_exit_share_exact_rig_data(data):
    fact = condition_fact("condition.prone", "Prone")
    recipe = data.condition_recipes[fact.behavior_id]
    exact = ContentBodyQualifier(contentRef=recipe.definitionRef)
    adapted = authored(data, binding("condition_entry", qualifier=exact),
        binding("condition_hold", qualifier=exact, rest=4),
        binding("condition_exit", qualifier=exact, reverse=True))
    actor = contact(adapted)
    application = compile_condition(adapted.condition_recipes, header(fact), fact, (),
        start_ms=100, badge_style=data.badge_style)
    application = bind_condition_body(application, recipe, adapted, actor)
    assert application.complete_ms == 400  # six frames / 20 fps, transition owner retains its full-frame duration
    assert required_body(sample_condition_body(application, 200, actor.life_state)).frame == 2
    appearance = resolve_condition_appearance((fact,), adapted.condition_recipes)
    rest = condition_body_pose(adapted, BodySample(actor.actor_uuid, "Idle", 0, "S"), actor, appearance)
    assert (rest.clip, rest.frame) == ("Alternate", 4)
    removed = replace(fact, event_uuid=uuid4())
    removal = compile_condition(adapted.condition_recipes, header(removed, applied=False), removed, (fact,),
        start_ms=500, badge_style=data.badge_style)
    removal = bind_condition_body(removal, recipe, adapted, actor)
    assert required_body(sample_condition_body(removal, 500, actor.life_state)).frame == 5
    assert required_body(sample_condition_body(removal, 700, actor.life_state)).frame == 1
    assert sample_condition_body(removal, 800, actor.life_state) is None


def test_equipment_commit_and_healing_body_reuse_existing_fact_owners(data):
    adapted = authored(data, binding("equipment", marker="commit", reverse=True), binding("healing"))
    actor = contact(adapted)
    timeline = compile_equipment(adapted, str(uuid4()), actor)
    assert timeline.commit_ms == 150 and timeline.complete_ms == 250
    assert sample_equipment(timeline, 149).committed is False
    assert sample_equipment(timeline, 150).committed is True
    assert sample_equipment(timeline, 0).body.frame == 5
    before, (root,) = player_history(healing_history())
    group = bind_choreography(before, root, adapted)
    baseline = bind_choreography(before, root, data)
    assert group.after == baseline.after
    assert baseline.complete_ms == 0 and group.complete_ms == 250
    assert sample_choreography(group, 0).vitals == sample_choreography(baseline, 0).vitals
    assert any(body.clip == "Alternate" and body.frame == 2 for body in sample_choreography(group, 100).bodies)


@pytest.mark.parametrize("seed", [1, 17, 5])
def test_attack_profiles_respect_exact_rig_item_source_and_outcome(data, seed):
    before, (root,) = player_history(attack_history("weapon.longsword", seed))
    fact = root.root.fact
    assert isinstance(fact, AttackFact) and fact.behavior_id is not None
    recipe = data.attack_recipes[fact.behavior_id]
    original = select_attack_profile(recipe, fact, data.root_rig)
    assert original is not None
    goblin_original = select_attack_profile(recipe, fact, "smallscale.goblin01")
    assert goblin_original is not None and goblin_original.id == "goblin01-physical"
    match = original.match.model_copy(update={"rigIds": (data.root_rig,),
        "sourceItemIds": (fact.source_item_id,), "sourceKinds": ("equipped",)})
    selected = original.model_copy(update={"id": "rig-specific", "precedence": 1000, "match": match,
        "actor": original.actor.model_copy(update={"clip": "Alternate"}),
        "anchors": (ActionFrameAnchor(name="contact", frame=2),),
        "attackVfx": original.attackVfx.model_copy(update={"onHit": {}, "onMiss": {}, "onCrit": {}})})
    recipe = recipe.model_copy(update={"variants": (selected, *recipe.variants)})
    adapted = authored(data)
    adapted = replace(adapted, attack_recipes={**adapted.attack_recipes, fact.behavior_id: recipe})
    assert select_attack_profile(recipe, fact, data.root_rig) == selected
    assert select_attack_profile(recipe, fact, "smallscale.goblin01") == goblin_original
    assert select_attack_profile(recipe, replace(fact, attack_source_kind="natural"), data.root_rig) != selected
    assert select_attack_profile(recipe, replace(fact, source_item_id="weapon.dagger"), data.root_rig) != selected
    bound = bind_attack(before, root, adapted)
    assert bound is not None and bound.timeline.profile_id == "rig-specific"
    assert bound.timeline.contact_ms == 100 and sample_attack(bound.timeline, 100).bodies[0].frame == 2
    original_bound = bind_attack(before, root, data)
    assert original_bound is not None and bound.after == original_bound.after


def test_selected_action_and_disabled_primary_recovery_preload_real_pixels_in_all_views(data, invisibility, graphics):
    before, root = invisibility
    for enabled in (True, False):
        adapted = authored(data, binding("body_action", marker="effect" if enabled else None,
            enabled=enabled, clip="Alternate" if enabled else "NotLoaded"),
            binding("body_action_recovery", clip="Recovery"))
        group = bind_choreography(before, root, adapted)
        cue, = group.body_actions
        rows: LoadedBodyRows = {}
        load_choreography_media(group, body_rows=rows)
        assert {key[3] for key in rows if key[1] == "Recovery"} == set(range(8))
        body = required_body(sample_body_action(cue, adapted, cue.join_ms + 100))
        actor = next(actor for actor in group.before.actors.values() if str(actor.uuid) == cue.contact.actor_uuid)
        layers = resolve_player_layers(adapted, actor, rig_id=cue.contact.rig_id)
        for quadrant in range(4):
            commands = actor_draw_commands(adapted, body, cue.contact, layers, rows, Camera(quadrant=quadrant))
            assert commands and any(pygame.mask.from_surface(command.surface).count() for command in commands)


def test_real_saved_avoidance_retains_motion_while_body_uses_explicit_frame_keys(data):
    before, roots = player_history(trap_expansion_history(program="jaw", save=True), role="traveler")
    adapted = authored(data, binding("save_avoidance", keys=((0., 5), (.5, 1), (1., 0))))
    found = []
    for root in roots:
        baseline, selected = bind_choreography(before, root, data), bind_choreography(before, root, adapted)
        original_hops = [cue for visit in walk_bound_timelines(baseline) if isinstance(visit.timeline, BoundChoreography)
                         for cue in visit.timeline.body_hops]
        selected_hops = [cue for visit in walk_bound_timelines(selected) if isinstance(visit.timeline, BoundChoreography)
                         for cue in visit.timeline.body_hops]
        for old, new in zip(original_hops, selected_hops):
            assert (new.contact, new.landing, new.start_ms, new.end_ms) == (old.contact, old.landing, old.start_ms, old.end_ms)
            middle = (new.start_ms + new.end_ms) / 2
            first, second = sample_body_hop(old, middle), sample_body_hop(new, middle)
            assert first is not None and second is not None and first[1] == second[1]
            assert (second[0].clip, second[0].frame) == ("Alternate", 1)
            assert selected.after == baseline.after
            found.append(new)
        before = reduce_lineage(before, root)
    assert found


def test_alternate_rig_keeps_required_shared_damage_and_death_coverage(data):
    adapted = authored(data, binding("movement", clip="Run", loop=True))
    for name in (data.damage_context.bodyClip, data.death_context.bodyClip):
        document = adapted.rigs[data.root_rig].model_dump(mode="json")
        del document["clips"][name]
        document["pose_sockets"] = {}
        rig = BodyRig.model_validate_json(json.dumps(document))
        with pytest.raises(ValueError, match="shared-vitals"):
            validate_rig_body_contexts(replace(adapted, rigs={**adapted.rigs, data.root_rig: rig}))


@pytest.mark.parametrize("failure", ["clip", "frame", "marker", "disabled"])
def test_rig_scoped_attack_profile_must_admit_a_real_body_and_contact(data, failure):
    adapted = authored(data)
    recipe = data.attack_recipes["action.attack"]
    original = recipe.variants[0]
    profile = original.model_copy(update={
        "match": original.match.model_copy(update={"rigIds": (data.root_rig,)}),
        "actor": original.actor.model_copy(update={"clip": "Missing" if failure == "clip" else "Alternate",
                                                   "enabled": failure != "disabled"}),
        "anchors": (ActionFrameAnchor(name="unknown" if failure == "marker" else "contact",
                                      frame=6 if failure == "frame" else 2),),
    })
    broken = replace(adapted, attack_recipes={"action.attack": recipe.model_copy(update={"variants": (profile,)})})
    with pytest.raises(ValueError, match="incompatible body or contact"):
        validate_rig_body_contexts(broken)


def test_attack_selector_rejects_unknown_rig_but_allows_installed_unloaded_rig(data):
    subset = replace(data, rigs={data.root_rig: data.rigs[data.root_rig]})
    installed = frozenset(data.rigs)
    validate_rig_body_contexts(subset, installed_rig_ids=installed)
    recipe = data.attack_recipes["action.attack"]
    profile = recipe.variants[0]
    typo = profile.model_copy(update={"match": profile.match.model_copy(update={"rigIds": ("smallscale.misspelled",)})})
    altered = replace(subset, attack_recipes={"action.attack": recipe.model_copy(update={"variants": (typo,)})})
    with pytest.raises(ValueError, match="unknown attack profile rig: smallscale.misspelled"):
        validate_rig_body_contexts(altered, installed_rig_ids=installed)
