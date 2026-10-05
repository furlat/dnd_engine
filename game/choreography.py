"""Compose retained action subtrees at the original authored child anchors.

This owns no queue or clock. A movement edge and a standalone action both ask
for the same passive child group, then sample it using their historical clock.
Technical event nodes preserve ancestry without becoming extra animations.
"""

from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, CompiledTimingReference, PresentationDependencies, TimingMeasurement, TimingReason, record_timing, translate_timing_evidence
from game.player_reduction import index_player_lineage
from dataclasses import dataclass, replace
from math import hypot
from typing import Iterator, Literal, Mapping, cast
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.dice import AttackOutcome
from dnd.types.event_facts import EventType, MovementTrajectory, SpatialChangeType
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.world import MovementMode, OccupancyLayer
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH
from game.connector_motion import passage_point
from game.animation import (
    DamageTiming, ActorContact, ObjectContact, BodySample, BodyTransition, CastSample, VitalsSample, body_rig, body_clip, body_frame,
    sample_cast, sample_damage_body, sample_equipment, facing_for_delta, sample_idle_body, resolve_damage,
    media_track_duration, actor_rest_pose, compile_life_body, sample_body_transition,
    body_context, resolve_body_context, context_duration, context_frame, sample_context_body, death_body_context,
    airborne_weight, resolve_child_attack_palette,
)
from game.animation_types import (AnimationData, Facing8, LifecycleFeedback, StudioCondition,
                                  BodyContext, MovementBodyQualifier, MovementRecovery, RoleDefault)
from game.residue_media import ResidueReveal
from game.mechanism_projectile import (MechanismProjectileCue, mechanism_projectile_duration,
    mechanism_projectile_target)
from game.animation_types import ParticleMediaAsset
from game.action_media import ActionStripCue, ActionStripSample, bind_action_strips, sample_action_strip
from game.attack import BoundAttack, AttackSample, bind_attack, sample_attack
from game.body_action import BodyActionCue, bind_body_action, join_body_action, sample_body_action, intervention_subjects
from game.body_hop import BodyHopCue, bind_save_hop, sample_body_hop
from game.portal_animation import (PortalTransferCue, bind_portal_transfer,
    portal_departure_contact, portal_arrival_contact, portal_actor_hidden, portal_body)
from game.portal_art import PortalArt
from game.combat import BoundCast, BoundEquipment, actor_contact, actor_is_visible, bind_cast, bind_equipment
from game.condition_animation import (ConditionTimeline, ConditionSample, compile_condition, sample_condition,
                                      bind_condition_body, sample_condition_body, resolve_condition_appearance,
                                      ConditionResponseCue, bind_event_condition_response, bind_received_damage_responses)
from game.condition_reaction import bind_condition_interception_media, bind_condition_reaction_bodies
from game.interruption import (ReactionMediaCue, bind_reaction_media, bind_cancellation_media, interruption_rule,
    interruption_ms, interrupt_body, interrupt_delivery, interrupt_sample)
from game.damage import DamageCue, bind_damage, sample_damage
from game.forced_movement import (
    ForcedMovementCue, ShoveCue, bind_forced_movement, bind_shove,
    forced_contact, sample_forced_body, sample_shove,
)
from game.player_facts import (
    ActionFact, AreaReachFact, AttackFact, ConditionChangeFact, ItemEffectChangeFact, DamageFact, DeathSaveFact, EquipmentFact, ForcedMovementFact,
    HealFact, ItemChargeFact, LifeFact, MovementFact, ObjectDamageFact, ObjectDestroyedFact, PlayerObject, PlayerActor, PlayerFact, PlayerLineage, PlayerNode, PlayerObservation, PlayerState,
    SensoryFact, ShoveFact, SpellFact, SpatialEffectStateFact, MechanismActivationFact, PortalTransferFact, SavingThrowFact, SpatialFact, StepFact, TemporaryHitPointsFact, TurnFact, FactionFact, VersionRow,
)
from game.world_animation import (
    ObjectDustContact, DestructionContact, WorldTransition, world_transitions, world_transition_end, merge_world_transitions, surface_reveal_delay,
    bind_spatial_media_motion,
)
from game.device_art import device_bank
from game.environment_art import load_environment_art
from game.environment_animation import remnant_bank
from game.entity_lifecycle import EntityLifecycleCue, bind_entity_lifecycle, lifecycle_phase
from game.player_reduction import copy_target, lineage_branch, reduce_lineage, reduce_nodes, observe_actors, stage_actors, stage_lineage, state_before_event as _before_event
from game.stationary_media import StationaryMediaCue
from game.finite_material import BodyMaterialCue
from game.spatial_response import SpatialResponseCue, damage_spatial_owner, bind_spatial_response
from game.spatial_contact_media import bind_spatial_contacts, ground_contact_is_authored, bind_suppression_media, damage_sweep_recipe
from game.construction_transitions import construction_duration, construction_media_limitation
from game.directed_contacts import directed_object_contacts, ordinary_object_contact
from game.world_animation import ConstructionCollapse
from game.construction_transitions import construction_creation_transitions
from game.wall_profile import wall_media_limitation


def _has_standalone_state(fact: PlayerFact | None, effect_ms: float | None) -> bool:
    return (isinstance(fact, (TemporaryHitPointsFact, FactionFact, ItemEffectChangeFact))
            or isinstance(fact, SpatialFact) and effect_ms is None
                and (fact.terminal_departure or fact.object_uuid is not None))


def _child_timing(fact: PlayerFact | None, at: float, parent_end: float,
                  injury_at: float | None, state_at: float | None,
                  portal: PortalTransferCue | None, sequence_at: float | None,
                  parent_uuid: UUID, displacement: ForcedMovementCue | None, *,
                  evidence: list[TimingEvidence] | None = None, child_uuid: UUID | None = None,
                  sequence_uuid: UUID | None = None) -> tuple[float, float | None]:
    """Existing contact/arrival anchors, with ordered generic-action groups."""
    effect_at = (injury_at if injury_at is not None and (
        isinstance(fact, TemporaryHitPointsFact) or isinstance(fact, DamageFact) and fact.stage == "applied")
        else state_at)
    start = max(at, parent_end) if isinstance(fact, MovementFact) else at
    start_source = TimingOperand(TimingReference('event', parent_uuid, 'effect'), at)
    if evidence is not None and child_uuid is not None:
        start_source = record_timing(evidence, TimingReference('event', child_uuid, 'start'), 'child_start',
            (start_source, TimingOperand(TimingReference('event', parent_uuid, 'complete'), parent_end))
                if isinstance(fact, MovementFact) else (start_source,), start,
            'maximum' if isinstance(fact, MovementFact) else 'offset')
        if effect_at is not None:
            record_timing(evidence, TimingReference('event', child_uuid, 'effect'), 'child_effect',
                (TimingOperand(TimingReference('event', parent_uuid, 'hp' if injury_at is not None and (
                    isinstance(fact, TemporaryHitPointsFact) or isinstance(fact, DamageFact) and fact.stage == 'applied')
                    else 'commit'), effect_at),), effect_at)
    if displacement is not None and displacement.event_uuid == parent_uuid:
        start = displacement.travel_end_ms
        effect_at = start
        if evidence is not None and child_uuid is not None:
            start_source = record_timing(evidence, TimingReference('event', child_uuid, 'start'), 'child_start',
                (TimingOperand(TimingReference('event', displacement.event_uuid, 'contact'), start),), start)
    if portal is not None and portal.arrival is not None and not isinstance(fact, (SpatialFact, SensoryFact)):
        start = max(start, portal.settled_ms)
        effect_at = start
        if evidence is not None and child_uuid is not None:
            start_source = record_timing(evidence, TimingReference('event', child_uuid, 'start'), 'child_start',
                (start_source, TimingOperand(TimingReference('event', portal.event_uuid, 'settled'), portal.settled_ms)),
                start, 'maximum')
    if sequence_at is not None:
        start = max(start, sequence_at)
        effect_at = start
        if evidence is not None and child_uuid is not None:
            start_source = record_timing(evidence, TimingReference('event', child_uuid, 'start'), 'child_start',
                (start_source, TimingOperand(TimingReference('event', sequence_uuid or parent_uuid,
                    'complete' if sequence_uuid is not None else 'effect'), sequence_at)), start, 'maximum')
    if evidence is not None and child_uuid is not None and (
            displacement is not None and displacement.event_uuid == parent_uuid
            or portal is not None and portal.arrival is not None and not isinstance(fact, (SpatialFact, SensoryFact))
            or sequence_at is not None):
        record_timing(evidence, TimingReference('event', child_uuid, 'effect'), 'child_effect',
            (start_source,), effect_at if effect_at is not None else start)
    return start, effect_at


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
    contact: ActorContact | None = None
    body_context: BodyContext | None = None
    end_ms: float | None = None
    data: AnimationData | None = None


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
class StateCommitEvidence:
    """Sources actually folded at one displayed-state boundary; not another reducer."""

    at_ms: float
    nodes: tuple[PlayerNode, ...]
    observation_event_uuids: tuple[UUID, ...]
    world_event_uuids: tuple[UUID, ...]
    version_rows: tuple[VersionRow, ...]


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
    entity_lifecycle: tuple[EntityLifecycleCue, ...] = ()
    finite_materials: tuple[BodyMaterialCue, ...] = ()
    spatial_responses: tuple[SpatialResponseCue, ...] = ()
    state_commits: tuple[StateCommitEvidence, ...] = ()
    timing_evidence: tuple[TimingEvidence, ...] = ()


def bound_action_dependencies(group: BoundChoreography) -> tuple[PresentationDependencies, ...]:
    """Retain compiler records without retaining a drawable action/group tree."""
    return (*tuple(PresentationDependencies(action.event_uuid, action.start_ms,
        action.bound.timeline.timing_evidence, 'attack' if isinstance(action.bound, BoundAttack) else 'cast')
        for action in group.nodes if action.bound.timeline.timing_evidence),
        *tuple(PresentationDependencies(cue.event_uuid, 0., cue.timing_evidence, 'body')
            for cue in group.body_actions if cue.timing_evidence),
        *tuple(PresentationDependencies(cue.event_uuid, cue.start_ms, cue.bound.timeline.timing_evidence, 'equipment')
            for cue in group.equipment if cue.bound.timeline.timing_evidence),
        *tuple(PresentationDependencies(cue.event_uuid, 0., cue.timing_evidence, 'condition_transition')
            for cue in group.conditions if cue.timing_evidence),
        *tuple(PresentationDependencies(cue.event_uuid, 0., cue.timing_evidence, 'damage')
            for cue in group.damage if cue.timing_evidence),
        *tuple(PresentationDependencies(cue.event_uuid, 0., cue.timing_evidence, 'lifecycle')
            for cue in group.entity_lifecycle if cue.timing_evidence))


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
    entity_lifecycle: tuple[tuple[EntityLifecycleCue, float], ...] = ()


def _bound_damage_timing(event: PlayerNode, owner: ActionNode) -> tuple[DamageTiming | None, ActorContact | None]:
    """Read the existing compiled damage placement, adding only its parent offset."""
    if isinstance(owner.bound, BoundAttack):
        timing = owner.bound.timeline.damage_timing
        target = owner.bound.timeline.target
        contact = target if isinstance(target, ActorContact) else None
        return ((DamageTiming(timing.start_ms + owner.start_ms, timing.end_ms + owner.start_ms,
                    timing.hp_ms + owner.start_ms, timing.flash_ms + owner.start_ms,
                    timing.number_ms + owner.start_ms, timing.life_body) if timing is not None else None), contact)
    delivery = next((row for row in owner.bound.timeline.applications
        if row.source.resolution_ref == event.resolution_ref), None)
    if (delivery is None or not isinstance(delivery.source.target, ActorContact)
            or delivery.damage_start_ms is None or delivery.damage_end_ms is None
            or delivery.hp_ms is None or delivery.flash_ms is None or delivery.number_ms is None):
        return None, None
    return (DamageTiming(owner.start_ms + delivery.damage_start_ms,
        owner.start_ms + delivery.damage_end_ms, owner.start_ms + delivery.hp_ms,
        owner.start_ms + delivery.flash_ms, owner.start_ms + delivery.number_ms, delivery.life_body), delivery.source.target)


def _observed_commit(fact: PlayerFact | None, source_lineages: Mapping[UUID, UUID],
                     milestones: Mapping[UUID, float]) -> float | None:
    if not isinstance(fact, SensoryFact) or not fact.observed_changes:
        return None
    sources = {source_lineages[row.source_event_uuid] for row in fact.observed_changes
               if row.source_event_uuid in source_lineages}
    dates = [milestones[source] for source in sources if source in milestones]
    return max(dates) if dates and len(dates) == len(sources) else None


