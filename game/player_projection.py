"""Project private recorded facts into the public player packet.

Perception is already resolved by native events. This module selects existing
authority, remembers last-observed world values, and copies committed facts;
it never asks the live engine what an observer can see.
"""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.types.senses import SensesSnapshot, reduce_senses_snapshot
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.core.base_actions import ActionEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.events import (
    DamageAppliedEvent, DeathSaveEvent, EncounterEvent, EntityCreatedEvent, ItemDestructionEvent,
    Event, ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, HealEvent, LifeStateChangeEvent,
    RoundEvent, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType, SpatialEffectChangeEvent,
    StepMovementEvent, TakeDamageEvent, TemporaryHitPointsChangedEvent, TurnEvent, WorldInitializedEvent, SavingThrowEvent,
)
from dnd.core.item_types import ItemIntegrity, ItemLocation, ItemPresentationState
from dnd.types.world import CardinalDirection
from dnd.types.residues import BodyReleaseRegion, BodyReleaseResult, ObjectResidueState
from game.actor_facts import ActorState, ConditionFact, PresentationTarget
from game.actor_projection import actor_fact_owner, actor_from_birth, apply_actor_fact
from game.player_facts import (
    ActionCancellation, ActionFact, ActionReaction, AttackFact, ConditionChangeFact, ContentAttribution, DamageFact,
    DeathSaveFact, EquipmentFact, FloorItem, ForcedMovementFact, PortalTransferFact, MechanismActivationFact, HealFact, ItemChargeFact, LifeFact,
    MovementFact, ObjectDamageFact, ObjectDestroyedFact, PlayerActor, PlayerFact, PlayerInitialization, PlayerLineage,
    PlayerNode, PlayerObject, PlayerObservation, PlayerSequence, PlayerState,
    PlayerWorld, SensoryFact, ShoveFact, SpatialFact, SpatialEffectStateFact, SpellFact, StepFact, TurnFact,
    VersionRow, VisualItem, VisualLoadout, WorldUpdate, TemporaryHitPointsFact, SavingThrowFact,
)
from game.presentation import ActorAdmission, CompletedLineage, IntervalEnvelope, ObjectiveRow, apply_world_fact
from game.replay import RecordedSequence
from game.player_reduction import apply_world_update


def _identified(event: Event, identity: UUID | None, observer: UUID) -> bool:
    return identity is not None and (identity == observer or str(observer) in
        event.identified_entity_observer_uuids.get(str(identity), set()))


def _position_allowed(event: Event, position: tuple[int, int], observer: UUID) -> bool:
    return str(observer) in event.located_position_observer_uuids.get(
        f"{position[0]},{position[1]}", set())


def _step_allowed(event: StepMovementEvent, observer: UUID) -> bool:
    return _identified(event, event.source_entity_uuid, observer) and (
        event.source_entity_uuid == observer or all(_position_allowed(event, position, observer)
            for position in (event.disclosed_path or (event.from_position, event.to_position))))


def _forced_allowed(event: ForcedMovementEvent, observer: UUID) -> bool:
    return _identified(event, event.target_entity_uuid, observer) and (
        observer in (event.source_entity_uuid, event.target_entity_uuid)
        or all(_position_allowed(event, point, observer) for point in (event.start_position, event.end_position)))


def _visual_loadout(actor: ActorState) -> VisualLoadout:
    items = {item.item_uuid: item for item in actor.items}
    return VisualLoadout(active_weapon_set=actor.active_weapon_set, layers=tuple(
        VisualItem(slot=slot, item_uuid=identity, item_id=items[identity].item_id,
            item_kind=items[identity].item_kind, visual_item_name=items[identity].visual_item_name,
            visual_variant_id=items[identity].visual_variant_id,
            equipped_visual_policy=items[identity].equipped_visual_policy)
        for slot, identity in actor.equipment))


def _public_actor(actor: ActorState, observer: UUID) -> PlayerActor:
    return PlayerActor(uuid=actor.uuid, name=actor.name,
        character_body_id=actor.character_body_id, creature_content_ref=actor.creature_content_ref,
        appearance=actor.appearance, visual_loadout=_visual_loadout(actor),
        normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp,
        temporary_hp=actor.temporary_hp, life_state=actor.life_state,
        temporary_hp_grant=actor.temporary_hp_grant,
        armor_class=actor.armor_class, conditions=actor.conditions,
        resolved_size=actor.resolved_size, structural_base_size=actor.structural_base_size,
        last_visual_position=actor.last_visual_position,
        occupancy_layer=(actor.occupancy_layer
                         if actor.uuid == observer or actor.last_visual_position is not None else None),
        controlled_items=actor.items if actor.uuid == observer else None)


