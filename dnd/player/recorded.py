"""Recorded native initialization and complete lineages for passive replay."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from dnd.player.capture import CompletedLineage, IntervalEnvelope
from dnd.player.facts import CombatLogAppend, PlayerSequence
from dnd.player.projection import SessionProjection, begin_projection, project_lineage, project_log_appends


class RecordedSequence(BaseModel):
    """Private native event inputs, including local objective diagnostics.

    Version 7: the startup world interval carries the actor change record of each of its versions, which the
    session's actor fold reads (engine-free replay builds bodies from births and records), and each lineage the
    native combat log of its retained events (`CompletedLineage.native_logs`), which each seat's walk projects.
    The initialization no longer carries the retired presentation's admissions, dispositions or fixture ids.
    Lineages and the startup interval also carry their sensory versions' notices (`notices`, empty when absent).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[7] = 7
    initialization: IntervalEnvelope
    lineages: tuple[CompletedLineage, ...]
    combat_log_appends: tuple[CombatLogAppend, ...] = ()


def project_sequence(native: RecordedSequence) -> PlayerSequence:
    """Produce one observer's packet entirely from their private saved capture.

    A recorded experiment has no session, so no sheet publication and no HUD.
    """
    session = SessionProjection()
    state, initial = begin_projection(session, native.initialization)
    if any(row.generation != initial.generation or row.observer_uuid != initial.observer_uuid
           for row in native.combat_log_appends):
        raise ValueError("Combat log append belongs to a different observer or generation")
    lineages = tuple(projected for row in native.lineages
        if (projected := project_lineage(session, state, row)) is not None)
    return PlayerSequence(initialization=initial, lineages=lineages,
        combat_log_appends=project_log_appends(state, native.combat_log_appends))

