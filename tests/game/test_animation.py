"""Imported recipes + detached facts + elapsed time produce visible samples.

The checked-in oracle runs NeuroClient's real clip queue with a 1 ms pump.
These tests exercise the public Python loading, compilation and sampling
boundaries; they require neither that checkout nor a TypeScript runtime.
"""

from dataclasses import replace
import json
from pathlib import Path
import shutil
from types import MappingProxyType

import pytest

from dnd.core.life_types import LifeState
from game.animation import ActorContact, CastApplication, CastInput, ProjectileSample, compile_cast, crossed_anchors, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import AnimationData, DamageContext, StudioSpellDraft


ORACLE = json.loads((Path(__file__).parent / "fixtures/neuroclient_animation_timing.json").read_text())
CASES = {case["id"]: case for case in ORACLE["cases"]}
QUEUE_CASES = (
    "queue-saved-speed1", "queue-cast-speed2", "queue-damage-speed2",
    "queue-lethal", "queue-near", "queue-recovery-enabled",
)


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(authored_bundles=())


def authored_data(data: AnimationData, draft_json: dict) -> AnimationData:
    draft = StudioSpellDraft.model_validate_json(json.dumps(draft_json))
    return replace(data, drafts=MappingProxyType({**data.drafts, draft.definitionRef.content_id: draft}))


def reference_cast(data: AnimationData, case_id: str):
    parameters = CASES[case_id]["input"]
    draft_json = data.drafts[parameters["draftContentId"]].model_dump(mode="json", exclude_unset=True)
    draft_json["cast"]["bodyPlaybackSpeed"] = parameters["castSpeed"]
    draft_json["cast"]["recovery"]["enabled"] = parameters["recoveryEnabled"]
    draft_json["damage"]["floatingNumber"]["enabled"] = parameters["numberEnabled"]
    selected = authored_data(data, draft_json)
    damage_context = data.damage_context.model_dump(mode="json", exclude_unset=True)
    damage_context["bodyPlaybackSpeed"] = parameters["damageSpeed"]
    selected = replace(selected, damage_context=DamageContext.model_validate_json(json.dumps(damage_context)))
    source = CastInput(
        root_event_uuid=case_id,
        caster=ActorContact('caster', tuple(parameters['sourceGrid']), 'S', parameters['visualScale']),
        applications=(
            CastApplication(
                application_id='application-1',
                target=ActorContact(
                    'target',
                    tuple(parameters['targetGrid']),
                    'W',
                    parameters['visualScale'],
                    parameters['initialHp'],
                    LifeState.DEAD if parameters['terminal'] else LifeState.ALIVE,
                ),
                damage_applied=True,
                damage_total=parameters['damageAmount'],
                resulting_hp=parameters['resultingHp'],
                resulting_life_state=LifeState.DEAD if parameters['lethal'] else None,
            ),
        ),
    )
    return compile_cast(selected, parameters["draftContentId"], source)


def test_loader_preserves_materialized_and_disabled_authoring_fields(data: AnimationData) -> None:
    document = json.loads((DATA_ROOT / "spell-studio-drafts.materialized.json").read_text())
    for source in document["spells"]:
        assert data.drafts[source["definitionRef"]["content_id"]].model_dump(mode="json", exclude_unset=True) == source
    assets = json.loads((DATA_ROOT / "source/public/studio/spell-projectile-assets.json").read_text())
    for source in assets:
        assert data.projectile_assets[source["assetId"]].model_dump(mode="json", exclude_unset=True) == source
    fire = data.drafts["spell.fire_bolt"]
    assert fire.cast.recovery.enabled is False
    assert fire.cast.recovery.bodyClip == "Taunt"
    assert [(layer.category, layer.enabled, layer.hidden) for layer in fire.cast.effects] == [("Effect1", False, True)]
    assert fire.projectile.sprite.mediaFailurePolicy == "fail_transaction"
    assert fire.condition.feedbackEnabled is True
    assert data.rig.FACING_ROW["E"] == 0
    assert data.rig.FACING_CYCLE[0] == "N"
    assert data.damage_context.bodyClip == "TakeDamage"
    assert data.death_context.bodyClip == "Die"
    assert data.number_style.anchorLiftPx == 50
    assert "equipment_transition" in json.loads(data.context_source_json)["contexts"]
    assert all(path.is_absolute() and path.is_file() for path in data.resources.values())
    with pytest.raises(TypeError):
        data.resources["/unexpected.png"] = Path("unexpected.png")