def _sensory_fact(event: SensoryUpdateEvent) -> SensoryFact:
    return SensoryFact(observer_uuid=event.observer_uuid, initial=event.initial,
        observer_position=event.observer_position, observer_position_changed=event.observer_position_changed,
        effective_light_levels_changed=dict(event.effective_light_levels_changed),
        hazardous_cells_changed=dict(event.hazardous_cells_changed),
        spatial_effects_changed=dict(event.spatial_effects_changed),
        spatial_effects_removed=frozenset(event.spatial_effects_removed),
        cause_event_uuid=event.cause_event_uuid,
        visible_cells_added=tuple(event.visible_cells_added), visible_cells_removed=tuple(event.visible_cells_removed),
        seen_cells_added=tuple(event.seen_cells_added),
        entity_contacts_changed=dict(event.entity_contacts_changed),
        entity_contacts_removed=frozenset(event.entity_contacts_removed),
        object_contacts_changed=dict(event.object_contacts_changed),
        object_contacts_removed=frozenset(event.object_contacts_removed),
        sense_modes_changed=event.sense_modes_changed,
        sense_modes=tuple(event.sense_modes) if event.sense_modes is not None else None,
        passive_perception_changed=event.passive_perception_changed,
        passive_perception=event.passive_perception, visual_access_changed=event.visual_access_changed,
        visual_access=event.visual_access, paths_dirty=event.paths_dirty)


