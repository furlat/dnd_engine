"""Compose retained action subtrees at the original authored child anchors.

This owns no queue or clock. A movement edge and a standalone action both ask
for the same passive child group, then sample it using their historical clock.
Technical event nodes preserve ancestry without becoming extra animations.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import MovementTrajectory, SpatialChangeType
from dnd.core.life_types import LifeState
from dnd.types.world import OccupancyLayer
from game.animation import (
    ActorContact, BodySample, CastSample, VitalsSample, body_clip, body_duration, body_frame,
    sample_cast, sample_damage_body, sample_equipment, facing_for_delta, sample_idle_body,
)
from game.animation_types import AnimationData, Facing8, LifecycleFeedback, StudioCondition
from game.residue_media import ResidueReveal
from game.animation_types import ParticleMediaAsset
from game.action_media import ActionStripCue, ActionStripSample, bind_action_strips, sample_action_strip
from game.attack import BoundAttack, AttackSample, bind_attack, sample_attack
from game.body_action import BodyActionCue, bind_body_action, join_body_action, sample_body_action
from game.combat import BoundCast, BoundEquipment, actor_contact, actor_is_visible, bind_cast, bind_equipment
from game.condition_animation import ConditionTimeline, ConditionSample, compile_condition, sample_condition
from game.damage import DamageCue, bind_damage, sample_damage
from game.forced_movement import (
    ForcedMovementCue, ShoveCue, bind_forced_movement, bind_shove,
    forced_contact, sample_forced_body, sample_shove,
)
from game.player_facts import (
    ActionFact, AttackFact, ConditionChangeFact, DamageFact, DeathSaveFact, EquipmentFact, ForcedMovementFact,
    HealFact, ItemChargeFact, LifeFact, MovementFact, PlayerActor, PlayerLineage, PlayerNode, PlayerObservation, PlayerState,
    SensoryFact, ShoveFact, SpellFact, SpatialEffectStateFact, SpatialFact, StepFact,
)
from game.world_animation import (
    WorldTransition, world_transitions, world_transition_end, merge_world_transitions, surface_reveal_delay,
)
from game.player_reduction import copy_target, lineage_branch, reduce_lineage, reduce_nodes, observe_actors, stage_actors, stage_lineage


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
    event: PlayerNode
    start_ms: float


@dataclass(frozen=True, slots=True)
class EquipmentCue:
    event_uuid: UUID
    start_ms: float
    bound: BoundEquipment


@dataclass(frozen=True, slots=True)
class LifecycleCue:
    event: PlayerNode
    start_ms: float
    contact: ActorContact
    feedback: LifecycleFeedback | None
    state_owned: bool
    death_end_ms: float | None
    data: AnimationData


@dataclass(frozen=True, slots=True)
class MotionCue:
    event_uuid: UUID
    start_ms: float
    timeline: "MotionTimeline"
    data: AnimationData


@dataclass(frozen=True, slots=True)
class BoundChoreography:
    root_uuid: UUID
    before: PlayerState
    after: PlayerState
    nodes: tuple[ActionNode, ...]
    conditions: tuple[ConditionTimeline, ...]
    complete_ms: float
    gaps: tuple[tuple[UUID, str], ...]
    healing: tuple[HealingCue, ...] = ()
    lifecycle: tuple[LifecycleCue, ...] = ()
    equipment: tuple[EquipmentCue, ...] = ()
    shoves: tuple[ShoveCue, ...] = ()
    forced_movement: tuple[ForcedMovementCue, ...] = ()
    damage: tuple[DamageCue, ...] = ()
    observations: tuple[tuple[float, PlayerObservation], ...] = ()
    body_actions: tuple[BodyActionCue, ...] = ()
    states: tuple[tuple[float, PlayerState], ...] = ()
    world_transitions: tuple[WorldTransition, ...] = ()
    movements: tuple[MotionCue, ...] = ()
    strips: tuple[ActionStripCue, ...] = ()
    residue_reveals: tuple[ResidueReveal, ...] = ()


@dataclass(frozen=True, slots=True)
class ChoreographySample:
    displayed: PlayerState
    clips: tuple[ActionSample, ...]
    conditions: tuple[ConditionSample, ...]
    vitals: tuple[VitalsSample, ...]
    complete: bool
    bodies: tuple[BodySample, ...] = ()
    contacts: tuple[ActorContact, ...] = ()
    strips: tuple[ActionStripSample, ...] = ()


def _before_event(before: PlayerState, lineage: PlayerLineage, event: PlayerNode) -> PlayerState:
    first = min(row.source_index for row in lineage.version_rows if row.lineage_uuid == event.lineage_uuid)
    completed = {row.event_uuid for row in lineage.version_rows if row.source_index < first}
    events = tuple(row for row in lineage.events if row.uuid in completed)
    if not events:
        return before
    return reduce_lineage(before, replace(lineage, events=events, end_cursor=first))


def bind_choreography(before: PlayerState, lineage: PlayerLineage, data: AnimationData,
                      *, facings: Mapping[str, Facing8] | None = None,
                      contacts: Mapping[str, ActorContact] | None = None) -> BoundChoreography:
    """Compile causal ownership from historical state and authorized action entries."""
    displayed_before = before
    before = stage_lineage(before, lineage)
    observation_lineages = {row.event_uuid: row.lineage_uuid for row in lineage.version_rows}
    observations: list[tuple[float, PlayerObservation]] = []
    entry_actors: set[UUID] = set()
    root_fact = lineage.root.fact
    if isinstance(root_fact, (AttackFact, SpellFact)):
        # NeuroClient stages newly after-visible referenced action actors before
        # dispatch. A remembered hidden actor is not a presented actor: use the
        # exact received reacquisition, never its old remembered coordinate.
        referenced = {root_fact.source_entity_uuid, root_fact.target_entity_uuid}
        if isinstance(root_fact, SpellFact):
            referenced.update(root_fact.declared_target_entity_uuids)
        successor = reduce_lineage(displayed_before, lineage)
        fresh = {row.actor.uuid: replace(row, actor=successor.actors[row.actor.uuid])
                 for row in lineage.observations
                 if row.actor.uuid in referenced and row.contact is not None and row.contact.visual
                 and (row.actor.uuid not in displayed_before.actors
                      or not actor_is_visible(displayed_before, displayed_before.actors[row.actor.uuid]))
                 and row.actor.uuid in successor.actors
                 and actor_is_visible(successor, successor.actors[row.actor.uuid])}
        before = observe_actors(before, tuple(fresh.values()))
        # An arrival-only relocation supplies a binding contact, but becomes
        # visible at release. It has no witnessed departure body to stage now.
        if root_fact.behavior_id not in data.relocation_actions:
            observations.extend((0, row) for row in fresh.values())
            entry_actors.update(fresh)
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    facts = {event.uuid: event.fact.condition for event in lineage.events
             if isinstance(event.fact, ConditionChangeFact)}
    order = {event.uuid: index for index, event in enumerate(lineage.events)}
    nodes: list[ActionNode] = []
    pending_conditions: list[tuple[float, PlayerNode, StudioCondition | None]] = []
    healing: list[HealingCue] = []
    lifecycle: list[LifecycleCue] = []
    equipment: list[EquipmentCue] = []
    shoves: list[ShoveCue] = []
    forced_movement: list[ForcedMovementCue] = []
    damage: list[DamageCue] = []
    body_actions: list[BodyActionCue] = []
    movements: list[MotionCue] = []
    strips: list[ActionStripCue] = []
    residue_reveals: list[ResidueReveal] = []
    actor_order: list[tuple[UUID, int, bool]] = []
    gaps: list[tuple[UUID, str]] = []
    state_nodes: list[tuple[float, PlayerNode]] = []
    recorded_transitions: list[WorldTransition] = []
    world_events = {update.event_uuid: update for update in lineage.world_updates}

    def visit(event: PlayerNode, at: float, owner: ActionNode | None = None,
              override: StudioCondition | None = None,
              displacement: ForcedMovementCue | None = None,
              interaction_actor: UUID | None = None,
              state_at_effect: float | None = None) -> float:
        fact = event.fact
        if event.canceled:
            # Cancellation is not rollback: completed children retain their
            # facts. A canceled action body has no invented delivery anchor.
            return max((visit(by_lineage[identity], at, owner, override, displacement, interaction_actor, state_at_effect)
                        for identity in event.children_lineages), default=at)
        if displacement is not None:
            at = dict(displacement.arrivals).get(event.uuid, at)
        observation_at = at
        placed_contacts = dict(contacts or {})
        if displacement is not None:
            placed = forced_contact(displacement, data, at)
            placed_contacts[placed.actor_uuid] = placed
        end = at
        if isinstance(fact, MovementFact):
            motion = bind_motion(_before_event(before, lineage, event),
                lineage_branch(lineage, event), data, contacts=placed_contacts)
            if motion is not None:
                movements.append(MotionCue(event.uuid, at, motion, data))
                return at + motion.complete_ms
        if (event.uuid == lineage.root.uuid and isinstance(fact, SpatialFact)
                and fact.change_type is SpatialChangeType.ENTITY_ENTERED):
            state_at_effect = at
        if isinstance(fact, SpatialEffectStateFact):
            state_at_effect = at
            recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "trap_state",
                fact.previous_state.value, fact.state.value, at))
        application = isinstance(fact, SpellFact) and fact.application_index is not None
        body_action = None
        binding = data.body_action_bindings.get(fact.behavior_id or "") if isinstance(fact, ActionFact) else None
        object_interaction = binding is not None and binding.interaction_target == "source_item"
        linked_effect = (object_interaction and isinstance(fact, ActionFact)
                         and fact.source_entity_uuid == interaction_actor)
        if object_interaction and isinstance(fact, ActionFact):
            interaction_actor = fact.source_entity_uuid
        if isinstance(fact, (ActionFact, SpellFact)) and not application and not linked_effect:
            try:
                body_action = bind_body_action(_before_event(before, lineage, event), event, data,
                    start_ms=at, facings=facings or {}, contacts=placed_contacts)
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
            if body_action is not None:
                actor_order.append((event.uuid, len(body_actions), True))
                body_actions.append(body_action)
                end = body_action.complete_ms
                at = body_action.effect_ms
                override = body_action.condition
                owner = None
                gaps.extend((event.uuid, detail) for detail in body_action.gaps)
                if body_action.relocates:
                    observation_at = at
                    state_at_effect = at
        if object_interaction:
            state_at_effect = at
        observations.extend((observation_at, observation) for observation in lineage.observations
                          if observation.actor.uuid not in entry_actors
                          and observation_lineages[observation.event_uuid] == event.lineage_uuid)
        visible_action = False
        if isinstance(fact, (AttackFact, SpellFact)):
            participants = (fact.source_entity_uuid, fact.target_entity_uuid)
            visible_action = all(identity is None or str(identity) in placed_contacts
                or identity in before.actors and actor_is_visible(before, before.actors[identity])
                for identity in participants)
        if isinstance(fact, (AttackFact, SpellFact)) and not application and visible_action and body_action is None:
            branch = lineage_branch(lineage, event)
            prior = _before_event(before, lineage, event)
            try:
                bound = (bind_attack(prior, branch, data, facings=facings, contacts=placed_contacts)
                         if isinstance(fact, AttackFact) else bind_cast(prior, branch, data, contacts=placed_contacts))
            except (ValueError, NotImplementedError) as error:
                bound = None
                gaps.append((event.uuid, str(error)))
            if bound is None:
                gaps.append((event.uuid, "Authored action delivery is not bound"))
            else:
                owner = ActionNode(event.uuid, at, bound)
                actor_order.append((event.uuid, len(nodes), False))
                nodes.append(owner)
                end = at + bound.timeline.complete_ms
                if isinstance(bound, BoundAttack):
                    at += bound.timeline.contact_ms
                    gaps.extend((event.uuid, f"Missing media: {name}") for name in bound.timeline.missing_media)
                else:
                    override = bound.timeline.recipe.condition
                    at += (bound.timeline.ground_delivery.travel_end_ms if bound.timeline.ground_delivery is not None
                           else bound.timeline.applications[0].travel_end_ms)
                    if bound.timeline.ground_delivery is not None:
                        state_at_effect = at
        elif isinstance(fact, SpellFact) and application and owner is not None and isinstance(owner.bound, BoundCast):
            identity = str(fact.application_id) if fact.application_id is not None else None
            delivery = next((row for row in owner.bound.timeline.applications
                             if row.source.application_id == identity), None)
            if delivery is not None:
                at = owner.start_ms + delivery.travel_end_ms
        if isinstance(fact, ShoveFact):
            try:
                cue = bind_shove(_before_event(before, lineage, event), event, data, at, placed_contacts)
                shoves.append(cue)
                end = max(end, cue.body_end_ms)
                at = cue.contact_ms
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        if isinstance(fact, ForcedMovementFact):
            try:
                displacement = bind_forced_movement(_before_event(before, lineage, event),
                    lineage_branch(lineage, event), data, at, placed_contacts)
                forced_movement.append(displacement)
                owner = None  # Its spatial children own their own reached-cell effects.
                end = max(end, displacement.complete_ms)
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        standalone_damage = None
        if (isinstance(fact, DamageFact) and fact.stage == "taken") and owner is None:
            try:
                standalone_damage = bind_damage(_before_event(before, lineage, event),
                    lineage_branch(lineage, event), data, start_ms=at,
                    contact=placed_contacts.get(str(fact.target_entity_uuid)))
                if standalone_damage is not None:
                    damage.append(standalone_damage)
                    end = max(end, standalone_damage.timing.end_ms)
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        bound_equipment = None
        if isinstance(fact, EquipmentFact):
            try:
                bound_equipment = bind_equipment(_before_event(before, lineage, event),
                    lineage_branch(lineage, event), data, facings or {}, contacts=contacts)
                if bound_equipment is not None:
                    equipment.append(EquipmentCue(event.uuid, at, bound_equipment))
                    end = max(end, at + bound_equipment.timeline.complete_ms)
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        if state_at_effect is not None:
            # The authored release/contact owns these received state changes.
            # Other primitives keep their existing condition/HP/equipment timing.
            timed_fact = fact if (isinstance(fact, (SensoryFact, SpatialFact, ItemChargeFact))
                or isinstance(fact, EquipmentFact) and bound_equipment is None) else None
            if timed_fact is not None or event.uuid in world_events:
                state_time = state_at_effect
                if event.uuid in world_events and owner is not None and isinstance(owner.bound, BoundCast):
                    area = owner.bound.timeline.recipe.area
                    ground = owner.bound.timeline.source.ground_target
                    if area is not None and area.surfaceReveal is not None and ground is not None:
                        state_time += surface_reveal_delay(world_events[event.uuid], displayed_before,
                            area.surfaceReveal, ground.grid, ground.elevation_steps)
                state_nodes.append((state_time, replace(event, fact=timed_fact)))
        if event.uuid in facts and facts[event.uuid].category != ConditionCategory.INTERNAL:
            pending_conditions.append((at, event, override))
        if (isinstance(fact, DamageFact) and fact.stage == "applied" and fact.body_release is not None
                and fact.target_entity_uuid is not None):
            prior = _before_event(before, lineage, event)
            actor = prior.actors.get(fact.target_entity_uuid)
            tracks = data.body_release_media.get(fact.body_release.release_id, ())
            if actor is not None and actor_is_visible(prior, actor) and tracks:
                try:
                    contact = placed_contacts.get(str(actor.uuid))
                    if contact is None:
                        contact = actor_contact(prior, actor, data, (facings or {}).get(str(actor.uuid), "S"))
                    direction = (1.0, 0.0)
                    source = prior.actors.get(fact.source_entity_uuid) if fact.source_entity_uuid is not None else None
                    if source is not None and actor_is_visible(prior, source):
                        source_contact = placed_contacts.get(str(source.uuid))
                        if source_contact is None:
                            source_contact = actor_contact(prior, source, data,
                                (facings or {}).get(str(source.uuid), "S"))
                        direction = (contact.grid[0] - source_contact.grid[0],
                                     contact.grid[1] - source_contact.grid[1])
                    cues = bind_action_strips(event.uuid, contact, tracks, data,
                        start_ms=state_at_effect if state_at_effect is not None else at, direction=direction,
                        release=fact.body_release)
                    strips.extend(cues)
                    # Binding stages world geometry for anchors. Floor growth
                    # compares historical values, before that staging step.
                    floor_before = _before_event(displayed_before, lineage, event)
                    deposited = reduce_lineage(floor_before, lineage_branch(lineage, event))
                    for cue in cues:
                        if not isinstance(cue.asset, ParticleMediaAsset) or cue.asset.region is None:
                            continue
                        for region in fact.body_release.regions:
                            for position in region.positions:
                                tile = deposited.tiles.get(position)
                                if tile is None:
                                    continue
                                old_tile = floor_before.tiles.get(position)
                                for residue in tile.residues:
                                    previous = next((row for row in old_tile.residues
                                        if row.condition_uuid == residue.condition_uuid), None) if old_tile else None
                                    if residue.contributions and (previous is None or residue.amount > previous.amount):
                                        change = ResidueReveal(position, previous, residue, cue.asset,
                                            fact.body_release.pattern or "blunt", cue.start_ms, cue.end_ms,
                                            cue.track.fps / cue.asset.defaultFps)
                                        if change not in residue_reveals:
                                            residue_reveals.append(change)
                    end = max(end, *(cue.end_ms for cue in cues))
                except (ValueError, NotImplementedError) as error:
                    gaps.append((event.uuid, str(error)))
        if isinstance(fact, HealFact) and not fact.was_blocked:
            healing.append(HealingCue(event, at))
            context = data.healing_context
            if context.bodyClip != "none":
                gaps.append((event.uuid, f"Healing bodyClip {context.bodyClip!r} is not bound"))
            if context.media:
                gaps.append((event.uuid, "Healing media tracks are not bound"))
            if owner is not None:
                gaps.append((event.uuid, "Nested healing feedback is anchored; HP-at-entry timing is not bound"))
        if isinstance(fact, (DeathSaveFact, LifeFact)):
            prior = _before_event(before, lineage, event)
            actor = prior.actors.get(fact.entity_uuid)
            if actor is not None:
                try:
                    # The native life commit emits sensory removal before its
                    # completion fact. Its causal parent's entry still owns the
                    # admitted visual pose from which this transition plays.
                    contact_state = (_before_event(before, lineage, by_lineage[event.parent_lineage])
                                     if isinstance(fact, LifeFact)
                                     and event.parent_lineage is not None
                                     and event.parent_lineage in by_lineage else prior)
                    contact = actor_contact(contact_state, contact_state.actors[actor.uuid], data,
                                            (facings or {}).get(str(actor.uuid), "S"))
                    contact = replace(contact, hp=actor.normal_hp, life_state=actor.life_state)
                    placed = placed_contacts.get(contact.actor_uuid)
                    if placed is not None:
                        contact = replace(contact, grid=placed.grid, elevation_steps=placed.elevation_steps,
                                          body_lift_px=placed.body_lift_px, facing=placed.facing)
                    feedback = None
                    state_owned = (owner is not None and event.uuid in owner.bound.owned_life_events
                                   or any(event.uuid in cue.owned_life_events for cue in damage))
                    death_end = None
                    if isinstance(fact, DeathSaveFact):
                        saves = data.death_save_context
                        feedback = (saves.criticalSuccess if fact.natural_roll == 20 else
                                    saves.criticalFailure if fact.natural_roll == 1 else
                                    saves.success if fact.succeeded else saves.failure)
                    else:
                        states = data.life_state_context
                        feedback = {LifeState.DYING: states.dying, LifeState.STABLE: states.stable,
                                    LifeState.ALIVE: states.revived}.get(fact.new_state)
                        if fact.new_state is LifeState.ALIVE and fact.previous_state is LifeState.ALIVE:
                            feedback = None
                        if not state_owned and fact.new_state is LifeState.DEAD:
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
        injury_at = None
        if standalone_damage is not None:
            cue = standalone_damage
            injury_at = cue.timing.start_ms
            terminal = cue.resulting_life_state == LifeState.DEAD or cue.contact.life_state == LifeState.DEAD
            metadata = body_clip(data, cue.contact, data.damage_context.bodyClip)
            child_at = cue.timing.start_ms if terminal else cue.timing.start_ms + (
                data.damage_context.conditionFrame * 1000 / (metadata.fps * data.damage_context.bodyPlaybackSpeed))
        if (isinstance(fact, DamageFact) and fact.stage == "taken") and owner is not None:
            contact = None
            damage_start = None
            if isinstance(owner.bound, BoundAttack):
                contact = owner.bound.timeline.target
                timing = owner.bound.timeline.damage_timing
                damage_start = owner.start_ms + timing.start_ms if timing is not None else at
            else:
                delivery = next((row for row in owner.bound.timeline.applications
                                 if row.source.target.actor_uuid == str(fact.target_entity_uuid)
                                 and abs(owner.start_ms + row.travel_end_ms - at) < .001), None)
                if delivery is not None:
                    contact = delivery.source.target
                    damage_start = owner.start_ms + (delivery.damage_start_ms or delivery.travel_end_ms)
            if contact is not None and damage_start is not None:
                injury_at = damage_start
                assert fact.target_entity_uuid is not None
                clip = body_clip(data, contact, data.damage_context.bodyClip)
                after_actor = reduce_lineage(before, lineage_branch(lineage, event)).actors[fact.target_entity_uuid]
                terminal = after_actor.life_state == LifeState.DEAD or contact.life_state == LifeState.DEAD
                child_at = damage_start if terminal else damage_start + (
                    data.damage_context.conditionFrame * 1000 / (clip.fps * data.damage_context.bodyPlaybackSpeed))
        for identity in event.children_lineages:
            child = by_lineage[identity]
            # Injury-owned world changes (such as deposited residue) commit at
            # contact. Existing condition gestures keep their authored timing.
            effect_at = (injury_at if injury_at is not None and isinstance(child.fact, DamageFact)
                         and child.fact.stage == "applied" else state_at_effect)
            child_start = max(child_at, end) if isinstance(child.fact, MovementFact) else child_at
            end = max(end, visit(child, child_start, owner, override, displacement, interaction_actor, effect_at))
        return end

    complete = visit(lineage.root, 0)
    memberships = {identity: actor.conditions for identity, actor in before.actors.items()}
    conditions: list[ConditionTimeline] = []
    for at, event, override in sorted(pending_conditions, key=lambda row: (row[0], order[row[1].uuid])):
        fact = event.fact
        assert isinstance(fact, ConditionChangeFact)
        transition = compile_condition(data.condition_recipes, event, facts[event.uuid],
            memberships[fact.target_entity_uuid], start_ms=at, badge_style=data.badge_style, override=override)
        conditions.append(transition)
        memberships[fact.target_entity_uuid] = transition.after_membership
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
    for event_uuid, index, is_body in reversed(actor_order):
        child_ends = [condition.complete_ms for condition in conditions
                      if owned_by(condition.event_uuid, event_uuid)]
        child_ends.extend(child.start_ms + child.bound.timeline.complete_ms for child in nodes
                          if owned_by(child.event_uuid, event_uuid))
        child_ends.extend(child.complete_ms for child in body_actions
                          if owned_by(child.event_uuid, event_uuid))
        child_ends.extend(cue.death_end_ms for cue in lifecycle if cue.death_end_ms is not None
                          and owned_by(cue.event.uuid, event_uuid))
        child_ends.extend(cue.start_ms + cue.bound.timeline.complete_ms for cue in equipment
                          if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.complete_ms for cue in forced_movement if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.timing.end_ms for cue in damage if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.start_ms + cue.timeline.complete_ms for cue in movements
                          if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.end_ms for cue in strips if owned_by(cue.event_uuid, event_uuid))
        if not child_ends:
            continue
        if is_body:
            body_actions[index] = join_body_action(body_actions[index], data, max(child_ends))
            complete = max(complete, body_actions[index].complete_ms)
            continue
        node = nodes[index]
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
    # Compile state once at the existing causal anchors. Frame sampling selects
    # a retained value; it never folds event streams or invokes native mechanics.
    states: list[tuple[float, PlayerState]] = []
    state = displayed_before
    for at in sorted({time for time, _ in (*state_nodes, *observations)}):
        selected = tuple(sorted((node for time, node in state_nodes if time == at), key=lambda node: order[node.uuid]))
        identities = {node.uuid for node in selected}
        state = reduce_nodes(state, selected, lineage.version_rows,
            tuple(observation for time, observation in observations if time == at),
            tuple(update for update in lineage.world_updates if update.event_uuid in identities))
        states.append((at, state))
        complete = max(complete, at)
    transitions = {(row.identity, row.field, row.start_ms): row
                   for row in (*world_transitions(displayed_before, states), *recorded_transitions,
                       *(replace(change, start_ms=change.start_ms + cue.start_ms)
                         for cue in movements for change in cue.timeline.world_transitions))}
    for transition in transitions.values():
        observed = next((state for at, state in reversed(states) if at <= transition.start_ms), displayed_before)
        complete = max(complete, world_transition_end(transition, observed, data.world_animations))
    return BoundChoreography(lineage.root.uuid, displayed_before, reduce_lineage(displayed_before, lineage),
                             tuple(nodes), tuple(conditions), complete, tuple(gaps), tuple(healing),
                             tuple(lifecycle), tuple(equipment), tuple(shoves), tuple(forced_movement), tuple(damage),
                             tuple(observations), tuple(body_actions), tuple(states),
                             tuple(sorted(transitions.values(), key=lambda row: row.start_ms)), tuple(movements), tuple(strips), tuple(residue_reveals) + tuple(
                                 replace(change, start_ms=change.start_ms + cue.start_ms,
                                         end_ms=change.end_ms + cue.start_ms)
                                 for cue in movements for change in cue.timeline.residue_reveals))


def sample_choreography(bound: BoundChoreography, elapsed_ms: float) -> ChoreographySample:
    """Absolute sampling: seeking neither replays mechanics nor consumes facts."""
    state = next((state for at, state in reversed(bound.states) if elapsed_ms >= at), bound.before)
    displayed = copy_target(state)
    clips: list[ActionSample] = []
    vitals: dict[str, VitalsSample] = {}
    bodies: dict[str, BodySample] = {}
    contacts: dict[str, ActorContact] = {}
    strips = [sample for cue in bound.strips
              if (sample := sample_action_strip(cue, elapsed_ms)) is not None]
    for cue in bound.body_actions:
        body = sample_body_action(cue, cue.data, elapsed_ms)
        if body is not None:
            contact = cue.contact
            if cue.relocates and elapsed_ms >= cue.effect_ms:
                actor = displayed.actors.get(UUID(body.actor_uuid))
                if actor is None or not actor_is_visible(displayed, actor):
                    continue
                contact = actor_contact(displayed, actor, cue.data, cue.contact.facing)
            bodies[body.actor_uuid] = body
            contacts[body.actor_uuid] = contact
    for cue in bound.shoves:
        if elapsed_ms >= cue.start_ms:
            bodies[cue.source.actor_uuid] = sample_shove(cue, cue.data, elapsed_ms)
            contacts[cue.source.actor_uuid] = cue.source
    for cue in bound.forced_movement:
        if elapsed_ms >= cue.start_ms:
            bodies[cue.actor.actor_uuid] = sample_forced_body(cue, cue.data, elapsed_ms)
            contacts[cue.actor.actor_uuid] = forced_contact(cue, cue.data, elapsed_ms)
    for node in bound.nodes:
        if elapsed_ms < node.start_ms:
            continue
        local = elapsed_ms - node.start_ms
        sample = (sample_attack(node.bound.timeline, local) if isinstance(node.bound, BoundAttack)
                  else sample_cast(node.bound.timeline, local))
        clips.append(ActionSample(node, sample))
        vitals.update((value.actor_uuid, value) for value in sample.vitals)
    for cue in bound.equipment:
        if elapsed_ms < cue.start_ms:
            continue
        sample = sample_equipment(cue.bound.timeline, elapsed_ms - cue.start_ms)
        identity = UUID(cue.bound.timeline.actor.actor_uuid)
        successor = cue.bound.after.actors[identity]
        if sample.committed:
            displayed.actors[identity] = replace(displayed.actors[identity],
                visual_loadout=replace(displayed.actors[identity].visual_loadout,
                    active_weapon_set=successor.visual_loadout.active_weapon_set))
        if sample.complete:
            # The authored commitFrame selects the set; completed item facts
            # settle the loadout identity after the same gesture.
            displayed.actors[identity] = replace(displayed.actors[identity],
                visual_loadout=successor.visual_loadout, controlled_items=successor.controlled_items,
                armor_class=successor.armor_class)
        else:
            bodies[sample.body.actor_uuid] = sample.body
    for cue in bound.damage:
        sample = sample_damage(cue, elapsed_ms)
        if sample.vitals is not None:
            vitals[cue.contact.actor_uuid] = sample.vitals
        if sample.body is not None:
            bodies[cue.contact.actor_uuid] = sample.body
    for cue in bound.lifecycle:
        if elapsed_ms < cue.start_ms or cue.state_owned or not isinstance(cue.event.fact, LifeFact):
            continue
        fact, contact = cue.event.fact, cue.contact
        vitals[contact.actor_uuid] = VitalsSample(contact.actor_uuid, fact.normal_hit_points, fact.new_state, None)
        if cue.death_end_ms is not None:
            bodies[contact.actor_uuid] = sample_damage_body(cue.data, contact, elapsed_ms, death_start_ms=cue.start_ms)
        elif fact.new_state is LifeState.ALIVE:
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
    for cue in bound.movements:
        if elapsed_ms < cue.start_ms:
            continue
        motion = sample_motion(cue.timeline, cue.data, elapsed_ms - cue.start_ms)
        if motion.displayed is not None:
            displayed = copy_target(motion.displayed)
        if motion.contact is not None:
            contacts[motion.contact.actor_uuid] = motion.contact
        if motion.body is not None:
            bodies[motion.body.actor_uuid] = motion.body
        vitals.update((value.actor_uuid, value) for value in motion.displayed_vitals)
        if motion.reaction_sample is not None:
            child = motion.reaction_sample
            clips.extend(child.clips)
            bodies.update((body.actor_uuid, body) for body in child.bodies)
            contacts.update((contact.actor_uuid, contact) for contact in child.contacts)
            strips.extend(child.strips)
    return ChoreographySample(displayed, tuple(clips), conditions, tuple(vitals.values()),
                              elapsed_ms >= bound.complete_ms, tuple(bodies.values()), tuple(contacts.values()), tuple(strips))


# Movement is a causal presentation primitive, at a root or below another effect.
@dataclass(frozen=True, slots=True)
class MotionLeg:
    start: tuple[float, float]
    end: tuple[float, float]
    start_height: float
    end_height: float
    start_ms: float
    end_ms: float
    body_start_ms: float = 0
    arc_height_px: float = 0
    curve_from: float = 0
    curve_to: float = 1
    initial_lift_px: float = 0


@dataclass(frozen=True, slots=True)
class MotionReaction:
    choreography: BoundChoreography
    contact: ActorContact
    source: ActorContact | None
    start_ms: float
    end_ms: float
    lift_px: float = 0
    action_label: str | None = None


@dataclass(frozen=True, slots=True)
class MotionTimeline:
    actor: ActorContact
    legs: tuple[MotionLeg, ...]
    clip: str
    playback_speed: float
    arc_height_px: float
    complete_ms: float
    reactions: tuple[MotionReaction, ...]
    settled_contact: ActorContact | None
    before: PlayerState
    actor_state: PlayerActor
    settled_lift_px: float = 0
    body_loops: bool = True
    states: tuple[tuple[float, PlayerState], ...] = ()
    world_transitions: tuple[WorldTransition, ...] = ()
    residue_reveals: tuple[ResidueReveal, ...] = ()


@dataclass(frozen=True, slots=True)
class MotionSample:
    contact: ActorContact | None
    body: BodySample | None
    lift_px: float
    complete: bool
    reaction: BoundChoreography | None = None
    reaction_elapsed_ms: float = 0
    displayed_vitals: tuple[VitalsSample, ...] = ()
    displayed: PlayerState | None = None
    reaction_sample: ChoreographySample | None = None


def _bind_jump(target: PlayerState, lineage: PlayerLineage, jump: MovementFact,
               steps: tuple[PlayerNode, ...], data: AnimationData,
               actor: ActorContact, contacts: Mapping[str, ActorContact]) -> MotionTimeline | None:
    """Resolve retained reactions at launch, then traverse one authored flight."""
    requested = jump.requested_end_position or jump.end_position
    assert requested is not None and jump.start_position is not None and jump.end_position is not None
    facing = facing_for_delta((requested[0] - actor.grid[0], requested[1] - actor.grid[1]), data)
    launch = replace(actor, facing=facing)
    working = target
    launch_state = target
    elapsed = 0.0
    reactions: list[MotionReaction] = []
    for step_node in steps:
        step = step_node.fact
        assert isinstance(step, StepFact)
        branch = lineage_branch(lineage, step_node)
        for event in branch.events:
            if not isinstance(event.fact, (AttackFact, SpellFact)) or event.parent_lineage != step_node.lineage_uuid:
                continue
            reaction_context = data.movement_reaction_context
            if reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled:
                return None
            current = working.actors[step.source_entity_uuid]
            # This existing composition places every OA before the one arc.
            # Earlier native steps cannot advance its retained launch layer.
            working = replace(working, actors={**working.actors, current.uuid: replace(
                current, occupancy_layer=target.actors[current.uuid].occupancy_layer)})
            held = replace(launch, hp=current.normal_hp, life_state=current.life_state)
            group = bind_choreography(working, lineage_branch(lineage, event), data,
                facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
            source = contacts.get(str(event.fact.source_entity_uuid)) or _visible_contact(
                working, event.fact.source_entity_uuid, data)
            reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                            held.body_lift_px, event.fact.name))
            elapsed += group.complete_ms
            working = group.after
            launch_state = working
        working = reduce_lineage(working, branch)
        if not step.committed:
            break
    final = reduce_lineage(target, lineage)
    settled = actor_contact(final, final.actors[jump.source_entity_uuid], data, facing)
    takeoff = next((node for node in lineage.events
                    if isinstance(node.fact, SpatialFact)
                    and node.fact.entity_uuid == jump.source_entity_uuid
                    and node.fact.change_type is SpatialChangeType.ENTITY_ENTERED
                    and node.fact.previous_occupancy_layer is OccupancyLayer.GROUND
                    and node.fact.occupancy_layer is OccupancyLayer.AIR), None)
    if takeoff is not None:
        # The recorded contact transition owns this state, including one-cell
        # jumps. A legacy arc without that fact supplies no layer information.
        launch_state = reduce_nodes(launch_state, (takeoff,), lineage.version_rows, (), ())
    landing = next((node for node in lineage.events
                    if isinstance(node.fact, SpatialFact)
                    and node.fact.entity_uuid == jump.source_entity_uuid
                    and node.fact.change_type is SpatialChangeType.ENTITY_ENTERED
                    and node.fact.previous_occupancy_layer is OccupancyLayer.AIR
                    and node.fact.occupancy_layer is OccupancyLayer.GROUND), None)
    context = data.movement_context
    last_step = steps[-1].fact
    assert isinstance(last_step, StepFact)
    legs: tuple[MotionLeg, ...] = ()
    states: list[tuple[float, PlayerState]] = []
    arc = 0.0
    if not last_step.committed:
        # Native earlier Steps may have committed. Preserve their legal facts;
        # the existing placement layer retains this unlaunched visual body.
        settled = replace(settled, grid=launch.grid, elevation_steps=launch.elevation_steps,
                          body_lift_px=launch.body_lift_px)
    else:
        arrival = last_step.to_position
        arrival_height = last_step.to_elevation_feet / 5
        distance = hypot(arrival[0] - jump.start_position[0],
                         arrival[1] - jump.start_position[1])
        duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                       context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
        legs = (MotionLeg(launch.grid, arrival, launch.elevation_steps, arrival_height,
                          elapsed, elapsed + duration, elapsed, arc, initial_lift_px=launch.body_lift_px),)
        states.append((elapsed, launch_state))
        elapsed += duration
    if landing is not None:
        landed = lineage_branch(lineage, landing)
        if any(isinstance(node.fact, (DamageFact, ConditionChangeFact, SpatialEffectStateFact,
                                      AttackFact, SpellFact)) for node in landed.events):
            first = min(row.source_index for row in lineage.version_rows
                        if row.lineage_uuid == landing.lineage_uuid)
            prior_ids = {row.event_uuid for row in lineage.version_rows if row.source_index < first}
            prior = reduce_nodes(target, tuple(node for node in lineage.events if node.uuid in prior_ids),
                lineage.version_rows, tuple(row for row in lineage.observations if row.event_uuid in prior_ids),
                tuple(row for row in lineage.world_updates if row.event_uuid in prior_ids))
            landing_contact = (replace(settled, grid=last_step.to_position,
                elevation_steps=last_step.to_elevation_feet / 5) if last_step.committed else settled)
            group = bind_choreography(prior, landed, data,
                contacts={**contacts, actor.actor_uuid: landing_contact})
            if group.complete_ms > 0:
                states.append((elapsed, prior))
                reactions.append(MotionReaction(group, landing_contact, None, elapsed, elapsed + group.complete_ms))
                elapsed += group.complete_ms
    # Later movement within the same native action starts from the completed
    # incoming jump. Its own retained Steps own subsequent travel and reactions.
    for event in lineage.events:
        if (not isinstance(event.fact, MovementFact)
                or event.parent_lineage != lineage.root.lineage_uuid):
            continue
        prior = _before_event(target, lineage, event)
        held = _visible_contact(prior, jump.source_entity_uuid, data, facing)
        group = bind_choreography(prior, lineage_branch(lineage, event), data,
            contacts={**contacts, actor.actor_uuid: held} if held is not None else contacts)
        if held is not None and group.complete_ms > 0:
            reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms))
            elapsed += group.complete_ms
    states.append((elapsed, final))
    transitions = merge_world_transitions(world_transitions(target, states),
        tuple(replace(change, start_ms=change.start_ms + reaction.start_ms)
              for reaction in reactions for change in reaction.choreography.world_transitions))
    return MotionTimeline(launch, legs, context.jumpClip, 1, arc, elapsed,
                          tuple(reactions), settled, target, target.actors[jump.source_entity_uuid],
                          settled_lift_px=settled.body_lift_px, body_loops=False,
                          states=tuple(states), world_transitions=transitions,
                          residue_reveals=tuple(replace(change,
                              start_ms=change.start_ms + reaction.start_ms,
                              end_ms=change.end_ms + reaction.start_ms)
                              for reaction in reactions for change in reaction.choreography.residue_reveals))


def _visible_contact(state: PlayerState, actor_uuid: UUID, data: AnimationData,
                     facing: Facing8 = "S") -> ActorContact | None:
    actor = state.actors.get(actor_uuid)
    return actor_contact(state, actor, data, facing) if actor is not None and actor_is_visible(state, actor) else None


def bind_motion(target: PlayerState, lineage: PlayerLineage,
                data: AnimationData, *, contacts: Mapping[str, ActorContact] | None = None) -> MotionTimeline | None:
    """Compile disclosed movement and ordered observation changes in one head.

    Hidden causal nodes supply no travel distance or duration. A received loss
    followed by reacquisition has one authored step of spacing; an isolated
    visible contact has the same dwell. Neither interval invents an edge.
    """
    root = lineage.root.fact
    if not isinstance(root, MovementFact):
        return None
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    children = tuple(by_lineage[identity] for identity in lineage.root.children_lineages)
    steps = tuple(event for event in children if isinstance(event.fact, StepFact))
    staged = stage_lineage(target, lineage)
    reference = _visible_contact(staged, root.source_entity_uuid, data)
    if reference is None:
        first = next((row for row in lineage.observations if row.actor.uuid == root.source_entity_uuid
                      and row.contact is not None and row.contact.visual), None)
        if first is None:
            return None
        staged = observe_actors(staged, (first,))
        reference = _visible_contact(staged, root.source_entity_uuid, data)
        assert reference is not None
    root_versions = {row.event_uuid for row in lineage.version_rows
                     if row.lineage_uuid == lineage.root.lineage_uuid}
    target = stage_actors(target, tuple(row for row in lineage.observations if row.event_uuid in root_versions))
    contacts = contacts or {}
    actor = contacts.get(reference.actor_uuid, reference)
    context = data.movement_context
    partial_jump = root.trajectory is MovementTrajectory.DIRECT_ARC
    if partial_jump and steps and root.start_position is not None and root.end_position is not None:
        return _bind_jump(target, lineage, root, steps, data, actor, contacts)
    reaction_context = data.movement_reaction_context
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    states: list[tuple[float, PlayerState]] = []
    elapsed = body_start = 0.0
    working = target
    settled = _visible_contact(working, root.source_entity_uuid, data)
    settled_lift = 0.0
    isolated_point = settled is not None
    hidden_transition = False
    uninterrupted = False
    for node in children:
        branch = lineage_branch(lineage, node)
        step = node.fact
        if not isinstance(step, StepFact) or partial_jump:
            # An opaque attempted edge still owns permitted action/effect
            # descendants. Play those at the known pose; absence of endpoint
            # authority never becomes an invented lead or flight.
            held = _visible_contact(working, root.source_entity_uuid, data)
            if held is not None and partial_jump:
                held = replace(held, grid=actor.grid, elevation_steps=actor.elevation_steps,
                               body_lift_px=actor.body_lift_px)
            overrides = dict(contacts)
            if held is not None:
                overrides[held.actor_uuid] = held
            group = bind_choreography(working, branch, data, contacts=overrides)
            if held is not None and group.complete_ms > 0:
                if hidden_transition:
                    elapsed += context.walkStepDurationMs
                    hidden_transition = False
                source = None
                label = None
                if group.nodes:
                    bound = group.nodes[0].bound
                    source = bound.timeline.source if isinstance(bound, BoundAttack) else bound.timeline.source.caster
                    action = next(row.fact for row in branch.events if row.uuid == group.nodes[0].event_uuid)
                    if isinstance(action, (AttackFact, SpellFact)):
                        label = action.name
                reactions.append(MotionReaction(group, held, source, elapsed,
                    elapsed + group.complete_ms, held.body_lift_px, label))
                elapsed += group.complete_ms
                isolated_point = False
                body_start = elapsed
            successor = group.after
            seen = _visible_contact(successor, root.source_entity_uuid, data)
            if group.movements:
                # This subtree already rendered its disclosed travel. The
                # opaque-node dwell below must not add another movement pause.
                working, settled = successor, seen
                isolated_point = hidden_transition = uninterrupted = False
                states.append((elapsed, working))
                continue
            previous = _visible_contact(working, root.source_entity_uuid, data)
            if previous is not None and (seen is None or seen.grid != previous.grid):
                if isolated_point and not partial_jump:
                    elapsed += context.walkStepDurationMs
                isolated_point = False
                hidden_transition = seen is None
                uninterrupted = False
            if seen is not None and (previous is None or seen.grid != previous.grid):
                if hidden_transition:
                    elapsed += context.walkStepDurationMs
                    hidden_transition = False
                isolated_point = True
                body_start = elapsed
            working, settled = successor, seen
            states.append((elapsed, working))
            continue
        if step.source_entity_uuid != root.source_entity_uuid:
            # Other subjects retain their own causal state, never this path.
            working = reduce_lineage(working, branch)
            states.append((elapsed, working))
            continue
        if hidden_transition:
            elapsed += context.walkStepDurationMs
            hidden_transition = False
        # Both endpoints are explicit player facts. The projection has already
        # applied native identity and per-endpoint grants; no root path is used.
        start, end = step.from_position, step.to_position
        height, end_height = step.from_elevation_feet / 5, step.to_elevation_feet / 5
        current = working.actors.get(step.source_entity_uuid, staged.actors[step.source_entity_uuid])
        leg_actor = replace(actor, hp=current.normal_hp, life_state=current.life_state)
        initial_lift = 0.0
        if not legs and _visible_contact(target, root.source_entity_uuid, data) is not None:
            start, height, initial_lift = actor.grid, actor.elevation_steps, actor.body_lift_px
        delta = end[0] - start[0], end[1] - start[1]
        distance = hypot(step.to_position[0] - step.from_position[0], step.to_position[1] - step.from_position[1])
        duration = context.walkStepDurationMs * distance
        if not uninterrupted:
            body_start = elapsed
        isolated_point = False
        attacks = tuple(event for event in branch.events if isinstance(event.fact, (AttackFact, SpellFact))
                        and event.parent_lineage == node.lineage_uuid)
        fraction = 0.0
        continuation: tuple[float, float] = start
        continuation_height = height
        if attacks:
            if reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled:
                return None
            fraction = min(0.35, max(0.12, reaction_context.movementLeadInMs / context.walkStepDurationMs))
            continuation = start[0] + delta[0] * fraction, start[1] + delta[1] * fraction
            continuation_height = height + (end_height - height) * fraction
            lead_end = elapsed + reaction_context.movementLeadInMs
            legs.append(MotionLeg(start, continuation, height, continuation_height,
                                  elapsed, lead_end, body_start, curve_to=fraction, initial_lift_px=initial_lift))
            elapsed = lead_end
            facing = facing_for_delta(delta, data)
            for attack_node in attacks:
                attack = attack_node.fact
                assert isinstance(attack, (AttackFact, SpellFact))
                current = working.actors[step.source_entity_uuid]
                held = replace(leg_actor, hp=current.normal_hp, life_state=current.life_state,
                               grid=continuation, elevation_steps=continuation_height, facing=facing,
                               body_lift_px=initial_lift * (1 - fraction))
                group = bind_choreography(working, lineage_branch(lineage, attack_node), data,
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
                source = contacts.get(str(attack.source_entity_uuid)) or _visible_contact(
                    working, attack.source_entity_uuid, data)
                reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                                held.body_lift_px, attack.name))
                elapsed += group.complete_ms
                working = group.after
            body_start = elapsed
            duration *= 1 - fraction
        if step.committed:
            legs.append(MotionLeg(continuation, end, continuation_height, end_height,
                                  elapsed, elapsed + duration, body_start, curve_from=fraction,
                                  initial_lift_px=initial_lift))
            elapsed += duration
            # Ground entry happens after reaching the cell. Its received damage,
            # conditions and world changes use the same child compositor as OA.
            for entry in branch.events:
                if (not isinstance(entry.fact, SpatialFact)
                        or entry.fact.change_type is not SpatialChangeType.ENTITY_ENTERED
                        or entry.parent_lineage != node.lineage_uuid):
                    continue
                entered = lineage_branch(lineage, entry)
                if not any(isinstance(row.fact, (DamageFact, ConditionChangeFact, SpatialEffectStateFact,
                                                AttackFact, SpellFact)) for row in entered.events):
                    continue
                held = replace(leg_actor, grid=end, elevation_steps=end_height,
                               facing=facing_for_delta(delta, data), body_lift_px=0)
                group = bind_choreography(working, entered, data,
                    contacts={**contacts, actor.actor_uuid: held})
                if group.complete_ms > 0:
                    reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms))
                    elapsed += group.complete_ms
                    body_start = elapsed
                working = group.after
        working = reduce_lineage(working, branch)
        states.append((elapsed, working))
        settled = _visible_contact(working, step.source_entity_uuid, data, facing_for_delta(delta, data))
        uninterrupted = settled is not None
        if not step.committed:
            settled_lift = initial_lift * (1 - fraction)
            if settled is not None:
                settled = replace(settled, grid=continuation, elevation_steps=continuation_height,
                                  body_lift_px=settled_lift)
            break
    if isolated_point and not partial_jump:
        elapsed += context.walkStepDurationMs
    # Root completion can carry ordinary state without a direct child payload.
    working = reduce_lineage(working, lineage)
    states.append((elapsed, working))
    if partial_jump and settled is not None and reactions:
        settled = replace(settled, grid=actor.grid, elevation_steps=actor.elevation_steps,
                          body_lift_px=actor.body_lift_px)
    if not legs and not states and not reactions:
        return None
    transitions = merge_world_transitions(world_transitions(target, states),
        tuple(replace(change, start_ms=change.start_ms + reaction.start_ms)
              for reaction in reactions for change in reaction.choreography.world_transitions))
    return MotionTimeline(actor, tuple(legs), context.walkClip, context.walkPlaybackSpeed,
                          0, elapsed, tuple(reactions), settled, target,
                          staged.actors[root.source_entity_uuid], settled_lift, states=tuple(states),
                          world_transitions=transitions,
                          residue_reveals=tuple(replace(change,
                              start_ms=change.start_ms + reaction.start_ms,
                              end_ms=change.end_ms + reaction.start_ms)
                              for reaction in reactions for change in reaction.choreography.residue_reveals))


def sample_motion(timeline: MotionTimeline, data: AnimationData, elapsed_ms: float,
                  *, clip: str | None = None) -> MotionSample:
    """Changing view or intake progress cannot alter authored movement time."""
    elapsed = max(0.0, min(elapsed_ms, timeline.complete_ms))
    complete = elapsed_ms >= timeline.complete_ms
    vitals: dict[str, VitalsSample] = {}
    displayed = timeline.before
    state_ms = -1.0
    for at, state in timeline.states:
        if elapsed < at:
            break
        displayed, state_ms = state, at
    active: MotionReaction | None = None
    active_sample: ChoreographySample | None = None
    for reaction in timeline.reactions:
        if elapsed < reaction.start_ms:
            break
        sample = sample_choreography(reaction.choreography, elapsed - reaction.start_ms)
        if reaction.end_ms > state_ms:
            displayed = sample.displayed
        vitals.update((value.actor_uuid, value) for value in sample.vitals)
        if elapsed < reaction.end_ms:
            active = reaction
            active_sample = sample
            break
    if active is not None:
        contact = active.contact
        assert active_sample is not None
        contact = next((row for row in active_sample.contacts if row.actor_uuid == contact.actor_uuid), contact)
        bodies = [body for clip_sample in active_sample.clips for body in clip_sample.sample.bodies
                  if body.actor_uuid == contact.actor_uuid]
        bodies.extend(body for body in active_sample.bodies if body.actor_uuid == contact.actor_uuid)
        body = bodies[-1] if bodies else sample_idle_body(data, contact, elapsed)
        return MotionSample(contact, body, active.lift_px, False, active.choreography,
                            elapsed - active.start_ms, tuple(vitals.values()), displayed, active_sample)
    leg = next((leg for leg in timeline.legs if leg.start_ms <= elapsed < leg.end_ms), None)
    if (complete and timeline.settled_contact is not None and timeline.legs
            and timeline.legs[-1].end_ms == timeline.complete_ms):
        leg = timeline.legs[-1]
    if leg is None:
        contact = (timeline.settled_contact if complete else
                   _visible_contact(displayed, UUID(timeline.actor.actor_uuid), data, timeline.actor.facing))
        return MotionSample(contact, sample_idle_body(data, contact, elapsed) if contact is not None else None,
                            contact.body_lift_px if contact is not None else 0, complete,
                            displayed_vitals=tuple(vitals.values()), displayed=displayed)
    progress = min(1.0, max(0.0, (elapsed - leg.start_ms) / (leg.end_ms - leg.start_ms)))
    delta = leg.end[0] - leg.start[0], leg.end[1] - leg.start[1]
    facing = facing_for_delta(delta, data)
    curve = leg.curve_from + (leg.curve_to - leg.curve_from) * progress
    lift = 4 * leg.arc_height_px * curve * (1 - curve) + leg.initial_lift_px * (1 - curve)
    contact = replace(timeline.actor, grid=(leg.start[0] + delta[0] * progress,
                                           leg.start[1] + delta[1] * progress), facing=facing,
                      elevation_steps=leg.start_height + (leg.end_height - leg.start_height) * progress,
                      body_lift_px=lift)
    current = vitals.get(contact.actor_uuid)
    if current is not None:
        contact = replace(contact, hp=current.hp, life_state=current.life_state)
    if complete and timeline.settled_contact is not None:
        contact = replace(timeline.settled_contact, facing=facing)
    selected = clip or timeline.clip
    metadata = body_clip(data, contact, selected)
    if not timeline.body_loops and selected == timeline.clip:
        frame = min(metadata.frames - 1, int(progress * metadata.frames))
    else:
        frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed,
                           metadata.frames, loop=True)
    return MotionSample(contact, BodySample(contact.actor_uuid, selected, frame, facing),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)