@pytest.fixture
def imported_tree(tmp_path: Path) -> Path:
    destination = tmp_path / "game/data/neuroclient"
    shutil.copytree(DATA_ROOT, destination)
    assets = tmp_path / "game/assets"
    assets.mkdir()
    (assets / "neuroclient").symlink_to(DATA_ROOT.parent.parent / "assets/neuroclient", target_is_directory=True)
    return destination


@pytest.mark.parametrize("case, error", [
    ("duplicate-ref", "duplicate spell draft"),
    ("duplicate-asset", "duplicate projectile assetId"),
    ("binding-mismatch", "no exact authored definitionRef"),
    ("missing-file", "missing local animation resource"),
    ("escaping-file", "invalid local animation resource path"),
])
def test_loader_rejects_ambiguous_or_unusable_imports(imported_tree: Path, case: str, error: str) -> None:
    path = imported_tree / "bindings.json"
    if case == "duplicate-ref":
        path = imported_tree / "spell-studio-drafts.materialized.json"
    elif case == "duplicate-asset":
        path = imported_tree / "source/public/studio/spell-projectile-assets.json"
    document = json.loads(path.read_text())
    if case == "duplicate-ref":
        document["spells"].append(document["spells"][0])
    elif case == "duplicate-asset":
        document.append(document[0])
    elif case == "binding-mismatch":
        document["spells"]["spell.fire_bolt"]["definition_contract_hash"] = "0" * 64
    else:
        url = next(iter(document["resources"]))
        document["resources"][url] = ("../outside.png" if case == "escaping-file"
                                       else "game/assets/neuroclient/missing.png")
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match=error):
        load_animation_data(imported_tree)


@pytest.mark.parametrize("path,value", [
    (("cast", "releaseFrame"), 0.5),
    (("cast", "releaseFrame"), 15),
    (("cast", "bodyPlaybackSpeed"), 99),
    (("projectile", "prepare", "assetPhase"), "impact"),
    (("projectile", "prepare", "durationMs"), 0),
    (("projectile", "sourceAnchorsByFacing"), {"BAD": {"basis": "tileCenter", "liftY": 0, "forwardPx": 0, "sidePx": 0, "axisPx": 0}}),
])
def test_invalid_source_timing_and_phase_fields_are_rejected(data: AnimationData, path: tuple[str, ...], value) -> None:
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    owner = document
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = value
    with pytest.raises(ValueError):
        StudioSpellDraft.model_validate_json(json.dumps(document))


def test_valid_source_area_remains_preserved_before_unsupported_execution(data: AnimationData) -> None:
    profile = json.loads((DATA_ROOT / "source/src/render/data/animation/generatedSpellPresentationProfile.json").read_text())
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["area"] = profile["area"]
    del document["projectile"]
    selected = authored_data(data, document)
    assert selected.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True) == document
    source = reference_cast(data, "queue-saved-speed1").source
    with pytest.raises(ValueError, match="projectile delivery without an area"):
        compile_cast(selected, "spell.fire_bolt", source)