def _destruction_transition(before: PlayerState, lineage: PlayerLineage, event: PlayerNode,
                            fact: ObjectDestroyedFact, data: AnimationData,
                            facings: Mapping[str, Facing8], at: float,
                            collapse_contacts: tuple[tuple[float,float,float], ...] = (),
                            ) -> tuple[WorldTransition | None, float | None, str | None]:
    """Bind the existing fracture and its authored geometry-clear milestone."""
    prior = _before_event(before, lineage, event)
    after = reduce_lineage(prior, lineage_branch(lineage, event))
    body_uuid = fact.replacement_uuid or fact.object_uuid
    body = after.objects.get(body_uuid)
    art = data.devices.get(fact.item_id)
    construction = data.construction_media.get(fact.item_id)
    original = (PlayerObject(item=fact.previous_item, placement=fact.placement)
        if fact.previous_item is not None else prior.objects.get(fact.object_uuid))
    if fact.remains_disposition is RemainsDisposition.DISINTEGRATED:
        if construction is not None and construction.surface is not None and construction.surface.material == "force_membrane" and original is not None:
            return WorldTransition(fact.object_uuid, "destruction", None, None, at,
                duration_ms=construction.surface.destructionMs,
                construction_collapse=ConstructionCollapse(original, collapse_contacts)), None, None
        dust = data.death_context.silhouetteDust
        if dust is None or original is None:
            return None, None, "Disintegration requires its witnessed object silhouette and authored dust"
        return WorldTransition(fact.object_uuid, "destruction", None, None, at,
            duration_ms=dust.duration_ms, object_dust=ObjectDustContact(original, fact.affected_volume,
                fact.resulting_placement is not None, event.uuid.int & 0xffffffff)), None, None
    if construction is not None and original is not None:
        limitation = construction_media_limitation(original, construction)
        if limitation is not None:
            return None, None, limitation
        return WorldTransition(fact.object_uuid, "destruction", None, None, at,
            duration_ms=construction_duration(data, construction, "destruction")), None, None
    if body is None:
        return None, None, None
    if art is not None and art.destruction is not None:
        facing = facings.get(str(fact.object_uuid))
        if facing is None:
            facing = art.rows[art.rows.index(
                fact.placement.orientation.value.upper() if fact.placement.orientation else "E")]
        destruction = DestructionContact(fact.item_id, fact.placement.position,
            fact.placement.base_height_steps, facing, device_bank(art).degrees,
            body_uuid, art.destruction.frame_count * 1000 / art.destruction.fps)
        return WorldTransition(fact.object_uuid, "destruction", None, None, at, destruction), None, None
    environment = load_environment_art()
    if (fact.item_id not in environment.doors and fact.item_id not in environment.traps
            and fact.item_id not in environment.props):
        return None, None, f"Missing object destruction media: {fact.item_id}"
    bank = remnant_bank(environment, body.item.item_id, fact.remnant_state,
                        outcome=fact.destruction_outcome)
    if bank is None:
        return None, None, f"Missing environment destruction entry: {fact.item_id}"
    direction = fact.placement.boundary_direction or fact.placement.orientation
    facing = cast(Facing8, {"east": "E", "south": "S", "west": "W", "north": "N"}[
        direction.value if direction is not None else "east"])
    destruction = DestructionContact(fact.item_id, fact.placement.position,
        fact.placement.base_height_steps, facing, 0, body_uuid,
        bank.duration_ms, bank_id=bank.identity,
        incorporated_items=fact.remnant_state.intact_supported_items if fact.remnant_state is not None else ())
    clearance = at + bank.frame_times_ms[bank.state_change_frame] if bank.state_change_frame else None
    return WorldTransition(fact.object_uuid, "destruction", None, None, at, destruction), clearance, None


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
    causal_index = index_player_lineage(lineage)
    by_lineage = causal_index.by_lineage
    destruction_owners: dict[UUID, UUID] = {}
    destruction_state_times: dict[UUID, float] = {}
    timing_evidence: list[TimingEvidence] = []

    def index_destruction(event: PlayerNode, owner: UUID | None = None) -> None:
        if isinstance(event.fact, ObjectDestroyedFact):
            owner = event.uuid
        if owner is not None:
            destruction_owners[event.lineage_uuid] = owner
        for identity in event.children_lineages:
            index_destruction(by_lineage[identity], owner)

    index_destruction(lineage.root)
    observations: list[tuple[float, PlayerObservation]] = []
    arrival_observations: dict[UUID, float] = {}
    arrival_snapshots: dict[tuple[UUID, UUID], tuple[UUID, float]] = {}
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
    memberships = {identity: actor.conditions for identity, actor in before.actors.items()}
    conditions: list[ConditionTimeline] = []
    joined_actors: set[UUID] = set()
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
    decorative_contact_media: list[StationaryMediaCue] = []
    finite_materials: list[BodyMaterialCue] = []
    spatial_responses: list[SpatialResponseCue] = []
    entity_lifecycle: list[EntityLifecycleCue] = []
    damage_sweep_starts: dict[UUID, float] = {}
    residue_reveals: list[ResidueReveal] = []
    actor_order: list[tuple[UUID, int, bool]] = []
    gaps: list[tuple[UUID, str]] = []
    state_nodes: list[tuple[float, PlayerNode]] = []
    result_placements: dict[UUID, DamageTiming] = {}

    def preceding_damage_commit(event: PlayerNode, target_uuid: UUID) -> float:
        """A later native consequence cannot expose HP from an unplayed result."""
        sources = tuple(TimingOperand(TimingReference('event', identity, 'hp'), timing.hp_ms)
                    for identity, timing in result_placements.items()
                    if causal_index.source_order[identity] < causal_index.source_order[event.uuid]
                    and isinstance(result := causal_index.by_uuid[identity].fact, DamageFact)
                    and result.stage == "applied" and result.target_entity_uuid == target_uuid)
        floor = max((source.at_ms for source in sources), default=0.)
        record_timing(timing_evidence, TimingReference('event', event.uuid, 'prior_hp_floor'), 'hp_callback',
            sources or (TimingOperand(TimingReference('event', lineage.root.uuid, 'group_origin'), 0.),), floor, 'maximum')
        return floor
    commit_milestones: dict[UUID, float] = {}
    turn_starts: list[tuple[float, UUID]] = []
    recorded_transitions: list[WorldTransition] = []
    external_reactions: list[BodyActionCue] = []
    reaction_media: list[ReactionMediaCue] = []
    condition_responses: dict[tuple[UUID, UUID], ConditionResponseCue] = {}
    world_events = {update.event_uuid: update for update in lineage.world_updates}
    spatial_effects = {identity: effect
        for identity, effect in (before.senses.spatial_effects.items() if before.senses is not None else ())}
    spatial_effects.update({identity: effect
        for event in lineage.events if isinstance(event.fact, SensoryFact)
        for identity, effect in event.fact.spatial_effects_changed.items()})
    spatial_contents = {identity: effect.content_ref.content_id for identity, effect in spatial_effects.items()}
    formation_starts: dict[UUID, float] = {}
    section_starts: dict[UUID, float] = {}
    # Creation's applied damage can precede its completion/observation in native
    # ancestry. Bind only shell facts actually disclosed in this same lineage.
    created_effects = {event.fact.spatial_effect_uuid: tuple(
        sensory.fact.spatial_effects_changed[event.fact.spatial_effect_uuid]
        for sensory in lineage.events if isinstance(sensory.fact, SensoryFact)
        and not sensory.canceled and event.fact.spatial_effect_uuid in sensory.fact.spatial_effects_changed)
        for event in lineage.events if isinstance(event.fact, SpatialEffectStateFact)
        and event.fact.operation is SpatialEffectChangeOperation.CREATED and not event.canceled}

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
        record_timing(timing_evidence, TimingReference('event', event.uuid, 'effect'),
            'reaction_alignment', (TimingOperand(TimingReference('event', event.uuid, 'effect'), effect_ms),
                *(TimingOperand(TimingReference('event', cue.event_uuid, 'effect'), cue.effect_ms) for cue in cues)),
            effect_ms + delay, 'maximum')
        for cue in cues:
            offset = effect_ms + delay - cue.effect_ms
            external_reactions.append(replace(cue, start_ms=offset, effect_ms=cue.effect_ms + offset,
                body_end_ms=cue.body_end_ms + offset, join_ms=cue.join_ms + offset,
                complete_ms=cue.complete_ms + offset,
                timing_evidence=translate_timing_evidence(cue.timing_evidence, offset)))
            reaction = next(root.root.fact for root in reactions if root.root.uuid == cue.event_uuid)
            assert isinstance(reaction, ActionFact) and reaction.reaction is not None
            media = data.interruptions.reactions.get(reaction.behavior_id or "")
            if media is not None and incoming is not None:
                reaction_media.append(bind_reaction_media(cue.event_uuid, event.uuid, incoming,
                    media, reaction.reaction.succeeded, effect_ms + delay, cutoff_ms,
                    reaction_id=reaction.behavior_id,
                    outcome_code=event.cancellation.outcome_code if event.cancellation is not None else None))
        return delay

    by_uuid = {event.uuid: event for event in lineage.events}

    def owned_by(identity: UUID, parent: UUID) -> bool:
        event = by_uuid[identity]
        while event.parent_lineage is not None and event.parent_lineage in by_lineage:
            event = by_lineage[event.parent_lineage]
            if event.uuid == parent:
                return True
        return False

    def finish_conditions(root: UUID | None = None) -> float:
        selected = [row for row in pending_conditions
                    if root is None or row[1].uuid == root or owned_by(row[1].uuid, root)]
        pending_conditions[:] = [row for row in pending_conditions if row not in selected]
        end = 0.
        for at, event, override in sorted(selected, key=lambda row: (row[0], order[row[1].uuid])):
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
            end = max(end, transition.complete_ms)
            gaps.extend((event.uuid, detail) for detail in transition.unsupported)

        return end

    def join_actor_subtrees(root: UUID | None = None) -> float:
        end = 0.
        for event_uuid, index, is_body in reversed(actor_order):
            if event_uuid in joined_actors or root is not None and event_uuid != root and not owned_by(event_uuid, root):
                continue
            joined_actors.add(event_uuid)
            child_inputs = [TimingOperand(TimingReference('event', condition.event_uuid, 'complete'), condition.complete_ms)
                          for condition in conditions if owned_by(condition.event_uuid, event_uuid)]
            child_inputs.extend(TimingOperand(TimingReference('event', child.event_uuid, 'complete'), child.start_ms + child.bound.timeline.complete_ms)
                              for child in nodes if owned_by(child.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', child.event_uuid, 'complete'), child.complete_ms)
                              for child in body_actions if owned_by(child.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event.uuid, 'complete'), cue.death_end_ms)
                              for cue in lifecycle if cue.death_end_ms is not None and owned_by(cue.event.uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event.uuid, 'body_end'), cue.body_end_ms)
                              for cue in lifecycle if cue.body_end_ms is not None and owned_by(cue.event.uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.start_ms + cue.bound.timeline.complete_ms)
                              for cue in equipment if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.complete_ms)
                              for cue in forced_movement if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.timing.end_ms)
                              for cue in damage if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event.uuid, 'complete'), cue.end_ms)
                              for cue in healing if cue.end_ms is not None and owned_by(cue.event.uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.start_ms + cue.timeline.complete_ms)
                              for cue in movements if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.end_ms)
                              for cue in strips if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.end_ms)
                              for cue in body_hops if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'complete'), cue.end_ms)
                              for cue in condition_responses.values() if owned_by(cue.event_uuid, event_uuid))
            child_inputs.extend(TimingOperand(TimingReference('event', cue.event_uuid, 'body_end'), cue.body_end_ms)
                              for cue in entity_lifecycle if owned_by(cue.event_uuid, event_uuid))
            child_ends = [source.at_ms for source in child_inputs]
            if not child_ends:
                continue
            if is_body:
                body_actions[index] = join_body_action(body_actions[index], data, max(child_ends), child_evidence=tuple(child_inputs))
                end = max(end, body_actions[index].complete_ms)
                continue
            node = nodes[index]
            child_end = max(child_ends) - node.start_ms
            timeline = node.bound.timeline
            if isinstance(node.bound, BoundCast):
                original = node.bound.timeline
                shift = max(0, child_end - original.recovery_start_ms)
                evidence = list(original.timing_evidence)
                recovery_ref = CompiledTimingReference('cast', original.source.root_event_uuid, 'recovery')
                prior = record_timing(evidence, recovery_ref, 'subtree_join',
                    (TimingOperand(recovery_ref, original.recovery_start_ms),), original.recovery_start_ms)
                joined = record_timing(evidence, recovery_ref, 'subtree_join', (prior,
                    *(replace(source, at_ms=source.at_ms-node.start_ms) for source in child_inputs)),
                    original.recovery_start_ms + shift, 'maximum')
                assert prior.producer_index is not None and joined.producer_index is not None
                complete_ref = replace(recovery_ref, anchor='complete')
                record_timing(evidence, complete_ref, 'subtree_join',
                    (TimingOperand(complete_ref, original.complete_ms, offset_ms=shift,
                        offset_producers=(joined.producer_index, prior.producer_index)),), original.complete_ms + shift)
                timeline = replace(original, timing_evidence=tuple(evidence), recovery_start_ms=original.recovery_start_ms + shift,
                    complete_ms=original.complete_ms + shift,
                    anchors=tuple(replace(anchor, at_ms=anchor.at_ms + shift)
                                  if anchor.name in ("recover", "complete") else anchor for anchor in original.anchors))
                nodes[index] = replace(node, bound=replace(node.bound, timeline=timeline))
            else:
                evidence = list(node.bound.timeline.timing_evidence)
                complete_ref = TimingReference('attack', node.event_uuid, 'complete')
                record_timing(evidence, complete_ref, 'subtree_join',
                    (TimingOperand(complete_ref, node.bound.timeline.complete_ms),
                     *(replace(source, at_ms=source.at_ms-node.start_ms) for source in child_inputs)),
                    max(node.bound.timeline.complete_ms, child_end), 'maximum')
                timeline = replace(node.bound.timeline, complete_ms=max(node.bound.timeline.complete_ms, child_end),
                    timing_evidence=tuple(evidence))
                nodes[index] = replace(node, bound=replace(node.bound, timeline=timeline))
            end = max(end, node.start_ms + timeline.complete_ms)
        return end

    def bind_lifecycle(event: PlayerNode, at: float,
                       placed_contacts: Mapping[str, ActorContact]) -> EntityLifecycleCue | None:
        fact = event.fact
        phase = lifecycle_phase(fact)
        if phase is not None and isinstance(fact, (SpatialFact, FactionFact)) and fact.entity_uuid is not None:
            prior = _before_event(before, lineage, event)
            witnessed = (reduce_lineage(prior, lineage_branch(lineage, event))
                         if phase == "arrival" else prior)
            parent = by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else None
            if (phase == "departure" and parent is not None and isinstance(parent.fact, ConditionChangeFact)
                    and parent.fact.event_type is EventType.CONDITION_REMOVAL
                    and parent.fact.target_entity_uuid == fact.entity_uuid):
                # Terminal removal owns its condition/item cleanup children.
                # Retain the permitted appearance at that exact boundary.
                witnessed = _before_event(before, lineage, parent)
            actor = witnessed.actors.get(fact.entity_uuid)
            if actor is not None and actor_is_visible(witnessed, actor):
                contact = actor_contact(witnessed, actor, data, (facings or {}).get(str(actor.uuid), "S"))
                placed = placed_contacts.get(contact.actor_uuid)
                if placed is not None:
                    contact = replace(contact, grid=placed.grid, elevation_steps=placed.elevation_steps,
                                      body_lift_px=placed.body_lift_px, facing=placed.facing)
                cue_at = at
                if phase == "departure":
                    # Finish this actor's received injury/death before its terminal
                    # body fade. The native removal itself is already committed.
                    departure_sources = (TimingOperand(TimingReference('event', event.uuid, 'admission'), cue_at),
                        *(TimingOperand(TimingReference('event', identity, 'complete'), timing.end_ms)
                          for identity, timing in result_placements.items() if order[identity] < order[event.uuid]
                          and isinstance(result := by_uuid[identity].fact, DamageFact)
                          and result.target_entity_uuid == fact.entity_uuid),
                        *(TimingOperand(TimingReference('event', row.event.uuid, 'body_end'),
                            row.body_end_ms or row.death_end_ms or row.start_ms) for row in lifecycle
                          if row.contact.actor_uuid == contact.actor_uuid))
                    cue_at = max(source.at_ms for source in departure_sources)
                    record_timing(timing_evidence, TimingReference('event', event.uuid, 'start'),
                        'lifetime_removal', departure_sources, cue_at, 'maximum')
                bound_lifecycle = bind_entity_lifecycle(event.uuid, phase, actor, contact, data, cue_at)
                if bound_lifecycle is not None:
                    cue, media = bound_lifecycle
                    entity_lifecycle.append(cue)
                    contact_media.extend(media)
                    return cue
        return None

    def bind_standalone_damage(event: PlayerNode, at: float,
                               placed_contacts: Mapping[str, ActorContact]) -> tuple[DamageCue | None, float]:
        fact = event.fact
        assert isinstance(fact, DamageFact) and fact.stage == "taken"
        standalone_damage = None
        end = at
        try:
            if fact.target_entity_uuid is not None:
                original_at = at
                at = max(at, preceding_damage_commit(event, fact.target_entity_uuid))
                prior_hp = timing_evidence[-1]
                record_timing(timing_evidence, TimingReference('event', event.uuid, 'start'), 'damage_start',
                    (TimingOperand(TimingReference('event', event.uuid, 'admission'), original_at),
                     TimingOperand(prior_hp.target, prior_hp.at_ms, prior_hp.index)), at, 'maximum')
            branch = lineage_branch(lineage, event)
            prior = _before_event(before, lineage, event)
            delay = 0.
            delay_field = 'damage.immediate'
            delay_owner = None
            admitted = next((packet for packet in branch.events
                if isinstance(packet.fact, DamageFact) and packet.fact.stage == "applied"
                and packet.parent_lineage == event.lineage_uuid and not packet.canceled), event)
            admitted_fact = admitted.fact
            assert isinstance(admitted_fact, DamageFact)
            spatial_owner = damage_spatial_owner(prior, admitted_fact, created_effects)
            spatial_binding = data.spatial_media.get(spatial_owner.content_ref.content_id) if spatial_owner is not None else None
            directed = spatial_binding.directedResponse if spatial_binding is not None else None
            recipient = prior.actors.get(admitted_fact.target_entity_uuid)
            if (directed is not None and spatial_owner is not None and recipient is not None
                    and actor_is_visible(prior, recipient) and admitted_fact.source_condition_uuid is not None):
                spatial_uuid = admitted_fact.source_condition_uuid
                response_sources = (TimingOperand(TimingReference('event', event.uuid, 'start'), at),
                    *(TimingOperand(TimingReference('event', cue.media.event_uuid, 'complete'), cue.media.end_ms)
                      for cue in spatial_responses if cue.owner_uuid == spatial_uuid))
                start = max(source.at_ms for source in response_sources)
                record_timing(timing_evidence, TimingReference('event', admitted.uuid, 'start'), 'damage_start',
                    response_sources, start, 'maximum')
                contact = placed_contacts.get(str(recipient.uuid)) or actor_contact(prior, recipient, data)
                admission = by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else event
                retired = any(isinstance(node.fact, SpatialEffectStateFact)
                    and node.fact.operation is SpatialEffectChangeOperation.REMOVED
                    and node.fact.spatial_effect_uuid == spatial_uuid and not node.canceled
                    and admission is not None and owned_by(node.uuid,admission.uuid) for node in lineage.events)
                response = bind_spatial_response(admitted.uuid, spatial_uuid, spatial_owner, contact,
                    directed, data, start, retired=retired)
                if response is not None:
                    spatial_responses.append(response)
                    delay = response.contact_ms-at
                    delay_field = 'spatial_response.contact_ms'
                    delay_owner = admitted.uuid
                    end = max(end, response.media.end_ms)
            for packet in branch.events:
                if (isinstance(packet.fact, DamageFact) and packet.fact.stage == "applied"
                        and packet.parent_lineage == event.lineage_uuid and not packet.canceled):
                    sweep = damage_sweep_recipe(prior, packet.fact, data, created_effects)
                    if sweep is not None:
                        delay = sweep.contactDelayMs
                        delay_field = 'damage_sweep.contactDelayMs'
                        delay_owner = packet.uuid
                        damage_sweep_starts[packet.uuid] = at
            record_timing(timing_evidence, TimingReference('event', event.uuid, 'contact'), 'contact',
                (TimingOperand(TimingReference('event', event.uuid, 'start'), at, offset_ms=delay,
                    authored_field=delay_field, contributor_event_uuid=delay_owner),), at + delay)
            standalone_damage = bind_damage(prior,
                branch, data, start_ms=at+delay, causal_index=causal_index,
                contact=placed_contacts.get(str(fact.target_entity_uuid)))
            if standalone_damage is not None:
                damage.append(standalone_damage)
                end = max(end, standalone_damage.timing.end_ms)
        except (ValueError, NotImplementedError) as error:
            gaps.append((event.uuid, str(error)))
        return standalone_damage, end

    def bind_life_transition(event: PlayerNode, fact: DeathSaveFact | LifeFact,
                             at: float, owner: ActionNode | None,
                             placed_contacts: Mapping[str, ActorContact]) -> float:
        """Bind one admitted life transition on its causal contact clock."""
        end = at
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
                        body = death_body_context(data, contact)
                        death_end = at if (contact.life_state is LifeState.DEAD
                                          or actor_rest_pose(data, contact) is not None) else (
                            at + context_duration(data, contact, body))
                        if death.hiddenSlots or death.media:
                            gaps.append((event.uuid, "Standalone death hiddenSlots/media are not bound"))
                    if not state_owned:
                        pose = resolve_condition_appearance(actor.conditions, data.condition_recipes).body_pose
                        life_body = compile_life_body(data, contact, fact.new_state, pose)
                        if life_body is not None:
                            body_end = at + life_body.frames * 1000 / life_body.fps
                if isinstance(fact, LifeFact) and fact.remains_disposition is RemainsDisposition.DISINTEGRATED:
                    dust = data.death_context.silhouetteDust
                    if dust is None:
                        raise ValueError("Disintegrated remains require authored silhouette dust")
                    prior_end = end
                    end = max(end, at + dust.duration_ms)
                    record_timing(timing_evidence, TimingReference('event', event.uuid, 'complete'), 'body_complete',
                        (TimingOperand(TimingReference('event', event.uuid, 'complete'), prior_end),
                         TimingOperand(TimingReference('event', event.uuid, 'start'), at,
                            offset_ms=dust.duration_ms, authored_field='death.silhouetteDust.duration_ms')), end, 'maximum')
                if death_end is not None:
                    record_timing(timing_evidence, TimingReference('event', event.uuid, 'body_end'), 'body_end',
                        (TimingOperand(TimingReference('event', event.uuid, 'start'), at,
                            offset_ms=death_end-at, authored_field='selected_death_body.duration'),), death_end)
                if body_end is not None:
                    record_timing(timing_evidence, TimingReference('event', event.uuid, 'body_end'), 'body_end',
                        (TimingOperand(TimingReference('event', event.uuid, 'start'), at,
                            offset_ms=body_end-at, authored_field='selected_life_body.frames/fps'),), body_end)
                lifecycle.append(LifecycleCue(event, at, contact, feedback, state_owned, death_end, data,
                                              life_body, body_end))
                prior_end = end
                end = max(end, death_end if death_end is not None else at,
                          body_end if body_end is not None else at)
                record_timing(timing_evidence, TimingReference('event', event.uuid, 'complete'), 'body_complete',
                    (TimingOperand(TimingReference('event', event.uuid, 'complete'), prior_end),
                     TimingOperand(TimingReference('event', event.uuid, 'body_end' if death_end is not None else 'start'), death_end if death_end is not None else at),
                     TimingOperand(TimingReference('event', event.uuid, 'body_end' if body_end is not None else 'start'), body_end if body_end is not None else at)), end, 'maximum')
            except (ValueError, NotImplementedError) as error:
                gaps.append((event.uuid, str(error)))
        return end

    def visit(event: PlayerNode, at: float, owner: ActionNode | None = None,
              override: StudioCondition | None = None,
              displacement: ForcedMovementCue | None = None,
              interaction_actor: UUID | None = None,
              state_at_effect: float | None = None,
              landed_contact: ActorContact | None = None) -> float:
        fact = event.fact
        if owner is not None:
            owner = next((node for node in nodes if node.event_uuid == owner.event_uuid), owner)
        if (isinstance(fact, ConditionChangeFact) and fact.consumed
                and owner is not None and isinstance(owner.bound, BoundCast)
                and str(fact.target_entity_uuid) == owner.bound.timeline.source.caster.actor_uuid):
            # A retained source effect is spent when released. Its removal and
            # light children precede the recipient's independent impact clock.
            at = state_at_effect = owner.start_ms + owner.bound.timeline.release_ms
        if isinstance(fact, AreaReachFact):
            # The native stage gives causality; the existing destruction art
            # supplies the moment the blocking shape has visibly cleared.
            reach_start = at
            at = max([at, *(destruction_state_times.get(by_lineage[identity].uuid, at)
                for identity in fact.prerequisite_destruction_lineages if identity in by_lineage)])
            record_timing(timing_evidence, TimingReference('event', event.uuid, 'admission'), 'area_reach',
                (TimingOperand(TimingReference('event', event.uuid, 'start'), reach_start),
                 *(TimingOperand(TimingReference('event', by_lineage[identity].uuid, 'clearance'),
                    destruction_state_times[by_lineage[identity].uuid])
                    for identity in fact.prerequisite_destruction_lineages if identity in by_lineage
                    and by_lineage[identity].uuid in destruction_state_times)), at, 'maximum')
            state_at_effect = at
            if owner is not None and isinstance(owner.bound, BoundCast):
                # Formation may occupy the already resolved initial footprint
                # before contact. Later reach still waits for real obstruction
                # clearance; no mechanical state/recipient date moves earlier.
                media_at = (owner.bound.timeline.release_ms
                    if fact.previous_reach_lineage_uuid is None and not fact.prerequisite_destruction_lineages
                    else at - owner.start_ms)
                updated = replace(owner, bound=replace(owner.bound, area_reach=(*owner.bound.area_reach,
                    (media_at, fact.newly_reached_positions))))
                nodes[nodes.index(owner)] = updated
                owner = updated
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
                            complete_ms=cue.complete_ms + delay,
                            timing_evidence=translate_timing_evidence(cue.timing_evidence, delay))
                        body_actions.append(cue)
                        end = cue.complete_ms
                    else:
                        attempt = (bind_attack(prior, branch, data, facings=facings, contacts=contacts)
                                   if isinstance(fact, AttackFact) else bind_cast(prior, branch, data,
                                       facings=facings, contacts=contacts))
                        if attempt is not None:
                            attempt = interrupt_delivery(attempt, rule,
                                outcome_code=event.cancellation.outcome_code if event.cancellation is not None else None)
                            at += join_reactions(event, at + attempt.timeline.complete_ms,
                                attempt if isinstance(attempt, BoundCast) else None, attempt.timeline.complete_ms)
                            nodes.append(ActionNode(event.uuid, at, attempt, interrupted=True))
                            end = at + attempt.timeline.complete_ms
                            if isinstance(attempt, BoundCast):
                                responses = bind_suppression_media(attempt, event.uuid, at,
                                    attempt.timeline.complete_ms)
                                contact_media.extend(bind_cancellation_media(attempt,event,end))
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
            arrival = dict(displacement.arrivals).get(event.uuid)
            if arrival is not None:
                at = state_at_effect = arrival
        observed_at = _observed_commit(fact, observation_lineages, commit_milestones)
        if observed_at is not None:
            at = state_at_effect = observed_at
        if fact is None or isinstance(fact, (SensoryFact, SpatialFact)):
            clearance = destruction_state_times.get(destruction_owners.get(event.lineage_uuid, event.uuid))
            if clearance is not None:
                at = max(at, clearance)
                state_at_effect = max(state_at_effect or at, clearance)
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
        if isinstance(fact, SpatialFact) and fact.change_type is SpatialChangeType.ENTITY_ENTERED:
            returning_actor = before.actors.get(fact.entity_uuid) if fact.entity_uuid is not None else None
            if returning_actor is not None:
                end = max(end, *(at + echo.returnPortalMs for recipe in data.condition_recipes.values()
                    if (echo := recipe.persistent.absenceEcho) is not None
                    and returning_actor.spatial_disposition in echo.dispositions), at)
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
                        arrival_snapshots[received.event_uuid, received.actor.uuid] = (event.uuid, at)
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
            if fact.operation is SpatialEffectChangeOperation.CREATED and not event.canceled:
                formation_starts[fact.spatial_effect_uuid] = at
            spatial_media = data.spatial_media.get(spatial_contents.get(fact.spatial_effect_uuid, ""))
            if spatial_media is not None:
                if fact.removed_positions and any(layer.cellVariants for layer in spatial_media.layers):
                    end = max(end,at+spatial_media.removalFadeMs)
                if fact.operation is SpatialEffectChangeOperation.CREATED and any(
                        layer.composition == "wall_modules" for layer in spatial_media.layers):
                    effect = spatial_effects.get(fact.spatial_effect_uuid)
                    geometry = effect.area_geometry if effect is not None else None
                    if (limitation := wall_media_limitation(geometry, spatial_media,
                            positions=effect.positions if effect is not None else (),
                            suppressed=bool(effect.suppressions) if effect is not None else False)) is not None:
                        gaps.append((event.uuid, limitation))
                if (fact.operation is SpatialEffectChangeOperation.REMOVED
                        and event.lineage_uuid not in destruction_owners):
                    recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "removal", None, None, at))
                elif (fact.operation is SpatialEffectChangeOperation.CREATED
                      and (spatial_media.formationCommitMs > 0
                           or any(layer.applicationAssetId is not None for layer in spatial_media.layers))):
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
            if (spatial_media is None and fact.operation is SpatialEffectChangeOperation.REMOVED
                    and event.lineage_uuid not in destruction_owners):
                previous = before.senses.spatial_effects.get(fact.spatial_effect_uuid) if before.senses is not None else None
                if previous is not None and any(obj.item.item_id in data.construction_media
                        and obj.item.construction_owner_uuid == fact.spatial_effect_uuid
                        for obj in before.objects.values()):
                    duration = max((construction_duration(data, data.construction_media[obj.item.item_id], 'removal')
                        for obj in before.objects.values() if obj.item.item_id in data.construction_media
                        and obj.item.construction_owner_uuid == fact.spatial_effect_uuid), default=0.)
                    recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "removal", None, None, at,
                        duration_ms=duration))
                    end = max(end, at + duration)
            if fact.previous_pressed is not None and fact.pressed is not None:
                recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "pressed",
                    str(fact.previous_pressed).lower(), str(fact.pressed).lower(), at))
            if fact.previous_state is not None and fact.state is not None:
                recorded_transitions.append(WorldTransition(fact.spatial_effect_uuid, "trap_state",
                    fact.previous_state.value, fact.state.value, at))
                portal_art = data.portals.get(spatial_contents.get(fact.spatial_effect_uuid, ""))
                if isinstance(portal_art, PortalArt):
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
        if (isinstance(fact, SpatialFact) and fact.object_uuid is not None
                and fact.change_type is SpatialChangeType.OBJECT_PLACED and not event.canceled):
            section_starts[fact.object_uuid] = state_at_effect if state_at_effect is not None else at
        if (isinstance(fact, SpatialFact) and fact.object_uuid is not None
                and fact.change_type is SpatialChangeType.OBJECT_REMOVED
                and event.lineage_uuid not in destruction_owners):
            original = before.objects.get(fact.object_uuid)
            binding = data.construction_media.get(original.item.item_id) if original is not None else None
            if binding is not None:
                contact_at = state_at_effect if state_at_effect is not None else at
                duration = construction_duration(data, binding, 'removal')
                recorded_transitions.append(WorldTransition(fact.object_uuid, 'removal', None, None, contact_at,
                    duration_ms=duration))
                end = max(end, contact_at+duration)
        if isinstance(fact, ObjectDamageFact) and fact.applied_damage > 0:
            flash = resolve_damage(data, fact.damage_type.value if fact.damage_type is not None else None).hitFlash
            if flash.enabled:
                recorded_transitions.append(WorldTransition(fact.object_uuid, "hit_flash", None, None,
                    state_at_effect if state_at_effect is not None else at, hit_flash=flash))
        if isinstance(fact, ObjectDestroyedFact):
            state_at_effect = state_at_effect if state_at_effect is not None else at
            transition, clearance, limitation = _destruction_transition(
                before, lineage, event, fact, data, facings or {}, state_at_effect,
                directed_object_contacts(owner.bound.timeline,str(fact.object_uuid))
                if owner is not None and isinstance(owner.bound,BoundCast) else ())
            if transition is not None:
                recorded_transitions.append(transition)
            if clearance is not None:
                destruction_state_times[event.uuid] = clearance
            if limitation is not None:
                gaps.append((event.uuid, limitation))
        application = isinstance(fact, SpellFact) and fact.application_index is not None
        spell_draft = data.drafts.get(fact.behavior_id or "") if isinstance(fact, SpellFact) else None
        child_attack = spell_draft.childAttack if spell_draft is not None else None
        attack_presentation = None
        if isinstance(fact, AttackFact) and event.parent_lineage is not None:
            parent = by_lineage.get(event.parent_lineage)
            if (parent is not None and isinstance(parent.fact, SpellFact)
                    and parent.fact.source_entity_uuid == fact.source_entity_uuid):
                parent_draft = data.drafts.get(parent.fact.behavior_id or "")
                if parent_draft is not None and parent_draft.childAttack is not None:
                    attack_presentation = resolve_child_attack_palette(
                        parent_draft.childAttack, parent_draft.elementColors)
        if child_attack is not None and not any(
                isinstance(by_lineage[identity].fact, AttackFact) for identity in event.children_lineages):
            gaps.append((event.uuid, "Authored child attack has no received attack"))
        body_action = None
        for subject in intervention_subjects(event,data):
            response_body = bind_body_action(_before_event(before,lineage,event),event,data,
                start_ms=at,facings=facings or {},contacts=placed_contacts,subject=subject)
            if response_body is not None:
                actor_order.append((event.uuid,len(body_actions),True))
                body_actions.append(response_body)
                end = max(end,response_body.complete_ms)
        binding = data.body_action_bindings.get(fact.behavior_id or "") if isinstance(fact, ActionFact) else None
        object_interaction = binding is not None and binding.interaction_target is not None
        linked_effect = (object_interaction and isinstance(fact, ActionFact)
                         and fact.source_entity_uuid == interaction_actor)
        if object_interaction and isinstance(fact, ActionFact):
            interaction_actor = fact.source_entity_uuid
        if isinstance(fact, (ActionFact, SpellFact)) and not application and not linked_effect and child_attack is None:
            try:
                body_action = bind_body_action(_before_event(before, lineage, event), event, data,
                    start_ms=at, facings=facings or {}, contacts=placed_contacts,
                    lineage=lineage_branch(lineage, event))
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
                        join_ms=body_action.join_ms + delay, complete_ms=body_action.complete_ms + delay,
                        timing_evidence=translate_timing_evidence(body_action.timing_evidence, delay))
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
                or isinstance(fact, (AttackFact, SpellFact)) and fact.target_kind == "object"
                    and identity == fact.target_entity_uuid and identity in before.objects
                for identity in participants)
        if ((isinstance(fact, (AttackFact, SpellFact)) or delivered_action) and not application and visible_action
                and body_action is None and child_attack is None):
            branch = lineage_branch(lineage, event)
            prior = _before_event(before, lineage, event)
            try:
                bound = (bind_attack(prior, branch, data, facings=facings, contacts=placed_contacts,
                                     child_presentation=attack_presentation, causal_index=causal_index,
                                     emitting_handlers=tuple(row.behavior_id for node in lineage.events
                                         for row in node.content_attributions if row.role=='effective_handler'
                                         and row.source_entity_uuid==fact.source_entity_uuid
                                         and event.lineage_uuid in row.emitted_lineage_uuids))
                         if isinstance(fact, AttackFact) else bind_cast(prior, branch, data,
                             contacts=placed_contacts, facings=facings, causal_index=causal_index))
            except (ValueError, NotImplementedError) as error:
                bound = None
                gaps.append((event.uuid, str(error)))
            if bound is None:
                gaps.append((event.uuid, "Authored action delivery is not bound"))
            else:
                rule = next((rule for rule in data.interruptions.rules
                             if rule.actionEconomySpent and "execution" in rule.phases), None)
                if reactions and rule is not None:
                    reaction_id = next((reaction.root.fact.behavior_id for reaction in reactions
                        if isinstance(reaction.root.fact,ActionFact)),None)
                    cutoff = interruption_ms(bound, rule, reaction_id=reaction_id)
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
                    state_at_effect = at
                    # Native hit admission owns the impulse. The ordinary attack
                    # supplies a physical-band contact, not authored weapon XYZ.
                    if isinstance(fact, AttackFact) and not event.canceled and fact.attack_outcome in (AttackOutcome.HIT, AttackOutcome.CRIT):
                        contact = bound.timeline.target
                        original = prior.objects.get(fact.target_entity_uuid)
                        binding = data.construction_media.get(original.item.item_id) if original is not None else None
                        if (isinstance(contact, ObjectContact) and binding is not None and binding.surface is not None
                                and binding.surface.material == 'force_membrane'):
                            recorded_transitions.append(WorldTransition(fact.target_entity_uuid, 'activation', None, None, at,
                                duration_ms=0, membrane_contact=ordinary_object_contact(contact, bound.timeline.source.grid)))
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
                contact_at = max(at, owner.start_ms + delivery.travel_end_ms)
                shift = contact_at - (owner.start_ms + delivery.travel_end_ms)
                if shift > 0 and owner.bound.staged_area:
                    delayed = replace(delivery, travel_end_ms=delivery.travel_end_ms + shift,
                        damage_start_ms=delivery.damage_start_ms + shift if delivery.damage_start_ms is not None else None,
                        damage_end_ms=delivery.damage_end_ms + shift if delivery.damage_end_ms is not None else None,
                        hp_ms=delivery.hp_ms + shift if delivery.hp_ms is not None else None,
                        flash_ms=delivery.flash_ms + shift if delivery.flash_ms is not None else None,
                        number_ms=delivery.number_ms + shift if delivery.number_ms is not None else None)
                    delivery_evidence = list(owner.bound.timeline.timing_evidence)
                    prior_anchors = {row.target.anchor: TimingOperand(row.target, row.at_ms, row.index)
                        for row in delivery_evidence if row.target.application_id == identity}
                    original_contact = prior_anchors.get('contact')
                    if original_contact is not None:
                        joined_contact = record_timing(delivery_evidence, original_contact.reference,
                            'staged_area_contact', (original_contact,
                                TimingOperand(TimingReference('event', event.uuid, 'admission'), at - owner.start_ms)),
                            delayed.travel_end_ms, 'maximum')
                        assert joined_contact.producer_index is not None and original_contact.producer_index is not None
                        for anchor, clock in (('damage_start', delayed.damage_start_ms), ('hp', delayed.hp_ms)):
                            prior = prior_anchors.get(anchor)
                            if prior is not None and clock is not None:
                                record_timing(delivery_evidence, prior.reference, 'staged_area_shift',
                                    (replace(prior, offset_ms=shift,
                                        offset_producers=(joined_contact.producer_index, original_contact.producer_index)),), clock)
                    timeline = replace(owner.bound.timeline, applications=tuple(
                        delayed if row.source.application_id == identity else row
                        for row in owner.bound.timeline.applications), timing_evidence=tuple(delivery_evidence))
                    updated = replace(owner, bound=replace(owner.bound, timeline=timeline))
                    nodes[nodes.index(owner)] = updated
                    owner = updated
                at = contact_at
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
            displacement_layers = (owner.bound.timeline.recipe.displacementLayers
                if owner is not None and isinstance(owner.bound, BoundCast) else ())
            owner = None  # Its spatial children own their own reached-cell effects.
            if owned_hop is None:
                state_at_effect = None
                try:
                    if fact.target_entity_uuid is not None:
                        original_at = at
                        at = max(at, preceding_damage_commit(event, fact.target_entity_uuid))
                        prior_hp = timing_evidence[-1]
                        record_timing(timing_evidence, TimingReference('event', event.uuid, 'start'), 'displacement_start',
                            (TimingOperand(TimingReference('event', event.uuid, 'admission'), original_at),
                             TimingOperand(prior_hp.target, prior_hp.at_ms, prior_hp.index)), at, 'maximum')
                    displacement = bind_forced_movement(_before_event(before, lineage, event),
                        lineage_branch(lineage, event), data, at, placed_contacts, layers=displacement_layers)
                    forced_movement.append(displacement)
                    state_at_effect = displacement.travel_end_ms
                    end = max(end, displacement.complete_ms)
                except (ValueError, NotImplementedError) as error:
                    gaps.append((event.uuid, str(error)))
        if isinstance(fact, DamageFact) and owner is not None:
            owned_reference = causal_index.by_uuid[owner.event_uuid].resolution_ref
            reference = event.resolution_ref
            if (reference is None or owned_reference is None
                    or reference.lineage_uuid != owned_reference.lineage_uuid):
                owner = None
                state_at_effect = None
        standalone_damage = None
        if (isinstance(fact, DamageFact) and fact.stage == "taken") and owner is None:
            standalone_damage, damage_end = bind_standalone_damage(event, at, placed_contacts)
            end = max(end, damage_end)
        damage_placement = standalone_damage.timing if standalone_damage is not None else None
        damage_contact = standalone_damage.contact if standalone_damage is not None else None
        if isinstance(fact, DamageFact) and fact.stage == "taken" and owner is not None:
            damage_placement, damage_contact = _bound_damage_timing(event, owner)
        if damage_placement is not None:
            results = (standalone_damage.results if standalone_damage is not None else
                       causal_index.results.get(event.resolution_ref, ()) if event.resolution_ref is not None else ())
            for result in results:
                if result.parent_lineage == event.lineage_uuid:
                    result_placements[result.uuid] = damage_placement
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
        entity_cue = bind_lifecycle(event, state_at_effect if state_at_effect is not None else at, placed_contacts)
        if entity_cue is not None:
            end = max(end, entity_cue.body_end_ms)
            if entity_cue.phase == "departure":
                at = state_at_effect = entity_cue.start_ms
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
        if _has_standalone_state(fact, state_at_effect):
            state_nodes.append((state_at_effect if state_at_effect is not None else at, event))
        if isinstance(fact, DamageFact) and fact.stage == "applied":
            placement = result_placements.get(event.uuid)
            spatial_owner = damage_spatial_owner(_before_event(before, lineage, event), fact, created_effects)
            spatial_binding = data.spatial_media.get(spatial_owner.content_ref.content_id) if spatial_owner is not None else None
            material = spatial_binding.damageMaterials.get(fact.damage_type.value) if spatial_binding is not None else None
            if material is not None and fact.applied_damage > 0:
                cue = BodyMaterialCue(event.uuid, str(fact.target_entity_uuid),
                    placement.hp_ms if placement is not None else at, material)
                finite_materials.append(cue)
                end = max(end, cue.end_ms)
            state_nodes.append((placement.hp_ms if placement is not None else
                                state_at_effect if state_at_effect is not None else at, event))
        placement = result_placements.get(event.uuid)
        response = bind_event_condition_response(event, _before_event(before, lineage, event).actors,
            placement.hp_ms if placement is not None else reaction_condition_times.get(event.uuid, at),
            data.condition_recipes)
        if response is not None:
            condition_responses[response.event_uuid, response.owner_uuid] = response
            end = max(end, response.end_ms)
        for received in bind_received_damage_responses(event,_before_event(before,lineage,event).actors,
                placement.hp_ms if placement is not None else at,data.condition_recipes):
            condition_responses[received.event_uuid,received.owner_uuid] = received
            end = max(end,received.end_ms)
        if (isinstance(fact, SpatialEffectStateFact) and bool(fact.removed_positions)
                or isinstance(fact, SpatialFact) and ground_contact_is_authored(before, fact, data)
                or isinstance(fact, DamageFact) and fact.stage == "applied"
                and (fact.effect_id is not None or fact.source_condition_uuid is not None or fact.spatial_source is not None)):
            contacts_here = bind_spatial_contacts(_before_event(before, lineage, event), event, data,
                damage_sweep_starts.get(event.uuid,
                    placement.hp_ms if placement is not None else state_at_effect if state_at_effect is not None else at), placed_contacts, created_effects)
            if isinstance(fact, SpatialFact):
                # Ground-entry splashes keep their own clock without pausing a
                # walk. Damage, dousing and other responses still join the head.
                decorative_contact_media.extend(contacts_here)
            else:
                contact_media.extend(contacts_here)
                end = max(end, max((cue.end_ms for cue in contacts_here),default=end))
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
            healing_cue = HealingCue(event, at)
            state_nodes.append((at, event))
            context = data.healing_context
            prior = _before_event(before, lineage, event)
            healed = prior.actors.get(fact.target_entity_uuid)
            if healed is not None and (str(healed.uuid) in placed_contacts or actor_is_visible(prior, healed)):
                contact = placed_contacts.get(str(healed.uuid)) or actor_contact(prior, healed, data)
                selected = resolve_body_context(data, contact, "healing", RoleDefault(),
                    body_context(context.bodyClip, context.bodyPlaybackSpeed, enabled=context.bodyClip != "none"))
                duration = context_duration(data, contact, selected)
                healing_cue = HealingCue(event, at, contact, selected, at + duration, data)
                end = max(end, at + duration)
            healing.append(healing_cue)
            if context.media:
                gaps.append((event.uuid, "Healing media tracks are not bound"))
        if isinstance(fact, (DeathSaveFact, LifeFact)):
            end = max(end, bind_life_transition(event, fact, at, owner, placed_contacts))

        # TakeDamage owns its nested condition callbacks. Direct on-hit riders
        # remain siblings at Attack's contact, exactly as in the source mapper.
        child_at = at
        injury_at = None
        if damage_placement is not None and damage_contact is not None:
            injury_at = damage_placement.start_ms
            clip = body_clip(data, damage_contact, data.damage_context.bodyClip)
            after_actor = reduce_lineage(before, lineage_branch(lineage, event)).actors.get(UUID(damage_contact.actor_uuid))
            terminal = (after_actor is not None and after_actor.life_state == LifeState.DEAD
                        or damage_contact.life_state == LifeState.DEAD)
            child_at = injury_at if terminal else injury_at + (
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
        commit_milestones[event.lineage_uuid] = state_at_effect if state_at_effect is not None else at
        sequence_children = isinstance(fact, ActionFact) and body_action is not None
        sequence_at = child_at
        sequence_uuid = None
        for identity in event.children_lineages:
            child = by_lineage[identity]
            child_start, effect_at = _child_timing(child.fact, child_at, end, injury_at,
                state_at_effect, portal_arrival, sequence_at if sequence_children else None,
                event.uuid, displacement, evidence=timing_evidence, child_uuid=child.uuid,
                sequence_uuid=sequence_uuid)
            child_end = visit(child, child_start, owner, override, displacement, interaction_actor, effect_at, landed_contact)
            if sequence_children:
                child_end = max(child_end, finish_conditions(child.uuid), join_actor_subtrees(child.uuid))
                # Child commands finish before the next command. State facts
                # share their action's effect anchor: a hatch opening and the
                # resulting fall must not become two sequential actions.
                if isinstance(child.fact, (ActionFact, AttackFact, SpellFact, MovementFact, ShoveFact, EquipmentFact)):
                    sequence_at = child_end
                    sequence_uuid = child.uuid
            end = max(end, child_end)
        return end

    complete = visit(lineage.root, 0)
    for index, node in enumerate(nodes):
        if not isinstance(node.bound, BoundCast) or not node.bound.staged_area:
            continue
        timeline = node.bound.timeline
        delivery = timeline.ground_delivery
        if delivery is None:
            continue
        impact = next((interval for interval in delivery.projectile_intervals if interval.name == "impact"), None)
        last_reach = max((at for at, _ in node.bound.area_reach), default=0.)
        if impact is None or last_reach < impact.end_ms:
            continue
        # Several slow structural collapses can outlast the authored explosion.
        # Fit its existing frames continuously across the causal reach plus its
        # original tail, preserving the first contact and every source frame.
        duration = impact.end_ms - impact.start_ms
        joined_duration = last_reach - impact.start_ms + duration
        ratio = joined_duration / duration
        joined = replace(impact, end_ms=impact.start_ms + joined_duration,
            fps=impact.fps / ratio, time_map=tuple(point.model_copy(update={
                "elapsedMs": point.elapsedMs * ratio}) for point in impact.time_map))
        shift = joined.end_ms - impact.end_ms
        timeline = replace(timeline, ground_delivery=replace(delivery,
            projectile_intervals=tuple(joined if row is impact else row for row in delivery.projectile_intervals)),
            recovery_start_ms=timeline.recovery_start_ms + shift,
            complete_ms=timeline.complete_ms + shift,
            anchors=tuple(replace(anchor, at_ms=anchor.at_ms + shift)
                if anchor.name in ("recover", "complete") else anchor for anchor in timeline.anchors))
        nodes[index] = replace(node, bound=replace(node.bound, timeline=timeline))
        complete = max(complete, node.start_ms + timeline.complete_ms)
    for at, actor_id in turn_starts:
        actor = before.actors.get(actor_id)
        if actor is not None:
            for member in actor.conditions:
                recipe = data.condition_recipes.get(member.behavior_id or "")
                if recipe is not None and recipe.activation is not None:
                    complete = max(complete, at + max((effect.startOffsetMs + effect.durationMs
                        for effect in recipe.activation.effects), default=0))
    complete = max(complete, finish_conditions(), join_actor_subtrees())
    # Compile state once at the existing causal anchors. Frame sampling selects
    # a retained value; it never folds event streams or invokes native mechanics.
    for reaction in reactions:
        cue = next((cue for cue in external_reactions if cue.event_uuid == reaction.root.uuid), None)
        observations.extend((cue.start_ms if cue is not None else 0., row) for row in reaction.observations)
    # Artwork and spatial admission/clearance have separate authored dates.
    # Keep each received world/sensory update indivisible and downstream of
    # every source it observes; the latest native reduction is untouched.
    received_objects = {obj.placement.object_uuid: obj for update in lineage.world_updates
        for obj in update.objects}
    known_objects = {**before.objects, **received_objects}
    formation_producers: dict[UUID, int] = {}
    removal_producers: dict[UUID, int] = {}
    event_producers: dict[UUID, int] = {}

    def timing_operand(index: int) -> TimingOperand:
        row = timing_evidence[index]
        return TimingOperand(row.target, row.at_ms, index)

    offset_sources: list[tuple[float, str, UUID | None]]
    removal_commits: dict[UUID, float] = {}
    for transition in recorded_transitions:
        if transition.field != "removal":
            continue
        identity = transition.identity
        binding = data.spatial_media.get(spatial_contents.get(identity, ""))
        offset_sources = [(binding.removalCommitMs, f'spatial_media.{spatial_contents[identity]}.removalCommitMs', None)] if binding is not None else []
        offset_sources.extend((binding.removalCommitMs, f'construction_media.{obj.item.item_id}.removalCommitMs', object_id)
            for object_id, obj in known_objects.items()
            if (object_id == identity or obj.item.construction_owner_uuid == identity)
            and (binding := data.construction_media.get(obj.item.item_id)) is not None)
        offsets = [value for value, _, _ in offset_sources]
        removal_commits[identity] = transition.start_ms + max(offsets, default=0.)
        removal_kind: Literal['object', 'spatial'] = 'object' if identity in known_objects else 'spatial'
        removal_producers[identity] = len(timing_evidence)
        timing_evidence.append(TimingEvidence(len(timing_evidence),
            TimingReference(removal_kind, identity, 'clearance'), 'clearance', 'maximum',
            tuple(TimingOperand(TimingReference(removal_kind, identity, 'start'), transition.start_ms,
                offset_ms=value, authored_field=field, contributor_object_uuid=object_id)
                for value, field, object_id in offset_sources)
                or (TimingOperand(TimingReference(removal_kind, identity, 'start'), transition.start_ms),),
            removal_commits[identity]))
    formation_commits: dict[UUID, float] = {}
    for identity, start in formation_starts.items():
        binding = data.spatial_media.get(spatial_contents.get(identity, ""))
        offset_sources = [(binding.formationCommitMs, f'spatial_media.{spatial_contents[identity]}.formationCommitMs', None)] if binding is not None else []
        offset_sources.extend((binding.formationCommitMs, f'construction_media.{obj.item.item_id}.formationCommitMs', obj.placement.object_uuid)
            for obj in received_objects.values() if obj.item.construction_owner_uuid == identity
            and (binding := data.construction_media.get(obj.item.item_id)) is not None)
        offsets = [value for value, _, _ in offset_sources]
        formation_commits[identity] = start + max(offsets, default=0.)
        formation_producers[identity] = len(timing_evidence)
        timing_evidence.append(TimingEvidence(len(timing_evidence),
            TimingReference('spatial', identity, 'formation'), 'formation', 'maximum',
            tuple(TimingOperand(TimingReference('spatial', identity, 'start'), start,
                offset_ms=value, authored_field=field, contributor_object_uuid=object_id)
                for value, field, object_id in offset_sources)
                or (TimingOperand(TimingReference('spatial', identity, 'start'), start),),
            formation_commits[identity]))
    for identity, start in section_starts.items():
        obj = received_objects.get(identity)
        binding = data.construction_media.get(obj.item.item_id) if obj is not None else None
        if binding is not None:
            assert obj is not None
            formation_commits[identity] = start + binding.formationCommitMs
            formation_producers[identity] = len(timing_evidence)
            timing_evidence.append(TimingEvidence(len(timing_evidence),
                TimingReference('object', identity, 'formation'), 'formation', 'offset',
                (TimingOperand(TimingReference('object', identity, 'start'), start,
                    offset_ms=binding.formationCommitMs, authored_field=f'construction_media.{obj.item.item_id}.formationCommitMs',
                    contributor_object_uuid=identity),),
                formation_commits[identity]))
    spatial_source_commits: dict[UUID, float] = {}
    spatial_source_producers: dict[UUID, int] = {}
    for event in lineage.events:
        if (not event.canceled and isinstance(event.fact, SpatialEffectStateFact)
                and event.fact.operation in (SpatialEffectChangeOperation.CREATED, SpatialEffectChangeOperation.REMOVED)):
            commits = (formation_commits if event.fact.operation is SpatialEffectChangeOperation.CREATED
                       else removal_commits)
            commit_at = commits.get(event.fact.spatial_effect_uuid)
            if commit_at is not None:
                spatial_source_commits[event.lineage_uuid] = commit_at
                spatial_source_producers[event.lineage_uuid] = (formation_producers
                    if event.fact.operation is SpatialEffectChangeOperation.CREATED else removal_producers)[event.fact.spatial_effect_uuid]
                commit_milestones[event.lineage_uuid] = max(commit_at,
                    commit_milestones.get(event.lineage_uuid, commit_at))
        elif (not event.canceled and isinstance(event.fact, SpatialFact)
                and event.fact.object_uuid is not None
                and event.fact.change_type is SpatialChangeType.OBJECT_PLACED):
            commit_at = formation_commits.get(event.fact.object_uuid)
            if commit_at is not None:
                spatial_source_commits[event.lineage_uuid] = commit_at
                spatial_source_producers[event.lineage_uuid] = formation_producers[event.fact.object_uuid]
                commit_milestones[event.lineage_uuid] = max(commit_at,
                    commit_milestones.get(event.lineage_uuid, commit_at))
    # A received sensory update may name only its cause, rather than repeat
    # the changed field. Carry the exact source deadline through its retained
    # ancestry, including nodes without a fact. Do not use unrelated cast or
    # sibling deadlines to infer ownership.
    spatial_causal_commits: dict[UUID, float] = {}
    spatial_causal_producers: dict[UUID, tuple[int, ...]] = {}
    for event in lineage.events:
        sources = [event]
        if isinstance(event.fact, SensoryFact) and event.fact.cause_event_uuid is not None:
            cause_lineage = observation_lineages.get(event.fact.cause_event_uuid)
            cause = by_lineage.get(cause_lineage) if cause_lineage is not None else None
            if cause is not None:
                sources.append(cause)
        dates = []
        causal_producers: list[int] = []
        for source in sources:
            ancestor: PlayerNode | None = source
            while ancestor is not None:
                if ancestor.lineage_uuid in spatial_source_commits:
                    dates.append(spatial_source_commits[ancestor.lineage_uuid])
                    causal_producers.append(spatial_source_producers[ancestor.lineage_uuid])
                ancestor = by_lineage.get(ancestor.parent_lineage) if ancestor.parent_lineage is not None else None
        if dates:
            spatial_causal_commits[event.lineage_uuid] = max(dates)
            spatial_causal_producers[event.lineage_uuid] = tuple(dict.fromkeys(causal_producers))
            commit_milestones[event.lineage_uuid] = max(max(dates),
                commit_milestones.get(event.lineage_uuid, 0.))
    dated_nodes = []
    for at, node in state_nodes:
        fact = node.fact
        owners = set()
        removed = set()
        if isinstance(fact, SpatialEffectStateFact) and fact.operation is SpatialEffectChangeOperation.CREATED:
            owners.add(fact.spatial_effect_uuid)
        elif isinstance(fact, SpatialEffectStateFact) and fact.operation is SpatialEffectChangeOperation.REMOVED:
            removed.add(fact.spatial_effect_uuid)
        update = world_events.get(node.uuid)
        if update is not None:
            owners.update(obj.placement.object_uuid for obj in update.objects)
            owners.update(obj.item.construction_owner_uuid for obj in update.objects
                if obj.item.construction_owner_uuid is not None)
            removed.update(update.objects_removed)
            removed.update(known_objects[identity].item.construction_owner_uuid
                for identity in update.objects_removed if identity in known_objects
                and known_objects[identity].item.construction_owner_uuid is not None)
        if isinstance(fact, SpatialFact) and fact.object_uuid is not None and fact.change_type is SpatialChangeType.OBJECT_PLACED:
            owners.add(fact.object_uuid)
            obj = received_objects.get(fact.object_uuid)
            if obj is not None and obj.item.construction_owner_uuid is not None:
                owners.add(obj.item.construction_owner_uuid)
        elif isinstance(fact, SpatialFact) and fact.object_uuid is not None and fact.change_type is SpatialChangeType.OBJECT_REMOVED:
            removed.add(fact.object_uuid)
            obj = known_objects.get(fact.object_uuid)
            if obj is not None and obj.item.construction_owner_uuid is not None:
                removed.add(obj.item.construction_owner_uuid)
        base_at = at
        at = max((at, *(formation_commits[owner] for owner in owners if owner in formation_commits),
                  *(removal_commits[owner] for owner in removed if owner in removal_commits)))
        commit_milestones[node.lineage_uuid] = max(at, commit_milestones.get(node.lineage_uuid, at))
        owner_inputs = tuple(timing_operand(formation_producers[owner]) for owner in sorted(owners, key=str)
            if owner in formation_producers) + tuple(timing_operand(removal_producers[owner])
            for owner in sorted(removed, key=str) if owner in removal_producers)
        if owner_inputs:
            event_producers[node.uuid] = len(timing_evidence)
            timing_evidence.append(TimingEvidence(len(timing_evidence), TimingReference('event', node.uuid, 'commit'),
                'world_floor', 'maximum', (TimingOperand(TimingReference('event', node.uuid, 'admission'), base_at),
                    *owner_inputs), at))
        dated_nodes.append((at, node))
    state_nodes = []
    for at, node in sorted(dated_nodes, key=lambda row: order[row[1].uuid]):
        spatial_commit = spatial_causal_commits.get(node.lineage_uuid)
        if spatial_commit is not None:
            base = timing_operand(event_producers[node.uuid]) if node.uuid in event_producers else TimingOperand(
                TimingReference('event', node.uuid, 'admission'), at)
            at = max(at, spatial_commit)
            event_producers[node.uuid] = len(timing_evidence)
            timing_evidence.append(TimingEvidence(len(timing_evidence), TimingReference('event', node.uuid, 'commit'),
                'spatial_cause', 'maximum', (base, *(timing_operand(index)
                    for index in spatial_causal_producers[node.lineage_uuid])), at))
        observed_at = _observed_commit(by_uuid[node.uuid].fact, observation_lineages, commit_milestones)
        if observed_at is not None:
            base = timing_operand(event_producers[node.uuid]) if node.uuid in event_producers else TimingOperand(
                TimingReference('event', node.uuid, 'admission'), at)
            observed_fact = by_uuid[node.uuid].fact
            assert isinstance(observed_fact, SensoryFact)
            observed_sources = {observation_lineages[row.source_event_uuid]: row.source_event_uuid
                for row in observed_fact.observed_changes if row.source_event_uuid in observation_lineages}
            inputs = tuple(TimingOperand(TimingReference('event', observed_sources[source], 'commit'),
                commit_milestones[source]) for source in sorted(observed_sources, key=str))
            at = max(at, observed_at)
            event_producers[node.uuid] = len(timing_evidence)
            timing_evidence.append(TimingEvidence(len(timing_evidence), TimingReference('event', node.uuid, 'commit'),
                'observed_source', 'maximum', (base, *inputs), at))
        if isinstance(node.fact, SensoryFact):
            base = timing_operand(event_producers[node.uuid]) if node.uuid in event_producers else TimingOperand(
                TimingReference('event', node.uuid, 'admission'), at)
            at = max((at, *(formation_commits[owner]
                for owner in node.fact.spatial_effects_changed if owner in formation_commits),
                *(removal_commits[owner] for owner in node.fact.spatial_effects_removed
                  if owner in removal_commits)))
            owner_inputs = tuple(timing_operand(formation_producers[owner])
                for owner in node.fact.spatial_effects_changed if owner in formation_producers) + tuple(
                timing_operand(removal_producers[owner]) for owner in node.fact.spatial_effects_removed
                if owner in removal_producers)
            if owner_inputs:
                event_producers[node.uuid] = len(timing_evidence)
                timing_evidence.append(TimingEvidence(len(timing_evidence), TimingReference('event', node.uuid, 'commit'),
                    'sensory_owner', 'maximum', (base, *owner_inputs), at))
        commit_milestones[node.lineage_uuid] = max(at, commit_milestones.get(node.lineage_uuid, at))
        state_nodes.append((at, node))
    dated_observations: list[tuple[float, PlayerObservation]] = []
    for at, row in observations:
        arrival = arrival_snapshots.get((row.event_uuid, row.actor.uuid))
        if arrival is not None:
            # An independently disclosed endpoint admits this exact received
            # snapshot at emergence. Its later ground consequence must not
            # delay first visibility, nor manufacture an earlier HP value.
            portal_uuid, arrival_at = arrival
            if any(existing.event_uuid == row.event_uuid and existing.actor.uuid == row.actor.uuid
                   for _, existing in dated_observations):
                continue
            timing_evidence.append(TimingEvidence(len(timing_evidence),
                TimingReference('observation', row.event_uuid, 'commit'), 'observation_floor', 'offset',
                (TimingOperand(TimingReference('event', portal_uuid, 'arrival'), arrival_at),), arrival_at))
            dated_observations.append((arrival_at, row))
            continue
        source_at = commit_milestones.get(observation_lineages[row.event_uuid])
        if source_at is not None:
            timing_evidence.append(TimingEvidence(len(timing_evidence),
                TimingReference('observation', row.event_uuid, 'commit'), 'observation_floor', 'maximum',
                (TimingOperand(TimingReference('observation', row.event_uuid, 'admission'), at),
                 TimingOperand(TimingReference('event', row.event_uuid, 'commit'),
                     source_at)), max(at, source_at)))
        dated_observations.append((max(at, source_at) if source_at is not None else at, row))
    observations = dated_observations
    states: list[tuple[float, PlayerState]] = []
    state_commits: list[StateCommitEvidence] = []
    state = displayed_before
    version_rows = tuple(row for root in (*reactions, lineage) for row in root.version_rows)
    for at in sorted({time for time, _ in (*state_nodes, *observations)}):
        identities = {node.uuid for time, node in state_nodes if time == at}
        selected = tuple(sorted((node for time, node in state_nodes
                                 if time == at), key=lambda node: order[node.uuid]))
        selected_observations = tuple(observation for time, observation in observations if time == at)
        selected_updates = tuple(update for update in lineage.world_updates if update.event_uuid in identities)
        state = reduce_nodes(state, selected, version_rows, selected_observations, selected_updates)
        state_commits.append(StateCommitEvidence(at, selected,
            tuple(row.event_uuid for row in selected_observations),
            tuple(row.event_uuid for row in selected_updates),
            tuple(row for row in version_rows if row.event_uuid in identities
                  or any(row.event_uuid == observation.event_uuid for observation in selected_observations))))
        states.append((at, state))
        complete = max(complete, at)
    recorded_transitions.extend(construction_creation_transitions(displayed_before, states, lineage, data,
        formation_starts={**formation_starts, **section_starts}))
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
        action_recipe = data.body_action_recipes.get(cue.recipe_id)
        if action_recipe is None or by_uuid[cue.event_uuid].canceled:
            continue
        descendants = tuple(node for node in lineage.events if owned_by(node.uuid,cue.event_uuid))
        modes = {effect.presence_mode for node in descendants if isinstance(node.fact,SensoryFact)
            for effect in node.fact.spatial_effects_changed.values()}
        for track in action_recipe.media:
            if track.requireHealingApplied and not any(isinstance(node.fact,HealFact)
                    and not node.canceled and not node.fact.was_blocked and node.fact.actual_healing > 0
                    and str(node.fact.target_entity_uuid) == cue.contact.actor_uuid for node in descendants):
                continue
            if track.requiredSaveSuccess is not None and track.requiredSaveSuccess != cue.save_success:
                continue
            if track.whenPresenceMode is not None and track.whenPresenceMode not in modes:
                continue
            if track.requireAppliedConditionId is not None and not any(isinstance(node.fact,ConditionChangeFact)
                    and not node.canceled and node.fact.event_type is EventType.CONDITION_APPLICATION
                    and node.fact.condition.behavior_id == track.requireAppliedConditionId for node in descendants):
                continue
            media = StationaryMediaCue(cue.event_uuid,track,cue.contact.grid,cue.contact.elevation_steps,
                cue.contact.facing,max(cue.start_ms,cue.effect_ms+track.startOffsetMs),data,
                actor_uuid=cue.contact.actor_uuid)
            stationary.append(media)
            complete = max(complete,media.end_ms)
            body_actions[index] = join_body_action(body_actions[index],data,media.end_ms)
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
    for cue in body_actions:
        material = data.action_materials.get(cue.recipe_id)
        if material is None or by_uuid[cue.event_uuid].canceled:
            continue
        if material.requireAppliedConditionId is not None and not any(
                isinstance(node.fact, ConditionChangeFact) and not node.canceled
                and node.fact.event_type is EventType.CONDITION_APPLICATION
                and node.fact.condition.behavior_id == material.requireAppliedConditionId
                and owned_by(node.uuid, cue.event_uuid) for node in lineage.events):
            continue
        finite = BodyMaterialCue(cue.event_uuid, cue.contact.actor_uuid, cue.effect_ms, material)
        finite_materials.append(finite)
        complete = max(complete, finite.end_ms)
    # Linked reactions remain distinct native roots. Their observations and final
    # state are retained in completion order; only their body clocks overlap.
    after = displayed_before
    for reaction in reactions:
        after = reduce_lineage(after, reaction)
    after = reduce_lineage(after, lineage)
    body_actions.extend(external_reactions)
    complete = max(complete, max((cue.complete_ms for cue in external_reactions), default=0.))
    complete = max(complete, max((cue.complete_ms for cue in reaction_media), default=0.))
    complete = max(complete, max((cue.end_ms for cue in contact_media), default=0.))
    return BoundChoreography(lineage.root.uuid, displayed_before, after,
                             tuple(nodes), tuple(conditions), complete, tuple(gaps), tuple(healing),
                             tuple(lifecycle), tuple(equipment), tuple(shoves), tuple(forced_movement), tuple(damage),
                             tuple(observations), tuple(body_actions), tuple(states),
                             tuple(sorted(transitions.values(), key=lambda row: row.start_ms)), tuple(movements), tuple(strips), tuple(residue_reveals) + tuple(
                                 replace(change, start_ms=change.start_ms + cue.start_ms,
                                         end_ms=change.end_ms + cue.start_ms)
                                 for cue in movements for change in cue.timeline.residue_reveals),
                             body_hops=tuple(body_hops), portals=tuple(portals), stationary_media=tuple(stationary),
                             turn_starts=tuple(turn_starts), contact_media=(*contact_media, *decorative_contact_media),
                             reaction_media=tuple(reaction_media), condition_responses=tuple(condition_responses.values()),
                             entity_lifecycle=tuple(entity_lifecycle), finite_materials=tuple(finite_materials),
                             spatial_responses=tuple(spatial_responses), state_commits=tuple(state_commits),
                             timing_evidence=tuple(timing_evidence))


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
    entity_lifecycle_samples = [(cue, elapsed_ms) for cue in bound.entity_lifecycle]
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
        # Binding may know a participant first revealed by this action. Keep
        # that body out of playback until its matching observation is admitted.
        unrevealed = {body.actor_uuid for body in sample.bodies
            if ((departed := displayed.actors.get(UUID(body.actor_uuid))) is not None and not departed.present)
            or ((prior := bound.before.actors.get(UUID(body.actor_uuid))) is None
                or not actor_is_visible(bound.before, prior))
            and ((current := displayed.actors.get(UUID(body.actor_uuid))) is None
                or not actor_is_visible(displayed, current))}
        if unrevealed:
            sample = replace(sample, bodies=tuple(body for body in sample.bodies if body.actor_uuid not in unrevealed),
                vitals=tuple(value for value in sample.vitals if value.actor_uuid not in unrevealed))
        if isinstance(node.bound, BoundCast) and node.bound.staged_area and isinstance(sample, CastSample):
            # A recipient first revealed by a breach has no visible idle body
            # before its received application reaches that presentation stage.
            pending = {application.source.target.actor_uuid
                for application in node.bound.timeline.applications
                if isinstance(application.source.target, ActorContact) and local < application.travel_end_ms
                and ((actor := bound.before.actors.get(UUID(application.source.target.actor_uuid))) is None
                     or not actor_is_visible(bound.before, actor))}
            sample = replace(sample, bodies=tuple(body for body in sample.bodies if body.actor_uuid not in pending),
                vitals=tuple(value for value in sample.vitals if value.actor_uuid not in pending))
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
                         if application.source.damage_applied and isinstance(application.source.target, ActorContact)}
                        if isinstance(node.bound, BoundCast) else None)
        vitals.update((value.actor_uuid, value) for value in sample.vitals
                      if UUID(value.actor_uuid) in displayed.actors
                      and (owned_vitals is None or value.actor_uuid in owned_vitals))
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
    for cue in bound.healing:
        if (cue.contact is not None and cue.body_context is not None and cue.body_context.actor.enabled
                and cue.end_ms is not None and cue.start_ms <= elapsed_ms < cue.end_ms and cue.data is not None):
            bodies.setdefault(cue.contact.actor_uuid,
                sample_context_body(cue.data, cue.contact, cue.body_context, elapsed_ms - cue.start_ms))
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
            entity_lifecycle_samples.extend(child.entity_lifecycle)
    for cue in bound.portals:
        if portal_actor_hidden(cue, elapsed_ms):
            hidden.add(cue.actor_uuid)
        contact = portal_departure_contact(cue, elapsed_ms) or portal_arrival_contact(cue, elapsed_ms)
        if contact is not None:
            contacts[cue.actor_uuid] = contact
            body = portal_body(cue,elapsed_ms)
            if body is not None:
                bodies[cue.actor_uuid] = body
        elif cue.arrival is not None and elapsed_ms >= cue.arrival_ms:
            actor = displayed.actors.get(UUID(cue.actor_uuid))
            if actor is not None and actor_is_visible(displayed, actor):
                contacts.setdefault(cue.actor_uuid, actor_contact(displayed, actor, cue.data, cue.arrival.facing))
    return ChoreographySample(displayed, tuple(clips), conditions, tuple(vitals.values()),
                              elapsed_ms >= bound.complete_ms, tuple(bodies.values()), tuple(contacts.values()), tuple(strips),
                              frozenset(hidden), tuple(portal_samples), tuple(stationary_samples), tuple(reaction_samples),
                              tuple(entity_lifecycle_samples))