def _project_fact(event: Event, observer: UUID, actors: dict[UUID, ActorState],
                  condition: ConditionFact | None, events: tuple[Event, ...],
                  admissions: tuple[ActorAdmission, ...], known: set[UUID],
                  observed_objects: set[UUID], senses: SensesSnapshot | None,
                  declaration_senses: SensesSnapshot | None = None) -> PlayerFact | None:
    source = event.source_entity_uuid if event.source_entity_uuid in known and _identified(event, event.source_entity_uuid, observer) else None
    target = event.target_entity_uuid if event.target_entity_uuid in known and _identified(event, event.target_entity_uuid, observer) else None
    match event:
        case SpatialEffectChangeEvent():
            if event.operation is SpatialEffectChangeOperation.REMOVED:
                # Removal's sensory child has already dropped the field. Only
                # its own entry contact can witness this mechanical removal;
                # a remembered field or ordinary sight loss grants nothing.
                if declaration_senses is None or senses is None:
                    return None
                observed = declaration_senses.spatial_effects.get(event.spatial_effect_uuid)
                if observed is None:
                    return None
                positions = tuple(position for position in event.previous_positions
                    if position in observed.positions
                    and (position in declaration_senses.visible or position in observed.visible_volume_positions)
                    and position in senses.visible)
                return SpatialEffectStateFact(spatial_effect_uuid=event.spatial_effect_uuid,
                    positions=positions, previous_state=None, state=None,
                    operation=event.operation) if positions else None
            observed = senses.spatial_effects.get(event.spatial_effect_uuid) if senses is not None else None
            if observed is None or (event.operation is not SpatialEffectChangeOperation.CREATED
                    and (event.previous_trap_state is None or event.trap_state is None)
                    and (event.previous_pressed is None or event.pressed is None)):
                return None
            # Fixture identity and cells are granted by this observer's recorded
            # sensory after-values. Unlike movement, native spatial-condition
            # events do not carry separate coordinate-grant metadata.
            positions = tuple(position for position in event.affected_positions
                if position in observed.positions and senses is not None
                and (position in senses.visible or position in observed.visible_volume_positions))
            return SpatialEffectStateFact(spatial_effect_uuid=event.spatial_effect_uuid,
                positions=positions, previous_state=event.previous_trap_state, state=event.trap_state,
                operation=event.operation, previous_pressed=event.previous_pressed,
                pressed=event.pressed) if positions else None
        case SensoryUpdateEvent():
            return _sensory_fact(event) if event.observer_uuid == observer else None
        case StepMovementEvent():
            if not _step_allowed(event, observer):
                return None
            return StepFact(source_entity_uuid=event.source_entity_uuid,
                from_position=event.from_position, to_position=event.to_position,
                from_elevation_feet=event.from_elevation_feet, to_elevation_feet=event.to_elevation_feet,
                disclosed_path=event.disclosed_path, trajectory=event.trajectory,
                provocation_policy=event.provocation_policy, committed=event.committed,
                resolved_speed_feet=event.resolved_speed_feet,
                movement_mode=event.movement_mode, from_layer=event.from_layer, to_layer=event.to_layer)
        case MovementEvent() | JumpEvent():
            steps = tuple(row for row in events if isinstance(row, StepMovementEvent)
                          and row.parent_lineage == event.lineage_uuid)
            observed = (source is not None or any(_identified(row, event.source_entity_uuid, observer) for row in steps)
                        or any(row.actor.uuid == event.source_entity_uuid for row in admissions))
            if not observed:
                return None
            atomic = isinstance(event, JumpEvent) and (
                event.source_entity_uuid == observer or bool(steps) and all(_step_allowed(row, observer) for row in steps)
                and set(event.path or ()).issubset({position for row in steps
                    for position in (row.disclosed_path or (row.from_position, row.to_position))}))
            # The trajectory ends at its last committed step. A portal or paid
            # retreat can change the native action's final position afterward.
            landing = max((row for row in steps if row.committed), key=lambda row: row.path_index, default=None)
            return MovementFact(source_entity_uuid=event.source_entity_uuid, trajectory=event.trajectory,
                start_position=event.start_position if atomic else None,
                end_position=(landing.to_position if landing is not None else event.start_position) if atomic else None,
                requested_end_position=event.requested_end_position if atomic and (
                    source == observer or event.requested_end_position in (event.path or ())) else None,
                path=tuple(event.path or ()) if atomic else (),
                start_elevation_feet=event.start_elevation_feet if atomic and isinstance(event, JumpEvent) else None,
                end_elevation_feet=(landing.to_elevation_feet if landing is not None else event.start_elevation_feet)
                    if atomic and isinstance(event, JumpEvent) else None,
                movement_mode=(event.movement_mode if event.source_entity_uuid == observer
                               or any(_step_allowed(row, observer) for row in steps) else None),
                start_layer=event.start_layer if atomic or event.source_entity_uuid == observer else None,
                end_layer=event.end_layer if atomic or event.source_entity_uuid == observer else None)
        case AttackEvent():
            if source is None or target is None:
                return None
            return AttackFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name, weapon_slot=event.weapon_slot,
                attack_outcome=event.attack_outcome, damage_types=tuple(event.damage_types),
                intercepted_by_condition_uuid=event.intercepted_by_condition_uuid,
                source_item_id=event.source_item_presentation.item_id if event.source_item_presentation is not None else None)
        case SpellEvent():
            if source is None or (event.target_entity_uuid is not None and target is None):
                return None
            area = event.area_geometry is not None
            if not area and any(not _identified(event, identity, observer) for identity in event.declared_target_entity_uuids):
                return None
            source_position = event.source_position
            if source_position is not None and event.source_entity_uuid != observer and not _position_allowed(event, source_position, observer):
                # Locating an actor at completion grants its received contact,
                # not an earlier declaration coordinate (e.g. teleport origin).
                contact = senses.entities.get(source) if senses is not None else None
                declared_contact = declaration_senses.entities.get(source) if declaration_senses is not None else None
                observed_declaration = (declared_contact is not None and declared_contact.visual
                    and declared_contact.position == source_position)
                if not observed_declaration and (
                        str(observer) not in event.located_entity_observer_uuids.get(str(source), set())
                        or contact is None or contact.position != source_position):
                    source_position = None
            area_position = event.aoe_position
            if area_position is not None and not (_position_allowed(event, area_position, observer)
                    or senses is not None and area_position in senses.visible
                    or declaration_senses is not None and area_position in declaration_senses.visible):
                area_position = None
            resolved_positions = event.resolved_area_positions
            if resolved_positions is not None:
                resolved_positions = tuple(position for position in resolved_positions
                    if _position_allowed(event, position, observer)
                    or senses is not None and position in senses.visible)
            return SpellFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name, source_position=source_position,
                cast_origin=event.cast_origin,
                source_item_uuid=event.source_item_uuid if event.source_item_uuid in observed_objects else None,
                declared_target_entity_uuids=tuple(identity for identity in event.declared_target_entity_uuids
                    if not area or identity in known and _identified(event, identity, observer)),
                application_id=event.application_id, application_index=event.application_index,
                attack_outcome=event.attack_outcome,
                effect_id=event.effect_id,
                aoe_position=area_position,
                area_geometry=event.area_geometry if area_position is not None else None,
                area_propagation=event.area_propagation,
                resolved_area_positions=resolved_positions,
                suppressions=tuple(SpellSuppression(provider_uuid=suppression.provider_uuid,
                    positions=tuple(position for position in suppression.positions
                        if _position_allowed(event, position, observer)
                        or senses is not None and position in senses.visible))
                    for suppression in event.suppressions
                    if (senses is not None and suppression.provider_uuid in senses.spatial_effects)
                    or (declaration_senses is not None and suppression.provider_uuid in declaration_senses.spatial_effects)))
        case ShoveEvent():
            return (None if source is None or target is None else ShoveFact(
                source_entity_uuid=source, target_entity_uuid=target, behavior_id=event.behavior_id,
                contest_success=event.contest_success, push_distance=event.push_distance,
                knocked_prone=event.knocked_prone))
        case MechanismActivationEvent():
            observed = senses.spatial_effects.get(event.mechanism_uuid) if senses is not None else None
            if observed is None and declaration_senses is not None:
                observed = declaration_senses.spatial_effects.get(event.mechanism_uuid)
            # Environmental discharges have no moving actor from which to infer
            # coordinate grants. Preserve this release's already witnessed cells
            # when its own cloud obscures them before completion.
            visible = set(senses.visible) if senses is not None else set()
            if declaration_senses is not None:
                visible.update(declaration_senses.visible)
            positions = tuple(position for position in event.affected_positions if position in visible)
            origin = event.origin_position if event.origin_position in visible else None
            if origin is None and not positions:
                return None
            return MechanismActivationFact(mechanism_uuid=event.mechanism_uuid if observed is not None else None,
                mechanism_content_id=event.mechanism_content_ref.content_id, target_entity_uuid=target,
                origin_position=origin, direction=event.direction, affected_positions=positions,
                end_position=event.end_position if event.end_position in visible else None,
                committed=event.committed)
        case PortalTransferEvent():
            if target is None:
                return None
            departure = event.start_position if (target == observer
                or _position_allowed(event, event.start_position, observer)) else None
            arrival = event.end_position if event.committed and (target == observer
                or _position_allowed(event, event.end_position, observer)) else None
            if departure is None and arrival is None:
                return None
            return PortalTransferFact(target_entity_uuid=target,
                # A revealed hatch observation may complete after its nested
                # transfer. Join only this observer's actual retained evidence.
                portal_uuid=event.portal_uuid if departure is not None and (
                    senses is not None and event.portal_uuid in senses.spatial_effects
                    or declaration_senses is not None and event.portal_uuid in declaration_senses.spatial_effects
                    or any(isinstance(row, SensoryUpdateEvent) and row.observer_uuid == observer
                        and event.portal_uuid in row.spatial_effects_changed for row in events)) else None,
                start_position=departure, end_position=arrival, committed=event.committed,
                portal_content_id=event.portal_content_ref.content_id if event.portal_content_ref is not None else None)
        case ForcedMovementEvent():
            if target is None or not _forced_allowed(event, observer):
                return None
            return ForcedMovementFact(source_entity_uuid=source, target_entity_uuid=target,
                start_position=event.start_position, end_position=event.end_position, actual_distance=event.actual_distance)
        case TakeDamageEvent():
            return (None if target is None else DamageFact(stage="taken", source_entity_uuid=source,
                target_entity_uuid=target, intercepted_by_condition_uuid=event.intercepted_by_condition_uuid))
        case DamageAppliedEvent():
            if target is None:
                return None
            release = None
            recorded = event.body_release
            if recorded is not None:
                contact = senses.entities.get(target) if senses is not None else None
                located = (target == observer or _position_allowed(event, recorded.position, observer)
                    or str(observer) in event.located_entity_observer_uuids.get(str(target), set())
                    and contact is not None and contact.visual and contact.position == recorded.position)
                if not located:
                    # Entry payloads can complete before their sensory child.
                    # A disclosed native edge already grants its reached cell.
                    by_lineage = {row.lineage_uuid: row for row in events}
                    parent = event.parent_lineage
                    while parent is not None and parent in by_lineage:
                        ancestor = by_lineage[parent]
                        if (isinstance(ancestor, StepMovementEvent)
                                and ancestor.source_entity_uuid == target and _step_allowed(ancestor, observer)
                                and recorded.position in (ancestor.disclosed_path or (
                                    ancestor.from_position, ancestor.to_position))
                                or isinstance(ancestor, ForcedMovementEvent)
                                and ancestor.target_entity_uuid == target and _forced_allowed(ancestor, observer)
                                and recorded.position in (ancestor.start_position, ancestor.end_position)):
                            located = True
                            break
                        parent = ancestor.parent_lineage
                if located:
                    deposited = recorded.deposited_position
                    if (deposited is not None and deposited != recorded.position
                            and not _position_allowed(event, deposited, observer)
                            and (senses is None or deposited not in senses.visible)):
                        deposited = None
                    regions = []
                    for region in recorded.regions:
                        positions = tuple(cell for cell in region.positions
                            if cell == recorded.position or _position_allowed(event, cell, observer)
                            or senses is not None and cell in senses.visible)
                        if positions:
                            regions.append(BodyReleaseRegion(ellipse=region.ellipse,
                                elevation_steps=region.elevation_steps, positions=positions))
                    release = BodyReleaseResult(release_id=recorded.release_id, position=recorded.position,
                        occupancy_layer=recorded.occupancy_layer, deposited_position=deposited,
                        pattern=recorded.pattern, critical_hit=recorded.critical_hit, regions=tuple(regions),
                        primary_damage_type=recorded.primary_damage_type,
                        secondary_damage_type=recorded.secondary_damage_type)
            return DamageFact(stage="applied", source_entity_uuid=source, target_entity_uuid=target,
                applied_damage=event.applied_damage, resulting_normal_hp=event.resulting_normal_hp,
                resulting_temporary_hp=event.resulting_temporary_hp, damage_type=event.damage_type,
                body_release=release, effect_id=event.effect_id if event.effect_id is not None and senses is not None
                    and any(effect.content_ref.identity_key == event.effect_id
                            for effect in senses.spatial_effects.values()) else None)
        case HealEvent():
            return (None if target is None else HealFact(source_entity_uuid=source, target_entity_uuid=target,
                actual_healing=event.actual_healing, was_blocked=event.was_blocked,
                source_condition_uuid=event.source_condition_uuid if target in actors and any(
                    member.condition_uuid == event.source_condition_uuid
                    and member.category is not ConditionCategory.INTERNAL
                    for member in actors[target].conditions) else None,
                resulting_normal_hp=event.resulting_normal_hp, resulting_temporary_hp=event.resulting_temporary_hp))
        case TemporaryHitPointsChangedEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer)
                    else TemporaryHitPointsFact(entity_uuid=event.entity_uuid,
                        resulting_temporary_hp=event.resulting_temporary_hp, grant=event.grant))
        case LifeStateChangeEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else LifeFact(
                entity_uuid=event.entity_uuid, previous_state=event.previous_state, new_state=event.new_state,
                reason=event.reason, normal_hit_points=event.normal_hit_points))
        case DeathSaveEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else DeathSaveFact(
                entity_uuid=event.entity_uuid, natural_roll=event.natural_roll, succeeded=event.succeeded))
        case SavingThrowEvent():
            return (None if target is None or event.result is None else SavingThrowFact(
                target_entity_uuid=target, ability_name=event.ability_name, succeeded=event.result,
                effect_id=event.saving_throw_context.effect_id if event.saving_throw_context is not None else None))
        case ItemChargeConsumptionEvent():
            return (ItemChargeFact(source_entity_uuid=observer, item_uuid=event.item_uuid,
                charges_after=event.charges_after, stack_count_after=event.stack_count_after,
                item_destroyed=event.item_destroyed) if event.source_entity_uuid == observer else None)
        case EquipmentEvent() | ItemLocationStateEvent():
            owner = actor_fact_owner(event)
            if owner is None or owner not in known or owner not in actors or not _identified(event, owner, observer):
                return None
            actor = actors[owner]
            return EquipmentFact(source_entity_uuid=owner, visual_loadout=_visual_loadout(actor),
                armor_class=actor.armor_class, controlled_items=actor.items if owner == observer else None)
        case SpatialChangeEvent():
            identified_entity = event.entity_uuid if _identified(event, event.entity_uuid, observer) else None
            own_position = identified_entity == observer
            if event.change_type not in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT,
                                         SpatialChangeType.PERCEIVABILITY_CHANGED, SpatialChangeType.MOVEMENT_COLLISION):
                return None
            parent = next((row for row in events if row.lineage_uuid == event.parent_lineage), None)
            parent_geometry = (
                isinstance(parent, ForcedMovementEvent) and parent.target_entity_uuid == event.entity_uuid
                and _forced_allowed(parent, observer)
                or isinstance(parent, StepMovementEvent) and parent.source_entity_uuid == event.entity_uuid
                and _step_allowed(parent, observer))
            located_arrival = (event.change_type is SpatialChangeType.ENTITY_ENTERED
                and str(observer) in event.located_entity_observer_uuids.get(str(event.entity_uuid), set()))
            if identified_entity is None or not (own_position or parent_geometry or located_arrival
                                                or _position_allowed(event, event.position, observer)):
                return None
            departure = (event.position if event.change_type is SpatialChangeType.ENTITY_LEFT
                         else event.old_position)
            arrival = (event.position if event.change_type is SpatialChangeType.ENTITY_ENTERED
                       else event.old_position)
            departure_allowed = own_position or parent_geometry or (
                departure is not None and _position_allowed(event, departure, observer))
            arrival_allowed = own_position or parent_geometry or located_arrival or (
                arrival is not None and _position_allowed(event, arrival, observer))
            return SpatialFact(change_type=event.change_type, entity_uuid=identified_entity, position=event.position,
                previous_occupancy_layer=event.previous_occupancy_layer if departure_allowed else None,
                occupancy_layer=event.occupancy_layer if arrival_allowed else None)
        case TurnEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=event.entity_uuid
                if _identified(event, event.entity_uuid, observer) else None, round_number=event.round_number)
        case RoundEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=event.round_number)
        case EncounterEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=None)
        case _ if condition is not None:
            return (None if target is None or condition.category is ConditionCategory.INTERNAL else
                ConditionChangeFact(target_entity_uuid=target, event_type=event.event_type, condition=condition,
                    consumed=condition.consumed))
        case CounterspellReactionEvent():
            return (None if source is None or target is None else ActionFact(
                source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name,
                reaction=ActionReaction(triggered_lineage_uuid=event.triggered_lineage_uuid,
                    succeeded=event.succeeded, automatic=event.automatic)))
        case ActionEvent():
            object_target = event.target_entity_uuid if event.target_entity_uuid in observed_objects else target
            return (None if source is None else ActionFact(source_entity_uuid=source, target_entity_uuid=object_target,
                behavior_id=event.behavior_id, name=event.name,
                source_item_uuid=event.source_item_uuid if event.source_item_uuid in observed_objects else None))
    return None