@pytest.mark.parametrize("case_id", (*QUEUE_CASES, "number-disabled"))
def test_authored_boundaries_match_original_runtime_pump(data: AnimationData, case_id: str) -> None:
    timeline = reference_cast(data, case_id)
    recorded = CASES[case_id]["timing"]
    phases = {phase.name: phase for phase in timeline.applications[0].projectile_intervals}
    # Each serial frame wakeup can round upward by less than the oracle's 1 ms
    # pump step. Bounds count dependencies: body(1), preparation join(2), travel
    # completion(3), damage delay(4), reaction frame/end(5), recovery body(6),
    # outer queue join(6 without recovery,7 with recovery).
    comparisons = (
        ("prepareStartMs", phases["prepare"].start_ms, recorded["prepareStartMs"], 1),
        ("releaseAnchorMs", timeline.release_ms, recorded["releaseAnchorMs"], 1),
        ("bodyEndMs", timeline.body_end_ms, recorded["bodyEndMs"], 1),
        ("travelStartMs", phases["travel"].start_ms, recorded["travelStartMs"], 2),
        ("impactMs", phases["travel"].end_ms, recorded["impactMs"], 3),
        ("impactEndMs", phases["impact"].end_ms, recorded["impactEndMs"], 4),
        ("damageStartMs", timeline.applications[0].damage_start_ms, recorded["damageStartMs"][0], 4),
        ("vitals", timeline.applications[0].hp_ms, recorded["vitals"][0]["timeMs"], 5),
        ("settledMs", timeline.complete_ms, recorded["settledMs"], 7 if timeline.recipe.cast.recovery.enabled else 6),
    )
    if recorded["recoveryStartMs"] is not None:
        comparisons += (("recoveryStartMs", timeline.recovery_start_ms, recorded["recoveryStartMs"], 6),)
    step_ms = CASES[case_id]["pump"]["stepMs"]
    for name, ideal, observed, wakeups in comparisons:
        assert -1e-7 <= observed - ideal <= wakeups * step_ms + 1e-7, (case_id, name, ideal, observed)
    assert sample_cast(timeline, timeline.complete_ms - 0.001).complete is False
    assert sample_cast(timeline, timeline.complete_ms).complete is True


@pytest.mark.parametrize("case_id", QUEUE_CASES)
def test_selected_visible_frames_match_original_queue(data: AnimationData, case_id: str) -> None:
    timeline = reference_cast(data, case_id)
    phases = {phase.name: phase for phase in timeline.applications[0].projectile_intervals}
    recorded_timing = CASES[case_id]["timing"]
    recorded_starts = {
        "prepare": recorded_timing["prepareStartMs"],
        "travel": recorded_timing["travelStartMs"],
        "impact": recorded_timing["impactMs"],
    }
    for reference in CASES[case_id]["selectedFrames"]:
        sample = sample_cast(timeline, reference["timeMs"])
        caster, target = sample.bodies
        assert caster.clip == reference["caster"]["clip"], (case_id, reference["timeMs"], "caster clip")
        assert caster.frame == reference["caster"]["frame"], (case_id, reference["timeMs"], "caster frame")
        assert caster.hide_weapon is (reference["caster"]["weapon"] is None)
        assert next((layer.category for layer in caster.cast_layers if layer.slot == "weaponGlow"), None) == reference["caster"]["glow"]
        assert target.clip == reference["target"]["clip"], (case_id, reference["timeMs"], "target clip")
        assert target.frame == reference["target"]["frame"], (case_id, reference["timeMs"], "target frame")
        assert sample.vitals[0].hp == reference["hp"]
        assert bool(sample.numbers) is reference["numberVisible"]
        assert len(sample.projectiles) == len(reference["projectiles"])
        for projectile, original in zip(sample.projectiles, reference["projectiles"]):
            assert ("cast" if projectile.phase == "prepare" else projectile.phase) == original["phase"]
            # Global start quantization is checked separately. Compare frames
            # at equal phase-local elapsed time: a sub-ms launch difference can
            # straddle a frame edge, so a blanket +/-1 frame tolerance is weaker.
            phase = phases[projectile.phase]
            phase_elapsed = reference["timeMs"] - recorded_starts[projectile.phase]
            aligned = sample_cast(timeline, phase.start_ms + phase_elapsed).projectiles[0]
            assert isinstance(aligned, ProjectileSample)
            assert aligned.column - phase.phase.start == original["frame"]
            assert data.rig.AUTHORED_PROJECTILE_ROW_ORDER[aligned.row] == original["facing"]
            assert aligned.point == pytest.approx(original["root"], abs=1e-6)
            assert aligned.rotation_radians == pytest.approx(original["rotation"], abs=1e-10)


