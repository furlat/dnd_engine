"""Associate received reaction roots with their triggering presentation head.

Grouping changes no native ancestry or reduction order. Unmatched reactions
remain ordinary roots, and the caller keeps its existing playback queue.
"""

from dataclasses import dataclass

from game.player_facts import ActionFact, PlayerLineage, PlayerState
from game.player_reduction import reduce_lineage, stage_lineage


@dataclass(frozen=True, slots=True)
class PresentationGroup:
    primary: PlayerLineage
    lineages: tuple[PlayerLineage, ...]
    reactions: tuple[PlayerLineage, ...] = ()


def presentation_groups(lineages: tuple[PlayerLineage, ...]) -> tuple[PresentationGroup, ...]:
    """Join only consecutive reaction roots naming the following native root."""
    result: list[PresentationGroup] = []
    pending: list[PlayerLineage] = []
    for lineage in lineages:
        fact = lineage.root.fact
        if isinstance(fact, ActionFact) and fact.reaction is not None:
            pending.append(lineage)
            continue
        if pending and all(isinstance(reaction.root.fact, ActionFact)
                and reaction.root.fact.reaction is not None
                and reaction.root.fact.reaction.triggered_lineage_uuid == lineage.root.lineage_uuid
                for reaction in pending):
            reactions = tuple(pending)
            result.append(PresentationGroup(lineage, (*reactions, lineage), reactions))
        else:
            result.extend(PresentationGroup(reaction, (reaction,)) for reaction in pending)
            result.append(PresentationGroup(lineage, (lineage,)))
        pending.clear()
    result.extend(PresentationGroup(reaction, (reaction,)) for reaction in pending)
    return tuple(result)


def reduce_presentation_group(before: PlayerState, group: PresentationGroup) -> PlayerState:
    """Retain the original completion order and cursor for every received root."""
    after = before
    for lineage in group.lineages:
        after = reduce_lineage(after, lineage)
    return after


def stage_presentation_group(before: PlayerState, group: PresentationGroup) -> PlayerState:
    """Include real observations belonging to the separately retained reaction."""
    staged = before
    for lineage in group.lineages:
        staged = stage_lineage(staged, lineage)
    return staged