def _content_attributions(event: Event, fact: PlayerFact | None, observer: UUID,
                          disclosed_lineages: set[UUID]) -> tuple[ContentAttribution, ...]:
    result: list[ContentAttribution] = []
    if fact is not None and isinstance(event, ActionEvent) and event.behavior_id is not None:
        result.append(ContentAttribution(role="behavior", behavior_id=event.behavior_id,
            provided_by_id=event.provided_by_id, origin_root_id=event.origin_root_id))
    if fact is not None and isinstance(event, ActionEvent) and event.source_item_presentation is not None:
        result.append(ContentAttribution(role="source_item", behavior_id=event.source_item_presentation.item_id))
    for evidence in event.effective_handler_presentations:
        if not _identified(event, evidence.source_entity_uuid, observer):
            continue
        emitted = tuple(identity for identity in evidence.emitted_lineage_uuids if identity in disclosed_lineages)
        if evidence.outcome is HandlerDispatchOutcome.EMITTED_EVENTS and not emitted:
            continue
        result.append(ContentAttribution(role="effective_handler", behavior_id=evidence.behavior_id,
            provided_by_id=evidence.provided_by_id, origin_root_id=evidence.origin_root_id,
            source_entity_uuid=evidence.source_entity_uuid, triggering_event_uuid=evidence.triggering_event_uuid,
            triggering_lineage_uuid=evidence.triggering_lineage_uuid,
            emitted_lineage_uuids=emitted, handler_name=evidence.handler_name,
            dispatch_index=evidence.dispatch_index, outcome=evidence.outcome))
    return tuple(result)