def test_pause_seek_and_large_delta_share_one_time_domain(data: AnimationData) -> None:
    timeline = reference_cast(data, "queue-saved-speed1")
    elapsed = 1500.0
    paused = sample_cast(timeline, elapsed)
    assert sample_cast(timeline, elapsed) == paused
    assert crossed_anchors(timeline, elapsed, elapsed) == ()
    direct = crossed_anchors(timeline, -1, elapsed)
    incremental = []
    previous = -1.0
    for current in (*range(0, 1500, 17), elapsed):
        incremental.extend(crossed_anchors(timeline, previous, current))
        sample_cast(timeline, current)
        previous = current
    assert tuple(incremental) == direct
    assert [anchor.name for anchor in direct] == ["action_start", "prepare", "release", "travel", "impact", "effect"]
    assert all(anchor.application_id == "application-1" for anchor in direct if anchor.name in {"travel", "impact", "effect"})
    assert sample_cast(timeline, elapsed) == paused
    assert paused.projectiles[0].phase == "impact"
    assert paused.bodies[1].clip == "TakeDamage"
    # Deliberate correction: NC's hitch case starts preparation at callback
    # delivery (1500), delaying travel until 2000. We continue from authored
    # boundaries and account for the elapsed remainder without shifting roots.
    hitch = CASES["queue-large-initial-delta"]
    assert hitch["timing"]["travelStartMs"] > elapsed
    assert timeline.complete_ms < hitch["timing"]["settledMs"]
    assert crossed_anchors(timeline, -1, 10000) == timeline.anchors
    final = sample_cast(timeline, 10000)
    assert final.complete and final.vitals[0].hp == 13
    assert final.projectiles == final.numbers == ()


def test_hidden_number_still_commits_hp_at_its_authored_frame(data: AnimationData) -> None:
    timeline = reference_cast(data, "number-disabled")
    before = sample_cast(timeline, timeline.applications[0].hp_ms - 0.001)
    at = sample_cast(timeline, timeline.applications[0].hp_ms)
    assert before.vitals[0].hp == 20 and at.vitals[0].hp == 13
    assert before.numbers == at.numbers == ()
    assert sample_cast(timeline, timeline.applications[0].flash_ms).vitals[0].flash == timeline.recipe.damage.hitFlash.color


def test_disclosed_damage_does_not_invent_hidden_numbers_or_health(data: AnimationData) -> None:
    original = reference_cast(data, "queue-saved-speed1")
    source = replace(
        original.source,
        applications=(
            replace(
                original.source.applications[0],
                target=replace(original.source.applications[0].target, hp=None),
                resulting_hp=None,
                damage_total=None,
            ),
        ),
    )
    timeline = compile_cast(data, "spell.fire_bolt", source)
    sample = sample_cast(timeline, timeline.applications[0].damage_start_ms + 100)
    assert sample.vitals[0].hp is None and sample.numbers == ()
    assert sample.bodies[1].clip == "TakeDamage"
    assert sample_cast(timeline, 10000).vitals[0].hp is None


def test_contact_without_a_damage_consequence_has_no_reaction_or_vitals_update(data: AnimationData) -> None:
    original = reference_cast(data, "queue-saved-speed1")
    source = replace(original.source, applications=(replace(original.source.applications[0], damage_applied=False, damage_total=None, resulting_hp=None),))
    timeline = compile_cast(data, "spell.fire_bolt", source)
    impact = next((phase for phase in timeline.applications[0].projectile_intervals if phase.name == 'impact'))
    sample = sample_cast(timeline, impact.start_ms + 100)
    assert sample.projectiles[0].phase == "impact"
    assert sample.bodies[1].clip == "Idle"
    assert sample.vitals[0].hp == 20
    assert sample.vitals[0].flash is None and sample.numbers == ()
    assert not {"effect", "vitals"}.intersection(anchor.name for anchor in timeline.anchors)
    with pytest.raises(ValueError, match="damage values require a disclosed damage application"):
        compile_cast(data, 'spell.fire_bolt', replace(source, applications=(replace(source.applications[0], damage_total=7),)))


def test_terminal_target_keeps_terminal_pose_during_new_feedback(data: AnimationData) -> None:
    timeline = reference_cast(data, "terminal")
    initial = sample_cast(timeline, 0)
    hit = sample_cast(timeline, timeline.applications[0].damage_start_ms)
    assert initial.bodies[1].clip == hit.bodies[1].clip == "Die"
    assert initial.bodies[1].frame == hit.bodies[1].frame == data.rig.SHEET_COLS - 1
    assert initial.vitals[0].life_state == hit.vitals[0].life_state == "dead"
    assert hit.vitals[0].hp == 0 and hit.numbers[0].value == 7


