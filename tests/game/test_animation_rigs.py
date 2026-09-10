"""Actor-specific clip metadata drives the existing pure cast boundary.

The Goblin binding uses real selected media. Alternate FPS/count fixtures are
validated hypothetical timing inputs only: they do not claim the unchanged
PNG files have another geometry. The drawer separately checks that boundary.
"""

from dataclasses import replace
import json
from types import MappingProxyType

import pytest

from dnd.core.life_types import LifeState
from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import AnimationData, BodyRig, StudioSpellDraft


ROOT = "neuroclient.modular"
GOBLIN = "smallscale.goblin01"


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(DATA_ROOT.parent / "rigs/goblin01.json",))


def cast_input(*, target_rig: str = GOBLIN, lethal: bool = False) -> CastInput:
    return CastInput(
        root_event_uuid='rig-reference',
        caster=ActorContact('caster', (0, 0), 'S', 0.5),
        applications=(
            CastApplication(
                application_id='application-1',
                target=ActorContact('target', (3, -3), 'W', 0.5, hp=20, rig_id=target_rig),
                damage_applied=True,
                damage_total=7,
                resulting_hp=0 if lethal else 13,
                resulting_life_state=LifeState.DEAD if lethal else None,
            ),
        ),
    )


def with_clip(data: AnimationData, rig_id: str, clip: str, *,
              fps: float, frames: int) -> AnimationData:
    document = data.rigs[rig_id].model_dump(mode="json")
    document["clips"][clip].update(fps=fps, frames=frames)
    rig = BodyRig.model_validate_json(json.dumps(document))
    return replace(data, rigs=MappingProxyType({**data.rigs, rig_id: rig}))


@pytest.mark.parametrize("lethal", [False, True])
def test_selected_fixed_target_preserves_shared_cast_and_feedback(data: AnimationData, lethal: bool) -> None:
    goblin = compile_cast(data, "spell.fire_bolt", cast_input(lethal=lethal))
    root = compile_cast(data, "spell.fire_bolt", cast_input(target_rig=ROOT, lethal=lethal))
    assert goblin.anchors == root.anchors
    assert goblin.applications[0].damage_start_ms is not None and goblin.applications[0].hp_ms is not None
    for elapsed in (0, goblin.release_ms, goblin.applications[0].damage_start_ms, goblin.applications[0].hp_ms,
                    goblin.complete_ms, goblin.complete_ms + 1000):
        assert sample_cast(goblin, elapsed) == sample_cast(root, elapsed)
    assert sample_cast(goblin, goblin.applications[0].hp_ms).vitals[0].hp == (0 if lethal else 13)
    final = sample_cast(goblin, goblin.complete_ms)
    assert final.complete
    assert final.bodies[1].clip == ("Die" if lethal else "Idle")
    assert final.vitals[0].life_state == (LifeState.DEAD if lethal else LifeState.ALIVE)


def test_target_metadata_controls_reaction_feedback_and_idle_without_retiming_release(data: AnimationData) -> None:
    original = compile_cast(data, "spell.fire_bolt", cast_input())
    selected = with_clip(data, GOBLIN, "TakeDamage", fps=6.0, frames=10)
    selected = with_clip(selected, GOBLIN, "Idle", fps=5.0, frames=4)
    timeline = compile_cast(selected, "spell.fire_bolt", cast_input())
    assert timeline.release_ms == original.release_ms
    assert timeline.body_end_ms == original.body_end_ms
    start = timeline.applications[0].damage_start_ms
    assert start is not None and start == original.applications[0].damage_start_ms
    assert timeline.applications[0].damage_end_ms == pytest.approx(start + 1500)
    assert timeline.applications[0].flash_ms == pytest.approx(start + 5000 / 6)
    assert timeline.applications[0].hp_ms == pytest.approx(start + 7000 / 6)
    before = sample_cast(timeline, start + 7000 / 6 - 0.001)
    feedback = sample_cast(timeline, start + 7000 / 6)
    assert before.vitals[0].hp == 20 and before.numbers == ()
    assert feedback.vitals[0].hp == 13 and feedback.numbers[0].value == 7
    assert feedback.bodies[1].frame == 7
    assert sample_cast(timeline, start + 500).bodies[1].frame == 3
    ending = sample_cast(timeline, start + 1500 - 0.001)
    assert ending.bodies[1].clip == "TakeDamage" and ending.bodies[1].frame == 8
    settled = sample_cast(timeline, start + 1500)
    assert settled.complete and settled.bodies[1].clip == "Idle" and settled.bodies[1].frame == 0
    assert sample_cast(timeline, start + 1500 + 1000).bodies[1].frame == 1


