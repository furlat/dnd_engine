"""Cross the real outgoing player bytes at playback-test boundaries."""

from game.animation import ActorContact, BodySample
from game.motion import MotionSample
from game.player_facts import PlayerLineage, PlayerState
from game.player_projection import decode_player_sequence, encode_player_sequence, project_sequence
from game.presentation import CompletedLineage, IntervalEnvelope
from game.replay import CapturedHistory, RecordedSequence


def player_inputs(initialization: IntervalEnvelope, lineages: tuple[CompletedLineage, ...]) -> tuple[PlayerState, tuple[PlayerLineage, ...]]:
    """Keep native assertions separate from the facts delivered to playback."""
    native = RecordedSequence(initialization=initialization, lineages=lineages)
    return decode_player_sequence(encode_player_sequence(project_sequence(native)))


def player_history(history: CapturedHistory, *, role: str | None = None) -> tuple[PlayerState, tuple[PlayerLineage, ...]]:
    if role is not None:
        return decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
    return player_inputs(history.initialization, history.lineages)


def visible_contact(sample: MotionSample) -> ActorContact:
    """A fully observed motion case must keep its expected body contact."""
    assert sample.contact is not None
    return sample.contact


def visible_body(sample: MotionSample) -> BodySample:
    assert sample.body is not None
    return sample.body