def test_authored_flash_and_number_fade_use_the_same_elapsed_time(data: AnimationData) -> None:
    timeline = reference_cast(data, "queue-lethal")
    damage = timeline.recipe.damage
    start = sample_cast(timeline, timeline.applications[0].flash_ms)
    assert start.vitals[0].flash == damage.hitFlash.color
    assert sample_cast(timeline, timeline.applications[0].flash_ms + damage.hitFlash.durationMs).vitals[0].flash is None
    number = sample_cast(timeline, timeline.applications[0].number_ms + damage.floatingNumber.durationMs * 0.75).numbers[0]
    assert (number.value, number.label, number.color) == (7, "Fire", damage.floatingNumber.color)
    assert number.progress == pytest.approx(0.75)
    assert number.alpha == pytest.approx(0.5)
    assert sample_cast(timeline, timeline.applications[0].number_ms + damage.floatingNumber.durationMs).numbers == ()


@pytest.mark.parametrize("resulting_hp, resulting_life, expected_clip, expected_life", [
    (0, None, "TakeDamage", LifeState.ALIVE),
    (None, LifeState.DEAD, "Die", LifeState.DEAD),
])
def test_life_transition_uses_the_disclosed_fact_not_hp_arithmetic(
    data: AnimationData, resulting_hp, resulting_life, expected_clip, expected_life,
) -> None:
    original = reference_cast(data, "queue-saved-speed1")
    source = replace(
        original.source,
        applications=(replace(original.source.applications[0], resulting_hp=resulting_hp, resulting_life_state=resulting_life),),
    )
    timeline = compile_cast(data, "spell.fire_bolt", source)
    sample = sample_cast(timeline, timeline.applications[0].damage_start_ms)
    assert sample.bodies[1].clip == expected_clip
    assert sample.vitals[0].life_state == expected_life


@pytest.mark.parametrize("initial_dying", [False, True])
@pytest.mark.parametrize("life", [LifeState.DYING, LifeState.STABLE])
def test_dying_requires_its_own_life_presentation(data: AnimationData, initial_dying: bool, life: LifeState) -> None:
    original = reference_cast(data, "queue-saved-speed1")
    source = (replace(
        original.source,
        applications=(
            replace(
                original.source.applications[0],
                target=replace(original.source.applications[0].target, life_state=life),
            ),
        ),
    )
              if initial_dying else replace(original.source, applications=(replace(original.source.applications[0], resulting_life_state=life),)))
    with pytest.raises(ValueError, match="dying"):
        compile_cast(data, "spell.fire_bolt", source)


@pytest.mark.parametrize("amount", [0, -1])
def test_damage_application_requires_a_positive_disclosed_amount(data: AnimationData, amount: int) -> None:
    source = reference_cast(data, "queue-saved-speed1").source
    with pytest.raises(ValueError, match="positive disclosed total"):
        compile_cast(data, 'spell.fire_bolt', replace(source, applications=(replace(source.applications[0], damage_total=amount),)))


def test_facing_override_does_not_replace_the_global_projectile_axis_inset(data: AnimationData) -> None:
    source = reference_cast(data, "queue-saved-speed1").source
    source = replace(source, applications=(replace(source.applications[0], target=replace(source.applications[0].target, grid=(3, 3))),))
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["projectile"]["sourceAnchorsByFacing"]["S"]["axisPx"] = 100
    timeline = compile_cast(authored_data(data, document), "spell.fire_bolt", source)
    # Original runtimeResolver.ts binds sourceForwardPx from sourceAnchor.axisPx
    # globally. The facing-specific axis remains authoring data, not that input.
    sample = sample_cast(timeline, 100)
    assert sample.bodies[0].facing == "S"
    assert sample.projectiles[0].phase == "prepare"
    assert sample.projectiles[0].point == pytest.approx((0, 44.5))
    assert timeline.applications[0].to_point == pytest.approx((0, 100.5))


def test_subpixel_delivery_requires_the_separate_zero_travel_proof(data: AnimationData) -> None:
    source = reference_cast(data, "queue-saved-speed1").source
    source = replace(source, applications=(replace(source.applications[0], target=replace(source.applications[0].target, grid=(0.01, 0.01))),))
    with pytest.raises(ValueError, match="zero-travel"):
        compile_cast(data, "spell.fire_bolt", source)


