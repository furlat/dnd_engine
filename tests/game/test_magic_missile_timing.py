"""A/B/A playback agrees with the unchanged NeuroClient queue's observed trace.

The offline source oracle supplies expected times and frames. Python tests need
only the retained JSON, original imported recipes and public compiler/sampler.
"""

import json
from pathlib import Path

import pytest

from game.animation import ActorContact, CastApplication, CastInput, CastTimeline, compile_cast, sample_cast
from game.animation_data import load_animation_data


ORACLE = json.loads((Path(__file__).parent / "fixtures/neuroclient_magic_missile_timing.json").read_text())
CASE = ORACLE["cases"][0]


@pytest.fixture(scope="module")
def timeline() -> CastTimeline:
    parameters = CASE["input"]
    targets = {
        row["uuid"]: ActorContact(row["uuid"], tuple(row["grid"]), "W", parameters["visualScale"], row["initialHp"])
        for row in parameters["targets"]
    }
    return compile_cast(load_animation_data(authored_bundles=()), parameters["draftContentId"], CastInput(
        CASE["id"], ActorContact("caster", tuple(parameters["sourceGrid"]), "E", parameters["visualScale"]),
        tuple(CastApplication(
            row["applicationId"], targets[row["targetUuid"]], True, row["damage"], row["resultingHp"],
            damage_type="Force",
        ) for row in parameters["applications"]),
    ))


def test_application_boundaries_and_repeated_body_join_match_source(timeline: CastTimeline) -> None:
    events = CASE["events"]
    launches = [event for event in events if event["kind"] == "projectile-launch"]
    arrivals = [event for event in events if event["kind"] == "projectile-arrival"]
    starts = [event for event in events if event["kind"] == "intent-started" and event["type"] == "takeDamage"]
    vitals = [event for event in events if event["kind"] == "vitals"]
    numbers = [event for event in events if event["kind"] == "number-visible"]
    number_ends = [event for event in events if event["kind"] == "number-removed"]
    states = [event for event in events if event["kind"] == "body-state"]
    settled = [event for event in events if event["kind"] == "queue-settled"]
    assert [event["applicationIndex"] for event in launches] == [0, 1, 2]
    assert [event["applicationIndex"] for event in arrivals] == [0, 1, 2]
    assert [(event["applicationIndex"], event["targetUuid"]) for event in starts] == [(0, "A"), (1, "B"), (2, "A")]
    assert [(event["uuid"], event["hp"]) for event in vitals] == [("A", 75), ("B", 75), ("A", 73)]
    assert [event["value"] for event in numbers] == ["5 Force", "5 Force", "2 Force"]
    assert len(settled) == 1
    assert len([event for event in states if event["to"] == "Casting"]) == 1
    assert timeline.recipe.damage is None  # The actual source uses its global Force damage context.

    comparisons = []
    for application, launch, arrival, start, vital, number, number_end in zip(
        timeline.applications, launches, arrivals, starts, vitals, numbers, number_ends, strict=True,
    ):
        assert application.damage is not None
        assert application.number_ms is not None
        assert start["timeMs"] == arrival["timeMs"]
        # Serial pump wakeups: release, stagger wait, travel completion, then
        # frame-zero callback on the next actor update. No frame tolerance hides
        # these dependencies; the absolute Python sampler applies frame zero at
        # the authored arrival itself.
        comparisons.extend((
            (application.travel_start_ms, launch["timeMs"], 2),
            (application.travel_end_ms, arrival["timeMs"], 3),
            (application.hp_ms, vital["timeMs"], 4),
            (application.number_ms, number["timeMs"], 4),
            (application.number_ms + application.damage.floatingNumber.durationMs, number_end["timeMs"], 4),
        ))
        assert vital["timeMs"] - arrival["timeMs"] == CASE["pump"]["stepMs"]
        assert number["timeMs"] == vital["timeMs"]
    caster_end = next(event["timeMs"] for event in states if event["uuid"] == "caster" and event["to"] == "Idle")
    comparisons.extend(((timeline.body_end_ms, caster_end, 1), (timeline.complete_ms, settled[0]["timeMs"], 4)))
    for ideal, observed, wakeups in comparisons:
        assert ideal is not None
        assert -1e-7 <= observed - ideal <= wakeups * CASE["pump"]["stepMs"] + 1e-7, (ideal, observed, wakeups)

    a_hits = [event for event in states if event["uuid"] == "A" and event["to"] == "TakingHit"]
    assert [(event["from"], event["timeMs"]) for event in a_hits] == [
        ("Idle", arrivals[0]["timeMs"]), ("TakingHit", arrivals[2]["timeMs"]),
    ]
    a_completions = [event for event in events if event["kind"] == "intent-completed"
                     and event["type"] == "takeDamage" and event["targetUuid"] == "A"]
    assert [(event["applicationIndex"], event["timeMs"]) for event in a_completions] == [
        (0, settled[0]["timeMs"]), (2, settled[0]["timeMs"]),
    ]
    # The first wait joins the reentered body; its nominal reaction duration is
    # not a separate body completion or a second cast queue barrier.
    first, _, last = timeline.applications
    assert first.damage_end_ms is not None and last.damage_end_ms == timeline.complete_ms
    assert sample_cast(timeline, first.damage_end_ms).bodies[1].clip == "TakeDamage"
    assert sample_cast(timeline, last.travel_end_ms - 0.001).bodies[1].frame > 0
    assert sample_cast(timeline, last.travel_end_ms).bodies[1].frame == 0
    assert not sample_cast(timeline, timeline.complete_ms - 0.001).complete
    assert sample_cast(timeline, timeline.complete_ms).complete


def test_visible_frames_preserve_three_darts_two_recipient_bodies_and_ordered_hp(timeline: CastTimeline) -> None:
    arrival_times = {event["timeMs"] for event in CASE["events"] if event["kind"] == "projectile-arrival"}
    indices = {application.source.application_id: index for index, application in enumerate(timeline.applications)}
    for reference in CASE["frames"]:
        sample = sample_cast(timeline, reference["timeMs"])
        assert [(body.actor_uuid, body.clip, body.frame) for body in sample.bodies] == [
            (body["uuid"], body["clip"], body["frame"]) for body in reference["bodies"]
        ], reference["timeMs"]
        assert [indices[effect.application_id] for effect in sample.projectiles] == reference["projectiles"]
        assert sample.complete is reference["done"]
        # At the three native arrival frames the original body's frame-zero
        # callback is pending until the next 1 ms pump. The boundary test above
        # checks that exact delay; all following HP/number samples must agree.
        if reference["timeMs"] not in arrival_times:
            assert {value.actor_uuid: value.hp for value in sample.vitals} == reference["hp"], reference["timeMs"]
            assert [f"{number.value} {number.label}" for number in sample.numbers] == reference["numbers"], reference["timeMs"]