# Passive descriptions for the developer inventory. These never dispatch events.
FACT_PRESENTATION = {
    "portal_transfer": ("portal_animation", "committed crossing; independently disclosed departure and arrival"),
    "attack": ("attack", "timeline; child results at contact"),
    "spell": ("cast", "timeline or parent application"),
    "area_reach": ("cast", "native propagation stage; recipients wait for prerequisite structural clearance"),
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
    "item_effect": ("item_attachment", "native item membership edge and retained application clock"),
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
    path_bend: tuple[float, float] = (0, 0)
    passage_scale: tuple[float, float] = (1, 1)
    passage_body_height_px: float = 0
    passage_socket: str | None = None
    passage_hold_fraction: float = 0
    lift_phase_edges: tuple[float, float] | None = None
    # Source-pixel riser height and admitted original-edge fractions (pauses may split an edge).
    support_riser: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class MotionReaction:
    choreography: BoundChoreography
    contact: ActorContact | None
    source: ActorContact | None
    start_ms: float
    end_ms: float
    lift_px: float = 0
    action_label: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class MotionReductionSource:
    """Exact inputs of an existing fold, not fresh semantic occurrences."""
    kind: Literal["reduction"] = "reduction"
    event_uuids: tuple[UUID, ...]
    observation_event_uuids: tuple[UUID, ...]
    world_event_uuids: tuple[UUID, ...]
    version_rows: tuple[VersionRow, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MotionGroupSource:
    kind: Literal["group_result"] = "group_result"
    root_uuid: UUID
    offset_ms: float
    inputs: MotionReductionSource
    commits: tuple[StateCommitEvidence, ...]
    before: PlayerState
    states: tuple[tuple[float, PlayerState], ...]
    timing_evidence: tuple[TimingEvidence, ...] = ()
    action_timing: tuple[PresentationDependencies, ...] = ()


@dataclass(frozen=True, slots=True)
class MotionStateProvenance:
    state_index: int
    at_ms: float
    origin: Literal["branch_fold", "nested_group_result", "jump_launch", "landing_prefix", "root_reconciliation"]
    sources: tuple[MotionReductionSource | MotionGroupSource, ...]


def _motion_reduction_source(lineage: PlayerLineage) -> MotionReductionSource:
    return MotionReductionSource(event_uuids=tuple(node.uuid for node in lineage.events),
        observation_event_uuids=tuple(row.event_uuid for row in lineage.observations),
        world_event_uuids=tuple(row.event_uuid for row in lineage.world_updates),
        version_rows=lineage.version_rows)


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
    animation_id: str | None = None
    body_frame_keys: tuple[tuple[float, int], ...] = ()
    body_context: BodyContext | None = None
    recovery_body: BodyContext | None = None
    recovery_start_ms: float | None = None
    state_provenance: tuple[MotionStateProvenance, ...] = ()
    root_uuid: UUID | None = None
    timing_evidence: tuple[TimingEvidence, ...] = ()


def _record_motion_span(rows: list[TimingEvidence], root_uuid: UUID, end: float, duration: float,
                        reason: TimingReason, field: str, contributor: UUID | None = None,
                        measurements: tuple[TimingMeasurement, ...] = ()) -> None:
    """Record the existing cursor increment, preserving its exact prior stage."""
    previous = rows[-1] if rows else None
    source = (TimingOperand(previous.target, previous.at_ms, previous.index, duration,
                authored_field=field, contributor_event_uuid=contributor, measurements=measurements)
        if previous is not None else TimingOperand(TimingReference('event', root_uuid, 'start'),
            0., offset_ms=duration, authored_field=field, contributor_event_uuid=contributor, measurements=measurements))
    record_timing(rows, TimingReference('event', root_uuid, 'complete'), reason, (source,), end)


def _resolve_motion_body(timeline: MotionTimeline, data: AnimationData, movement: MovementFact,
                         recovery: MovementRecovery) -> MotionTimeline:
    qualifier = MovementBodyQualifier(movement_mode=movement.movement_mode, trajectory=movement.trajectory,
                                      connector_presentation_key=movement.connector_presentation_key)
    flight = (data.movement_context.flight if movement.movement_mode is MovementMode.FLYING
              and movement.trajectory is MovementTrajectory.PATH else None)
    default = (flight.body if flight is not None else body_context(
        timeline.clip, timeline.playback_speed, loop=timeline.body_loops).model_copy(
            update={"frameKeys": timeline.body_frame_keys}))
    selected = resolve_body_context(data, timeline.actor, "movement", qualifier, default)
    recovered = resolve_body_context(data, timeline.actor, "movement_recovery", qualifier, body_context(
        recovery.bodyClip, recovery.bodyPlaybackSpeed, enabled=recovery.enabled))
    recovery_start = timeline.complete_ms
    duration = (context_duration(data, timeline.settled_contact, recovered)
                if timeline.legs and timeline.settled_contact is not None else 0.)
    evidence = list(timeline.timing_evidence)
    if timeline.root_uuid is not None:
        _record_motion_span(evidence, timeline.root_uuid, recovery_start + duration, duration,
            'motion_recovery', 'movement_recovery.context_duration')
    return replace(timeline, timing_evidence=tuple(evidence), clip=selected.actor.clip, playback_speed=selected.actor.playbackSpeed,
        body_loops=selected.playback == "loop", body_frame_keys=selected.frameKeys,
        body_context=selected, recovery_body=recovered, recovery_start_ms=recovery_start,
        complete_ms=recovery_start + duration)


@dataclass(frozen=True, slots=True)
class TimelineVisit:
    """One already-bound timeline at its absolute offset within the head."""
    offset_ms: float
    event_uuid: UUID | None
    timeline: BoundChoreography | MotionTimeline


def walk_bound_timelines(choreography: BoundChoreography | None = None,
                         motion: MotionTimeline | None = None, *,
                         offset_ms: float = 0., event_uuid: UUID | None = None) -> Iterator[TimelineVisit]:
    if choreography is not None:
        yield TimelineVisit(offset_ms, choreography.root_uuid, choreography)
        for cue in choreography.movements:
            yield from walk_bound_timelines(motion=cue.timeline,
                offset_ms=offset_ms + cue.start_ms, event_uuid=cue.event_uuid)
    elif motion is not None:
        yield TimelineVisit(offset_ms, event_uuid if event_uuid is not None else motion.root_uuid, motion)
        for reaction in motion.reactions:
            yield from walk_bound_timelines(choreography=reaction.choreography,
                offset_ms=offset_ms + reaction.start_ms)


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
    working_sources: list[MotionReductionSource | MotionGroupSource] = []
    launch_sources: list[MotionReductionSource | MotionGroupSource] = []
    provenance: list[MotionStateProvenance] = []
    launch_transitions: tuple[WorldTransition, ...] = ()
    elapsed = 0.0
    motion_evidence: list[TimingEvidence] = []
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
            working_sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
                inputs=_motion_reduction_source(lineage_branch(lineage, event)), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
            reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                            held.body_lift_px, event.fact.name))
            elapsed += group.complete_ms
            _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
            working = group.after
            launch_state = working
            launch_sources = list(working_sources)
        working = reduce_lineage(working, branch)
        working_sources.append(_motion_reduction_source(branch))
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
        launch_sources.append(_motion_reduction_source(replace(lineage, events=(takeoff,), observations=(), world_updates=())))
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
        launch_sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
            inputs=_motion_reduction_source(departing), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
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
        anticipation_ms = max((track.contactFrame*1000/track.fps for track in context.jumpMedia
            if track.role == "takeoff" and set(track.whenConditions) <= members
            and not set(track.unlessConditions) & members), default=0)
        elapsed += anticipation_ms
        _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, anticipation_ms, 'motion_span', 'jumpMedia.takeoff.contactFrame/fps')
        distance = hypot(arrival[0] - jump.start_position[0],
                         arrival[1] - jump.start_position[1])
        duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                       context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
        if last_step.resolved_speed_feet is not None and last_step.resolved_speed_feet > 0:
            duration *= data.movement_reference_speed_feet/last_step.resolved_speed_feet
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
        legs = (MotionLeg(launch.grid, arrival, launch.elevation_steps, arrival_height,
                          elapsed, elapsed + duration, elapsed, arc, initial_lift_px=launch.body_lift_px),)
        provenance.append(MotionStateProvenance(len(states), elapsed, "jump_launch", tuple(launch_sources)))
        states.append((elapsed, launch_state))
        elapsed += duration
        _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, duration, 'motion_span',
            'movement.jump.duration', steps[-1].uuid, (
                TimingMeasurement('distance_cells', distance),
                TimingMeasurement('jumpBaseDurationMs', context.jumpBaseDurationMs),
                TimingMeasurement('jumpPerCellDurationMs', context.jumpPerCellDurationMs),
                TimingMeasurement('jumpMinDurationMs', context.jumpMinDurationMs),
                TimingMeasurement('jumpMaxDurationMs', context.jumpMaxDurationMs),
                TimingMeasurement('reference_speed_feet', data.movement_reference_speed_feet),
                TimingMeasurement('resolved_speed_feet', last_step.resolved_speed_feet or 0)))
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
                provenance.append(MotionStateProvenance(len(states), elapsed, "landing_prefix",
                    (_motion_reduction_source(replace(lineage,
                        events=tuple(node for node in lineage.events if node.uuid in prior_ids),
                        observations=tuple(row for row in lineage.observations if row.event_uuid in prior_ids),
                        world_updates=tuple(row for row in lineage.world_updates if row.event_uuid in prior_ids))),)))
                states.append((elapsed, prior))
                reactions.append(MotionReaction(group, landing_contact, None, elapsed, elapsed + group.complete_ms))
                elapsed += group.complete_ms
                _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
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
            reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms, held.body_lift_px))
            elapsed += group.complete_ms
            _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
    provenance.append(MotionStateProvenance(len(states), elapsed, "root_reconciliation", (_motion_reduction_source(lineage),)))
    states.append((elapsed, final))
    transitions = merge_world_transitions(world_transitions(target, states), launch_transitions,
        tuple(replace(change, start_ms=change.start_ms + reaction.start_ms)
              for reaction in reactions for change in reaction.choreography.world_transitions))
    return _resolve_motion_body(MotionTimeline(launch, legs, context.jumpClip, 1, arc, elapsed,
                          tuple(reactions), settled, target, target.actors[jump.source_entity_uuid],
                          settled_lift_px=settled.body_lift_px if settled is not None else 0, body_loops=False,
                          states=tuple(states), state_provenance=tuple(provenance), root_uuid=lineage.root.uuid, timing_evidence=tuple(motion_evidence), world_transitions=transitions,
                          residue_reveals=tuple(replace(change,
                              start_ms=change.start_ms + reaction.start_ms,
                              end_ms=change.end_ms + reaction.start_ms)
                              for reaction in reactions for change in reaction.choreography.residue_reveals),
                          contact_media=tuple(contact_media)), data, jump, context.jumpRecovery)