def _floor_item(item: ItemPresentationState, residues: tuple[ObjectResidueState, ...]) -> FloorItem:
    return FloorItem(item_uuid=item.item_uuid, item_id=item.item_id, name=item.name,
        visual_item_name=item.visual_item_name, visual_variant_id=item.visual_variant_id,
        map_char=item.map_char, boundary_structure=item.boundary_structure,
        blocks_propagation=item.blocks_propagation,
        is_open=item.is_open, is_lit=item.is_lit, is_engaged=item.is_engaged,
        surface_residues=residues, current_hit_points=item.current_hit_points, maximum_hit_points=item.maximum_hit_points,
        concentration_capacity=item.concentration_capacity, concentration_slots=item.concentration_slots,
        door_mechanism=item.door_mechanism, door_swing=item.door_swing, remnant_state=item.remnant_state,
        integrity=item.integrity, destruction_outcome=item.destruction_outcome)


_DELTAS = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
           CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}
_OPPOSITE = {CardinalDirection.NORTH: CardinalDirection.SOUTH,
             CardinalDirection.SOUTH: CardinalDirection.NORTH,
             CardinalDirection.EAST: CardinalDirection.WEST,
             CardinalDirection.WEST: CardinalDirection.EAST}


def _object_observed(world: PresentationTarget, identity: UUID) -> bool:
    senses = world.senses
    if senses is None:
        return False
    if identity in senses.objects:
        return True
    obj = world.objects[identity]
    direction = obj.placement.boundary_direction
    if direction is None or obj.item.boundary_structure is None:
        return False
    x, y = obj.placement.position
    dx, dy = _DELTAS[direction]
    # Boundary appearance belongs to either observed incident support, including
    # a wall which stops its author's cell from entering optical visibility.
    return (x, y) in senses.visible or (x + dx, y + dy) in senses.visible


