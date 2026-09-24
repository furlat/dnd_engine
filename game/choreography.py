"""Compose retained action subtrees at the original authored child anchors.

This owns no queue or clock. A movement edge and a standalone action both ask
for the same passive child group, then sample it using their historical clock.
Technical event nodes preserve ancestry without becoming extra animations.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping, cast
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import EventType, MovementTrajectory, SpatialChangeType
from dnd.core.life_types import LifeState
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.world import OccupancyLayer
from game.animation import (
    ActorContact, BodySample, BodyTransition, CastSample, VitalsSample, body_clip, body_duration, body_frame,
    sample_cast, sample_damage_body, sample_equipment, facing_for_delta, sample_idle_body, resolve_damage,
    media_track_duration, actor_rest_pose, compile_life_body, sample_body_transition,
)
from game.animation_types import AnimationData, Facing8, LifecycleFeedback, StudioCondition
from game.residue_media import ResidueReveal
from game.mechanism_projectile import (MechanismProjectileCue, mechanism_projectile_duration,
    mechanism_projectile_target)
from game.animation_types import ParticleMediaAsset
from game.action_media import ActionStripCue, ActionStripSample, bind_action_strips, sample_action_strip
from game.attack import BoundAttack, AttackSample, bind_attack, sample_attack
from game.body_action import BodyActionCue, bind_body_action, join_body_action, sample_body_action
from game.body_hop import BodyHopCue, bind_save_hop, sample_body_hop
from game.portal_animation import (PortalTransferCue, bind_portal_transfer,
    portal_departure_contact, portal_arrival_contact, portal_actor_hidden)
from game.combat import BoundCast, BoundEquipment, actor_contact, actor_is_visible, bind_cast, bind_equipment
from game.condition_animation import (ConditionTimeline, ConditionSample, compile_condition, sample_condition,
                                      bind_condition_body, sample_condition_body, resolve_condition_appearance,
                                      ConditionResponseCue, bind_condition_response)
from game.condition_reaction import bind_condition_interception_media, bind_condition_reaction_bodies
from game.interruption import (ReactionMediaCue, bind_reaction_media, interruption_rule,
    interruption_ms, interrupt_body, interrupt_delivery, interrupt_sample)
from game.damage import DamageCue, bind_damage, sample_damage
from game.forced_movement import (
    ForcedMovementCue, ShoveCue, bind_forced_movement, bind_shove,
    forced_contact, sample_forced_body, sample_shove,
)
from game.player_facts import (
    ActionFact, AttackFact, ConditionChangeFact, DamageFact, DeathSaveFact, EquipmentFact, ForcedMovementFact,
    HealFact, ItemChargeFact, LifeFact, MovementFact, ObjectDamageFact, ObjectDestroyedFact, PlayerActor, PlayerLineage, PlayerNode, PlayerObservation, PlayerState,
    SensoryFact, ShoveFact, SpellFact, SpatialEffectStateFact, MechanismActivationFact, PortalTransferFact, SavingThrowFact, SpatialFact, StepFact, TemporaryHitPointsFact, TurnFact,
)
from game.world_animation import (
    DestructionContact, WorldTransition, world_transitions, world_transition_end, merge_world_transitions, surface_reveal_delay,
    bind_spatial_media_motion,
)
from game.device_art import device_bank
from game.environment_art import load_environment_art
from game.environment_animation import remnant_bank
from game.player_reduction import copy_target, lineage_branch, reduce_lineage, reduce_nodes, observe_actors, stage_actors, stage_lineage
from game.stationary_media import StationaryMediaCue
from game.spatial_contact_media import bind_spatial_contacts, ground_contact_is_authored, bind_suppression_media


@dataclass(frozen=True, slots=True)
class ActionNode:
    event_uuid: UUID
    start_ms: float
    bound: BoundAttack | BoundCast
    interrupted: bool = False


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
    body: BodyTransition | None = None
    body_end_ms: float | None = None


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
    body_hops: tuple[BodyHopCue, ...] = ()
    portals: tuple[PortalTransferCue, ...] = ()
    stationary_media: tuple[StationaryMediaCue, ...] = ()
    turn_starts: tuple[tuple[float, UUID], ...] = ()
    contact_media: tuple[StationaryMediaCue, ...] = ()
    reaction_media: tuple[ReactionMediaCue, ...] = ()
    condition_responses: tuple[ConditionResponseCue, ...] = ()


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
    hidden_actors: frozenset[str] = frozenset()
    portals: tuple[tuple[PortalTransferCue, float], ...] = ()
    stationary_media: tuple[tuple[StationaryMediaCue, float], ...] = ()
    reaction_media: tuple[tuple[ReactionMediaCue, float], ...] = ()


def _before_event(before: PlayerState, lineage: PlayerLineage, event: PlayerNode) -> PlayerState:
    first = min(row.source_index for row in lineage.version_rows if row.lineage_uuid == event.lineage_uuid)
    completed = {row.event_uuid for row in lineage.version_rows if row.source_index < first}
    events = tuple(row for row in lineage.events if row.uuid in completed)
    if not events:
        return before
    return reduce_lineage(before, replace(lineage, events=events, end_cursor=first))


def bind_choreography(before: PlayerState, lineage: PlayerLineage, data: AnimationData,
                      *, facings: Mapping[str, Facing8] | None = None,
                      contacts: Mapping[str, ActorContact] | None = None,
                      activated_conditions: frozenset[UUID] = frozenset(),
                      reactions: tuple[PlayerLineage, ...] = ()) -> BoundChoreography:
    """Compile causal ownership from historical state and authorized action entries."""
    displayed_before = before
    for reaction in reactions:
        before = stage_lineage(before, reaction)
    before = stage_lineage(before, lineage)
    observation_lineages = {row.event_uuid: row.lineage_uuid
                            for root in (*reactions, lineage) for row in root.version_rows}
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    destruction_owners: dict[UUID, UUID] = {}
    destruction_state_times: dict[UUID, float] = {}

    def index_destruction(event: PlayerNode, owner: UUID | None = None) -> None:
        if isinstance(event.fact, ObjectDestroyedFact):
            bank = remnant_bank(load_environment_art(), event.fact.item_id,
                event.fact.remnant_state, outcome=event.fact.destruction_outcome)
            owner = event.uuid if bank is not None and bank.state_change_frame else None
        if owner is not None:
            destruction_owners[event.lineage_uuid] = owner
        for identity in event.children_lineages:
            index_destruction(by_lineage[identity], owner)

    index_destruction(lineage.root)
    observations: list[tuple[float, PlayerObservation]] = []
    arrival_observations: dict[UUID, float] = {}
    entry_actors: set[UUID] = set()
    root_fact = lineage.root.fact
    if (isinstance(root_fact, (AttackFact, SpellFact))
            or isinstance(root_fact, ActionFact) and root_fact.behavior_id in data.drafts):
        # NeuroClient stages newly after-visible referenced action actors before
        # dispatch. A remembered hidden actor is not a presented actor: use the
        # exact received reacquisition, never its old remembered coordinate.
        referenced = {root_fact.source_entity_uuid, root_fact.target_entity_uuid}
        if isinstance(root_fact, SpellFact):
            referenced.update(root_fact.declared_target_entity_uuids)
        successor = reduce_lineage(displayed_before, lineage)
        fresh = {row.actor.uuid: replace(row, actor=successor.actors[row.actor.uuid])
                 for row in lineage.observations
                 if observation_lineages[row.event_uuid] not in destruction_owners
                 and row.actor.uuid in referenced and row.contact is not None and row.contact.visual
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
    facts = {event.uuid: event.fact.condition for event in lineage.events
             if isinstance(event.fact, ConditionChangeFact)}
    order = {event.uuid: index for index, event in enumerate(lineage.events)}
    nodes: list[ActionNode] = []
    pending_conditions: list[tuple[float, PlayerNode, StudioCondition | None]] = []
    reaction_condition_times: dict[UUID, float] = {}
    healing: list[HealingCue] = []
    lifecycle: list[LifecycleCue] = []
    equipment: list[EquipmentCue] = []
    shoves: list[ShoveCue] = []
    forced_movement: list[ForcedMovementCue] = []
    damage: list[DamageCue] = []
    body_actions: list[BodyActionCue] = []
    body_hops: list[BodyHopCue] = []
    portals: list[PortalTransferCue] = []
    movements: list[MotionCue] = []
    strips: list[ActionStripCue] = []
    contact_media: list[StationaryMediaCue] = []
    residue_reveals: list[ResidueReveal] = []
    actor_order: list[tuple[UUID, int, bool]] = []
    gaps: list[tuple[UUID, str]] = []
    state_nodes: list[tuple[float, PlayerNode]] = []
    turn_starts: list[tuple[float, UUID]] = []
    recorded_transitions: list[WorldTransition] = []
    external_reactions: list[BodyActionCue] = []
    reaction_media: list[ReactionMediaCue] = []
    condition_responses: dict[tuple[UUID, UUID], ConditionResponseCue] = {}
    world_events = {update.event_uuid: update for update in lineage.world_updates}
    spatial_contents = {identity: effect.content_ref.content_id
        for identity, effect in (before.senses.spatial_effects.items() if before.senses is not None else ())}
    spatial_contents.update({identity: effect.content_ref.content_id
        for event in lineage.events if isinstance(event.fact, SensoryFact)
        for identity, effect in event.fact.spatial_effects_changed.items()})

    def join_reactions(event: PlayerNode, effect_ms: float,
                       incoming: BoundCast | BodyActionCue | None = None, cutoff_ms: float = 0.) -> float:
        if event.uuid != lineage.root.uuid or not reactions:
            return 0.
        cues = []
        for reaction in reactions:
            cue = bind_body_action(before, reaction.root, data, start_ms=0.,
                facings=facings or {}, contacts=contacts or {})
            if cue is None:
                gaps.append((reaction.root.uuid, "Disclosed reaction has no authored body"))
            else:
                cues.append(cue)
                gaps.extend((cue.event_uuid, detail) for detail in cue.gaps)
        delay = max((cue.effect_ms - effect_ms for cue in cues), default=0.)
        delay = max(0., delay)
        for cue in cues:
            offset = effect_ms + delay - cue.effect_ms
            external_reactions.append(replace(cue, start_ms=offset, effect_ms=cue.effect_ms + offset,
                body_end_ms=cue.body_end_ms + offset, join_ms=cue.join_ms + offset,
                complete_ms=cue.complete_ms + offset))
            reaction = next(root.root.fact for root in reactions if root.root.uuid == cue.event_uuid)
            assert isinstance(reaction, ActionFact) and reaction.reaction is not None
            media = data.interruptions.reactions.get(reaction.behavior_id or "")
            if media is not None and incoming is not None:
                reaction_media.append(bind_reaction_media(cue.event_uuid, event.uuid, incoming,
                    media, reaction.reaction.succeeded, effect_ms + delay, cutoff_ms))
        return delay

    def visit(event: PlayerNode, at: float, owner: ActionNode | None = None,
              override: StudioCondition | None = None,
              displacement: ForcedMovementCue | None = None,
              interaction_actor: UUID | None = None,
              state_at_effect: float | None = None,
              landed_contact: ActorContact | None = None) -> float:
        fact = event.fact
        if event.canceled:
            # Invalid commands have no gesture. A recorded mechanical block
            # may play a prefix of the original action, with no invented impact.
            end = at
            rule = interruption_rule(event, data)
            if isinstance(fact, SpellFact) and fact.application_index is not None and owner is not None:
                rule = None  # The admitted area owns this child's protection response.
            if rule is not None and isinstance(fact, (AttackFact, SpellFact, ActionFact)):
                prior = _before_event(before, lineage, event)
                branch = lineage_branch(lineage, event)
                try:
                    cue = bind_body_action(prior, event, data, start_ms=at,
                        facings=facings or {}, contacts=contacts or {})
                    if cue is not None:
                        cue = interrupt_body(cue, rule)
                        delay = join_reactions(event, cue.effect_ms, cue)
                        cue = replace(cue, start_ms=cue.start_ms + delay, effect_ms=cue.effect_ms + delay,
                            body_end_ms=cue.body_end_ms + delay, join_ms=cue.join_ms + delay,
                            complete_ms=cue.complete_ms + delay)
                        body_actions.append(cue)
                        end = cue.complete_ms
                    else:
                        attempt = (bind_attack(prior, branch, data, facings=facings, contacts=contacts)
                                   if isinstance(fact, AttackFact) else bind_cast(prior, branch, data,
                                       facings=facings, contacts=contacts))
                        if attempt is not None:
                            attempt = interrupt_delivery(attempt, rule)
                            at += join_reactions(event, at + attempt.timeline.complete_ms,
                                attempt if isinstance(attempt, BoundCast) else None, attempt.timeline.complete_ms)
                            nodes.append(ActionNode(event.uuid, at, attempt, interrupted=True))
                            end = at + attempt.timeline.complete_ms
                            if isinstance(attempt, BoundCast):
                                responses = bind_suppression_media(attempt, event.uuid, at,
                                    attempt.timeline.complete_ms)
                                contact_media.extend(responses)
                                end = max(end, max((cue.end_ms for cue in responses), default=end))
                        else:
                            gaps.append((event.uuid, "Blocked action has no authored attempt profile"))
                except (ValueError, NotImplementedError) as error:
                    gaps.append((event.uuid, str(error)))
            # Cancellation is not rollback. Child facts remain at the point
            # the attempt was checked/interrupted, and can outlive that prefix.
            observations.extend((end, row) for row in lineage.observations
                if row.actor.uuid not in entry_actors
                and observation_lineages[row.event_uuid] == event.lineage_uuid)
            return max((visit(by_lineage[identity], end, owner, override, displacement, interaction_actor, state_at_effect, landed_contact)
                        for identity in event.children_lineages), default=end)
        owned_hop = next((cue for cue in body_hops if cue.movement_event_uuid == event.uuid), None)
        if owned_hop is not None:
            # The real displacement is drawn by the authored avoidance. Its
            # ordinary spatial children still commit at the recorded landing.
            landed_contact = owned_hop.landing
            displacement = None
            at = state_at_effect = owned_hop.end_ms
        if event.uuid in arrival_observations:
            # Perception can publish inside an immediate arrival consequence.
            # Its contacts, visibility and matching world support are one
            # received observation, admitted together as emergence begins.
            at = state_at_effect = arrival_observations[event.uuid]
        if displacement is not None:
            at = dict(displacement.arrivals).get(event.uuid, at)
        observation_at = at
        placed_contacts = dict(contacts or {})
        if landed_contact is not None:
            placed_contacts[landed_contact.actor_uuid] = landed_contact
        if displacement is not None:
            placed = forced_contact(displacement, data, at)
            placed_contacts[placed.actor_uuid] = placed
        end = at
        if isinstance(fact, TurnFact) and fact.event_type is EventType.TURN_START and fact.entity_uuid is not None:
            turn_starts.append((at, fact.entity_uuid))
        if isinstance(fact, MovementFact):
            motion = bind_motion(_before_event(before, lineage, event),
                lineage_branch(lineage, event), data, contacts=placed_contacts,
                activated_conditions=activated_conditions)
            if motion is not None:
                movements.append(MotionCue(event.uuid, at, motion, data))
                return at + motion.complete_ms
        if (event.uuid == lineage.root.uuid and isinstance(fact, SpatialFact)
                and fact.change_type is SpatialChangeType.ENTITY_ENTERED):
            state_at_effect = at
        if isinstance(fact, PortalTransferFact) and fact.committed:
            prior = _before_event(before, lineage, event)
            branch = lineage_branch(lineage, event)
            successor = reduce_lineage(prior, branch)
            content = fact.portal_content_id or (
                spatial_contents.get(fact.portal_uuid, "") if fact.portal_uuid is not None else "")
            art = data.portals.get(content or "spatial_effect.environment.portal")
            if art is None:
                gaps.append((event.uuid, f"Missing portal presentation: {content}"))
            if art is not None:
                actor = prior.actors.get(fact.target_entity_uuid)
                later = successor.actors.get(fact.target_entity_uuid)
                departure = arrival = None
                if actor is not None and fact.start_position is not None and fact.start_position in prior.tiles:
                    departure = placed_contacts.get(str(actor.uuid)) or actor_contact(prior, actor, data,
                        (facings or {}).get(str(actor.uuid), "S"))
                    departure = replace(departure, grid=fact.start_position,
                        elevation_steps=prior.tiles[fact.start_position].elevation_steps, body_lift_px=0)
                if later is not None and fact.end_position is not None and fact.end_position in successor.tiles:
                    arrival = actor_contact(successor, later, data,
                        departure.facing if departure is not None else (facings or {}).get(str(later.uuid), "S"))
                    arrival = replace(arrival, grid=fact.end_position,
                        elevation_steps=successor.tiles[fact.end_position].elevation_steps, body_lift_px=0)
                opening = next((row.start_ms for row in reversed(recorded_transitions)
                    if row.identity == fact.portal_uuid and row.field == "trap_state"
                    and row.current == "activated"), None)
                cue = bind_portal_transfer(event.uuid, fact.portal_uuid, str(fact.target_entity_uuid),
                    departure, arrival, art, at, opening, data)
                portals.append(cue)
                landed_contact = arrival
                end = cue.complete_ms
                at = cue.arrival_ms if arrival is not None else cue.disappear_ms
                observation_at = state_at_effect = at
                if arrival is not None:
                    perceived_arrival = next((node for node in branch.events
                        if isinstance(node.fact, SensoryFact) and (
                            node.fact.observer_uuid == fact.target_entity_uuid
                            and node.fact.observer_position_changed and node.fact.observer_position == fact.end_position
                            or fact.target_entity_uuid in node.fact.entity_contacts_changed
                            and node.fact.entity_contacts_changed[fact.target_entity_uuid].visual
                            and node.fact.entity_contacts_changed[fact.target_entity_uuid].position == fact.end_position)), None)
                    if perceived_arrival is not None:
                        arrival_observations[perceived_arrival.uuid] = at
                if arrival is not None and departure is None:
                    # A first arrival observation can belong to an immediate
                    # ground consequence. Reveal its exact received snapshot
                    # as the authorized body emerges, without inventing the
                    # unseen pre-injury actor state.
                    received = next((row for row in lineage.observations
                        if row.actor.uuid == fact.target_entity_uuid and row.contact is not None
                        and row.contact.visual and row.contact.position == fact.end_position), None)
                    if received is not None:
                        observations.append((at, received))
        if isinstance(fact, MechanismActivationFact) and fact.committed:
            animation = data.world_animations.get(fact.mechanism_content_id)
            if animation is not None and animation.activation_frames:
                release_ms = (animation.contact_frame or 0) * 1000 / animation.fps
                duration = len(animation.activation_frames) * 1000 / animation.fps
                projectile = None
                origin = fact.origin_position or next(iter(fact.affected_positions), None)
                destination = fact.end_position or (fact.affected_positions[-1] if fact.affected_positions else None)
                if (animation.projectile is not None and origin is not None and destination is not None
                        and origin in before.tiles and destination in before.tiles):
                    start_height = before.tiles[origin].elevation_steps
                    end_height = before.tiles[destination].elevation_steps
                    prior = _before_event(before, lineage, event)
                    actor = prior.actors.get(fact.target_entity_uuid) if fact.target_entity_uuid else None
                    target_registration = None
                    if actor is not None and actor_is_visible(prior, actor):
                        contact = placed_contacts.get(str(actor.uuid)) or actor_contact(
                            prior, actor, data, (facings or {}).get(str(actor.uuid), "S"))
                        target_registration = mechanism_projectile_target(contact, data)
                    travel = mechanism_projectile_duration(origin, destination, start_height, end_height,
                                                           animation.projectile)
                    projectile = MechanismProjectileCue(event.uuid, fact.mechanism_uuid,
                        origin, start_height, destination, end_height, fact.direction, animation.projectile,
                        release_ms, release_ms + travel, target_registration, fact.origin_position is not None)
                    release_ms += travel
                    duration = max(duration, release_ms)
                identity = fact.mechanism_uuid if fact.origin_position is not None else None
                recorded_transitions.append(WorldTransition(identity or event.uuid, "activation", None, None, at,
                    duration_ms=duration, projectile=projectile))
                end = at + duration
                if animation.successful_save_hop is not None:
                    prior = _before_event(before, lineage, event)
                    children = tuple(by_lineage[row] for row in event.children_lineages)
                    saved = dict.fromkeys(node.fact.target_entity_uuid for node in children
                        if isinstance(node.fact, SavingThrowFact) and node.fact.succeeded and not node.canceled
                        and node.fact.effect_id == animation.successful_save_hop.effect_id)
                    for target_uuid in saved:
                        actor = prior.actors.get(target_uuid)
                        movement = next((node.fact for node in children
                            if isinstance(node.fact, ForcedMovementFact) and not node.canceled
                            and node.fact.target_entity_uuid == target_uuid and node.fact.actual_distance > 0), None)
                        if (actor is None or not actor_is_visible(prior, actor) or movement is None
                                or movement.end_position not in before.tiles):
                            continue
                        contact = placed_contacts.get(str(actor.uuid)) or actor_contact(
                            prior, actor, data, (facings or {}).get(str(actor.uuid), "S"))
                        hop = bind_save_hop(event, children,
                            animation.successful_save_hop, contact, at + release_ms, data,
                            landing_elevation_steps=before.tiles[movement.end_position].elevation_steps)
                        if hop is not None:
                            body_hops.append(hop)
                            end = max(end, hop.end_ms)
                at += release_ms
                state_at_effect = at
        if isinstance(fact, SpatialEffectStateFact):
            state_at_effect = at
            spatial_media = data.spatial_media.get(spatial_contents.get(fact.spatial_effect_uuid, ""))
            if spatial_media is not None:
                if fact.operation is SpatialEffectChangeOperation.REMOVED:
                    recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "removal", None, None, at))
                elif (fact.operation is SpatialEffectChangeOperation.CREATED
                      and any(layer.applicationAssetId is not None for layer in spatial_media.layers)):
                    recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "creation", None, None, at))
                elif (fact.operation is SpatialEffectChangeOperation.FOOTPRINT_CHANGED
                      and spatial_media.movementSpeedCellsPerSecond is not None):
                    prior = _before_event(before, lineage, event)
                    successor = reduce_lineage(prior, lineage_branch(lineage, event))
                    old_effect = prior.senses.spatial_effects.get(fact.spatial_effect_uuid) if prior.senses is not None else None
                    new_effect = successor.senses.spatial_effects.get(fact.spatial_effect_uuid) if successor.senses is not None else None
                    field_motion = (bind_spatial_media_motion(old_effect, new_effect, spatial_media.movementSpeedCellsPerSecond)
                                    if old_effect is not None and new_effect is not None else None)
                    if field_motion is not None:
                        recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "spatial_motion",
                            str(field_motion.before.area_geometry), str(field_motion.after.area_geometry), at,
                            duration_ms=field_motion.duration_ms, spatial_motion=field_motion))
                        end = max(end, at + field_motion.duration_ms)
                        at = observation_at = state_at_effect = end
            if fact.previous_pressed is not None and fact.pressed is not None:
                recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "pressed",
                    str(fact.previous_pressed).lower(), str(fact.pressed).lower(), at))
            if fact.previous_state is not None and fact.state is not None:
                recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "trap_state",
                    fact.previous_state.value, fact.state.value, at))
                portal_art = data.portals.get(spatial_contents.get(fact.spatial_effect_uuid, ""))
                if portal_art is not None:
                    bank = portal_art.entrance
                    frames = bank.opening_frames if fact.state.value == "activated" else bank.closing_frames
                    end = max(end, at + frames * 1000 / bank.fps)
            if fact.operation is SpatialEffectChangeOperation.CREATED and owner is not None and isinstance(owner.bound, BoundCast):
                identity = spatial_contents.get(fact.spatial_effect_uuid, "")
                animation = data.world_animations.get(identity)
                if animation is not None and animation.creation_start_frame is not None:
                    recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "creation", None, None, at))
                media = data.spatial_media.get(identity)
                if media is not None:
                    timeline = owner.bound.timeline
                    track = next((track for track in timeline.recipe.media
                                  if track.assetPhase == media.assetPhase
                                  and any(track.assetId == layer.assetId for layer in media.layers)), None)
                    if track is not None:
                        end = owner.start_ms + timeline.release_ms + track.startOffsetMs + media_track_duration(data, track)
                        recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "creation", None, None,
                            at, duration_ms=max(0, end - at)))
        if isinstance(fact, SensoryFact) and fact.spatial_effects_changed:
            # Observed same-owner geometry is sufficient even when the private
            # footprint event was not disclosed. The observation is the event;
            # this does not invent a second native movement or reveal its cause.
            prior = _before_event(before, lineage, event)
            for identity, new_effect in fact.spatial_effects_changed.items():
                spatial_media = data.spatial_media.get(new_effect.content_ref.content_id)
                old_effect = prior.senses.spatial_effects.get(identity) if prior.senses is not None else None
                if spatial_media is None or spatial_media.movementSpeedCellsPerSecond is None or old_effect is None:
                    continue
                field_motion = bind_spatial_media_motion(old_effect, new_effect, spatial_media.movementSpeedCellsPerSecond)
                if field_motion is None or any(change.identity == identity and change.spatial_motion is not None
                        and change.spatial_motion.before.area_geometry == field_motion.before.area_geometry
                        and change.spatial_motion.after.area_geometry == field_motion.after.area_geometry
                        and change.start_ms <= at <= change.start_ms + change.spatial_motion.duration_ms
                        for change in recorded_transitions):
                    continue
                recorded_transitions.append(WorldTransition(identity, "spatial_motion",
                    str(field_motion.before.area_geometry), str(field_motion.after.area_geometry), at,
                    duration_ms=field_motion.duration_ms, spatial_motion=field_motion))
                end = max(end, at + field_motion.duration_ms)
            if end > at:
                at = observation_at = state_at_effect = end
        if isinstance(fact, ObjectDamageFact) and fact.applied_damage > 0:
            flash = resolve_damage(data, fact.damage_type.value if fact.damage_type is not None else None).hitFlash
            if flash.enabled:
                recorded_transitions.append(WorldTransition(fact.object_uuid, "hit_flash", None, None,
                    state_at_effect if state_at_effect is not None else at, hit_flash=flash))
        if isinstance(fact, ObjectDestroyedFact):
            prior = _before_event(before, lineage, event)
            after_destruction = reduce_lineage(prior, lineage_branch(lineage, event))
            body_uuid = fact.replacement_uuid or fact.object_uuid
            body = after_destruction.objects.get(body_uuid)
            art = data.devices.get(fact.item_id)
            if body is not None and art is not None and art.destruction is not None:
                # The public fact owns witnessed placement. Physical state
                # commits at contact; only art settles.
                device_facing = (facings or {}).get(str(fact.object_uuid))
                if device_facing is None:
                    device_facing = art.rows[art.rows.index(
                        fact.placement.orientation.value.upper() if fact.placement.orientation else "E")]
                destruction = DestructionContact(fact.item_id, fact.placement.position,
                    fact.placement.base_height_steps, device_facing, device_bank(art).degrees,
                    body_uuid, art.destruction.frame_count * 1000 / art.destruction.fps)
                recorded_transitions.append(WorldTransition(fact.object_uuid, "destruction", None, None,
                    state_at_effect if state_at_effect is not None else at, destruction))
            elif body is not None:
                environment = load_environment_art()
                if (fact.item_id in environment.doors or fact.item_id in environment.traps
                        or fact.item_id in environment.props):
                    bank = remnant_bank(environment, body.item.item_id, fact.remnant_state,
                                        outcome=fact.destruction_outcome)
                    if bank is None:
                        gaps.append((event.uuid, f"Missing environment destruction entry: {fact.item_id}"))
                    else:
                        direction = fact.placement.boundary_direction or fact.placement.orientation
                        facing = cast(Facing8, {"east": "E", "south": "S", "west": "W", "north": "N"}[
                            direction.value if direction is not None else "east"])
                        destruction = DestructionContact(fact.item_id, fact.placement.position,
                            fact.placement.base_height_steps, facing, 0, body_uuid,
                            bank.duration_ms, bank_id=bank.identity)
                        recorded_transitions.append(WorldTransition(fact.object_uuid, "destruction", None, None,
                            state_at_effect if state_at_effect is not None else at, destruction))
                        if bank.state_change_frame:
                            destruction_state_times[event.uuid] = (
                                state_at_effect if state_at_effect is not None else at
                            ) + bank.frame_times_ms[bank.state_change_frame]
                else:
                    gaps.append((event.uuid, f"Missing object destruction media: {fact.item_id}"))
        application = isinstance(fact, SpellFact) and fact.application_index is not None
        spell_draft = data.drafts.get(fact.behavior_id or "") if isinstance(fact, SpellFact) else None
        child_attack = spell_draft.childAttack if spell_draft is not None else None
        attack_presentation = None
        if isinstance(fact, AttackFact) and event.parent_lineage is not None:
            parent = by_lineage.get(event.parent_lineage)
            if (parent is not None and isinstance(parent.fact, SpellFact)
                    and parent.fact.source_entity_uuid == fact.source_entity_uuid):
                parent_draft = data.drafts.get(parent.fact.behavior_id or "")
                attack_presentation = parent_draft.childAttack if parent_draft is not None else None
        if child_attack is not None and not any(
                isinstance(by_lineage[identity].fact, AttackFact) for identity in event.children_lineages):
            gaps.append((event.uuid, "Authored child attack has no received attack"))
        body_action = None
        binding = data.body_action_bindings.get(fact.behavior_id or "") if isinstance(fact, ActionFact) else None
        object_interaction = binding is not None and binding.interaction_target is not None
        linked_effect = (object_interaction and isinstance(fact, ActionFact)
                         and fact.source_entity_uuid == interaction_actor)
        if object_interaction and isinstance(fact, ActionFact):
            interaction_actor = fact.source_entity_uuid
        if isinstance(fact, (ActionFact, SpellFact)) and not application and not linked_effect and child_attack is None:
            try:
                body_action = bind_body_action(_before_event(before, lineage, event), event, data,
                    start_ms=at, facings=facings or {}, contacts=placed_contacts)
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
            if (body_action is None and isinstance(fact, ActionFact) and fact.behavior_id is not None
                    and fact.behavior_id not in data.drafts):
                recipe_id = binding.source_recipe if binding is not None else fact.behavior_id
                actor = before.actors.get(fact.source_entity_uuid)
                if (recipe_id not in data.body_action_recipes and actor is not None
                        and (str(actor.uuid) in placed_contacts or actor_is_visible(before, actor))):
                    gaps.append((event.uuid, f"Missing body-action recipe: {recipe_id}"))
            if body_action is not None:
                rule = next((rule for rule in data.interruptions.rules
                             if rule.actionEconomySpent and "execution" in rule.phases), None)
                if reactions and rule is not None:
                    anchor = interrupt_body(body_action, rule).effect_ms
                    delay = join_reactions(event, anchor, body_action)
                    body_action = replace(body_action, start_ms=body_action.start_ms + delay,
                        effect_ms=body_action.effect_ms + delay, body_end_ms=body_action.body_end_ms + delay,
                        join_ms=body_action.join_ms + delay, complete_ms=body_action.complete_ms + delay)
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
        delivered_action = isinstance(fact, ActionFact) and fact.behavior_id in data.drafts
        if (isinstance(fact, (AttackFact, SpellFact))
                or isinstance(fact, ActionFact) and delivered_action):
            participants = (fact.source_entity_uuid, fact.target_entity_uuid)
            visible_action = all(identity is None or str(identity) in placed_contacts
                or identity in before.actors and actor_is_visible(before, before.actors[identity])
                for identity in participants)
        if ((isinstance(fact, (AttackFact, SpellFact)) or delivered_action) and not application and visible_action
                and body_action is None and child_attack is None):
            branch = lineage_branch(lineage, event)
            prior = _before_event(before, lineage, event)
            try:
                bound = (bind_attack(prior, branch, data, facings=facings, contacts=placed_contacts,
                                     child_presentation=attack_presentation)
                         if isinstance(fact, AttackFact) else bind_cast(prior, branch, data,
                             contacts=placed_contacts, facings=facings))
            except (ValueError, NotImplementedError) as error:
                bound = None
                gaps.append((event.uuid, str(error)))
            if bound is None:
                gaps.append((event.uuid, "Authored action delivery is not bound"))
            else:
                rule = next((rule for rule in data.interruptions.rules
                             if rule.actionEconomySpent and "execution" in rule.phases), None)
                if reactions and rule is not None:
                    cutoff = interruption_ms(bound, rule)
                    at += join_reactions(event, at + cutoff,
                        bound if isinstance(bound, BoundCast) else None, cutoff)
                delay, reaction_bodies = bind_condition_reaction_bodies(prior, branch, bound, data,
                    start_ms=at, facings=facings or {}, contacts=placed_contacts)
                at += delay
                owner = ActionNode(event.uuid, at, bound)
                actor_order.append((event.uuid, len(nodes), False))
                nodes.append(owner)
                if isinstance(bound, BoundCast):
                    contact = (bound.timeline.ground_delivery.travel_end_ms if bound.timeline.ground_delivery is not None
                               else min((row.travel_end_ms for row in bound.timeline.applications),
                                        default=bound.timeline.release_ms))
                    contact_media.extend(bind_suppression_media(bound, event.uuid, at, contact))
                for reaction_body in reaction_bodies:
                    actor_order.append((reaction_body.event_uuid, len(body_actions), True))
                    body_actions.append(reaction_body)
                    reaction_condition_times[reaction_body.event_uuid] = reaction_body.effect_ms
                contact_media.extend(bind_condition_interception_media(prior, branch, bound, data,
                    start_ms=at, contacts=placed_contacts))
                end = at + bound.timeline.complete_ms
                if isinstance(bound, BoundAttack):
                    at += bound.timeline.contact_ms
                    gaps.extend((event.uuid, f"Missing media: {name}") for name in bound.timeline.missing_media)
                else:
                    override = bound.timeline.recipe.condition
                    at += (bound.timeline.ground_delivery.travel_end_ms if bound.timeline.ground_delivery is not None
                           else bound.timeline.applications[0].travel_end_ms if bound.timeline.applications
                           else bound.timeline.release_ms + (bound.timeline.recipe.contact.delayMs
                               if bound.timeline.recipe.contact is not None else 0))
                    state_at_effect = at
        elif isinstance(fact, SpellFact) and application and owner is not None and isinstance(owner.bound, BoundCast):
            identity = str(fact.application_id) if fact.application_id is not None else None
            delivery = next((row for row in owner.bound.timeline.applications
                             if row.source.application_id == identity), None)
            if delivery is not None:
                at = owner.start_ms + delivery.travel_end_ms
                state_at_effect = at
        if isinstance(fact, ShoveFact):
            try:
                cue = bind_shove(_before_event(before, lineage, event), event, data, at, placed_contacts)
                shoves.append(cue)
                end = max(end, cue.body_end_ms)
                at = cue.contact_ms
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        if isinstance(fact, ForcedMovementFact):
            owner = None  # Its spatial children own their own reached-cell effects.
            if owned_hop is None:
                try:
                    displacement = bind_forced_movement(_before_event(before, lineage, event),
                        lineage_branch(lineage, event), data, at, placed_contacts)
                    forced_movement.append(displacement)
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
            pending_conditions.append((reaction_condition_times.get(event.uuid, at), event, override))
            if (isinstance(fact, ConditionChangeFact) and fact.event_type is EventType.CONDITION_REMOVAL
                    and fact.consumed):
                response = bind_condition_response(event.uuid, fact.target_entity_uuid, fact.condition,
                    "consumed", reaction_condition_times.get(event.uuid, at), data.condition_recipes)
                if response is not None:
                    condition_responses[response.event_uuid, response.owner_uuid] = response
                    end = max(end, response.end_ms)
        if isinstance(fact, TemporaryHitPointsFact):
            state_nodes.append((state_at_effect if state_at_effect is not None else at, event))
        if isinstance(fact, DamageFact) and fact.stage == "applied":
            state_nodes.append((state_at_effect if state_at_effect is not None else at, event))
        if (isinstance(fact, SpatialFact) and ground_contact_is_authored(before, fact, data)
                or isinstance(fact, DamageFact) and fact.stage == "applied" and fact.effect_id is not None):
            contact_media.extend(bind_spatial_contacts(_before_event(before, lineage, event), event, data,
                state_at_effect if state_at_effect is not None else at, placed_contacts))
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
                        release=fact.body_release,
                        spell_color=owner.bound.timeline.recipe.elementColors.primary
                            if owner is not None and isinstance(owner.bound, BoundCast) else None)
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
                                            cue.track.fps / cue.asset.defaultFps, cue.response)
                                        if change not in residue_reveals:
                                            residue_reveals.append(change)
                    end = max(end, *(cue.end_ms for cue in cues))
                except (ValueError, NotImplementedError) as error:
                    gaps.append((event.uuid, str(error)))
        if isinstance(fact, HealFact) and not fact.was_blocked:
            healing.append(HealingCue(event, at))
            state_nodes.append((at, event))
            if fact.actual_healing > 0 and fact.source_condition_uuid is not None:
                prior = _before_event(before, lineage, event)
                actor = prior.actors.get(fact.target_entity_uuid)
                member = next((row for row in actor.conditions if row.condition_uuid == fact.source_condition_uuid), None) if actor else None
                if member is not None:
                    response = bind_condition_response(event.uuid, fact.target_entity_uuid, member,
                        "healed", at, data.condition_recipes)
                    if response is not None:
                        condition_responses[response.event_uuid, response.owner_uuid] = response
                        end = max(end, response.end_ms)
            context = data.healing_context
            if context.bodyClip != "none":
                gaps.append((event.uuid, f"Healing bodyClip {context.bodyClip!r} is not bound"))
            if context.media:
                gaps.append((event.uuid, "Healing media tracks are not bound"))
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
                    life_body = None
                    body_end = None
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
                            death_end = at if actor_rest_pose(data, contact) is not None else (
                                at + body_duration(body_clip(data, contact, death.bodyClip), death.bodyPlaybackSpeed))
                            if death.hiddenSlots or death.media:
                                gaps.append((event.uuid, "Standalone death hiddenSlots/media are not bound"))
                        if not state_owned:
                            pose = resolve_condition_appearance(actor.conditions, data.condition_recipes).body_pose
                            life_body = compile_life_body(data, contact, fact.new_state, pose)
                            if life_body is not None:
                                body_end = at + life_body.frames * 1000 / life_body.fps
                    lifecycle.append(LifecycleCue(event, at, contact, feedback, state_owned, death_end, data,
                                                  life_body, body_end))
                    end = max(end, death_end if death_end is not None else at,
                              body_end if body_end is not None else at)
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
        portal_arrival = None
        if isinstance(fact, PortalTransferFact):
            portal_arrival = next((cue for cue in portals if cue.event_uuid == event.uuid), None)
        elif (isinstance(fact, SpatialFact) and fact.change_type is SpatialChangeType.ENTITY_ENTERED
                and event.parent_lineage is not None and event.parent_lineage in by_lineage):
            parent = by_lineage[event.parent_lineage]
            if (isinstance(parent.fact, PortalTransferFact)
                    and fact.entity_uuid == parent.fact.target_entity_uuid
                    and fact.position == parent.fact.end_position):
                portal_arrival = next((cue for cue in portals if cue.event_uuid == parent.uuid), None)
        for identity in event.children_lineages:
            child = by_lineage[identity]
            # Injury-owned world changes (such as deposited residue) commit at
            # contact. Existing condition gestures keep their authored timing.
            effect_at = (injury_at if injury_at is not None and (
                         isinstance(child.fact, TemporaryHitPointsFact)
                         or isinstance(child.fact, DamageFact) and child.fact.stage == "applied")
                         else state_at_effect)
            child_start = max(child_at, end) if isinstance(child.fact, MovementFact) else child_at
            if (portal_arrival is not None and portal_arrival.arrival is not None
                    and not isinstance(child.fact, (SpatialFact, SensoryFact))):
                # The receiver is disclosed as emergence begins. Its grounded
                # arrival consequences play once that same body has settled.
                child_start = max(child_start, portal_arrival.settled_ms)
                effect_at = child_start
            end = max(end, visit(child, child_start, owner, override, displacement, interaction_actor, effect_at, landed_contact))
        return end

    complete = visit(lineage.root, 0)
    for at, actor_id in turn_starts:
        actor = before.actors.get(actor_id)
        if actor is not None:
            for member in actor.conditions:
                recipe = data.condition_recipes.get(member.behavior_id or "")
                if recipe is not None and recipe.activation is not None:
                    complete = max(complete, at + max((effect.startOffsetMs + effect.durationMs
                        for effect in recipe.activation.effects), default=0))
    memberships = {identity: actor.conditions for identity, actor in before.actors.items()}
    conditions: list[ConditionTimeline] = []
    for at, event, override in sorted(pending_conditions, key=lambda row: (row[0], order[row[1].uuid])):
        fact = event.fact
        assert isinstance(fact, ConditionChangeFact)
        transition = compile_condition(data.condition_recipes, event, facts[event.uuid],
            memberships[fact.target_entity_uuid], start_ms=at, badge_style=data.badge_style, override=override,
            media=data.condition_media, media_activated=fact.condition.condition_uuid in activated_conditions)
        actor = before.actors.get(fact.target_entity_uuid)
        if actor is not None and actor_is_visible(before, actor):
            contact = (contacts or {}).get(str(actor.uuid)) or actor_contact(
                before, actor, data, (facings or {}).get(str(actor.uuid), "S"))
            transition = bind_condition_body(transition, data.condition_recipes.get(fact.condition.behavior_id or ""),
                                             data, contact)
        conditions.append(transition)
        # The same received condition commit also owns its recorded AC/max-HP
        # after-values; membership-only sampling must not leave those stale.
        state_nodes.append((transition.start_ms, event))
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
        child_ends.extend(cue.body_end_ms for cue in lifecycle if cue.body_end_ms is not None
                          and owned_by(cue.event.uuid, event_uuid))
        child_ends.extend(cue.start_ms + cue.bound.timeline.complete_ms for cue in equipment
                          if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.complete_ms for cue in forced_movement if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.timing.end_ms for cue in damage if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.start_ms + cue.timeline.complete_ms for cue in movements
                          if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.end_ms for cue in strips if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.end_ms for cue in body_hops if owned_by(cue.event_uuid, event_uuid))
        child_ends.extend(cue.end_ms for cue in condition_responses.values() if owned_by(cue.event_uuid, event_uuid))
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
    for reaction in reactions:
        cue = next((cue for cue in external_reactions if cue.event_uuid == reaction.root.uuid), None)
        observations.extend((cue.start_ms if cue is not None else 0., row) for row in reaction.observations)
    # Fracture starts at impact; its received geometry/perception can change
    # later, when the authored shape clears. Keep sibling damage, conditions,
    # releases and unrelated world changes on their own existing anchors.
    state_nodes = [(max(at, destruction_state_times.get(destruction_owners.get(node.lineage_uuid, node.uuid), at)), node)
                   if node.fact is None or isinstance(node.fact, (SensoryFact, SpatialFact))
                   else (at, node) for at, node in state_nodes]
    observations = [(max(at, destruction_state_times.get(
                        destruction_owners.get(observation_lineages[row.event_uuid], row.event_uuid), at)), row)
                    for at, row in observations]
    states: list[tuple[float, PlayerState]] = []
    state = displayed_before
    version_rows = tuple(row for root in (*reactions, lineage) for row in root.version_rows)
    for at in sorted({time for time, _ in (*state_nodes, *observations)}):
        selected = tuple(sorted((node for time, node in state_nodes if time == at), key=lambda node: order[node.uuid]))
        identities = {node.uuid for node in selected}
        state = reduce_nodes(state, selected, version_rows,
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
    # An endpoint exists only when its spatial change was disclosed. The body
    # release clock remains the relocation owner, including arrival-only views.
    stationary = []
    for index, cue in enumerate(body_actions):
        if not cue.relocates:
            continue
        draft = data.drafts[cue.recipe_id]
        for node in lineage.events:
            fact = node.fact
            if (not isinstance(fact, SpatialFact) or str(fact.entity_uuid) != cue.contact.actor_uuid
                    or not owned_by(node.uuid, cue.event_uuid)):
                continue
            attachment = {SpatialChangeType.ENTITY_LEFT: "departure_ground",
                          SpatialChangeType.ENTITY_ENTERED: "arrival_ground"}.get(fact.change_type)
            support = before.tiles.get(fact.position)
            if support is None:
                support = next((state.tiles[fact.position] for _, state in states
                                if fact.position in state.tiles), None)
            if support is None:
                continue
            for track in draft.media:
                if track.attachment == attachment:
                    media = StationaryMediaCue(node.uuid, track, fact.position, support.elevation_steps,
                        cue.contact.facing, max(cue.start_ms, cue.effect_ms+track.startOffsetMs), data)
                    stationary.append(media)
                    complete = max(complete, media.end_ms)
        declaration = by_uuid[cue.event_uuid].fact
        position = declaration.source_position if isinstance(declaration, SpellFact) else None
        support = (displayed_before.tiles.get(position) or before.tiles.get(position)) if position is not None else None
        departure_height = support.elevation_steps if support is not None else None
        previous_actor = displayed_before.actors.get(UUID(cue.contact.actor_uuid))
        if position is None and previous_actor is not None and actor_is_visible(displayed_before, previous_actor):
            previous_contact = actor_contact(displayed_before, previous_actor, data)
            position = previous_contact.grid
            departure_height = previous_contact.elevation_steps
        if position is not None and not by_uuid[cue.event_uuid].canceled:
            for track in draft.media:
                if (track.attachment != "departure_ground" or departure_height is None
                        or any(media.track.id == track.id and media.position == position
                               and owned_by(media.event_uuid, cue.event_uuid) for media in stationary)):
                    continue
                # A witnessed departure can lose all later spatial facts. Its
                # declaration or pre-head visible body still owns that contact.
                # A canceled declaration alone never proves a departure; real
                # completed spatial descendants were handled above.
                media = StationaryMediaCue(cue.event_uuid, track, position, departure_height,
                    cue.contact.facing, max(cue.start_ms, cue.effect_ms+track.startOffsetMs), data)
                stationary.append(media)
                complete = max(complete, media.end_ms)
        ends = [media.end_ms for media in stationary
                if media.event_uuid == cue.event_uuid or owned_by(media.event_uuid, cue.event_uuid)]
        if ends:
            body_actions[index] = join_body_action(cue, data, max(ends))
    # Linked reactions remain distinct native roots. Their observations and final
    # state are retained in completion order; only their body clocks overlap.
    after = displayed_before
    for reaction in reactions:
        after = reduce_lineage(after, reaction)
    after = reduce_lineage(after, lineage)
    body_actions.extend(external_reactions)
    complete = max(complete, max((cue.complete_ms for cue in external_reactions), default=0.))
    complete = max(complete, max((cue.complete_ms for cue in reaction_media), default=0.))
    return BoundChoreography(lineage.root.uuid, displayed_before, after,
                             tuple(nodes), tuple(conditions), complete, tuple(gaps), tuple(healing),
                             tuple(lifecycle), tuple(equipment), tuple(shoves), tuple(forced_movement), tuple(damage),
                             tuple(observations), tuple(body_actions), tuple(states),
                             tuple(sorted(transitions.values(), key=lambda row: row.start_ms)), tuple(movements), tuple(strips), tuple(residue_reveals) + tuple(
                                 replace(change, start_ms=change.start_ms + cue.start_ms,
                                         end_ms=change.end_ms + cue.start_ms)
                                 for cue in movements for change in cue.timeline.residue_reveals),
                             body_hops=tuple(body_hops), portals=tuple(portals), stationary_media=tuple(stationary),
                             turn_starts=tuple(turn_starts), contact_media=tuple(contact_media),
                             reaction_media=tuple(reaction_media), condition_responses=tuple(condition_responses.values()))


def sample_choreography(bound: BoundChoreography, elapsed_ms: float) -> ChoreographySample:
    """Absolute sampling: seeking neither replays mechanics nor consumes facts."""
    state = next((state for at, state in reversed(bound.states) if elapsed_ms >= at), bound.before)
    displayed = copy_target(state)
    clips: list[ActionSample] = []
    vitals: dict[str, VitalsSample] = {}
    bodies: dict[str, BodySample] = {}
    contacts: dict[str, ActorContact] = {}
    hidden: set[str] = set()
    portal_samples = [(cue, elapsed_ms) for cue in bound.portals]
    stationary_samples = [(cue, elapsed_ms) for cue in bound.stationary_media]
    reaction_samples = [(cue, elapsed_ms) for cue in bound.reaction_media]
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
        if node.interrupted and local >= node.bound.timeline.complete_ms:
            continue
        sample = (sample_attack(node.bound.timeline, local) if isinstance(node.bound, BoundAttack)
                  else sample_cast(node.bound.timeline, local))
        if node.interrupted:
            source = (node.bound.timeline.source.actor_uuid if isinstance(node.bound, BoundAttack)
                      else node.bound.timeline.source.caster.actor_uuid)
            sample = interrupt_sample(sample, source)
        clips.append(ActionSample(node, sample))
        # CastSample includes passive recipient snapshots for standalone
        # playback. Only actual damage owns HP here; healing's received state
        # must survive while a non-damaging cast continues its media tail.
        owned_vitals = ({application.source.target.actor_uuid
                         for application in node.bound.timeline.applications
                         if application.source.damage_applied}
                        if isinstance(node.bound, BoundCast) else None)
        vitals.update((value.actor_uuid, value) for value in sample.vitals
                      if owned_vitals is None or value.actor_uuid in owned_vitals)
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
    for hop in bound.body_hops:
        actor = displayed.actors.get(UUID(hop.contact.actor_uuid))
        if actor is not None and actor.life_state is LifeState.ALIVE and actor_is_visible(displayed, actor):
            sampled_hop = sample_body_hop(hop, elapsed_ms)
            if sampled_hop is not None:
                body, contact = sampled_hop
                bodies[body.actor_uuid] = body
                contacts[body.actor_uuid] = contact
            elif elapsed_ms > hop.end_ms:
                # Continue from received landing state while the mechanism's
                # closing animation finishes; an enclosing walk holds its old
                # entry contact otherwise. Later displacement keeps priority.
                contacts.setdefault(hop.contact.actor_uuid,
                    actor_contact(displayed, actor, hop.data, hop.landing.facing))
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
        elif cue.body is not None:
            body = sample_body_transition(cue.body, elapsed_ms - cue.start_ms)
            if body is not None:
                bodies[contact.actor_uuid] = body
            else:
                bodies.pop(contact.actor_uuid, None)
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
    for timeline in bound.conditions:
        body = sample_condition_body(timeline, elapsed_ms, displayed.actors[timeline.target_uuid].life_state)
        if body is not None:
            bodies[body.actor_uuid] = body
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
            hidden.update(child.hidden_actors)
            portal_samples.extend(child.portals)
            stationary_samples.extend(child.stationary_media)
            reaction_samples.extend(child.reaction_media)
    for cue in bound.portals:
        if portal_actor_hidden(cue, elapsed_ms):
            hidden.add(cue.actor_uuid)
        contact = portal_departure_contact(cue, elapsed_ms) or portal_arrival_contact(cue, elapsed_ms)
        if contact is not None:
            contacts[cue.actor_uuid] = contact
        elif cue.arrival is not None and elapsed_ms >= cue.arrival_ms:
            actor = displayed.actors.get(UUID(cue.actor_uuid))
            if actor is not None and actor_is_visible(displayed, actor):
                contacts.setdefault(cue.actor_uuid, actor_contact(displayed, actor, cue.data, cue.arrival.facing))
    return ChoreographySample(displayed, tuple(clips), conditions, tuple(vitals.values()),
                              elapsed_ms >= bound.complete_ms, tuple(bodies.values()), tuple(contacts.values()), tuple(strips),
                              frozenset(hidden), tuple(portal_samples), tuple(stationary_samples), tuple(reaction_samples))


# Passive descriptions for the developer inventory. These never dispatch events.
FACT_PRESENTATION = {
    "portal_transfer": ("portal_animation", "committed crossing; independently disclosed departure and arrival"),
    "attack": ("attack", "timeline; child results at contact"),
    "spell": ("cast", "timeline or parent application"),
    "movement": ("movement", "timeline"),
    "step": ("movement", "parent motion edge"),
    "forced_movement": ("forced_movement", "timeline"),
    "shove": ("shove", "timeline; children own outcomes"),
    "damage": ("damage", "parent contact or standalone; applied after-values"),
    "heal": ("healing", "actual HP and feedback at parent contact or standalone entry"),
    "life": ("lifecycle", "parent result or standalone lifecycle"),
    "death_save": ("lifecycle", "outcome feedback"),
    "saving_throw": ("body_hop", "factual save result; optional authored avoidance at parent contact"),
    "equipment": ("equipment", "appearance transition or state"),
    "condition": ("condition", "membership and selected appearance"),
    "action": ("body_action", "selected body recipe or causal parent"),
    "spatial_effect_state": ("world_animation", "observed spatial creation or trap transition"),
    "mechanism_activation": ("world_animation", "finite discharge; child consequences at authored contact"),
    "object_destroyed": ("world_animation", "witnessed destruction and ordinary remnant"),
    "object_damage": ("world_animation", "confirmed item damage flash at parent contact"),
}


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
    speed_scale: float = 1


@dataclass(frozen=True, slots=True)
class MotionReaction:
    choreography: BoundChoreography
    contact: ActorContact | None
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
    contact_media: tuple[StationaryMediaCue, ...] = ()


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
               actor: ActorContact, contacts: Mapping[str, ActorContact],
               activated_conditions: frozenset[UUID]) -> MotionTimeline | None:
    """Resolve retained reactions at launch, then traverse one authored flight."""
    requested = jump.requested_end_position or jump.end_position
    assert requested is not None and jump.start_position is not None and jump.end_position is not None
    facing = facing_for_delta((requested[0] - actor.grid[0], requested[1] - actor.grid[1]), data)
    launch = replace(actor, facing=facing)
    working = target
    launch_state = target
    launch_transitions: tuple[WorldTransition, ...] = ()
    elapsed = 0.0
    reactions: list[MotionReaction] = []
    contact_media: list[StationaryMediaCue] = []
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
                facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held},
                activated_conditions=activated_conditions)
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
    settled = _visible_contact(final, jump.source_entity_uuid, data, facing)
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
    for departure in lineage.events:
        if (not isinstance(departure.fact, SpatialFact)
                or departure.fact.entity_uuid != jump.source_entity_uuid
                or departure.fact.change_type is not SpatialChangeType.ENTITY_LEFT
                or departure.fact.position != jump.start_position
                or departure.fact.occupancy_layer is not OccupancyLayer.AIR):
            continue
        departing = lineage_branch(lineage, departure)
        # Takeoff releases pressure; vacating the launch cell can close an
        # occupied door. Both run alongside the arc, never as a midair pause.
        # Preflight reactions are intentionally played before this earlier
        # native subtree. Bind within the enclosing root's cursor interval,
        # retaining the actor state those reactions have already produced.
        launch_binding = replace(launch_state, reducer_cursor=target.reducer_cursor)
        group = bind_choreography(launch_binding, departing, data,
            contacts={**contacts, actor.actor_uuid: launch}, activated_conditions=activated_conditions)
        launch_transitions += tuple(replace(change, start_ms=change.start_ms + elapsed)
                                    for change in group.world_transitions)
        launch_state = group.after
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
        if settled is not None:
            settled = replace(settled, grid=launch.grid, elevation_steps=launch.elevation_steps,
                              body_lift_px=launch.body_lift_px)
    else:
        arrival = last_step.to_position
        arrival_height = last_step.to_elevation_feet / 5
        members = {member.behavior_id for member in launch_state.actors[jump.source_entity_uuid].conditions}
        # Authored takeoff anticipation happens on the ground, after any
        # preflight reaction. The body still plays one cycle over actual airtime.
        elapsed += max((track.contactFrame*1000/track.fps for track in context.jumpMedia
            if track.role == "takeoff" and set(track.whenConditions) <= members
            and not set(track.unlessConditions) & members), default=0)
        distance = hypot(arrival[0] - jump.start_position[0],
                         arrival[1] - jump.start_position[1])
        duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                       context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
        if last_step.resolved_speed_feet is not None and last_step.resolved_speed_feet > 0:
            duration *= data.movement_reference_speed_feet/last_step.resolved_speed_feet
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
        legs = (MotionLeg(launch.grid, arrival, launch.elevation_steps, arrival_height,
                          elapsed, elapsed + duration, elapsed, arc, initial_lift_px=launch.body_lift_px),)
        states.append((elapsed, launch_state))
        elapsed += duration
    if landing is not None:
        landed = lineage_branch(lineage, landing)
        if (any(isinstance(node.fact, (DamageFact, ConditionChangeFact, SpatialEffectStateFact, MechanismActivationFact, PortalTransferFact,
                                      AttackFact, SpellFact)) for node in landed.events)
                or isinstance(landing.fact, SpatialFact) and ground_contact_is_authored(target, landing.fact, data)):
            first = min(row.source_index for row in lineage.version_rows
                        if row.lineage_uuid == landing.lineage_uuid)
            prior_ids = {row.event_uuid for row in lineage.version_rows if row.source_index < first}
            prior = reduce_nodes(target, tuple(node for node in lineage.events if node.uuid in prior_ids),
                lineage.version_rows, tuple(row for row in lineage.observations if row.event_uuid in prior_ids),
                tuple(row for row in lineage.world_updates if row.event_uuid in prior_ids))
            landing_contact = (replace(launch, grid=last_step.to_position,
                elevation_steps=last_step.to_elevation_feet / 5) if last_step.committed else settled)
            group = bind_choreography(prior, landed, data,
                contacts={**contacts, actor.actor_uuid: landing_contact} if landing_contact is not None else contacts,
                activated_conditions=activated_conditions)
            if group.complete_ms > 0:
                states.append((elapsed, prior))
                reactions.append(MotionReaction(group, landing_contact, None, elapsed, elapsed + group.complete_ms))
                elapsed += group.complete_ms
            else:
                contact_media.extend(replace(cue, start_ms=elapsed+cue.start_ms) for cue in group.contact_media)
    # Later movement within the same native action starts from the completed
    # incoming jump. Its own retained Steps own subsequent travel and reactions.
    for event in lineage.events:
        if (not isinstance(event.fact, MovementFact)
                or event.parent_lineage != lineage.root.lineage_uuid):
            continue
        prior = _before_event(target, lineage, event)
        held = _visible_contact(prior, jump.source_entity_uuid, data, facing)
        group = bind_choreography(prior, lineage_branch(lineage, event), data,
            contacts={**contacts, actor.actor_uuid: held} if held is not None else contacts,
            activated_conditions=activated_conditions)
        if held is not None and group.complete_ms > 0:
            reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms))
            elapsed += group.complete_ms
    states.append((elapsed, final))
    transitions = merge_world_transitions(world_transitions(target, states), launch_transitions,
        tuple(replace(change, start_ms=change.start_ms + reaction.start_ms)
              for reaction in reactions for change in reaction.choreography.world_transitions))
    return MotionTimeline(launch, legs, context.jumpClip, 1, arc, elapsed,
                          tuple(reactions), settled, target, target.actors[jump.source_entity_uuid],
                          settled_lift_px=settled.body_lift_px if settled is not None else 0, body_loops=False,
                          states=tuple(states), world_transitions=transitions,
                          residue_reveals=tuple(replace(change,
                              start_ms=change.start_ms + reaction.start_ms,
                              end_ms=change.end_ms + reaction.start_ms)
                              for reaction in reactions for change in reaction.choreography.residue_reveals),
                          contact_media=tuple(contact_media))


def _visible_contact(state: PlayerState, actor_uuid: UUID, data: AnimationData,
                     facing: Facing8 = "S") -> ActorContact | None:
    actor = state.actors.get(actor_uuid)
    return actor_contact(state, actor, data, facing) if actor is not None and actor_is_visible(state, actor) else None


def bind_motion(target: PlayerState, lineage: PlayerLineage,
                data: AnimationData, *, contacts: Mapping[str, ActorContact] | None = None,
                activated_conditions: frozenset[UUID] = frozenset()) -> MotionTimeline | None:
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
        return _bind_jump(target, lineage, root, steps, data, actor, contacts, activated_conditions)
    reaction_context = data.movement_reaction_context
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    contact_media: list[StationaryMediaCue] = []
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
            group = bind_choreography(working, branch, data, contacts=overrides,
                activated_conditions=activated_conditions)
            if group.complete_ms > 0:
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
                    elapsed + group.complete_ms, held.body_lift_px if held is not None else 0, label))
                elapsed += group.complete_ms
                isolated_point = False
                body_start = elapsed
            else:
                contact_media.extend(replace(cue, start_ms=elapsed+cue.start_ms) for cue in group.contact_media)
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
        speed_scale = ((step.resolved_speed_feet/data.movement_reference_speed_feet)
                       if step.resolved_speed_feet is not None and step.resolved_speed_feet > 0 else 1)
        duration = context.walkStepDurationMs * distance / speed_scale
        if not uninterrupted:
            body_start = elapsed
        elif legs:
            previous = legs[-1]
            phase = (previous.end_ms-previous.body_start_ms)*previous.speed_scale
            body_start = elapsed-phase/speed_scale
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
                                  elapsed, lead_end, body_start, curve_to=fraction, initial_lift_px=initial_lift,
                                  speed_scale=speed_scale))
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
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held},
                    activated_conditions=activated_conditions)
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
                                  initial_lift_px=initial_lift, speed_scale=speed_scale))
            elapsed += duration
            # The committed edge owns departure and arrival consequences.
            # Both use the same lineage compositor, including an empty discharge.
            for entry in branch.events:
                if (not isinstance(entry.fact, SpatialFact)
                        or entry.fact.change_type not in (SpatialChangeType.ENTITY_LEFT, SpatialChangeType.ENTITY_ENTERED)
                        or entry.parent_lineage != node.lineage_uuid):
                    continue
                entered = lineage_branch(lineage, entry)
                if not (any(isinstance(row.fact, (DamageFact, ConditionChangeFact, SpatialEffectStateFact, MechanismActivationFact, PortalTransferFact,
                                                AttackFact, SpellFact)) for row in entered.events)
                        or ground_contact_is_authored(working, entry.fact, data)):
                    continue
                held = replace(leg_actor, grid=end, elevation_steps=end_height,
                               facing=facing_for_delta(delta, data), body_lift_px=0)
                group = bind_choreography(working, entered, data,
                    contacts={**contacts, actor.actor_uuid: held}, activated_conditions=activated_conditions)
                if group.complete_ms > 0:
                    reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms))
                    elapsed += group.complete_ms
                    body_start = elapsed
                else:
                    contact_media.extend(replace(cue, start_ms=elapsed+cue.start_ms) for cue in group.contact_media)
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
                              for reaction in reactions for change in reaction.choreography.residue_reveals),
                          contact_media=tuple(contact_media))


def motion_leg_contact(actor: ActorContact, leg: MotionLeg, data: AnimationData,
                       elapsed_ms: float) -> ActorContact:
    """One world trajectory for the body and its registered attached media."""
    progress = min(1.0, max(0.0, (elapsed_ms-leg.start_ms)/(leg.end_ms-leg.start_ms)))
    delta = leg.end[0]-leg.start[0], leg.end[1]-leg.start[1]
    curve = leg.curve_from+(leg.curve_to-leg.curve_from)*progress
    lift = 4*leg.arc_height_px*curve*(1-curve)+leg.initial_lift_px*(1-curve)
    return replace(actor, grid=(leg.start[0]+delta[0]*progress, leg.start[1]+delta[1]*progress),
        facing=facing_for_delta(delta, data),
        elevation_steps=leg.start_height+(leg.end_height-leg.start_height)*progress, body_lift_px=lift)


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
        if contact is None:
            # An unseen mover can operate a visible fixture. Its permitted
            # descendants play without fabricating the mover's body or path.
            return MotionSample(None, None, 0, False, active.choreography,
                                elapsed - active.start_ms, tuple(vitals.values()), displayed, active_sample)
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
    contact = motion_leg_contact(timeline.actor, leg, data, elapsed)
    facing, lift = contact.facing, contact.body_lift_px
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
        frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed * leg.speed_scale,
                           metadata.frames, loop=True)
    return MotionSample(contact, BodySample(contact.actor_uuid, selected, frame, facing),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)