def test_caster_clip_metadata_controls_release_prepare_and_recovery(data: AnimationData) -> None:
    selected = with_clip(data, ROOT, "Attack5", fps=6.0, frames=15)
    selected = with_clip(selected, ROOT, "Taunt", fps=8.0, frames=9)
    document = selected.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["cast"]["recovery"]["enabled"] = True
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    selected = replace(selected, drafts=MappingProxyType({**selected.drafts, "spell.fire_bolt": draft}))
    timeline = compile_cast(selected, "spell.fire_bolt", cast_input())
    assert timeline.release_ms == pytest.approx(7000 / 6)
    assert timeline.body_end_ms == pytest.approx(14000 / 6)
    prepare = next((phase for phase in timeline.applications[0].projectile_intervals if phase.name == 'prepare'))
    assert prepare.start_ms == pytest.approx(1000 / 6)
    assert prepare.end_ms == pytest.approx(timeline.release_ms)
    assert sample_cast(timeline, 250).bodies[0].frame == 1
    assert sample_cast(timeline, 250).bodies[1].frame == 3
    assert timeline.applications[0].damage_start_ms is not None and timeline.applications[0].damage_end_ms is not None
    assert timeline.applications[0].damage_end_ms - timeline.applications[0].damage_start_ms == pytest.approx(14000 / 12)
    assert timeline.complete_ms - timeline.recovery_start_ms == pytest.approx(1000)
    recovering = sample_cast(timeline, timeline.recovery_start_ms + 500)
    assert recovering.bodies[0].clip == "Taunt" and recovering.bodies[0].frame == 4
    assert sample_cast(timeline, timeline.complete_ms).bodies[0].clip == "Idle"


@pytest.mark.parametrize("already_dead", [False, True])
def test_target_death_uses_its_own_duration_and_terminal_frame(data: AnimationData, already_dead: bool) -> None:
    selected = with_clip(data, GOBLIN, "Die", fps=4.0, frames=9)
    source = cast_input(lethal=True)
    if already_dead:
        source = replace(
            source,
            applications=(
                replace(
                    source.applications[0],
                    target=replace(source.applications[0].target, life_state=LifeState.DEAD, hp=0),
                    resulting_life_state=None,
                ),
            ),
        )
    timeline = compile_cast(selected, "spell.fire_bolt", source)
    start = timeline.applications[0].damage_start_ms
    assert start is not None and timeline.applications[0].damage_end_ms is not None
    if already_dead:
        assert timeline.applications[0].damage_end_ms == start
        assert sample_cast(timeline, 0).bodies[1].frame == 8
    else:
        assert timeline.applications[0].damage_end_ms == pytest.approx(start + 2000)
        assert sample_cast(timeline, start + 750).bodies[1].frame == 3
    for elapsed in (timeline.complete_ms, timeline.complete_ms + 10000):
        final = sample_cast(timeline, elapsed)
        assert final.complete and final.vitals[0].life_state == LifeState.DEAD
        assert final.bodies[1].clip == "Die" and final.bodies[1].frame == 8


@pytest.mark.parametrize("clip,lethal", [("Idle", False), ("TakeDamage", False), ("Die", True)])
def test_missing_target_clip_rejects_before_playback(data: AnimationData, clip: str, lethal: bool) -> None:
    document = data.rigs[GOBLIN].model_dump(mode="json")
    del document["clips"][clip]
    rig = BodyRig.model_validate_json(json.dumps(document))
    selected = replace(data, rigs=MappingProxyType({**data.rigs, GOBLIN: rig}))
    with pytest.raises(ValueError, match=f"missing body clip mapping: {GOBLIN}/{clip}"):
        compile_cast(selected, "spell.fire_bolt", cast_input(lethal=lethal))


@pytest.mark.parametrize("field,anchor", [("floatingNumber", "vitals"), ("hitFlash", "hit flash")])
def test_unreachable_required_target_feedback_rejects(data: AnimationData, field: str, anchor: str) -> None:
    selected = with_clip(data, GOBLIN, "TakeDamage", fps=12.0, frames=12)
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["damage"][field]["frame"] = 12
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    selected = replace(selected, drafts=MappingProxyType({**selected.drafts, "spell.fire_bolt": draft}))
    with pytest.raises(ValueError, match=f"unreachable {anchor} frame"):
        compile_cast(selected, "spell.fire_bolt", cast_input())


def test_unreachable_caster_release_rejects(data: AnimationData) -> None:
    selected = with_clip(data, ROOT, "Attack5", fps=12.0, frames=7)
    with pytest.raises(ValueError, match="unreachable release frame 7"):
        compile_cast(selected, "spell.fire_bolt", cast_input())


def test_fixed_rig_cannot_cast_without_an_authored_clip_mapping(data: AnimationData) -> None:
    source = cast_input()
    source = replace(source, caster=replace(source.caster, rig_id=GOBLIN))
    with pytest.raises(ValueError, match=f"missing body clip mapping: {GOBLIN}/Attack5"):
        compile_cast(data, "spell.fire_bolt", source)