def _observed_object(world: PresentationTarget, remembered: PlayerState, identity: UUID) -> PlayerObject:
    """Refresh seen wall faces while preserving the last observation of others."""
    obj = world.objects[identity]
    direction = obj.placement.boundary_direction
    visible_faces: set[CardinalDirection] = set()
    if direction is not None and world.senses is not None:
        x, y = obj.placement.position
        dx, dy = _DELTAS[direction]
        if (x, y) in world.senses.visible:
            visible_faces.add(_OPPOSITE[direction])
        if (x + dx, y + dy) in world.senses.visible:
            visible_faces.add(direction)
    previous = remembered.objects.get(identity)
    retained: dict[UUID, ObjectResidueState] = {}
    if previous is not None:
        for residue in previous.item.surface_residues:
            faces = tuple(face for face in residue.faces if face not in visible_faces)
            if faces:
                retained[residue.condition_uuid] = residue.model_copy(update={"faces": faces})
    for residue in obj.item.surface_residues:
        faces = {face for face in residue.faces if face in visible_faces}
        if not faces:
            continue
        prior = retained.get(residue.condition_uuid)
        if prior is not None:
            faces.update(prior.faces)
        retained[residue.condition_uuid] = residue.model_copy(update={
            "faces": tuple(sorted(faces, key=lambda face: face.value)),
        })
    return PlayerObject(placement=obj.placement, item=_floor_item(obj.item,
        tuple(retained[identity] for identity in sorted(retained, key=str))))


def _world_update(world: PresentationTarget, remembered: PlayerState, event_uuid: UUID) -> WorldUpdate | None:
    senses = world.senses
    if senses is None or world.world is None:
        return None
    tiles = tuple(world.tiles[position] for position in sorted(senses.visible) if position in world.tiles
                  and remembered.tiles.get(position) != world.tiles[position])
    observed = {identity: _observed_object(world, remembered, identity)
                for identity in world.objects if _object_observed(world, identity)}
    objects = tuple(observed[identity] for identity in sorted(observed, key=str)
                    if remembered.objects.get(identity) != observed[identity])
    removed = tuple(identity for identity, obj in remembered.objects.items()
                    if identity not in observed
                    and any(position in senses.visible for position in obj.placement.positions))
    connectors = tuple(row for row in world.world.connectors
                       if all(point in senses.visible for point in row.endpoints))
    if not tiles and not objects and not removed and connectors == remembered.connectors:
        return None
    update = WorldUpdate(event_uuid=event_uuid, tiles=tiles, objects=objects,
                         objects_removed=removed, connectors=connectors)
    apply_world_update(remembered, update)
    return update


def _versions(rows: tuple[ObjectiveRow, ...]) -> tuple[VersionRow, ...]:
    return tuple(VersionRow(source_index=row.source_index, event_uuid=row.event_uuid,
                            lineage_uuid=row.lineage_uuid) for row in rows)