def _visible_contact(state: PlayerState, actor_uuid: UUID, data: AnimationData,
                     facing: Facing8 = "S") -> ActorContact | None:
    actor = state.actors.get(actor_uuid)
    return actor_contact(state, actor, data, facing) if actor is not None and actor_is_visible(state, actor) else None


def _flight_path_phases(children: tuple[PlayerNode, ...], subject: UUID,
                        clearance: float, height_scale: float) -> dict[UUID, tuple[float, float, float]]:
    """Parameterize only adjacent, disclosed committed edges, never a root path.

    An opaque or rejected edge ends the span. A stopped attempt therefore reaches
    its last admitted support before its reaction, without inventing a return leg.
    """
    result: dict[UUID, tuple[float, float, float]] = {}
    span: list[tuple[UUID, StepFact]] = []

    def finish() -> None:
        distances = [hypot(step.to_position[0] - step.from_position[0],
                           step.to_position[1] - step.from_position[1]) for _, step in span]
        total = sum(distances)
        if not total:
            span.clear()
            return
        height = max(clearance, *(abs(step.to_elevation_feet-step.from_elevation_feet) / 5 * height_scale
                                  for _, step in span))
        distance = 0.
        for (identity, _), length in zip(span, distances, strict=True):
            result[identity] = (distance / total, (distance + length) / total, height)
            distance += length
        span.clear()

    for node in children:
        step = node.fact
        if not isinstance(step, StepFact) or step.source_entity_uuid != subject or not step.committed:
            finish()
            continue
        if span and (span[-1][1].to_position != step.from_position
                     or span[-1][1].to_elevation_feet != step.from_elevation_feet):
            finish()
        span.append((node.uuid, step))
    finish()
    return result


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
    flight = (context.flight if root.movement_mode is MovementMode.FLYING
              and root.trajectory is MovementTrajectory.PATH else None)
    flight_phases = (_flight_path_phases(children, root.source_entity_uuid, flight.clearancePx,
        HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH) if flight is not None else {})
    connector_profile = context.connectorProfiles.get(root.connector_presentation_key) if root.connector_presentation_key is not None else None
    arc_height = connector_profile.arcHeightPx if connector_profile is not None else 0
    partial_jump = root.trajectory is MovementTrajectory.DIRECT_ARC
    if partial_jump and steps and root.start_position is not None and root.end_position is not None:
        return _bind_jump(target, lineage, root, steps, data, actor, contacts, activated_conditions)
    reaction_context = data.movement_reaction_context
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    contact_media: list[StationaryMediaCue] = []
    states: list[tuple[float, PlayerState]] = []
    provenance: list[MotionStateProvenance] = []
    elapsed = body_start = 0.0
    motion_evidence: list[TimingEvidence] = []
    working = target
    settled = _visible_contact(working, root.source_entity_uuid, data)
    settled_lift = 0.0
    isolated_point = settled is not None
    hidden_transition = False
    uninterrupted = False
    for node in children:
        sources: list[MotionReductionSource | MotionGroupSource] = []
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
                    _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, context.walkStepDurationMs, 'motion_dwell', 'movement.walkStepDurationMs')
                    hidden_transition = False
                source = None
                label = None
                if group.nodes:
                    bound = group.nodes[0].bound
                    source = bound.timeline.source if isinstance(bound, BoundAttack) else bound.timeline.source.caster
                    action = next(row.fact for row in branch.events if row.uuid == group.nodes[0].event_uuid)
                    if isinstance(action, (AttackFact, SpellFact)):
                        label = action.name
                sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
                    inputs=_motion_reduction_source(branch), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
                reactions.append(MotionReaction(group, held, source, elapsed,
                    elapsed + group.complete_ms, held.body_lift_px if held is not None else 0, label))
                elapsed += group.complete_ms
                _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
                isolated_point = False
                body_start = elapsed
            else:
                sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
                    inputs=_motion_reduction_source(branch), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
                contact_media.extend(replace(cue, start_ms=elapsed+cue.start_ms) for cue in group.contact_media)
            successor = group.after
            seen = _visible_contact(successor, root.source_entity_uuid, data)
            if group.movements:
                # This subtree already rendered its disclosed travel. The
                # opaque-node dwell below must not add another movement pause.
                working, settled = successor, seen
                isolated_point = hidden_transition = uninterrupted = False
                provenance.append(MotionStateProvenance(len(states), elapsed, "nested_group_result", tuple(sources)))
                states.append((elapsed, working))
                continue
            previous = _visible_contact(working, root.source_entity_uuid, data)
            if previous is not None and (seen is None or seen.grid != previous.grid):
                if isolated_point and not partial_jump:
                    elapsed += context.walkStepDurationMs
                    _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, context.walkStepDurationMs, 'motion_dwell', 'movement.walkStepDurationMs')
                isolated_point = False
                hidden_transition = seen is None
                uninterrupted = False
            if seen is not None and (previous is None or seen.grid != previous.grid):
                if hidden_transition:
                    elapsed += context.walkStepDurationMs
                    _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, context.walkStepDurationMs, 'motion_dwell', 'movement.walkStepDurationMs')
                    hidden_transition = False
                isolated_point = True
                body_start = elapsed
            working, settled = successor, seen
            provenance.append(MotionStateProvenance(len(states), elapsed, "nested_group_result", tuple(sources)))
            states.append((elapsed, working))
            continue
        if step.source_entity_uuid != root.source_entity_uuid:
            # Other subjects retain their own causal state, never this path.
            working = reduce_lineage(working, branch)
            provenance.append(MotionStateProvenance(len(states), elapsed, "branch_fold", (_motion_reduction_source(branch),)))
            states.append((elapsed, working))
            continue
        if hidden_transition:
            elapsed += context.walkStepDurationMs
            _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, context.walkStepDurationMs, 'motion_dwell', 'movement.walkStepDurationMs')
            hidden_transition = False
        # Both endpoints are explicit player facts. The projection has already
        # applied native identity and per-endpoint grants; no root path is used.
        start, end = step.from_position, step.to_position
        height, end_height = step.from_elevation_feet / 5, step.to_elevation_feet / 5
        path_bend = (0.0, 0.0)
        passage_scale = (1.0, 1.0)
        passage_body_height = 0.0
        passage_socket = None
        passage_hold_fraction = 0.0
        arc_height = connector_profile.arcHeightPx if connector_profile is not None and step.committed else 0
        phase_from, phase_to = 0., 1.
        lift_phase_edges = None
        if flight is not None and step.committed:
            phase_from, phase_to, arc_height = flight_phases[node.uuid]
            lift_phase_edges = (flight.takeoffFraction, 1 - flight.landingFraction)
        if step.committed and connector_profile is not None and connector_profile.passageBodyHeightPx is not None:
            opening = passage_point(working, start, end)
            if opening is not None:
                passage_scale = connector_profile.passageScale
                passage_body_height = connector_profile.passageBodyHeightPx
                passage_socket = connector_profile.passageSocket
                passage_hold_fraction = connector_profile.passageHoldFraction
                path_bend = (opening[0] - (start[0] + end[0]) / 2,
                             opening[1] - (start[1] + end[1]) / 2)
                arc_height = ((opening[2] - (height + end_height) / 2)
                              * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
                              - connector_profile.passageBodyHeightPx * actor.visual_scale)
        current = working.actors.get(step.source_entity_uuid, staged.actors[step.source_entity_uuid])
        leg_actor = replace(actor, hp=current.normal_hp, life_state=current.life_state)
        initial_lift = 0.0
        if not legs and _visible_contact(target, root.source_entity_uuid, data) is not None:
            start, height, initial_lift = actor.grid, actor.elevation_steps, actor.body_lift_px
        delta = end[0] - start[0], end[1] - start[1]
        distance = hypot(step.to_position[0] - step.from_position[0], step.to_position[1] - step.from_position[1])
        speed_scale = ((step.resolved_speed_feet/data.movement_reference_speed_feet)
                       if step.resolved_speed_feet is not None and step.resolved_speed_feet > 0 else 1)
        duration = (connector_profile.durationMs if connector_profile is not None else context.walkStepDurationMs * distance / speed_scale)
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
            if flight is not None and not step.committed:
                fraction = 0.  # No admitted flight: resolve the veto on its known ground support.
            continuation = start[0] + delta[0] * fraction, start[1] + delta[1] * fraction
            continuation_height = height + (end_height - height) * fraction
            lead_end = elapsed + ((duration*fraction if flight is not None else reaction_context.movementLeadInMs) if fraction else 0)
            if fraction:
                legs.append(MotionLeg(start, continuation, height, continuation_height,
                                  elapsed, lead_end, body_start, arc_height_px=arc_height,
                                  curve_from=phase_from, curve_to=phase_from+(phase_to-phase_from)*fraction, initial_lift_px=initial_lift,
                                  speed_scale=speed_scale, path_bend=path_bend,
                                  passage_scale=passage_scale, passage_body_height_px=passage_body_height,
                                  passage_socket=passage_socket, passage_hold_fraction=passage_hold_fraction,
                                  lift_phase_edges=lift_phase_edges,
                                  support_riser=(abs(end_height-height)*HEIGHT_STEP_PIXELS*data.rig.TILE_W/TILE_WIDTH, 0., fraction) if flight is not None else None))
            elapsed = lead_end
            _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, ((duration*fraction if flight is not None else reaction_context.movementLeadInMs) if fraction else 0), 'motion_span', 'movement_reaction.lead_in', node.uuid)
            facing = facing_for_delta(delta, data)
            for attack_node in attacks:
                attack = attack_node.fact
                assert isinstance(attack, (AttackFact, SpellFact))
                current = working.actors[step.source_entity_uuid]
                held = replace(motion_leg_contact(leg_actor, legs[-1], data, lead_end) if fraction
                               else replace(leg_actor, grid=start, elevation_steps=height, body_lift_px=initial_lift),
                               hp=current.normal_hp, life_state=current.life_state, facing=facing)
                group = bind_choreography(working, lineage_branch(lineage, attack_node), data,
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held},
                    activated_conditions=activated_conditions)
                source = contacts.get(str(attack.source_entity_uuid)) or _visible_contact(
                    working, attack.source_entity_uuid, data)
                sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
                    inputs=_motion_reduction_source(lineage_branch(lineage, attack_node)), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
                reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                                held.body_lift_px, attack.name))
                elapsed += group.complete_ms
                _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
                working = group.after
            body_start = elapsed
            duration *= 1 - fraction
        if step.committed:
            legs.append(MotionLeg(continuation, end, continuation_height, end_height,
                                  elapsed, elapsed + duration, body_start, arc_height_px=arc_height,
                                  curve_from=phase_from+(phase_to-phase_from)*fraction, curve_to=phase_to,
                                  initial_lift_px=initial_lift, speed_scale=speed_scale, path_bend=path_bend,
                                  passage_scale=passage_scale, passage_body_height_px=passage_body_height,
                                  passage_socket=passage_socket, passage_hold_fraction=passage_hold_fraction,
                                  lift_phase_edges=lift_phase_edges,
                                  support_riser=(abs(end_height-height)*HEIGHT_STEP_PIXELS*data.rig.TILE_W/TILE_WIDTH, fraction, 1.) if flight is not None else None))
            elapsed += duration
            _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, duration, 'motion_span',
                'movement.connector.durationMs' if connector_profile is not None else 'movement.walkStepDurationMs*distance/speed_scale',
                node.uuid, (TimingMeasurement('distance_cells', distance), TimingMeasurement('speed_scale', speed_scale),
                    TimingMeasurement('remaining_fraction', 1-fraction),
                    TimingMeasurement('base_duration_ms', connector_profile.durationMs if connector_profile is not None else context.walkStepDurationMs)))
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
                held = motion_leg_contact(leg_actor, legs[-1], data, legs[-1].end_ms)
                group = bind_choreography(working, entered, data,
                    contacts={**contacts, actor.actor_uuid: held}, activated_conditions=activated_conditions)
                sources.append(MotionGroupSource(root_uuid=group.root_uuid, offset_ms=elapsed,
                    inputs=_motion_reduction_source(entered), commits=group.state_commits,
                    before=group.before, states=group.states, timing_evidence=group.timing_evidence,
                    action_timing=bound_action_dependencies(group)))
                if group.complete_ms > 0:
                    reactions.append(MotionReaction(group, held, None, elapsed, elapsed + group.complete_ms, held.body_lift_px))
                    elapsed += group.complete_ms
                    _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, group.complete_ms, 'motion_span', 'group.complete_ms', group.root_uuid)
                    body_start = elapsed
                else:
                    contact_media.extend(replace(cue, start_ms=elapsed+cue.start_ms) for cue in group.contact_media)
                working = group.after
        working = reduce_lineage(working, branch)
        sources.append(_motion_reduction_source(branch))
        provenance.append(MotionStateProvenance(len(states), elapsed, "branch_fold", tuple(sources)))
        states.append((elapsed, working))
        settled = _visible_contact(working, step.source_entity_uuid, data, facing_for_delta(delta, data))
        uninterrupted = settled is not None
        if not step.committed:
            settled_lift = initial_lift * (1 - fraction)
            if settled is not None:
                settled = (motion_leg_contact(settled, legs[-1], data, legs[-1].end_ms)
                           if attacks and fraction else replace(settled, grid=continuation,
                               elevation_steps=continuation_height, body_lift_px=settled_lift))
                settled_lift = settled.body_lift_px
            break
    if isolated_point and not partial_jump:
        elapsed += context.walkStepDurationMs
        _record_motion_span(motion_evidence, lineage.root.uuid, elapsed, context.walkStepDurationMs, 'motion_dwell', 'movement.walkStepDurationMs')
    # Root completion can carry ordinary state without a direct child payload.
    working = reduce_lineage(working, lineage)
    provenance.append(MotionStateProvenance(len(states), elapsed, "root_reconciliation", (_motion_reduction_source(lineage),)))
    states.append((elapsed, working))
    if partial_jump and settled is not None and reactions:
        settled = replace(settled, grid=actor.grid, elevation_steps=actor.elevation_steps,
                          body_lift_px=actor.body_lift_px)
    if not legs and not states and not reactions:
        return None
    transitions = merge_world_transitions(world_transitions(target, states),
        tuple(replace(change, start_ms=change.start_ms + reaction.start_ms)
              for reaction in reactions for change in reaction.choreography.world_transitions))
    return _resolve_motion_body(MotionTimeline(actor, tuple(legs), connector_profile.bodyClip if connector_profile is not None else context.walkClip,
                          1 if connector_profile is not None else context.walkPlaybackSpeed,
                          arc_height, elapsed, tuple(reactions), settled, target,
                          staged.actors[root.source_entity_uuid], settled_lift, body_loops=connector_profile.bodyLoops if connector_profile is not None else True, states=tuple(states), state_provenance=tuple(provenance), root_uuid=lineage.root.uuid, timing_evidence=tuple(motion_evidence),
                          world_transitions=transitions,
                          residue_reveals=tuple(replace(change,
                              start_ms=change.start_ms + reaction.start_ms,
                              end_ms=change.end_ms + reaction.start_ms)
                              for reaction in reactions for change in reaction.choreography.residue_reveals),
                          contact_media=tuple(contact_media),
                          animation_id=connector_profile.animationId if connector_profile is not None else None,
                          body_frame_keys=connector_profile.bodyFrameKeys if connector_profile is not None else ()),
                          data, root, context.walkRecovery)