@pytest.mark.parametrize("case_id", QUEUE_CASES)
def test_queue_cleanup_removes_decoration_without_delaying_settlement(data: AnimationData, case_id: str) -> None:
    timeline = reference_cast(data, case_id)
    recorded = CASES[case_id]["timing"]
    if recorded["numberRemovedMs"][0] == recorded["settledMs"]:
        assert sample_cast(timeline, timeline.complete_ms - 0.001).numbers
    final = sample_cast(timeline, timeline.complete_ms)
    assert final.complete and final.projectiles == final.numbers == ()
    assert final.vitals[0].flash is None


def test_authored_recovery_joins_delivery_while_number_finishes_its_own_lifetime(data: AnimationData) -> None:
    timeline = reference_cast(data, "queue-recovery-enabled")
    recorded = CASES["queue-recovery-enabled"]
    recovery = next(row for row in recorded["bodyTransitions"] if row["clip"] == "Taunt")
    assert recovery["timeMs"] == recorded["timing"]["recoveryStartMs"]
    assert timeline.recovery_start_ms >= max(timeline.body_end_ms, timeline.applications[0].damage_end_ms)
    before = sample_cast(timeline, timeline.recovery_start_ms - 0.001)
    start = sample_cast(timeline, timeline.recovery_start_ms)
    assert before.bodies[0].clip == "Idle" and before.bodies[1].clip == "TakeDamage"
    assert (start.bodies[0].clip, start.bodies[0].frame, start.bodies[1].clip) == ("Taunt", 0, "Idle")
    assert start.bodies[0].hide_weapon is False and start.bodies[0].cast_layers == ()
    assert start.numbers and start.vitals[0].hp == 13 and not start.complete
    number_lifetime = recorded["timing"]["numberRemovedMs"][0] - recorded["timing"]["numberVisibleMs"][0]
    removal = timeline.applications[0].number_ms + number_lifetime
    assert sample_cast(timeline, removal - 0.001).numbers
    after = sample_cast(timeline, removal)
    assert after.numbers == () and after.bodies[0].clip == "Taunt" and not after.complete
    final = sample_cast(timeline, timeline.complete_ms)
    assert final.bodies[0].clip == "Idle" and final.complete
    assert data.drafts["spell.fire_bolt"].cast.recovery.enabled is False


@pytest.mark.parametrize("case, error", [
    ("unknown-spell", "unknown authored spell binding"),
    ("unknown-asset", "unknown projectile assetId"),
    ("missing-media", "missing local projectile media"),
    ("missing-glow", "missing enabled cast layer resource"),
    ("geometry", "geometry projectile"),
    ("tangent", "tangent-facing projectile rows"),
    ("locked_initial_tangent", "tangent-facing projectile rows"),
    ("missing-recovery", "missing body clip resource: neuroclient.modular/Taunt"),
])
def test_unimplemented_or_missing_resources_fail_before_sampling(data: AnimationData, case: str, error: str) -> None:
    original = reference_cast(data, "queue-saved-speed1")
    selected = data
    spell_id = "spell.missing" if case == "unknown-spell" else "spell.fire_bolt"
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    if case == "unknown-asset":
        document["projectile"]["prepare"]["assetId"] = "missing-projectile"
    elif case == "missing-media":
        sheet = data.projectile_assets[document["projectile"]["sprite"]["assetId"]].sheet
        selected = replace(data, resources=MappingProxyType({url: path for url, path in data.resources.items() if url != sheet}))
    elif case == "missing-glow":
        selected = replace(data, resources=MappingProxyType({url: path for url, path in data.resources.items()
                                                            if url != "/spritesheets/Magic2/Attack5.png"}))
    elif case == "geometry":
        document["projectile"]["geometry"]["enabled"] = True
    elif case in {"tangent", "locked_initial_tangent"}:
        document["projectile"]["orientation"]["directionSource"] = case
    elif case == "missing-recovery":
        document["cast"]["recovery"]["enabled"] = True
        selected = replace(data, resources=MappingProxyType({url: path for url, path in data.resources.items()
                                                            if url != "/spritesheets/NakedBody/Taunt.png"}))
    selected = authored_data(selected, document)
    with pytest.raises(ValueError, match=error):
        compile_cast(selected, spell_id, original.source)