def _project_nodes(events: tuple[Event, ...], versions: tuple[VersionRow, ...],
                   admissions: tuple[ActorAdmission, ...], conditions: tuple[ConditionFact, ...],
                   private_world: PresentationTarget, private_actors: dict[UUID, ActorState],
                   remembered: PlayerState) -> tuple[tuple[PlayerNode, ...], tuple[PlayerObservation, ...], tuple[WorldUpdate, ...]]:
    observer = remembered.observer_uuid
    indexes = {row.event_uuid: row.source_index for row in versions}
    facts = {row.event_uuid: row for row in conditions}
    observations: list[PlayerObservation] = []
    updates: list[WorldUpdate] = []
    nodes: list[PlayerNode] = []
    pending = iter(sorted(admissions, key=lambda row: indexes[row.event_uuid]))
    admission = next(pending, None)
    by_lineage = {event.lineage_uuid: event for event in events}
    # A delivery can obscure itself; a field removal clears its contact through
    # a sensory child before completing. Retain each event's entry sight: a
    # nested event must not borrow its outer root's earlier observation.
    delivery_starts: dict[UUID, int] = {}
    for version in versions:
        declared = by_lineage.get(version.lineage_uuid)
        if (isinstance(declared, MechanismActivationEvent)
                or isinstance(declared, SpellEvent) and declared.area_geometry is not None
                or isinstance(declared, SpatialEffectChangeEvent)
                and declared.operation is SpatialEffectChangeOperation.REMOVED):
            delivery_starts.setdefault(version.lineage_uuid, version.source_index)
    pending_deliveries = iter(sorted(delivery_starts.items(), key=lambda row: row[1]))
    next_delivery = next(pending_deliveries, None)
    delivery_declarations: dict[UUID, SensesSnapshot | None] = {}
    # A break's sensory children can run before its completion. Capture the
    # contact at the integrity transition's entry; old recordings instead
    # witness the removal which preceded their replacement-object fact.
    destroyed_ids = {event.item_state.item_uuid for event in events
                     if isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED}
    explicit_destructions = {event.item_uuid for event in events if isinstance(event, ItemDestructionEvent)}
    removal_starts: dict[UUID, int] = {}
    for version in versions:
        removed = by_lineage.get(version.lineage_uuid)
        if isinstance(removed, ItemDestructionEvent) and not removed.canceled:
            removal_starts.setdefault(removed.item_uuid, version.source_index)
        elif (isinstance(removed, SpatialChangeEvent) and not removed.canceled
                and removed.change_type is SpatialChangeType.OBJECT_REMOVED and removed.object_uuid in destroyed_ids):
            assert removed.object_uuid is not None
            removal_starts.setdefault(removed.object_uuid, version.source_index)
    pending_removals = iter(sorted(removal_starts.items(), key=lambda row: row[1]))
    next_removal = next(pending_removals, None)
    destroyed_contacts: dict[UUID, PlayerObject] = {}
    # An interaction may itself hide the object. Retain its already granted
    # identity at entry; a remote control's undisclosed target gains no identity.
    observed_objects = {identity for identity in private_world.objects if _object_observed(private_world, identity)}
    for event in events:
        while next_removal is not None and next_removal[1] <= indexes[event.uuid]:
            identity = next_removal[0]
            if identity in private_world.objects and _object_observed(private_world, identity):
                destroyed_contacts[identity] = _observed_object(private_world, remembered, identity)
            next_removal = next(pending_removals, None)
        while next_delivery is not None and next_delivery[1] <= indexes[event.uuid]:
            delivery_declarations[next_delivery[0]] = private_world.senses
            next_delivery = next(pending_deliveries, None)
        while admission is not None and indexes[admission.event_uuid] <= indexes[event.uuid]:
            private_actors[admission.actor.uuid] = admission.actor
            observed = _public_actor(admission.actor, observer)
            observations.append(PlayerObservation(event_uuid=admission.event_uuid, actor=observed, contact=admission.contact))
            remembered.actors[observed.uuid] = observed
            admission = next(pending, None)
        if not event.canceled:
            if isinstance(event, EntityCreatedEvent):
                private_actors[event.entity_uuid] = actor_from_birth(event)
            owner = actor_fact_owner(event)
            if owner is not None and owner in private_actors:
                private_actors[owner] = apply_actor_fact(private_actors[owner], event, facts.get(event.uuid))
            world_changed = apply_world_fact(private_world, event, facts.get(event.uuid))
            if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer:
                # Native spatial commits publish their sensory child before
                # their own completion. Its exact recorded parent after-value
                # was already true when this contact/visibility was captured.
                parent = event.parent_lineage
                while parent is not None and parent in by_lineage:
                    ancestor = by_lineage[parent]
                    if isinstance(ancestor, SpatialChangeEvent) and ancestor.change_type is SpatialChangeType.OBJECT_CHANGED:
                        apply_world_fact(private_world, ancestor)
                    parent = ancestor.parent_lineage
                private_world.senses = reduce_senses_snapshot(observer, private_world.senses, event)
                world_changed = True
            if world_changed:
                update = _world_update(private_world, remembered, event.uuid)
                if update is not None:
                    updates.append(update)
        if (isinstance(event, ActionEvent) and event.source_item_uuid is not None
                and event.source_item_uuid in private_world.objects
                and _object_observed(private_world, event.source_item_uuid)):
            observed_objects.add(event.source_item_uuid)
        fact = _project_fact(event, observer, private_actors, facts.get(event.uuid), events, admissions,
                            set(remembered.actors), observed_objects, private_world.senses,
                            delivery_declarations.get(event.lineage_uuid))
        if (isinstance(event, TakeDamageEvent) and not event.canceled
                and event.final_damage is not None and event.resulting_hp is not None):
            identity = event.target_entity_uuid
            if identity is not None and (
                    identity in private_world.objects
                    and private_world.objects[identity].item.integrity is ItemIntegrity.INTACT
                    and _object_observed(private_world, identity)
                    or identity in destroyed_contacts):
                components = event.resolution.components if event.resolution is not None else ()
                fact = ObjectDamageFact(object_uuid=identity, applied_damage=event.final_damage,
                    resulting_hp=event.resulting_hp,
                    damage_type=components[0].damage_type if len(components) == 1 else None)
        if (isinstance(event, ItemDestructionEvent) and not event.canceled
                and event.resulting_state is not None and event.resulting_state.integrity is ItemIntegrity.DESTROYED):
            destroyed = destroyed_contacts.get(event.item_uuid)
            if destroyed is not None:
                fact = ObjectDestroyedFact(object_uuid=destroyed.item.item_uuid,
                    placement=destroyed.placement, item_id=destroyed.item.item_id,
                    remnant_state=event.resulting_state.remnant_state,
                    destruction_outcome=event.resulting_state.destruction_outcome)
        if (isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED
                and event.item_state.item_uuid not in explicit_destructions):
            destroyed = destroyed_contacts.get(event.item_state.item_uuid)
            if destroyed is not None:
                replacement = event.replacement_item_uuid
                if (replacement is None or replacement not in private_world.objects
                        or not _object_observed(private_world, replacement)):
                    replacement = None
                fact = ObjectDestroyedFact(object_uuid=destroyed.item.item_uuid,
                    replacement_uuid=replacement, placement=destroyed.placement, item_id=destroyed.item.item_id,
                    remnant_state=event.item_state.remnant_state)
        nodes.append(PlayerNode(uuid=event.uuid, lineage_uuid=event.lineage_uuid,
            parent_event=event.parent_event, parent_lineage=event.parent_lineage,
            children_lineages=tuple(event.children_lineages), phase=event.phase,
            canceled=event.canceled, fact=fact, combat_log=event.combat_log,
            cancellation=ActionCancellation(phase=event.canceled_from_phase,
                action_economy_spent=event.action_economy_spent, outcome_code=event.outcome_code)
                if event.canceled and isinstance(event, ActionEvent) and fact is not None else None))
    disclosed = {node.lineage_uuid for node in nodes if node.fact is not None}
    nodes = [replace(node, content_attributions=_content_attributions(event, node.fact, observer, disclosed))
             for node, event in zip(nodes, events, strict=True)]
    return tuple(nodes), tuple(observations), tuple(updates)