def passage_weight(phase: float, hold_fraction: float) -> float:
    """An authored passage holds at sill height; ordinary arcs remain parabolic."""
    if not hold_fraction:
        return 4 * phase * (1 - phase)
    edge = min(1., min(phase, 1 - phase) / ((1 - hold_fraction) / 2))
    return edge * edge * (3 - 2 * edge)


def motion_leg_contact(actor: ActorContact, leg: MotionLeg, data: AnimationData,
                       elapsed_ms: float) -> ActorContact:
    """One world trajectory for the body and its registered attached media."""
    progress = min(1.0, max(0.0, (elapsed_ms-leg.start_ms)/(leg.end_ms-leg.start_ms)))
    delta = leg.end[0]-leg.start[0], leg.end[1]-leg.start[1]
    curve = leg.curve_from+(leg.curve_to-leg.curve_from)*progress
    if leg.lift_phase_edges is None:
        weight = passage_weight(curve, leg.passage_hold_fraction)
    else:
        takeoff, landing = leg.lift_phase_edges
        weight = airborne_weight(curve, takeoff, landing)
    lift = (leg.arc_height_px * weight
            + leg.initial_lift_px * (1 - curve))
    if leg.support_riser is not None:
        riser, first, last = leg.support_riser
        edge_progress = first + (last - first) * progress
        # At the tile boundary the feet must clear the higher support, including
        # late rises/early descents where the whole-path envelope is already low.
        lift = max(lift, riser * min(edge_progress, 1 - edge_progress))
    bend_weight = 4 * curve * (1 - curve)
    return replace(actor, grid=(leg.start[0]+delta[0]*progress+leg.path_bend[0]*bend_weight,
                               leg.start[1]+delta[1]*progress+leg.path_bend[1]*bend_weight),
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
        held_leg = next((leg for leg in reversed(timeline.legs)
                         if leg.lift_phase_edges is not None and leg.end_ms <= active.start_ms), None)
        active_bodies = [body for body in bodies if body.clip != "Idle"]
        body = (active_bodies[-1] if active_bodies else
                _motion_leg_body(timeline, held_leg, contact, data, held_leg.end_ms)
                if held_leg is not None and contact.body_lift_px > 0 else
                bodies[-1] if bodies else sample_idle_body(data, contact, elapsed))
        return MotionSample(contact, body, active.lift_px, False, active.choreography,
                            elapsed - active.start_ms, tuple(vitals.values()), displayed, active_sample)
    if (timeline.recovery_body is not None and timeline.recovery_body.actor.enabled
            and timeline.recovery_start_ms is not None and timeline.recovery_start_ms <= elapsed < timeline.complete_ms
            and timeline.settled_contact is not None):
        contact = timeline.settled_contact
        return MotionSample(contact, sample_context_body(data, contact, timeline.recovery_body,
            elapsed - timeline.recovery_start_ms), contact.body_lift_px, False,
            displayed_vitals=tuple(vitals.values()), displayed=displayed)
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
    contact = motion_leg_contact(timeline.actor, leg, data, elapsed)
    facing, lift = contact.facing, contact.body_lift_px
    current = vitals.get(contact.actor_uuid)
    if current is not None:
        contact = replace(contact, hp=current.hp, life_state=current.life_state)
    if complete and timeline.settled_contact is not None:
        contact = replace(timeline.settled_contact, facing=facing)
    return MotionSample(contact, _motion_leg_body(timeline, leg, contact, data, elapsed, clip),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)


def _motion_leg_body(timeline: MotionTimeline, leg: MotionLeg, contact: ActorContact,
                     data: AnimationData, elapsed: float, clip: str | None = None) -> BodySample:
    """One source pose for moving and paused portions of the same admitted leg."""
    progress = min(1., max(0., (elapsed-leg.start_ms)/(leg.end_ms-leg.start_ms)))
    selected = clip or timeline.clip
    metadata = body_clip(data, contact, selected)
    if timeline.body_context is not None and selected == timeline.clip:
        phase = leg.curve_from + (leg.curve_to - leg.curve_from) * progress
        frame = context_frame(timeline.body_context, metadata, (elapsed - leg.body_start_ms) * leg.speed_scale,
                              progress=phase if not timeline.body_loops else None)
    elif not timeline.body_loops and selected == timeline.clip:
        phase = leg.curve_from + (leg.curve_to - leg.curve_from) * progress
        if timeline.body_frame_keys:
            frame = timeline.body_frame_keys[-1][1]
            for (start, first), (end, last) in zip(timeline.body_frame_keys, timeline.body_frame_keys[1:]):
                if phase <= end:
                    frame = round(first + (last - first) * (phase - start) / (end - start))
                    break
            if frame >= metadata.frames:
                raise ValueError(f"{timeline.animation_id} requests missing {selected} frame {frame}")
        else:
            frame = min(metadata.frames - 1, int(phase * metadata.frames))
    else:
        frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed * leg.speed_scale,
                           metadata.frames, loop=True)
    phase = leg.curve_from + (leg.curve_to - leg.curve_from) * progress
    tuck = passage_weight(phase, leg.passage_hold_fraction) ** 2
    scale = (1 + (leg.passage_scale[0] - 1) * tuck,
             1 + (leg.passage_scale[1] - 1) * tuck)
    socket, weight = leg.passage_socket, tuck
    if leg.lift_phase_edges is not None and "airborne_support" in body_rig(data, contact).pose_sockets:
        socket = "airborne_support"
        takeoff, landing = leg.lift_phase_edges
        weight = airborne_weight(phase, takeoff, landing)
    return BodySample(contact.actor_uuid, selected, frame, contact.facing,
        scale=scale, scale_anchor_height_px=leg.passage_body_height_px,
        registration_socket=socket, registration_weight=weight)
