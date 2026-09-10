"""Compose retained action subtrees at the original authored child anchors.

This owns no queue or clock. A movement edge and a standalone action both ask
for the same passive child group, then sample it using their historical clock.
Technical event nodes preserve ancestry without becoming extra animations.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from dnd.actions import AttackEvent, SpellEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import DeathSaveEvent, Event, HealEvent, LifeStateChangeEvent, TakeDamageEvent
from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, BodySample, CastSample, VitalsSample, body_clip, body_duration,
    sample_cast, sample_damage_body,
)
from game.animation_types import AnimationData, Facing8, LifecycleFeedback, StudioCondition
from game.attack import BoundAttack, AttackSample, bind_attack, sample_attack
from game.combat import BoundCast, actor_contact, bind_cast
from game.condition_animation import ConditionTimeline, ConditionSample, compile_condition, sample_condition
from game.presentation import (
    CompletedLineage, PresentationTarget, copy_target, lineage_branch, reduce_lineage,
)


@dataclass(frozen=True, slots=True)
class ActionNode:
    event_uuid: UUID
    start_ms: float
    bound: BoundAttack | BoundCast


@dataclass(frozen=True, slots=True)
class ActionSample:
    node: ActionNode
    sample: AttackSample | CastSample


@dataclass(frozen=True, slots=True)
class HealingCue:
    event: HealEvent
    start_ms: float


@dataclass(frozen=True, slots=True)
class LifecycleCue:
    event: DeathSaveEvent | LifeStateChangeEvent
    start_ms: float
    contact: ActorContact
    feedback: LifecycleFeedback | None
    state_owned: bool
    death_end_ms: float | None
    data: AnimationData


@dataclass(frozen=True, slots=True)
class BoundChoreography:
    root_uuid: UUID
    before: PresentationTarget
    after: PresentationTarget
    nodes: tuple[ActionNode, ...]
    conditions: tuple[ConditionTimeline, ...]
    complete_ms: float
    gaps: tuple[tuple[UUID, str], ...]
    healing: tuple[HealingCue, ...] = ()
    lifecycle: tuple[LifecycleCue, ...] = ()


@dataclass(frozen=True, slots=True)
class ChoreographySample:
    displayed: PresentationTarget
    clips: tuple[ActionSample, ...]
    conditions: tuple[ConditionSample, ...]
    vitals: tuple[VitalsSample, ...]
    complete: bool
    bodies: tuple[BodySample, ...] = ()


def _before_event(before: PresentationTarget, lineage: CompletedLineage, event: Event) -> PresentationTarget:
    first = min(row.source_index for row in lineage.objective_rows if row.lineage_uuid == event.lineage_uuid)
    completed = {row.event_uuid for row in lineage.objective_rows if row.source_index < first}
    events = tuple(row for row in lineage.events if row.uuid in completed)
    if not events:
        return before
    return reduce_lineage(before, replace(lineage, events=events, end_cursor=first))


def bind_choreography(before: PresentationTarget, lineage: CompletedLineage, data: AnimationData,
                      *, facings: Mapping[str, Facing8] | None = None,
                      contacts: Mapping[str, ActorContact] | None = None) -> BoundChoreography:
    """Compile exact causal ownership, never content names or future conditions."""
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    facts = {fact.event_uuid: fact for fact in lineage.conditions}
    order = {event.uuid: index for index, event in enumerate(lineage.events)}
    nodes: list[ActionNode] = []
    pending_conditions: list[tuple[float, Event, StudioCondition | None]] = []
    healing: list[HealingCue] = []
    lifecycle: list[LifecycleCue] = []
    gaps: list[tuple[UUID, str]] = []

    def visit(event: Event, at: float, owner: ActionNode | None = None,
              override: StudioCondition | None = None) -> float:
        if event.canceled:
            # Cancellation is not rollback: completed children retain their
            # facts. A canceled action body has no invented delivery anchor.
            return max((visit(by_lineage[identity], at, owner, override)
                        for identity in event.children_lineages), default=at)
        end = at
        application = isinstance(event, SpellEvent) and event.application_index is not None
        if isinstance(event, (AttackEvent, SpellEvent)) and not application:
            branch = lineage_branch(lineage, event)
            prior = _before_event(before, lineage, event)
            try:
                bound = (bind_attack(prior, branch, data, facings=facings, contacts=contacts)
                         if isinstance(event, AttackEvent) else bind_cast(prior, branch, data, contacts=contacts))
            except (ValueError, NotImplementedError) as error:
                bound = None
                gaps.append((event.uuid, str(error)))
            if bound is None:
                gaps.append((event.uuid, "Authored action delivery is not bound"))
            else:
                owner = ActionNode(event.uuid, at, bound)
                nodes.append(owner)
                end = at + bound.timeline.complete_ms
                if isinstance(bound, BoundAttack):
                    at += bound.timeline.contact_ms
                    gaps.extend((event.uuid, f"Missing media: {name}") for name in bound.timeline.missing_media)
                else:
                    override = bound.timeline.recipe.condition
                    at += bound.timeline.applications[0].travel_end_ms
        elif isinstance(event, SpellEvent) and application and owner is not None and isinstance(owner.bound, BoundCast):
            identity = str(event.application_id) if event.application_id is not None else None
            delivery = next(row for row in owner.bound.timeline.applications
                            if row.source.application_id == identity)
            at = owner.start_ms + delivery.travel_end_ms
        if event.uuid in facts and facts[event.uuid].category != ConditionCategory.INTERNAL:
            pending_conditions.append((at, event, override))
        if isinstance(event, HealEvent) and not event.was_blocked:
            healing.append(HealingCue(event, at))
            context = data.healing_context
            if context.bodyClip != "none":
                gaps.append((event.uuid, f"Healing bodyClip {context.bodyClip!r} is not bound"))
            if context.media:
                gaps.append((event.uuid, "Healing media tracks are not bound"))
            if owner is not None:
                gaps.append((event.uuid, "Nested healing feedback is anchored; HP-at-entry timing is not bound"))
        if isinstance(event, (DeathSaveEvent, LifeStateChangeEvent)):
            prior = _before_event(before, lineage, event)
            actor = prior.actors.get(event.entity_uuid)
            if actor is not None:
                try:
                    # The native life commit emits sensory removal before its
                    # completion fact. Its causal parent's entry still owns the
                    # admitted visual pose from which this transition plays.
                    contact_state = (_before_event(before, lineage, by_lineage[event.parent_lineage])
                                     if isinstance(event, LifeStateChangeEvent)
                                     and event.parent_lineage is not None
                                     and event.parent_lineage in by_lineage else prior)
                    contact = actor_contact(contact_state, contact_state.actors[actor.uuid], data,
                                            (facings or {}).get(str(actor.uuid), "S"))
                    contact = replace(contact, hp=actor.normal_hp, life_state=actor.life_state)
                    placed = (contacts or {}).get(contact.actor_uuid)
                    if placed is not None:
                        contact = replace(contact, grid=placed.grid, elevation_steps=placed.elevation_steps,
                                          body_lift_px=placed.body_lift_px, facing=placed.facing)
                    feedback = None
                    state_owned = owner is not None and event.uuid in owner.bound.owned_life_events
                    death_end = None
                    if isinstance(event, DeathSaveEvent):
                        saves = data.death_save_context
                        feedback = (saves.criticalSuccess if event.natural_roll == 20 else
                                    saves.criticalFailure if event.natural_roll == 1 else
                                    saves.success if event.succeeded else saves.failure)
                    else:
                        states = data.life_state_context
                        feedback = {LifeState.DYING: states.dying, LifeState.STABLE: states.stable,
                                    LifeState.ALIVE: states.revived}.get(event.new_state)
                        if event.new_state is LifeState.ALIVE and event.previous_state is LifeState.ALIVE:
                            feedback = None
                        if not state_owned and event.new_state is LifeState.DEAD:
                            death = data.death_context
                            death_end = at + body_duration(body_clip(data, contact, death.bodyClip),
                                                           death.bodyPlaybackSpeed)
                            if death.hiddenSlots or death.media:
                                gaps.append((event.uuid, "Standalone death hiddenSlots/media are not bound"))
                    lifecycle.append(LifecycleCue(event, at, contact, feedback, state_owned, death_end, data))
                    end = max(end, death_end if death_end is not None else at)
                except (ValueError, NotImplementedError) as error:
                    gaps.append((event.uuid, str(error)))

        # TakeDamage owns its nested condition callbacks. Direct on-hit riders
        # remain siblings at Attack's contact, exactly as in the source mapper.
        child_at = at
        if isinstance(event, TakeDamageEvent) and owner is not None:
            contact = None
            damage_start = None
            if isinstance(owner.bound, BoundAttack):
                contact = owner.bound.timeline.target
                timing = owner.bound.timeline.damage_timing
                damage_start = owner.start_ms + timing.start_ms if timing is not None else at
            else:
                delivery = next((row for row in owner.bound.timeline.applications
                                 if row.source.target.actor_uuid == str(event.target_entity_uuid)
                                 and abs(owner.start_ms + row.travel_end_ms - at) < .001), None)
                if delivery is not None:
                    contact = delivery.source.target
                    damage_start = owner.start_ms + (delivery.damage_start_ms or delivery.travel_end_ms)
            if contact is not None and damage_start is not None:
                assert event.target_entity_uuid is not None
                clip = body_clip(data, contact, data.damage_context.bodyClip)
                after_actor = reduce_lineage(before, lineage_branch(lineage, event)).actors[event.target_entity_uuid]
                terminal = after_actor.life_state == LifeState.DEAD or contact.life_state == LifeState.DEAD
                child_at = damage_start if terminal else damage_start + (
                    data.damage_context.conditionFrame * 1000 / (clip.fps * data.damage_context.bodyPlaybackSpeed))
        for identity in event.children_lineages:
            end = max(end, visit(by_lineage[identity], child_at, owner, override))
        return end

    complete = visit(lineage.root, 0)
    memberships = {identity: actor.conditions for identity, actor in before.actors.items()}
    conditions: list[ConditionTimeline] = []
    for at, event, override in sorted(pending_conditions, key=lambda row: (row[0], order[row[1].uuid])):
        assert event.target_entity_uuid is not None
        transition = compile_condition(data.condition_recipes, event, facts[event.uuid],
            memberships[event.target_entity_uuid], start_ms=at, badge_style=data.badge_style, override=override)
        conditions.append(transition)
        memberships[event.target_entity_uuid] = transition.after_membership
        complete = max(complete, transition.complete_ms)
        gaps.extend((event.uuid, detail) for detail in transition.unsupported)

    by_uuid = {event.uuid: event for event in lineage.events}

    def owned_by(identity: UUID, parent: UUID) -> bool:
        event = by_uuid[identity]
        while event.parent_lineage is not None and event.parent_lineage in by_lineage:
            event = by_lineage[event.parent_lineage]
            if event.uuid == parent:
                return True
        return False

    # Postorder joins: an authored recovery follows the whole delivery subtree,
    # including a nested cast or a condition transition longer than hit recovery.
    # These are offsets inside this one head, never extra queued roots.
    for index in reversed(range(len(nodes))):
        node = nodes[index]
        child_ends = [condition.complete_ms for condition in conditions
                      if owned_by(condition.event_uuid, node.event_uuid)]
        child_ends.extend(child.start_ms + child.bound.timeline.complete_ms for child in nodes[index + 1:]
                          if owned_by(child.event_uuid, node.event_uuid))
        child_ends.extend(cue.death_end_ms for cue in lifecycle if cue.death_end_ms is not None
                          and owned_by(cue.event.uuid, node.event_uuid))
        if not child_ends:
            continue
        child_end = max(child_ends) - node.start_ms
        timeline = node.bound.timeline
        if isinstance(node.bound, BoundCast):
            original = node.bound.timeline
            shift = max(0, child_end - original.recovery_start_ms)
            timeline = replace(original, recovery_start_ms=original.recovery_start_ms + shift,
                complete_ms=original.complete_ms + shift,
                anchors=tuple(replace(anchor, at_ms=anchor.at_ms + shift)
                              if anchor.name in ("recover", "complete") else anchor for anchor in original.anchors))
            nodes[index] = replace(node, bound=replace(node.bound, timeline=timeline))
        else:
            timeline = replace(node.bound.timeline, complete_ms=max(node.bound.timeline.complete_ms, child_end))
            nodes[index] = replace(node, bound=replace(node.bound, timeline=timeline))
        complete = max(complete, node.start_ms + timeline.complete_ms)
    return BoundChoreography(lineage.root.uuid, before, reduce_lineage(before, lineage),
                             tuple(nodes), tuple(conditions), complete, tuple(gaps), tuple(healing), tuple(lifecycle))


def sample_choreography(bound: BoundChoreography, elapsed_ms: float) -> ChoreographySample:
    """Absolute sampling: seeking neither replays mechanics nor consumes facts."""
    displayed = copy_target(bound.before)
    clips: list[ActionSample] = []
    vitals: dict[str, VitalsSample] = {}
    bodies: dict[str, BodySample] = {}
    for node in bound.nodes:
        if elapsed_ms < node.start_ms:
            continue
        local = elapsed_ms - node.start_ms
        sample = (sample_attack(node.bound.timeline, local) if isinstance(node.bound, BoundAttack)
                  else sample_cast(node.bound.timeline, local))
        clips.append(ActionSample(node, sample))
        vitals.update((value.actor_uuid, value) for value in sample.vitals)
    for cue in bound.lifecycle:
        if elapsed_ms < cue.start_ms or cue.state_owned or not isinstance(cue.event, LifeStateChangeEvent):
            continue
        event, contact = cue.event, cue.contact
        vitals[contact.actor_uuid] = VitalsSample(contact.actor_uuid, event.normal_hit_points, event.new_state, None)
        if cue.death_end_ms is not None:
            bodies[contact.actor_uuid] = sample_damage_body(cue.data, contact, elapsed_ms, death_start_ms=cue.start_ms)
        elif event.new_state is LifeState.ALIVE:
            bodies.pop(contact.actor_uuid, None)
    conditions = tuple(sample_condition(row, elapsed_ms) for row in bound.conditions)
    for timeline, sample in zip(bound.conditions, conditions):
        if elapsed_ms >= timeline.start_ms:
            actor = displayed.actors[timeline.target_uuid]
            displayed.actors[actor.uuid] = replace(actor, conditions=sample.membership)
    for identity, value in vitals.items():
        actor = displayed.actors[UUID(identity)]
        displayed.actors[actor.uuid] = replace(actor,
            normal_hp=actor.normal_hp if value.hp is None else value.hp, life_state=value.life_state)
    return ChoreographySample(displayed, tuple(clips), conditions, tuple(vitals.values()),
                              elapsed_ms >= bound.complete_ms, tuple(bodies.values()))