@dataclass(slots=True)
class ProjectionState:
    """Private recorded aggregates and last-observed memory for one observer."""

    world: PresentationTarget
    actors: dict[UUID, ActorState]
    remembered: PlayerState


def begin_projection(initialization: IntervalEnvelope) -> tuple[ProjectionState, PlayerInitialization]:
    """Start a projection from recorded initialization; no native queries."""
    world_event = next((event for _, event in initialization.admitted if isinstance(event, WorldInitializedEvent)), None)
    if world_event is None:
        raise ValueError("player projection requires recorded world initialization")
    world = PlayerWorld(battlefield_id=world_event.battlefield_id, battlefield_name=world_event.battlefield_name,
        bounds=world_event.bounds, width=world_event.width, height=world_event.height)
    private_world = PresentationTarget(generation=initialization.generation, observer_uuid=initialization.observer_uuid)
    remembered = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid, world=world)
    actors: dict[UUID, ActorState] = {}
    versions = _versions(initialization.objective_rows)
    nodes, observations, updates = _project_nodes(tuple(event for _, event in initialization.admitted),
        versions, initialization.admissions, initialization.conditions, private_world, actors, remembered)
    initial = PlayerInitialization(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
        world=world, nodes=nodes, version_rows=versions, end_cursor=initialization.end_cursor,
        observations=observations, world_updates=updates)
    return ProjectionState(private_world, actors, remembered), initial


def project_lineage(state: ProjectionState, lineage: CompletedLineage) -> PlayerLineage | None:
    """Advance the same private projection memory over one closed root."""
    if state.world.generation != lineage.generation or state.world.observer_uuid != lineage.observer_uuid:
        raise ValueError("recorded lineage belongs to another projection")
    versions = _versions(lineage.objective_rows)
    nodes, observations, updates = _project_nodes(lineage.events, versions, lineage.admissions,
        lineage.conditions, state.world, state.actors, state.remembered)
    if not observations and not updates and not any(node.fact is not None or node.combat_log is not None
                                                   or node.content_attributions for node in nodes):
        return None
    root = next(node for node in nodes if node.uuid == lineage.root.uuid)
    return PlayerLineage(generation=lineage.generation, observer_uuid=lineage.observer_uuid,
        root=root, events=nodes, version_rows=versions, start_cursor=lineage.start_cursor,
        end_cursor=lineage.end_cursor, observations=observations, world_updates=updates)


def project_sequence(native: RecordedSequence) -> PlayerSequence:
    """Produce one observer's packet entirely from their private saved capture."""
    state, initial = begin_projection(native.initialization)
    return PlayerSequence(initialization=initial, lineages=tuple(
        projected for row in native.lineages if (projected := project_lineage(state, row)) is not None))
